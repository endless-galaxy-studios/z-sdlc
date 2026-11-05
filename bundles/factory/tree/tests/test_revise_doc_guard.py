"""Tests for revise_doc_guard.py: a spec or plan revision publishes only what a planning run could, answers
every request, and renders both the revision comment and the PR description again. The fixture repository
uses test_implement_guard's CODEOWNERS and operations catalog, not the project's."""

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

FACTORY = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FACTORY))
sys.path.insert(0, str(FACTORY / "tests"))

import test_implement_guard as tig  # noqa: E402

SCRIPT = FACTORY / "revise_doc_guard.py"
DOC = "docs/current_work/sdlc-lite/d15_x_plan.md"


def git(*args, cwd):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@e", "-c", "gc.auto=0", "-c", "maintenance.auto=false",
                           *args], cwd=cwd, check=True,
                          capture_output=True, text=True).stdout.strip()


def result(**kw):
    r = tig.Result().plan(document=DOC)
    r.update(summary="Narrowed the scope to the market views, as asked.",
             responses=[{"request": "Drop the web change", "action": "done", "note": "Removed phase 3."},
                        {"request": "Use a new table", "action": "needs-your-call", "note": "That is a schema change: approve it?"}],
             verification=["Plan review round 2: clean"], follow_ups=[])
    r["notes"] = "round 2"
    r.update(kw)
    return r


class ReviseDocGuard(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        root = pathlib.Path(self.tmp.name)
        self.src = root / "src"
        (self.src / ".github/factory/production").mkdir(parents=True)
        git("init", "-q", "-b", "main", cwd=self.src)
        (self.src / ".github/CODEOWNERS").write_text(tig.FIXTURE_CODEOWNERS)
        (self.src / ".github/factory/production/ops.json").write_text(tig.FIXTURE_CATALOG)
        (self.src / "README.md").write_text("hi\n")
        git("add", "-A", cwd=self.src)
        git("commit", "-q", "-m", "base", cwd=self.src)
        self.merge_base = git("rev-parse", "HEAD", cwd=self.src)
        # The plan PR: the factory's first plan commit.
        git("checkout", "-q", "-b", "factory/15-plan", cwd=self.src)
        self.write(DOC, "# Plan v1\n")
        self.write("docs/_index.md", "| D15 | x | Draft |\n")
        self.commit("plan")
        self.base = git("rev-parse", "HEAD", cwd=self.src)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, path, text):
        f = self.src / path
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text)

    def commit(self, msg):
        git("add", "-A", cwd=self.src)
        git("commit", "-q", "-m", msg, cwd=self.src)

    def run_guard(self, res, revision="2", limit="5"):
        root = pathlib.Path(tempfile.mkdtemp(dir=self.tmp.name))
        bundle = root / "revise.bundle"
        git("bundle", "create", "-q", str(bundle), f"{self.base}..HEAD", cwd=self.src)
        dst = root / "dst"
        git("clone", "-q", "--no-local", str(self.src), str(dst), cwd=root)
        git("checkout", "-q", "main", cwd=dst)
        (root / "result.json").write_text(json.dumps(res))
        out = subprocess.run([sys.executable, "-I", str(SCRIPT), str(bundle), self.base, str(root / "result.json"), "15",
                              "https://run", str(root / "out"), "plan", self.merge_base],
                             cwd=dst, capture_output=True, text=True,
                             env=dict(os.environ, REVISION=revision, REVISION_LIMIT=limit))
        return out, root / "out"

    def revise(self, path=DOC, text="# Plan v2\n"):
        self.write(path, text)
        self.commit("revise(#16): narrow scope")

    def test_accepts_and_renders(self):
        self.revise()
        out, o = self.run_guard(result())
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        comment = (o / "comment.md").read_text()
        self.assertTrue(comment.startswith("<!-- factory-revise: 2 -->"))
        self.assertIn("**Revision 2 of 5:**", comment)
        self.assertIn("Needs your call", comment)
        body = (o / "pr-body.md").read_text()
        self.assertTrue(body.startswith("<!-- factory-pr: v1 plan -->"))
        self.assertIn("Refs #15", body)
        self.assertEqual((o / "head").read_text().strip(), git("rev-parse", "HEAD", cwd=self.src))

    def refused(self, res, why, **kw):
        out, _ = self.run_guard(res, **kw)
        self.assertEqual(out.returncode, 1, out.stdout + out.stderr)
        self.assertIn(why, out.stdout)

    def test_refuses_code(self):
        self.revise("api/x.py", "x = 1\n")
        self.refused(result(), "may only change")

    def test_refuses_an_owned_sdlc_file(self):
        self.revise("ops/sdlc/knowledge/README.md", "x\n")
        self.refused(result(), "CODEOWNERS")

    def test_refuses_knowledge_that_governs_agents_by_name(self):
        self.revise("ops/sdlc/knowledge/agent-context-map.yaml", "x: 1\n")
        self.refused(result(), "agent or gate configuration")

    def test_refuses_another_document(self):
        self.revise()
        self.refused(result(document="docs/current_work/sdlc-lite/d99_other_plan.md"), "isn't a document this PR")

    def test_refuses_nothing_to_publish(self):
        self.revise()
        self.refused(result(status="failed"), "nothing to publish")
        self.refused(result(status="done"), "nothing to publish")

    def test_planning_rules_apply(self):
        self.revise()
        self.refused(result(status="escalated"), "no critical or major finding")
        self.refused(result(responses=[]), "a response to each request")
        self.refused(result(summary="key ghp_" + "a" * 30), "credential")

    def test_revision_range(self):
        self.revise()
        self.refused(result(), "outside 1..5", revision="6")

    def test_a_project_without_a_production_tier_revises_plans(self):
        # The guard runs in a checkout of main, so main has no catalog.
        git("checkout", "-q", "main", cwd=self.src)
        git("rm", "-q", ".github/factory/production/ops.json", cwd=self.src)
        git("commit", "-q", "-m", "no production tier", cwd=self.src)
        git("checkout", "-q", "factory/15-plan", cwd=self.src)
        self.revise()
        out, _ = self.run_guard(result())
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.revise(text="# Plan v3\n\n### Phase 1: A\n\n### Gate G1: Look at it\n\n### Phase 2: B\n")
        self.refused(result(), "no production tier")


if __name__ == "__main__":
    unittest.main()
