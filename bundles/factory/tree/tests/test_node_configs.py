"""node_configs.py: the config file each Node tool in a profile's verify loads by name, recorded before the agent
starts and checked before verify runs the tools (process/factory.md, Stack Profiles)."""

import pathlib
import subprocess
import sys
import tempfile
import unittest

FACTORY = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = FACTORY / "node_configs.py"


class NodeConfigs(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        # The checkout's root is the working directory; the node directory is below it.
        self.ws = pathlib.Path(self.tmp.name) / "ws"
        self.web = self.ws / "src" / "web"
        self.web.mkdir(parents=True)

    def add(self, path):
        (self.ws / path).parent.mkdir(parents=True, exist_ok=True)
        (self.ws / path).write_text("export default {}\n")

    def run_script(self, *args):
        return subprocess.run([sys.executable, "-I", str(SCRIPT), *args], capture_output=True, text=True, cwd=self.ws)

    def record(self):
        r = self.run_script("record", "src/web")
        self.assertEqual(r.returncode, 0, r.stderr)
        (self.ws / "verify.conf").write_text("python=.\nnode=src/web\n" + r.stdout)
        return dict(line.split("=", 1) for line in r.stdout.splitlines())

    def check(self, *tools):
        return self.run_script("check", "src/web", "verify.conf", *tools)

    def test_a_project_with_both_vite_and_vitest_configs(self):
        for name in ("eslint.config.js", "vite.config.ts", "vitest.config.ts"):
            self.add(f"src/web/{name}")
        self.assertEqual(self.record(), {"eslint_config": "eslint.config.js", "vite_config": "vite.config.ts",
                                         "vitest_config": "vitest.config.ts", "vitest_workspace": ""})
        self.assertEqual(self.check("eslint", "vite", "vitest").returncode, 0)

    def test_an_added_file_earlier_in_a_tools_order_fails_the_check(self):
        self.add("src/web/vite.config.ts")
        self.add("src/web/eslint.config.ts")
        self.assertEqual(self.record()["vite_config"], "vite.config.ts")
        # Vite tries .js before .ts, and ESLint .js before .ts.
        self.add("src/web/vite.config.js")
        self.add("src/web/eslint.config.js")
        r = self.check("eslint", "vite")
        self.assertEqual(r.returncode, 1)
        self.assertIn("vite would load vite.config.js in src/web, not vite.config.ts, the file it loaded", r.stdout)
        self.assertIn("eslint would load eslint.config.js", r.stdout)
        self.assertIn("Remove it, or leave the change to CD", r.stdout)

    def test_vitest_reads_its_own_name_before_vites(self):
        # Test settings kept in vite.config.ts: an added vitest.config.ts would replace them.
        self.add("src/web/vite.config.ts")
        self.assertEqual(self.record()["vitest_config"], "vite.config.ts")
        self.add("src/web/vitest.config.ts")
        self.assertEqual(self.check("vite").returncode, 0)
        r = self.check("vitest")
        self.assertEqual(r.returncode, 1)
        self.assertIn("vitest would load vitest.config.ts in src/web, not vite.config.ts", r.stdout)

    def test_vitest_and_eslint_search_upward_to_the_checkouts_root(self):
        self.add("src/vitest.config.ts")
        self.add("eslint.config.mjs")
        # Above the checkout's root isn't the run's: it's never searched.
        (self.ws.parent / "vite.config.ts").write_text("")
        got = self.record()
        self.assertEqual((got["vitest_config"], got["eslint_config"], got["vite_config"]),
                         ("../vitest.config.ts", "../../eslint.config.mjs", ""))
        # A nearer one, added since, would win.
        self.add("src/web/vite.config.mts")
        r = self.check("vitest", "vite")
        self.assertEqual(r.returncode, 1)
        self.assertIn("vitest would load vite.config.mts in src/web, not ../vitest.config.ts", r.stdout)
        self.assertIn("vite would load vite.config.mts in src/web, and loaded none when the job began", r.stdout)

    def test_a_workspace_file_beside_vitests_config(self):
        self.add("src/web/vitest.config.ts")
        self.assertEqual(self.record()["vitest_workspace"], "")
        self.add("src/web/vitest.projects.json")
        r = self.check("vitest")
        self.assertEqual(r.returncode, 1)
        self.assertIn("vitest would read vitest.projects.json in src/web to choose its tests, and read none", r.stdout)
        # Only Vitest reads it.
        self.assertEqual(self.check("eslint", "vite").returncode, 0)

    def test_a_config_file_removed_since_fails_too(self):
        self.add("src/web/vite.config.ts")
        self.record()
        (self.web / "vite.config.ts").unlink()
        r = self.check("vite")
        self.assertEqual(r.returncode, 1)
        self.assertIn("vite would load no config file in src/web, not vite.config.ts", r.stdout)

    def test_refusals(self):
        (self.ws / "verify.conf").write_text("python=.\nnode=src/web\n")
        r = self.check("vite")
        self.assertEqual(r.returncode, 2)
        self.assertIn("no eslint_config=, vite_config=, vitest_config=, vitest_workspace= line", r.stderr)
        for bad in ("/abs", "../up", "src/../.."):
            self.assertEqual(self.run_script("record", bad).returncode, 2, bad)
        self.assertEqual(self.run_script("check", "src/web", "verify.conf", "webpack").returncode, 2)
        self.assertEqual(self.run_script("record").returncode, 2)


if __name__ == "__main__":
    unittest.main()
