"""Tests for factory_branch.sh: reading a factory branch in an agent job (fetch, check, switch) and
fast-forwarding it in a writer job (push). Fixture repositories stand in for GitHub; push reaches the
local remote through a url.insteadOf rewrite of the https URL it builds."""

import os
import pathlib
import subprocess
import tempfile
import unittest

FACTORY = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = FACTORY / "factory_branch.sh"
IDENTITY = ["-c", "user.name=t", "-c", "user.email=t@e"]


def git(*args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def write(root, files):
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)


class FactoryBranch(unittest.TestCase):
    BRANCH = "factory/7-impl"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        # main: CODEOWNERS (the real file's shape) and agent configuration.
        src = self.root / "src"
        src.mkdir()
        git("init", "-q", "-b", "main", cwd=src)
        write(src, {
            ".github/CODEOWNERS": "/.github/ @cd\n.claude/ @cd\nCLAUDE.md @cd\n/ops/sdlc/ @cd\n/ops/sdlc/disciplines/*.md\n",
            ".claude/settings.json": '{"v": "old"}\n', "CLAUDE.md": "old\n", "api/a.py": "a\n",
            ".github/factory/services.json": '{"services": []}\n', ".github/factory/services.py": "old = 1\n",
            "docs/current_work/planning/d1_x_plan.md": "plan\n"})
        git("add", "-A", cwd=src)
        git(*IDENTITY, "commit", "-q", "-m", "base", cwd=src)
        # The factory branch, off this base.
        git("checkout", "-q", "-b", self.BRANCH, cwd=src)
        write(src, {"api/b.py": "b\n"})
        git("add", "-A", cwd=src)
        git(*IDENTITY, "commit", "-q", "-m", "work", cwd=src)
        self.head = self.work = git("rev-parse", "HEAD", cwd=src)
        # main moves on: newer agent configuration, and a new skill.
        git("checkout", "-q", "main", cwd=src)
        write(src, {".claude/settings.json": '{"v": "new"}\n', ".claude/skills/s/SKILL.md": "skill\n",
                    ".github/factory/services.json": '{"services": ["new"]}\n', ".github/factory/services.py": "new = 1\n"})
        git("add", "-A", cwd=src)
        git(*IDENTITY, "commit", "-q", "-m", "main moves", cwd=src)
        self.remote = self.root / "remote.git"
        git("clone", "-q", "--bare", str(src), str(self.remote), cwd=self.root)
        self.src = src
        # The job's checkout of main, with origin still set (the fetch happens before it is removed).
        self.ws = self.root / "ws"
        git("clone", "-q", "--no-local", "--single-branch", "-b", "main", str(self.remote), str(self.ws), cwd=self.root)
        self.temp = self.root / "runner-temp"
        self.temp.mkdir()
        self.env = {**os.environ, "READ_TOKEN": "read-token", "RUNNER_TEMP": str(self.temp)}

    def tearDown(self):
        self.tmp.cleanup()

    def run_script(self, *args, env=None):
        return subprocess.run(["bash", str(SCRIPT), *args], cwd=self.ws, env=env or self.env,
                              capture_output=True, text=True)

    def add_to_branch(self, files):
        """Someone pushes one more commit to the branch, on top of the factory's work."""
        git("checkout", "-q", "-B", self.BRANCH, self.work, cwd=self.src)
        write(self.src, files)
        git("add", "-A", cwd=self.src)
        git(*IDENTITY, "commit", "-q", "-m", "more", cwd=self.src)
        git("push", "-q", "--force", str(self.remote), self.BRANCH, cwd=self.src)
        self.head = git("rev-parse", "HEAD", cwd=self.src)


class Fetch(FactoryBranch):
    def test_prints_the_branch_head_and_keeps_no_fetch_head(self):
        r = self.run_script("fetch", self.BRANCH)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), self.head)
        self.assertFalse((self.ws / ".git/FETCH_HEAD").exists())
        # Fetched, not checked out: the workspace stays on main.
        self.assertEqual(git("rev-parse", "--abbrev-ref", "HEAD", cwd=self.ws), "main")


class Check(FactoryBranch):
    def test_a_clean_branch_passes_silently(self):
        r = self.run_script("check", self.BRANCH, self.head, "code")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(r.stdout, "")

    def test_a_moved_branch_is_refused(self):
        r = self.run_script("check", self.BRANCH, "0" * 40, "code")
        self.assertEqual(r.returncode, 1)
        self.assertIn(f"::error::{self.BRANCH} is at {self.head}, not {'0' * 40}", r.stdout)

    def test_owned_paths_and_agent_configuration_are_refused(self):
        for path in (".claude/settings.json", "api/CLAUDE.md", ".github/workflows/x.yml", "ops/sdlc/process/p.md",
                     "web/.mcp.json"):
            with self.subTest(path=path):
                self.add_to_branch({path: "changed\n"})
                r = self.run_script("check", self.BRANCH, self.head, "code")
                self.assertEqual(r.returncode, 1, r.stdout)
                self.assertIn(path, r.stdout.splitlines())
                self.assertIn("changes paths this stage may not", r.stdout)

    def test_unowned_sdlc_hygiene_passes(self):
        self.add_to_branch({"ops/sdlc/disciplines/testing.md": "entry\n"})
        self.assertEqual(self.run_script("check", self.BRANCH, self.head, "code").returncode, 0)

    def test_a_document_branch_may_change_only_document_paths(self):
        self.add_to_branch({"docs/current_work/planning/d1_x_plan.md": "revised\n"})
        # The branch's first commit changed api/b.py, which a document stage may not.
        r = self.run_script("check", self.BRANCH, self.head, "doc")
        self.assertEqual(r.returncode, 1)
        self.assertIn("api/b.py", r.stdout.splitlines())
        self.assertEqual(self.run_script("check", self.BRANCH, self.head, "code").returncode, 0)

    def test_unknown_kind(self):
        self.assertEqual(self.run_script("check", self.BRANCH, self.head, "other").returncode, 1)


class Switch(FactoryBranch):
    def test_main_agent_configuration_over_the_branch_hidden_from_git(self):
        self.assertEqual(self.run_script("check", self.BRANCH, self.head, "code").returncode, 0)
        r = self.run_script("switch", self.head)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(git("rev-parse", "HEAD", cwd=self.ws), self.head)
        self.assertTrue((self.ws / "api/b.py").exists())
        # main's copies, not the branch's.
        self.assertEqual((self.ws / ".claude/settings.json").read_text(), '{"v": "new"}\n')
        self.assertEqual((self.ws / ".claude/skills/s/SKILL.md").read_text(), "skill\n")
        # The services list the MCP step reads from the working tree is main's current one too.
        self.assertEqual((self.ws / ".github/factory/services.json").read_text(), '{"services": ["new"]}\n')
        self.assertEqual((self.ws / ".github/factory/services.py").read_text(), "new = 1\n")
        # Nothing of it shows as a change or can be committed.
        self.assertEqual(git("status", "--porcelain", cwd=self.ws), "")
        self.assertIn("S .claude/settings.json", git("ls-files", "-v", ".claude", cwd=self.ws))


class Push(FactoryBranch):
    def setUp(self):
        super().setUp()
        # The agent's commit on top of the branch head, as the publish job has it after the guard.
        self.run_script("fetch", self.BRANCH)
        git("checkout", "-q", "--detach", self.head, cwd=self.ws)
        write(self.ws, {"api/c.py": "c\n"})
        git("add", "-A", cwd=self.ws)
        git(*IDENTITY, "commit", "-q", "-m", "revision", cwd=self.ws)
        self.new = git("rev-parse", "HEAD", cwd=self.ws)
        (self.temp / "out").mkdir()
        (self.temp / "out/head").write_text(self.new + "\n")
        # The https URL the script builds, rewritten to the fixture remote.
        url = "https://x-access-token:app-token@github.com/o/r.git"
        gitconfig = self.root / "gitconfig"
        gitconfig.write_text(f'[url "{self.remote}"]\n\tinsteadOf = {url}\n')
        self.env.update(GH_TOKEN="app-token", GH_REPO="o/r", GIT_CONFIG_GLOBAL=str(gitconfig))

    def remote_head(self):
        return git("rev-parse", f"refs/heads/{self.BRANCH}", cwd=self.remote)

    def test_fast_forwards_from_the_base(self):
        r = self.run_script("push", self.BRANCH, self.head)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.remote_head(), self.new)

    def test_refuses_a_branch_that_moved(self):
        self.add_to_branch({"api/d.py": "d\n"})
        moved = self.remote_head()
        r = self.run_script("push", self.BRANCH, self.work)
        self.assertEqual(r.returncode, 1)
        self.assertIn("moved since this run started", r.stdout)
        self.assertEqual(self.remote_head(), moved)


class Usage(FactoryBranch):
    def test_unknown_command(self):
        self.assertEqual(self.run_script("nope").returncode, 2)


if __name__ == "__main__":
    unittest.main()
