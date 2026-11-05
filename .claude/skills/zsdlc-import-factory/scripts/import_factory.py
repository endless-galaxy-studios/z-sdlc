#!/usr/bin/env python3
"""Import the software factory from its incubator (quantile) into z-sdlc's `factory` bundle.

    python3 .claude/skills/zsdlc-import-factory/scripts/import_factory.py ~/Projects/quantile
    python3 .claude/skills/zsdlc-import-factory/scripts/import_factory.py ~/Projects/quantile --apply
    python3 .claude/skills/zsdlc-import-factory/scripts/import_factory.py ~/Projects/quantile --to-incubator
    python3 .claude/skills/zsdlc-import-factory/scripts/import_factory.py ~/Projects/quantile --prove

It reads the incubator at a commit (default HEAD), never its working tree, and sorts every file under its
.github/factory/ with import.json's rules: excluded (the project's own), a seed (the bundle keeps its own
generic version), or bundle code (everything else, the bundle's tree). It compares each bundle code file
three ways (the incubator now, the bundle now, the incubator at the last import) and reports what the
incubator added, changed and removed; what z-sdlc changed itself (a fix found in a project that installed
the bundle goes straight into z-sdlc, CD 2026-10-12), which is never overwritten; and conflicts, changed
on both sides. It also reports settings the incubator's JSON seeds have and the bundle's don't; other seeds the incubator changed since the last import; incubator-specific text an import would
add; and whether the incubator's copies of z-sdlc's skills and process docs still match z-sdlc's.

--apply writes the bundle code and records the imported commit in import.json. It refuses while an item
marked [fix first] is open (a missing seed setting, an incubator edit to z-sdlc's text), since recording the
import would hide it. An added or removed file, and an item marked [check, then --accept] (a conflict
among them), need --accept. --to-incubator writes z-sdlc's own changes (bundle code it's ahead on, newer
skills and process docs) into the incubator's working tree, for a person to commit there.

--prove installs the incubator's bundle code at the commit, with the bundle's seeds, into a clone of the
incubator (nothing may change) and into an empty project (every template renders, the workflow policy
passes, every test passes).

Exit 0 when nothing needs a person, 1 when something does (or the proof fails), 2 on a usage or setup error.
"""
import argparse
import datetime
import difflib
import fnmatch
import json
import pathlib
import re
import shlex
import shutil
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve()
ROOT = HERE.parents[4]
RULES = HERE.parents[1] / "import.json"

# The CODEOWNERS Enablement step 9 asks for (process/factory.md), for the empty project's seeded test: the
# factory's and other agents' and tools' paths, what each profile's tools load just because it exists (§ Stack
# Profiles), the owner-less lines for what agents may write, then the governing knowledge and the agent files
# owned again after them (last match wins).
PROOF_CODEOWNERS = """/.github/ @owner
.mcp.json @owner
.claude/ @owner
CLAUDE.md @owner
claude.md @owner
Claude.md @owner
CLAUDE.local.md @owner
claude.local.md @owner
Claude.local.md @owner
AGENTS.md @owner
agents.md @owner
Agents.md @owner
GEMINI.md @owner
.codex/ @owner
.gemini/ @owner
.cursor/ @owner
.vscode/ @owner
.devcontainer/ @owner
.envrc @owner
.gitattributes @owner
mise.toml @owner
.tool-versions @owner
/ops/sdlc/ @owner
requirements*.txt @owner
pyproject.toml @owner
setup.py @owner
setup.cfg @owner
pytest.ini @owner
.pytest.ini @owner
pytest.toml @owner
.pytest.toml @owner
tox.ini @owner
conftest.py @owner
sitecustomize.py @owner
hatch.toml @owner
hatch_build.py @owner
uv.lock @owner
uv.toml @owner
.python-version @owner
.python-versions @owner
ruff.toml @owner
.ruff.toml @owner
mypy.ini @owner
.mypy.ini @owner
.coveragerc @owner
alembic.ini @owner
*.csproj @owner
*.fsproj @owner
*.vbproj @owner
*.csproj.user @owner
*.fsproj.user @owner
*.vbproj.user @owner
*.props @owner
*.targets @owner
*.rsp @owner
*.sln @owner
*.slnx @owner
*.slnf @owner
global.json @owner
nuget.config @owner
NuGet.config @owner
NuGet.Config @owner
.config/dotnet-tools.json @owner
dotnet-tools.json @owner
*.runsettings @owner
xunit.runner.json @owner
.editorconfig @owner
.globalconfig @owner
package.json @owner
package-lock.json @owner
pnpm-lock.yaml @owner
pnpm-workspace.yaml @owner
.npmrc @owner
.pnpmfile.cjs @owner
eslint.config.* @owner
tsconfig*.json @owner
vite.config.* @owner
vitest.config.* @owner
vitest.workspace.* @owner
.eslintrc* @owner
postcss.config.* @owner
.postcssrc* @owner
babel.config.* @owner
.babelrc* @owner
/ops/sdlc/disciplines/*.md
/ops/sdlc/knowledge/**/*.yaml
/ops/sdlc/process/sdlc_changelog.md
/ops/sdlc/knowledge/agent-context-map.yaml @owner
/ops/sdlc/knowledge/architecture/agent-communication-protocol.yaml @owner
/ops/sdlc/knowledge/architecture/agent-orchestration-patterns.yaml @owner
/ops/sdlc/knowledge/architecture/knowledge-management-methodology.yaml @owner
/ops/sdlc/knowledge/architecture/model-tier-strategy.yaml @owner
/ops/sdlc/knowledge/architecture/prompt-engineering-patterns.yaml @owner
/ops/sdlc/knowledge/architecture/token-economics.yaml @owner
/ops/sdlc/knowledge/architecture/security-review-taxonomy.yaml @owner
CLAUDE.md @owner
claude.md @owner
Claude.md @owner
CLAUDE.local.md @owner
claude.local.md @owner
Claude.local.md @owner
AGENTS.md @owner
agents.md @owner
Agents.md @owner
GEMINI.md @owner
"""


class Stop(Exception):
    """A usage or setup error: exit 2."""


class Refused(Exception):
    """--apply won't write without a person's say: exit 1."""


# What --apply does about a need: FIX refuses until it's resolved (applying would record the import and hide
# it), ACCEPT needs --accept after a person has checked it, NOTE never blocks (it concerns the incubator).
FIX, ACCEPT, NOTE = "fix first", "check, then --accept", "for the incubator"


def git(repo, *args, binary=False):
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True)
    if r.returncode:
        raise Stop(f"git {' '.join(args)}: {r.stderr.decode(errors='replace').strip()}")
    return r.stdout if binary else r.stdout.decode()


def keys(value, prefix=""):
    """The dotted paths of a JSON object's settings; keys starting with _ are documentation."""
    out = set()
    if isinstance(value, dict):
        for k, v in value.items():
            if k.startswith("_"):
                continue
            path = f"{prefix}.{k}" if prefix else k
            out.add(path)
            out |= keys(v, path)
    return out


class Import:
    def __init__(self, root, rules_path, incubator, commit):
        self.root, self.rules_path, self.incubator = pathlib.Path(root), pathlib.Path(rules_path), pathlib.Path(incubator)
        try:
            self.rules = json.loads(self.rules_path.read_text())
            bundle = json.loads((self.root / "skeleton/manifest.json").read_text())["bundles"][self.rules["bundle"]]
            self.tree_dir = self.root / bundle["tree"]["from"]
            self.tree_to = bundle["tree"]["to"]
            self.seed_dir = self.root / bundle["seed"]["from"]
        except (OSError, ValueError, KeyError, TypeError) as e:
            raise Stop(f"can't read the rules or the bundle's manifest entry: {e}") from e
        self.render = bundle.get("render")
        sdlc_root = (bundle.get("requires") or {}).get("sdlc_root", "ops/sdlc")
        # z-sdlc's text that the incubator keeps exact copies of: {z-sdlc path: incubator path}.
        self.mirrors = {s: ".claude/" + s for s in bundle.get("skills", [])}
        self.mirrors.update({p: f"{sdlc_root}/{p}" for p in bundle.get("process", [])})
        self.source = self.rules["source"].rstrip("/")
        self.commit = git(self.incubator, "rev-parse", "--verify", f"{commit}^{{commit}}").strip()
        last = (self.rules.get("last_import") or {}).get("commit") or ""
        self.last = git(self.incubator, "rev-parse", "--verify", f"{last}^{{commit}}").strip() if last else ""
        self.needs, self.notes = [], []  # needs: (what --apply does about it, text)

    # ---- reading the incubator
    def listing(self, commit):
        """{path under source: git mode} at a commit."""
        out = git(self.incubator, "ls-tree", "-r", "-z", commit, "--", self.source)
        files = {}
        for entry in filter(None, out.split("\0")):
            meta, path = entry.split("\t", 1)
            mode = meta.split()[0]
            if mode == "120000":
                raise Stop(f"{path} is a symlink: the bundle takes regular files only")
            files[path[len(self.source) + 1:]] = mode
        return files

    def blob(self, commit, path):
        return git(self.incubator, "show", f"{commit}:{path}", binary=True)

    def kind(self, rel):
        if any(fnmatch.fnmatchcase(rel, pattern) for pattern in self.rules["excluded"]):
            return "excluded"
        return "seed" if rel in self.rules["seed"] else "tree"

    @staticmethod
    def files_under(directory):
        return sorted(p.relative_to(directory).as_posix() for p in directory.rglob("*")
                      if p.is_file() and "__pycache__" not in p.parts and p.name != ".DS_Store")

    # ---- the report
    def analyze(self):
        listing = self.listing(self.commit)
        kinds = {rel: self.kind(rel) for rel in listing}
        self.tree = {rel: (self.blob(self.commit, f"{self.source}/{rel}"), listing[rel])
                     for rel, k in kinds.items() if k == "tree"}
        self.compare()
        self.excluded = sorted(rel for rel, k in kinds.items() if k == "excluded")
        self.seeds = sorted(rel for rel, k in kinds.items() if k == "seed")
        self.check_specific()
        self.check_seeds(kinds)
        self.check_mirrors()
        paths = [self.source, *self.mirrors.values()]
        self.log = git(self.incubator, "log", "--oneline", "--no-decorate", f"{self.last}..{self.commit}", "--",
                       *paths).strip() if self.last else ""
        return self

    def compare(self):
        """Each bundle code file three ways: the incubator now, the bundle now, and the incubator at the last
        import, which both started from. A fix found in a project that installed the bundle is made in z-sdlc
        (CD, 2026-10-12), so the bundle can be ahead: that is never overwritten, and goes to the incubator."""
        have = set(self.files_under(self.tree_dir)) if self.tree_dir.exists() else set()
        base = {}
        if self.last:
            base = {rel: mode for rel, mode in self.listing(self.last).items() if self.kind(rel) == "tree"}
        self.added, self.changed, self.removed, self.conflicts, self.ahead = [], [], [], [], []
        for rel in sorted(set(self.tree) | have):
            theirs = (self.tree[rel][0], self.tree[rel][1] == "100755") if rel in self.tree else None
            ours = ((self.tree_dir / rel).read_bytes(), bool((self.tree_dir / rel).stat().st_mode & 0o100)) \
                if rel in have else None
            if theirs == ours:
                continue
            if not self.last:  # no recorded starting point: the incubator's version is the import
                start = ours
            elif rel in base and (ours is not None or self.ever_in_bundle(rel)):
                start = (self.blob(self.last, f"{self.source}/{rel}"), base[rel] == "100755")
            else:  # new since the last import, or excluded then and bundle code under today's rules
                start = None
            if ours == start:  # only the incubator changed it: import it
                (self.added if ours is None else self.removed if theirs is None else self.changed).append(rel)
            elif theirs == start:  # only z-sdlc changed it
                how = "added" if start is None else "removed" if ours is None else "changed"
                self.ahead.append((rel, how))
                self.needs.append((NOTE, f"bundle code {rel}: z-sdlc {how} it and the incubator hasn't; copy it into "
                                         "the incubator (--to-incubator)"))
            else:
                self.conflicts.append(rel)
                self.needs.append((ACCEPT, f"bundle code {rel}: changed in both the incubator and z-sdlc since the last "
                                           "import; merge z-sdlc's change into the incubator's file and commit it "
                                           "there, then --apply --accept takes the incubator's"))

    def ever_in_bundle(self, rel):
        """Whether z-sdlc's history has ever had this bundle code file. One the bundle never had was excluded at
        the last import (the rules changed since), so it is new to the bundle, not something z-sdlc removed.
        Outside a git repository, assume it was."""
        path = (self.tree_dir / rel).relative_to(self.root).as_posix()
        r = subprocess.run(["git", "-C", str(self.root), "log", "-1", "--format=%H", "--", path],
                           capture_output=True, text=True)
        return r.returncode != 0 or bool(r.stdout.strip())

    def was_ours(self, ours, data):
        """Whether these bytes are a version of z-sdlc's file its history committed: then the incubator's copy is
        one --to-incubator wrote, not an edit made there. Outside a git repository, assume it isn't."""
        h = subprocess.run(["git", "hash-object", "--stdin"], input=data, capture_output=True)
        r = subprocess.run(["git", "-C", str(self.root), "log", "--format=", "--raw", "--no-abbrev", "--", ours],
                           capture_output=True, text=True)
        if h.returncode or r.returncode:
            return False
        blob = h.stdout.decode().strip()
        return any(line.split()[3] == blob for line in r.stdout.splitlines() if line.startswith(":"))

    def check_specific(self):
        patterns = self.rules.get("specific") or []
        if not patterns:
            return
        pattern = re.compile("|".join(patterns), re.I)
        for rel in self.added + self.changed + self.conflicts:
            new = self.tree[rel][0].decode(errors="replace").splitlines()
            old = (self.tree_dir / rel).read_text(errors="replace").splitlines() \
                if (self.tree_dir / rel).exists() else []
            for line in difflib.unified_diff(old, new, lineterm="", n=0):
                if line.startswith("+") and not line.startswith("+++") and pattern.search(line):
                    self.needs.append((ACCEPT, f"incubator-specific text added to {rel}: {line[1:].strip()[:110]}"))

    def check_seeds(self, kinds):
        for rel in self.rules["seed"]:
            path = f"{self.source}/{rel}"
            if rel not in kinds:
                self.notes.append(f"seed {rel}: the incubator has none")
                continue
            ours = self.seed_dir / rel
            if not ours.exists():
                self.needs.append((FIX, f"seed {rel}: the bundle has no generic version (add "
                                        f"{ours.relative_to(self.root)})"))
                continue
            theirs = self.blob(self.commit, path)
            if rel.endswith(".json"):
                # Below a free setting the keys are the project's own data (stack.env's variable names).
                free = (self.rules.get("free_settings") or {}).get(rel, [])
                settle = lambda ks: {k for k in ks if not any(k.startswith(f + ".") for f in free)}  # noqa: E731
                try:
                    theirs_keys, our_keys = settle(keys(json.loads(theirs))), settle(keys(json.loads(ours.read_text())))
                except ValueError as e:
                    self.needs.append((FIX, f"seed {rel}: isn't JSON ({e})"))
                    continue
                for k in sorted(theirs_keys - our_keys):
                    self.needs.append((FIX, f"seed {rel}: the incubator has setting {k}; add it to the bundle's "
                                            "seed with a default"))
                # An optional setting (one the bundle's code reads only when it's there) can be absent in the
                # incubator, which may not use it.
                optional = (self.rules.get("optional_settings") or {}).get(rel, [])
                for k in sorted(our_keys - theirs_keys):
                    if any(k == o or k.startswith(o + ".") for o in optional):
                        continue
                    self.needs.append((FIX, f"seed {rel}: the bundle's seed has setting {k} and the incubator "
                                            "doesn't: removed there? (if it's optional, list it in "
                                            "import.json's optional_settings)"))
            elif self.last:
                try:
                    before = self.blob(self.last, path)
                except Stop:
                    before = None
                if before != theirs:
                    self.needs.append((ACCEPT, f"seed {rel}: the incubator changed its own since the last import; "
                                               "does the bundle's generic version need the same change?"))

    def check_mirrors(self):
        self.newer_mirrors = []
        for ours, theirs in sorted(self.mirrors.items()):
            try:
                copy = self.blob(self.commit, theirs)
            except Stop:
                self.needs.append((NOTE, f"{theirs}: the incubator has no copy of z-sdlc's {ours}"))
                continue
            if copy == (self.root / ours).read_bytes():
                continue
            edited = False
            if self.last:
                try:
                    edited = self.blob(self.last, theirs) != copy
                except Stop:
                    edited = True
            if edited and self.was_ours(ours, copy):  # the incubator took a copy z-sdlc committed (--to-incubator)
                edited = False
            if edited:
                self.needs.append((FIX, f"{theirs}: the incubator changed its copy of z-sdlc's {ours} since the "
                                        "last import; port the change into z-sdlc, then copy it back"))
            else:
                self.newer_mirrors.append((ours, theirs))
                self.needs.append((NOTE, f"{theirs}: z-sdlc's {ours} is newer; copy it into the incubator "
                                         "(--to-incubator)"))

    def report(self):
        short = self.commit[:7]
        print(f"{self.rules['incubator']} {self.source}/ at {short}"
              + (f" (last import {self.last[:7]})" if self.last else " (no import recorded yet)"))
        print(f"\nBundle code ({self.tree_dir.relative_to(self.root)}/): {len(self.tree)} files")
        for label, files in (("added", self.added), ("changed", self.changed), ("removed", self.removed),
                             ("conflict", self.conflicts)):
            for rel in files:
                print(f"  {label:<8} {rel}")
        for rel, how in self.ahead:
            print(f"  ahead    {rel} (z-sdlc {how} it)")
        if not (self.added or self.changed or self.removed or self.conflicts or self.ahead):
            print("  in sync")
        print(f"\nNot imported: {len(self.seeds)} seeds, {len(self.excluded)} excluded")
        for note in self.notes:
            print(f"  {note}")
        if self.log:
            print(f"\nIncubator commits since the last import:\n  " + self.log.replace("\n", "\n  "))
        if self.needs:
            print("\nNeeds a person:")
            for what, need in self.needs:
                print(f"  - [{what}] {need}")

    # ---- writing
    def apply(self, accept):
        # Applying records the import, and later reports compare against it: what isn't resolved first is lost.
        if any(what == FIX for what, _ in self.needs):
            raise Refused("resolve every [fix first] item above, then apply")
        if (self.added or self.removed or any(what == ACCEPT for what, _ in self.needs)) and not accept:
            raise Refused("the import adds or removes bundle files, or lists [check, then --accept] items (above): "
                          "check each, then re-run with --apply --accept (or add a rule to import.json for a file)")
        for rel in self.added + self.changed + self.conflicts:  # conflicts only get here with --accept
            data, mode = self.tree[rel]
            dest = self.tree_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            dest.chmod(0o755 if mode == "100755" else 0o644)
        for rel in self.removed:
            (self.tree_dir / rel).unlink()
            parent = (self.tree_dir / rel).parent
            while parent != self.tree_dir and not any(parent.iterdir()):
                parent.rmdir()
                parent = parent.parent
        self.rules["last_import"] = {"commit": self.commit, "date": datetime.date.today().isoformat()}
        self.rules_path.write_text(json.dumps(self.rules, indent=2) + "\n")
        print(f"\nApplied: {len(self.added)} added, {len(self.changed)} changed, {len(self.removed)} removed"
              + (f", {len(self.conflicts)} conflicts taken from the incubator" if self.conflicts else "")
              + f"; last import is now {self.commit[:7]}."
              + (f" {len(self.ahead)} files z-sdlc changed are kept." if self.ahead else ""))
        print(f"For the changelog entry: imported from {self.rules['incubator']} "
              + (f"{self.last[:7]}..{self.commit[:7]}" if self.last else self.commit[:7]) + ".")

    def to_incubator(self):
        """Write z-sdlc's own changes (bundle code it's ahead on, newer skills and process docs) into the
        incubator's working tree, for a person to commit there with the incubator's CI."""
        writes = [(f"{self.source}/{rel}", how, self.tree_dir / rel) for rel, how in self.ahead]
        writes += [(theirs, "changed", self.root / ours) for ours, theirs in self.newer_mirrors]
        if not writes:
            print("\nNothing for the incubator: it has every z-sdlc change.")
            return
        head = git(self.incubator, "rev-parse", "HEAD").strip()
        if head != self.commit:
            raise Refused(f"the incubator's checkout is at {head[:7]}, not {self.commit[:7]}: check out the commit you "
                          "imported first")
        dirty = git(self.incubator, "status", "--porcelain", "--", *(path for path, _, _ in writes)).strip()
        if dirty:
            raise Refused("the incubator has uncommitted changes in these files:\n  " + dirty.replace("\n", "\n  "))
        print("\nWritten into the incubator's working tree:")
        for path, how, source in writes:
            dest = self.incubator / path
            if how == "removed":
                dest.unlink(missing_ok=True)
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(source.read_bytes())
                dest.chmod(0o755 if source.stat().st_mode & 0o100 else 0o644)
            print(f"  {how:<8} {path}")
        print("Commit them in the incubator with its changelog entry, and let its CI pass; the next report shows them "
              "in sync.")

    # ---- the proof
    def result(self):
        """The bundle code as this import leaves it: the incubator's, with z-sdlc's own changes kept."""
        files = dict(self.tree)
        for rel, how in self.ahead:
            if how == "removed":
                files.pop(rel, None)
            else:
                path = self.tree_dir / rel
                files[rel] = (path.read_bytes(), "100755" if path.stat().st_mode & 0o100 else "100644")
        return files

    def install(self, project):
        """What sdlc-initialize and sdlc-migrate do: the bundle code, then any absent seed."""
        to = project / self.tree_to
        for rel, (data, mode) in self.result().items():
            dest = to / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            dest.chmod(0o755 if mode == "100755" else 0o644)
        seeded = []
        for rel in self.files_under(self.seed_dir):
            dest = project / self.tree_to / rel
            if not dest.exists():
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(self.seed_dir / rel, dest)
                seeded.append(rel)
        return seeded

    @staticmethod
    def run(cmd, cwd):
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
        return r.returncode, (r.stdout + r.stderr).strip()

    def prove(self):
        ok = True
        with tempfile.TemporaryDirectory(prefix="import-factory-") as tmp:
            tmp = pathlib.Path(tmp)
            policy = [sys.executable, f"{self.tree_to}/workflow_policy.py", ".github/workflows"]
            render = shlex.split(self.render) if self.render else None

            print(f"\nProof 1: the incubator at {self.commit[:7]} takes the bundle without changing")
            inc = tmp / "incubator"
            git(tmp, "clone", "-q", "--no-local", str(self.incubator.resolve()), str(inc))
            git(inc, "checkout", "-q", "--detach", self.commit)
            seeded = self.install(inc)
            if render:
                code, out = self.run(render, inc)
                ok &= self.step("render", code == 0, out)
            # The only changes allowed are z-sdlc's own, which the incubator hasn't taken yet (and their render).
            expected = {f"{self.source}/{rel}" for rel, _ in self.ahead}
            status = [line[3:] for line in git(inc, "status", "--porcelain", "--untracked-files=all").splitlines()]
            unexpected = [path for path in status if path not in expected
                          and not (expected and path.startswith(".github/workflows/"))]
            label = "nothing changed" if not status else f"only z-sdlc's own changes ({len(status)} files)"
            ok &= self.step(label, not unexpected and not seeded,
                            "\n".join(unexpected) or ("seeded: " + ", ".join(seeded) if seeded else ""))
            code, out = self.run(policy, inc)
            ok &= self.step("workflow policy", code == 0, out)
            # The incubator's own settings, which a seed never changes: a test that needs a setting only the seed has
            # fails here, as it would in any project that installed an older seed.
            ok &= self.tests(inc)

            print("\nProof 2: an empty project with an Enablement-shaped CODEOWNERS")
            empty = tmp / "empty"
            (empty / ".github/workflows").mkdir(parents=True)
            git(empty, "init", "-q", "-b", "main")
            (empty / ".github/CODEOWNERS").write_text(PROOF_CODEOWNERS)
            seeded = self.install(empty)
            print(f"  seeded   {len(seeded)} files")
            if render:
                code, out = self.run(render, empty)
                rendered = len(list((empty / ".github/workflows").glob("factory-*.yml")))
                templates = sum(1 for rel in self.result() if rel.startswith("templates/") and rel.endswith(".yml"))
                ok &= self.step(f"render ({rendered} of {templates} templates)", code == 0 and rendered == templates > 0,
                                out)
            code, out = self.run(policy, empty)
            ok &= self.step("workflow policy", code == 0, out)
            ok &= self.tests(empty)
        return ok

    def tests(self, project):
        code, out = self.run([sys.executable, "-m", "unittest", "discover", "-s", f"{self.tree_to}/tests"], project)
        summary = next((l for l in reversed(out.splitlines()) if l.startswith(("OK", "FAILED", "Ran "))), "")
        return self.step(f"tests: {summary}", code == 0, out)

    @staticmethod
    def step(label, passed, out):
        print(f"  {'pass' if passed else 'FAIL':<8} {label}")
        if not passed and out:
            print("    " + "\n    ".join(out.splitlines()[-15:]))
        return passed


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("incubator", help="a local clone of the incubator (quantile)")
    ap.add_argument("--commit", default="HEAD", help="the incubator commit to import (default HEAD)")
    ap.add_argument("--apply", action="store_true", help="write the bundle code and record the import")
    ap.add_argument("--accept", action="store_true", help="with --apply: allow files added to or removed from the bundle")
    ap.add_argument("--to-incubator", action="store_true",
                    help="write z-sdlc's own changes into the incubator's working tree, to commit there")
    ap.add_argument("--prove", action="store_true", help="install the result into the incubator and an empty project")
    ap.add_argument("--root", default=str(ROOT), help=argparse.SUPPRESS)
    ap.add_argument("--rules", default=str(RULES), help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    try:
        imp = Import(args.root, args.rules, args.incubator, args.commit).analyze()
        imp.report()
        if args.apply:
            imp.apply(args.accept)
        if args.to_incubator:
            imp.to_incubator()
        proved = imp.prove() if args.prove else True
    except Stop as e:
        print(f"import_factory: {e}", file=sys.stderr)
        return 2
    except Refused as e:
        print(f"\nNot applied: {e}")
        return 1
    # Accepted and applied, a [check, then --accept] item is settled; the others still need a person.
    open_needs = [what for what, _ in imp.needs if not (args.apply and args.accept and what == ACCEPT)]
    return 0 if proved and not open_needs else 1


if __name__ == "__main__":
    sys.exit(main())
