#!/usr/bin/env python3
"""The GitHub half of a repository's factory setup (z-sdlc process/factory.md, Enablement steps 2 to 9).

    python3 .github/factory/bootstrap.py            report what is missing; change nothing
    python3 .github/factory/bootstrap.py --apply    also create what it can, then report

It applies only the factory's labels, its environments (deployable from the default branch only, with
production's required reviewer) and this repository's entries in the runner groups. It reports and never sets
secrets and variables (their values are CD's), the App's install and permissions, CODEOWNERS and the default
branch's rules (security configuration stays CD's). It writes only what differs, so it is safe to run again.
It runs as the gh login: the runner groups and the App check need an organization admin's token (admin:org),
and without one they are reported as unchecked. The runner groups are factory.json's runners.groups, by default
the shared pool factory-pool (strict and planning) and, with a production tier (production/ops.json), the
project's own factory-pool-<repository>-prod; both are restricted to the workflows that use them. When a
workflow runs on the CI tier's label (runners.ci), the CI group too (factory-ci), restricted to the
repositories that use it and not to workflows: a pull request's run comes from its merge ref, which a
group's branch-pinned workflow list never matches.

Exit 0 when nothing is missing, 1 when something is (or a write failed), 2 on a usage or settings error.
"""
import argparse
import json
import pathlib
import re
import subprocess
import sys
import urllib.parse

# Every factory label (process/factory.md, Labels): name, colour, description.
# The factory owns every label in its namespace, LABEL_PREFIX: a project's other label rules (github-provenance's
# checkpoint labels) leave them to this list, process/factory.md § Labels.
LABEL_PREFIX = "factory:"
LABELS = [
    ("factory:triage", "1d76db", "Opt-in: run factory triage on this issue (removed when triage applies)"),
    ("factory:ready-for-dispatch", "0e8a16",
     "Triage: small and clear; dispatch unattended to implement, review and open a draft PR"),
    ("factory:ready-to-plan", "5319e7", "Triage: needs a plan; tier (lite or full) named in the triage comment"),
    ("factory:needs-input", "fbca04", "Waiting on CD; the question comment names the stage to restart"),
    ("factory:wait", "c5def5", "Triage: blocked by other work or a dependency; comment says what would change that"),
    ("factory:review-capped", "d93f0b", "Review cap hit; draft PR parked with open findings"),
    ("factory:escalated", "b60205", "Revision limit hit; no more automatic runs, CD decides"),
    ("factory:advisor", "8e44ad", "Planning uses a Fable advisor (set by triage or CD; a property, not a state)"),
    ("factory:follow-up", "1d76db",
     "Filed by the factory from a merged plan's PR; triaged, then held until factory:go (a property)"),
    ("factory:go", "0e8a16", "Release a held follow-up: start its triaged stage once (removed after)"),
    ("factory:revise", "fbca04", "On a factory PR: revise it from the latest review comments (drafts)"),
    ("factory:gate", "e99695",
     "Execution stopped before a production gate; its gate run waits for CD's approval (D4)"),
    ("factory:gate-retry", "fbca04", "On an execution PR: build a fresh gate request and start its gate run (D4)"),
]
APP_PERMISSIONS = {"contents": "write", "issues": "write", "pull_requests": "write", "metadata": "read"}
SHARED_GROUP = "factory-pool"
CI_GROUP = "factory-ci"
RUNS_ON = re.compile(r"^\s*runs-on:\s*\[\s*self-hosted\s*,\s*([A-Za-z0-9_.-]+)\s*\]", re.M)
CODEOWNERS_PATHS = (".github/CODEOWNERS", "CODEOWNERS", "docs/CODEOWNERS")


class Settings(Exception):
    pass


def gh(method, path, body=None):
    """gh api as the logged-in user: (HTTP status, parsed body or None). Status 0 when gh itself failed."""
    args = ["gh", "api", "-i", "-X", method, path, "-H", "Accept: application/vnd.github+json"]
    if body is not None:
        args += ["--input", "-"]
    r = subprocess.run(args, input=None if body is None else json.dumps(body), capture_output=True, text=True)
    head, rest = (re.split(r"\r?\n\r?\n", r.stdout, maxsplit=1) + [""])[:2]
    m = re.match(r"HTTP/\S+\s+(\d{3})", head)
    if not m:
        return 0, {"message": (r.stderr or r.stdout).strip()}
    try:
        data = json.loads(rest) if rest.strip() else None
    except json.JSONDecodeError:
        data = None
    return int(m.group(1)), data


def fnmatch_regex(pattern):
    """A ruleset ref pattern as a regex, matched the way GitHub matches it (Ruby's File.fnmatch with
    FNM_PATHNAME): `*` and `?` stay inside one path segment, `**/` spans any number of them, a `**` not followed
    by `/` is a `*`, and `[...]` is a set of characters other than `/`."""
    regex, i = "", 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            regex, i = regex + "(?:[^/]*/)*", i + 3
        elif pattern[i] == "*":
            while i < len(pattern) and pattern[i] == "*":
                i += 1
            regex += "[^/]*"
        elif pattern[i] == "?":
            regex, i = regex + "[^/]", i + 1
        elif pattern[i] == "[" and "]" in pattern[i + 2:]:
            end = pattern.index("]", i + 2)
            body = pattern[i + 1:end]
            negate = body[:1] in ("!", "^")
            body = body[1:] if negate else body
            chars = "".join("\\" + c if c in "\\]^" else c for c in body)
            regex, i = regex + ("(?!/)[^" if negate else "(?!/)[") + chars + "]", end + 1
        elif pattern[i] == "\\" and i + 1 < len(pattern):
            regex, i = regex + re.escape(pattern[i + 1]), i + 2
        else:
            regex, i = regex + re.escape(pattern[i]), i + 1
    return regex


class Bootstrap:
    def __init__(self, api, root, repo, apply, reviewer=None):
        self.api, self.root, self.repo, self.apply, self.reviewer = api, pathlib.Path(root), repo, apply, reviewer
        self.owner, self.name = repo.split("/", 1)
        self.rows, self.failed = [], 0
        factory = self.root / ".github" / "factory"
        try:
            self.cfg = json.loads((factory / "factory.json").read_text())
            self.planning = json.loads((factory / "planning.json").read_text()) \
                if (factory / "planning.json").exists() else {}
            self.services = json.loads((factory / "services.json").read_text()) \
                if (factory / "services.json").exists() else {}
            runners, envs = self.cfg["runners"], self.cfg["environments"]
            self.labels = {k: runners[k] for k in ("strict", "planning", "production")}
            self.envs = {k: envs[k] for k in ("writer", "planning", "production")}
            self.app_slug = self.cfg["app"]["login"].removesuffix("[bot]")
        except (OSError, ValueError, KeyError, TypeError) as e:
            raise Settings(f"can't read .github/factory/factory.json's runners, environments and app: {e}") from e
        groups = runners.get("groups") or {}
        self.groups = {"shared": groups.get("shared") or SHARED_GROUP,
                       "production": groups.get("production") or f"factory-pool-{self.name}-prod",
                       "ci": groups.get("ci") or CI_GROUP}
        # The CI tier is optional: a factory.json from before it has no label for it.
        self.ci_label = runners.get("ci") if isinstance(runners.get("ci"), str) else None
        # A production tier is the project's own operations catalog (D4); without it there is no gate to run.
        self.production = (factory / "production" / "ops.json").exists()

    # ---- reporting
    def note(self, state, section, text):
        self.rows.append((state, section, text))
        if state in ("missing", "problem", "failed"):
            self.failed += 1

    def write(self, section, what, method, path, body=None):
        """One write: True when GitHub accepted it; a failure is reported."""
        status, data = self.api(method, path, body)
        if 200 <= status < 300:
            return True
        self.note("failed", section, f"{what}: HTTP {status} {(data or {}).get('message', '')}".strip())
        return False

    def list_all(self, path, key):
        """Every item of a paged list, or None when the token can't read it."""
        items, page = [], 1
        while True:
            sep = "&" if "?" in path else "?"
            status, data = self.api("GET", f"{path}{sep}per_page=100&page={page}")
            if status != 200:
                return None
            batch = data if key is None else (data or {}).get(key, [])
            items += batch
            if len(batch) < 100:
                return items
            page += 1

    # ---- the repository
    def run(self):
        status, info = self.api("GET", f"repos/{self.repo}")
        if status != 200:
            raise Settings(f"can't read {self.repo} (HTTP {status}): check the name and gh's login")
        self.repo_id, self.default = info["id"], info["default_branch"]
        self.merge_settings = {k: info.get(k) for k in ("allow_merge_commit", "allow_squash_merge", "allow_rebase_merge")}
        self.org = (info.get("owner") or {}).get("type") == "Organization"
        if not self.check_settings() and self.apply:
            # The labels and runner-group entries would work, but a factory with someone else's App or image
            # wouldn't: fill factory.json first, so the setup is applied once, whole.
            self.apply = False
            self.note("problem", "settings", "nothing applied: fill the settings above, run render.py, then --apply")
        self.check_labels()
        self.check_environments()
        self.check_secrets()
        self.check_runner_groups()
        self.check_app()
        self.check_codeowners()
        self.check_branch_rules()
        return self.failed

    def check_settings(self):
        """factory.json's settings that only the adopter can fill: the bundle's seed holds placeholders for them
        (z-sdlc process/factory.md, Enablement). True when every one is filled."""
        app, image = self.cfg.get("app") or {}, self.cfg.get("image") or {}
        echo = (self.cfg.get("smoke") or {}).get("echo_host") or ""
        digest = image.get("digest") or ""
        unset = []
        # The seed's placeholders, exactly (z-sdlc bundles/factory/seed/factory.json).
        if not (isinstance(app.get("user_id"), int) and app["user_id"] > 0) or not str(app.get("login", "")).endswith("[bot]") \
                or app.get("login") == "your-factory-app[bot]":
            unset.append("app.user_id and app.login: your factory App's bot user (Enablement step 5, create_app.py)")
        if not image.get("repository") or image["repository"] == "ghcr.io/your-org/factory-job":
            unset.append("image.repository: where your job image is published (Enablement step 3)")
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest) or set(digest[7:]) == {"0"}:
            unset.append("image.digest: the built image's digest (Enablement step 3)")
        if not echo or echo.endswith(".invalid"):
            unset.append("smoke.echo_host: your echo service (Enablement step 4)")
        for text in unset:
            self.note("missing", "settings", f"factory.json {text}")
        if not unset:
            self.note("ok", "settings", "factory.json names your App, image and echo service")
        return not unset

    def check_labels(self):
        have = {l["name"]: l for l in self.list_all(f"repos/{self.repo}/labels", None) or []}
        ok = 0
        for name, color, description in LABELS:
            cur = have.get(name)
            if cur is None:
                if self.apply and self.write("labels", f"create {name}", "POST", f"repos/{self.repo}/labels",
                                             {"name": name, "color": color, "description": description}):
                    self.note("created", "labels", name)
                elif not self.apply:
                    self.note("missing", "labels", name)
            elif cur.get("color", "").lower() != color or (cur.get("description") or "") != description:
                if self.apply and self.write("labels", f"update {name}", "PATCH",
                                             f"repos/{self.repo}/labels/{urllib.parse.quote(name, safe='')}",
                                             {"color": color, "description": description}):
                    self.note("updated", "labels", f"{name} (colour and description)")
                elif not self.apply:
                    self.note("missing", "labels", f"{name}: colour or description differs from the factory's")
            else:
                ok += 1
        if ok:
            self.note("ok", "labels", f"{ok} of {len(LABELS)} as the factory defines them")
        # One in the factory's namespace it doesn't define (a typo, or one a removed stage left): never deleted for
        # you, since removing a label strips it from every issue that has it.
        defined = {n.lower() for n, _, _ in LABELS}
        for name in sorted(have):
            if name.lower().startswith(LABEL_PREFIX) and name.lower() not in defined:
                self.note("problem", "labels", f"{name}: not one of the factory's labels; remove it, or add it to "
                                               "LABELS if the factory should have it")

    # ---- environments
    def wanted_environments(self):
        envs = [(self.envs["writer"], False), (self.envs["planning"], False)]
        return envs + [(self.envs["production"], True)] if self.production else envs

    def check_environments(self):
        have = {e["name"]: e for e in self.list_all(f"repos/{self.repo}/environments", "environments") or []}
        for env, reviewed in self.wanted_environments():
            base = f"repos/{self.repo}/environments/{urllib.parse.quote(env, safe='')}"
            if env not in have:
                if not self.apply:
                    self.note("missing", "environments", f"{env} (deployable from {self.default} only"
                              + (", CD as required reviewer)" if reviewed else ")"))
                    continue
                body = {"deployment_branch_policy": {"protected_branches": False, "custom_branch_policies": True}}
                if reviewed:
                    reviewer = self.reviewer_id()
                    if reviewer is None:
                        continue
                    body["reviewers"] = [{"type": "User", "id": reviewer}]
                if self.write("environments", f"create {env}", "PUT", base, body) and self.write(
                        "environments", f"{env}: allow {self.default}", "POST", f"{base}/deployment-branch-policies",
                        {"name": self.default, "type": "branch"}):
                    self.note("created", "environments", f"{env}, deployable from {self.default} only"
                              + (" (required reviewer set)" if reviewed else ""))
                continue
            self.check_environment(env, have[env], base, reviewed)

    def check_environment(self, env, cur, base, reviewed):
        policy = cur.get("deployment_branch_policy") or {}
        if not policy.get("custom_branch_policies"):
            # Changing an existing environment's protection is CD's: a PUT replaces all of it.
            self.note("problem", "environments", f"{env} is deployable from any branch: limit it to {self.default}")
            return
        names = {p.get("name") for p in self.list_all(f"{base}/deployment-branch-policies", "branch_policies") or []}
        if self.default not in names:
            if self.apply and self.write("environments", f"{env}: allow {self.default}", "POST",
                                         f"{base}/deployment-branch-policies",
                                         {"name": self.default, "type": "branch"}):
                self.note("updated", "environments", f"{env}: deployable from {self.default}")
                names.add(self.default)
            elif not self.apply:
                self.note("missing", "environments", f"{env}: {self.default} isn't an allowed branch")
        extra = sorted(n for n in names if n != self.default)
        if extra:
            self.note("problem", "environments", f"{env} also deploys from {', '.join(extra)}: {self.default} only")
        reviewers = [r for rule in cur.get("protection_rules") or [] if rule.get("type") == "required_reviewers"
                     for r in rule.get("reviewers") or []]
        if reviewed and not reviewers:
            self.note("problem", "environments", f"{env} has no required reviewer: CD approves every gate run")
        if self.default in names and not extra and (reviewers or not reviewed):
            self.note("ok", "environments", f"{env}: deployable from {self.default} only"
                      + (", with a required reviewer" if reviewed else ""))

    def reviewer_id(self):
        path = f"users/{self.reviewer}" if self.reviewer else "user"
        status, data = self.api("GET", path)
        if status != 200:
            self.note("failed", "environments", f"can't find the reviewer ({path}): HTTP {status}")
            return None
        return data["id"]

    # ---- secrets and variables: names only, never values
    def check_secrets(self):
        names = lambda path, key: {s["name"] for s in self.list_all(path, key) or []}  # noqa: E731
        repo_secrets = names(f"repos/{self.repo}/actions/secrets", "secrets")
        org_secrets = names(f"repos/{self.repo}/actions/organization-secrets", "secrets") if self.org else set()
        self.secret("repository secret", "CLAUDE_CODE_OAUTH_TOKEN", repo_secrets, "from `claude setup-token`")
        if "CLAUDE_CODE_OAUTH_TOKEN" in org_secrets:
            self.note("problem", "secrets", "CLAUDE_CODE_OAUTH_TOKEN is also an organization secret: never share it")
        if "CONTEXT7_API_KEY" not in repo_secrets:
            self.note("optional", "secrets", "repository secret CONTEXT7_API_KEY (Context7's higher rate limit)")
        wanted = {self.envs["writer"]: ([("FACTORY_APP_PRIVATE_KEY", "the App's private key")],
                                        [("FACTORY_APP_CLIENT_ID", "the App's client ID")])}
        planning = []
        if ((self.planning.get("database") or {}).get("host") or "").strip():
            planning.append(("FACTORY_DB_READER_PASSWORD", "the planning database's read-only password"))
        for s in self.services.get("services") or []:
            slot = s.get("slot") or ""
            if slot.startswith("FACTORY_EXEC_SVC_"):
                # An execution stage's service: a repository secret, as implement and revise use no environment.
                self.secret("repository secret", slot, repo_secrets, f"service {s.get('name', '?')}'s credential")
            elif slot:
                planning.append((slot, f"service {s.get('name', '?')}'s credential"))
        wanted[self.envs["planning"]] = (planning, [])
        for env, (secrets, variables) in wanted.items():
            base = f"repos/{self.repo}/environments/{urllib.parse.quote(env, safe='')}"
            have_s = names(f"{base}/secrets", "secrets")
            have_v = names(f"{base}/variables", "variables")
            for name, what in secrets:
                self.secret(f"{env} secret", name, have_s, what)
            for name, what in variables:
                self.secret(f"{env} variable", name, have_v, what)

    def secret(self, where, name, have, what):
        if name in have:
            self.note("ok", "secrets", f"{where} {name}")
        else:
            self.note("missing", "secrets", f"{where} {name} ({what}): set it by hand")

    # ---- runner groups
    def workflow_refs(self):
        """The workflows per tier: the shared pool's (strict and planning), production's and the CI tier's."""
        shared, production, ci = [], [], []
        for f in sorted((self.root / ".github" / "workflows").glob("*.yml")):
            labels = set(RUNS_ON.findall(f.read_text()))
            ref = f"{self.repo}/.github/workflows/{f.name}@refs/heads/{self.default}"
            if labels & {self.labels["strict"], self.labels["planning"]}:
                shared.append(ref)
            if self.labels["production"] in labels:
                production.append(ref)
            if self.ci_label and self.ci_label in labels:
                ci.append(ref)
        return shared, production, ci

    def check_runner_groups(self):
        if not self.org:
            self.note("problem", "runner groups", f"{self.owner} isn't an organization: the runners are org-level")
            return
        groups = self.list_all(f"orgs/{self.owner}/actions/runner-groups", "runner_groups")
        if groups is None:
            self.note("unchecked", "runner groups", "needs an organization admin's token (admin:org)")
            return
        shared, production, ci = self.workflow_refs()
        by_name = {g["name"]: g for g in groups}
        self.check_group(by_name.get(self.groups["shared"]), self.groups["shared"], shared, "host/setup.sh")
        if self.production:
            self.check_group(by_name.get(self.groups["production"]), self.groups["production"], production,
                             "host/setup-production.sh")
        if ci:
            self.check_group(by_name.get(self.groups["ci"]), self.groups["ci"], ci, "host/setup.sh (TIER=ci)",
                             by_workflow=False)

    def check_group(self, group, name, refs, setup, by_workflow=True):
        """A runner group: this repository in it, and (by_workflow) its workflows; the CI group isn't restricted
        to workflows, because pull requests' runs come from merge refs a branch-pinned list never matches."""
        section = f"runner group {name}"
        base = f"orgs/{self.owner}/actions/runner-groups"
        if group is None:
            what = f"{len(refs)} workflows" if by_workflow else "any of its workflows"
            if not self.apply:
                self.note("missing", section, f"the group itself (selected repositories, {what})")
                return
            status, group = self.api("POST", base, {"name": name, "visibility": "selected",
                                                    "selected_repository_ids": [self.repo_id],
                                                    "restricted_to_workflows": by_workflow,
                                                    "selected_workflows": refs if by_workflow else []})
            if status != 201:
                self.note("failed", section, f"create the group: HTTP {status} {(group or {}).get('message', '')}")
                return
            self.note("created", section, f"for {self.name}, with {what}; register its runners with {setup}")
            return
        gid = group["id"]
        if group.get("visibility") != "selected":
            self.note("problem", section, f"visibility is {group.get('visibility')}: every repository can use it")
            return
        if group.get("allows_public_repositories"):
            # A public repository's pull requests come from forks: anyone's code on this host. CD's call to change.
            self.note("problem", section, "lets public repositories use it")
        repos = self.list_all(f"{base}/{gid}/repositories", "repositories")
        if repos is None:
            self.note("unchecked", section, "can't read its repositories")
            return
        repo_ids = [r["id"] for r in repos]
        if self.repo_id not in repo_ids:
            if self.apply and self.write(section, f"add {self.name}", "PUT", f"{base}/{gid}/repositories/{self.repo_id}"):
                self.note("added", section, f"repository {self.name}")
                repo_ids.append(self.repo_id)
            elif not self.apply:
                self.note("missing", section, f"repository {self.name}")
        if not by_workflow:
            if group.get("restricted_to_workflows"):
                # Lifting it is CD's call, like restricting the others.
                self.note("problem", section, "is restricted to selected workflows: a pull request's run comes from "
                          "its merge ref, which the list never matches, so its jobs would wait forever")
            elif self.repo_id in repo_ids:
                self.note("ok", section, f"{self.name} (its workflows that run on {self.ci_label})")
        elif not group.get("restricted_to_workflows"):
            # Restricting it now would stop every other project's workflows that aren't listed: CD's call.
            self.note("problem", section, "isn't restricted to selected workflows")
        else:
            self.check_group_workflows(group, section, base, repo_ids, refs)
        runners = self.list_all(f"{base}/{gid}/runners", "runners")
        if runners is not None and not runners:
            self.note("problem", section, f"has no runners: register them with {setup}")

    def check_group_workflows(self, group, section, base, repo_ids, refs):
        gid, have = group["id"], list(group.get("selected_workflows") or [])
        prefix = f"{self.repo}/.github/workflows/"
        stale = sorted(w for w in have if w.startswith(prefix) and w not in refs)
        if stale:
            self.note("problem", section, f"lists workflows {self.name} no longer renders: {', '.join(stale)}")
        missing = [r for r in refs if r not in have]
        if not missing:
            self.note("ok", section, f"{self.name} and its {len(refs)} workflow{'s' if len(refs) != 1 else ''}")
            return
        if not self.apply:
            for r in missing:
                self.note("missing", section, f"workflow {r.removeprefix(prefix)}")
            return
        # A PATCH replaces the workflow list with what it sends (an omitted list empties it) and, if it sends
        # visibility, empties the repository list: send the whole list, never visibility, then check both.
        wanted = have + missing
        if not self.write(section, "add workflows", "PATCH", f"{base}/{gid}",
                          {"name": group["name"], "restricted_to_workflows": True, "selected_workflows": wanted}):
            return
        status, now = self.api("GET", f"{base}/{gid}")
        after = {r["id"] for r in self.list_all(f"{base}/{gid}/repositories", "repositories") or []}
        lost = [i for i in repo_ids if i not in after]
        if lost:
            self.write(section, "restore its repositories", "PUT", f"{base}/{gid}/repositories",
                       {"selected_repository_ids": repo_ids})
            self.note("problem", section, f"the update dropped {len(lost)} repositories; restored, check it")
        if status != 200 or not set(wanted) <= set(now.get("selected_workflows") or []):
            self.note("failed", section, "the workflow list didn't take: check it in the org settings")
            return
        self.note("added", section, f"{len(missing)} workflows: "
                  + ", ".join(r.removeprefix(prefix) for r in missing))

    # ---- the App
    def check_app(self):
        if not self.org:
            return
        installs = self.list_all(f"orgs/{self.owner}/installations", "installations")
        if installs is None:
            self.note("unchecked", "app", "needs an organization admin's token (admin:org)")
            return
        inst = next((i for i in installs if i.get("app_slug") == self.app_slug), None)
        if inst is None:
            self.note("problem", "app", f"{self.app_slug} isn't installed in {self.owner}: install it on {self.name}")
            return
        if inst.get("repository_selection") != "all":
            repos = self.list_all(f"user/installations/{inst['id']}/repositories", "repositories")
            if repos is None:
                self.note("unchecked", "app", f"can't list {self.app_slug}'s repositories")
            elif not any(r.get("full_name") == self.repo for r in repos):
                self.note("problem", "app", f"{self.app_slug} isn't installed on {self.name}")
                return
        perms = inst.get("permissions") or {}
        if perms != APP_PERMISSIONS:
            diff = sorted(f"{k}: {perms.get(k, 'none')}" for k in set(perms) | set(APP_PERMISSIONS)
                          if perms.get(k) != APP_PERMISSIONS.get(k))
            self.note("problem", "app", f"{self.app_slug}'s permissions differ from contents, issues and pull "
                      f"requests write, metadata read (and nothing else): {', '.join(diff)}")
        else:
            self.note("ok", "app", f"{self.app_slug} installed, with exactly the factory's permissions")

    # ---- CODEOWNERS and the default branch's rules: report only
    def check_codeowners(self):
        path = next((p for p in CODEOWNERS_PATHS if (self.root / p).exists()), None)
        if path is None:
            self.note("problem", "codeowners", "no CODEOWNERS: .github/, .claude/ and the agent configuration "
                      "must be code-owned (D2 rule 6)")
            return
        owned = {line.split()[0] for line in (self.root / path).read_text().splitlines()
                 if line.strip() and not line.lstrip().startswith("#") and len(line.split()) > 1}
        for p in ("/.github/", "/.claude/"):
            if not owned & {p, p.rstrip("/"), p + "**", p.lstrip("/")}:
                self.note("problem", "codeowners", f"{path} doesn't own {p}")
                return
        self.note("ok", "codeowners", f"{path} owns /.github/ and /.claude/ (the seeded tests check the rest)")

    @staticmethod
    def a_team_approves_every_file(entry):
        """One of a ruleset pull-request rule's required reviewers, read as D2 rule 6 needs it: a team (a team holds
        accounts, never an App) whose approval is required (0 only adds it for visibility) on every file. Its
        patterns are .gitignore's syntax; only `*` itself is proven to match every path, dot-directories at any
        depth included (a leading space is part of a pattern there), and a `!` line exempts paths, so anything
        else is reported, never guessed at."""
        patterns = entry.get("file_patterns") or []
        return ((entry.get("reviewer") or {}).get("type") == "Team" and (entry.get("minimum_approvals") or 0) >= 1
                and "*" in patterns and not any(p.strip().startswith("!") for p in patterns))

    def check_branch_rules(self):
        owner_review, team_review, checks, merge_methods, bypass = False, None, set(), None, []
        for rs in self.list_all(f"repos/{self.repo}/rulesets?includes_parents=true", None) or []:
            status, full = self.api("GET", f"repos/{self.repo}/rulesets/{rs['id']}")
            if status != 200 or full.get("enforcement") != "active" or full.get("target") != "branch":
                continue
            include = ((full.get("conditions") or {}).get("ref_name") or {}).get("include") or []
            if not {"~DEFAULT_BRANCH", "~ALL", f"refs/heads/{self.default}"} & set(include):
                continue
            for actor in full.get("bypass_actors") or []:
                # Missing means always; exempt doesn't apply the rules at all. Either lets the actor push to the
                # default branch with no PR. In pull-request mode a bypass only merges a PR, and is recorded.
                if actor.get("bypass_mode", "always") != "pull_request":
                    who = f"{actor.get('actor_type', '?')} {actor.get('actor_id') or ''}".strip()
                    bypass.append(f"{full.get('name') or full.get('id')} lets {who} bypass it "
                                  f"{actor.get('bypass_mode', 'always')}")
            for rule in full.get("rules") or []:
                params = rule.get("parameters") or {}
                if rule.get("type") == "pull_request" and params.get("require_code_owner_review"):
                    owner_review = True
                if rule.get("type") == "pull_request" and team_review is None:
                    team_review = next((e["reviewer"].get("id") or "?" for e in params.get("required_reviewers") or []
                                        if self.a_team_approves_every_file(e)), None)
                if rule.get("type") == "pull_request" and params.get("allowed_merge_methods"):
                    allowed = set(params["allowed_merge_methods"])
                    merge_methods = allowed if merge_methods is None else merge_methods & allowed
                if rule.get("type") == "required_status_checks":
                    checks |= {c.get("context") for c in params.get("required_status_checks") or []}
        status, prot = self.api("GET", f"repos/{self.repo}/branches/{self.default}/protection")
        if status == 200:
            owner_review |= bool((prot.get("required_pull_request_reviews") or {}).get("require_code_owner_reviews"))
            checks |= set(((prot.get("required_status_checks") or {}).get("contexts")) or [])
        if owner_review:
            self.note("ok", "branch rules", f"{self.default} requires code-owner review")
        else:
            self.note("problem", "branch rules", f"{self.default} doesn't require code-owner review (D2 rule 6)")
        # Classic branch protection has no required team, so only a ruleset counts. Without one, GitHub asks no
        # code-owner review of a PR whose author owns what it changes and counts an App's approval, so an App could
        # approve and merge CD's own PR, recorded as a pass.
        if team_review is not None:
            self.note("ok", "branch rules", f"{self.default} requires team {team_review}'s approval on every file: "
                      "only people CD trusts as reviewers may be on it")
        else:
            self.note("problem", "branch rules", f"{self.default}'s rulesets don't require a team to approve every file "
                      "(required reviewers: a team of people with write access, file pattern `*`, one approval, no `!` "
                      "line). Without it an App's approval merges a PR CD opens (D2 rule 6)")
        for text in dict.fromkeys(bypass):
            self.note("problem", "branch rules", f"{self.default}'s ruleset {text}: set it to pull requests only, so "
                      "nothing reaches it but a PR (Enablement step 9)")
        if checks:
            self.note("ok", "branch rules", f"{self.default} requires {', '.join(sorted(c for c in checks if c))}: "
                      "it must run render.py --check, workflow_policy.py and the factory's tests")
        else:
            self.note("problem", "branch rules", f"{self.default} has no required status check: CI must run "
                      "render.py --check, workflow_policy.py and the factory's tests")
        release = ((self.cfg.get("release") or {}).get("branch") or "").strip()
        if release:
            self.check_release_branch(release)
            self.check_pinned_branches()
        elif self.production:
            self.check_merge_methods(merge_methods)

    def covering_rulesets(self, ref):
        """The active branch rulesets that cover a ref: one of their ref_name includes matches it (GitHub's
        fnmatch patterns, ~ALL and ~DEFAULT_BRANCH) and none of their excludes does."""
        def matches(pattern, ref):
            if pattern == "~ALL":
                return True
            if pattern == "~DEFAULT_BRANCH":
                return ref == f"refs/heads/{self.default}"
            return re.fullmatch(fnmatch_regex(pattern), ref) is not None
        found = []
        for rs in self.list_all(f"repos/{self.repo}/rulesets?includes_parents=true", None) or []:
            status, full = self.api("GET", f"repos/{self.repo}/rulesets/{rs['id']}")
            if status != 200 or full.get("enforcement") != "active" or full.get("target") != "branch":
                continue
            names = (full.get("conditions") or {}).get("ref_name") or {}
            if any(matches(p, ref) for p in names.get("include") or []) \
                    and not any(matches(p, ref) for p in names.get("exclude") or []):
                found.append(full)
        return found

    def check_release_branch(self, branch):
        """Production follows a release branch (D4 rule 13): every host serving production deploys it by itself, so
        CD's merge into it is the deploy's approval. Its rulesets must make that merge the only way in: a PR with
        code-owner review and merge commits only (provenance reads them), no force push, no deletion, and updates
        restricted to bypass actors who are only organization or repository admins, in pull-request mode."""
        status, _ = self.api("GET", f"repos/{self.repo}/branches/{urllib.parse.quote(branch, safe='')}")
        if status != 200:
            self.note("problem", "release branch", f"no branch {branch} (factory.json's release.branch): create it at "
                      f"{self.default}'s tip and point production's hosts at it (Enablement step 2), or set release.branch "
                      "to \"\" for the fallback, execution-PR gates (D4 rule 13)")
            return
        found, methods, problems = set(), None, []
        for full in self.covering_rulesets(f"refs/heads/{branch}"):
            for actor in full.get("bypass_actors") or []:
                who = f"{actor.get('actor_type', '?')} {actor.get('actor_id') or ''}".strip()
                admin = actor.get("actor_type") in ("OrganizationAdmin", "EnterpriseOwner") or (
                    actor.get("actor_type") == "RepositoryRole" and actor.get("actor_id") == 5)
                if not admin:
                    # An App, team, deploy key or a role below admin could merge a release PR: that is a deploy.
                    problems.append(f"lets {who} bypass it: only organization or repository admins may")
                elif actor.get("bypass_mode", "always") != "pull_request":
                    # Missing means always; exempt doesn't apply the rules at all. Either can push, force-push or delete.
                    problems.append(f"lets {who} bypass it {actor.get('bypass_mode', 'always')}: set it to pull requests only")
            for rule in full.get("rules") or []:
                params = rule.get("parameters") or {}
                if rule.get("type") == "pull_request":
                    if params.get("require_code_owner_review"):
                        found.add("code-owner review")
                    if params.get("allowed_merge_methods"):
                        allowed = set(params["allowed_merge_methods"])
                        methods = allowed if methods is None else methods & allowed
                if rule.get("type") == "update":
                    if params.get("update_allows_fetch_and_merge"):
                        problems.append("lets updates through as fetch and merge (a fork-sync allowance)")
                    else:
                        found.add("update")
                if rule.get("type") in ("non_fast_forward", "deletion"):
                    found.add(rule["type"])
        if methods == {"merge"}:
            found.add("merge commits")
        wanted = {"code-owner review": "a PR with code-owner review", "merge commits": "merge commits only",
                  "update": "restricted updates", "non_fast_forward": "no force push", "deletion": "no deletion"}
        missing = [text for key, text in wanted.items() if key not in found]
        if missing:
            self.note("problem", "release branch", f"{branch}'s rulesets lack {', '.join(missing)}: merging into it "
                      "deploys, so CD's merge must be the only way in (D4 rule 13)")
        for problem in dict.fromkeys(problems):
            self.note("problem", "release branch", f"{branch}'s ruleset {problem} (D4 rule 13)")
        if not missing and not problems:
            self.note("ok", "release branch", f"{branch} takes changes only through a PR an admin merges, with "
                      "code-owner review and a merge commit")

    # Names a release gate pins its commit on, spread over the pattern: a ruleset must cover every one.
    PINNED_SAMPLES = ("refs/heads/factory/release/1-G1-0123456789ab", "refs/heads/factory/release/42-G7-fedcba987654",
                      "refs/heads/factory/release/99999-G99-a1b2c3d4e5f6")

    def check_pinned_branches(self):
        """A release gate pins its commit on factory/release/<pr>-<gate>-<commit> (D4 rule 13). Rulesets must keep
        every such branch from moving once the factory App creates it: updates, deletion and force pushes
        restricted, creation allowed, and no bypass actor at all, the App included."""
        problems, uncovered = [], {}
        for ref in self.PINNED_SAMPLES:
            found = set()
            for full in self.covering_rulesets(ref):
                types = {rule.get("type") for rule in full.get("rules") or []}
                if "creation" in types and not full.get("bypass_actors"):
                    problems.append("restricts creation: the factory App couldn't pin a release gate's commit")
                # Samples can't see every exclude: one that could leave out any pinned name is a hole.
                for pattern in ((full.get("conditions") or {}).get("ref_name") or {}).get("exclude") or []:
                    literal = re.split(r"[*?\[]", pattern, maxsplit=1)[0]
                    if pattern == "~ALL" or "refs/heads/factory/release/".startswith(literal) \
                            or literal.startswith("refs/heads/factory/release/"):
                        problems.append(f"excludes {pattern}, which can leave pinned branches out")
                if types & {"update", "deletion", "non_fast_forward"} and full.get("bypass_actors"):
                    actors = ", ".join(f"{a.get('actor_type', '?')} {a.get('actor_id') or ''}".strip()
                                       for a in full["bypass_actors"])
                    problems.append(f"lets {actors} bypass it: nothing may move a pinned branch")
                for rule in full.get("rules") or []:
                    if rule.get("type") == "update" and (rule.get("parameters") or {}).get("update_allows_fetch_and_merge"):
                        problems.append("lets updates through as fetch and merge (a fork-sync allowance)")
                    elif rule.get("type") in ("update", "deletion", "non_fast_forward"):
                        found.add(rule["type"])
            for key, text in (("update", "restricted updates"), ("deletion", "no deletion"),
                              ("non_fast_forward", "no force push")):
                if key not in found:
                    uncovered.setdefault(text, ref[len("refs/heads/"):])
        if uncovered:
            self.note("problem", "release branch", "factory/release/** (release gates' pinned commits) needs a ruleset "
                      f"with {', '.join(uncovered)} on every branch under it ({', '.join(sorted(set(uncovered.values())))} "
                      "isn't covered): a pinned branch could move after CD reviews it (D4 rule 13)")
        for problem in dict.fromkeys(problems):
            self.note("problem", "release branch", f"factory/release/**'s ruleset {problem} (D4 rule 13)")
        if not uncovered and not problems:
            self.note("ok", "release branch", "factory/release/** branches can't move once created")

    def check_merge_methods(self, ruleset_methods):
        """With a production tier, an execution PR merges with a merge commit (D4 rule 13): the broker deploys
        the PR's head, so a squash or rebase leaves production on a commit the default branch doesn't contain,
        and rule 7 refuses the next gate."""
        keys = {"merge": "allow_merge_commit", "squash": "allow_squash_merge", "rebase": "allow_rebase_merge"}
        if any(self.merge_settings.get(k) is None for k in keys.values()):
            self.note("unchecked", "branch rules", "can't read the repository's merge settings (they need admin "
                      "access): execution PRs must merge with a merge commit (D4 rule 13)")
            return
        allowed = {m for m, k in keys.items() if self.merge_settings[k]}
        if ruleset_methods is not None:
            allowed &= ruleset_methods
        if "merge" not in allowed:
            self.note("problem", "branch rules", f"{self.default} allows no merge commit: an execution PR merges "
                      "with one (D4 rule 13)")
        elif allowed - {"merge"}:
            self.note("problem", "branch rules", f"{self.default} also allows {' and '.join(sorted(allowed - {'merge'}))} "
                      "merges: one of an execution PR leaves production on a commit the branch doesn't contain, and "
                      "the next gate is refused (D4 rules 7 and 13). Allow merge commits only, in the repository's "
                      "settings or the branch's ruleset (allowed merge methods)")
        else:
            self.note("ok", "branch rules", f"{self.default} merges with merge commits only (D4 rule 13)")


def main(argv=None, api=gh):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--apply", action="store_true", help="create the labels, environments and runner-group entries")
    ap.add_argument("--repo", help="owner/name (default: gh's repository for the checkout)")
    ap.add_argument("--reviewer", help="production's required reviewer (default: the gh login)")
    ap.add_argument("--root", default=str(pathlib.Path(__file__).resolve().parents[2]), help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    repo = args.repo
    if not repo:
        r = subprocess.run(["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"],
                           cwd=args.root, capture_output=True, text=True)
        repo = r.stdout.strip()
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", repo or ""):
        print("bootstrap: can't tell the repository; pass --repo owner/name", file=sys.stderr)
        return 2
    try:
        b = Bootstrap(api, args.root, repo, args.apply, args.reviewer)
        failed = b.run()
    except Settings as e:
        print(f"bootstrap: {e}", file=sys.stderr)
        return 2
    width = max((len(s) for s, _, _ in b.rows), default=0)
    section = None
    for state, sec, text in b.rows:
        if sec != section:
            print(sec)
            section = sec
        print(f"  {state:<{width}}  {text}")
    print(f"\n{repo}: " + ("nothing missing" if not failed else f"{failed} to fix")
          + ("" if args.apply else " (report only; --apply creates labels, environments and runner-group entries)"))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
