"""Release gates (z-sdlc process/factory.md, D4 rule 13): a gate with a **Release:** line, in a project whose
production follows a release branch. Its commit is pinned, CD's merge of its release PR is the deploy, and its
gate run (kind release) binds that PR and its merge. The other kinds' requests and digests don't change.
Run by CI: python -m unittest discover -s .github/factory/tests"""

import base64
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
import implement_guard as guard  # noqa: E402
import render  # noqa: E402

CATALOG_TEXT = json.dumps({"version": 1, "operations": {
    "health": {"kind": "read", "summary": "Production's health", "timeout_s": 60, "outputs": {"status": "^(ok|down)$"}},
    "deploy": {"kind": "change", "summary": "Deploy a commit", "timeout_s": 600, "params": {"sha": "^[0-9a-f]{40}$"},
               "outputs": {"previous_sha": "^[0-9a-f]{40}$"}},
}})
CATALOG = gates.load_catalog(CATALOG_TEXT)
APP, REPO, PR, HEAD = 339877552, "o/r", 8, "a" * 40
MERGE = "d" * 40
PLAN_PATH = "docs/current_work/planning/d99_thing_plan.md"
PLAN = """# D99: Thing

### Phase 1: Code

Write it.

### Gate G1: Deploy it

**After:** Phase 1. **Changes production:** yes.

```gate-ops
{"steps": [{"id": "deploy", "op": "deploy", "with": {"sha": "${head}"}}],
 "rollback": [{"op": "deploy", "with": {"sha": "${steps.deploy.previous_sha}"}}]}
```

### Gate G2: Confirm by hand

**Runbook:**
- [ ] check the dashboard

### Phase 2: Release the API

Write the API.

### Gate G3: The API reaches production

**After:** Phase 2. **Changes production:** yes.
**Release:** the web app needs the new endpoint before Phase 3 builds on it

```gate-ops
{"steps": [{"op": "health"}]}
```

### Phase 3: Records

Write the result.
"""


def request(gate_id, release=None, plan=PLAN):
    return gates.build_request(repo=REPO, issue=7, pr=PR, plan=PLAN_PATH, plan_blob="b" * 40, plan_text=plan,
                               gate_id=gate_id, attempt=1, head=HEAD, catalog=CATALOG, gate_outputs={},
                               ops_digest="c" * 64, release=release)


def release_pr(**changes):
    pr = {"number": 41, "merged": True, "merge_commit_sha": MERGE, "user": {"id": APP},
          "base": {"ref": "release/production"},
          "head": {"ref": f"factory/release/{PR}-G3-{HEAD[:12]}", "sha": HEAD, "repo": {"full_name": REPO}}}
    for key, value in changes.items():
        if isinstance(value, dict):
            pr[key] = {**pr[key], **value}
        else:
            pr[key] = value
    return pr


def binding(pr=None):
    return gates.release_binding(pr or release_pr(), repo=REPO, app_id=APP, branch="release/production", pr=PR,
                                 gate_id="G3", head=HEAD)


class ReleaseGates(unittest.TestCase):
    def test_the_release_line_makes_a_release_gate(self):
        gs = gates.parse_gates(PLAN)
        self.assertEqual([g["release"] for g in gs],
                         [None, None, "the web app needs the new endpoint before Phase 3 builds on it"])
        self.assertEqual(gates.check_plan(PLAN, CATALOG), [])
        with self.assertRaisesRegex(gates.Invalid, "G3: more than one Release line"):
            gates.parse_gates(PLAN.replace("**Release:** the web", "**Release:** twice\n**Release:** the web"))
        # A Release line outside a gate section is no gate's.
        self.assertEqual([g["release"] for g in gates.parse_gates(PLAN.replace(
            "Write it.", "Write it.\n**Release:** not a gate"))][0], None)

    def test_a_release_gate_runs_only_read_steps_and_has_no_rollback(self):
        bad = PLAN.replace('{"steps": [{"op": "health"}]}',
                           '{"steps": [{"id": "deploy", "op": "deploy", "with": {"sha": "${head}"}}],\n'
                           ' "rollback": [{"op": "deploy", "with": {"sha": "${steps.deploy.previous_sha}"}}]}')
        errors = gates.check_plan(bad, CATALOG)
        self.assertIn("G3: a release gate has no rollback (its release is live from the merge; rolling back is CD's, "
                      "through the host)", errors)
        self.assertIn("G3.steps[1]: a release gate runs only read operations (deploy is change)", errors)
        # Without a block, it only checks production serves the release.
        bare = PLAN.replace('```gate-ops\n{"steps": [{"op": "health"}]}\n```\n', "")
        self.assertEqual(gates.check_plan(bare, CATALOG), [])
        self.assertEqual(request("G3", binding(), plan=bare)["steps"], [])

    def test_a_release_request_binds_its_release_pr_and_merge(self):
        req = request("G3", binding())
        self.assertEqual(req["kind"], "release")
        self.assertEqual(req["release"], {"branch": "release/production", "pr": 41, "merge": MERGE})
        self.assertEqual([s["op"] for s in req["steps"]], ["health"])
        self.assertEqual(req["rollback"], [])
        other = request("G3", {**binding(), "merge": "e" * 40})
        self.assertNotEqual(req["digest"], other["digest"])
        self.assertEqual(gates.parse_title(gates.run_title(req))["kind"], "release")
        with self.assertRaisesRegex(gates.Invalid, "G3 is a release gate: its request needs its merged release PR"):
            request("G3")
        with self.assertRaisesRegex(gates.Invalid, "G1 isn't a release gate"):
            request("G1", binding())

    def test_the_other_kinds_keep_their_digests(self):
        # Computed with gates.py before release gates: these kinds' fields and digest formula are unchanged. (The
        # operations digest still hashes gates.py itself, so a host re-runs its setup to install the new copy.)
        self.assertEqual(request("G1")["digest"], "ae13698a91f35575f7b3a9b3c580baa1be7e9972c737ad74e0c191c74256c9bf")
        self.assertEqual(request("G2")["digest"], "656fb2ecb3be76e0a7cfd5174ffab01b686b0e54510ffec65fd524060a76008d")
        self.assertNotIn("release", request("G1"))

    def test_the_release_pr_must_be_the_pinned_one_merged(self):
        self.assertEqual(gates.pin_branch(PR, "G3", HEAD), f"factory/release/{PR}-G3-{HEAD[:12]}")
        for changes, why in [
                ({"head": {"ref": f"factory/release/{PR}-G2-{HEAD[:12]}"}}, "isn't from"),
                ({"head": {"sha": "f" * 40}}, "isn't from"),
                ({"head": {"repo": {"full_name": "fork/r"}}}, "isn't from"),
                ({"base": {"ref": "main"}}, "isn't the factory's into release/production"),
                ({"user": {"id": 1}}, "isn't the factory's into release/production"),
                ({"merged": False}, "isn't merged"),
                ({"merge_commit_sha": None}, "isn't merged")]:
            with self.subTest(changes=changes), self.assertRaisesRegex(gates.Invalid, why):
                binding(release_pr(**changes))
        with self.assertRaisesRegex(gates.Invalid, "not a release branch"):
            gates.release_binding(release_pr(), repo=REPO, app_id=APP, branch="release/../main", pr=PR, gate_id="G3",
                                  head=HEAD)

    def test_the_release_pr_lists_what_merging_deploys(self):
        def c(sha, subject, login):
            return {"sha": sha, "author": {"login": login}, "commit": {"message": subject + "\n\nbody"}}
        body = gates.render_release_pr(pr=PR, pr_title="Add `x` <img src=y>", gate_id="G3", gate_title="The API",
                                       why="the web app needs it", head=HEAD, branch="release/production",
                                       default_branch="main", own=[c("1" * 40, "One", "factory[bot]"),
                                                                   c("2" * 40, "Two", "a-writer")],
                                       others=[c("3" * 40, "Fix <b>it</b>", "someone")], total=3, complete=True,
                                       run_url="https://x/run")
        self.assertTrue(body.startswith(f'<!-- {gates.RELEASE_PR}: {{"gate":"G3","head":"{HEAD}","pr":{PR},"v":1}} -->'))
        self.assertIn("**Merging this deploys.**", body)
        self.assertIn("Merging deploys 3 commits:", body)
        self.assertIn("**#8's own, not released yet (2):**", body)
        self.assertIn("- `222222222222` Two (a\\-writer)", body)  # agent-written text, escaped
        self.assertIn("**From `main`, which `release/production` doesn't have yet (1):**", body)
        self.assertNotIn("partial", body)
        partial = gates.render_release_pr(pr=PR, pr_title="t", gate_id="G3", gate_title="g", why="w", head=HEAD,
                                          branch="release/production", default_branch="main", own=[], others=[],
                                          total=300, complete=False, run_url="https://x/run")
        self.assertIn("Merging deploys 300 commits", partial)
        self.assertIn("the lists below are partial", partial)
        # Agent-written text is shown escaped, never rendered.
        self.assertIn("\\<img src\\=y\\>", body)
        self.assertIn("Fix \\<b\\>it", body)

    def test_a_list_github_cut_short_is_partial(self):
        own_c, mine = {"sha": "1" * 40}, {"sha": "1" * 40}
        full = gates.release_commits({"total_commits": 1, "commits": [own_c]}, {"total_commits": 1, "commits": [mine]})
        self.assertEqual((len(full[0]), full[2], full[3]), (1, 1, True))
        # GitHub's compare lists at most 250 commits: a total above the list is a partial list, either side.
        self.assertFalse(gates.release_commits({"total_commits": 300, "commits": [own_c]},
                                               {"total_commits": 1, "commits": [mine]})[3])
        self.assertFalse(gates.release_commits({"total_commits": 1, "commits": [own_c]},
                                               {"total_commits": 260, "commits": [mine]})[3])

    def test_the_tracker_and_request_say_how_a_release_gate_runs(self):
        state = {"tracker": None, "requests": [], "results": {}}
        tracker = gates.render_tracker({"v": 1, "issue": 7, "plan": PLAN_PATH, "stopped_at": "G3"}, PLAN, state)
        self.assertIn("| G3 | The API reaches production | you merge its release PR, then the production runner checks |",
                      tracker)
        req = request("G3", binding())
        text = gates.render_request(req, "https://x/run", CATALOG, PLAN)
        self.assertIn("release PR #41 merged into `release/production`", text)
        self.assertIn("nothing rolls back, since the release is live", text)
        # A failed release gate: the release is live, and only reverting a revert brings it back.
        failed = {"unsigned": True, "digest": req["digest"], "gate": "G3", "status": "failed", "kind": "release"}
        text = gates.render_result(failed, req, "https://x/run")
        self.assertIn("**The release is live:**", text)
        self.assertIn("record a `baseline`", text)
        self.assertIn("first revert the revert", text)
        self.assertNotIn("request changes", text)


class ReleaseGateCli(unittest.TestCase):
    """The commands factory-gate-request.yml and factory-gate.yml run, on the files they fetch."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        d = pathlib.Path(self.tmp.name)
        (d / "factory" / "production").mkdir(parents=True)
        (d / "factory" / "production" / "ops.json").write_text(CATALOG_TEXT)
        (d / "factory" / "production" / "receipt.pub").write_text(ed25519.public_key(bytes(range(32))).hex())
        for name in ("gates.py", "ed25519.py"):  # the operations' digest covers them, and the broker
            (d / "factory" / name).write_bytes((FACTORY / name).read_bytes())
        (d / "factory" / "production" / "factory_op.py").write_text("# a stand-in broker\n")
        tracker = gates.marker(gates.TRACKER, {"v": 1, "issue": 7, "plan": PLAN_PATH, "stopped_at": "G3"})
        (d / "comments.ndjson").write_text(json.dumps({"id": 1, "created_at": "2026-11-05T00:00:00Z",
                                                       "user": {"id": APP, "type": "Bot"}, "body": tracker}) + "\n")
        import base64
        (d / "plan.json").write_text(json.dumps({"sha": "b" * 40, "content": base64.b64encode(PLAN.encode()).decode()}))
        (d / "pr.json").write_text(json.dumps({"number": PR, "state": "open", "title": "The thing", "user": {"id": APP},
                                               "head": {"ref": "factory/7-impl", "sha": HEAD,
                                                        "repo": {"full_name": REPO}}}))
        (d / "release-pr.json").write_text(json.dumps(release_pr()))
        self.d = d

    def run_cli(self, cmd, *extra):
        d = self.d
        out = d / "out"
        code = gates.cli([cmd, "--repo", REPO, "--app-id", str(APP), "--factory-dir", str(d / "factory"),
                          "--pr-json", str(d / "pr.json"), "--comments", str(d / "comments.ndjson"),
                          "--plan-meta", str(d / "plan.json"), "--out", str(out), *extra])
        return code, out.read_text()

    def test_release_gate_names_the_pinned_branch(self):
        code, out = self.run_cli("release-gate")
        self.assertEqual(json.loads(out), {"gate": "G3", "pin": f"factory/release/{PR}-G3-{HEAD[:12]}", "release": True})

    def test_a_done_release_gate_opens_nothing(self):
        req = request("G3", binding())
        receipt = {"v": 1, "digest": req["digest"], "pr": PR, "gate": "G3", "kind": "release", "head": HEAD,
                   "status": "done", "steps": [], "rollback": []}
        lines = [json.loads(line) for line in (self.d / "comments.ndjson").read_text().splitlines()]
        for i, (name, payload) in enumerate([(gates.REQUEST, {"request": req, "run_url": "https://x/run"}),
                                             (gates.RESULT, gates.sign_receipt(bytes(range(32)), receipt))], 2):
            lines.append({"id": i, "created_at": f"2026-11-05T00:0{i}:00Z", "user": {"id": APP, "type": "Bot"},
                          "body": gates.marker(name, payload)})
        (self.d / "comments.ndjson").write_text("".join(json.dumps(c) + "\n" for c in lines))
        with self.assertRaisesRegex(gates.Invalid, "G3 is already done"):
            self.run_cli("release-gate")

    def test_the_request_needs_the_merged_release_pr(self):
        with self.assertRaisesRegex(gates.Invalid, "needs its merged release PR"):
            self.run_cli("request")
        code, out = self.run_cli("request", "--release-branch", "release/production",
                                 "--release-pr", str(self.d / "release-pr.json"))
        req = json.loads(out)
        self.assertEqual((req["kind"], req["release"]["merge"]), ("release", MERGE))
        # The gate run rebuilds it from GitHub's record of the release PR, and refuses another merge.
        import base64
        b64 = base64.b64encode(out.encode()).decode()
        code, _ = self.run_cli("verify-request", "--request-b64", b64, "--run-url", "https://x/run",
                               "--release-branch", "release/production", "--release-pr", str(self.d / "release-pr.json"))
        self.assertEqual(code, 0)
        (self.d / "release-pr.json").write_text(json.dumps(release_pr(merge_commit_sha="e" * 40)))
        with self.assertRaisesRegex(gates.Invalid, "isn't what the plan, the PR and the earlier results give now"):
            self.run_cli("verify-request", "--request-b64", b64, "--run-url", "https://x/run",
                         "--release-branch", "release/production", "--release-pr", str(self.d / "release-pr.json"))

    def test_release_pr_splits_the_pr_s_commits_from_the_rest(self):
        (self.d / "compare-release.json").write_text(json.dumps({"total_commits": 2, "commits": [
            {"sha": "1" * 40, "commit": {"message": "From main\n\nbody", "author": {"name": "Ann"}}},
            {"sha": "2" * 40, "author": {"login": "factory[bot]"}, "commit": {"message": "The PR's"}}]}))
        # The PR's own: 2, and 0 that an earlier release gate shipped (on the release branch already).
        (self.d / "compare-default.json").write_text(json.dumps({"total_commits": 2, "commits": [{"sha": "0" * 40},
                                                                                                {"sha": "2" * 40}]}))
        code, out = self.run_cli("release-pr", "--release-branch", "release/production", "--default-branch", "main",
                                 "--compare-release", str(self.d / "compare-release.json"),
                                 "--compare-default", str(self.d / "compare-default.json"), "--run-url", "https://x/run")
        self.assertIn("Merging deploys 2 commits", out)
        self.assertIn("- `222222222222` The PR\\'s (factory\\[bot\\])", out)
        self.assertIn("**From `main`, which `release/production` doesn't have yet (1):**\n\n- `111111111111` From main (Ann)", out)
        self.assertNotIn("000000000000", out)


# A stand-in for gh: GET requests read the fixture (applying --jq with jq), writes are logged with their token.
FAKE_GH = textwrap.dedent("""\
    #!/usr/bin/env python3
    import json, os, subprocess, sys
    args = sys.argv[1:]
    log = open(os.environ["FAKE_GH_LOG"], "a")
    if args[0] in ("pr", "workflow"):
        log.write(json.dumps({"call": args, "token": os.environ.get("GH_TOKEN")}) + "\\n")
        if args[:2] == ["pr", "create"]:
            if os.environ.get("FAKE_GH_CREATE_FAIL"):
                print("GraphQL: A pull request already exists (createPullRequest)", file=sys.stderr)
                sys.exit(1)
            print("https://github.com/o/r/pull/77")
        sys.exit(0)
    method, path, jq, fields, i = "GET", None, None, {}, 1
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
        else:
            path = a; i += 1
    if method != "GET":
        log.write(json.dumps({"method": method, "path": path, "fields": fields, "token": os.environ.get("GH_TOKEN")}) + "\\n")
        if path == os.environ.get("FAKE_GH_REFUSE"):
            print("gh: Reference already exists (HTTP 422)", file=sys.stderr)
            sys.exit(1)
        print("{}")
        sys.exit(0)
    data = json.load(open(os.environ["FAKE_GH_FIXTURE"]))
    if path not in data:
        print(f"gh: Not Found (HTTP 404) {path}", file=sys.stderr)
        sys.exit(1)
    body = json.dumps(data[path])
    if jq is None:
        print(body)
    else:
        sys.stdout.write(subprocess.run(["jq", "-c", "-r", jq], input=body, capture_output=True, text=True,
                                        check=True).stdout)
""")


class FakeGhCase(unittest.TestCase):
    """A project with a release branch and a production tier, its PR stopped at release gate G3, and a fake gh."""

    PIN = f"factory/release/{PR}-G3-{HEAD[:12]}"
    LIST = f"repos/{REPO}/pulls?state=all&base=release/production&head=o:{PIN}&per_page=100"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = self.root = pathlib.Path(self.tmp.name)
        factory = root / ".github" / "factory"
        shutil.copytree(FACTORY, factory, ignore=shutil.ignore_patterns("tests", "__pycache__"))
        (factory / "production").mkdir(exist_ok=True)
        (factory / "production" / "ops.json").write_text(CATALOG_TEXT)
        (factory / "production" / "receipt.pub").write_text(ed25519.public_key(bytes(range(32))).hex())
        (factory / "production" / "factory_op.py").write_text("# a stand-in broker\n")
        values = render.settings(factory)
        values.setdefault("release", {})["branch"] = "release/production"  # optional: a project may not have one
        values["app"]["user_id"] = APP
        (factory / "factory.json").write_text(json.dumps(values))
        import yaml
        workflow = yaml.safe_load(render.render((FACTORY / "templates" / "factory-gate-request.yml").read_text(), values))
        step = next(st for st in workflow["jobs"]["request"]["steps"] if st.get("name", "").startswith("Build the request"))
        self.assertEqual(step["env"]["RELEASE_BRANCH"], "release/production")
        (root / "step.sh").write_text(step["run"])
        bin_dir = root / "bin"
        bin_dir.mkdir()
        (bin_dir / "gh").write_text(FAKE_GH)
        (bin_dir / "gh").chmod(0o755)
        self.log, self.fixture = root / "gh.log", root / "fixture.json"
        self.env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "FAKE_GH_LOG": str(self.log),
                    "FAKE_GH_FIXTURE": str(self.fixture), "PR": str(PR), "APP_ID": str(APP), "RUN_URL": "https://x/run",
                    "GH_REPO": REPO, "GH_TOKEN": "read-token", "APP_TOKEN": "app-token", "PIN_TOKEN": "pin-token",
                    "RELEASE_BRANCH": "release/production", "REQUESTER": "", "STOPPED_HEAD": HEAD,
                    "DEFAULT_BRANCH": "main", "GITHUB_STEP_SUMMARY": str(root / "summary")}
        tracker = gates.marker(gates.TRACKER, {"v": 1, "issue": 7, "plan": PLAN_PATH, "stopped_at": "G3"})
        self.data = {
            f"repos/{REPO}/pulls/{PR}": {"number": PR, "state": "open", "title": "The thing", "user": {"id": APP},
                                         "head": {"ref": "factory/7-impl", "sha": HEAD, "repo": {"full_name": REPO}}},
            f"repos/{REPO}/issues/{PR}/comments": [{"id": 1, "created_at": "2026-11-05T00:00:00Z",
                                                    "user": {"id": APP, "type": "Bot"}, "body": tracker}],
            f"repos/{REPO}/contents/{PLAN_PATH}?ref=main": {"sha": "b" * 40,
                                                           "content": base64.b64encode(PLAN.encode()).decode()},
            self.LIST: [],
            f"repos/{REPO}/pulls?state=open&base=release/production&per_page=100": [],
            f"repos/{REPO}/compare/release/production...{HEAD}": {"total_commits": 1, "commits": [
                {"sha": HEAD, "commit": {"message": "The work"}}]},
            f"repos/{REPO}/compare/main...{HEAD}": {"commits": [{"sha": HEAD}]},
        }
        for status in ("waiting", "queued", "in_progress", "pending", "requested"):
            self.data[f"repos/{REPO}/actions/workflows/factory-gate.yml/runs?status={status}&per_page=100"] = {
                "workflow_runs": []}

    def run_step(self):
        self.log.write_text("")
        self.fixture.write_text(json.dumps(self.data))
        r = subprocess.run(["bash", "-e", "-o", "pipefail", str(self.root / "step.sh")], cwd=self.root, env=self.env,
                           capture_output=True, text=True)
        calls = [json.loads(line) for line in self.log.read_text().splitlines()]
        return r.returncode, calls, r.stderr

    def said(self, calls):
        return " ".join(c["fields"].get("body", "") for c in calls if c.get("path", "").endswith("/comments"))



@unittest.skipUnless(shutil.which("jq"), "needs jq")
class ReleaseGateRequest(FakeGhCase):
    """factory-gate-request.yml's request step, rendered for a release branch and run against a fake gh."""

    def test_the_first_stop_pins_the_commit_and_opens_the_release_pr(self):
        code, calls, err = self.run_step()
        self.assertEqual(code, 0, err)
        pins = [c for c in calls if c.get("path") == f"repos/{REPO}/git/refs"]
        self.assertEqual(pins, [{"method": "POST", "path": f"repos/{REPO}/git/refs", "token": "pin-token",
                                 "fields": {"ref": f"refs/heads/{self.PIN}", "sha": HEAD}}])
        create = [c for c in calls if c.get("call", [""])[:2] == ["pr", "create"]]
        self.assertEqual(len(create), 1)
        self.assertEqual(create[0]["token"], "app-token")
        self.assertIn("--head", create[0]["call"])
        self.assertEqual(create[0]["call"][create[0]["call"].index("--head") + 1], self.PIN)
        self.assertEqual(create[0]["call"][create[0]["call"].index("--base") + 1], "release/production")
        self.assertIn("G3 deploys when you merge", self.said(calls))
        self.assertFalse([c for c in calls if c.get("call", [""])[0] == "workflow"])

    def test_ops_and_cd_gates_are_asked_for_as_before(self):
        # The step every production project runs: a gate without a Release line pins nothing, opens nothing, and
        # dispatches its gate run, with or without a release branch.
        comments = f"repos/{REPO}/issues/{PR}/comments"
        for gate_id, kind in (("G1", "ops"), ("G2", "cd")):
            for release_branch in ("release/production", ""):
                with self.subTest(gate=gate_id, release_branch=release_branch):
                    self.env["RELEASE_BRANCH"] = release_branch
                    self.data[comments] = [{"id": 1, "created_at": "2026-11-05T00:00:00Z", "user": {"id": APP, "type": "Bot"},
                                            "body": gates.marker(gates.TRACKER, {"v": 1, "issue": 7, "plan": PLAN_PATH,
                                                                                 "stopped_at": gate_id})}]
                    code, calls, err = self.run_step()
                    self.assertEqual(code, 0, err)
                    runs = [c["call"] for c in calls if c.get("call", [""])[0] == "workflow"]
                    self.assertEqual(len(runs), 1)
                    self.assertIn(f"kind={kind}", runs[0])
                    self.assertIn(f"gate={gate_id}", runs[0])
                    self.assertFalse([c for c in calls if c.get("path") == f"repos/{REPO}/git/refs"
                                      or c.get("call", [""])[:2] in (["pr", "create"], ["pr", "close"])])
                    request = json.loads((self.root / "request.json").read_text())
                    self.assertEqual(request["kind"], kind)
                    self.assertNotIn("release", request)

    def test_a_pinned_name_at_another_commit_is_never_used(self):
        self.data[f"repos/{REPO}/git/ref/heads/{self.PIN}"] = {"object": {"sha": "f" * 40}}
        code, calls, err = self.run_step()
        self.assertEqual(code, 1)
        self.assertIn("already exists, at `ffffffffffff`", self.said(calls))
        self.assertFalse([c for c in calls if c.get("path") == f"repos/{REPO}/git/refs" or "call" in c])

    def test_someone_else_s_pr_from_the_pinned_name_is_refused_never_used(self):
        self.data[f"repos/{REPO}/git/ref/heads/{self.PIN}"] = {"object": {"sha": HEAD}}
        self.data[self.LIST] = [
            {"number": 50, "state": "open", "merged_at": None, "user": {"id": 1},
             "head": {"sha": HEAD, "repo": {"full_name": REPO}}},
            {"number": 51, "state": "closed", "merged_at": "2026-11-05T00:00:00Z", "user": {"id": APP},
             "head": {"sha": HEAD, "repo": {"full_name": "fork/r"}}}]
        code, calls, err = self.run_step()
        self.assertEqual(code, 1)
        self.assertIn("#50, not the factory's, is open", self.said(calls))
        # Neither #50 nor the fork's merged #51 counts as the release: nothing is created, merged or asked for.
        self.assertFalse([c for c in calls if "call" in c or c.get("path") == f"repos/{REPO}/git/refs"])

    def test_a_refused_release_pr_is_said_and_closes_nothing(self):
        self.env["FAKE_GH_CREATE_FAIL"] = "1"
        self.data[f"repos/{REPO}/pulls?state=open&base=release/production&per_page=100"] = [
            {"number": 40, "user": {"id": APP}, "head": {"ref": f"factory/release/{PR}-G3-{'f' * 12}",
                                                        "repo": {"full_name": REPO}}}]
        code, calls, err = self.run_step()
        self.assertEqual(code, 1)
        self.assertIn("GitHub refused it (GraphQL: A pull request already exists", self.said(calls))
        self.assertFalse([c for c in calls if c.get("call", [""])[:2] == ["pr", "close"]])

    def test_the_gate_s_stale_release_prs_and_waiting_runs_go(self):
        self.data[f"repos/{REPO}/pulls?state=open&base=release/production&per_page=100"] = [
            {"number": 40, "user": {"id": APP}, "head": {"ref": f"factory/release/{PR}-G3-{'f' * 12}",
                                                        "repo": {"full_name": REPO}}},
            {"number": 39, "user": {"id": APP}, "head": {"ref": f"factory/release/{PR}-G30-{'f' * 12}",
                                                        "repo": {"full_name": REPO}}},
            {"number": 38, "user": {"id": 1}, "head": {"ref": f"factory/release/{PR}-G3-{'e' * 12}",
                                                      "repo": {"full_name": REPO}}}]
        self.data[f"repos/{REPO}/actions/workflows/factory-gate.yml/runs?status=waiting&per_page=100"] = {
            "workflow_runs": [{"id": 900, "display_title": f"factory-gate #{PR} G3 a1 release {'0' * 64}"},
                              {"id": 901, "display_title": f"factory-gate #{PR}0 G3 a1 release {'0' * 64}"}]}
        code, calls, err = self.run_step()
        self.assertEqual(code, 0, err)
        closed = [c["call"][2] for c in calls if c.get("call", [""])[:2] == ["pr", "close"]]
        self.assertEqual(closed, ["40"])  # not G30's, not someone else's
        cancels = [c["path"] for c in calls if c.get("path", "").endswith("/cancel")]
        self.assertEqual(cancels, [f"repos/{REPO}/actions/runs/900/cancel"])

    def test_nothing_to_release_is_said(self):
        self.data[f"repos/{REPO}/compare/release/production...{HEAD}"] = {"total_commits": 0, "commits": []}
        code, calls, err = self.run_step()
        self.assertEqual(code, 1)
        self.assertIn("already has `aaaaaaaaaaaa`, so G3 has nothing to release", self.said(calls))
        self.assertFalse([c for c in calls if "call" in c])

    def test_an_open_release_pr_waits_for_cd(self):
        self.data[f"repos/{REPO}/git/ref/heads/{self.PIN}"] = {"object": {"sha": HEAD}}
        self.data[self.LIST] = [{"number": 41, "state": "open", "merged_at": None, "user": {"id": APP},
                                 "head": {"sha": HEAD, "repo": {"full_name": REPO}}}]
        code, calls, err = self.run_step()
        self.assertEqual(code, 0, err)
        self.assertIn("release PR #41", self.said(calls))
        self.assertFalse([c for c in calls if "call" in c])

    def test_a_merged_release_pr_asks_for_the_release_gate_run(self):
        self.data[f"repos/{REPO}/git/ref/heads/{self.PIN}"] = {"object": {"sha": HEAD}}
        self.data[self.LIST] = [{"number": 41, "state": "closed", "merged_at": "2026-11-05T00:00:00Z",
                                 "user": {"id": APP}, "head": {"sha": HEAD, "repo": {"full_name": REPO}}}]
        self.data[f"repos/{REPO}/pulls/41"] = release_pr()
        code, calls, err = self.run_step()
        self.assertEqual(code, 0, err)
        runs = [c["call"] for c in calls if c.get("call", [""])[0] == "workflow"]
        self.assertEqual(len(runs), 1)
        self.assertIn("kind=release", runs[0])
        request = json.loads((self.root / "request.json").read_text())  # what the step encodes and dispatches
        self.assertEqual(request["release"], {"branch": "release/production", "pr": 41, "merge": MERGE})
        self.assertFalse([c for c in calls if c.get("call", [""])[:2] == ["pr", "create"]])

    def test_a_release_merged_at_an_older_commit_is_reported(self):
        older = "9" * 40
        self.env.update(STOPPED_HEAD=older, RELEASED="41")
        self.data[f"repos/{REPO}/pulls/41"] = release_pr(head={"ref": f"factory/release/{PR}-G3-{older[:12]}", "sha": older})
        code, calls, err = self.run_step()
        self.assertEqual(code, 1)
        self.assertIn("Release PR #41 deployed `999999999999`, not this PR's head `aaaaaaaaaaaa`", self.said(calls))
        # Said only of the App's release PR from this PR's pin at that commit: otherwise it's only "moved".
        for forged in (release_pr(user={"id": 1}, head={"ref": f"factory/release/{PR}-G3-{older[:12]}", "sha": older}),
                       release_pr(head={"ref": f"factory/release/9{PR}-G3-{older[:12]}", "sha": older}),
                       release_pr(merged=False, head={"ref": f"factory/release/{PR}-G3-{older[:12]}", "sha": older})):
            with self.subTest(forged=forged["head"]["ref"]):
                self.data[f"repos/{REPO}/pulls/41"] = forged
                code, calls, err = self.run_step()
                self.assertEqual(code, 1)
                self.assertNotIn("deployed", self.said(calls))
                self.assertIn("the branch moved", self.said(calls))

    def test_a_refused_pin_is_said(self):
        self.env["FAKE_GH_REFUSE"] = f"repos/{REPO}/git/refs"
        code, calls, err = self.run_step()
        self.assertEqual(code, 1)
        self.assertIn("GitHub refused the pinned branch", self.said(calls))
        self.assertFalse([c for c in calls if "call" in c])

    def test_the_release_pr_is_announced_before_the_cleanup(self):
        self.data[f"repos/{REPO}/pulls?state=open&base=release/production&per_page=100"] = [
            {"number": 40, "user": {"id": APP}, "head": {"ref": f"factory/release/{PR}-G3-{'f' * 12}",
                                                        "repo": {"full_name": REPO}}}]
        self.data[f"repos/{REPO}/actions/workflows/factory-gate.yml/runs?status=waiting&per_page=100"] = {
            "workflow_runs": [{"id": 900, "display_title": f"factory-gate #{PR} G3 a1 release {'0' * 64}"}]}
        self.env["FAKE_GH_REFUSE"] = f"repos/{REPO}/actions/runs/900/cancel"
        code, calls, err = self.run_step()
        self.assertEqual(code, 1)  # the cancel failed
        self.assertIn("G3 deploys when you merge** https://github.com/o/r/pull/77", self.said(calls))

@unittest.skipUnless(shutil.which("jq"), "needs jq")
class ReleaseMergeAndGateRun(FakeGhCase):
    """factory-advance's release-gate job, and factory-gate.yml's check of a release request, run the same way."""

    def step(self, workflow, job, name):
        import yaml
        values = render.settings(self.root / ".github" / "factory")
        text = render.render((FACTORY / "templates" / workflow).read_text(), values)
        steps = yaml.safe_load(text)["jobs"][job]["steps"]
        script = self.root / f"{job}.sh"
        script.write_text(next(st for st in steps if st.get("name", "").startswith(name))["run"])
        return script

    def run_script(self, script, **env):
        self.log.write_text("")
        self.fixture.write_text(json.dumps(self.data))
        r = subprocess.run(["bash", "-e", "-o", "pipefail", str(script)], cwd=self.root, env={**self.env, **env},
                           capture_output=True, text=True)
        return r.returncode, [json.loads(line) for line in self.log.read_text().splitlines()], r.stdout + r.stderr

    def test_the_merge_asks_for_the_gate_run_of_its_own_pr(self):
        import yaml
        values = render.settings(self.root / ".github" / "factory")
        job = yaml.safe_load(render.render((FACTORY / "templates" / "factory-advance.yml").read_text(), values))["jobs"]["release-gate"]
        self.assertIn("github.event.pull_request.base.ref == 'release/production'", job["if"])
        self.assertIn("startsWith(github.event.pull_request.head.ref, 'factory/release/')", job["if"])
        self.assertEqual(job["permissions"], {"actions": "write"})
        script = self.step("factory-advance.yml", "release-gate", "Ask for the release gate's run")
        merged = dict(HEAD_REF=self.PIN, HEAD_SHA=HEAD, AUTHOR=str(APP), RELEASE_PR="41")
        code, calls, out = self.run_script(script, **merged)
        self.assertEqual(code, 0, out)
        self.assertEqual([c["call"] for c in calls], [["workflow", "run", "factory-gate-request.yml", "--ref", "main",
                                                       "-f", f"pr={PR}", "-f", f"head={HEAD}", "-f", "released=41"]])
        for changes in ({"AUTHOR": "1"}, {"HEAD_REF": f"factory/release/{PR}-G3-x"}, {"HEAD_REF": "factory/7-impl"}):
            with self.subTest(changes=changes):
                code, calls, out = self.run_script(script, **{**merged, **changes})
                self.assertEqual((code, calls), (0, []))
        # A branch not at the commit its name pins asks for nothing.
        code, calls, out = self.run_script(script, **{**merged, "HEAD_SHA": "f" * 40})
        self.assertEqual((code, calls), (1, []))

    def test_the_gate_run_rebuilds_the_release_from_github(self):
        script = self.step("factory-gate.yml", "prepare", "Check the request")
        self.data[f"repos/{REPO}/pulls/41"] = release_pr()
        factory = self.root / ".github" / "factory"
        req = gates.build_request(repo=REPO, issue=7, pr=PR, plan=PLAN_PATH, plan_blob="b" * 40, plan_text=PLAN,
                                  gate_id="G3", attempt=1, head=HEAD, catalog=CATALOG, gate_outputs={},
                                  ops_digest=gates.ops_digest(gates.repo_ops_files(factory)), release=binding())
        env = dict(REQUEST=base64.b64encode(gates.canonical(req).encode()).decode(), GATE="G3", ATTEMPT="1",
                   KIND="release", DIGEST=req["digest"], GITHUB_OUTPUT=str(self.root / "output"))
        code, calls, out = self.run_script(script, **env)
        self.assertEqual(code, 0, out)
        self.assertIn("release PR #41 merged into `release/production`", (self.root / "request-comment.md").read_text())
        # A plain ops gate's request (no release PR) is checked as before.
        comments = f"repos/{REPO}/issues/{PR}/comments"
        self.data[comments] = [{"id": 1, "created_at": "2026-11-05T00:00:00Z", "user": {"id": APP, "type": "Bot"},
                                "body": gates.marker(gates.TRACKER, {"v": 1, "issue": 7, "plan": PLAN_PATH,
                                                                     "stopped_at": "G1"})}]
        ops = gates.build_request(repo=REPO, issue=7, pr=PR, plan=PLAN_PATH, plan_blob="b" * 40, plan_text=PLAN,
                                  gate_id="G1", attempt=1, head=HEAD, catalog=CATALOG, gate_outputs={},
                                  ops_digest=gates.ops_digest(gates.repo_ops_files(factory)))
        code, calls, out = self.run_script(script, **{**env, "REQUEST": base64.b64encode(gates.canonical(ops).encode()).decode(),
                                                      "GATE": "G1", "KIND": "ops", "DIGEST": ops["digest"]})
        self.assertEqual(code, 0, out)
        self.data[comments] = [{"id": 1, "created_at": "2026-11-05T00:00:00Z", "user": {"id": APP, "type": "Bot"},
                                "body": gates.marker(gates.TRACKER, {"v": 1, "issue": 7, "plan": PLAN_PATH,
                                                                     "stopped_at": "G3"})}]
        # A request naming another merge than GitHub's record of its release PR is refused.
        forged = {**req, "release": {**req["release"], "merge": "e" * 40}}
        forged["digest"] = gates.digest(forged)
        code, calls, out = self.run_script(script, **{**env, "REQUEST": base64.b64encode(gates.canonical(forged).encode()).decode(),
                                                      "DIGEST": forged["digest"]})
        self.assertNotEqual(code, 0)
        self.assertIn("isn't what the plan, the PR and the earlier results give now", out)

class PlanPrBody(unittest.TestCase):
    def test_a_release_gate_needs_a_release_branch(self):
        with self.assertRaisesRegex(guard.Refused, "G3 is a release gate, but this project's production doesn't follow"):
            guard.plan_gate_lines(PLAN, CATALOG_TEXT)
        lines = guard.plan_gate_lines(PLAN, CATALOG_TEXT, "release/production")
        self.assertIn("A release: the factory opens a release PR into `release/production` at this gate, and merging "
                      "it deploys.", lines[2])
        self.assertIn("then runs `health`; it can't roll back", lines[2])


if __name__ == "__main__":
    unittest.main()
