"""bootstrap.py against an in-memory GitHub that keeps the runner-group API's two quirks (measured on
2026-10-12): a PATCH replaces the workflow list with what it sends (an omitted list empties it), and a PATCH
that sends visibility empties the repository list."""
import contextlib
import copy
import io
import json
import urllib.parse
import pathlib
import re
import sys
import tempfile
import unittest

FACTORY = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(FACTORY))
import bootstrap  # noqa: E402

REPO, OTHER = "acme/widget", "acme/gadget"
# The settings Enablement fills, as a project that has done so has them.
FIXTURE_SETTINGS = {"app": {"user_id": 424242, "login": "acme-factory[bot]"},
                    "image": {"repository": "ghcr.io/acme/factory-job", "digest": "sha256:" + "a" * 64},
                    "smoke": {"echo_host": "echo.acme.example", "host_probes": ""}}
OTHER_WF = f"{OTHER}/.github/workflows/factory-triage.yml@refs/heads/main"


# The default branch's required reviewers, as Enablement step 9 sets them: a team of people approves every file.
TEAM_REVIEW = {"file_patterns": ["*"], "minimum_approvals": 1, "reviewer": {"id": 3, "type": "Team"}}


class FakeGitHub:
    def __init__(self):
        self.repo = {"id": 7, "default_branch": "main", "owner": {"type": "Organization"}}
        self.labels = []
        self.envs = {}
        self.repo_secrets, self.org_secrets = set(), set()
        self.groups = [{"id": 4, "name": "factory-pool", "visibility": "selected", "restricted_to_workflows": True,
                        "selected_workflows": [OTHER_WF], "repos": [9], "runners": ["runner-1"]}]
        self.installations = [{"id": 1, "app_slug": "acme-factory", "repository_selection": "all",
                               "permissions": dict(bootstrap.APP_PERMISSIONS)}]
        self.rulesets = [{"id": 1, "name": "main", "enforcement": "active", "target": "branch",
                          "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"]}},
                          "bypass_actors": [{"actor_id": None, "actor_type": "OrganizationAdmin",
                                             "bypass_mode": "pull_request"}],
                          "rules": [{"type": "pull_request", "parameters": {"require_code_owner_review": True,
                                                                             "required_reviewers": [dict(TEAM_REVIEW)]}},
                                    {"type": "required_status_checks",
                                     "parameters": {"required_status_checks": [{"context": "ci-ok"}]}}]}]
        self.admin = True
        self.writes = []
        self.branches = set()
        self.protection = None  # the default branch's classic protection: none

    def env(self, name):
        return self.envs.setdefault(name, {"policy": None, "branches": [], "reviewers": [], "secrets": set(),
                                           "variables": set()})

    def __call__(self, method, path, body=None):
        if method != "GET":
            self.writes.append((method, path, copy.deepcopy(body)))
        path, _, query = path.partition("?")
        page = int(dict(p.split("=") for p in query.split("&") if "=" in p).get("page", "1"))
        if page > 1:
            return 200, [] if path.endswith("/labels") or path.endswith("/rulesets") else {
                "labels": [], "environments": [], "branch_policies": [], "secrets": [], "variables": [],
                "runner_groups": [], "repositories": [], "runners": [], "installations": []}
        r = f"repos/{REPO}"
        m = lambda pattern: re.fullmatch(pattern, path)  # noqa: E731
        if path == r:
            return 200, self.repo
        if path in ("user", "users/cd"):
            return 200, {"id": 101, "login": "cd"}
        if path == f"{r}/labels":
            if method == "POST":
                self.labels.append(dict(body))
                return 201, body
            return 200, self.labels
        if g := m(rf"{r}/labels/(.+)"):
            label = next(l for l in self.labels if l["name"] == g.group(1).replace("%3A", ":"))
            label.update(body)
            return 200, label
        if path == f"{r}/environments":
            return 200, {"environments": [
                {"name": n, "deployment_branch_policy": e["policy"],
                 "protection_rules": [{"type": "required_reviewers", "reviewers": e["reviewers"]}] if e["reviewers"]
                 else []} for n, e in self.envs.items()]}
        if g := m(rf"{r}/environments/([^/]+)"):
            e = self.env(g.group(1))
            e["policy"] = body["deployment_branch_policy"]
            e["reviewers"] = [{"type": "User", "reviewer": {"id": x["id"]}} for x in body.get("reviewers", [])]
            return 200, {}
        if g := m(rf"{r}/environments/([^/]+)/deployment-branch-policies"):
            e = self.envs.get(g.group(1))
            if e is None:
                return 404, {"message": "Not Found"}
            if method == "POST":
                e["branches"].append(body["name"])
                return 200, body
            return 200, {"branch_policies": [{"name": b} for b in e["branches"]]}
        if g := m(rf"{r}/environments/([^/]+)/(secrets|variables)"):
            e = self.envs.get(g.group(1))
            if e is None:
                return 404, {"message": "Not Found"}
            return 200, {g.group(2): [{"name": n} for n in sorted(e[g.group(2)])]}
        if path == f"{r}/actions/secrets":
            return 200, {"secrets": [{"name": n} for n in sorted(self.repo_secrets)]}
        if path == f"{r}/actions/organization-secrets":
            return 200, {"secrets": [{"name": n} for n in sorted(self.org_secrets)]}
        base = "orgs/acme/actions/runner-groups"
        if path == base:
            if not self.admin:
                return 403, {"message": "Must have admin rights"}
            if method == "POST":
                g = {"id": 10 + len(self.groups), "name": body["name"], "visibility": body["visibility"],
                     "restricted_to_workflows": body["restricted_to_workflows"],
                     "selected_workflows": list(body["selected_workflows"]),
                     "repos": list(body["selected_repository_ids"]), "runners": []}
                self.groups.append(g)
                return 201, self.public(g)
            return 200, {"runner_groups": [self.public(g) for g in self.groups]}
        if g := m(rf"{base}/(\d+)(/.*)?"):
            group = next(x for x in self.groups if x["id"] == int(g.group(1)))
            rest = g.group(2) or ""
            if rest == "" and method == "PATCH":
                group["name"] = body["name"]
                group["restricted_to_workflows"] = body.get("restricted_to_workflows", False)
                group["selected_workflows"] = list(body.get("selected_workflows", []))  # quirk 1
                if "visibility" in body:
                    group["visibility"], group["repos"] = body["visibility"], []  # quirk 2
                return 200, self.public(group)
            if rest == "":
                return 200, self.public(group)
            if rest == "/repositories" and method == "PUT":
                group["repos"] = list(body["selected_repository_ids"])
                return 204, None
            if rest == "/repositories":
                return 200, {"repositories": [{"id": i} for i in group["repos"]]}
            if (h := re.fullmatch(r"/repositories/(\d+)", rest)) and method == "PUT":
                group["repos"].append(int(h.group(1)))
                return 204, None
            if rest == "/runners":
                return 200, {"runners": [{"name": n} for n in group["runners"]]}
        if path == "orgs/acme/installations":
            if not self.admin:
                return 403, {"message": "Must have admin rights"}
            return 200, {"installations": self.installations}
        if path == f"{r}/rulesets":
            return 200, [{"id": rs["id"]} for rs in self.rulesets]
        if g := m(rf"{r}/rulesets/(\d+)"):
            return 200, next(rs for rs in self.rulesets if rs["id"] == int(g.group(1)))
        if path == f"{r}/branches/main/protection":
            return (200, self.protection) if self.protection else (404, {"message": "Branch not protected"})
        if g := m(rf"{r}/branches/([^/]+)"):
            return (200, {"name": urllib.parse.unquote(g.group(1))}) if urllib.parse.unquote(g.group(1)) in self.branches \
                else (404, {"message": "Branch not found"})
        raise AssertionError(f"unexpected call {method} {path}")

    @staticmethod
    def public(g):
        return {k: v for k, v in g.items() if k not in ("repos", "runners")}

    def set_up(self, production=False):
        """Everything the factory needs, as a project already set up has it."""
        self.labels = [{"name": n, "color": c, "description": d} for n, c, d in bootstrap.LABELS]
        envs = ["factory-writer", "factory-planning"] + (["factory-production"] if production else [])
        for name in envs:
            e = self.env(name)
            e["policy"] = {"protected_branches": False, "custom_branch_policies": True}
            e["branches"] = ["main"]
        if production:
            self.env("factory-production")["reviewers"] = [{"type": "User", "reviewer": {"id": 101}}]
        self.env("factory-writer")["secrets"].add("FACTORY_APP_PRIVATE_KEY")
        self.env("factory-writer")["variables"].add("FACTORY_APP_CLIENT_ID")
        self.repo_secrets.add("CLAUDE_CODE_OAUTH_TOKEN")
        pool = self.groups[0]
        pool["repos"].append(7)
        pool["selected_workflows"] += [f"{REPO}/.github/workflows/{w}@refs/heads/main" for w in SHARED]
        if production:
            self.groups.append({"id": 5, "name": "factory-pool-widget-prod", "visibility": "selected",
                                "restricted_to_workflows": True, "repos": [7], "runners": ["runner-prod"],
                                "selected_workflows": [f"{REPO}/.github/workflows/factory-gate.yml@refs/heads/main"]})


SHARED = ["factory-implement.yml", "factory-plan.yml", "factory-triage.yml"]


class Bootstrap(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        factory, workflows = self.root / ".github" / "factory", self.root / ".github" / "workflows"
        factory.mkdir(parents=True)
        workflows.mkdir()
        cfg = json.loads((FACTORY / "factory.json").read_text())
        cfg.update(FIXTURE_SETTINGS)  # a set-up project's own App, image and echo host, whatever this one's are
        # No release block, as in a project that enabled the factory before the release branch existed: the fallback,
        # whatever this project's own release model is. release_project() sets one.
        cfg.pop("release", None)
        (factory / "factory.json").write_text(json.dumps(cfg))
        (factory / "planning.json").write_text(json.dumps({"database": {"host": "", "name": ""}}))
        (factory / "services.json").write_text(json.dumps({"services": []}))
        for name, label in [("factory-implement.yml", "factory"), ("factory-plan.yml", "factory-plan"),
                            ("factory-triage.yml", "factory"), ("factory-gate.yml", "factory-prod")]:
            (workflows / name).write_text(f"jobs:\n  a:\n    runs-on: ubuntu-latest\n  b:\n    runs-on: [self-hosted, {label}]\n")
        (workflows / "ci.yml").write_text("jobs:\n  t:\n    runs-on: ubuntu-latest\n")
        (self.root / ".github" / "CODEOWNERS").write_text("/.github/ @cd\n/.claude/ @cd\n")
        self.gh = FakeGitHub()

    def tearDown(self):
        self.tmp.cleanup()

    def production_tier(self):
        (self.root / ".github" / "factory" / "production").mkdir()
        (self.root / ".github" / "factory" / "production" / "ops.json").write_text("{}")

    def run_it(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = bootstrap.main(["--repo", REPO, "--root", str(self.root), *args], api=self.gh)
        return code, out.getvalue()

    def pool(self):
        return self.gh.groups[0]

    def test_a_set_up_repository_needs_nothing_and_apply_writes_nothing(self):
        self.gh.set_up()
        code, out = self.run_it()
        self.assertEqual(code, 0, out)
        self.assertIn("nothing missing", out)
        code, out = self.run_it("--apply")
        self.assertEqual((code, self.gh.writes), (0, []), out)

    def test_check_reports_what_a_new_repository_lacks_and_writes_nothing(self):
        code, out = self.run_it()
        self.assertEqual(code, 1)
        self.assertEqual(self.gh.writes, [])
        self.assertEqual(out.count("missing   factory:"), len(bootstrap.LABELS), out)
        for text in ("factory-writer (deployable from main only)", "repository widget",
                     "workflow factory-plan.yml", "FACTORY_APP_PRIVATE_KEY", "FACTORY_APP_CLIENT_ID",
                     "CLAUDE_CODE_OAUTH_TOKEN"):
            self.assertIn(text, out)
        self.assertNotIn("factory-production", out)  # no production tier
        self.assertNotIn("FACTORY_DB_READER_PASSWORD", out)  # planning.json names no database

    def test_apply_sets_up_a_new_repository_and_keeps_the_other_projects(self):
        code, out = self.run_it("--apply")
        self.assertEqual(code, 1, out)  # the secrets are still CD's to set
        self.assertEqual({l["name"] for l in self.gh.labels}, {n for n, _, _ in bootstrap.LABELS})
        for env in ("factory-writer", "factory-planning"):
            self.assertEqual(self.gh.envs[env]["branches"], ["main"])
            self.assertTrue(self.gh.envs[env]["policy"]["custom_branch_policies"])
        pool = self.pool()
        self.assertEqual(sorted(pool["repos"]), [7, 9])  # gadget kept
        self.assertEqual(set(pool["selected_workflows"]),
                         {OTHER_WF} | {f"{REPO}/.github/workflows/{w}@refs/heads/main" for w in SHARED})
        self.assertNotIn("factory-gate.yml", json.dumps(pool["selected_workflows"]))
        self.assertEqual(len(self.gh.groups), 1)  # no production group without a production tier
        patches = [b for m, p, b in self.gh.writes if m == "PATCH" and "runner-groups" in p]
        self.assertEqual(len(patches), 1)
        self.assertNotIn("visibility", patches[0])
        self.assertIn(OTHER_WF, patches[0]["selected_workflows"])
        # And a second run has nothing left to apply but the secrets.
        self.gh.writes.clear()
        code, out = self.run_it("--apply")
        self.assertEqual(self.gh.writes, [])
        self.assertEqual([l for l in out.splitlines() if l.lstrip().startswith("missing")
                          and "secret" not in l and "variable" not in l], [], out)

    def test_a_production_tier_gets_its_own_group_and_a_reviewed_environment(self):
        self.production_tier()
        code, out = self.run_it("--apply", "--reviewer", "cd")
        prod = next(g for g in self.gh.groups if g["name"] == "factory-pool-widget-prod")
        self.assertEqual(prod["repos"], [7])
        self.assertEqual(prod["selected_workflows"], [f"{REPO}/.github/workflows/factory-gate.yml@refs/heads/main"])
        self.assertTrue(prod["restricted_to_workflows"])
        self.assertEqual(prod["visibility"], "selected")
        self.assertIn("register its runners with host/setup-production.sh", out)
        env = self.gh.envs["factory-production"]
        self.assertEqual((env["branches"], env["reviewers"][0]["reviewer"]["id"]), (["main"], 101))
        self.assertNotIn("factory-gate.yml", json.dumps(self.pool()["selected_workflows"]))

    def test_a_production_tier_needs_merge_commits_only(self):
        self.production_tier()
        self.gh.repo.update(allow_merge_commit=True, allow_squash_merge=True, allow_rebase_merge=False)
        code, out = self.run_it()
        self.assertIn("main also allows squash merges", out)
        # Restricted in the ruleset instead of the repository's settings, it holds.
        self.gh.rulesets[0]["rules"][0]["parameters"]["allowed_merge_methods"] = ["merge"]
        code, out = self.run_it()
        self.assertIn("main merges with merge commits only", out)
        self.gh.repo.update(allow_merge_commit=False)
        code, out = self.run_it()
        self.assertIn("main allows no merge commit", out)

    def release_project(self):
        factory = self.root / ".github" / "factory"
        cfg = json.loads((factory / "factory.json").read_text())
        cfg["release"] = {"branch": "release/production"}
        (factory / "factory.json").write_text(json.dumps(cfg))
        self.production_tier()
        self.gh.repo.update(allow_merge_commit=True, allow_squash_merge=True, allow_rebase_merge=True)
        self.gh.branches = {"release/production"}

    def release_ruleset(self, **changes):
        rs = {"id": 2, "enforcement": "active", "target": "branch",
              "conditions": {"ref_name": {"include": ["refs/heads/release/production"]}},
              "bypass_actors": [{"actor_id": 1, "actor_type": "OrganizationAdmin", "bypass_mode": "pull_request"}],
              "rules": [{"type": "pull_request", "parameters": {"require_code_owner_review": True,
                                                                "allowed_merge_methods": ["merge"]}},
                        {"type": "update"}, {"type": "non_fast_forward"}, {"type": "deletion"}]}
        rs.update(changes)
        return rs

    def pinned_ruleset(self, **changes):
        rs = {"id": 3, "enforcement": "active", "target": "branch",
              "conditions": {"ref_name": {"include": ["refs/heads/factory/release/**"]}}, "bypass_actors": [],
              "rules": [{"type": "update"}, {"type": "non_fast_forward"}, {"type": "deletion"}]}
        rs.update(changes)
        return rs

    def test_a_release_branch_needs_its_ruleset(self):
        self.release_project()
        code, out = self.run_it()
        self.assertIn("release/production's rulesets lack a PR with code-owner review, merge commits only, restricted "
                      "updates, no force push, no deletion", out)
        # The default branch's merge methods don't matter: deploys follow the release branch.
        self.assertNotIn("also allows", out)
        self.gh.rulesets += [self.release_ruleset(), self.pinned_ruleset()]
        code, out = self.run_it()
        self.assertIn("release/production takes changes only through a PR an admin merges", out)
        self.assertIn("factory/release/** branches can't move once created", out)
        self.gh.branches = set()
        code, out = self.run_it()
        self.assertIn("no branch release/production", out)

    def test_a_release_branch_ruleset_admits_only_admins_on_pull_requests(self):
        self.release_project()
        self.gh.rulesets += [self.release_ruleset(), self.pinned_ruleset()]
        for actor, expect in [
                ({"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always"}, "RepositoryRole 5 bypass it always"),
                ({"actor_id": 5, "actor_type": "RepositoryRole"}, "RepositoryRole 5 bypass it always"),
                ({"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "exempt"}, "RepositoryRole 5 bypass it exempt"),
                ({"actor_id": 4, "actor_type": "RepositoryRole", "bypass_mode": "pull_request"}, "lets RepositoryRole 4 bypass it"),
                ({"actor_id": 9, "actor_type": "Integration", "bypass_mode": "pull_request"}, "lets Integration 9 bypass it"),
                ({"actor_id": 7, "actor_type": "Team", "bypass_mode": "pull_request"}, "lets Team 7 bypass it"),
                ({"actor_id": 3, "actor_type": "DeployKey", "bypass_mode": "pull_request"}, "lets DeployKey 3 bypass it")]:
            with self.subTest(actor=actor):
                self.gh.rulesets[-2]["bypass_actors"] = [actor]
                code, out = self.run_it()
                self.assertIn(expect, out)
                self.assertNotIn("takes changes only through", out)
        self.gh.rulesets[-2]["bypass_actors"] = [{"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "pull_request"}]
        code, out = self.run_it()
        self.assertIn("release/production takes changes only through a PR an admin merges", out)

    def test_a_release_branch_ruleset_restricts_updates_and_merges_with_merge_commits(self):
        self.release_project()
        self.gh.rulesets += [self.release_ruleset(), self.pinned_ruleset()]
        rules = self.gh.rulesets[-2]["rules"]
        rules[1] = {"type": "update", "parameters": {"update_allows_fetch_and_merge": True}}
        code, out = self.run_it()
        self.assertIn("lets updates through as fetch and merge", out)
        del rules[1]
        code, out = self.run_it()
        self.assertIn("lack restricted updates", out)
        rules.insert(1, {"type": "update"})
        rules[0]["parameters"]["allowed_merge_methods"] = ["merge", "squash"]
        code, out = self.run_it()
        self.assertIn("lack merge commits only", out)
        del rules[0]["parameters"]["allowed_merge_methods"]
        code, out = self.run_it()
        self.assertIn("lack merge commits only", out)

    def test_ruleset_patterns_include_and_exclude_like_github(self):
        self.release_project()
        self.gh.rulesets += [self.release_ruleset(), self.pinned_ruleset()]
        self.gh.rulesets[-2]["conditions"]["ref_name"] = {"include": ["refs/heads/release/**"]}
        code, out = self.run_it()
        self.assertIn("release/production takes changes only through a PR an admin merges", out)
        # An exclude that matches the branch takes the ruleset off it.
        self.gh.rulesets[-2]["conditions"]["ref_name"] = {"include": ["~ALL"], "exclude": ["refs/heads/release/*"]}
        code, out = self.run_it()
        self.assertIn("release/production's rulesets lack a PR with code-owner review", out)
        # A single * doesn't cross a slash, and nor does a ** without one after it (GitHub's FNM_PATHNAME).
        for include in ("refs/heads/*", "refs/heads/**"):
            with self.subTest(include=include):
                self.gh.rulesets[-2]["conditions"]["ref_name"] = {"include": [include]}
                code, out = self.run_it()
                self.assertIn("release/production's rulesets lack", out)
        self.gh.rulesets[-2]["conditions"]["ref_name"] = {"include": ["refs/heads/**/*"]}
        code, out = self.run_it()
        self.assertIn("release/production takes changes only through a PR an admin merges", out)
        # A set in an exclude counts.
        self.gh.rulesets[-2]["conditions"]["ref_name"] = {"include": ["~ALL"], "exclude": ["refs/heads/[q-s]elease/*"]}
        code, out = self.run_it()
        self.assertIn("release/production's rulesets lack", out)

    def test_ref_patterns_match_as_github_matches_them(self):
        # Ruby's File.fnmatch with FNM_PATHNAME, which GitHub's docs name for branch patterns.
        for pattern, ref, want in [
                ("refs/heads/**", "refs/heads/main", True), ("refs/heads/**", "refs/heads/release/production", False),
                ("refs/heads/**/*", "refs/heads/release/production", True),
                ("refs/heads/**/production", "refs/heads/production", True),
                ("refs/heads/**/production", "refs/heads/a/b/production", True),
                ("refs/heads/**/production", "refs/heads/xproduction", False),
                ("refs/heads/factory/release/**", "refs/heads/factory/release/1-G1-0123456789ab", True),
                ("refs/heads/factory/**", "refs/heads/factory/release/1-G1-0123456789ab", False),
                ("refs/heads/factory/release/[4-9]*", "refs/heads/factory/release/42-G7-fedcba987654", True),
                ("refs/heads/factory/release/[!4-9]*", "refs/heads/factory/release/42-G7-fedcba987654", False),
                ("refs/heads/release?production", "refs/heads/release/production", False),
                ("refs/heads/release.production", "refs/heads/releaseXproduction", False)]:
            with self.subTest(pattern=pattern, ref=ref):
                self.assertEqual(re.fullmatch(bootstrap.fnmatch_regex(pattern), ref) is not None, want)

    def test_pinned_release_branches_cant_move(self):
        self.release_project()
        self.gh.rulesets += [self.release_ruleset()]
        code, out = self.run_it()
        self.assertIn("factory/release/** (release gates' pinned commits) needs a ruleset with restricted updates, "
                      "no deletion, no force push on every branch under it", out)
        self.gh.rulesets.append(self.pinned_ruleset(bypass_actors=[{"actor_id": 9, "actor_type": "Integration",
                                                                     "bypass_mode": "always"}]))
        code, out = self.run_it()
        self.assertIn("lets Integration 9 bypass it: nothing may move a pinned branch", out)
        self.gh.rulesets[-1] = self.pinned_ruleset(rules=[{"type": "creation"}, {"type": "update"},
                                                          {"type": "non_fast_forward"}, {"type": "deletion"}])
        code, out = self.run_it()
        self.assertIn("restricts creation: the factory App couldn't pin", out)
        self.gh.rulesets[-1] = self.pinned_ruleset(rules=[{"type": "update", "parameters": {"update_allows_fetch_and_merge": True}},
                                                          {"type": "non_fast_forward"}, {"type": "deletion"}])
        code, out = self.run_it()
        self.assertIn("factory/release/**'s ruleset lets updates through as fetch and merge", out)
        self.gh.rulesets[-1] = self.pinned_ruleset()
        code, out = self.run_it()
        self.assertIn("factory/release/** branches can't move once created", out)

    def test_a_pinned_ruleset_covers_every_pinned_name(self):
        self.release_project()
        self.gh.rulesets += [self.release_ruleset(), self.pinned_ruleset()]
        # Only some names: PR 1's, all but an excluded gate, or GitHub's `**` without a slash, which stops at one.
        for names, expect in (({"include": ["refs/heads/factory/release/1-*"]}, "isn't covered"),
                              ({"include": ["refs/heads/factory/**"]}, "isn't covered"),
                              ({"include": ["refs/heads/factory/release/**"], "exclude": ["refs/heads/factory/release/*-G7-*"]},
                               "excludes refs/heads/factory/release/*-G7-*"),
                              # An exclude no sample hits is still a hole.
                              ({"include": ["refs/heads/factory/release/**"], "exclude": ["refs/heads/factory/release/1?-*"]},
                               "excludes refs/heads/factory/release/1?-*, which can leave pinned branches out")):
            with self.subTest(names=names):
                self.gh.rulesets[-1]["conditions"]["ref_name"] = names
                code, out = self.run_it()
                self.assertIn(expect, out)
                self.assertNotIn("can't move once created", out)
        # An exclude elsewhere is fine.
        self.gh.rulesets[-1]["conditions"]["ref_name"] = {"include": ["refs/heads/factory/release/**"],
                                                          "exclude": ["refs/heads/main"]}
        code, out = self.run_it()
        self.assertIn("factory/release/** branches can't move once created", out)

    def test_the_pinned_ruleset_is_checked_before_the_release_branch_exists(self):
        self.release_project()
        self.gh.branches = set()
        code, out = self.run_it()
        self.assertIn("no branch release/production", out)
        self.assertIn("factory/release/** (release gates' pinned commits) needs a ruleset", out)

    def test_merge_settings_matter_only_with_a_production_tier(self):
        self.gh.repo.update(allow_merge_commit=True, allow_squash_merge=True, allow_rebase_merge=True)
        self.gh.set_up()
        code, out = self.run_it()
        self.assertNotIn("merge commit", out)

    def test_the_planning_secrets_follow_planning_json_and_services_json(self):
        factory = self.root / ".github" / "factory"
        (factory / "planning.json").write_text(json.dumps({"database": {"host": "db.example", "name": "w"}}))
        (factory / "services.json").write_text(json.dumps({"services": [{"name": "search", "slot": "FACTORY_SVC_2"},
                                                                        {"name": "memory", "slot": "FACTORY_EXEC_SVC_1"}]}))
        self.gh.set_up()
        code, out = self.run_it()
        self.assertEqual(code, 1)
        self.assertIn("factory-planning secret FACTORY_DB_READER_PASSWORD", out)
        self.assertIn("factory-planning secret FACTORY_SVC_2 (service search's credential)", out)
        # An execution stage's service credential is a repository secret, never the planning environment's.
        self.assertIn("repository secret FACTORY_EXEC_SVC_1 (service memory's credential)", out)
        self.assertNotIn("factory-planning secret FACTORY_EXEC_SVC_1", out)

    def test_an_org_wide_claude_token_is_a_problem(self):
        self.gh.set_up()
        self.gh.org_secrets.add("CLAUDE_CODE_OAUTH_TOKEN")
        code, out = self.run_it()
        self.assertEqual(code, 1)
        self.assertIn("also an organization secret", out)

    def test_the_app_must_have_exactly_the_factory_permissions(self):
        self.gh.set_up()
        self.gh.installations[0]["permissions"]["workflows"] = "write"
        code, out = self.run_it()
        self.assertEqual(code, 1)
        self.assertIn("workflows: write", out)

    def test_without_an_org_admin_token_the_org_checks_are_unchecked_not_failed(self):
        self.gh.set_up()
        self.gh.admin = False
        code, out = self.run_it()
        self.assertEqual(code, 0, out)
        self.assertEqual(out.count("unchecked"), 2)

    def test_an_environment_open_to_any_branch_is_left_to_cd(self):
        self.gh.set_up()
        self.gh.envs["factory-planning"]["policy"] = None
        code, out = self.run_it("--apply")
        self.assertEqual(code, 1)
        self.assertIn("factory-planning is deployable from any branch", out)
        self.assertEqual(self.gh.writes, [])

    def test_a_label_in_the_factorys_namespace_it_doesnt_define_is_reported_never_removed(self):
        self.gh.set_up()
        self.gh.labels += [{"name": "factory:tirage", "color": "000000", "description": ""},
                           {"name": "sdlc", "color": "000000", "description": ""}]  # another bundle's: not ours
        for args in ((), ("--apply",)):
            code, out = self.run_it(*args)
            self.assertEqual(code, 1, out)
            self.assertIn("factory:tirage: not one of the factory's labels", out)
            self.assertNotIn("sdlc:", out)
        self.assertEqual(self.gh.writes, [])
        self.assertIn("factory:tirage", {l["name"] for l in self.gh.labels})

    def test_a_label_that_differs_is_updated_on_apply_only(self):
        self.gh.set_up()
        self.gh.labels[0]["color"] = "000000"
        code, out = self.run_it()
        self.assertEqual((code, self.gh.writes), (1, []))
        code, out = self.run_it("--apply")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.gh.labels[0]["color"], bootstrap.LABELS[0][1])

    def ci_workflow(self):
        # A project with a CI tier, whether or not this one has one (an upgraded project's factory.json may not).
        cfg_file = self.root / ".github" / "factory" / "factory.json"
        cfg = json.loads(cfg_file.read_text())
        cfg["runners"]["ci"] = "factory-ci"
        cfg_file.write_text(json.dumps(cfg))
        (self.root / ".github" / "workflows" / "ci.yml").write_text(
            "jobs:\n  t:\n    runs-on: ubuntu-latest\n  e2e:\n    runs-on: [self-hosted, factory-ci]\n")

    def ci_group(self):
        return next((g for g in self.gh.groups if g["name"] == "factory-ci"), None)

    def test_the_ci_tier_gets_a_group_for_its_repositories_not_its_workflows(self):
        self.gh.set_up()
        code, out = self.run_it()
        self.assertEqual(code, 0, out)
        self.assertNotIn("factory-ci", out)  # no workflow uses the label: no group
        self.ci_workflow()
        code, out = self.run_it()
        self.assertEqual(code, 1)
        self.assertIn("the group itself (selected repositories, any of its workflows)", out)
        code, out = self.run_it("--apply")
        ci = self.ci_group()
        # Pull requests' runs come from merge refs, which a branch-pinned workflow list never matches.
        self.assertEqual((ci["visibility"], ci["repos"], ci["restricted_to_workflows"], ci["selected_workflows"]),
                         ("selected", [7], False, []))
        self.assertIn("register its runners with host/setup.sh (TIER=ci)", out)
        self.assertNotIn("ci.yml", json.dumps(self.pool()["selected_workflows"]))  # never in the agents' pool
        self.gh.writes.clear()
        code, out = self.run_it("--apply")
        self.assertEqual(self.gh.writes, [])
        self.assertIn("widget (its workflows that run on factory-ci)", out)

    def test_a_ci_group_restricted_to_workflows_is_left_to_cd(self):
        self.gh.set_up()
        self.ci_workflow()
        self.gh.groups.append({"id": 6, "name": "factory-ci", "visibility": "selected", "restricted_to_workflows": True,
                               "selected_workflows": [f"{REPO}/.github/workflows/ci.yml@refs/heads/main"], "repos": [7],
                               "runners": ["box-ci-1"]})
        code, out = self.run_it("--apply")
        self.assertEqual(code, 1)
        self.assertIn("its merge ref, which the list never matches", out)
        self.assertEqual(self.gh.writes, [])

    def test_a_group_open_to_public_repositories_is_left_to_cd(self):
        self.gh.set_up()
        self.pool()["allows_public_repositories"] = True
        code, out = self.run_it("--apply")
        self.assertEqual(code, 1)
        self.assertIn("lets public repositories use it", out)
        self.assertEqual(self.gh.writes, [])

    def test_a_group_open_to_every_workflow_is_left_to_cd(self):
        self.gh.set_up()
        self.pool()["restricted_to_workflows"] = False
        code, out = self.run_it("--apply")
        self.assertEqual(code, 1)
        self.assertIn("isn't restricted to selected workflows", out)
        self.assertEqual(self.gh.writes, [])

    def test_a_workflow_no_longer_rendered_is_reported(self):
        self.gh.set_up()
        self.pool()["selected_workflows"].append(f"{REPO}/.github/workflows/factory-old.yml@refs/heads/main")
        code, out = self.run_it()
        self.assertEqual(code, 1)
        self.assertIn("no longer renders: acme/widget/.github/workflows/factory-old.yml", out)

    def test_branch_rules_need_code_owner_review_and_a_required_check(self):
        self.gh.set_up()
        self.gh.rulesets[0]["rules"] = []
        code, out = self.run_it()
        self.assertEqual(code, 1)
        self.assertIn("doesn't require code-owner review", out)
        self.assertIn("main's rulesets don't require a team to approve every file", out)
        self.assertIn("has no required status check", out)

    def test_a_team_of_people_must_approve_every_file(self):
        # GitHub asks no code-owner review of a PR whose author owns what it changes, and counts an App's approval:
        # only a team's required review keeps an App from approving and merging CD's own PR (D2 rule 6).
        self.gh.set_up()
        params = self.gh.rulesets[0]["rules"][0]["parameters"]
        code, out = self.run_it()
        self.assertEqual(code, 0, out)
        self.assertIn("main requires team 3's approval on every file", out)
        lacking = "main's rulesets don't require a team to approve every file"
        for name, reviewers in [
                ("none", []),
                ("visibility only", [dict(TEAM_REVIEW, minimum_approvals=0)]),
                ("not a team", [dict(TEAM_REVIEW, reviewer={"id": 3, "type": "User"})]),
                ("some files", [dict(TEAM_REVIEW, file_patterns=["src/**", ".github/"])]),
                ("an unproven pattern", [dict(TEAM_REVIEW, file_patterns=["**"])]),
                ("a leading space, literal in .gitignore", [dict(TEAM_REVIEW, file_patterns=[" *"])]),
                ("a file exempted", [dict(TEAM_REVIEW, file_patterns=["*", "!docs/**"])]),
                ("exempted first", [dict(TEAM_REVIEW, file_patterns=["!docs/**", "*"])])]:
            with self.subTest(name):
                params["required_reviewers"] = reviewers
                code, out = self.run_it()
                self.assertEqual(code, 1, out)
                self.assertIn(lacking, out)
        # A narrower team besides doesn't matter, nor do other patterns beside `*`.
        params["required_reviewers"] = [dict(TEAM_REVIEW, file_patterns=["src/**"], reviewer={"id": 8, "type": "Team"}),
                                        dict(TEAM_REVIEW, file_patterns=["docs/**", "*"])]
        code, out = self.run_it()
        self.assertEqual(code, 0, out)
        self.assertIn("main requires team 3's approval on every file", out)
        # Classic branch protection has no required team: its code-owner review leaves the gap open.
        del params["required_reviewers"]
        params["require_code_owner_review"] = False
        self.gh.protection = {"required_pull_request_reviews": {"require_code_owner_reviews": True,
                                                                "required_approving_review_count": 1}}
        code, out = self.run_it()
        self.assertEqual(code, 1, out)
        self.assertIn("main requires code-owner review", out)
        self.assertIn(lacking, out)

    def test_the_default_branch_is_bypassed_only_through_pull_requests(self):
        # Always (or a missing mode, which means always) and exempt let an admin push to it with no PR. Every factory
        # project's default branch takes PRs only, the bypass included (Enablement step 9).
        self.gh.set_up()
        actor = self.gh.rulesets[0]["bypass_actors"][0]
        for name, mode in [("always", "always"), ("exempt", "exempt"), ("missing", None)]:
            with self.subTest(name):
                actor.pop("bypass_mode", None)
                if mode:
                    actor["bypass_mode"] = mode
                code, out = self.run_it()
                self.assertEqual(code, 1, out)
                self.assertIn(f"main's ruleset main lets OrganizationAdmin bypass it {mode or 'always'}: set it to "
                              "pull requests only", out)
        actor["bypass_mode"] = "pull_request"
        # A tag ruleset's always bypass (release tags are pushed, never merged) is no concern of the default branch's.
        self.gh.rulesets.append({"id": 2, "name": "release tags", "enforcement": "active", "target": "tag",
                                 "conditions": {"ref_name": {"include": ["~ALL"]}},
                                 "bypass_actors": [{"actor_id": 5, "actor_type": "RepositoryRole",
                                                    "bypass_mode": "always"}], "rules": [{"type": "creation"}]})
        code, out = self.run_it()
        self.assertEqual(code, 0, out)
        self.assertNotIn("bypass it", out)

    def test_codeowners_must_own_github_and_claude(self):
        self.gh.set_up()
        (self.root / ".github" / "CODEOWNERS").write_text("/.github/ @cd\n")
        code, out = self.run_it()
        self.assertEqual(code, 1)
        self.assertIn("doesn't own /.claude/", out)

    def test_the_seeds_placeholders_block_apply(self):
        cfg = json.loads((self.root / ".github/factory/factory.json").read_text())
        cfg.update({"app": {"user_id": 0, "login": "your-factory-app[bot]"},
                    "image": {"repository": "ghcr.io/your-org/factory-job", "digest": "sha256:" + "0" * 64},
                    "smoke": {"echo_host": "echo.example.invalid", "host_probes": ""}})
        (self.root / ".github/factory/factory.json").write_text(json.dumps(cfg))
        code, out = self.run_it("--apply")
        self.assertEqual(code, 1)
        self.assertEqual(self.gh.writes, [])
        for text in ("app.user_id and app.login", "image.repository", "image.digest", "smoke.echo_host",
                     "nothing applied: fill the settings above"):
            self.assertIn(text, out)

    def test_only_the_seeds_exact_placeholders_count(self):
        cfg = json.loads((self.root / ".github/factory/factory.json").read_text())
        cfg.update({"app": {"user_id": 7, "login": "your-org-factory[bot]"},
                    "image": {"repository": "ghcr.io/your-org-co/factory-job", "digest": "sha256:" + "c" * 64}})
        (self.root / ".github/factory/factory.json").write_text(json.dumps(cfg))
        code, out = self.run_it()
        self.assertIn("factory.json names your App, image and echo service", out)

    def test_an_unreadable_factory_json_is_a_settings_error(self):
        (self.root / ".github" / "factory" / "factory.json").write_text("{}")
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code, _ = self.run_it()
        self.assertEqual(code, 2)
        self.assertIn("factory.json", err.getvalue())


if __name__ == "__main__":
    unittest.main()
