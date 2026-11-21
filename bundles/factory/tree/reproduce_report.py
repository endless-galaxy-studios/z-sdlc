"""Check a reproduce run's result and write its issue comment (factory-implement.yml's reproduce-report job; D6
rule 8). Runs on a GitHub-hosted runner, from the default branch's checkout, so nothing the agent touched runs here.

Usage: python3 -I reproduce_report.py <result.json> <issue> <run-url> <out-dir>

The result is the agent's (reproduce.schema.json): every text field is checked like any agent text (no
credential-like string, no image or embed) and posted as literal text, and the spec is posted in a fenced block
whose fence the writer picks, longer than any run of backticks in it. The browser evidence links come from the
same place as a PR's (EVIDENCE_MANIFEST, EVIDENCE_REPORT, EVIDENCE_VIDEO, EVIDENCE_TRACE; implement_guard.py), so
the writer builds them itself.

Writes <out-dir>/comment.md and <out-dir>/next: `plan` when the run reproduced the bug, partly reproduced it or was
blocked (planning goes on; a blocked run says the cause is unconfirmed), `needs-input` when it didn't reproduce
it (CD answers before any plan is written, and the reply restarts the reproduce step). Exits 1 on a result it
won't post, saying why.
"""

import json
import pathlib
import re
import sys

# The shared renderer and checks sit beside this script, in the default branch's checkout.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import implement_guard as guard  # noqa: E402

STATUSES = {"reproduced", "partially-reproduced", "not-reproduced", "blocked"}
INVISIBLE = re.compile("[\u0000-\u0008\u000b-\u001f\u007f-\u009f\u061c\u200b-\u200f\u202a-\u202e\u2060-\u2069\ufeff]")
CI = {"yes", "no", "unknown"}
# A kept spec: repro-<issue>-<slug>.spec.<ext> at a plain relative path (process/factory.md § Reproducing in a
# browser).
SPEC_PATH = re.compile(r"([A-Za-z0-9_.-]+/)*repro-[0-9]+-[a-z0-9][a-z0-9-]{0,60}\.spec\.(ts|tsx|js|mjs|cjs)")
HEADLINE = {
    "reproduced": "**Reproduced in a real browser.** Planning starts from the failing spec below.",
    "partially-reproduced": "**Partly reproduced in a real browser.** Planning starts from what the spec below shows; "
                            "the summary says which part didn't reproduce.",
    "not-reproduced": "**Not reproduced.** The steps and variations below all behaved, so nothing is planned yet.",
    "blocked": "**Not confirmed: the reproduce step was blocked.** Planning goes on, with the cause unconfirmed.",
}


class Refused(Exception):
    pass


def check(result):
    """The result against reproduce.schema.json's rules and the writer's own. Raises Refused."""
    keys = {"status", "summary", "reason", "tried", "failed_requests", "spec", "ci_runs_spec"}
    if not isinstance(result, dict) or set(result) != keys:
        raise Refused(f"the result must have exactly {sorted(keys)}")
    if result["status"] not in STATUSES:
        raise Refused(f"unknown status {result['status']!r}")
    if result["ci_runs_spec"] not in CI:
        raise Refused("ci_runs_spec must be yes, no or unknown")
    for key, cap in (("summary", 1500), ("reason", 500)):
        if not isinstance(result[key], str) or len(result[key]) > cap:
            raise Refused(f"{key} must be text of at most {cap} characters")
    if not result["summary"].strip():
        raise Refused("summary is empty")
    for key, most in (("tried", 10), ("failed_requests", 30)):
        items = result[key]
        if not isinstance(items, list) or len(items) > most \
                or not all(isinstance(x, str) and 0 < len(x) <= 300 for x in items):
            raise Refused(f"{key} must be at most {most} lines of at most 300 characters")
    spec = result["spec"]
    if not isinstance(spec, dict) or set(spec) != {"path", "content"} \
            or not all(isinstance(spec[k], str) for k in spec) or len(spec["content"]) > 20000:
        raise Refused("spec must be {path, content}, the content at most 20000 characters")
    if bool(spec["path"]) != bool(spec["content"].strip()):
        raise Refused("a spec needs both its path and its content")
    if spec["path"] and (not SPEC_PATH.fullmatch(spec["path"]) or ".." in spec["path"].split("/")):
        raise Refused(f"the spec's path isn't repro-<issue>-<slug>.spec.<ext> at a plain relative path: "
                      f"{spec['path'][:80]!r}")
    if result["status"] in ("reproduced", "partially-reproduced") and not spec["path"]:
        raise Refused(f"a {result['status']} result needs the spec that shows it")
    if result["status"] in ("blocked", "not-reproduced") and not result["reason"].strip():
        raise Refused(f"a {result['status']} result says why in reason")
    if result["status"] == "not-reproduced" and not result["tried"]:
        raise Refused("a not-reproduced result lists what was tried")
    texts = [result["summary"], result["reason"], spec["path"], *result["tried"], *result["failed_requests"]]
    for t in texts + [spec["content"]]:
        if guard.TOKEN.search(t):
            raise Refused("the result contains a credential-like string")
        try:
            t.encode("utf-8")
        except UnicodeEncodeError:
            raise Refused("the result has text that isn't UTF-8")
    # Code CD and the planner read must show what it does: no bidirectional or other invisible control characters
    # (a Trojan-source spec reads one way and runs another), and no control characters but newline and tab.
    if INVISIBLE.search(spec["content"]):
        raise Refused("the spec holds bidirectional or other invisible control characters")
    # The spec is posted as code, which renders no image; everything else is posted as text.
    for t in texts:
        if guard.EMBED.search(t):
            raise Refused("the result contains an image or embed")


def fenced(content):
    """The content in a fenced block whose fence is longer than any run of backticks in it."""
    longest = max((len(m) for m in re.findall(r"`+", content)), default=0)
    fence = "`" * max(3, longest + 1)
    return [fence + "ts", content.rstrip("\n"), fence]


def comment(result, issue, run_url, evidence=(), spec_text=True):
    status = result["status"]
    lines = []
    if status == "not-reproduced":
        # Stage marker first (D1 rule 5): CD's reply restarts the reproduce step.
        lines.append("<!-- factory-stage: reproduce -->")
    lines += [f"<!-- factory-reproduce: {json.dumps({'status': status, 'ci': result['ci_runs_spec']})} -->", "",
              HEADLINE[status], "", guard.literal(result["summary"])]
    if result["reason"].strip():
        label = "What blocked it" if status == "blocked" else "What would change it" \
            if status == "not-reproduced" else "Note"
        lines += ["", f"**{label}:** {guard.literal(result['reason'])}"]
    if result["tried"]:
        lines += ["", "### What was tried", ""] + [f"{i}. {guard.literal(t)}" for i, t in enumerate(result["tried"], 1)]
    lines += ["", "### Requests that failed", ""]
    lines += guard.bullets(result["failed_requests"]) or ["None."]
    if evidence:
        lines += ["", "### Browser evidence", ""] + list(evidence)
    spec = result["spec"]
    if spec["path"]:
        ci = {"yes": "The project's CI runs a spec at that path.",
              "no": "The project's CI doesn't run it: the spec is this step's own evidence.",
              "unknown": "Whether the project's CI runs it wasn't found."}[result["ci_runs_spec"]]
        lines += ["", "### The reproducing spec", "",
                  f"`{spec['path']}`, not committed: the plan and its execution keep it. {ci}", ""]
        lines += fenced(spec["content"]) if spec_text else [
            "_Too long to post with the rest: it's in the run's `reproduce-transcript` artifact (7 days)._"]
    if status == "not-reproduced":
        lines += ["", "_Reply on this issue with what the steps above are missing (data, an account, a setting, other "
                      "steps) to run the reproduce step again, or move the issue on yourself._"]
    lines += ["", f"<sub>factory reproduce · issue #{issue} · [run]({run_url})</sub>"]
    return "\n".join(lines) + "\n"


def video_flag(record, status):
    """A reproduce run records video (process/factory.md D6 rules 5 and 7): said when this one kept none. A blocked
    run is exempt, and a record evidence_lines can't read is said there already."""
    if status == "blocked":
        return []
    try:
        rec = guard.evidence_record(record) if (record or "").strip() else None
    except (guard.Refused, TypeError, KeyError, AttributeError, ValueError, RecursionError):
        return []
    if rec and rec["video"]:
        return []
    return ["- **No video:** this reproduce run kept none (D6 rules 5 and 7), so its result rests on its screenshots "
            "and trace, if any."]


def main():
    import os
    result_path, issue, run_url, out_dir = sys.argv[1:5]
    out = pathlib.Path(out_dir)
    try:
        if not issue.isascii() or not issue.isdigit():
            raise Refused("bad issue number")
        result = json.loads(pathlib.Path(result_path).read_text())
        check(result)
        record = os.environ.get("EVIDENCE_MANIFEST", "")
        evidence = guard.evidence_lines(record,
                                        {k: os.environ.get(f"EVIDENCE_{k.upper()}", "") for k in ("report", "video", "trace")},
                                        run_url, issue, guard.evidence_archive())
        evidence = video_flag(record, result["status"]) + list(evidence)
        body = comment(result, issue, run_url, evidence)
        if len(body.encode()) > guard.MAX_POST:
            # The spec is the one part that can be long: post the rest rather than lose the run.
            body = comment(result, issue, run_url, evidence, spec_text=False)
        if len(body.encode()) > guard.MAX_POST:
            raise Refused(f"the comment would be {len(body.encode())} bytes (cap {guard.MAX_POST})")
    except (Refused, ValueError, OSError, KeyError, TypeError, AttributeError) as e:
        print(f"::error::reproduce output refused: {e}")
        return 1
    out.mkdir(parents=True, exist_ok=True)
    (out / "comment.md").write_text(body)
    nxt = "needs-input" if result["status"] == "not-reproduced" else "plan"
    (out / "next").write_text(nxt + "\n")
    print(f"reproduce: {result['status']}, next {nxt}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
