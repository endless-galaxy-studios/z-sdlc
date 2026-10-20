"""Tests for revise_gate.sh: which PRs a revise stage takes, who may ask, the revision limit, and the plan
and next gate an execution PR's revision may stop before; and for gate_stop.sh, what a revision that stopped
there does. A fake gh serves fixture responses (applying --jq with jq) and logs every write, so the
comments, labels, dispatches and outputs are checked exactly. The scripts run from a copy of the factory
directory with a test receipt key, so a gate this PR has passed can be signed, and an empty catalog: the
plan's gates are CD gates, so the tests need no project's operations."""

import base64
import itertools
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest

FACTORY = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FACTORY))
import ed25519  # noqa: E402
import gates  # noqa: E402

APP = json.loads((FACTORY / "factory.json").read_text())["app"]
APP_USER_ID = APP["user_id"]
RUN_URL = "https://github.com/o/r/actions/runs/1"
SECRET = bytes(range(32))
HEAD = "a" * 40
LITE_PLAN = "docs/current_work/sdlc-lite/d19_x_plan.md"
# Two CD gates (no gate-ops block: CD runs the runbook).
PLAN = """# D19: X

### Phase 1: Code

Write it.

### Gate G1: Check by hand

**Runbook:**
- [ ] read the pre-flight facts

### Gate G2: Confirm by hand

**Runbook:**
- [ ] check the dashboard

### Phase 2: Records

Write the result.
"""

FAKE_GH = textwrap.dedent("""\
    #!/usr/bin/env python3
    # A stand-in for gh: GET requests read the fixture, anything else is logged.
    import json, os, subprocess, sys
    args = sys.argv[1:]
    log = open(os.environ["FAKE_GH_LOG"], "a")
    if args[:2] in (["issue", "edit"], ["workflow", "run"]):
        log.write(json.dumps({"call": args, "token": os.environ.get("GH_TOKEN")}) + "\\n")
        sys.exit(0)
    if args[:2] == ["issue", "view"]:
        issue = json.load(open(os.environ["FAKE_GH_FIXTURE"]))["issue"]
        jq = args[args.index("-q") + 1]
        sys.stdout.write(subprocess.run(["jq", "-r", jq], input=json.dumps(issue), capture_output=True, text=True,
                                        check=True).stdout)
        sys.exit(0)
    assert args[0] == "api", args
    method, path, jq, fields = "GET", None, None, {}
    i = 1
    while i < len(args):
        a = args[i]
        if a == "-X":
            method = args[i + 1]; i += 2
        elif a == "--jq":
            jq = args[i + 1]; i += 2
        elif a in ("-f", "-F"):
            k, _, v = args[i + 1].partition("="); fields[k] = v; i += 2
            method = "POST" if method == "GET" else method
        elif a == "--paginate":
            i += 1
        elif a == "-H":
            i += 2
        else:
            path = a; i += 1
    if method != "GET":
        log.write(json.dumps({"method": method, "path": path, "fields": fields,
                              "token": os.environ.get("GH_TOKEN")}) + "\\n")
        print("{}")
        sys.exit(0)
    data = json.load(open(os.environ["FAKE_GH_FIXTURE"]))
    if path not in data:
        print("gh: Not Found (HTTP 404)", file=sys.stderr)
        sys.exit(1)
    if isinstance(data[path], str):
        # A raw file (Accept: application/vnd.github.raw).
        sys.stdout.write(data[path])
        sys.exit(0)
    body = json.dumps(data[path])
    if jq is None:
        print(body)
    else:
        sys.stdout.write(subprocess.run(["jq", "-c", "-r", jq], input=body, capture_output=True, text=True,
                                        check=True).stdout)
""")


IDS = itertools.count(100)


def comment(body, user_id=APP_USER_ID, kind="Bot", login=APP["login"]):
    return {"id": next(IDS), "user": {"id": user_id, "type": kind, "login": login}, "body": body,
            "created_at": "2026-10-12T00:00:00Z"}


def gate_marker(name, payload):
    return comment(gates.marker(name, payload) + "\nhuman text")


def passed(gate_id, secret=SECRET, pr=5):
    """The App's request comment for one of PLAN's gates on PR #5, and the broker's signed done result."""
    req = gates.build_request(repo="o/r", issue=7, pr=pr, plan=LITE_PLAN, plan_blob="b" * 40, plan_text=PLAN,
                              gate_id=gate_id, attempt=1, head=HEAD, catalog=None, gate_outputs={},
                              ops_digest="c" * 64)
    steps = [{"id": s["id"], "op": s["op"], "status": "done", "outputs": {}} for s in req["steps"]]
    receipt = {"v": 1, "digest": req["digest"], "pr": req["pr"], "gate": req["gate"], "kind": req["kind"],
               "head": req["head"], "status": "done", "steps": steps, "rollback": []}
    return [gate_marker(gates.REQUEST, {"request": req}),
            gate_marker(gates.RESULT, gates.sign_receipt(secret, receipt))]


@unittest.skipUnless(shutil.which("jq"), "needs jq")
class ReviseGate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        # The factory directory, with a test receipt key and an empty catalog.
        self.factory = self.root / "factory"
        shutil.copytree(FACTORY, self.factory, ignore=shutil.ignore_patterns("tests", "__pycache__"))
        (self.factory / "production").mkdir(exist_ok=True)
        (self.factory / "production" / "receipt.pub").write_text(ed25519.public_key(SECRET).hex() + "\n")
        (self.factory / "production" / "ops.json").write_text('{"version": 1, "operations": {}}\n')
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        gh = bin_dir / "gh"
        gh.write_text(FAKE_GH)
        gh.chmod(0o755)
        self.log = self.root / "gh.log"
        self.fixture = self.root / "fixture.json"
        self.output = self.root / "output"
        self.summary = self.root / "summary"
        self.env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "FAKE_GH_LOG": str(self.log),
                    "FAKE_GH_FIXTURE": str(self.fixture), "PR": "5", "REQUESTER": "cd", "RUN_URL": RUN_URL,
                    "GH_REPO": "o/r", "GH_TOKEN": "read-token", "APP_TOKEN": "app-token",
                    "RUNNER_TEMP": str(self.root), "GITHUB_OUTPUT": str(self.output),
                    "GITHUB_STEP_SUMMARY": str(self.summary)}
        self.fresh()

    def fresh(self):
        """A new case: no calls logged, no outputs, the default fixture (an open factory code PR, one
        earlier revision by the App, and markers by others that don't count)."""
        for f in (self.log, self.output, self.summary):
            f.write_text("")
        self.data = {
            "repos/o/r/pulls/5": {"head": {"ref": "factory/7-impl", "sha": "a" * 40, "repo": {"full_name": "o/r"}},
                                  "state": "open", "user": {"id": APP_USER_ID}},
            "repos/o/r/collaborators/cd/permission": {"permission": "admin"},
            "repos/o/r/issues/5/comments": [comment("<!-- factory-revise: 1 -->\nRevised."),
                                            comment("<!-- factory-revise: 2 -->\nby a person", 1, "User"),
                                            comment("<!-- factory-revise: 3 -->\nanother bot", 41898282)],
            "repos/o/r/pulls/5/files": [],
            # The plan stage's reservation on the issue.
            "repos/o/r/issues/7/comments": [comment("<!-- factory-id: D19 -->\nReserved **D19**.")],
        }

    def tearDown(self):
        self.tmp.cleanup()

    def run_gate(self, kind, limit):
        self.fixture.write_text(json.dumps(self.data))
        return subprocess.run(["bash", str(self.factory / "revise_gate.sh"), kind],
                              env={**self.env, "REVISION_LIMIT": str(limit)}, cwd=self.root, capture_output=True,
                              text=True)

    def outputs(self):
        out = {}
        for line in self.output.read_text().splitlines():
            k, _, v = line.partition("=")
            out[k] = v
        return out

    def writes(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def doc_pr(self, ref, files):
        self.data["repos/o/r/pulls/5"]["head"]["ref"] = ref
        self.data["repos/o/r/pulls/5/files"] = [{"filename": f, "status": s} for f, s in files]


class Code(ReviseGate):
    def test_proceeds_with_the_next_revision(self):
        r = self.run_gate("code", 3)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        # Only the App's own markers count: one earlier revision.
        self.assertEqual(self.outputs(), {"proceed": "true", "issue": "7", "branch": "factory/7-impl",
                                          "base": "a" * 40, "revision": "2", "plan": "", "next_gate": ""})
        self.assertEqual(self.summary.read_text(), "Revision 2 of 3 for PR #5 (issue #7)\n")
        self.assertEqual(self.writes(), [])

    def execution(self, files, on_main=(LITE_PLAN,), text=PLAN):
        self.data["repos/o/r/pulls/5/files"] = [{"filename": f, "status": s} for f, s in files]
        for path in on_main:
            self.data[f"repos/o/r/contents/{path}"] = text

    def test_an_execution_pr_names_the_plan_its_result_doc_belongs_to(self):
        for result, plan, reserved in [
                ("docs/current_work/sdlc-lite/d19_x_result.md", LITE_PLAN, "D19"),
                ("docs/current_work/results/d7a_y_z_result.md", "docs/current_work/planning/d7a_y_z_plan.md", "D7a")]:
            with self.subTest(result=result):
                self.fresh()
                self.data["repos/o/r/issues/7/comments"] = [comment(f"<!-- factory-id: {reserved} -->\nReserved.")]
                # Only the result doc the PR adds counts: one the branch carries from main, or changes, doesn't.
                self.execution([("api/a.py", "modified"), (result, "added"),
                                ("docs/current_work/sdlc-lite/completed/d13_x_result.md", "modified")], [plan])
                r = self.run_gate("code", 3)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertEqual((self.outputs()["plan"], self.outputs()["next_gate"]), (plan, "G1"))
                self.assertEqual(self.summary.read_text(),
                                 f"Revision 2 of 3 for PR #5 (issue #7, executing {plan}, next gate G1)\n")
                self.assertEqual(self.writes(), [])

    def test_the_result_doc_must_be_for_the_issues_own_deliverable(self):
        result = [("docs/current_work/sdlc-lite/d19_x_result.md", "added")]
        for reservations in (
                # Another deliverable's plan, merged on main: not this issue's.
                [comment("<!-- factory-id: D20 -->\nReserved.")],
                # A re-plan: the latest reservation is the issue's.
                [comment("<!-- factory-id: D19 -->\nReserved."), comment("<!-- factory-id: D20 -->\nReserved.")],
                # None, or only ones the App didn't write.
                [],
                [comment("<!-- factory-id: D19 -->", 1, "User", "someone"),
                 comment("<!-- factory-id: D19 -->", 41898283, "Bot", "other-app[bot]")],
                # Not at the start of the comment.
                [comment("Quoting <!-- factory-id: D19 -->")]):
            with self.subTest(reservations=reservations):
                self.fresh()
                self.data["repos/o/r/issues/7/comments"] = reservations
                self.execution(result)
                r = self.run_gate("code", 3)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertEqual((self.outputs()["plan"], self.outputs()["next_gate"]), ("", ""))
                self.assertIn("::warning::docs/current_work/sdlc-lite/d19_x_result.md is for D19, but issue #7 reserved", r.stdout)
        # The plan stage's reservations from before 2026-10-09 were github-actions'.
        self.fresh()
        self.data["repos/o/r/issues/7/comments"] = [comment("<!-- factory-id: D19 -->", 41898282, "Bot", "github-actions[bot]")]
        self.execution(result)
        r = self.run_gate("code", 3)
        self.assertEqual(self.outputs()["plan"], LITE_PLAN, r.stdout + r.stderr)

    def test_the_gate_tracker_names_the_plan_first(self):
        tracker = "docs/current_work/planning/d20_x_plan.md"
        self.data["repos/o/r/issues/5/comments"] += [
            comment('<!-- factory-gate-tracker: {"issue":7,"plan":"docs/current_work/planning/d1_forged_plan.md"} -->\n', 1, "User"),
            comment('<!-- factory-gate-tracker: {"issue":7,"plan":"%s","stopped_at":"G2"} -->\n### Production gates' % tracker)]
        self.execution([("docs/current_work/sdlc-lite/d19_x_result.md", "added")], [LITE_PLAN, tracker])
        r = self.run_gate("code", 3)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.outputs()["plan"], tracker)

    def test_the_next_gate_is_the_first_this_pr_hasnt_passed(self):
        forged = passed("G1", secret=bytes(32))
        cases = [([], "G1"),
                 (passed("G1"), "G2"),
                 (passed("G1") + passed("G2"), ""),
                 # Only the broker's signature counts, and only for this PR.
                 (forged, "G1"),
                 (passed("G1", pr=6), "G1")]
        for comments, next_gate in cases:
            with self.subTest(next_gate=next_gate, comments=len(comments)):
                self.fresh()
                self.data["repos/o/r/issues/5/comments"] += comments
                self.execution([("docs/current_work/sdlc-lite/d19_x_result.md", "added")])
                r = self.run_gate("code", 3)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertEqual((self.outputs()["plan"], self.outputs()["next_gate"]), (LITE_PLAN, next_gate))
        # A plan without gates, or whose gates don't parse: the plan, no gate.
        for text in ("# D19: X\n\n### Phase 1: Code\n", PLAN.replace("### Gate G2", "### Gate G3")):
            with self.subTest(text=text[:40]):
                self.fresh()
                self.execution([("docs/current_work/sdlc-lite/d19_x_result.md", "added")], text=text)
                r = self.run_gate("code", 3)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertEqual((self.outputs()["plan"], self.outputs()["next_gate"]), (LITE_PLAN, ""))

    def test_no_gate_without_a_production_runner(self):
        # A project that set up no production runner has no receipt key: no gate can run there.
        (self.factory / "production" / "receipt.pub").unlink()
        self.execution([("docs/current_work/sdlc-lite/d19_x_result.md", "added")])
        r = self.run_gate("code", 3)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual((self.outputs()["proceed"], self.outputs()["plan"], self.outputs()["next_gate"]),
                         ("true", LITE_PLAN, ""))

    def test_no_plan_without_exactly_one_added_result_doc_whose_plan_is_on_main(self):
        for files, on_main in [
                ([("docs/current_work/sdlc-lite/d19_x_result.md", "modified")], [LITE_PLAN]),
                ([("docs/current_work/sdlc-lite/d19_x_result.md", "added"),
                  ("docs/current_work/sdlc-lite/d20_y_result.md", "added")], [LITE_PLAN]),
                ([("docs/current_work/sdlc-lite/d19_x_result.md", "added")], []),
                ([("docs/current_work/sdlc-lite/completed/d19_x_result.md", "added")], [LITE_PLAN]),
                ([("docs/current_work/sdlc-lite/d19_x_plan.md", "added")], [LITE_PLAN])]:
            with self.subTest(files=files, on_main=on_main):
                self.fresh()
                self.execution(files, on_main)
                r = self.run_gate("code", 3)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertEqual((self.outputs()["plan"], self.outputs()["next_gate"]), ("", ""))
                self.assertNotIn("::error::", r.stdout)

    def test_refuses_what_isnt_an_open_factory_code_pr(self):
        cases = [("head", {"ref": "factory/7-plan", "sha": "a" * 40, "repo": {"full_name": "o/r"}}),
                 ("head", {"ref": "feature/x", "sha": "a" * 40, "repo": {"full_name": "o/r"}}),
                 ("head", {"ref": "factory/7-impl", "sha": "a" * 40, "repo": {"full_name": "fork/r"}}),
                 ("state", "closed"), ("user", {"id": 1})]
        for key, value in cases:
            with self.subTest(key=key, value=value):
                self.fresh()
                self.data["repos/o/r/pulls/5"][key] = value
                r = self.run_gate("code", 3)
                self.assertEqual(r.returncode, 1)
                self.assertIn("::error::PR #5 isn't an open factory code PR", r.stdout)
                self.assertEqual(self.outputs(), {"proceed": "false"})
                self.assertEqual(self.writes(), [])

    def test_a_requester_without_write_access_is_told_and_nothing_runs(self):
        for permission in ("read", "triage", None):
            with self.subTest(permission=permission):
                self.fresh()
                if permission:
                    self.data["repos/o/r/collaborators/cd/permission"] = {"permission": permission}
                else:
                    del self.data["repos/o/r/collaborators/cd/permission"]
                r = self.run_gate("code", 3)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertEqual(self.outputs(), {"proceed": "false"})
                self.assertEqual(self.writes(), [
                    {"method": "DELETE", "path": "repos/o/r/issues/5/labels/factory:revise", "fields": {},
                     "token": "app-token"},
                    {"method": "POST", "path": "repos/o/r/issues/5/comments", "token": "app-token",
                     "fields": {"body": f"Revisions need a reviewer with write access. <sub>factory revise · [run]({RUN_URL})</sub>"}}])

    def test_the_limit_escalates_the_issue(self):
        r = self.run_gate("code", 1)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.outputs(), {"proceed": "false"})
        body = ("**Revision limit reached** (1 for a code PR): no more automatic revisions. Push the changes "
                f"yourself, or close the PR and re-triage the issue. <sub>factory revise · [run]({RUN_URL})</sub>")
        self.assertEqual(self.writes(), [
            {"method": "DELETE", "path": "repos/o/r/issues/5/labels/factory:revise", "fields": {}, "token": "app-token"},
            {"method": "POST", "path": "repos/o/r/issues/5/comments", "fields": {"body": body}, "token": "app-token"},
            {"call": ["issue", "edit", "7", "--add-label", "factory:escalated"], "token": "app-token"}])


class Doc(ReviseGate):
    def test_a_lite_plan(self):
        self.doc_pr("factory/7-plan", [("docs/current_work/sdlc-lite/d12_rate_limits_plan.md", "added"),
                                       ("docs/_index.md", "modified"),
                                       ("docs/current_work/sdlc-lite/d3_old_plan.md", "removed")])
        r = self.run_gate("doc", 5)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.outputs(), {
            "proceed": "true", "issue": "7", "branch": "factory/7-plan", "base": "a" * 40, "revision": "2",
            "stage": "plan", "document": "docs/current_work/sdlc-lite/d12_rate_limits_plan.md",
            "deliverable": "D12", "skill": "sdlc-lite-plan"})
        self.assertEqual(self.summary.read_text(), "Revision 2 of 5 for plan PR #5 (issue #7, "
                         "docs/current_work/sdlc-lite/d12_rate_limits_plan.md, /sdlc-lite-plan)\n")

    def test_a_spec_and_a_full_plan(self):
        for ref, doc, stage in (("factory/7-spec", "docs/current_work/specs/d12a_feeds_spec.md", "spec"),
                                ("factory/7-plan", "docs/current_work/planning/d12a_feeds_plan.md", "plan")):
            with self.subTest(stage=stage):
                self.fresh()
                self.doc_pr(ref, [(doc, "modified")])
                r = self.run_gate("doc", 5)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                out = self.outputs()
                self.assertEqual((out["stage"], out["document"], out["deliverable"], out["skill"]),
                                 (stage, doc, "D12a", "sdlc-plan"))

    def test_needs_exactly_one_document_of_its_stage(self):
        for files in ([], [("docs/current_work/specs/d12_x_spec.md", "added")],
                      [("docs/current_work/sdlc-lite/d12_x_plan.md", "added"),
                       ("docs/current_work/planning/d12_x_plan.md", "added")]):
            with self.subTest(files=files):
                self.fresh()
                self.doc_pr("factory/7-plan", files)
                r = self.run_gate("doc", 5)
                self.assertEqual(r.returncode, 1)
                self.assertIn("::error::PR #5 doesn't add or change exactly one plan document", r.stdout)
                self.assertEqual(self.outputs(), {"proceed": "false"})

    def test_refuses_a_code_pr(self):
        r = self.run_gate("doc", 5)
        self.assertEqual(r.returncode, 1)
        self.assertIn("::error::PR #5 isn't an open factory spec or plan PR", r.stdout)

    def test_the_limit_points_at_an_interactive_session(self):
        self.doc_pr("factory/7-spec", [("docs/current_work/specs/d12_x_spec.md", "added")])
        r = self.run_gate("doc", 1)
        self.assertEqual(r.returncode, 0, r.stderr)
        body = ("**Revision limit reached** (1 for a spec PR): no more automatic revisions. A document that needs "
                "another round usually needs a conversation: continue in an interactive `sdlc-plan` session on "
                "`factory/7-spec` (it can read this review), push the changes yourself, or close the PR to stop. "
                f"<sub>factory revise · [run]({RUN_URL})</sub>")
        self.assertEqual(self.writes()[1], {"method": "POST", "path": "repos/o/r/issues/5/comments",
                                            "fields": {"body": body}, "token": "app-token"})
        self.assertEqual(self.writes()[2]["call"], ["issue", "edit", "7", "--add-label", "factory:escalated"])


class StopAtGate(ReviseGate):
    """gate_stop.sh: the stop-at-gate job of factory-revise.yml, after the revision comment."""

    def stop(self, gate="G1", next_gate="G1", plan=LITE_PLAN, published=HEAD):
        self.data["repos/o/r/pulls/5"].update(number=5)
        self.data[f"repos/o/r/contents/{LITE_PLAN}?ref=main"] = {"sha": "b" * 40,
                                                                 "content": base64.b64encode(PLAN.encode()).decode()}
        self.data["issue"] = {"labels": [{"name": "factory:review-capped"}, {"name": "factory:advisor"}]}
        self.fixture.write_text(json.dumps(self.data))
        env = {**self.env, "GH_TOKEN": "app-token", "READ_TOKEN": "read-token", "ISSUE_NUMBER": "7",
               "DEFAULT_BRANCH": "main", "PLAN": plan, "NEXT_GATE": next_gate, "PUBLISHED_HEAD": published,
               "RESULT": json.dumps({"status": "awaiting-approval", "gate": gate})}
        return subprocess.run(["bash", str(self.factory / "gate_stop.sh")], env=env, cwd=self.root,
                              capture_output=True, text=True)

    def tracker(self):
        body = (self.root / "tracker.md").read_text()
        return gates.parse_marker(body)[1], body

    LABELS = {"call": ["issue", "edit", "7", "--add-label", "factory:gate", "--remove-label", "factory:review-capped"],
              "token": "app-token"}
    DISPATCH = {"call": ["workflow", "run", "factory-gate-request.yml", "--ref", "main", "-f", "pr=5", "-f", f"head={HEAD}"],
                "token": "read-token"}

    def test_the_first_stop_posts_the_tracker_labels_and_asks_for_the_gate(self):
        r = self.stop()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        tracker = {"method": "POST", "path": "repos/o/r/issues/5/comments", "token": "app-token",
                   "fields": {"body": f"@{self.root}/tracker.md"}}
        self.assertEqual(self.writes(), [tracker, self.LABELS, self.DISPATCH])
        payload, body = self.tracker()
        self.assertEqual(payload, {"v": 1, "issue": 7, "plan": LITE_PLAN, "stopped_at": "G1"})
        self.assertIn("| G1 | Check by hand | CD runs the runbook | requesting |", body)
        self.assertEqual(self.summary.read_text(), "PR #5: revision stopped before G1; gate run requested\n")

    def test_a_later_stop_updates_the_apps_tracker(self):
        self.data["repos/o/r/issues/5/comments"] += [
            comment('<!-- factory-gate-tracker: {"issue":7,"plan":"%s","stopped_at":""} -->\n' % LITE_PLAN, 1, "User"),
            comment('<!-- factory-gate-tracker: {"issue":7,"plan":"%s","stopped_at":"G1"} -->\n' % LITE_PLAN)]
        app_tracker = self.data["repos/o/r/issues/5/comments"][-1]["id"]
        self.data["repos/o/r/issues/5/comments"] += passed("G1")
        r = self.stop(gate="G2", next_gate="G2")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.writes()[0], {"method": "PATCH", "path": f"repos/o/r/issues/comments/{app_tracker}",
                                            "token": "app-token", "fields": {"body": f"@{self.root}/tracker.md"}})
        self.assertEqual(self.writes()[1:], [self.LABELS, self.DISPATCH])
        payload, body = self.tracker()
        self.assertEqual(payload["stopped_at"], "G2")
        self.assertIn("| G1 | Check by hand | CD runs the runbook | done |", body)

    def test_a_branch_that_moved_gets_no_gate_run(self):
        moved = "d" * 40
        self.data["repos/o/r/pulls/5"]["head"]["sha"] = moved
        r = self.stop()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        writes = self.writes()
        # The tracker and the label, so factory:gate-retry can still ask; no dispatch.
        self.assertEqual([w.get("path") or w["call"][:2] for w in writes],
                         ["repos/o/r/issues/5/comments", ["issue", "edit"], "repos/o/r/issues/5/comments"])
        self.assertIn("**No gate run requested:** the branch moved after this revision was pushed (`aaaaaaa` to "
                      "`ddddddd`)", writes[2]["fields"]["body"])
        self.assertIn("add `factory:gate-retry` to ask for G1 on them", writes[2]["fields"]["body"])
        self.assertNotIn(self.DISPATCH, writes)

    def test_refuses_any_gate_but_the_next_and_does_nothing(self):
        for kw in ({"gate": "G2"}, {"gate": "G99"}, {"gate": ""}, {"next_gate": ""}, {"gate": "G2", "next_gate": "G1"},
                   {"plan": ""}, {"published": ""}, {"published": "abc"}):
            with self.subTest(**kw):
                self.fresh()
                r = self.stop(**kw)
                self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                self.assertIn("::error::", r.stdout)
                self.assertEqual(self.writes(), [])


class Usage(unittest.TestCase):
    def test_unknown_kind(self):
        r = subprocess.run(["bash", str(FACTORY / "revise_gate.sh"), "other"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)


if __name__ == "__main__":
    unittest.main()
