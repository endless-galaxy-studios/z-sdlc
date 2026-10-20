"""Tests for agent_job.sh: the scaffolding the agent jobs share. What it decides (which statuses bundle,
when the commits are refused, which files are frozen) and what it writes (the issue context, the MCP
config, the schema and advisor variables) must match what the workflows did inline before."""

import json
import os
import pathlib
import shutil
import stat
import subprocess
import tempfile
import unittest

FACTORY = pathlib.Path(__file__).resolve().parents[1]
APP = json.loads((FACTORY / "factory.json").read_text())["app"]
PROFILE = json.loads((FACTORY / "factory.json").read_text())["stack"]["profile"]
SCRIPT = FACTORY / "agent_job.sh"
NEEDS_JQ = unittest.skipUnless(shutil.which("jq"), "needs jq")


def git(*args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


class AgentJob(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        self.temp = self.root / "runner-temp"
        self.temp.mkdir()
        self.checks = self.root / "checks"
        self.files = {k: self.root / k for k in ("env", "output", "summary")}
        for f in self.files.values():
            f.write_text("")
        self.env = {**os.environ, "RUNNER_TEMP": str(self.temp), "CHECKS": str(self.checks),
                    "GITHUB_ENV": str(self.files["env"]), "GITHUB_OUTPUT": str(self.files["output"]),
                    "GITHUB_STEP_SUMMARY": str(self.files["summary"])}
        self.env.pop("CONTEXT7_API_KEY", None)

    def tearDown(self):
        self.tmp.cleanup()

    def run_script(self, *args, script=SCRIPT, cwd=None, env=None):
        return subprocess.run(["bash", str(script), *args], cwd=cwd or self.root, env=env or self.env,
                              capture_output=True, text=True)

    def lines(self, name):
        return self.files[name].read_text().splitlines()


class Freeze(AgentJob):
    def test_freezes_scripts_guards_schemas_and_the_named_settings(self):
        r = self.run_script("freeze", "implement-sandbox.settings.json")
        self.assertEqual(r.returncode, 0, r.stderr)
        frozen = {p.name for p in self.checks.iterdir()}
        for name in ("agent_job.sh", "factory_branch.sh", "git_guard.sh", "session_log.sh", "run_metrics.py",
                     "implement_guard.py", "catalog.py", "gates.py", "implement.schema.json", "plan.schema.json",
                     "implement-sandbox.settings.json", "factory.json", "profiles"):
            self.assertIn(name, frozen)
        # Only the named settings: a planning stage builds its own settings file at that path.
        self.assertNotIn("planning-sandbox.settings.json", frozen)
        self.assertEqual(stat.S_IMODE(self.checks.stat().st_mode), 0o700)
        self.assertTrue(os.access(self.checks / "git_guard.sh", os.X_OK))
        # The project's stack profile, at the same path as in the repository: its services list among it, which
        # the sandbox check reads out of the agent's reach.
        profile = self.checks / "profiles" / PROFILE
        self.assertEqual(sorted(p.name for p in profile.iterdir()),
                         ["Dockerfile", "install.sh", "services", "test-services.sh", "verify", "with-test-services"])
        for name in ("install.sh", "test-services.sh", "verify", "with-test-services"):
            self.assertTrue(os.access(profile / name, os.X_OK), name)
        self.assertEqual(stat.S_IMODE((self.checks / "run_metrics.py").stat().st_mode), 0o644)

    def test_a_missing_named_file_fails(self):
        self.assertNotEqual(self.run_script("freeze", "no-such.settings.json").returncode, 0)


@NEEDS_JQ
class Mcp(AgentJob):
    def test_context7_without_a_key(self):
        r = self.run_script("mcp")
        self.assertEqual(r.returncode, 0, r.stderr)
        cfg = self.temp / "factory-mcp.json"
        self.assertEqual(r.stdout.strip(), str(cfg))
        self.assertEqual(self.lines("env"), [f"FACTORY_MCP_CONFIG={cfg}"])
        self.assertEqual(json.loads(cfg.read_text()),
                         {"mcpServers": {"context7": {"type": "http", "url": "https://mcp.context7.com/mcp"}}})

    def test_context7_with_a_key_names_the_variable_never_the_value(self):
        r = self.run_script("mcp", env={**self.env, "CONTEXT7_API_KEY": "ctx7sk-secret"})
        self.assertEqual(r.returncode, 0, r.stderr)
        text = (self.temp / "factory-mcp.json").read_text()
        self.assertNotIn("ctx7sk-secret", text)
        self.assertEqual(json.loads(text)["mcpServers"]["context7"]["headers"],
                         {"CONTEXT7_API_KEY": "${CONTEXT7_API_KEY}"})


@NEEDS_JQ
class Schema(AgentJob):
    def test_sets_the_stage_variable(self):
        for name, var in (("implement", "FACTORY_IMPLEMENT_SCHEMA"), ("revise-doc", "FACTORY_REVISE_DOC_SCHEMA"),
                          ("triage", "FACTORY_TRIAGE_SCHEMA")):
            self.files["env"].write_text("")
            r = self.run_script("schema", name)
            self.assertEqual(r.returncode, 0, r.stderr)
            key, _, value = self.lines("env")[0].partition("=")
            self.assertEqual(key, var)
            self.assertEqual(json.loads(value), json.loads((FACTORY / f"{name}.schema.json").read_text()))
            self.assertNotIn("\n", value)

    def test_refuses_a_single_quote(self):
        # A copy of the script beside a schema with an apostrophe in it.
        d = self.root / "factory"
        d.mkdir()
        shutil.copy(SCRIPT, d)
        (d / "bad.schema.json").write_text('{"description": "the agent\'s result"}')
        r = self.run_script("schema", "bad", script=d / "agent_job.sh")
        self.assertEqual(r.returncode, 1)
        self.assertIn("must not contain single quotes", r.stdout)
        self.assertEqual(self.lines("env"), [])

    def test_refuses_a_path(self):
        self.assertEqual(self.run_script("schema", "../implement").returncode, 1)


class Advisor(AgentJob):
    def test_values(self):
        for value, expected in (("none", ["FACTORY_ADVISOR=opus", "CLAUDE_CODE_DISABLE_ADVISOR_TOOL=1"]),
                                ("opus", ["FACTORY_ADVISOR=opus"]), ("fable", ["FACTORY_ADVISOR=fable"])):
            self.files["env"].write_text("")
            r = self.run_script("advisor", value)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(self.lines("env"), expected)

    def test_unknown(self):
        r = self.run_script("advisor", "auto")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.lines("env"), [])


@NEEDS_JQ
class IssueContext(AgentJob):
    ISSUE = {"number": 7, "title": "A title", "body": "Body with <!-- a marker --> and @someone",
             "author": {"login": "cd"}, "labels": [{"name": "factory:triage"}, {"name": "bug"}],
             "state": "OPEN", "url": "https://github.com/o/r/issues/7",
             "comments": [{"author": {"login": "cd"}, "authorAssociation": "OWNER",
                           "createdAt": "2026-10-12T00:00:00Z", "body": "a reply", "id": "x"}]}
    # The jq programs the workflows ran inline before agent_job.sh (implement; plan and revise-doc).
    OLD = """{
              repo: env.GITHUB_REPOSITORY, base: $base,
              issue: {number, title, body, author: .author.login, labels: [.labels[].name], state, url},
              comments: [.comments[] | {author: .author.login, author_association: .authorAssociation,
                                        created_at: .createdAt, body}]
            }"""
    OLD_ID = OLD.replace("base: $base,", "base: $base, deliverable: $id,")

    def setUp(self):
        super().setUp()
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        fixture = self.root / "issue-fixture.json"
        fixture.write_text(json.dumps(self.ISSUE))
        gh = bin_dir / "gh"
        gh.write_text(f'#!/usr/bin/env bash\n[ "$1 $2" = "issue view" ] && cat "{fixture}"\n')
        gh.chmod(0o755)
        self.workspace = self.root / "ws"
        self.workspace.mkdir()
        self.env.update(PATH=f"{bin_dir}:{self.env['PATH']}", ISSUE_NUMBER="7", GITHUB_REPOSITORY="o/r",
                        GITHUB_WORKSPACE=str(self.workspace))
        self.fixture = fixture

    def old(self, program, *args):
        return subprocess.run(["jq", *args, program, str(self.fixture)], env=self.env, check=True,
                              capture_output=True, text=True).stdout

    def test_same_bytes_as_the_inline_version(self):
        r = self.run_script("issue-context", "abc123")
        self.assertEqual(r.returncode, 0, r.stderr)
        out = (self.workspace / ".factory/issue-context.json").read_text()
        self.assertEqual(out, self.old(self.OLD, "--arg", "base", "abc123"))
        self.assertEqual(json.loads((self.temp / "issue.json").read_text()), self.ISSUE)

    def test_with_a_deliverable(self):
        r = self.run_script("issue-context", "abc123", "D12a")
        self.assertEqual(r.returncode, 0, r.stderr)
        out = (self.workspace / ".factory/issue-context.json").read_text()
        self.assertEqual(out, self.old(self.OLD_ID, "--arg", "base", "abc123", "--arg", "id", "D12a"))


class Repo(AgentJob):
    """A clone with origin removed and its hooks hashed, as an agent job has before the agent."""

    def setUp(self):
        super().setUp()
        src = self.root / "src"
        src.mkdir()
        git("init", "-q", "-b", "main", cwd=src)
        (src / "a.txt").write_text("a\n")
        git("add", "-A", cwd=src)
        git("-c", "user.name=t", "-c", "user.email=t@e", "commit", "-q", "-m", "base", cwd=src)
        self.repo = self.root / "ws"
        git("clone", "-q", "--no-local", str(src), str(self.repo), cwd=self.root)
        git("remote", "remove", "origin", cwd=self.repo)
        git("config", "user.name", APP["login"], cwd=self.repo)
        git("config", "user.email", f"{APP['user_id']}+{APP['login']}@users.noreply.github.com", cwd=self.repo)
        self.checks.mkdir(mode=0o700)
        hashes = subprocess.run("find .git/hooks -type f -exec sha256sum {} + | sort", shell=True, cwd=self.repo,
                                check=True, capture_output=True, text=True).stdout
        (self.checks / "git-hooks.sha256").write_text(hashes)
        self.base = git("rev-parse", "HEAD", cwd=self.repo).strip()
        self.bundle = self.temp / "implement" / "implement.bundle"

    def commit(self, name="b.txt"):
        (self.repo / name).write_text("b\n")
        git("add", "-A", cwd=self.repo)
        git("commit", "-q", "-m", "work", cwd=self.repo)

    def bundle_run(self, status, *publishing):
        return self.run_script("bundle", self.base, str(self.bundle), status, *publishing, cwd=self.repo)


class Bundle(Repo):
    def test_a_publishing_status_bundles_the_commits(self):
        self.commit()
        r = self.bundle_run("done", "done", "escalated", "awaiting-approval")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.lines("output"), ["bundle=yes"])
        self.assertEqual(self.lines("summary"), ["Commits since the base: 1"])
        self.assertEqual(stat.S_IMODE(self.bundle.parent.stat().st_mode), 0o700)
        heads = git("bundle", "list-heads", str(self.bundle), cwd=self.repo)
        self.assertIn(git("rev-parse", "HEAD", cwd=self.repo).strip(), heads)

    def test_a_status_that_doesnt_publish_bundles_nothing(self):
        self.commit()
        for status in ("needs-input", "failed", "rescope"):
            r = self.bundle_run(status, "done", "escalated", "awaiting-approval")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse(self.bundle.exists())
        self.assertEqual(self.lines("output"), [])

    def test_a_publishing_status_without_a_commit_is_refused(self):
        r = self.bundle_run("escalated", "done", "escalated")
        self.assertEqual(r.returncode, 1)
        self.assertIn("::error::status escalated but the agent made no commit", r.stdout)
        self.assertFalse(self.bundle.exists())
        self.assertEqual(self.lines("summary"), ["Commits since the base: 0"])

    def test_uncommitted_changes_are_refused_after_bundling(self):
        self.commit()
        (self.repo / "a.txt").write_text("changed\n")
        (self.repo / "new.txt").write_text("new\n")
        r = self.bundle_run("split", "awaiting-approval", "escalated", "split")
        self.assertEqual(r.returncode, 1)
        self.assertIn("::error::status split but the agent left uncommitted changes:", r.stdout)
        self.assertIn("a.txt", r.stdout)
        # The bundle stays, so the commits can be uploaded for CD; publish won't run.
        self.assertTrue(self.bundle.exists())
        self.assertEqual(self.lines("output"), ["bundle=yes", "incomplete=yes"])


class Quiesce(Repo):
    def test_a_clean_repository_passes(self):
        r = self.run_script("quiesce", cwd=self.repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_runs_git_guard(self):
        hook = self.repo / ".git/hooks/post-checkout"
        hook.write_text("#!/bin/sh\necho planted\n")
        r = self.run_script("quiesce", cwd=self.repo)
        self.assertEqual(r.returncode, 1)
        self.assertIn("hooks changed", r.stdout)


@NEEDS_JQ
class ReviseContext(AgentJob):
    """CD's review since the last revision, collected through a fake gh (test_revise_gate's)."""
    # The jq program revise and revise-doc ran inline before agent_job.sh (revise-doc's adds the document).
    OLD = """{pr: ($pr | tonumber), issue: ($issue | tonumber), branch: $branch, base: $base, merge_base: $merge_base,
              revision: ($revision | tonumber), limit: ($limit | tonumber), body: $body, requests: $requests[0]}"""
    OLD_DOC = """{pr: ($pr | tonumber), issue: ($issue | tonumber), stage: $stage, document: $document,
              deliverable: $deliverable, branch: $branch, base: $base, merge_base: $merge_base,
              revision: ($revision | tonumber), limit: ($limit | tonumber), body: $body, requests: $requests[0]}"""

    def setUp(self):
        super().setUp()
        from test_revise_gate import FAKE_GH
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        (bin_dir / "gh").write_text(FAKE_GH)
        (bin_dir / "gh").chmod(0o755)
        self.workspace = self.root / "ws"
        self.workspace.mkdir()
        self.fixture = self.root / "fixture.json"
        (self.root / "gh.log").write_text("")
        self.env.update(PATH=f"{bin_dir}:{self.env['PATH']}", FAKE_GH_LOG=str(self.root / "gh.log"),
                        FAKE_GH_FIXTURE=str(self.fixture), GITHUB_REPOSITORY="o/r", GITHUB_WORKSPACE=str(self.workspace),
                        PR="5", ISSUE_NUMBER="7", BRANCH="factory/7-impl", BASE="b" * 40, REVISION="2",
                        REVISION_LIMIT="3")
        cd = {"login": "cd", "type": "User"}
        app = {"login": APP["login"], "type": "Bot", "id": APP["user_id"]}
        self.data = {
            "repos/o/r/pulls/5": {"body": "The PR's description."},
            "repos/o/r/issues/5/comments": [
                {"user": app, "created_at": "2026-10-10T00:00:00Z", "body": "<!-- factory-revise: 1 -->\nRevised."},
                {"user": cd, "author_association": "OWNER", "created_at": "2026-10-09T00:00:00Z", "body": "before it"},
                {"user": cd, "author_association": "OWNER", "created_at": "2026-10-11T03:00:00Z", "body": "a comment"},
                {"user": {"login": "x", "type": "User"}, "author_association": "NONE", "created_at": "2026-10-11T04:00:00Z",
                 "body": "a stranger"},
                {"user": app, "created_at": "2026-10-11T05:00:00Z", "body": "a bot"}],
            "repos/o/r/pulls/5/reviews": [
                {"user": cd, "author_association": "OWNER", "submitted_at": "2026-10-11T01:00:00Z",
                 "state": "CHANGES_REQUESTED", "body": "a review"},
                {"user": cd, "author_association": "OWNER", "submitted_at": "2026-10-11T02:00:00Z",
                 "state": "COMMENTED", "body": ""}],
            "repos/o/r/pulls/5/comments": [
                {"user": cd, "author_association": "MEMBER", "created_at": "2026-10-11T02:30:00Z", "path": "api/a.py",
                 "line": None, "original_line": 4, "body": "inline"}],
        }

    def run_context(self, *args):
        self.fixture.write_text(json.dumps(self.data))
        return self.run_script("revise-context", "c" * 40, *args, cwd=self.workspace)

    def old(self, program, *extra):
        args = ["-n", "--arg", "pr", "5", "--arg", "issue", "7", "--arg", "branch", "factory/7-impl", "--arg", "base",
                "b" * 40, "--arg", "merge_base", "c" * 40, "--arg", "revision", "2", "--arg", "limit", "3", *extra,
                "--rawfile", "body", str(self.temp / "body.md"), "--slurpfile", "requests", str(self.temp / "requests.json")]
        return subprocess.run(["jq", *args, program], check=True, capture_output=True, text=True).stdout

    def test_maintainers_since_the_last_revision_oldest_first(self):
        r = self.run_context()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        context = json.loads((self.workspace / ".factory/revise-context.json").read_text())
        self.assertEqual([(q["kind"], q["body"]) for q in context["requests"]],
                         [("review", "a review"), ("inline", "inline"), ("comment", "a comment")])
        self.assertEqual(context["requests"][1]["line"], 4)
        self.assertEqual(context["body"], "The PR's description.\n")
        self.assertEqual(self.lines("summary"), ["Requests since the last revision: 3"])

    def test_same_bytes_as_the_inline_versions(self):
        self.assertEqual(self.run_context().returncode, 0)
        self.assertEqual((self.workspace / ".factory/revise-context.json").read_text(), self.old(self.OLD))
        r = self.run_context("plan", "docs/current_work/sdlc-lite/d12_x_plan.md", "D12")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.workspace / ".factory/revise-context.json").read_text(),
                         self.old(self.OLD_DOC, "--arg", "stage", "plan", "--arg", "document",
                                  "docs/current_work/sdlc-lite/d12_x_plan.md", "--arg", "deliverable", "D12"))

    def test_an_execution_pr_names_its_plan_and_next_gate(self):
        self.env["PLAN"] = "docs/current_work/sdlc-lite/d19_x_plan.md"
        self.env["NEXT_GATE"] = "G1"
        r = self.run_context()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        context = json.loads((self.workspace / ".factory/revise-context.json").read_text())
        self.assertEqual(list(context)[:4], ["pr", "issue", "plan", "gate"])
        self.assertEqual((context["plan"], context["gate"]), ("docs/current_work/sdlc-lite/d19_x_plan.md", "G1"))
        # A plan with no gate left: the plan, no gate.
        self.env["NEXT_GATE"] = ""
        self.assertEqual(self.run_context().returncode, 0)
        context = json.loads((self.workspace / ".factory/revise-context.json").read_text())
        self.assertEqual(context["plan"], "docs/current_work/sdlc-lite/d19_x_plan.md")
        self.assertNotIn("gate", context)
        self.env["PLAN"] = ""
        self.assertEqual(self.run_context().returncode, 0)
        context = json.loads((self.workspace / ".factory/revise-context.json").read_text())
        self.assertNotIn("plan", context)
        self.assertNotIn("gate", context)

    def test_nothing_new_is_refused(self):
        self.data["repos/o/r/issues/5/comments"].append(
            {"user": {"type": "Bot", "id": APP["user_id"]}, "created_at": "2026-10-12T00:00:00Z",
             "body": "<!-- factory-revise: 2 -->\nRevised again."})
        r = self.run_context()
        self.assertEqual(r.returncode, 1)
        self.assertIn("::error::no review comments since the last revision", r.stdout)
        self.assertFalse((self.workspace / ".factory/revise-context.json").exists())


@NEEDS_JQ
class Stats(AgentJob):
    def test_cost_turns_and_models_of_the_last_result(self):
        exec_file = self.root / "exec.json"
        exec_file.write_text(json.dumps([
            {"type": "result", "total_cost_usd": 1, "num_turns": 2},
            {"type": "result", "total_cost_usd": 4.5, "num_turns": 40,
             "modelUsage": {"claude-sonnet-5-5": {}, "claude-opus-5-5": {}}}]))
        r = self.run_script("stats", env={**self.env, "EXEC": str(exec_file)})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.lines("output"),
                         ['stats={"cost":4.5,"turns":40,"models":["claude-opus-5-5","claude-sonnet-5-5"]}'])


class Lost(AgentJob):
    def test_reports_why_and_whether_the_log_was_kept(self):
        # A copy of the script beside a stand-in session_log.sh that echoes what it was given.
        d = self.root / "factory"
        d.mkdir()
        shutil.copy(SCRIPT, d)
        (d / "session_log.sh").write_text('#!/usr/bin/env bash\necho "why=stopped at the $3-minute limit ($1 $2 [$4])"\n'
                                          'echo saved=yes\n')
        (d / "session_log.sh").chmod(0o755)
        r = self.run_script("lost", "revise", script=d / "agent_job.sh", env={**self.env, "AGENT_MINUTES": "240"})
        self.assertEqual(r.returncode, 0, r.stderr)
        why = f"stopped at the 240-minute limit ({self.temp}/agent-start {self.temp}/session-log [])"
        self.assertEqual(self.lines("output"), [f"why={why}", "saved=yes"])
        self.assertIn(f"::error::The revise agent {why}.", r.stdout)
        self.assertEqual(self.lines("summary"), [f"The revise agent {why}. Session log kept: yes"])


@unittest.skipUnless(os.access("/usr/local/bin/python3", os.X_OK), "needs the job image's /usr/local/bin/python3")
class Metrics(AgentJob):
    def test_writes_the_record(self):
        r = self.run_script("metrics", "revise", env={**self.env, "ISSUE_NUMBER": "7", "WORKFLOW": "factory-revise"})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        record = json.loads((self.temp / "metrics/metrics.json").read_text())
        self.assertEqual((record.get("stage"), record.get("issue")), ("revise", 7))


class Services(AgentJob):
    """services runs the stack profile's test-services.sh with the project's database, into its env file."""

    def setUp(self):
        super().setUp()
        self.factory = self.root / "factory"
        (self.factory / "profiles/stub").mkdir(parents=True)
        shutil.copy(SCRIPT, self.factory)
        (self.factory / "factory.json").write_text(json.dumps({"stack": {
            "profile": "stub", "python": "srv", "node": "ui", "env_file": "srv/.env", "database": "projdb"}}))
        (self.factory / "profiles/stub/test-services.sh").write_text('#!/usr/bin/env bash\necho "dir=$1 db=$2"\n')
        (self.factory / "profiles/stub/test-services.sh").chmod(0o755)
        self.workspace = self.root / "ws"
        (self.workspace / "srv").mkdir(parents=True)
        self.env["GITHUB_WORKSPACE"] = str(self.workspace)

    def test_into_the_projects_env_file(self):
        r = self.run_script("services", script=self.factory / "agent_job.sh")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual((self.workspace / "srv/.env").read_text(), f"dir={self.workspace}/.factory/db db=projdb\n")

    def test_into_a_named_file(self):
        out = self.root / "elsewhere"
        self.assertEqual(self.run_script("services", str(out), script=self.factory / "agent_job.sh").returncode, 0)
        self.assertTrue(out.read_text().startswith("dir="))
        self.assertFalse((self.workspace / "srv/.env").exists())

    def test_a_profile_that_doesnt_exist(self):
        (self.factory / "factory.json").write_text(json.dumps({"stack": {"profile": "nope"}}))
        r = self.run_script("services", script=self.factory / "agent_job.sh")
        self.assertEqual(r.returncode, 1)
        self.assertIn("names no profile", r.stdout)


class Verify(unittest.TestCase):
    """The python-node profile's verify: the commands the factory's skills used to name, per area."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = pathlib.Path(self.tmp.name)
        shutil.copy(FACTORY / "profiles/python-node/verify", self.dir)
        (self.dir / "verify.conf").write_text("python=api\nnode=web\n")

    def tearDown(self):
        self.tmp.cleanup()

    def verify(self, *args):
        # In the temp directory: verify's directories are relative, and a checkout may have its own (web/).
        return subprocess.run(["bash", str(self.dir / "verify"), *args], capture_output=True, text=True, cwd=self.dir)

    def test_print_shows_the_commands(self):
        r = self.verify("--print")
        self.assertEqual(r.returncode, 0, r.stderr)
        wrap = f"{self.dir}/with-test-services"
        self.assertEqual(r.stdout.splitlines(), [
            f"python: {wrap} bash -c 'cd api && python -m pytest -q'",
            "node: cd web && npx --no-install eslint . && npx --no-install tsc -b && npx --no-install vite build"])
        self.assertIn("echo probe-ok", self.verify("--print", "probe").stdout)

    def test_runs_every_area_and_reports_the_failures(self):
        # Stand-ins: a wrapper that runs its command, and neither directory exists, so both areas fail.
        (self.dir / "with-test-services").write_text('#!/usr/bin/env bash\nexec "$@"\n')
        (self.dir / "with-test-services").chmod(0o755)
        r = self.verify("python", "node")
        self.assertEqual(r.returncode, 1)
        self.assertIn("== verify python:", r.stdout)
        self.assertIn("== verify node:", r.stdout)
        self.assertIn("verify: failed: python node", r.stdout)

    def test_unknown_area_or_missing_conf(self):
        self.assertEqual(self.verify("everything").returncode, 2)
        (self.dir / "verify.conf").write_text("")
        self.assertEqual(self.verify("--print").returncode, 2)


class VerifyDotnetNode(Verify):
    """The dotnet-node profile's verify: verify.conf's python= is the .NET directory."""

    def setUp(self):
        super().setUp()
        shutil.copy(FACTORY / "profiles/dotnet-node/verify", self.dir)
        (self.dir / "verify.conf").write_text("python=.\nnode=src/Web\n")

    def test_print_shows_the_commands(self):
        r = self.verify("--print")
        self.assertEqual(r.returncode, 0, r.stderr)
        wrap = f"{self.dir}/with-test-services"
        lines = r.stdout.splitlines()
        # The note first: an agent's own dotnet commands need -m:1 in the sandbox too.
        self.assertIn("-m:1", lines[0])
        self.assertEqual(lines[1:], [
            f"dotnet: {wrap} bash -c 'cd . && dotnet test --no-restore -c Release -m:1"
            " --filter \"Category!=Nightly&Category!=External\"'",
            "node: cd src/Web && node_modules/.bin/eslint . && node_modules/.bin/tsc -b"
            " && node_modules/.bin/vitest run && node_modules/.bin/vite build"])
        probe = self.verify("--print", "probe").stdout
        self.assertIn("dotnet build --no-restore -c Release -m:1", probe)
        self.assertIn("echo probe-ok", probe)

    def test_runs_every_area_and_reports_the_failures(self):
        (self.dir / "with-test-services").write_text('#!/usr/bin/env bash\nexec "$@"\n')
        (self.dir / "with-test-services").chmod(0o755)
        (self.dir / "verify.conf").write_text("python=no-such-dir\nnode=no-such-dir\n")
        r = self.verify("dotnet", "node")
        self.assertEqual(r.returncode, 1)
        self.assertIn("== verify dotnet:", r.stdout)
        self.assertIn("== verify node:", r.stdout)
        self.assertIn("verify: failed: dotnet node", r.stdout)
        # The python-node area names aren't this profile's.
        self.assertEqual(self.verify("python").returncode, 2)


class Usage(AgentJob):
    def test_unknown_command(self):
        self.assertEqual(self.run_script("nope").returncode, 2)
        self.assertEqual(self.run_script().returncode, 2)


if __name__ == "__main__":
    unittest.main()
