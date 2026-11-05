"""This project's CODEOWNERS against the factory's publish guard (z-sdlc process/factory.md, Enablement step 9):
what agents may never change, what they may write, and the SDLC changelog's real publish path. The path lists
are this project's; edit them with its CODEOWNERS. Run by CI: python -m unittest discover -s .github/factory/tests"""

import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest

FACTORY = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FACTORY))
import implement_guard as guard  # noqa: E402

PATH = FACTORY.parent / "CODEOWNERS"
CODEOWNERS = PATH.read_text() if PATH.exists() else ""
# What the stack profile's tools load just because it exists (z-sdlc process/factory.md, § Stack Profiles, What
# CODEOWNERS must cover): sample paths in the project's two directories (factory.json's stack), present or not.
NODE_FILES = ["package.json", ".npmrc", "eslint.config.js", "tsconfig.json", "tsconfig.app.json", "vite.config.ts",
              "vitest.config.ts", "postcss.config.js", ".postcssrc", "babel.config.js", ".babelrc"]
# Each profile's package manager: npm reads its own lockfile, pnpm its own, its workspace file and .pnpmfile.cjs.
PACKAGE_MANAGER_FILES = {"python-node": ["package-lock.json"],
                         "dotnet-node": ["pnpm-lock.yaml", "pnpm-workspace.yaml", ".pnpmfile.cjs"],
                         "python-uv-node": ["pnpm-lock.yaml", "pnpm-workspace.yaml", ".pnpmfile.cjs"]}
PROFILE_FILES = {
    "python-node": ["requirements.txt", "requirements-dev.txt", "pyproject.toml", "setup.py", "setup.cfg", "pytest.ini",
                    ".pytest.ini", "pytest.toml", ".pytest.toml", "tox.ini", "conftest.py", "tests/conftest.py",
                    "sitecustomize.py", "hatch.toml", "hatch_build.py"],
    # Every uv project, not only stack.python's (the profile installs and checks each top-level one): add theirs.
    "python-uv-node": ["pyproject.toml", "uv.lock", "uv.toml", ".python-version", ".python-versions", "setup.py",
                       "setup.cfg", "pytest.ini", ".pytest.ini", "pytest.toml", ".pytest.toml", "tox.ini",
                       "conftest.py", "tests/conftest.py", "sitecustomize.py", "hatch.toml", "hatch_build.py",
                       "ruff.toml", ".ruff.toml", "mypy.ini", ".mypy.ini", ".coveragerc", "alembic.ini"],
    "dotnet-node": ["App.csproj", "src/App/App.csproj", "src/App/App.csproj.user", "Directory.Build.props",
                    "Directory.Build.targets",
                    "src/Directory.Build.rsp", "Directory.Packages.props", "Directory.Solution.props",
                    "Directory.Solution.targets", "build/common.targets", "App.sln", "App.slnx", "App.slnf", "global.json",
                    "dotnet-tools.json", "nuget.config", "NuGet.config", "NuGet.Config", ".config/dotnet-tools.json", "tests/test.runsettings",
                    "tests/xunit.runner.json", ".editorconfig", "src/.globalconfig"],
}


# A project may track files with Git LFS, and CI's checkout leaves them as pointers: a local clone would make
# git-lfs fetch objects that aren't there. These tests never read LFS content.
GIT_ENV = {**os.environ, "GIT_LFS_SKIP_SMUDGE": "1"}


def run(*args, cwd):
    subprocess.run(args, cwd=cwd, check=True, capture_output=True, env=GIT_ENV)


class CodeownersPaths(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # The guard refuses an empty file (it fails closed), so these fail until .github/CODEOWNERS exists.
        cls.patterns = guard.codeowners_patterns(CODEOWNERS)

    def test_protected(self):
        # Enablement's minimum. Add this project's test and build configuration (what CI's checks load).
        for path in [".github/workflows/ci.yml", ".github/CODEOWNERS", ".github/factory/implement_guard.py",
                     ".claude/settings.json", ".claude/skills/sdlc-implement/SKILL.md", "CLAUDE.md", "docs/CLAUDE.md",
                     ".mcp.json", "ops/sdlc/process/review-fix-loop.md"]:
            self.assertIsNotNone(guard.protected(path, self.patterns), path)

    def test_other_agents_and_tools_configuration(self):
        # What other agents, editors and environment tools load on CD's machine just because it exists.
        for path in ["AGENTS.md", "api/AGENTS.md", "GEMINI.md", ".codex/config.toml", ".gemini/settings.json",
                     ".cursor/rules/x.mdc", ".vscode/tasks.json", ".devcontainer/devcontainer.json", ".envrc",
                     ".gitattributes", "mise.toml", ".tool-versions"]:
            self.assertIsNotNone(guard.protected(path, self.patterns), path)

    def test_any_case(self):
        # A case-insensitive checkout (macOS) reads .Claude/ as .claude/; the guard matches owned lines in any case.
        for path in ["Claude.md", ".Claude/settings.local.json", ".GitHub/workflows/x.yml", "docs/claude.MD"]:
            self.assertIsNotNone(guard.protected(path, self.patterns), path)

    def test_github_owns_every_casing_agents_load(self):
        # GitHub matches CODEOWNERS case-sensitively, the guard doesn't: a casing CODEOWNERS doesn't list gets no
        # code owner on a person's PR. So list each casing the tools load, early and again after the owner-less
        # lines (last match wins). Add the casings your own tools load.
        names = ["CLAUDE.md", "claude.md", "Claude.md", "CLAUDE.local.md", "claude.local.md", "Claude.local.md",
                 "AGENTS.md", "agents.md", "Agents.md", "GEMINI.md"]
        for path in names + ["docs/" + n for n in names] + ["ops/sdlc/disciplines/" + n for n in names]:
            self.assertIsNotNone(guard.owner_on_github(path, self.patterns), path)

    def test_agent_files_stay_owned_under_the_owner_less_lines(self):
        # Last match wins: CLAUDE.md, CLAUDE.local.md and AGENTS.md are owned again after the owner-less lines.
        for path in ["ops/sdlc/disciplines/CLAUDE.md", "ops/sdlc/disciplines/CLAUDE.local.md",
                     "ops/sdlc/disciplines/AGENTS.md"]:
            self.assertIsNotNone(guard.protected(path, self.patterns), path)

    def test_the_profiles_build_files(self):
        # A revise run installs a factory branch's dependencies outside the sandbox, and CI builds a factory PR.
        stack = json.loads((FACTORY / "factory.json").read_text())["stack"]
        paths = [os.path.normpath(f"{stack['python']}/{p}") for p in PROFILE_FILES.get(stack["profile"], [])]
        paths += [os.path.normpath(f"{stack['node']}/{p}")
                  for p in NODE_FILES + PACKAGE_MANAGER_FILES.get(stack["profile"], [])]
        for path in paths:
            self.assertIsNotNone(guard.protected(path, self.patterns), path)

    def test_not_protected(self):
        # Add this project's source paths: agents must be able to change them.
        for path in ["README.md", "docs/_index.md", "notCLAUDE.md", "docs/CLAUDE.md.txt",
                     "ops/sdlc/disciplines/testing.md"]:
            self.assertIsNone(guard.protected(path, self.patterns), path)

    def test_owner_less_lines_unown_only_the_files_they_name(self):
        for path in ["ops/sdlc/disciplines/x.md/CLAUDE.md", "ops/sdlc/disciplines/x.md/notes.txt",
                     "ops/sdlc/disciplines/x.md/.claude/settings.json"]:
            self.assertIsNotNone(guard.protected(path, self.patterns), path)

    def test_disciplines_only_in_the_real_file(self):
        for path in ["ops/sdlc/disciplines/README.txt", "ops/sdlc/disciplines/x/y.md", "ops/sdlc/knowledge/README.md",
                     "ops/sdlc/knowledge/provenance_log.md", "ops/sdlc/process/review-fix-loop.md"]:
            self.assertIsNotNone(guard.protected(path, self.patterns), path)

    def test_knowledge_writable_except_what_governs_agents(self):
        # Agent-writable on purpose (SDLC hygiene), with CD's PR review as the control (z-sdlc process/factory.md,
        # Enablement step 9); the files that route or govern agents are owned again. The guard keeps the list.
        for path in ["ops/sdlc/knowledge/x.yaml", "ops/sdlc/knowledge/coding/shell-patterns.yaml"]:
            self.assertIsNone(guard.protected(path, self.patterns), path)
        for path in guard.GOVERNING_KNOWLEDGE:
            self.assertIsNotNone(guard.protected(path, self.patterns), path)

    def test_the_changelog_and_only_it_is_writable(self):
        self.assertIsNone(guard.protected("ops/sdlc/process/sdlc_changelog.md", self.patterns))
        self.assertIsNotNone(guard.protected("ops/sdlc/process/sdlc_changelog.md.bak", self.patterns))
        self.assertIsNotNone(guard.protected("ops/sdlc/process/review-fix-loop.md", self.patterns))


class RealChangelog(unittest.TestCase):
    """The publish path a stage takes to commit to the SDLC changelog, on the real file: a shallow clone of
    this repository (publish checks out the base at depth 1), an entry added the way an agent adds one, the
    bundle, and the guard's commit check with the real CODEOWNERS and each stage's path rules. Nothing is
    pushed. It holds whether or not the changelog is over the blob cap."""

    LOG = "ops/sdlc/process/sdlc_changelog.md"

    def setUp(self):
        root = FACTORY.parents[1]
        if not (root / ".git").exists() or not (root / self.LOG).exists():
            self.skipTest("not in a checkout of this repository")
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dst = pathlib.Path(self.tmp.name) / "dst"
        run("git", "clone", "-q", "--depth", "1", "--no-local", f"file://{root}", str(self.dst), cwd=self.tmp.name)
        run("git", "config", "user.email", "t@example.com", cwd=self.dst)
        run("git", "config", "user.name", "t", cwd=self.dst)
        self.base = self.git("rev-parse", "HEAD")
        log = self.dst / self.LOG
        text = log.read_text()
        first = re.search(r"^## \d{4}-\d{2}-\d{2}:", text, re.M)
        at = first.start() if first else len(text)
        entry = "## 2026-10-11: Smoke entry\n\n**Changes made:**\n\n1. A line.\n\n---\n\n"
        log.write_text(text[:at] + entry + text[at:])
        run("git", "commit", "-q", "-am", "log", cwd=self.dst)
        self.bundle = pathlib.Path(self.tmp.name) / "stage.bundle"
        run("git", "bundle", "create", "-q", str(self.bundle), f"{self.base}..HEAD", cwd=self.dst)
        run("git", "checkout", "-q", "--detach", self.base, cwd=self.dst)

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.dst, check=True, capture_output=True, text=True,
                              env=GIT_ENV).stdout.strip()

    def check(self, allowed):
        cwd = os.getcwd()
        os.chdir(self.dst)
        try:
            return guard.check_commits(str(self.bundle), self.base, guard.codeowners_patterns(CODEOWNERS), allowed)
        finally:
            os.chdir(cwd)

    def test_code_and_document_stages_may_commit_to_it(self):
        for stage, allowed in (("implement", None), ("plan", guard.DOC_STAGE_PATHS)):
            with self.subTest(stage=stage):
                head, paths = self.check(allowed)
                self.assertEqual(paths, [self.LOG])


if __name__ == "__main__":
    unittest.main()
