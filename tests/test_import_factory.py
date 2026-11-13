"""Tests for .claude/skills/zsdlc-import-factory/scripts/import_factory.py against a fixture z-sdlc and a fixture
incubator. The proof (--prove) runs the real bundle's render and tests, so it is checked live, not here.
Run: python3 -m unittest discover -s tests"""
import contextlib
import importlib.util
import io
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / ".claude/skills/zsdlc-import-factory/scripts/import_factory.py"
spec = importlib.util.spec_from_file_location("import_factory", SCRIPT)
imf = importlib.util.module_from_spec(spec)
sys.modules["import_factory"] = imf
spec.loader.exec_module(imf)

SKILL, PROCESS = "skills/sdlc-triage/SKILL.md", "process/factory.md"
MANIFEST = {"bundles": {"factory": {
    "skills": [SKILL], "process": [PROCESS],
    "tree": {"from": "bundles/factory/tree", "to": ".github/factory"},
    "seed": {"from": "bundles/factory/seed", "to": ".github/factory"},
    "render": "python3 .github/factory/render.py", "requires": {"sdlc_root": "ops/sdlc"}}}}
RULES = {"bundle": "factory", "source": ".github/factory",
         "seed": ["factory.json", "README.md"], "excluded": ["production/*", "*__pycache__*"],
         "free_settings": {"factory.json": ["stack.env"]}, "specific": ["acme-only", "/home/"],
         "last_import": {"commit": "", "date": ""}}
FACTORY_JSON = {"app": {"login": "bot"}, "stack": {"profile": "p", "env": {}}}


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@e", *args],
                          check=True, capture_output=True, text=True).stdout.strip()


class ImportFactory(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = pathlib.Path(self.tmp.name)
        self.z, self.inc = base / "z", base / "inc"
        # The incubator, at its first commit.
        self.put(self.inc, ".github/factory/guard.py", "x = 1\n")
        self.put(self.inc, ".github/factory/run.sh", "#!/bin/sh\necho hi\n", mode=0o755)
        self.put(self.inc, ".github/factory/factory.json", json.dumps({**FACTORY_JSON, "stack": {"profile": "p",
                                                                        "env": {"MODEL_DIR": "m"}}}))
        self.put(self.inc, ".github/factory/README.md", "acme notes\n")
        self.put(self.inc, ".github/factory/production/ops.json", "{}\n")
        self.put(self.inc, ".claude/" + SKILL, "triage text\n")
        self.put(self.inc, "ops/sdlc/" + PROCESS, "rules\n")
        git(self.inc.parent, "init", "-q", "-b", "main", str(self.inc))
        self.commit("one")
        # z-sdlc, in sync with it.
        self.put(self.z, "skeleton/manifest.json", json.dumps(MANIFEST))
        self.put(self.z, "bundles/factory/tree/guard.py", "x = 1\n")
        self.put(self.z, "bundles/factory/tree/run.sh", "#!/bin/sh\necho hi\n", mode=0o755)
        self.put(self.z, "bundles/factory/seed/factory.json", json.dumps(FACTORY_JSON))
        self.put(self.z, "bundles/factory/seed/README.md", "generic notes\n")
        self.put(self.z, SKILL, "triage text\n")
        self.put(self.z, PROCESS, "rules\n")
        self.rules = self.z / "import.json"
        self.rules.write_text(json.dumps(RULES))
        # The untracked names file (CLAUDE.md, check 6), with an invented name.
        self.put(self.z, ".claude/private-names.txt", "Hushproject\n")

    def tearDown(self):
        self.tmp.cleanup()

    @staticmethod
    def put(root, rel, text, mode=0o644):
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        path.chmod(mode)

    def commit(self, msg):
        git(self.inc, "add", "-A")
        git(self.inc, "commit", "-q", "-m", msg)
        return git(self.inc, "rev-parse", "HEAD")

    def run_it(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            code = imf.main([str(self.inc), "--root", str(self.z), "--rules", str(self.rules), *args])
        return code, out.getvalue()

    def recorded(self):
        return json.loads(self.rules.read_text())["last_import"]["commit"]

    def test_in_sync_needs_nothing_and_apply_records_the_commit(self):
        code, out = self.run_it()
        self.assertEqual(code, 0, out)
        self.assertIn("in sync", out)
        self.assertIn("Not imported: 2 seeds, 1 excluded", out)
        code, out = self.run_it("--apply")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.recorded(), git(self.inc, "rev-parse", "HEAD"))

    def test_a_changed_file_is_imported_and_the_log_shows_the_commits(self):
        self.run_it("--apply")
        self.put(self.inc, ".github/factory/guard.py", "x = 2\n")
        head = self.commit("fix(factory): the guard")
        code, out = self.run_it()
        self.assertEqual(code, 0, out)
        self.assertIn("changed  guard.py", out)
        self.assertIn("fix(factory): the guard", out)
        self.assertEqual((self.z / "bundles/factory/tree/guard.py").read_text(), "x = 1\n")  # report only
        code, out = self.run_it("--apply")
        self.assertEqual(code, 0, out)
        self.assertEqual((self.z / "bundles/factory/tree/guard.py").read_text(), "x = 2\n")
        self.assertEqual(self.recorded(), head)

    def test_the_executable_bit_is_part_of_a_file(self):
        (self.z / "bundles/factory/tree/run.sh").chmod(0o644)
        code, out = self.run_it("--apply")
        self.assertIn("changed  run.sh", out)
        self.assertTrue((self.z / "bundles/factory/tree/run.sh").stat().st_mode & 0o100)

    def test_a_new_file_needs_accept(self):
        self.put(self.inc, ".github/factory/new_tool.py", "y = 1\n")
        self.commit("feat: a tool")
        code, out = self.run_it("--apply")
        self.assertEqual(code, 1)
        self.assertIn("added    new_tool.py", out)
        self.assertIn("Not applied", out)
        self.assertFalse((self.z / "bundles/factory/tree/new_tool.py").exists())
        self.assertEqual(self.recorded(), "")
        code, out = self.run_it("--apply", "--accept")
        self.assertEqual(code, 0, out)
        self.assertTrue((self.z / "bundles/factory/tree/new_tool.py").exists())

    def test_a_file_the_rules_no_longer_exclude_is_added_not_removed_by_z_sdlc(self):
        self.put(self.inc, ".github/factory/host/setup.sh", "setup\n")
        rules = {**RULES, "excluded": [*RULES["excluded"], "host/*"]}
        self.rules.write_text(json.dumps(rules))
        self.commit("host setup")
        self.assertEqual(self.run_it("--apply")[0], 0)
        git(self.z.parent, "init", "-q", str(self.z))
        git(self.z, "add", "-A")
        git(self.z, "commit", "-q", "-m", "z-sdlc")
        rules = {**json.loads(self.rules.read_text()), "excluded": RULES["excluded"]}
        self.rules.write_text(json.dumps(rules))
        code, out = self.run_it()
        self.assertIn("added    host/setup.sh", out)
        self.assertNotIn("removed it", out)
        # A file z-sdlc's history had and deleted is still z-sdlc's removal.
        (self.z / "bundles/factory/tree/guard.py").unlink()
        git(self.z, "commit", "-q", "-am", "z-sdlc drops the guard")
        code, out = self.run_it()
        self.assertIn("ahead    guard.py (z-sdlc removed it)", out)

    def test_a_copy_z_sdlc_committed_is_not_an_incubator_edit(self):
        self.assertEqual(self.run_it("--apply")[0], 0)
        git(self.z.parent, "init", "-q", str(self.z))
        self.put(self.z, PROCESS, "rules, revised\n")
        git(self.z, "add", "-A")
        git(self.z, "commit", "-q", "-m", "z-sdlc revises the rules")
        # --to-incubator's copy, committed in the incubator; then z-sdlc revises again, uncommitted.
        self.put(self.inc, "ops/sdlc/" + PROCESS, "rules, revised\n")
        self.commit("docs: z-sdlc's rules")
        self.put(self.z, PROCESS, "rules, revised twice\n")
        code, out = self.run_it()
        self.assertNotIn("the incubator changed its copy", out)
        self.assertIn("z-sdlc's process/factory.md is newer", out)
        # An edit made in the incubator is still one.
        self.put(self.inc, "ops/sdlc/" + PROCESS, "rules, edited in the incubator\n")
        self.commit("docs: an incubator edit")
        code, out = self.run_it()
        self.assertIn("the incubator changed its copy", out)

    def test_a_removed_file_needs_accept(self):
        self.put(self.z, "bundles/factory/tree/old/gone.py", "z = 1\n")
        code, out = self.run_it("--apply")
        self.assertEqual(code, 1)
        self.assertIn("removed  old/gone.py", out)
        self.assertTrue((self.z / "bundles/factory/tree/old/gone.py").exists())
        code, out = self.run_it("--apply", "--accept")
        self.assertEqual(code, 0, out)
        self.assertFalse((self.z / "bundles/factory/tree/old").exists())

    def test_seeds_and_excluded_files_never_enter_the_tree(self):
        self.run_it("--apply", "--accept")
        tree = sorted(p.relative_to(self.z / "bundles/factory/tree").as_posix()
                      for p in (self.z / "bundles/factory/tree").rglob("*") if p.is_file())
        self.assertEqual(tree, ["guard.py", "run.sh"])

    def test_a_new_setting_in_a_json_seed_must_be_fixed_before_applying(self):
        self.put(self.inc, ".github/factory/factory.json", json.dumps({**FACTORY_JSON, "smoke": {"echo_host": "e"}}))
        self.commit("feat: echo host")
        code, out = self.run_it("--apply", "--accept")
        self.assertEqual(code, 1)
        self.assertIn("[fix first] seed factory.json: the incubator has setting smoke.echo_host", out)
        self.assertNotIn("stack.env.MODEL_DIR", out)  # a free setting: the project's own names
        self.assertEqual(self.recorded(), "")
        self.put(self.z, "bundles/factory/seed/factory.json", json.dumps({**FACTORY_JSON, "smoke": {"echo_host": ""}}))
        code, out = self.run_it("--apply")
        self.assertEqual(code, 0, out)

    def test_an_optional_setting_the_incubator_lacks_is_no_finding(self):
        seed = {**FACTORY_JSON, "fixtures": {"path": ""}, "runners": {"strict": "f", "ci": "f-ci"}, "extra": 1}
        self.put(self.z, "bundles/factory/seed/factory.json", json.dumps(seed))
        rules = json.loads(self.rules.read_text())
        rules["optional_settings"] = {"factory.json": ["fixtures", "runners.ci"]}
        self.rules.write_text(json.dumps(rules))
        code, out = self.run_it()
        self.assertNotIn("setting fixtures", out)
        self.assertNotIn("setting runners.ci", out)
        self.assertIn("[fix first] seed factory.json: the bundle's seed has setting extra and the incubator doesn't", out)

    def test_a_changed_text_seed_is_reported_and_needs_accept(self):
        self.run_it("--apply")
        self.put(self.inc, ".github/factory/README.md", "acme notes, more\n")
        head = self.commit("docs: notes")
        code, out = self.run_it("--apply")
        self.assertEqual(code, 1)
        self.assertIn("[check, then --accept] seed README.md: the incubator changed its own", out)
        self.assertNotEqual(self.recorded(), head)  # not recorded: the next report still shows it
        code, out = self.run_it("--apply", "--accept")
        self.assertEqual(self.recorded(), head)
        code, out = self.run_it()
        self.assertEqual(code, 0, out)  # checked and recorded: gone

    def test_incubator_specific_text_is_flagged_and_needs_accept(self):
        self.put(self.inc, ".github/factory/guard.py", "x = 1\npath = '/home/acme-only/x'\n")
        self.commit("oops")
        code, out = self.run_it("--apply")
        self.assertEqual(code, 1)
        self.assertIn("incubator-specific text added to guard.py: path = '/home/acme-only/x'", out)
        self.assertEqual((self.z / "bundles/factory/tree/guard.py").read_text(), "x = 1\n")

    def test_a_private_name_is_flagged_and_never_written_to_import_json(self):
        self.put(self.inc, ".github/factory/guard.py", "x = 1\nhost = 'hushproject-db'\n")
        self.commit("names the project")
        code, out = self.run_it("--apply")
        self.assertEqual(code, 1)
        self.assertIn("incubator-specific text added to guard.py: host = 'hushproject-db'", out)
        code, out = self.run_it("--apply", "--accept")
        self.assertEqual(code, 0, out)
        self.assertNotIn("hushproject", self.rules.read_text().lower())

    def test_a_missing_names_file_blocks_apply(self):
        (self.z / ".claude/private-names.txt").unlink()
        code, out = self.run_it("--apply")
        self.assertEqual(code, 1)
        self.assertIn(".claude/private-names.txt is missing or empty", out)
        self.assertEqual(self.recorded(), "")

    def test_the_clone_defaults_to_the_local_file(self):
        self.put(self.z, ".claude/incubator-clone.txt", f"{self.inc}\n")
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            code = imf.main(["--root", str(self.z), "--rules", str(self.rules)])
        self.assertEqual(code, 0, out.getvalue())
        self.assertIn("in sync", out.getvalue())

    def test_no_clone_and_no_local_file_is_a_usage_error(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            code = imf.main(["--root", str(self.z), "--rules", str(self.rules)])
        self.assertEqual(code, 2)
        self.assertIn("incubator-clone.txt is missing or empty", out.getvalue())

    def test_a_newer_z_sdlc_mirror_is_reported_but_never_blocks(self):
        self.run_it("--apply")
        self.put(self.z, PROCESS, "rules, revised\n")
        self.put(self.inc, ".github/factory/guard.py", "x = 4\n")
        head = self.commit("fix the guard")
        code, out = self.run_it("--apply")
        self.assertEqual(code, 1)  # still something for a person: copy it to the incubator
        self.assertIn("[for the incubator] ops/sdlc/process/factory.md: z-sdlc's process/factory.md is newer", out)
        self.assertEqual(self.recorded(), head)

    def test_an_incubator_edit_to_a_mirror_blocks_applying_until_ported(self):
        self.run_it("--apply")
        self.put(self.inc, ".claude/" + SKILL, "triage text, edited in the incubator\n")
        self.put(self.inc, ".github/factory/guard.py", "x = 3\n")
        self.commit("edit the skill and the guard")
        code, out = self.run_it("--apply", "--accept")
        self.assertEqual(code, 1)
        self.assertIn("[fix first] .claude/skills/sdlc-triage/SKILL.md: the incubator changed its copy", out)
        # Not recorded, so the next report still says to port it, not to overwrite the incubator's edit.
        code, out = self.run_it()
        self.assertIn("the incubator changed its copy of z-sdlc's skills/sdlc-triage/SKILL.md", out)
        self.assertNotIn("is newer; copy it into the incubator", out)
        self.put(self.z, SKILL, "triage text, edited in the incubator\n")  # ported
        code, out = self.run_it("--apply")
        self.assertEqual(code, 0, out)
        self.assertEqual((self.z / "bundles/factory/tree/guard.py").read_text(), "x = 3\n")

    # ---- z-sdlc's own changes (a fix found in a project that installed the bundle, CD 2026-10-12)
    def test_a_z_sdlc_fix_is_kept_and_goes_to_the_incubator(self):
        self.run_it("--apply")
        self.put(self.z, "bundles/factory/tree/guard.py", "x = 5\n")  # fixed in z-sdlc during the pilot
        code, out = self.run_it("--apply")
        self.assertEqual(code, 1, out)  # something for a person: the incubator lacks the fix
        self.assertIn("ahead    guard.py (z-sdlc changed it)", out)
        self.assertEqual((self.z / "bundles/factory/tree/guard.py").read_text(), "x = 5\n")  # never overwritten
        code, out = self.run_it("--to-incubator")
        self.assertIn("changed  .github/factory/guard.py", out)
        self.assertEqual((self.inc / ".github/factory/guard.py").read_text(), "x = 5\n")
        self.commit("fix(factory): the guard, from z-sdlc")
        code, out = self.run_it()
        self.assertEqual(code, 0, out)
        self.assertIn("in sync", out)

    def test_a_file_z_sdlc_added_is_ahead_not_removed(self):
        self.run_it("--apply")
        self.put(self.z, "bundles/factory/tree/new_check.py", "ok = True\n")
        code, out = self.run_it("--apply")
        self.assertIn("ahead    new_check.py (z-sdlc added it)", out)
        self.assertNotIn("removed  new_check.py", out)
        self.assertTrue((self.z / "bundles/factory/tree/new_check.py").exists())
        self.run_it("--to-incubator")
        self.assertEqual((self.inc / ".github/factory/new_check.py").read_text(), "ok = True\n")

    def test_a_file_the_incubator_deleted_is_removed_with_accept(self):
        self.run_it("--apply")
        git(self.inc, "rm", "-q", ".github/factory/run.sh")
        self.commit("drop run.sh")
        code, out = self.run_it("--apply")
        self.assertEqual(code, 1)
        self.assertIn("removed  run.sh", out)
        self.run_it("--apply", "--accept")
        self.assertFalse((self.z / "bundles/factory/tree/run.sh").exists())

    def test_a_change_on_both_sides_is_a_conflict_until_merged(self):
        self.run_it("--apply")
        self.put(self.z, "bundles/factory/tree/guard.py", "x = 5\n")
        self.put(self.inc, ".github/factory/guard.py", "x = 6\n")
        self.commit("the incubator's change")
        code, out = self.run_it("--apply")
        self.assertEqual(code, 1)
        self.assertIn("conflict guard.py", out)
        self.assertIn("Not applied", out)
        self.assertEqual((self.z / "bundles/factory/tree/guard.py").read_text(), "x = 5\n")
        self.put(self.inc, ".github/factory/guard.py", "x = 5\ny = 6\n")  # merged in the incubator
        self.commit("merge z-sdlc's fix")
        code, out = self.run_it("--apply", "--accept")
        self.assertEqual(code, 0, out)
        self.assertEqual((self.z / "bundles/factory/tree/guard.py").read_text(), "x = 5\ny = 6\n")

    def test_to_incubator_refuses_uncommitted_work_there(self):
        self.run_it("--apply")
        self.put(self.z, "bundles/factory/tree/guard.py", "x = 5\n")
        self.put(self.inc, ".github/factory/guard.py", "x = 8\n")  # uncommitted in the incubator
        code, out = self.run_it("--to-incubator")
        self.assertEqual(code, 1)
        self.assertIn("uncommitted changes", out)
        self.assertEqual((self.inc / ".github/factory/guard.py").read_text(), "x = 8\n")

    def test_to_incubator_copies_newer_skills_and_process_docs(self):
        self.run_it("--apply")
        self.put(self.z, PROCESS, "rules, revised\n")
        self.run_it("--to-incubator")
        self.assertEqual((self.inc / "ops/sdlc" / PROCESS).read_text(), "rules, revised\n")

    def test_only_committed_work_is_imported(self):
        self.put(self.inc, ".github/factory/guard.py", "x = 99\n")  # not committed
        code, out = self.run_it("--apply")
        self.assertEqual(code, 0, out)
        self.assertEqual((self.z / "bundles/factory/tree/guard.py").read_text(), "x = 1\n")

    def test_an_unknown_commit_is_a_usage_error(self):
        code, out = self.run_it("--commit", "no-such-ref")
        self.assertEqual(code, 2)
        self.assertIn("import_factory:", out)


if __name__ == "__main__":
    unittest.main()
