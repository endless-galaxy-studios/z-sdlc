"""Root's own entry points: load() and main()'s dispatch with a poisoned host module beside gates.py on sys.path (the
real hazard: root puts its library directory on the path), a project's own ops/<name>.sh reaching every reader of the
block, `check` before the first baseline, and the real step path, factory_op.py run as __main__ in a process of its own,
where the host module's exceptions must be the broker's own."""

import io
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import fakes
from fakes import Env, TOKEN
import factory_op as fo
import gates
from test_broker_fitness import POISON, PoisonFinder


class ScriptsTest(unittest.TestCase):
    """A project that keeps ops/warm-cache.sh for an operation of its own: every reader of the block sees the script."""

    def setUp(self):
        cat = fakes.catalog_dict()
        cat["operations"]["warm-cache"] = {"kind": "read", "summary": "Warm the cache", "timeout_s": 60, "outputs": {}}
        cat["broker"]["op_secrets"]["warm-cache"] = []
        self.env = Env(cat=cat)
        self.addCleanup(self.env.close)
        for name, value in (("LOCK", self.env.tmp / "run" / "broker.lock"), ("STEPS_DIR", self.env.tmp / "steps")):
            p = mock.patch.object(fo, name, value)
            p.start()
            self.addCleanup(p.stop)
        fakes.no_live_steps(self)

    def script(self):
        (self.env.lib / "ops").mkdir(exist_ok=True)
        (self.env.lib / "ops" / "warm-cache.sh").write_text("exit 0\n")

    def test_without_its_script_the_catalog_has_a_problem_and_steps_fail(self):
        self.assertTrue(any("warm-cache" in p for p in fo.broker_problems(self.env.cat, fo.lib_scripts(self.env.lib))))
        self.assertEqual(self.env.run_op("health").status, "failed")

    def test_with_its_script_every_reader_accepts_the_catalog(self):
        self.script()
        self.assertEqual(fo.broker_problems(self.env.cat, fo.lib_scripts(self.env.lib)), [])
        self.assertEqual(self.env.run_op("health").status, "done")
        self.assertEqual(fo.cmd_baseline(self.env.cfg, gates, self.env.cat, self.env.secret, "n", False, self.env.svc_factory(),
                                         fakes.Console()), 0)
        with mock.patch("os.geteuid", return_value=1000), mock.patch.object(fo, "egress_serve") as serve, \
                mock.patch("socket.socket"), mock.patch("os.dup", return_value=9):
            self.assertEqual(fo.egress_main(lib=self.env.lib), 0)
        serve.assert_called_once()
        routes, _ = fakes.gate_routes(self.env)
        gh = fo.GitHub(self.env.cfg["repo"], TOKEN, opener=fakes.FakeOpener(self.env.cfg["repo"], routes))
        signed = fo.serve_one(self.env.cfg, gates, self.env.cat, json.dumps({"run_id": 55, "pr": 7, "token": TOKEN}),
                              self.env.secret, svc_factory=lambda cfg, token: self.env.services(gh))
        self.assertEqual(gates.verify_receipt(self.env.public, signed)["status"], "done")
        self.assertFalse(any("is neither a generic operation" in p for p in fo.check(self.env.cfg, self.env.cat, gates)))


class CheckTest(unittest.TestCase):
    def setUp(self):
        self.env = Env()
        self.addCleanup(self.env.close)
        self.key = self.env.tmp / "receipt.key"
        self.key.write_text(self.env.secret.hex())
        p = mock.patch.object(fo, "KEY", self.key)
        p.start()
        self.addCleanup(p.stop)

    def test_no_recorded_state_yet_isnt_a_problem(self):
        problems = fo.check(self.env.cfg, self.env.cat, gates)
        self.assertFalse(any("recorded" in p for p in problems), problems)

    def test_a_record_that_doesnt_match_the_block_is_one(self):
        state = self.env.capture_state()
        state["recorded"].pop("fp_cache")
        self.env.append_baseline(state)
        self.assertTrue(any("recorded outputs changed" in p for p in fo.check(self.env.cfg, self.env.cat, gates)))

    def test_an_unfinished_run_and_a_badly_signed_record_are_problems(self):
        self.env.append_baseline(self.env.capture_state(), secret=bytes(range(60, 92)))
        fo.ledger_append(self.env.cfg["ledger"], {"event": "start", "run": "r9"})
        problems = fo.check(self.env.cfg, self.env.cat, gates)
        self.assertTrue(any("fails signature verification" in p for p in problems), problems)
        self.assertTrue(any("r9 needs resolving" in p for p in problems), problems)

    def test_a_python_below_the_blocks_floor_is_a_problem(self):
        cat = fakes.load(fakes.catalog_dict(broker__python="3.99"))
        self.assertTrue(any("below broker.python 3.99" in p for p in fo.check(self.env.cfg, cat, gates)))


class LoadAndMainTest(unittest.TestCase):
    """load() and main() as root, with factory_op_host.py poisoned beside gates.py in the library directory root puts on
    sys.path, and a finder that fails any import of it by name."""

    def setUp(self):
        self.env = Env()
        self.addCleanup(self.env.close)
        self.lib = self.env.tmp / "factory-prod"
        shutil.copytree(self.env.lib, self.lib)
        (self.lib / fo.HOST_MODULE).write_text(POISON)
        self.config = self.env.tmp / "etc-config.json"
        self.config.write_text(json.dumps({**self.env.cfg, "lib_dir": str(self.lib)}))
        self.key = self.env.tmp / "receipt.key"
        self.key.write_text(self.env.secret.hex())
        self.finder = PoisonFinder()
        sys.modules.pop("factory_op_host", None)
        sys.meta_path.insert(0, self.finder)
        self.addCleanup(sys.meta_path.remove, self.finder)
        before = list(sys.path)
        self.addCleanup(lambda: sys.path.__setitem__(slice(None), before))
        # load() narrows the openssl programs ed25519 signs with to root's own (S8): put the shared module back after.
        import ed25519
        saved = ed25519._openssls

        def unguard():
            ed25519._openssls = saved
            ed25519.__dict__.pop("_factory_op_guarded", None)
        self.addCleanup(unguard)
        for name, value in (("LOCK", self.env.tmp / "run" / "broker.lock"), ("STEPS_DIR", self.env.tmp / "steps"),
                            ("CONFIG", self.config), ("KEY", self.key), ("HEALTH_STAMP", self.env.tmp / "stamp")):
            p = mock.patch.object(fo, name, value)
            p.start()
            self.addCleanup(p.stop)
        fakes.no_live_steps(self)
        self.addCleanup(self.never_imported)

    def never_imported(self):
        self.assertEqual(self.finder.asked, [])
        self.assertNotIn("factory_op_host", sys.modules)

    def test_load_reads_config_and_catalog_and_puts_only_data_in_hand(self):
        with mock.patch.object(fo, "LIB", self.lib):
            cfg, gates_mod, catalog, problems = fo.load(fo.tier_names("factory-prod"))
        self.assertIn(str(self.lib), sys.path)  # the hazard is real: the poisoned module is importable by name now
        self.assertEqual(catalog["broker"]["egress"], fakes.CATALOG["broker"]["egress"])
        self.assertTrue(any("lib_dir" in p for p in problems), problems)  # a temp lib isn't the tier's install path

    def test_load_reads_the_installed_package_once_and_keeps_its_digest(self):
        """config.json and ops.json come from the bytes the digest covers (the library's copy, never /etc's), and the
        Loaded result carries that digest for the lock-time check."""
        import ed25519
        self.config.write_text(json.dumps({"repo": "octo-org/elsewhere"}))  # /etc's copy, which must not be what is read
        with mock.patch.object(fo, "LIB", self.lib):
            loaded = fo.load(fo.tier_names("factory-prod"))
        cfg, _, catalog, problems = loaded
        self.assertEqual(cfg, json.loads((self.lib / "config.json").read_text()))
        self.assertEqual(catalog["broker"]["egress"], fakes.CATALOG["broker"]["egress"])
        self.assertEqual(loaded.package.digest, fo.installed_digest(gates, self.lib))
        self.assertEqual(loaded.package.lib, self.lib)
        self.assertIn("config.json", gates.installed_ops_files(self.lib))
        self.assertTrue(ed25519._factory_op_guarded)
        self.assertFalse(any("started from" in p for p in problems), problems)

    def test_a_broker_file_that_isnt_the_running_one_is_a_problem(self):
        (self.lib / "factory_op.py").write_text((self.lib / "factory_op.py").read_text() + "\n# installed as this started\n")
        with mock.patch.object(fo, "LIB", self.lib):
            problems = fo.load(fo.tier_names("factory-prod"))[3]
        self.assertTrue(any("isn't the one this command started from" in p for p in problems), problems)

    def test_a_package_that_changed_between_the_imports_and_the_snapshot_is_a_problem(self):
        """Setup's install landing while load imports gates and ed25519: the code imported isn't the code hashed."""
        older = dict(fo.read_package(self.lib), **{"gates.py": b"# the gates.py imported before setup replaced it\n"})
        with mock.patch.object(fo, "LIB", self.lib), mock.patch.object(fo, "read_package", return_value=older):
            problems = fo.load(fo.tier_names("factory-prod"))[3]
        self.assertTrue(any("changed while this command loaded it" in p for p in problems), problems)
        with mock.patch.object(fo, "LIB", self.lib), mock.patch.object(fo, "read_package", side_effect=OSError("gone")):
            problems = fo.load(fo.tier_names("factory-prod"))[3]
        self.assertTrue(any("changed while this command loaded it" in p for p in problems), problems)
        self.assertEqual(fo.read_package(self.lib), gates.installed_ops_files(self.lib))  # the same files, read without gates

    def test_a_library_without_its_host_module_is_a_problem(self):
        (self.lib / fo.HOST_MODULE).unlink()
        with mock.patch.object(fo, "LIB", self.lib):
            problems = fo.load(fo.tier_names("factory-prod"))[3]
        self.assertTrue(any(f"no {fo.HOST_MODULE}" in p for p in problems), problems)

    def test_a_broken_catalog_is_a_problem_not_a_crash(self):
        (self.lib / "ops.json").write_text("{not json")
        with mock.patch.object(fo, "LIB", self.lib):
            _, _, catalog, problems = fo.load(fo.tier_names("factory-prod"))
        self.assertIsNone(catalog)
        self.assertTrue(any("ops.json isn't usable" in p for p in problems))

    def main(self, *argv, answers=("yes",)):
        sys.path.insert(0, str(self.lib))
        cfg = {**self.env.cfg}
        out = io.StringIO()
        with mock.patch.object(fo, "LIB", pathlib.Path("/usr/local/lib/factory-prod")), \
                mock.patch("os.geteuid", return_value=0), mock.patch.object(fo, "install_root_signals"), \
                mock.patch.object(fo, "load", return_value=(cfg, gates, self.env.cat, [])), \
                mock.patch.object(fo, "real_services", lambda c, token, cat: self.env.services(fakes.github_for(c, self.env.repo, []))), \
                mock.patch("builtins.input", side_effect=list(answers)), mock.patch("sys.stdout", out), \
                mock.patch("sys.stderr", new_callable=io.StringIO):
            rc = fo.main(["factory_op.py", *argv])
        return rc, out.getvalue()

    def test_every_root_command_through_main(self):
        rc, out = self.main("pubkey")
        self.assertEqual((rc, out.strip()), (0, self.env.public))
        rc, out = self.main("baseline", "first")
        self.assertEqual(rc, 0, out)
        self.assertIn("baseline recorded", out)
        rc, out = self.main("check")
        self.assertIn('"ok"', out)
        rc, out = self.main("health")
        self.assertEqual(rc, 0, out)
        rc, out = self.main("diagnose", "host-check")
        self.assertEqual(rc, 0, out)
        rc, out = self.main("drift-check")
        self.assertEqual((rc, out.strip()), (0, "drift: ok"))
        fo.ledger_append(self.env.cfg["ledger"], {"event": "start", "run": "r9", "repo": "x", "pr": 7, "issue": 3, "gate": "G1",
                                                  "attempt": 1, "digest": "d" * 64, "github_run": 5})
        rc, out = self.main("resolve", "r9", "failed", "by hand")
        self.assertEqual(rc, 0, out)

    def test_main_refuses_every_command_while_load_found_problems_but_check_reports_them(self):
        with mock.patch.object(fo, "LIB", pathlib.Path("/usr/local/lib/factory-prod")), \
                mock.patch("os.geteuid", return_value=0), mock.patch.object(fo, "install_root_signals"), \
                mock.patch.object(fo, "load", return_value=(self.env.cfg, gates, self.env.cat, ["rollbacks must be false"])):
            for cmd in (["baseline", "n"], ["health"], ["diagnose", "host-check"], ["drift-check"], ["resolve", "r", "failed"]):
                with self.subTest(cmd), mock.patch("sys.stderr", new_callable=io.StringIO) as err:
                    self.assertEqual(fo.main(["factory_op.py", *cmd]), 1)
                    self.assertIn("rollbacks must be false", err.getvalue())
            with mock.patch("sys.stdout", new_callable=io.StringIO) as out:
                self.assertEqual(fo.main(["factory_op.py", "check"]), 1)
            self.assertIn("rollbacks must be false", out.getvalue())


DRIVER = r'''
import datetime, importlib.util, json, sys
from unittest import mock
path, host, env_file = sys.argv[1:4]
spec = importlib.util.spec_from_file_location("__main__", path)
mod = importlib.util.module_from_spec(spec)
sys.modules["__main__"] = mod
try:
    spec.loader.exec_module(mod)  # main() refuses outside a tier's install path; every definition is in place by then
except SystemExit:
    pass
assert "factory_op" not in sys.modules
class Clock:
    t = 0.0
    def monotonic(self): return self.t
    def sleep(self, s): self.t += s
    def now(self): return datetime.datetime(2026, 11, 5, 12, tzinfo=datetime.timezone.utc)
with mock.patch("os.geteuid", return_value=1000):
    rc = mod.op_main("health", json.loads(open(env_file).read()), connect=lambda h, t: None, clock=Clock(), host_module=host)
print(json.dumps({"rc": rc, "factory_op_is_main": sys.modules.get("factory_op") is mod}))
'''

MINIMAL_HOST = '''
import datetime
from factory_op import Deployment, StepFailed, Unavailable
T = datetime.datetime(2026, 11, 5, 9, tzinfo=datetime.timezone.utc)
def client(ctx): return None
def preflight(ctx): pass
def latest(ctx): return {s: "success" for s in ctx.services}
def deployments(ctx, svc): return []
def serving(ctx, svc): return Deployment("dep-0001", None, "success", T)
def reports(ctx, svc, deployment_id): raise Unavailable("no usable answer")
def heartbeat(ctx, svc, deployment_id, patient): raise Unavailable("no usable answer")
def capture(ctx): raise StepFailed("not here")
OPS = {"snapshot-status": lambda ctx: {}, "snapshot-now": lambda ctx: {}}
'''


class RealStepPathTest(unittest.TestCase):
    """factory_op.py loaded as __main__, as `python3 -I factory_op.py op <name>` runs it, in a process of its own: the host
    module's `from factory_op import Unavailable` must be the broker's own class, or a strict read's "no usable answer"
    would escape health's handling instead of naming the service."""

    def test_the_host_modules_exceptions_are_the_brokers_own(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            lib, step = tmp / "lib", tmp / "step"
            lib.mkdir()
            step.mkdir()
            (lib / "ops.json").write_text(json.dumps(fakes.CATALOG))
            (lib / "host.py").write_text(MINIMAL_HOST)
            (step / "secret-token").write_text(fakes.SENTINEL_TOKEN)
            cfg = fakes.make_config(tmp, lib)
            (tmp / "config.json").write_text(json.dumps(cfg))
            env = {"OP_OUT": str(step / "out"), "OP_DETAIL": str(step / "detail.json"), "FACTORY_STEP_DIR": str(step),
                   "FACTORY_CLONE": str(tmp / "clone.git"), "FACTORY_CONFIG": str(tmp / "config.json"),
                   "FACTORY_RELEASE_HEAD": "", "FACTORY_RUN": "r1"}
            (tmp / "env.json").write_text(json.dumps(env))
            (tmp / "driver.py").write_text(DRIVER)
            r = subprocess.run([sys.executable, "-I", str(tmp / "driver.py"), str(fakes.PROD / "factory_op.py"), str(lib / "host.py"),
                                str(tmp / "env.json")], capture_output=True, text=True, timeout=60)
            self.assertEqual(r.returncode, 0, r.stderr)
            result = json.loads(r.stdout.strip().splitlines()[-1])
            self.assertEqual(result, {"rc": 1, "factory_op_is_main": True}, r.stderr)
            self.assertIn("FAILED: unhealthy: web,jobs; web: no usable answer", r.stderr)
            out = (step / "out").read_text()
            self.assertIn("healthy=no\n", out)
            self.assertIn("unhealthy=web,jobs\n", out)


if __name__ == "__main__":
    unittest.main()
