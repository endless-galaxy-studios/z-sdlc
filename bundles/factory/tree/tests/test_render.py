"""Tests for render.py: this project's workflows are its templates rendered with its factory.json, byte for
byte; another project's settings render workflows that pass workflow_policy.py with none of this project's
values left; and what the renderer refuses."""

import contextlib
import importlib.util
import io
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

FACTORY = pathlib.Path(__file__).resolve().parents[1]
WORKFLOWS = FACTORY.parent / "workflows"
sys.path.insert(0, str(FACTORY))

import render  # noqa: E402

HAS_YAML = importlib.util.find_spec("yaml") is not None


def quiet_main(args):
    """render.main, with its output (::error:: lines CI would annotate) captured."""
    with contextlib.redirect_stdout(io.StringIO()):
        return render.main(args)

# Another project: every setting differs from any real project's.
OTHER = {
    "app": {"user_id": 123456, "login": "other-factory[bot]"},
    "image": {"repository": "ghcr.io/other-org/job", "digest": "sha256:" + "b" * 64},
    "runners": {"strict": "strict-pool", "planning": "plan-pool", "production": "prod-pool"},
    "environments": {"writer": "writer-env", "planning": "planning-env", "production": "production-env"},
    "models": {
        "triage": {"default": "claude-test-a", "options": ["claude-test-a", "claude-test-b"]},
        "implement": {"default": "claude-test-b", "options": ["claude-test-b"]},
        "plan": {"default": "claude-test-c", "options": ["claude-test-c", "claude-test-a"]},
        "revise": "claude-test-d", "revise_doc": "claude-test-e", "improve": "claude-test-f",
        "smoke": {"default": "claude-test-a", "options": ["claude-test-a"]},
        "probe": "claude-test-g",
    },
    "limits": {"agent_minutes": 100, "code_revisions": 2, "doc_revisions": 4},
    "improve": {"cron": "5 4 * * 1"},
    "smoke": {"echo_host": "echo.other.example", "host_probes": "10.9.9.9 10.9.9.10"},
    "stack": {"profile": "python-node", "python": "server", "node": "client", "env_file": "server/.env",
              "database": "otherdb", "env": {}},
}
OTHER_PLANNING = {"database": {"host": "10.0.0.9", "port": 5433, "name": "otherdb", "user": "reader2", "local_port": 7432}}
THIS = json.loads((FACTORY / "factory.json").read_text())
THIS_PLANNING = json.loads((FACTORY / "planning.json").read_text()) if (FACTORY / "planning.json").exists() else {}


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from strings(v)


def this_projects_values():
    """This project's settings as they appear in its rendered workflows (values too short to be telling left out)."""
    c, db = THIS, THIS_PLANNING.get("database") or {}
    values = [str(c["app"]["user_id"]), c["app"]["login"].removesuffix("[bot]"), *c["environments"].values(),
              c["image"]["repository"], c["image"]["digest"].removeprefix("sha256:")[:8],
              *(f"[self-hosted, {label}]" for label in c["runners"].values() if isinstance(label, str)),
              *strings(c["models"]), f'"{c["improve"]["cron"]}"', f'AGENT_MINUTES: "{c["limits"]["agent_minutes"]}"',
              f'REVISION_LIMIT: "{c["limits"]["code_revisions"]}"', f'REVISION_LIMIT: "{c["limits"]["doc_revisions"]}"',
              c["smoke"]["echo_host"]]
    if db.get("host"):
        values += [f"database {db['name']}", f"127.0.0.1:{db['local_port']}"]
    return [v for v in dict.fromkeys(values) if len(v) >= 4]


class ThisProject(unittest.TestCase):
    def test_the_workflows_are_the_templates_rendered(self):
        rendered = render.render_all(FACTORY, FACTORY / "templates")
        on_disk = {p.name: p.read_text() for p in WORKFLOWS.glob("factory-*.yml")}
        self.assertEqual(sorted(rendered), sorted(on_disk))
        for name, text in rendered.items():
            with self.subTest(workflow=name):
                self.assertEqual(text, on_disk[name], f"{name}: edit templates/{name}, then run render.py")

    def test_check_mode_passes(self):
        self.assertEqual(quiet_main(["--check"]), 0)


class AnotherProject(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = pathlib.Path(self.tmp.name)
        # The other project's factory directory: this project's files, its own settings.
        self.factory = root / "factory"
        shutil.copytree(FACTORY, self.factory, ignore=shutil.ignore_patterns("tests", "templates", "__pycache__"))
        (self.factory / "factory.json").write_text(json.dumps(OTHER))
        (self.factory / "planning.json").write_text(json.dumps(OTHER_PLANNING))
        self.out = root / "workflows"
        self.out.mkdir()
        self.rendered = render.render_all(self.factory, FACTORY / "templates")
        for name, text in self.rendered.items():
            (self.out / name).write_text(text)

    def tearDown(self):
        self.tmp.cleanup()

    def test_none_of_this_projects_settings_are_left(self):
        for name, text in self.rendered.items():
            for value in this_projects_values():
                with self.subTest(workflow=name, value=value):
                    self.assertNotIn(value, text)

    def test_its_settings_are_where_this_projects_were(self):
        implement = self.rendered["factory-implement.yml"]
        self.assertIn("runs-on: [self-hosted, strict-pool]", implement)
        self.assertIn("image: ghcr.io/other-org/job@sha256:" + "b" * 64, implement)
        self.assertIn("timeout-minutes: 130", implement)
        self.assertIn('AGENT_MINUTES: "100"', implement)
        self.assertIn("options: [claude-test-b]", implement)
        self.assertIn('bot_id: "123456"', implement)
        self.assertIn("bot_name: other-factory[bot]", implement)
        plan = self.rendered["factory-plan.yml"]
        self.assertIn("runs-on: [self-hosted, plan-pool]", plan)
        self.assertIn("environment: planning-env", plan)
        self.assertIn("timeout-minutes: 145", plan)
        self.assertIn("127.0.0.1:7432 (database otherdb, user reader2,", plan)
        self.assertIn("psql -h 127.0.0.1 -p 7432 -U reader2 otherdb.", plan)
        self.assertIn('cron: "5 4 * * 1"', self.rendered["factory-improve.yml"])
        smoke = self.rendered["factory-smoke.yml"]
        self.assertIn('allowedDomains = ["echo.other.example"]', smoke)
        self.assertIn("bash /opt/factory-probe/services_probe.sh echo.other.example", smoke)
        self.assertIn('FACTORY_HOST_PROBES: "10.9.9.9 10.9.9.10 172.17.0.1 10.0.2.2"', smoke)
        self.assertIn("runs-on: [self-hosted, prod-pool]", self.rendered["factory-gate.yml"])
        # No fixtures block (a project from before it): the fixtures jobs render, and are skipped.
        for name in ("factory-implement.yml", "factory-revise.yml"):
            self.assertIn("      '' != '' && ", self.rendered[name])
            self.assertIn("secrets[''] }}", self.rendered[name])

    @unittest.skipUnless(HAS_YAML, "needs PyYAML")
    def test_the_policy_holds_with_its_labels_and_environments(self):
        # ci.yml isn't the factory's; the policy checks the factory workflows of the other project.
        r = subprocess.run([sys.executable, str(FACTORY / "workflow_policy.py"), str(self.out), str(self.factory)],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("0 violations", r.stdout)

    @unittest.skipUnless(HAS_YAML, "needs PyYAML")
    def test_the_policy_reads_the_labels_from_factory_json(self):
        # With this project's factory.json, the other project's planning jobs are on unknown runners.
        shutil.copy(FACTORY / "factory.json", self.factory / "factory.json")
        r = subprocess.run([sys.executable, str(FACTORY / "workflow_policy.py"), str(self.out), str(self.factory)],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)
        self.assertIn(f"a planning agent job must run on {THIS['runners']['planning']} runners", r.stdout)


FIXTURES = {"path": "tools/art/cache", "run": "IDS=A,B tools/art/sync.sh", "secret": "ART_API_KEY", "apt": "webp",
            "cache_key": "art-v1", "key_files": "tools/art/sync.sh"}


@unittest.skipUnless(HAS_YAML, "needs PyYAML")
class Fixtures(unittest.TestCase):
    """A project with fixtures (D2 rule 7): the fixtures job renders with its settings and passes the
    policy; the policy refuses each way the job or its secret could reach further."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = pathlib.Path(self.tmp.name)
        self.factory = root / "factory"
        shutil.copytree(FACTORY, self.factory, ignore=shutil.ignore_patterns("tests", "templates", "__pycache__"))
        self.settings = {**OTHER, "fixtures": dict(FIXTURES)}
        self.write_settings()
        (self.factory / "planning.json").write_text(json.dumps(OTHER_PLANNING))
        self.out = root / "workflows"
        self.out.mkdir()
        self.rendered = render.render_all(self.factory, FACTORY / "templates")
        for name, text in self.rendered.items():
            (self.out / name).write_text(text)

    def tearDown(self):
        self.tmp.cleanup()

    def write_settings(self):
        (self.factory / "factory.json").write_text(json.dumps(self.settings))

    def policy(self):
        r = subprocess.run([sys.executable, str(FACTORY / "workflow_policy.py"), str(self.out), str(self.factory)],
                           capture_output=True, text=True)
        return r.returncode, r.stdout

    def edit(self, name, old, new):
        text = (self.out / name).read_text()
        self.assertIn(old, text)
        (self.out / name).write_text(text.replace(old, new, 1))

    def test_the_job_renders_and_holds(self):
        for name in ("factory-implement.yml", "factory-revise.yml"):
            text = self.rendered[name]
            with self.subTest(workflow=name):
                self.assertIn("      'tools/art/cache' != '' && ", text)
                self.assertIn("key: art-v1-${{ hashFiles('tools/art/sync.sh') }}", text)
                self.assertIn("FIXTURE_SECRET: ${{ secrets['ART_API_KEY'] }}", text)
                self.assertIn("          IDS=A,B tools/art/sync.sh\n", text)
                self.assertIn("if: needs.fixtures.result == 'success'", text)
                # The secret is named only in the fixtures job.
                jobs = text.split("\n  fixtures:\n", 1)[1].split("\n  implement:\n" if "implement" in name
                                                                   else "\n  revise:\n", 1)
                self.assertIn("ART_API_KEY", jobs[0])
                self.assertNotIn("ART_API_KEY", jobs[1])
        self.assertEqual(self.policy(), (0, "workflow policy: 19 workflows, 0 violations\n"))

    def test_a_projects_own_fixtures_job_is_its_own(self):
        # The policy reads every workflow; a project's ci.yml may have a job of that name.
        (self.out / "ci.yml").write_text("on: push\njobs:\n  fixtures:\n    runs-on: ubuntu-latest\n    steps:\n"
                                          "      - run: make fixtures\n        env:\n          K: ${{ secrets.OTHER_KEY }}\n")
        self.assertEqual(self.policy(), (0, "workflow policy: 20 workflows, 0 violations\n"))

    def test_the_secret_in_an_agent_job(self):
        self.edit("factory-implement.yml", "          ADVISOR: ${{ inputs.advisor || 'none' }}\n",
                  "          ADVISOR: ${{ inputs.advisor || 'none' }}\n          ART: ${{ secrets.ART_API_KEY }}\n")
        code, out = self.policy()
        self.assertEqual(code, 1)
        self.assertIn("implement: references the fixtures secret ART_API_KEY", out)

    def test_a_factory_branch_checkout(self):
        self.edit("factory-revise.yml", "          ref: ${{ github.event.repository.default_branch }}\n          persist-credentials: false\n\n"
                  "      # The project's CI", "          ref: ${{ needs.gate.outputs.branch }}\n          persist-credentials: false\n\n"
                  "      # The project's CI")
        code, out = self.policy()
        self.assertEqual(code, 1)
        self.assertIn("fixtures: the fixtures job checks out the default branch once", out)

    def test_a_self_hosted_runner_outputs_or_another_action(self):
        self.edit("factory-implement.yml", "    runs-on: ubuntu-latest\n    timeout-minutes: 15\n",
                  "    runs-on: [self-hosted, strict-pool]\n    timeout-minutes: 15\n    outputs:\n      x: y\n")
        self.edit("factory-implement.yml", "      - uses: actions/cache@", "      - uses: someone/cache@")
        code, out = self.policy()
        self.assertEqual(code, 1)
        self.assertIn("fixtures: the fixtures job runs on a GitHub-hosted runner", out)
        self.assertIn("fixtures: the fixtures job has no outputs", out)
        self.assertIn("action not allowed in the fixtures job: someone/cache@", out)

    def test_a_secret_any_other_way(self):
        self.edit("factory-implement.yml", "          FIXTURE_PATH: tools/art/cache\n",
                  "          FIXTURE_PATH: tools/art/cache\n          OTHER: ${{ secrets.OTHER_KEY }}\n")
        code, out = self.policy()
        self.assertEqual(code, 1)
        self.assertIn("env OTHER: a fixtures job's secret is", out)

    def test_settings_that_would_change_the_workflow(self):
        for key, value in (("run", "x ${{ secrets.OTHER_KEY }}"), ("path", "a'b"), ("path", "../up"),
                           ("secret", "A-B"), ("apt", "webp; curl x"), ("key_files", "a') || ('b")):
            with self.subTest(key=key, value=value):
                self.settings["fixtures"] = {**FIXTURES, key: value}
                self.write_settings()
                code, out = self.policy()
                self.assertEqual(code, 1)
                self.assertIn(f"factory.json fixtures.{key}:", out)
        self.settings["fixtures"] = {**FIXTURES, "run": ""}
        self.write_settings()
        self.assertIn("a path needs run, cache_key and key_files", self.policy()[1])


COMPOSITE = "runs:\n  using: composite\n  steps:\n{steps}"
RUN = "    - shell: bash\n      run: {run}\n"
CI = "on: pull_request\njobs:\n{jobs}"
JOB = "  {name}:\n    runs-on: {runs_on}\n{extra}    steps:\n      - uses: {uses}\n"
REASON = "the end-to-end suites need a larger machine than hosted runners give"


@unittest.skipUnless(HAS_YAML, "needs PyYAML")
class ProjectWorkflows(unittest.TestCase):
    """The policy reads the project's own workflows too. Local composite actions are scanned as the job's own
    steps; the organization's hosted labels count as hosted; and a self-hosted CI job runs without the factory
    container only by a named, reasoned exemption, which never reaches the factory's secret rules."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = pathlib.Path(self.tmp.name) / "repo"
        self.factory = self.repo / ".github/factory"
        shutil.copytree(FACTORY, self.factory, ignore=shutil.ignore_patterns("tests", "templates", "__pycache__"))
        self.settings = json.loads(json.dumps(OTHER))
        self.write_settings()
        (self.factory / "planning.json").write_text(json.dumps(OTHER_PLANNING))
        self.workflows = self.repo / ".github/workflows"
        self.workflows.mkdir()
        for name, text in render.render_all(self.factory, FACTORY / "templates").items():
            (self.workflows / name).write_text(text)

    def tearDown(self):
        self.tmp.cleanup()

    def write_settings(self):
        (self.factory / "factory.json").write_text(json.dumps(self.settings))

    def set_policy(self, **policy):
        self.settings["policy"] = {"hosted_labels": [], "self_hosted_exemptions": [], **policy}
        self.write_settings()

    def ci(self, *jobs):
        (self.workflows / "ci.yml").write_text(CI.format(jobs="".join(jobs)))

    def action(self, path, text):
        (self.repo / path).mkdir(parents=True, exist_ok=True)
        (self.repo / path / "action.yml").write_text(text)

    def policy(self):
        r = subprocess.run([sys.executable, str(FACTORY / "workflow_policy.py"), str(self.workflows), str(self.factory)],
                           capture_output=True, text=True)
        return r.returncode, r.stdout

    def test_a_composite_action_is_scanned_as_the_jobs_own_steps(self):
        self.action(".github/actions/setup", COMPOSITE.format(steps=RUN.format(run="echo setup")
                                                             + "    - uses: ./.github/actions/inner\n"))
        self.action(".github/actions/inner", COMPOSITE.format(steps=RUN.format(run="echo inner")))
        self.ci(JOB.format(name="test", runs_on="ubuntu-latest", extra="", uses="./.github/actions/setup"))
        self.assertEqual(self.policy(), (0, "workflow policy: 20 workflows, 0 violations\n"))
        # A nested action's step is checked like any other.
        self.action(".github/actions/inner", COMPOSITE.format(steps=RUN.format(run="claude -p hello")))
        code, out = self.policy()
        self.assertEqual(code, 1)
        self.assertIn("test / run: runs Claude Code outside the action", out)

    def test_what_cant_be_scanned_is_refused(self):
        self.action(".github/actions/js", "runs:\n  using: node24\n  main: index.js\n")
        self.action(".github/actions/self", COMPOSITE.format(steps="    - uses: ./.github/actions/self\n"))
        self.action(".github/actions/agent", COMPOSITE.format(steps="    - uses: anthropics/claude-code-action@v1\n"))
        self.ci(*(JOB.format(name=f"j{i}", runs_on="ubuntu-latest", extra="", uses=uses) for i, uses in enumerate(
            ["./.github/actions/js", "./.github/actions/missing", "./../outside", "./.github/actions/self",
             "./.github/actions/agent"])))
        code, out = self.policy()
        self.assertEqual(code, 1)
        for message in ("j0: local action ./.github/actions/js runs node24, not composite steps",
                        "j1: local action ./.github/actions/missing has no action.yml or action.yaml",
                        "j2: local action ./../outside is outside the repository",
                        "j3: local action ./.github/actions/self uses itself",
                        "j4: agent step inside local action ./.github/actions/agent"):
            self.assertIn(message, out)

    def test_an_agent_job_runs_no_local_action(self):
        self.action(".github/actions/setup", COMPOSITE.format(steps=RUN.format(run="echo setup")))
        self.ci("  agent:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: ./.github/actions/setup\n"
                "      - uses: anthropics/claude-code-action@v1\n")
        code, out = self.policy()
        self.assertEqual(code, 1)
        self.assertIn("agent: an agent job runs no local action", out)

    def test_the_factorys_secrets_inside_a_local_action(self):
        self.action(".github/actions/leak", COMPOSITE.format(
            steps="    - shell: bash\n      run: echo\n      env:\n        T: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}\n"))
        self.ci(JOB.format(name="test", runs_on="ubuntu-latest", extra="", uses="./.github/actions/leak"))
        code, out = self.policy()
        self.assertEqual(code, 1)
        self.assertIn("OAuth token in env outside an agent job's run step", out)

    def test_a_job_after_one_that_carries_on_needs_a_status_function_too(self):
        # factory-revise.yml's stop-at-gate as #78 merged it: skipped whenever the fixtures job was.
        path = self.workflows / "factory-revise.yml"
        text = path.read_text()
        old = "      !cancelled() && needs.report.result == 'success'"
        self.assertIn(old, text)
        path.write_text(text.replace(old, "      needs.report.result == 'success'", 1))
        code, out = self.policy()
        self.assertEqual(code, 1)
        self.assertIn("factory-revise.yml: stop-at-gate: runs after publish, report, revise, which carry on past a "
                      "skipped or failed job, so its `if` needs a status function too", out)
        # A project's own workflows are its own.
        path.write_text(text)
        self.ci(JOB.format(name="build", runs_on="ubuntu-latest", extra="    if: always()\n", uses="actions/checkout@v4"),
                JOB.format(name="test", runs_on="ubuntu-latest", extra="    needs: build\n", uses="actions/checkout@v4"))
        self.assertEqual(self.policy(), (0, "workflow policy: 20 workflows, 0 violations\n"))

    def test_the_organizations_hosted_labels(self):
        self.ci(JOB.format(name="big", runs_on="org-linux-16core", extra="", uses="actions/checkout@v4"))
        code, out = self.policy()
        self.assertIn("big: runs off GitHub-hosted runners without a container", out)
        self.set_policy(hosted_labels=["org-linux-16core"])
        self.assertEqual(self.policy(), (0, "workflow policy: 20 workflows, 0 violations\n"))
        # Labels every self-hosted runner carries (GitHub matches them without regard to case), or a factory runner's.
        for label in ("self-hosted", "Linux", "x64", "ARM64", "strict-pool", "Strict-Pool", "has space"):
            with self.subTest(label=label):
                self.set_policy(hosted_labels=["org-linux-16core", label])
                code, out = self.policy()
                self.assertEqual(code, 1)
                self.assertIn("isn't a GitHub-hosted runner label", out)

    def test_an_exemption_lets_one_named_job_through(self):
        services = "    services:\n      postgres:\n        image: postgres:16\n"
        self.ci(JOB.format(name="e2e", runs_on="[self-hosted, ci-box]", extra=services, uses="actions/checkout@v4"),
                JOB.format(name="e2e-new", runs_on="[self-hosted, ci-box]", extra="", uses="actions/checkout@v4"))
        code, out = self.policy()
        self.assertIn("e2e: runs service containers off GitHub-hosted runners", out)
        self.set_policy(self_hosted_exemptions=[{"workflow": "ci.yml", "job": "e2e", "reason": REASON}])
        code, out = self.policy()
        self.assertIn(f"::notice::ci.yml: e2e: runs on a self-hosted runner without the factory container", out)
        errors = [line for line in out.splitlines() if line.startswith("::error::")]
        self.assertFalse([line for line in errors if "ci.yml: e2e: " in line], errors)
        # Only the job it names: a new self-hosted job is still a violation.
        self.assertEqual(code, 1)
        self.assertIn("e2e-new: runs off GitHub-hosted runners without a container", out)

    def test_an_exemption_never_reaches_the_secret_rules(self):
        self.ci("  e2e:\n    runs-on: [self-hosted, ci-box]\n    steps:\n      - run: echo\n        env:\n"
                "          T: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}\n          K: ${{ secrets.FACTORY_APP_PRIVATE_KEY }}\n")
        self.set_policy(self_hosted_exemptions=[{"workflow": "ci.yml", "job": "e2e", "reason": REASON}])
        code, out = self.policy()
        self.assertEqual(code, 1)
        self.assertIn("OAuth token in env outside an agent job's run step", out)
        self.assertIn("App key outside create-github-app-token's private-key", out)

    # The job runs in its disposable runner container: no container of its own.
    CI_JOB = ("  e2e:\n    runs-on: [self-hosted, ci-pool]\n    permissions:\n      contents: read\n"
              "    steps:\n      - uses: actions/checkout@v4\n        with:\n          persist-credentials: false\n"
              "      - run: make e2e\n")

    def ci_tier(self, job=None, workflow="ci.yml"):
        self.settings["runners"] = {**OTHER["runners"], "ci": "ci-pool"}
        self.write_settings()
        (self.workflows / workflow).write_text(CI.format(jobs=job or self.CI_JOB))

    def test_a_ci_tier_job_that_holds_nothing(self):
        # No container (it runs in the launcher's), read-only, no persisted credentials, no secret, no job token.
        self.ci_tier()
        self.assertEqual(self.policy(), (0, "workflow policy: 20 workflows, 0 violations\n"))

    def test_what_a_ci_tier_job_may_not_do(self):
        cases = [
            (("persist-credentials: false", "fetch-depth: 0"), "checkout sets persist-credentials: false"),
            (("contents: read", "contents: write"), "needs explicit read-only permissions"),
            (("      - run: make e2e\n", "      - run: make e2e\n        env:\n          K: ${{ secrets.ART_KEY }}\n"),
             "holds no secret and no job token"),
            (("      - run: make e2e\n", "      - run: make e2e\n        env:\n          GH_TOKEN: ${{ github.token }}\n"),
             "holds no secret and no job token"),
            (("    steps:\n", "    container:\n      image: ghcr.io/other-org/e2e@sha256:" + "c" * 64 + "\n    steps:\n"),
             "with no container of its own"),
            (("    steps:\n", "    services:\n      pg:\n        image: postgres:16\n    steps:\n"),
             "with no service containers of its own"),
            (("      - run: make e2e\n", "      - uses: docker://alpine:3\n"), "runs no docker:// step"),
            (("      - run: make e2e\n", "      - uses: anthropics/claude-code-action@v1\n"), "no agent job runs on the CI tier"),
        ]
        for (old, new), message in cases:
            with self.subTest(message=message):
                self.assertIn(old, self.CI_JOB)
                self.ci_tier(self.CI_JOB.replace(old, new, 1))
                code, out = self.policy()
                self.assertEqual(code, 1)
                self.assertIn(message, out)

    def test_the_ci_tier_is_for_a_projects_own_workflows(self):
        self.ci_tier(workflow="factory-extra.yml")
        code, out = self.policy()
        self.assertEqual(code, 1)
        self.assertIn("only a project's own workflows run on the CI tier (ci-pool)", out)
        # And its label is one of the factory's: never a hosted label, never exempt.
        self.set_policy(hosted_labels=["ci-pool"])
        self.assertIn("isn't a GitHub-hosted runner label", self.policy()[1])

    def test_exemptions_that_cant_hold(self):
        self.ci(JOB.format(name="hosted", runs_on="ubuntu-latest", extra="", uses="actions/checkout@v4"),
                JOB.format(name="pool", runs_on="[self-hosted, strict-pool]", extra="", uses="actions/checkout@v4"),
                JOB.format(name="agent", runs_on="[self-hosted, ci-box]", extra="", uses="anthropics/claude-code-action@v1"))
        entry = lambda **kw: {"workflow": "ci.yml", "job": "hosted", "reason": REASON, **kw}
        cases = [
            ([entry(workflow="factory-implement.yml", job="implement")], "never a factory workflow"),
            ([entry(reason="short")], "reason says why"),
            ([entry(job="gone")], "ci.yml has no job gone"),
            ([entry()], "hosted: has an exemption from the container rule it doesn't need"),
            ([entry(job="pool")], "pool: exempt from the container rule, but an agent job or one on the factory's"),
            ([entry(job="agent")], "agent: exempt from the container rule, but an agent job or one on the factory's"),
            ([entry(), entry()], "listed twice"),
            ([{"workflow": "ci.yml", "job": "hosted"}], "needs exactly workflow, job and reason"),
        ]
        for exemptions, message in cases:
            with self.subTest(message=message):
                self.set_policy(self_hosted_exemptions=exemptions)
                code, out = self.policy()
                self.assertEqual(code, 1)
                self.assertIn(message, out)


class Refusals(unittest.TestCase):
    VALUES = {"a": {"n": 3, "s": "x", "l": ["p", "q"], "b": True}, "_doc": "notes", "planning": {"x": 1}}

    def test_substitution(self):
        self.assertEqual(render.render("%{a.s}:%{a.n}:%{a.n+4}:[%{a.l}]", self.VALUES), "x:3:7:[p, q]")

    def test_an_optional_setting_renders_empty_when_missing(self):
        # A project installed before a setting existed keeps rendering (the fixtures block).
        self.assertEqual(render.render("[%{a.s?}][%{a.z?}][%{z.y?}]", self.VALUES), "[x][][]")
        with self.assertRaises(render.Invalid):
            render.render("%{a?}", self.VALUES)

    def test_unknown_or_group_or_unrenderable(self):
        for template in ("%{a.z}", "%{a}", "%{z.y}", "%{a.b}", "%{a.s+1}"):
            with self.subTest(template=template):
                with self.assertRaises(render.Invalid):
                    render.render(template, self.VALUES)

    def test_a_percent_brace_that_isnt_a_placeholder(self):
        with self.assertRaises(render.Invalid) as e:
            render.render("ok\n%{A}\n", self.VALUES)
        self.assertIn("line 2", str(e.exception))

    def test_unused_settings_are_refused(self):
        with tempfile.TemporaryDirectory() as d:
            d = pathlib.Path(d)
            (d / "templates").mkdir()
            (d / "factory.json").write_text(json.dumps({"a": {"used": 1, "unused": 2}, "_doc": "x"}))
            (d / "templates/factory-x.yml").write_text("v: %{a.used}\n")
            with self.assertRaises(render.Invalid) as e:
                render.render_all(d, d / "templates")
            self.assertIn("a.unused", str(e.exception))

    def test_check_finds_a_hand_edited_workflow_and_a_missing_template(self):
        with tempfile.TemporaryDirectory() as d:
            d = pathlib.Path(d)
            (d / "templates").mkdir()
            (d / "workflows").mkdir()
            (d / "factory.json").write_text(json.dumps({"a": {"v": 1}}))
            (d / "templates/factory-x.yml").write_text("v: %{a.v}\n")
            self.assertEqual(quiet_main([str(d), str(d / "templates"), str(d / "workflows")]), 0)
            self.assertEqual(quiet_main(["--check", str(d), str(d / "templates"), str(d / "workflows")]), 0)
            (d / "workflows/factory-x.yml").write_text((d / "workflows/factory-x.yml").read_text() + "# hand edit\n")
            self.assertEqual(quiet_main(["--check", str(d), str(d / "templates"), str(d / "workflows")]), 1)
            (d / "workflows/factory-x.yml").unlink()
            (d / "workflows/factory-y.yml").write_text("unmanaged\n")
            self.assertEqual(quiet_main(["--check", str(d), str(d / "templates"), str(d / "workflows")]), 1)


if __name__ == "__main__":
    unittest.main()
