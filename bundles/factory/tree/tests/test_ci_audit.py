"""ci_audit.py: the project's own CI read against Enablement step 10. Which triggers carry agent-written code and
which copy of the workflow each runs; which jobs fetch that code (a job's `if:` clears an event only when it can't
be true for a factory PR or push); each finding (secret, checkout, token, runner, head, remote-call, missing,
unreadable); reusable workflows under their callers' events; secret existence by name through a fake gh (names
only, a level it couldn't read is "not checked", never empty); scheduled runs' gaps; exit statuses; --json; and the
script under `python3 -I`. Every workflow is a fixture in a temporary repository: no network, no gh."""

import contextlib
import io
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
import urllib.parse

FACTORY = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FACTORY))

try:
    import yaml  # noqa: F401
    import ci_audit as ci  # noqa: E402
    import workflow_policy as wp  # noqa: E402
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

SETTINGS = {
    "runners": {"strict": "factory", "planning": "factory-plan", "production": "factory-prod", "ci": "factory-ci"},
    "environments": {"writer": "factory-writer", "planning": "factory-planning", "production": "factory-production"},
    "release": {"branch": "release/production"},
    "policy": {"hosted_labels": ["acme-large"], "self_hosted_exemptions": [
        {"workflow": "ci.yml", "job": "gpu", "reason": "an isolated box with no credentials, wiped after each job"}]},
}

# A job that holds to step 10: hosted, read-only token, a checkout that keeps no credentials, no secret.
CLEAN = textwrap.dedent("""
    on: pull_request
    permissions:
      contents: read
    jobs:
      test:
        runs-on: ubuntu-latest
        steps:
          - uses: actions/checkout@v4
            with:
              persist-credentials: false
          - run: make test
""")


def refuse(args):
    raise AssertionError(f"gh called without --repo: {args}")


class FakeGitHub:
    """acme/app on GitHub, through gh: secret names by level, environments, the default branch, the token's
    default, and scheduled runs. Asserts every secrets call asks for names only."""

    def __init__(self):
        self.default_branch = "main"
        self.token_default = "read"
        self.repository = ["NPM_TOKEN", "UNUSED_TOKEN"]
        self.organization = ["ORG_TOKEN"]
        self.environments = {"production": ["DEPLOY_KEY"]}
        self.runs = {}
        self.fail = {}  # a path: gh's error for it
        self.calls = []

    def __call__(self, args):
        self.calls.append(list(args))
        if args[:2] == ["run", "list"]:
            workflow = args[args.index("--workflow") + 1]
            limit = int(args[args.index("--limit") + 1])
            assert args[args.index("--event") + 1] == "schedule" and args[args.index("--repo") + 1] == "acme/app"
            return 0, json.dumps([{"createdAt": t} for t in self.runs.get(workflow, [])[:limit]]), ""
        assert args[0] == "api", args
        rest = [a for a in args[1:] if a != "--paginate"]
        path, jq = rest[0], rest[rest.index("--jq") + 1]
        if path in self.fail:
            return 1, "", self.fail[path] + "\n"
        base = "repos/acme/app"
        if path == base:
            return 0, self.default_branch + "\n", ""
        if path == f"{base}/actions/permissions/workflow":
            return 0, self.token_default + "\n", ""
        names = {f"{base}/actions/secrets": self.repository, f"{base}/actions/organization-secrets": self.organization,
                 f"{base}/environments": list(self.environments)}
        for env, secrets in self.environments.items():
            names[f"{base}/environments/{urllib.parse.quote(env, safe='')}/secrets"] = secrets
        if path not in names:
            return 1, "", "gh: Not Found (HTTP 404)\n"
        assert jq.endswith("[].name"), jq  # names, never values
        return 0, "".join(n + "\n" for n in names[path]), ""


@unittest.skipUnless(HAS_YAML, "needs PyYAML")
class Case(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.workflows = self.tmp / ".github" / "workflows"
        self.workflows.mkdir(parents=True)
        self.factory = self.tmp / ".github" / "factory"
        self.factory.mkdir()
        (self.factory / "factory.json").write_text(json.dumps(SETTINGS))

    def workflow(self, name, text):
        (self.workflows / name).write_text(textwrap.dedent(text))

    def audit(self, **kw):
        kw.setdefault("gh", refuse)
        return ci.audit(self.workflows, self.factory, **kw)

    def found(self, report, level="findings"):
        return sorted((f["workflow"], f["job"], f["rule"]) for f in report[level])

    def messages(self, report, rule, level="findings"):
        return [f["message"] for f in report[level] if f["rule"] == rule]

    def job(self, report, file, job_id):
        workflow = next(w for w in report["workflows"] if w["file"] == file)
        return next(j for j in workflow["jobs"] if j["id"] == job_id)

    def triggers(self, report, file):
        workflow = next(w for w in report["workflows"] if w["file"] == file)
        return {t["event"]: t for t in workflow["triggers"]}

    def main(self, argv, gh=refuse):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            status = ci.main(argv, gh=gh)
        return status, out.getvalue()


class Triggers(Case):
    def test_which_triggers_carry_agent_code_and_which_copy_each_runs(self):
        self.workflow("ci.yml", """
            name: CI
            on:
              push:
              pull_request:
              pull_request_target:
              schedule:
                - cron: "0 3 * * *"
              workflow_dispatch:
            jobs:
              noop:
                runs-on: ubuntu-latest
                steps:
                  - run: "true"
        """)
        self.workflow("after.yml", """
            on:
              workflow_run:
                workflows: [CI]
                types: [completed]
            jobs:
              noop:
                runs-on: ubuntu-latest
                steps:
                  - run: "true"
        """)
        self.workflow("nightly.yml", """
            name: Nightly
            on:
              schedule:
                - cron: "0 1 * * *"
            jobs:
              noop:
                runs-on: ubuntu-latest
                steps:
                  - run: "true"
        """)
        self.workflow("after-nightly.yml", """
            on:
              workflow_run:
                workflows: [Nightly]
            jobs:
              noop:
                runs-on: ubuntu-latest
                steps:
                  - run: "true"
        """)
        report = self.audit()
        t = self.triggers(report, "ci.yml")
        self.assertEqual(t["push"]["agent_code"], "factory pushes")
        self.assertEqual(t["push"]["copy"], "the pushed commit's")
        self.assertEqual(t["pull_request"]["agent_code"], "yes")
        self.assertIn("the PR's own copy", t["pull_request"]["copy"])
        self.assertEqual(t["pull_request_target"]["copy"], "the PR's base branch's")
        self.assertEqual(t["pull_request_target"]["agent_code"], "if a job checks out the PR's head")
        self.assertEqual(t["schedule"]["copy"], "the default branch's")
        self.assertEqual(t["schedule"]["filters"], "cron: 0 3 * * *")
        self.assertEqual(t["workflow_dispatch"]["copy"], "the branch or tag it's dispatched on")
        self.assertEqual(self.triggers(report, "after.yml")["workflow_run"]["agent_code"],
                         "if a job checks out the triggering run's head")
        self.assertEqual(self.triggers(report, "after.yml")["workflow_run"]["copy"], "the default branch's")
        self.assertTrue(self.triggers(report, "after-nightly.yml")["workflow_run"]["agent_code"].startswith("no"))

    def test_push_filters_against_factory_branches(self):
        cases = {
            "branches: [main]": False,
            "branches: ['**']": True,
            "branches: ['factory/*']": True,
            "branches: ['factory/*-split']": True,         # names factory/: matches whatever the samples
            "branches-ignore: ['factory/**']": False,
            "tags: ['v*']": False,
            "branches: ['**', '!factory/**']": False,
            "paths: ['src/**']": True,
        }
        for i, (spec, reaches) in enumerate(cases.items()):
            self.workflow(f"p{i}.yml", f"""
                on:
                  push:
                    {spec}
                jobs:
                  noop:
                    runs-on: ubuntu-latest
                    steps:
                      - run: "true"
            """)
        report = self.audit()
        for i, (spec, reaches) in enumerate(cases.items()):
            self.assertEqual(self.triggers(report, f"p{i}.yml")["push"]["agent_code"],
                             "factory pushes" if reaches else "no", spec)

    def test_a_pr_branch_filter_excludes_factory_prs_only_when_the_default_branch_is_known(self):
        self.workflow("dev.yml", """
            on:
              pull_request:
                branches: [develop]
            jobs:
              noop:
                runs-on: ubuntu-latest
                steps:
                  - run: "true"
        """)
        # Without --repo the default branch is unknown: the filter may let factory PRs through.
        self.assertEqual(self.triggers(self.audit(), "dev.yml")["pull_request"]["agent_code"], "yes")
        report = self.audit(repo="acme/app", gh=FakeGitHub())
        self.assertTrue(self.triggers(report, "dev.yml")["pull_request"]["agent_code"].startswith("no"))
        # The release branch is a base factory PRs target too.
        self.workflow("dev.yml", (self.workflows / "dev.yml").read_text().replace("[develop]", "['release/**']"))
        report = self.audit(repo="acme/app", gh=FakeGitHub())
        self.assertEqual(self.triggers(report, "dev.yml")["pull_request"]["agent_code"], "yes")


class Rules(Case):
    def test_a_clean_job_has_no_findings(self):
        self.workflow("ci.yml", CLEAN)
        report = self.audit()
        self.assertEqual(report["findings"], [])
        job = self.job(report, "ci.yml", "test")
        self.assertTrue(job["agent_code"])
        self.assertEqual(job["agent_events"], ["pull_request"])
        self.assertEqual(self.main([str(self.workflows), "--factory-dir", str(self.factory)])[0], 0)

    def test_secrets_anywhere_in_the_job(self):
        self.workflow("ci.yml", """
            on: pull_request
            permissions:
              contents: read
            env:
              WORKFLOW_WIDE: ${{ secrets.WORKFLOW_WIDE }}
            jobs:
              test:
                runs-on: ubuntu-latest
                env:
                  JOB_WIDE: ${{ secrets.job_wide }}
                steps:
                  - uses: actions/checkout@v4
                    with:
                      persist-credentials: false
                  - name: Install
                    run: npm ci
                    env:
                      NPM_TOKEN: ${{ secrets.NPM_TOKEN }}
                  - uses: some/action@v1
                    with:
                      key: ${{ secrets['INDEXED'] }}
                  - run: echo "${{ secrets.IN_RUN }}" > /dev/null
                  - run: echo secrets.NOT_AN_EXPRESSION
                  - run: echo "${{ steps.secrets.outputs.token }} ${{ needs.secrets.outputs.x }} ${{ inputs.secrets }}"
                  - run: echo "${{ steps.my-secrets.outputs.y }}"
                  - uses: actions/cache@v4
                    with:
                      key: ${{ hashFiles('config/secrets.example', 'secrets') }}
                  - uses: other/action@v1
                    with:
                      token: ${{ secrets.GITHUB_TOKEN }}
                      all: ${{ toJSON(secrets) }}
        """)
        report = self.audit()
        job = self.job(report, "ci.yml", "test")
        by_name = {s["name"]: s for s in job["secrets"]}
        self.assertEqual(sorted(by_name), ["*", "GITHUB_TOKEN", "INDEXED", "IN_RUN", "JOB_WIDE", "NPM_TOKEN",
                                           "WORKFLOW_WIDE"])
        self.assertEqual(by_name["NPM_TOKEN"]["where"], ["step 'Install' env"])
        self.assertEqual(by_name["WORKFLOW_WIDE"]["where"], ["workflow env"])
        self.assertEqual(by_name["JOB_WIDE"]["where"], ["job env"])
        self.assertEqual(by_name["IN_RUN"]["where"], ["step 'run: echo \"${{ secrets.IN_RUN }}\" > /dev/null' run"])
        self.assertEqual(by_name["*"]["where"], ["step 'other/action@v1' with"])  # toJSON(secrets) alone
        self.assertEqual(by_name["GITHUB_TOKEN"]["status"], "built in")
        self.assertEqual(by_name["NPM_TOKEN"]["status"], "not checked")
        secrets = self.messages(report, "secret")
        self.assertEqual(len(secrets), 6)  # every one but the job's own token
        self.assertFalse(any("GITHUB_TOKEN" in m for m in secrets))
        self.assertTrue(any(m.startswith("every secret") for m in secrets))
        self.assertTrue(all("before or after the PR's code runs" in m for m in secrets))

    def test_a_step_if_clears_nothing(self):
        self.workflow("ci.yml", CLEAN.replace("      - run: make test\n", (
            "      - run: make test\n"
            "      - name: Publish\n"
            "        if: github.event_name == 'push'\n"
            "        run: npm publish\n"
            "        env:\n"
            "          NPM_TOKEN: ${{ secrets.NPM_TOKEN }}\n")))
        self.assertEqual(self.found(self.audit()), [("ci.yml", "test", "secret")])

    def test_a_checkout_that_keeps_credentials(self):
        self.workflow("ci.yml", CLEAN.replace("persist-credentials: false", "persist-credentials: true"))
        self.workflow("lint.yml", CLEAN.replace("        with:\n          persist-credentials: false\n", ""))
        report = self.audit()
        self.assertEqual(self.found(report), [("ci.yml", "test", "checkout"), ("lint.yml", "test", "checkout")])
        self.assertEqual(self.job(report, "lint.yml", "test")["checkouts"][0]["persist_credentials"], "unset (true)")
        self.assertEqual(self.job(report, "lint.yml", "test")["checkouts"][0]["ref"], None)

    def test_a_checkout_pinned_to_the_default_branch_runs_no_agent_code(self):
        self.workflow("ci.yml", """
            on: pull_request
            jobs:
              fixtures:
                runs-on: self-hosted
                steps:
                  - uses: actions/checkout@v4
                    with:
                      ref: ${{ github.event.repository.default_branch }}
                  - run: ./fetch.sh
                    env:
                      FIXTURE_KEY: ${{ secrets.FIXTURE_KEY }}
              docs:
                runs-on: ubuntu-latest
                steps:
                  - uses: actions/checkout@v4
                    with:
                      ref: gh-pages
              other:
                runs-on: ubuntu-latest
                steps:
                  - uses: actions/checkout@v4
                    with:
                      repository: acme/tools
        """)
        report = self.audit()
        self.assertEqual(report["findings"], [])
        for job in ("fixtures", "docs", "other"):
            self.assertFalse(self.job(report, "ci.yml", job)["agent_code"], job)

    def test_a_ref_this_audit_cant_read_counts_as_the_prs(self):
        self.workflow("ci.yml", CLEAN.replace("persist-credentials: false", "persist-credentials: false\n"
                                              "          ref: ${{ inputs.ref }}"))
        self.assertTrue(self.job(self.audit(), "ci.yml", "test")["agent_code"])

    def test_the_token(self):
        cases = {
            "": True,                                         # the repository's default, not read
            "permissions: write-all": True,
            "permissions: read-all": False,
            "permissions: {}": False,
            "permissions:\n  contents: read\n  id-token: write": True,
            "permissions:\n  contents: read\n  pull-requests: read": False,
        }
        for i, (block, flagged) in enumerate(cases.items()):
            text = CLEAN.replace("permissions:\n  contents: read\n", block + "\n" if block else "")
            self.workflow(f"t{i}.yml", text)
        report = self.audit()
        flagged = sorted(f"t{i}.yml" for i, f in enumerate(cases.values()) if f)
        self.assertEqual(sorted(f["workflow"] for f in report["findings"] if f["rule"] == "token"), flagged)
        self.assertEqual({f["rule"] for f in report["findings"]}, {"token"})
        # A job's own block wins over the workflow's.
        self.workflow("t9.yml", CLEAN.replace("    runs-on: ubuntu-latest",
                                              "    runs-on: ubuntu-latest\n    permissions:\n      contents: write"))
        self.assertIn(("t9.yml", "test", "token"), self.found(self.audit()))

    def test_a_read_only_repository_default_is_info(self):
        self.workflow("ci.yml", CLEAN.replace("permissions:\n  contents: read\n", ""))
        gh = FakeGitHub()
        report = self.audit(repo="acme/app", gh=gh)
        self.assertEqual(self.found(report), [])
        self.assertEqual(self.messages(report, "token", "info")[0][:40], "its token is read-only by the repository")
        gh.token_default = "write"
        self.assertEqual(self.found(self.audit(repo="acme/app", gh=gh)), [("ci.yml", "test", "token")])

    def test_runners(self):
        runners = {
            "hosted": ("ubuntu-latest", None),
            "larger": ("acme-large", None),             # policy.hosted_labels
            "tier": ("[self-hosted, factory-ci]", None),  # the CI tier
            "bare": ("self-hosted", "runner"),
            "unlisted": ("macos-13", "runner"),          # not in the policy's hosted list: said so
            "boxed": ("[self-hosted, linux]\n    container: ghcr.io/acme/ci@sha256:0", "info"),
            "gpu": ("[self-hosted, gpu]", "info"),         # exempted in factory.json
            "strict": ("[self-hosted, factory]", "runner"),
            "dynamic": ("${{ inputs.runner }}", "runner"),
            "group": ("\n      group: big-runners", "runner"),
        }
        jobs = "".join(f"""
  {name}:
    runs-on: {runs_on}
    steps:
      - uses: actions/checkout@v4
        with:
          persist-credentials: false
""" for name, (runs_on, _) in runners.items())
        self.workflow("ci.yml", "on: pull_request\npermissions:\n  contents: read\njobs:" + jobs)
        report = self.audit()
        findings = {f["job"] for f in report["findings"] if f["rule"] == "runner"}
        info = {f["job"] for f in report["info"] if f["rule"] == "runner"}
        self.assertEqual(findings, {n for n, (_, r) in runners.items() if r == "runner"})
        self.assertEqual(info, {n for n, (_, r) in runners.items() if r == "info"})
        self.assertEqual(self.job(report, "ci.yml", "tier")["runner"]["kind"], "ci-tier")
        self.assertEqual(self.job(report, "ci.yml", "larger")["runner"]["kind"], "hosted")
        self.assertEqual(self.job(report, "ci.yml", "dynamic")["runner"]["kind"], "unknown")
        self.assertEqual(self.job(report, "ci.yml", "unlisted")["runner"]["kind"], "unlisted")
        unlisted = [f["message"] for f in report["findings"] if f["job"] == "unlisted"][0]
        self.assertIn("doesn't list as GitHub-hosted", unlisted)
        self.assertIn("policy.hosted_labels", unlisted)

    def test_a_matrix_runner_is_read_from_its_values(self):
        self.workflow("ci.yml", """
            on: pull_request
            permissions:
              contents: read
            jobs:
              test:
                strategy:
                  matrix:
                    os: [ubuntu-latest, macos-latest]
                    include:
                      - os: [self-hosted, linux]
                runs-on: ${{ matrix.os }}
                steps:
                  - uses: actions/checkout@v4
                    with:
                      persist-credentials: false
        """)
        report = self.audit()
        self.assertEqual(self.job(report, "ci.yml", "test")["runner"]["kind"], "self-hosted")
        self.assertEqual(self.found(report), [("ci.yml", "test", "runner")])

    def test_pull_request_target_checking_out_the_head(self):
        self.workflow("label.yml", """
            on: pull_request_target
            permissions:
              contents: read
            jobs:
              base:
                runs-on: ubuntu-latest
                steps:
                  - uses: actions/checkout@v4
                    with:
                      persist-credentials: false
                  - run: ./label.sh
                    env:
                      TOKEN: ${{ secrets.LABEL_TOKEN }}
              head:
                runs-on: ubuntu-latest
                steps:
                  - uses: actions/checkout@v4
                    with:
                      ref: ${{ github.event.pull_request.head.sha }}
                      persist-credentials: false
                  - run: make test
              cli:
                runs-on: ubuntu-latest
                steps:
                  - run: gh pr checkout ${{ github.event.number }} && make test
        """)
        report = self.audit()
        self.assertFalse(self.job(report, "label.yml", "base")["agent_code"])  # the base branch's code
        self.assertEqual(self.found(report), [("label.yml", "cli", "head"), ("label.yml", "head", "head")])

    def test_workflow_run_checking_out_the_triggering_head(self):
        self.workflow("ci.yml", CLEAN.replace("on: pull_request", "name: CI\non: pull_request"))
        self.workflow("report.yml", """
            on:
              workflow_run:
                workflows: [CI]
            jobs:
              comment:
                runs-on: ubuntu-latest
                steps:
                  - uses: actions/download-artifact@v4
                    with:
                      run-id: ${{ github.event.workflow_run.id }}
              rebuild:
                runs-on: ubuntu-latest
                steps:
                  - uses: actions/checkout@v4
                    with:
                      ref: ${{ github.event.workflow_run.head_sha }}
                  - run: make
        """)
        report = self.audit()
        self.assertFalse(self.job(report, "report.yml", "comment")["agent_code"])
        self.assertIn(("report.yml", "comment", "artifacts"), self.found(report, "info"))
        self.assertEqual({f[2] for f in self.found(report) if f[1] == "rebuild"}, {"checkout", "token"})

    def test_a_local_composite_actions_checkout(self):
        action = self.tmp / ".github" / "actions" / "setup"
        action.mkdir(parents=True)
        (action / "action.yml").write_text(textwrap.dedent("""
            runs:
              using: composite
              steps:
                - name: Fetch
                  uses: actions/checkout@v4
        """))
        self.workflow("ci.yml", CLEAN.replace("- run: make test", "- uses: ./.github/actions/setup"))
        report = self.audit()
        self.assertEqual(self.found(report), [("ci.yml", "test", "checkout")])
        self.assertIn("(in ./.github/actions/setup)", self.messages(report, "checkout")[0])

    def test_the_factorys_own_workflows_are_left_to_the_policy(self):
        self.workflow("factory-triage.yml", CLEAN.replace("make test", "make test\n        env:\n"
                                                          "          K: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}"))
        report = self.audit()
        self.assertEqual(report["findings"], [])
        self.assertIn((None, None, "factory-workflows"), self.found(report, "info"))
        # Its secrets are still checked, but one that reads as empty is info: the factory's templates reference
        # optional slots (FACTORY_SVC_2..4, Context7) by design, and bootstrap.py checks the ones it needs.
        report = self.audit(repo="acme/app", gh=FakeGitHub())
        self.assertEqual(report["findings"], [])
        self.assertIn(("factory-triage.yml", "test", "missing"),
                      [(f["workflow"], f["job"], f["rule"]) for f in report["info"]])
        self.assertEqual(self.job(report, "factory-triage.yml", "test")["secrets"][0]["status"], "missing")


class Conditions(Case):
    """A job's `if:` clears an event only when it is false for a factory PR or push whatever else holds."""

    def flagged(self, triggers, condition, steps="", repo=None):
        self.workflow("ci.yml", f"""
            on: {triggers}
            permissions:
              contents: read
            jobs:
              deploy:
                runs-on: ubuntu-latest
                if: {condition}
                steps:
                  - uses: actions/checkout@v4
                    with:
                      persist-credentials: false
                  - run: ./deploy.sh
                    env:
                      DEPLOY_KEY: ${{{{ secrets.DEPLOY_KEY }}}}
        """)
        report = self.audit(repo=repo, gh=FakeGitHub() if repo else refuse)
        return [f[2] for f in self.found(report) if f[2] == "secret"] != [], self.job(report, "ci.yml", "deploy")

    def test_an_event_gate_clears_pull_request(self):
        flagged, job = self.flagged("{pull_request: {}, push: {branches: [main]}}", "github.event_name == 'push'")
        self.assertFalse(flagged)
        self.assertEqual(job["cleared"], {"pull_request": "its if: github.event_name == 'push'"})

    def test_the_same_gate_with_an_unfiltered_push_is_still_flagged(self):
        flagged, job = self.flagged("[pull_request, push]", "github.event_name == 'push'")
        self.assertTrue(flagged)
        self.assertEqual(job["agent_events"], ["push"])

    def test_a_ref_gate_clears_pull_request_and_factory_pushes(self):
        flagged, _ = self.flagged("[pull_request, push]", "${{ github.ref == 'refs/heads/main' }}")
        self.assertFalse(flagged)
        flagged, _ = self.flagged("[pull_request, push]", "startsWith(github.ref, 'refs/heads/factory/')")
        self.assertTrue(flagged)

    def test_a_default_branch_gate_under_pull_request_target_is_still_flagged(self):
        self.workflow("ci.yml", """
            on: pull_request_target
            permissions:
              contents: read
            jobs:
              test:
                runs-on: ubuntu-latest
                if: github.ref == 'refs/heads/main'
                steps:
                  - uses: actions/checkout@v4
                    with:
                      ref: ${{ github.event.pull_request.head.sha }}
                      persist-credentials: false
        """)
        self.assertIn(("ci.yml", "test", "head"), self.found(self.audit()))  # default branch unknown
        self.assertIn(("ci.yml", "test", "head"), self.found(self.audit(repo="acme/app", gh=FakeGitHub())))

    def test_an_expression_it_cant_read_is_still_flagged(self):
        for condition in ("contains(github.event.pull_request.labels.*.name, 'deploy')", "${{ !cancelled() }}",
                          "github.event_name == 'push' || inputs.force", "${{ env.DEPLOY }} == 'true'"):
            self.assertTrue(self.flagged("pull_request", condition)[0], condition)
        # But a conjunct that is false is enough.
        self.assertFalse(self.flagged("pull_request", "github.event_name == 'push' && inputs.force")[0])

    def test_a_deploy_on_merge_gate_clears_the_unmerged_pr(self):
        # A merged PR's closed run checks out the base branch, which CD reviewed; an unmerged one is the PR's code.
        self.assertFalse(self.flagged("{pull_request: {types: [closed]}}",
                                      "github.event.pull_request.merged == true")[0])
        self.assertFalse(self.flagged("{pull_request: {types: [closed]}}", "github.event.pull_request.merged")[0])
        self.assertTrue(self.flagged("[pull_request, push]", "github.event.pull_request.merged != true")[0])

    def test_strings_compare_without_regard_to_case(self):
        self.assertFalse(self.flagged("pull_request", "github.event_name != 'PULL_REQUEST'")[0])
        self.assertEqual(ci.condition("github.event_name == 'Pull_Request'", {"github.event_name": "pull_request"}),
                         True)

    def test_a_job_that_needs_a_cleared_job(self):
        self.workflow("ci.yml", """
            on: pull_request
            permissions:
              contents: read
            jobs:
              gate:
                runs-on: ubuntu-latest
                if: github.event_name == 'push'
                steps:
                  - run: "true"
              after:
                needs: gate
                runs-on: ubuntu-latest
                steps:
                  - uses: actions/checkout@v4
              always:
                needs: [gate]
                if: always()
                runs-on: ubuntu-latest
                steps:
                  - uses: actions/checkout@v4
        """)
        report = self.audit()
        self.assertEqual(self.job(report, "ci.yml", "after")["cleared"],
                         {"pull_request": "it needs gate, which doesn't run"})
        self.assertEqual(self.found(report), [("ci.yml", "always", "checkout")])

    def test_the_reader(self):
        pr = {"github.event_name": "pull_request", "github.ref": "refs/pull/1/merge", "github.head_ref": "factory/1-x"}
        cases = {
            "github.event_name == 'push'": False,
            "github.event_name == 'push' || github.event_name == 'pull_request'": True,
            "(github.event_name == 'push') && startsWith(github.head_ref, 'factory/')": False,
            "startsWith(github.head_ref, 'FACTORY/')": True,
            "github.ref != 'refs/heads/main'": True,
            "github.event.pull_request.draft == false": ci.UNKNOWN,
            "github.event_name == 'push' || github.actor == 'x'": ci.UNKNOWN,
            "github.event_name == 'pull_request' || github.actor == 'x'": True,
            "github.base_ref == 'main'": ci.UNKNOWN,  # not in the context: unknown
            "format('{0}', github.ref)": ci.UNKNOWN,
            None: True,
            False: False,
        }
        for text, want in cases.items():
            self.assertIs(ci.condition(text, pr), want, text)


class Reusable(Case):
    CALLEE = """
        on:
          workflow_call:
            secrets:
              TOKEN:
                required: false
        permissions:
          contents: read
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - uses: actions/checkout@v4
                with:
                  persist-credentials: false
              - run: make
                env:
                  TOKEN: ${{ secrets.TOKEN }}
                  OTHER: ${{ secrets.NPM_TOKEN }}
    """

    def caller(self, secrets):
        self.workflow("ci.yml", f"""
            on: pull_request
            permissions:
              contents: read
            jobs:
              build:
                uses: ./.github/workflows/build.yml
                {secrets}
        """)

    def test_inherit_passes_every_secret_to_a_job_that_runs_agent_code(self):
        self.workflow("build.yml", self.CALLEE)
        self.caller("secrets: inherit")
        report = self.audit()
        self.assertEqual(self.found(report), [("build.yml", "build", "secret"), ("build.yml", "build", "secret"),
                                              ("ci.yml", "build", "secret")])
        self.assertEqual(self.triggers(report, "build.yml")["workflow_call"]["agent_code"],
                         "through its callers (pull_request)")
        self.assertTrue(self.job(report, "ci.yml", "build")["agent_code"])

    def test_only_the_secrets_a_caller_passes_count(self):
        self.workflow("build.yml", self.CALLEE)
        self.caller("secrets:\n                  TOKEN: ${{ secrets.NPM_TOKEN }}")
        report = self.audit(repo="acme/app", gh=FakeGitHub())
        self.assertEqual(self.found(report), [("build.yml", "build", "secret")])
        self.assertIn("secret TOKEN", self.messages(report, "secret")[0])
        build = {s["name"]: s["status"] for s in self.job(report, "build.yml", "build")["secrets"]}
        self.assertEqual(build["TOKEN"], "passed")  # its caller's NPM_TOKEN is the one checked
        self.assertEqual({s["name"]: s["status"] for s in self.job(report, "ci.yml", "build")["secrets"]},
                         {"NPM_TOKEN": "exists"})

    def test_a_callers_if_counts(self):
        self.workflow("build.yml", self.CALLEE)
        self.caller("secrets: inherit\n                if: github.event_name == 'push'")
        report = self.audit()
        self.assertEqual(report["findings"], [])
        self.assertTrue(self.triggers(report, "build.yml")["workflow_call"]["agent_code"].startswith("no"))

    def test_another_repositorys_workflow(self):
        self.workflow("ci.yml", """
            on: pull_request
            permissions:
              contents: read
            jobs:
              with-secrets:
                uses: acme/shared/.github/workflows/build.yml@v1
                secrets: inherit
              without:
                uses: acme/shared/.github/workflows/lint.yml@v1
        """)
        report = self.audit()
        self.assertEqual(self.found(report), [("ci.yml", "with-secrets", "remote-call")])
        self.assertIn(("ci.yml", "without", "remote-call"), self.found(report, "info"))


class Existence(Case):
    def setUp(self):
        super().setUp()
        self.gh = FakeGitHub()
        self.workflow("deploy.yml", """
            on:
              push:
                branches: [main]
            permissions:
              contents: read
            jobs:
              publish:
                runs-on: ubuntu-latest
                steps:
                  - run: npm publish
                    env:
                      NPM_TOKEN: ${{ secrets.NPM_TOKEN }}
                      ORG: ${{ secrets.ORG_TOKEN }}
                      GH: ${{ secrets.GITHUB_TOKEN }}
              production:
                runs-on: ubuntu-latest
                environment: production
                steps:
                  - run: ./deploy.sh
                    env:
                      KEY: ${{ secrets.DEPLOY_KEY }}
              stray:
                runs-on: ubuntu-latest
                steps:
                  - run: ./deploy.sh
                    env:
                      KEY: ${{ secrets.DEPLOY_KEY }}
                      GONE: ${{ secrets.MISSING_ONE }}
              staging:
                runs-on: ubuntu-latest
                environment:
                  name: staging
                steps:
                  - run: "true"
        """)

    def statuses(self, report, job):
        return {s["name"]: s["status"] for s in self.job(report, "deploy.yml", job)["secrets"]}

    def test_each_secret_by_name_at_each_level(self):
        report = self.audit(repo="acme/app", gh=self.gh)
        self.assertEqual(self.statuses(report, "publish"), {"NPM_TOKEN": "exists", "ORG_TOKEN": "exists",
                                                            "GITHUB_TOKEN": "built in"})
        details = {s["name"]: s["detail"] for s in self.job(report, "deploy.yml", "publish")["secrets"]}
        self.assertEqual((details["NPM_TOKEN"], details["ORG_TOKEN"]), ("repository", "organization"))
        self.assertEqual(self.statuses(report, "production"), {"DEPLOY_KEY": "exists"})
        self.assertEqual(self.statuses(report, "stray"), {"DEPLOY_KEY": "missing", "MISSING_ONE": "missing"})
        missing = self.messages(report, "missing")
        self.assertEqual(len(missing), 2)
        self.assertIn("only in environment production, which this job doesn't use", missing[0])
        self.assertIn("MISSING_ONE", missing[1])
        self.assertEqual(self.found(report), [("deploy.yml", "stray", "missing"), ("deploy.yml", "stray", "missing")])
        info = self.found(report, "info")
        self.assertIn((None, None, "unused-secret"), info)
        self.assertEqual(self.messages(report, "unused-secret", "info"),
                         ["repository secret UNUSED_TOKEN exists, but no workflow here references it"])
        # The environment's secret is the production job's, never the stray one's, which can't read it.
        rows = {(r["level"], r["name"]): r["referenced_by"] for r in report["secrets"]}
        self.assertEqual(rows[("environment production", "DEPLOY_KEY")], ["deploy.yml/production"])
        self.assertEqual(rows[("repository", "NPM_TOKEN")], ["deploy.yml/publish"])
        self.assertIn("environment staging is referenced but doesn't exist", self.messages(report, "environment",
                                                                                          "info")[0])
        # Names only: every secrets call asks gh for .name.
        secret_calls = [c for c in self.gh.calls if "secrets" in " ".join(c)]
        self.assertTrue(secret_calls and all(c[-1].endswith("[].name") for c in secret_calls))

    def test_a_level_it_cant_read_is_not_checked_never_empty(self):
        self.gh.fail["repos/acme/app/actions/organization-secrets"] = "HTTP 403: Resource not accessible"
        report = self.audit(repo="acme/app", gh=self.gh)
        self.assertEqual(self.statuses(report, "stray")["MISSING_ONE"], "unknown")
        self.assertEqual(self.statuses(report, "publish")["ORG_TOKEN"], "unknown")
        self.assertEqual(self.found(report), [])
        self.assertIn("organization not readable", report["summary"])

    def test_without_repo_or_gh_existence_is_not_checked(self):
        report = self.audit()  # refuse: gh is never called
        self.assertEqual(self.statuses(report, "stray")["MISSING_ONE"], "not checked")
        self.assertTrue(report["summary"].endswith("secrets' existence not checked (no --repo)"))

        def no_gh(args):
            raise FileNotFoundError("gh")
        report = self.audit(repo="acme/app", gh=no_gh)
        self.assertIn("not checked (gh isn't installed)", report["summary"])
        self.assertEqual(self.found(report), [])
        status, out = self.main([str(self.workflows), "--factory-dir", str(self.factory)])
        self.assertIn("not checked (no --repo)", out)


class Runs(Case):
    def test_gaps_between_scheduled_runs(self):
        self.workflow("nightly.yml", """
            on:
              schedule:
                - cron: "0 * * * *"
            jobs:
              check:
                runs-on: ubuntu-latest
                steps:
                  - run: "true"
        """)
        gh = FakeGitHub()
        gh.runs["nightly.yml"] = ["2026-11-16T03:10:00Z", "2026-11-16T01:40:00Z", "2026-11-16T01:05:00Z",
                                  "2026-11-15T23:20:00Z"]
        now = ci.parse_time("2026-11-16T04:00:00Z")
        report = self.audit(repo="acme/app", runs=4, gh=gh, now=now)
        row = report["schedules"][0]
        self.assertEqual(row["cron"], ["0 * * * *"])
        self.assertEqual(row["gaps_minutes"], [105.0, 35.0, 90.0])
        self.assertEqual(row["since_last_minutes"], 50.0)
        self.assertEqual(self.found(report), [])  # gaps are information
        self.assertIn("1h45m", ci.render(report))

    def test_runs_needs_repo(self):
        self.workflow("ci.yml", CLEAN)
        self.assertEqual(self.main([str(self.workflows), "--runs", "5"])[0], 2)


class Output(Case):
    def test_exit_statuses(self):
        self.assertEqual(self.main([str(self.tmp / "nowhere")])[0], 2)
        self.workflow("ci.yml", CLEAN)
        self.assertEqual(self.main([str(self.workflows), "--repo", "not a repo"])[0], 2)
        self.assertEqual(self.main([str(self.workflows), "--bogus"])[0], 2)
        (self.factory / "factory.json").write_text("{")
        self.assertEqual(self.main([str(self.workflows), "--factory-dir", str(self.factory)])[0], 2)

    def test_a_workflow_that_doesnt_parse_is_a_finding(self):
        self.workflow("ci.yml", CLEAN)
        self.workflow("broken.yml", "on: [push\njobs: {")
        self.workflow("empty.yml", "")
        status, out = self.main([str(self.workflows), "--factory-dir", str(self.factory)])
        self.assertEqual(status, 1)
        report = self.audit()
        self.assertEqual(self.found(report), [("broken.yml", None, "unreadable"), ("empty.yml", None, "unreadable")])

    def test_no_factory_json_is_said_plainly(self):
        (self.factory / "factory.json").unlink()
        self.workflow("ci.yml", CLEAN.replace("ubuntu-latest", "[self-hosted, factory-ci]"))
        report = self.audit()
        self.assertEqual(self.found(report), [("ci.yml", "test", "runner")])  # the CI tier's label isn't known
        self.assertIn("factory.json not found", ci.render(report))

    def test_json_carries_the_same_findings_as_the_tables(self):
        self.workflow("ci.yml", CLEAN.replace("persist-credentials: false", "persist-credentials: true")
                      .replace("make test", "make test\n        env:\n          K: ${{ secrets.K }}"))
        status, text = self.main([str(self.workflows), "--factory-dir", str(self.factory)])
        json_status, data = self.main([str(self.workflows), "--factory-dir", str(self.factory), "--json"])
        data = json.loads(data)
        self.assertEqual((status, json_status), (1, 1))
        self.assertEqual(sorted(f["rule"] for f in data["findings"]), ["checkout", "secret"])
        for f in data["findings"]:
            self.assertIn(f"[{f['rule']}] {f['workflow']} / {f['job']}: {f['message']}", text)
        self.assertEqual(text.rstrip().splitlines()[-1], data["summary"])
        self.assertEqual(data["workflows"][0]["jobs"][0]["checkouts"][0]["persist_credentials"], "True")

    def test_the_policys_settings_are_put_back(self):
        before = {name: getattr(wp, name) for name in ci.POLICY_GLOBALS}
        self.workflow("ci.yml", CLEAN)
        self.audit()
        self.assertEqual({name: getattr(wp, name) for name in ci.POLICY_GLOBALS}, before)

    def test_it_runs_isolated(self):
        self.workflow("ci.yml", CLEAN.replace("persist-credentials: false", "persist-credentials: true"))
        r = subprocess.run([sys.executable, "-I", str(FACTORY / "ci_audit.py"), str(self.workflows),
                            "--factory-dir", str(self.factory)], capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertTrue(r.stdout.rstrip().splitlines()[-1].startswith("ci audit: 1 workflows, 1 jobs "
                                                                       "(1 run agent-written code), 1 findings"))


if __name__ == "__main__":
    unittest.main()
