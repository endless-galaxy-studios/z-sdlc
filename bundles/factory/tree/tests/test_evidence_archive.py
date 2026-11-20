"""host/evidence_archive.py: the archive's pull of the factory's browser evidence (process/factory.md D6 rule 7),
against a stand-in for GitHub's API. It files a run's evidence where the PR said it would be, takes it only from the
factory's own runs on the default branch, and never overwrites. The live API isn't exercised here."""

import io
import json
import pathlib
import sys
import tempfile
import unittest
import zipfile

FACTORY = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FACTORY / "host"))
sys.path.insert(0, str(FACTORY))
import evidence_archive as ea  # noqa: E402
import implement_guard as guard  # noqa: E402

REPO = "acme/app"


def zipped(name, data):
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        z.writestr(name, data)
    return out.getvalue()


class FakeAPI:
    def __init__(self, runs, artifacts, files):
        self.calls = []
        self.routes = {f"/repos/{REPO}": json.dumps({"default_branch": "main"}).encode()}
        for wf in ea.WORKFLOWS:
            mine = [r for r in runs if r["path"].endswith(wf)]
            self.routes[f"/repos/{REPO}/actions/workflows/{wf}/runs"] = json.dumps({"workflow_runs": mine}).encode()
        for run_id, arts in artifacts.items():
            self.routes[f"/repos/{REPO}/actions/runs/{run_id}/artifacts"] = json.dumps({"artifacts": arts}).encode()
        for art_id, body in files.items():
            self.routes[f"/repos/{REPO}/actions/artifacts/{art_id}/zip"] = body

    def __call__(self, path):
        self.calls.append(path)
        key = path.split("?")[0]
        if key.endswith("/runs") and "&page=" in path and not path.endswith("&page=1"):
            return 200, json.dumps({"workflow_runs": self.pages.get((key, path.rsplit("=", 1)[1]), [])}).encode()
        return (200, self.routes[key]) if key in self.routes else (404, b"")

    pages = {}


def run(run_id, wf="factory-implement.yml", branch="main", repo=REPO, event="workflow_dispatch", conclusion="success"):
    return {"id": run_id, "path": f".github/workflows/{wf}", "head_branch": branch, "event": event,
            "conclusion": conclusion, "head_repository": {"full_name": repo}}


def record(issue, run_id):
    return json.dumps({"files": [], "dropped": [], "report": True, "video": True, "trace": False,
                       "issue": issue, "run": run_id}).encode()


class Pull(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def api(self, rec=None):
        arts = {7: [{"id": 1, "name": "evidence.json"}, {"id": 2, "name": "evidence-report.html"},
                    {"id": 3, "name": "evidence-video.webm"}, {"id": 4, "name": "other.txt"}]}
        files = {1: rec or record(42, 7), 2: b"<!doctype html>report", 3: zipped("evidence-video.webm", b"\x1a\x45video")}
        return FakeAPI([run(7)], arts, files)

    def test_a_run_lands_where_the_pr_said(self):
        api = self.api()
        written = ea.pull_run(api, REPO, run(7), self.root)
        where = self.root / "app" / "42" / "7"
        self.assertEqual(sorted(pathlib.Path(p).name for p in written),
                         ["evidence-report.html", "evidence-video.webm", "evidence.json"])
        self.assertEqual((where / "evidence-report.html").read_bytes(), b"<!doctype html>report")
        self.assertEqual((where / "evidence-video.webm").read_bytes(), b"\x1a\x45video")  # a zipped download, unwrapped
        self.assertFalse(any("/4/" in c for c in api.calls))  # not an evidence file: never downloaded
        # The writer names the same path: <archive>/<repository name>/<issue>/<run id>/.
        rec = json.dumps({"files": [{"file": "a.png", "step": 1, "shows": "x", "bug": False, "kind": "screenshot"}],
                          "dropped": [], "report": True, "video": False, "trace": False, "issue": 42, "run": 7})
        lines = guard.evidence_lines(rec, {"report": "2"}, f"https://github.com/{REPO}/actions/runs/7", "42",
                                     str(self.root))
        self.assertIn(f"`{where}/`", "\n".join(lines))

    def test_never_twice(self):
        ea.pull_run(self.api(), REPO, run(7), self.root)
        again = self.api()
        self.assertEqual(ea.pull_run(again, REPO, run(7), self.root), [])
        self.assertFalse(any(c.endswith("/2/zip") for c in again.calls))

    def test_a_record_that_doesnt_name_this_run_is_skipped(self):
        for rec in (record(42, 8), json.dumps({"files": []}).encode(), record(0, 7), record(True, 7)):
            with self.subTest(rec=rec[:50]), self.assertRaises(ea.Skip):
                ea.pull_run(self.api(rec), REPO, run(7), self.root)
        self.assertFalse(any(self.root.iterdir()))

    def test_only_the_factorys_own_runs(self):
        implement = [run(1), run(2, branch="feature"), dict(run(3), path=".github/workflows/other.yml"),
                     run(5, repo="someone/fork"),  # a fork's PR from a branch named main
                     run(6, event="pull_request"), run(7, event="issues"), run(8, conclusion="skipped")]
        api = FakeAPI([run(4, "factory-revise.yml"), run(9, "factory-revise.yml", event="issues")], {}, {})
        api.routes[f"/repos/{REPO}/actions/workflows/factory-implement.yml/runs"] = json.dumps(
            {"workflow_runs": implement}).encode()
        self.assertEqual([r["id"] for r in ea.runs(api, REPO, 14)], [1, 7, 4])

    def test_every_page(self):
        first = [run(i) for i in range(100)]
        api = FakeAPI([], {}, {})
        api.routes[f"/repos/{REPO}/actions/workflows/factory-implement.yml/runs"] = json.dumps(
            {"workflow_runs": first}).encode()
        api.pages = {(f"/repos/{REPO}/actions/workflows/factory-implement.yml/runs", "2"): [run(100), run(101)]}
        self.assertEqual(len(list(ea.runs(api, REPO, 90))), 102)

    def test_a_record_of_the_wrong_shape_is_skipped(self):
        with self.assertRaises(ea.Skip):
            ea.pull_run(self.api(b"[]"), REPO, run(7), self.root)

    def test_a_run_once_done_is_never_asked_about_again(self):
        config = self.root / "archive.json"
        token = self.root / "token"
        token.write_text("t\n")
        archive = self.root / "archive"
        archive.mkdir()
        config.write_text(json.dumps({"root": str(archive), "token_file": str(token), "repos": [REPO]}))
        api = self.api()
        api.routes[f"/repos/{REPO}/actions/workflows/factory-implement.yml/runs"] = json.dumps(
            {"workflow_runs": [run(7), run(8)]}).encode()
        api.routes[f"/repos/{REPO}/actions/runs/8/artifacts"] = json.dumps({"artifacts": []}).encode()
        old_make, old_argv = ea.make_api, sys.argv
        ea.make_api = lambda tok: api
        try:
            sys.argv = ["evidence_archive.py", str(config)]
            self.assertEqual(ea.main(), 0)
            self.assertEqual((archive / ".seen-runs").read_text().split(), [f"{REPO}#7", f"{REPO}#8"])
            api.calls.clear()
            self.assertEqual(ea.main(), 0)
            self.assertFalse([c for c in api.calls if "/actions/runs/" in c])
        finally:
            ea.make_api, sys.argv = old_make, old_argv

    def test_unwrap(self):
        self.assertEqual(ea.unwrap("evidence-report.html", b"<html>"), b"<html>")
        self.assertEqual(ea.unwrap("evidence-report.html", zipped("evidence-report.html", b"<html>")), b"<html>")
        # A trace is itself a zip: unwrapped only from a wrapper holding exactly it.
        trace = zipped("trace.trace", b"x")
        self.assertEqual(ea.unwrap("evidence-trace.zip", trace), trace)
        self.assertEqual(ea.unwrap("evidence-trace.zip", zipped("evidence-trace.zip", trace)), trace)

    def test_dry_run_writes_nothing(self):
        planned = ea.pull_run(self.api(), REPO, run(7), self.root, dry_run=True)
        self.assertTrue(planned)
        self.assertFalse(any(self.root.iterdir()))


class Setup(unittest.TestCase):
    def test_the_installer_keeps_the_token_off_screen_and_the_user_unprivileged(self):
        text = (FACTORY / "host" / "setup-archive.sh").read_text()
        self.assertIn('read -rsp "Read-only Actions token', text)
        self.assertIn("chmod 640 /etc/factory-evidence/token", text)
        self.assertIn("ReadWritePaths=$root", text)
        self.assertIn("NoNewPrivileges=yes", text)


if __name__ == "__main__":
    unittest.main()
