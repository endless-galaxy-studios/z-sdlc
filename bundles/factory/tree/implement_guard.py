"""Check an implement run's output before the factory pushes it (factory-implement.yml, publish job).

Usage: python3 -I implement_guard.py <bundle> <base-sha> <result.json> <issue-number> <run-url> <out-dir> [<stage> [<stats.json>]]

<stage> is implement (the default) or execute, which publish code; revise, which adds commits to an open
factory code PR (the base is the PR's head; REVISION, REVISION_LIMIT and, for an execution PR, PLAN and
NEXT_GATE in the environment) and renders the revision comment instead of a PR body; or
plan or spec, which publish a
document for CD to approve by merging: those may touch only docs/ and the discipline parking lots, return `awaiting-approval` with
the deliverable ID and document path, and reference the issue (`Refs #n`) rather than close it; or split, the same
for a split record: status `split` with the parts, which must match the split record's parts table and the
catalog rows at the head (catalog.py reads both).

Runs on a GitHub-hosted runner, in a fresh checkout of the default branch at <base-sha>, so nothing
the agent touched runs here: a bundle carries objects and refs only, never config or hooks. Refuses:
- a bundle that doesn't verify, or whose commits don't sit on <base-sha> as a straight line (no
  merges), or with no commits or too many;
- any commit touching a path covered by .github/CODEOWNERS (read here, from the default branch): the
  gate's own config and the agents' configuration need CD's review, never the factory's. As on
  GitHub, the last matching line decides, and a line with no owner leaves its paths unowned (the
  discipline parking lots, which agents write);
- symlinks and submodules; a file version over the size cap, in any commit (unless the file was
  already over it on the base: the SDLC changelog); patches over the size cap; token-shaped strings
  in any file version's bytes, any path, or any commit's message or author;
- a result that breaks the output rules, or carries token-shaped strings, images or embeds;
- a PR brief that doesn't match its schema's caps, leaves a required section empty, names an unsafe
  path, or runs far past its word budget.

On success it fetches the commits to refs/factory/head and writes <out-dir>/head (the commit SHA),
<out-dir>/title and <out-dir>/pr-body.md. Every refusal is printed as ::error:: and exits 1.

The PR body follows ops/sdlc/templates/pr_description_template.md. This script renders it from the
result's `brief` fields in a fixed order, and agent text is literal: one line per field, every ASCII
punctuation mark escaped outside `code spans`, so only this script makes headings, lists and the
collapsed agent record. <stats.json> is the run's cost, turns and models, read from the runtime's
record in the agent job; without it the record says they weren't recorded.
"""

import json
import os
import pathlib
import re
import subprocess
import sys

# The shared catalog reader sits beside this script, in the base checkout (never the agent's tree).
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import catalog  # noqa: E402

MAX_COMMITS = 20
MAX_FILES = 40
MAX_DIFF_BYTES = 400_000
MAX_BLOB_BYTES = 200_000
TOKEN = re.compile(r"sk-ant-|gh[pousr]_[A-Za-z0-9_]{20}|github_pat_|ctx7sk|-----BEGIN [A-Z ]*PRIVATE KEY-----")
EMBED = re.compile(r"!\[|<\s*(img|picture|source|video|audio|svg|iframe|object|embed)\b", re.I)
SYMLINK, GITLINK = "120000", "160000"
# Agent and gate configuration, refused at any depth whatever CODEOWNERS says: an owner-less
# CODEOWNERS line must never be able to unown a nested copy (e.g. ops/sdlc/disciplines/x.md/CLAUDE.md).
CONFIG_DIRS = {".claude", ".github", ".git"}
CONFIG_FILES = {"claude.md", "claude.local.md", ".mcp.json"}


GATE_ID = re.compile(r"^G[1-9][0-9]?$")


CATALOG = ".github/factory/production/ops.json"


def read_catalog():
    """The operations catalog's text, or None for a project without a production tier (D4: the tier and its
    catalog are the project's own, and the factory bundle doesn't install them)."""
    path = pathlib.Path(CATALOG)
    return path.read_text() if path.exists() else None


def plan_gate_lines(plan_text, catalog_text):
    """The plan's production gates, checked against the operations catalog (gates.py), as PR body lines.
    A plan whose gates break the rules is refused here, before CD is asked to approve it. Without a catalog
    (catalog_text None) the project has no production tier, so a plan may have no gates: CD gates run
    through the production broker too."""
    import gates  # noqa: E402 (beside this file)
    if catalog_text is None:
        try:
            found = gates.parse_gates(plan_text)
        except gates.Invalid as e:
            raise Refused(f"the plan's production gates break the rules: {e}") from None
        if found:
            raise Refused(f"the plan has production gates ({', '.join(g['id'] for g in found)}), but this project "
                          f"has no production tier ({CATALOG}), which every gate runs through, CD's included")
        return []
    catalog = gates.load_catalog(catalog_text)
    errors = gates.check_plan(plan_text, catalog)
    if errors:
        raise Refused("the plan's production gates break the rules: " + "; ".join(errors)[:600])
    lines = []
    for g in gates.parse_gates(plan_text):
        if g["block"] is None:
            lines.append(f"- **{g['id']}: {literal(g['title'])}.** You run its runbook, then approve the gate run.")
            continue
        ops = ", ".join(f"`{s['op']}`" for s in g["block"]["steps"])
        rb = ", ".join(f"`{s['op']}`" for s in g["block"].get("rollback", [])) or "none"
        lines.append(f"- **{g['id']}: {literal(g['title'])}.** The production runner runs {ops}; rollback: {rb}.")
    return lines


def agent_config(path):
    parts = path.split("/")
    return any(part in CONFIG_DIRS for part in parts[:-1]) or parts[-1].lower() in CONFIG_FILES \
        or parts[-1] in CONFIG_DIRS
CODE_STAGES = ("implement", "execute")
DOC_STAGES = ("plan", "spec", "split")
SPLIT_DOC = re.compile(r"^docs/current_work/planning/(d\d+)_[a-z0-9_]+_split\.md$")
DOC_PREFIX = "docs/"
# What a document stage may change: its documents, and the discipline parking lots agents write to.
DOC_STAGE_PATHS = (DOC_PREFIX, "ops/sdlc/disciplines/", "ops/sdlc/knowledge/", "ops/sdlc/process/sdlc_changelog.md")
# SDLC files future agents read: every change to one is named in the PR (Review focus).
SDLC_HYGIENE = ("ops/sdlc/disciplines/", "ops/sdlc/knowledge/")
FOLLOW_UP_ID = re.compile(r"^F([1-9]|10)$")
# Writer markers around the follow-up checklist; factory-follow-ups.yml parses between them.
FOLLOW_UPS_OPEN, FOLLOW_UPS_CLOSE = "<!-- factory-follow-ups v1 -->", "<!-- /factory-follow-ups -->"
DELIVERABLE = re.compile(r"^D\d+[a-z]?$")
# The PR brief. Its caps per field live in the stage's schema (checked at generation by the CLI and
# again here); the total is measured against the template's target, and refused only far past it.
SCHEMAS = {"plan": "plan.schema.json", "spec": "plan.schema.json", "split": "plan.schema.json",
           "implement": "implement.schema.json", "execute": "implement.schema.json",
           "revise": "revise.schema.json"}
REVISE_ACTIONS = {"done": "Done", "declined": "Declined", "needs-your-call": "Needs your call"}
WORD_TARGET = {"plan": 450, "spec": 450, "split": 450, "implement": 500, "execute": 500}
WORD_LIMIT_FACTOR = 2
TIERS = ("low", "medium", "high")
SAFE_PATH = re.compile(r"^[A-Za-z0-9_.@+-]+(?:/[A-Za-z0-9_.@+-]+)*$")
PUNCT = re.compile(r"([!-/:-@\[-`{-~])")
CODE_SPAN = re.compile(r"`([^`]{1,200})`")
# Control characters, and characters that reorder or hide text in what GitHub shows.
INVISIBLE = re.compile(r"[\x00-\x08\x0e-\x1b\x7f\u202a-\u202e\u2066-\u2069]")
MODEL = re.compile(r"^claude-[a-z0-9.-]{1,60}$")
# The deliverable's documents, lite (sdlc-lite/, moved to completed/) or full tier (specs/, planning/, results/).
LITE_DOC = re.compile(r"^docs/current_work/(?:sdlc-lite/(?:completed/)?|specs/|planning/|results/)"
                      r"d\d+[a-z]?_[a-z0-9_]+_(plan|result|spec)\.md$")


class Refused(Exception):
    pass


def git(*args, binary=False):
    """git with hooks and fsmonitor off; raises on failure."""
    out = subprocess.run(["git", "-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false", *args],
                         capture_output=True, check=False)
    if out.returncode:
        raise Refused(f"git {' '.join(args[:2])} failed: {out.stderr.decode(errors='replace').strip()[:300]}")
    return out.stdout if binary else out.stdout.decode()


def codeowners_patterns(text):
    """CODEOWNERS paths as regexes (gitignore rules: a leading or inner slash anchors at the root,
    otherwise the name matches at any depth; an owned pattern also covers everything under a
    directory). Each entry is (pattern, regex, owned): a line with no owner unowns exactly the files
    it names, never anything beneath them, which is stricter than GitHub."""
    patterns = []
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        pattern, *owners = line.split()
        if any(c in pattern for c in "[]\\!"):
            raise Refused(f"CODEOWNERS pattern this check can't evaluate: {pattern}")
        anchored = pattern.startswith("/") or "/" in pattern.strip("/")
        body = pattern.strip("/")
        regex, i = "", 0
        while i < len(body):
            if body.startswith("**/", i):
                regex, i = regex + "(?:.*/)?", i + 3
            elif body.startswith("**", i):
                regex, i = regex + ".*", i + 2
            elif body[i] == "*":
                regex, i = regex + "[^/]*", i + 1
            elif body[i] == "?":
                regex, i = regex + "[^/]", i + 1
            else:
                regex, i = regex + re.escape(body[i]), i + 1
        suffix = "(?:/.*)?$" if owners else "$"
        patterns.append((pattern, re.compile(("^" if anchored else "^(?:.*/)?") + regex + suffix), bool(owners)))
    if not patterns:
        raise Refused("CODEOWNERS has no patterns")
    return patterns


def protected(path, patterns):
    """The owning pattern, or None. The last matching line wins, as on GitHub."""
    match = next(((p, owned) for p, rx, owned in reversed(patterns) if rx.match(path)), None)
    return match[0] if match and match[1] else None


def strings(value):
    """Every string in a JSON value, at any depth."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for v in value:
            yield from strings(v)
    elif isinstance(value, dict):
        for v in value.values():
            yield from strings(v)


def conforms(value, schema, where):
    """The brief against its schema: exact fields, types, enums and the caps (maxLength, maxItems)."""
    kind = schema.get("type")
    if kind == "object":
        if not isinstance(value, dict) or set(value) != set(schema["properties"]):
            raise Refused(f"{where} doesn't have the schema's fields")
        for key, sub in schema["properties"].items():
            conforms(value[key], sub, f"{where}.{key}")
    elif kind == "array":
        if not isinstance(value, list):
            raise Refused(f"{where} isn't a list")
        if len(value) > schema.get("maxItems", len(value)):
            raise Refused(f"{where} has {len(value)} items (cap {schema['maxItems']})")
        for i, item in enumerate(value):
            conforms(item, schema["items"], f"{where}[{i}]")
    elif kind == "string":
        if not isinstance(value, str):
            raise Refused(f"{where} isn't a string")
        if len(value) > schema.get("maxLength", len(value)):
            raise Refused(f"{where} is {len(value)} characters (cap {schema['maxLength']})")
        if "enum" in schema and value not in schema["enum"]:
            raise Refused(f"{where} isn't one of {schema['enum']}")
    else:
        raise Refused(f"{where}: schema type {kind!r} this check can't evaluate")


def result_schema(stage):
    return json.loads((pathlib.Path(__file__).resolve().parent / SCHEMAS[stage]).read_text())


def brief_schema(stage):
    return result_schema(stage)["properties"]["brief"]


def check_extras(result, stage):
    """Add-ons and follow-ups (code stages): the schema's shape and caps, ids F1.. in order, and
    one-line titles. Returns their strings for the token and embed scan."""
    if stage not in CODE_STAGES:
        return []
    props = result_schema(stage)["properties"]
    conforms(result.get("add_ons"), props["add_ons"], "add_ons")
    conforms(result.get("follow_ups"), props["follow_ups"], "follow_ups")
    for i, f in enumerate(result["follow_ups"], 1):
        if f["id"] != f"F{i}" or not FOLLOW_UP_ID.match(f["id"]):
            raise Refused(f"follow_ups[{i - 1}].id must be F{i}")
        if not f["title"].strip() or "\n" in f["title"]:
            raise Refused(f"follow-up {f['id']} has an empty or multi-line title")
    for a in result["add_ons"]:
        if not a["what"].strip() or not a["paths"]:
            raise Refused("an add-on needs what it is and the files it changed")
    return list(strings(result["add_ons"])) + list(strings(result["follow_ups"]))


def check_add_on_paths(result, paths, stage):
    """Every add-on names only files this PR changes."""
    if stage not in CODE_STAGES:
        return
    for a in result["add_ons"]:
        for path in a["paths"]:
            if path not in paths:
                raise Refused(f"add-on {a['what'][:40]!r} names {path[:80]!r}, which this PR doesn't change")


def brief_words(brief):
    return sum(len(s.split()) for s in strings(brief))


def check_brief(brief, stage):
    """The PR description's sections (ops/sdlc/templates/pr_description_template.md): the schema's
    shape and caps, every section a PR needs filled, safe paths, and the word budget."""
    conforms(brief, brief_schema(stage), "brief")
    missing = [name for name, filled in (
        ("problem", brief["problem"].strip()),
        ("decisions", brief["decisions"] and all(d["choice"].strip() for d in brief["decisions"])),
        ("scope.tackled", any(s.strip() for s in brief["scope"]["tackled"])),
        ("risk.why", brief["risk"]["why"].strip()),
        ("risk.undo", brief["risk"]["undo"].strip()),
        ("review_focus", any(s.strip() for s in brief["review_focus"])),
        ("verification", any(s.strip() for s in brief["verification"])),
        ("how_it_works", brief["how_it_works"].strip()),
        ("files", brief["files"]),
        ("scope_integrity", stage in DOC_STAGES or brief["scope_integrity"].strip()),
    ) if not filled]
    if brief["risk"]["tier"] not in TIERS:
        missing.append("risk.tier")
    if stage in DOC_STAGES and any(not d["rejected"].strip() for d in brief["decisions"]):
        missing.append("decisions[].rejected")
    if missing:
        raise Refused(f"the PR brief leaves {', '.join(missing)} empty")
    for f in brief["files"]:
        if not SAFE_PATH.match(f["path"]) or {".", ".."} & set(f["path"].split("/")):
            raise Refused(f"brief.files has a path this check won't render: {f['path'][:80]!r}")
    words, limit = brief_words(brief), WORD_TARGET[stage] * WORD_LIMIT_FACTOR
    if words > limit:
        raise Refused(f"the PR brief is {words} words (target {WORD_TARGET[stage]}, limit {limit})")


def check_revise_result(result, plan="", next_gate=""):
    """A revision's result: the schema's shape and caps, something to report, and no tokens or embeds. A
    revision of an execution PR (<plan>, the plan it executes) that leaves nothing open for CD may stop before
    the plan's next gate this PR hasn't passed (<next_gate>), as the execute stage does: awaiting-approval,
    naming that gate."""
    if not isinstance(result, dict) or result.get("status") not in ("done", "escalated", "awaiting-approval"):
        raise Refused(f"nothing to publish for revise status {result.get('status') if isinstance(result, dict) else None!r}")
    props = result_schema("revise")["properties"]
    for key in ("gate", "reason", "summary", "responses", "verification", "findings", "follow_ups"):
        conforms(result.get(key), props[key], key)
    if not result["summary"].strip() or not result["responses"]:
        raise Refused("a revision needs a summary and a response to each request")
    orch = result.get("orchestrator")
    if not isinstance(orch, dict) or not isinstance(orch.get("review_rounds"), int) \
            or not isinstance(orch.get("agents"), list) or not all(isinstance(a, str) for a in orch["agents"]):
        raise Refused("the orchestrator record is malformed")
    for t in list(strings({k: result[k] for k in props if k != "orchestrator"})) + orch["agents"]:
        if TOKEN.search(t):
            raise Refused("the result contains a credential-like string")
        if EMBED.search(t):
            raise Refused("the result contains an image or embed")
    serious = any(f["severity"] in ("critical", "major") for f in result["findings"])
    if (result["status"] == "escalated") != serious:
        raise Refused("escalated if and only if a critical or major finding is open")
    if result["status"] == "awaiting-approval":
        if not plan:
            raise Refused("only a revision of an execution PR stops at a production gate")
        if not next_gate or result["gate"] != next_gate:
            raise Refused(f"a revision stops only before the plan's next gate ({next_gate or 'none left'}), "
                          f"not {result['gate']!r}")
        if any(r["action"] == "needs-your-call" for r in result["responses"]):
            raise Refused("a revision that leaves a request for CD's call doesn't stop at a gate (that is done)")
    elif result["gate"]:
        raise Refused("only a revision stopped at a production gate names a gate")


def revise_comment(result, revision, limit, run_url, paths, stats=None):
    """The revision comment on the PR. The writer's marker opens it; factory-revise.yml counts them."""
    lines = [f"<!-- factory-revise: {revision} -->", "",
             f"**Revision {revision} of {limit}:** {literal(result['summary'])}", ""]
    if result["status"] == "escalated":
        lines += [f"**Escalated:** {literal(result['reason'])} The open findings are below.", ""]
    if result["status"] == "awaiting-approval":
        lines += [f"**Stopped before production gate {escape(result['gate'])}.** The work before it is done and nothing "
                  "is open for you, so the factory asks for the gate: the gate tracker on this PR shows the request. "
                  "Approve its gate run when you want it to run; to change the code first, request changes again.", ""]
    lines += ["### What you asked for", ""]
    for i, r in enumerate(result["responses"], 1):
        lines.append(f"{i}. **{literal(r['request'])}**: {REVISE_ACTIONS[r['action']]}. {literal(r['note'])}")
    if result["verification"]:
        lines += ["", "### How it was verified", ""] + bullets(result["verification"])
    serious = [f for f in result["findings"] if f["severity"] in ("critical", "major")]
    minor = [f for f in result["findings"] if f["severity"] == "minor"]
    if serious:
        lines += ["", "### Open findings", ""]
        lines += [f"- **{f['severity'].capitalize()}** at {literal(f['location'])}: {literal(f['summary'])}" for f in serious]
    if result["follow_ups"]:
        lines += ["", "### For later (file by hand if you want them)", ""]
        lines += [f"- **{literal(f['title'])}**: {literal(f['summary'])}" for f in result["follow_ups"]]
    orch = result["orchestrator"]
    record = [f"- **Review rounds:** {orch['review_rounds']}; agents: {literal(', '.join(orch['agents'])) or 'none'}",
              f"- **Models and cost:** {run_stats(stats) or 'not recorded'}",
              f"- **Files changed in this revision:** {len(paths)}"] + [f"  - `{p}`" for p in paths[:20]]
    if minor:
        record += ["", "**Open minor findings**", ""] + [f"- {literal(f['location'])}: {literal(f['summary'])}" for f in minor]
    lines += ["", "<details><summary>Agent record</summary>", ""] + record + ["", "</details>", "",
              f"<sub>factory revise · [run]({run_url}) · request changes again for another revision "
              f"({limit - revision} left)</sub>"]
    return "\n".join(lines) + "\n"


def check_split(result):
    """A split result: a split record for this deliverable, and parts that follow the split rules.
    Returns the parts' strings for the token and embed scan."""
    m = SPLIT_DOC.match(result.get("document") or "")
    if not m or m.group(1) != str(result.get("deliverable", "")).lower():
        raise Refused("a split needs its split record at docs/current_work/planning/dNN_name_split.md, for its deliverable")
    conforms(result.get("parts"), result_schema("split")["properties"]["parts"], "parts")
    try:
        catalog.check_parts(result["deliverable"], result["parts"])
    except ValueError as e:
        raise Refused(f"split parts: {e}")
    return list(strings(result["parts"]))


def check_split_docs(result, read, spec_exists=lambda path: pathlib.Path(path).is_file()):
    """The split record's parts table and the catalog at the head agree with the result. `read` returns
    a file's text at the head; `spec_exists` says whether a reused spec is approved (on the default
    branch, this checkout)."""
    for p in result["parts"]:
        if p["spec"] and not spec_exists(p["spec"]):
            raise Refused(f"{p['part']} reuses {p['spec']}, which isn't an approved spec on the default branch")
    try:
        table = catalog.split_parts(read(result["document"]))
        rows = catalog.catalog_rows(read("docs/_index.md"))
        key = lambda p: (p["part"], p["tier"], p["depends_on"], p["spec"])
        if [key(p) for p in table] != [key(p) for p in result["parts"]]:
            raise Refused("the split record's parts table doesn't match the result's parts")
        parent = result["deliverable"]
        if parent not in rows:
            raise Refused(f"the catalog has no row for {parent}")
        missing = [p["part"] for p in result["parts"] if p["part"] not in catalog.ids(rows[parent]["Depends on"])]
        if missing:
            raise Refused(f"the catalog's {parent} row doesn't depend on its parts {missing}")
        for p in result["parts"]:
            row = rows.get(p["part"])
            if row is None:
                raise Refused(f"the catalog has no row for {p['part']}")
            if catalog.ids(row["Depends on"]) != p["depends_on"]:
                raise Refused(f"the catalog's {p['part']} row doesn't depend on {p['depends_on']}")
    except (KeyError, ValueError) as e:
        raise Refused(f"split documents: {e}")


def check_result(result, stage="implement"):
    publishable = ("done", "escalated") if stage in CODE_STAGES else ("split",) if stage == "split" \
        else ("awaiting-approval", "escalated")
    if stage == "execute":
        # Stopped before a production gate (design rule D4): the work so far opens or extends the PR.
        publishable += ("awaiting-approval",)
    if result.get("status") not in publishable:
        raise Refused(f"nothing to publish for status {result.get('status')!r} at the {stage} stage")
    gate = result.get("gate", "")
    if stage == "execute" and result["status"] == "awaiting-approval":
        if not isinstance(gate, str) or not GATE_ID.match(gate):
            raise Refused("an execution stopped at a gate needs the gate's ID (G1, G2, ...)")
    elif gate:
        raise Refused("only an execution stopped at a production gate names a gate")
    if stage in ("plan", "spec") and result.get("parts"):
        raise Refused("only a split result carries parts")
    if result.get("questions"):
        raise Refused(f"a {result['status']} result carries questions")
    if stage in DOC_STAGES:
        document = result.get("document")
        if not isinstance(document, str) or not document.startswith(DOC_PREFIX) or not document.endswith(".md") \
                or not SAFE_PATH.match(document) or {".", ".."} & set(document.split("/")):
            raise Refused("a document result needs a docs/*.md path")
        if not isinstance(result.get("deliverable"), str) or not DELIVERABLE.match(result["deliverable"]):
            raise Refused("a document result needs its deliverable ID (Dnn)")
    title = result.get("title")
    if not isinstance(title, str) or not title.strip() or "\n" in title or len(title) > 72:
        raise Refused("the PR title is empty, multi-line or over 72 characters")
    check_brief(result.get("brief"), stage)
    texts = [title, result.get("reason"), result.get("document", "")] + check_extras(result, stage)
    if stage == "split":
        texts += check_split(result)
    texts += result.get("deferred") or []
    texts += result.get("outbound") or []
    for f in result.get("findings") or []:
        if not isinstance(f, dict) or f.get("severity") not in ("critical", "major", "minor"):
            raise Refused("a finding has no valid severity")
        texts += [f.get("location"), f.get("summary")]
    orch = result.get("orchestrator")
    if not isinstance(orch, dict) or not isinstance(orch.get("review_rounds"), int) \
            or not isinstance(orch.get("agents"), list) or not isinstance(orch.get("facts", ""), str):
        raise Refused("the orchestrator record is malformed")
    texts += orch["agents"] + [orch.get("facts", "")]
    if not all(isinstance(t, str) for t in texts):
        raise Refused("the result has a non-string text field")
    for t in texts + list(strings(result["brief"])):
        if TOKEN.search(t):
            raise Refused("the result contains a credential-like string")
        if EMBED.search(t):
            raise Refused("the result contains an image or embed")
    serious = any(f.get("severity") in ("critical", "major") for f in result.get("findings") or [])
    if result["status"] == "escalated" and not serious:
        raise Refused("an escalated result lists no critical or major finding")
    if result["status"] in ("done", "awaiting-approval") and serious:
        raise Refused(f"a {result['status']} result lists a critical or major finding (that is escalated)")


def grows_a_large_file(base, path, size):
    """A file already over the blob cap on the base (the SDLC changelog, 750 KB) may still change: its
    new versions stay within the base size plus the patch cap, which bounds the growth anyway. A file
    under the cap on the base that crosses it is still refused, however small the change."""
    if not path:
        return False
    found = subprocess.run(["git", "cat-file", "-s", f"{base}:{path}"], capture_output=True, text=True)
    if found.returncode != 0:
        return False
    old = int(found.stdout)
    return old > MAX_BLOB_BYTES and size <= old + MAX_DIFF_BYTES


def check_commits(bundle, base, patterns, allowed_prefix=None):
    git("bundle", "verify", bundle)
    git("fetch", "--no-tags", "--quiet", bundle, "HEAD:refs/factory/head")
    head = git("rev-parse", "--verify", "refs/factory/head^{commit}").strip()
    git("merge-base", "--is-ancestor", base, head)
    commits = git("rev-list", f"{base}..{head}").split()
    if not commits:
        raise Refused("the bundle has no new commits")
    if len(commits) > MAX_COMMITS:
        raise Refused(f"{len(commits)} commits (cap {MAX_COMMITS})")
    if git("rev-list", "--min-parents=2", f"{base}..{head}").strip():
        raise Refused("the commits include a merge")
    # Every commit, not only the final tree: each is pushed and each can be checked out.
    paths = set()
    for sha in commits:
        raw = git("diff-tree", "-r", "-z", "--no-renames", "--root", "--no-commit-id", sha, binary=True)
        fields = raw.split(b"\0")
        for meta, path in zip(fields[0::2], fields[1::2]):
            if not meta:
                continue
            new_mode = meta.decode().split()[1]
            name = path.decode("utf-8", errors="replace")
            if new_mode in (SYMLINK, GITLINK):
                raise Refused(f"{name}: symlinks and submodules aren't allowed")
            paths.add(name)
    for path in sorted(paths):
        if agent_config(path):
            raise Refused(f"{path}: agent or gate configuration; the factory never changes it")
        owner = protected(path, patterns)
        if owner:
            raise Refused(f"{path}: covered by CODEOWNERS ({owner}); the factory never changes it")
    if allowed_prefix:
        allowed = (allowed_prefix,) if isinstance(allowed_prefix, str) else tuple(allowed_prefix)
        outside = [path for path in sorted(paths) if not path.startswith(allowed)]
        if outside:
            raise Refused(f"{outside[0]}: this stage may only change {' or '.join(allowed)}")
    if len(paths) > MAX_FILES:
        raise Refused(f"{len(paths)} files changed (cap {MAX_FILES})")
    # Every object the push would carry (commits with all their headers, trees with their names,
    # every file version including ones a later commit deletes): blobs size-capped, and the raw bytes
    # of all of them scanned. diff-tree --binary encodes binary contents and log formats skip extra
    # headers, so only the raw objects show everything.
    objects = [o.split(" ", 1) for o in git("rev-list", "--objects", f"{base}..{head}").split("\n") if o]
    shas = [o[0] for o in objects]
    names = {o[0]: o[1] for o in objects if len(o) == 2}
    raw = subprocess.run(["git", "cat-file", "--batch"], input=("\n".join(shas) + "\n").encode(),
                         capture_output=True, check=True).stdout
    pos = 0
    while pos < len(raw):
        header_end = raw.index(b"\n", pos)
        sha, kind, size = raw[pos:header_end].decode().split(" ")
        size = int(size)
        body = raw[header_end + 1:header_end + 1 + size]
        pos = header_end + 1 + size + 1
        if kind == "blob" and size > MAX_BLOB_BYTES and not grows_a_large_file(base, names.get(sha), size):
            raise Refused(f"a file version is {size} bytes (cap {MAX_BLOB_BYTES})")
        if TOKEN.search(body.decode("latin-1")):
            raise Refused(f"a {kind} contains a credential-like string")
    # Each commit's patch (binary contents included) and message, not just the final diff.
    total = 0
    for sha in commits:
        patch = git("diff-tree", "-p", "--binary", "--no-color", "--no-ext-diff", "--no-textconv", "-U0",
                    "--root", "--no-commit-id", sha, binary=True)
        total += len(patch)
        for line in patch.decode("utf-8", errors="replace").split("\n"):
            if line.startswith("+") and not line.startswith("+++") and TOKEN.search(line):
                raise Refused(f"commit {sha[:12]} adds a credential-like string")
        if TOKEN.search(git("log", "-1", "--format=%an%n%ae%n%cn%n%ce%n%B", sha)):
            raise Refused(f"commit {sha[:12]}'s message or author contains a credential-like string")
    if total > MAX_DIFF_BYTES:
        raise Refused(f"the commits' patches are {total} bytes (cap {MAX_DIFF_BYTES})")
    return head, sorted(paths)


def escape(text):
    """Agent text in a PR body: no markers, no @mentions, and no #refs (a closing keyword before one
    would close that issue on merge). The guard adds the one `Fixes #<issue>` itself."""
    text = text.replace("<!--", "&lt;!--")
    text = re.sub(r"@(?=[A-Za-z0-9])", "@\u200b", text)
    text = re.sub(r"(?i)\bGH-(?=\d)", "GH\u200b-", text)
    text = re.sub(r"/issues/(?=\d)", "/issues/\u200b", text)
    return re.sub(r"#(?=\d)", "#\u200b", text)


def literal(text):
    """Agent text as one line of literal markdown: escape()'s neutralizing, whitespace collapsed,
    control and bidi characters dropped, and every ASCII punctuation mark backslash-escaped outside
    `code spans`. Nothing in it can start a heading, list, table, fence, HTML block or link."""
    text = " ".join(INVISIBLE.sub("", escape(text)).split())
    out, pos = [], 0
    for m in CODE_SPAN.finditer(text):
        out += [PUNCT.sub(r"\\\1", text[pos:m.start()]), m.group(0)]
        pos = m.end()
    return "".join(out + [PUNCT.sub(r"\\\1", text[pos:])])


def bullets(items, prefix="- "):
    return [prefix + literal(x) for x in items if x.strip()]


def run_stats(stats):
    """Cost, turns and models from the agent job's record of the run, or None."""
    if not isinstance(stats, dict):
        return None
    cost, turns = stats.get("cost"), stats.get("turns")
    models = [m for m in stats.get("models") or [] if isinstance(m, str) and MODEL.match(m)]
    if not isinstance(cost, (int, float)) or isinstance(cost, bool) or cost < 0 or not models:
        return None
    turns = f"; {turns} turns" if isinstance(turns, int) and not isinstance(turns, bool) else ""
    return f"{', '.join(models)}; ${cost:.2f} at API rates{turns}"


def pr_body(result, issue, run_url, paths, stage="implement", stats=None, exists=None, present=None, plan_gates=None):
    """The PR description in the template's fixed order. `exists` says whether a path is in the base
    checkout (the default branch), to mark a key file new or not found. `present` is the changed paths
    that still exist at the head (a moved file counts once, at its new path); defaults to `paths`."""
    present = paths if present is None else present
    exists = exists or (lambda path: pathlib.Path(path).exists())
    brief, code = result["brief"], stage in CODE_STAGES
    findings = result.get("findings") or []
    serious = [f for f in findings if f["severity"] in ("critical", "major")]
    minor = [f for f in findings if f["severity"] == "minor"]
    # Writer marker: which stage opened this PR (factory-follow-ups.yml files follow-ups for execute only).
    lines = [f"<!-- factory-pr: v1 {stage} -->", ""]
    if stage == "split":
        lines += [f"**{escape(result['deliverable'])} splits into {len(result['parts'])} parts, for your approval:** "
                  f"`{escape(result['document'])}`. Merging this PR approves the split: the factory files an issue per "
                  f"part, linked under this one, each held until you add `factory:go`. To change the split, edit the "
                  f"parts table and the catalog rows on this branch before merging; closing it stops the issue.", ""]
    elif not code:
        lines += [f"**{escape(result['deliverable'])} {stage}, for your approval:** `{escape(result['document'])}`. "
                  f"Merging this PR approves it and starts the next stage; closing it stops the issue.", ""]
    if serious:
        lines += ["**Escalated: findings are open for you to decide.** They are under Review focus.", ""]
    if stage == "execute" and result.get("status") == "awaiting-approval":
        lines += [f"**Stopped before production gate {escape(result['gate'])}.** This PR stays open for the whole "
                  f"deliverable: the gate tracker comment shows each gate, each gate's request and signed result "
                  f"appear as comments, and later segments add their commits here. Merge it, with a merge commit, "
                  f"when execution finishes.", ""]
    if plan_gates:
        lines += ["**This plan touches production.** Merging it approves what each gate below may do; each gate "
                  "still runs only after you approve its gate run (environment `factory-production`).", ""]
        lines += plan_gates + [""]

    lines += ["## The problem", "", literal(brief["problem"])]
    lines += ["", "## What changes for users", ""] + (bullets(brief["user_changes"]) or ["Nothing visible."])
    lines += ["", "## What you're approving", ""]
    for i, d in enumerate(brief["decisions"], 1):
        # The renderer supplies "Rather than"; drop the agent's own copy of it.
        alt = re.sub(r"(?i)^\s*rather than[\s,:]*", "", d["rejected"])
        rejected = f" Rather than {literal(alt)}" if alt.strip() else ""
        lines.append(f"{i}. **{literal(d['choice'])}**{rejected}")
    if stage == "execute":
        lines += ["", "## Deviations from the approved plan", ""] + (bullets(brief["deviations"]) or ["None."])
    if stage == "split":
        lines += ["", "## The parts", ""]
        for p in result["parts"]:
            deps = ", ".join(p["depends_on"]) or "nothing"
            spec = f" Reuses the spec `{p['spec']}`." if p["spec"] else ""
            lines.append(f"- **{p['part']}** ({p['tier']}): **{literal(p['name'])}**. {literal(p['scope'])} "
                         f"Depends on: {deps}.{spec}")
    scope = brief["scope"]
    lines += ["", "## Scope", ""]
    for key, label in (("tackled", "Tackled"), ("not_tackled", "Not tackled"), ("deferred", "Deferred")):
        if any(s.strip() for s in scope[key]):
            lines += [f"- **{label}:**"] + bullets(scope[key], "  - ")
    if code and result["add_ons"]:
        lines += ["", "## Add-ons beyond the plan" if stage == "execute" else "## Add-ons beyond the issue", ""]
        for a in result["add_ons"]:
            files = ", ".join(f"`{p}`" for p in a["paths"])
            lines.append(f"- **{literal(a['what'])}**: {literal(a['why'])} Files: {files}. Verified: {literal(a['verified'])}")
    if code and result["follow_ups"]:
        if stage == "execute":
            lines += ["", "## Follow-ups", "", "Checked items become issues when you merge this PR; each is triaged, "
                      "then held until you add `factory:go`. Uncheck any you don't want.", "", FOLLOW_UPS_OPEN]
            box = "- [x] "
        else:
            lines += ["", "## Follow-ups to file by hand", "",
                      "A direct fix files no follow-ups automatically; open an issue for any you want."]
            box = "- "
        for f in result["follow_ups"]:
            why = f" _Not now: {literal(f['why_not_now'])}_" if f["why_not_now"].strip() else ""
            lines.append(f"{box}**{f['id']}: {literal(f['title'])}**: {literal(f['summary'])}{why}")
        if stage == "execute":
            lines.append(FOLLOW_UPS_CLOSE)
    if code:
        lines += ["", "## Scope integrity", "", literal(brief["scope_integrity"])]
    risk = brief["risk"]
    lines += ["", "## Risk", "", f"**{risk['tier'].capitalize()}**: {literal(risk['why'])}", ""]
    lines += bullets(risk["items"]) + [f"- **Undo:** {literal(risk['undo'])}"]
    lines += ["", "## Review focus", ""] + bullets(brief["review_focus"])
    hygiene = [p for p in paths if p.startswith(SDLC_HYGIENE)]
    if hygiene:
        lines.append("- **SDLC knowledge changed** (future agents read these): " + ", ".join(f"`{p}`" for p in hygiene))
    lines += [f"- **Open {f['severity']} finding** at {literal(f['location'])}: {literal(f['summary'])}" for f in serious]
    lines += ["", "## How it was verified" if code else "## How it will be verified", ""] + bullets(brief["verification"])
    lines += ["", "## How it works", "", literal(brief["how_it_works"])]
    lines += ["", "## Learn the change", "", "**Files, in reading order**", ""]
    for f in brief["files"]:
        path = f["path"]
        mark = "" if exists(path) else " (new)" if not code or path in paths else " (not found in the repository)"
        lines.append(f"- `{path}`{mark}: {literal(f['role'])}")
    concepts = [c for c in brief["concepts"] if c["term"].strip()]
    if concepts:
        lines += ["", "**Concepts**", ""] + [f"- **{literal(c['term'])}**: {literal(c['meaning'])}" for c in concepts]
    if result.get("outbound"):
        lines += ["", "**Not done: needs a person**", ""] + bullets(result["outbound"])
    lines += ["", f"Refs #{issue}" if not code else f"Fixes #{issue}"]

    orch = result.get("orchestrator") or {}
    target = WORD_TARGET[stage]
    record = []
    if not code:
        record.append(f"- **{stage.capitalize()}:** `{escape(result['document'])}`")
    for path in present:
        kind = LITE_DOC.match(path)
        if code and kind:
            record.append(f"- **{kind.group(1).capitalize()}:** `{path}`")
    record.append(f"- **Review rounds:** {orch.get('review_rounds', '?')}; agents: "
                  f"{literal(', '.join(orch.get('agents') or [])) or 'none'}; orchestrator edits: {orch.get('self_edits', '?')}")
    if (orch.get("facts") or "").strip():
        record.append(f"- **FACTS:** {literal(orch['facts'])}")
    record.append(f"- **Models and cost:** {run_stats(stats) or 'not recorded'}")
    record.append(f"- **Length:** {brief_words(brief)} words above this record (target {target})")
    record.append(f"- **Run:** [factory {stage}]({run_url}); files changed: {len(present)}")
    if minor:
        record += ["", "**Open minor findings**", ""]
        record += [f"- {literal(f['location'])}: {literal(f['summary'])}" for f in minor]
    if result.get("deferred"):
        record += ["", "**Deferred by the run**", ""] + bullets(result["deferred"])
    lines += ["", "<details><summary>Agent record</summary>", ""] + record + ["", "</details>",
              "", "<sub>Opened by the factory, which never merges. It doesn't revise PRs yet: "
                  "push fixes yourself or close the PR.</sub>"]
    return "\n".join(lines) + "\n"


def main():
    bundle, base, result_path, issue, run_url, out_dir = sys.argv[1:7]
    stage = sys.argv[7] if len(sys.argv) > 7 else "implement"
    stats_path = sys.argv[8] if len(sys.argv) > 8 else ""
    out = pathlib.Path(out_dir)
    try:
        if not re.fullmatch(r"[0-9a-f]{40}", base) or not issue.isdigit():
            raise Refused("bad base SHA or issue number")
        if stage not in CODE_STAGES + DOC_STAGES + ("revise",):
            raise Refused(f"unknown stage {stage!r}")
        result = json.loads(pathlib.Path(result_path).read_text())
        if stage == "revise":
            check_revise_result(result, os.environ.get("PLAN", ""), os.environ.get("NEXT_GATE", ""))
        else:
            check_result(result, stage)
        patterns = codeowners_patterns(pathlib.Path(".github/CODEOWNERS").read_text())
        head, paths = check_commits(bundle, base, patterns, DOC_STAGE_PATHS if stage in DOC_STAGES else None)
        if stage == "split":
            check_split_docs(result, lambda path: git("show", f"{head}:{path}"))
        plan_gates = None
        if stage == "plan" and result["document"].endswith("_plan.md"):
            plan_gates = plan_gate_lines(git("show", f"{head}:{result['document']}"), read_catalog()) or None
        if stage != "revise":
            check_add_on_paths(result, paths, stage)
        try:
            stats = json.loads(pathlib.Path(stats_path).read_text()) if stats_path else None
        except (OSError, ValueError):
            stats = None
        if stage == "revise":
            revision, limit = int(os.environ["REVISION"]), int(os.environ["REVISION_LIMIT"])
            if not 1 <= revision <= limit:
                raise Refused(f"revision {revision} is outside 1..{limit}")
            body = revise_comment(result, revision, limit, run_url, paths, stats)
        else:
            # Changed paths that exist at the head: a move is one file, at its new path.
            present = git("diff", "--name-only", "-M", "--diff-filter=d", base, head).split()
            body = pr_body(result, issue, run_url, paths, stage, stats, present=present, plan_gates=plan_gates)
    except (Refused, ValueError, OSError, KeyError, TypeError, AttributeError, subprocess.CalledProcessError) as e:
        print(f"::error::{stage} output refused: {e}")
        return 1
    out.mkdir(parents=True, exist_ok=True)
    (out / "head").write_text(head + "\n")
    if stage == "revise":
        (out / "comment.md").write_text(body)
        print(f"revise output accepted: {head[:12]}, {len(paths)} files")
        return 0
    title = result["title"].strip()
    if stage in DOC_STAGES:
        title = f"{result['deliverable']}: {title}"
    (out / "title").write_text(title + "\n")
    (out / "pr-body.md").write_text(body)
    print(f"{stage} output accepted: {head[:12]}, {len(paths)} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
