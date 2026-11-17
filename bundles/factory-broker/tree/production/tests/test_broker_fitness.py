"""The checks-only broker's fitness (z-sdlc process/factory.md D4, process/factory-broker.md):

- root runs no project code: every root command runs with a host module beside the broker that raises the moment
  anything imports it, and nothing imports it by name;
- a step loads the host module only by its explicit path, and fails closed on a missing primitive, a wrong OPS set,
  a module that raises, or one that imports broker internals;
- no rollback runs: a non-empty rollback is refused for every request kind, before anything is recorded;
- broker_problems refuses a release service with no evidence, an unknown block key, `rollbacks` not false, a missing
  required operation, and a script standing in for a generic operation;
- the instance comes from the install path;
- the digest the broker computes over its installed layout is the one the repository's layout gives, host module
  included.
Run by CI: python3 -I -m unittest discover -s .github/factory/production/tests"""

import ast
import io
import json
import os
import pathlib
import shutil
import sys
import tempfile
import unittest
from unittest import mock

import fakes
from fakes import Env, TOKEN
import factory_op as fo
import gates

POISON = 'raise RuntimeError("POISONED: the host module was imported")\n'


class PoisonFinder:
    """A meta path finder that fails any import of the host module by name."""

    def __init__(self):
        self.asked = []

    def find_spec(self, name, path=None, target=None):
        if name.split(".")[0] == "factory_op_host":
            self.asked.append(name)
            raise ImportError("POISONED: something imported factory_op_host by name")
        return None


class PoisonedBase(unittest.TestCase):
    def setUp(self):
        self.env = Env()
        self.addCleanup(self.env.close)
        self.cfg = self.env.cfg
        (self.env.lib / fo.HOST_MODULE).write_text(POISON)
        self.finder = PoisonFinder()
        sys.modules.pop("factory_op_host", None)
        sys.meta_path.insert(0, self.finder)
        self.addCleanup(sys.meta_path.remove, self.finder)
        for name, value in (("LOCK", self.env.tmp / "run" / "broker.lock"), ("STEPS_DIR", self.env.tmp / "steps")):
            patcher = mock.patch.object(fo, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        fakes.no_live_steps(self)
        self.addCleanup(self.never_imported)

    def never_imported(self):
        self.assertEqual(self.finder.asked, [])
        self.assertNotIn("factory_op_host", sys.modules)

    def baseline(self):
        console = fakes.Console()
        self.assertEqual(fo.cmd_baseline(self.cfg, gates, self.env.cat, self.env.secret, "first", False,
                                         self.env.svc_factory(), console), 0, console.lines)
        return console


class RootRunsNoProjectCodeTest(PoisonedBase):
    """Every root command, with a poisoned factory_op_host.py in the library directory and a finder that fails any
    import of it by name. The steps run in-process, loading fake_host by its path, as a sandboxed step loads the
    project's."""

    def test_check_runs_offline_without_the_lock(self):
        with mock.patch.object(fo, "broker_lock", side_effect=AssertionError("check took the lock")), \
                mock.patch("socket.socket.connect", side_effect=AssertionError("check made a request")):
            problems = fo.check(self.cfg, self.env.cat, gates)
        self.assertIsInstance(problems, list)
        self.assertFalse(any("POISONED" in p for p in problems), problems)

    def test_baseline(self):
        console = self.baseline()
        self.assertIn("baseline recorded", console.lines[-1])

    def test_health(self):
        console = fakes.Console()
        rc = fo.cmd_health(self.cfg, self.env.cat, self.env.svc_factory(), console, clock=self.env.clock,
                           stamp=self.env.tmp / "health.stamp")
        self.assertEqual(rc, 0, console.lines)

    def test_diagnose(self):
        for name in ("host-check", "check-token"):
            console = fakes.Console()
            self.assertEqual(fo.cmd_diagnose(self.cfg, self.env.cat, name, self.env.svc_factory(), console), 0,
                             (name, console.lines))

    def test_drift_check(self):
        self.baseline()
        issues, line = fo.drift_check(self.cfg, gates, self.env.cat, self.env.secret, self.env.svc_factory())
        self.assertEqual(issues, [], line)

    def test_serve_a_gate_end_to_end(self):
        self.baseline()
        routes, _ = fakes.gate_routes(self.env)
        gh = fo.GitHub(self.cfg["repo"], TOKEN, opener=fakes.FakeOpener(self.cfg["repo"], routes))
        line = json.dumps({"run_id": 55, "pr": 7, "token": TOKEN})
        signed = fo.serve_one(self.cfg, gates, self.env.cat, line, self.env.secret, svc_factory=lambda cfg, token: self.env.services(gh))
        receipt = gates.verify_receipt(self.env.public, signed)
        self.assertEqual(receipt["status"], "done", receipt.get("reason"))

    def test_resolve(self):
        fo.ledger_append(self.cfg["ledger"], {"event": "start", "run": "r9", "repo": self.cfg["repo"], "pr": 7, "issue": 3,
                                              "gate": "G1", "attempt": 1, "digest": "d" * 64, "github_run": 5, "kind": "ops",
                                              "head": "a" * 40, "at": "x", "approver": 1})
        self.assertEqual(fo.cmd_resolve(self.cfg, gates, self.env.secret, "r9", "checked by hand"), 0)

    def test_the_loader_is_called_only_by_op_main_and_nothing_imports_the_module_by_name(self):
        tree = ast.parse(pathlib.Path(fo.__file__).read_text())
        callers = set()
        for func in (n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)):
            for call in (n for n in ast.walk(func) if isinstance(n, ast.Call)):
                name = getattr(call.func, "id", None) or getattr(call.func, "attr", None)
                if name == "load_host":
                    callers.add(func.name)
                if name == "spec_from_file_location":
                    self.assertEqual(func.name, "load_host")
        self.assertEqual(callers, {"op_main"})
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                self.assertFalse(any("factory_op_host" in a.name for a in node.names))
            if isinstance(node, ast.ImportFrom):
                self.assertNotIn("factory_op_host", node.module or "")
        src = pathlib.Path(fo.__file__).read_text()
        self.assertNotIn("__import__(", src)
        self.assertNotIn("import_module(", src)


class StepLoadingTest(unittest.TestCase):
    """op_main loads the host module from its path, checks the interface, and fails the step closed otherwise."""

    def setUp(self):
        self.env = Env()
        self.addCleanup(self.env.close)
        self.n = 0

    def module(self, text):
        self.n += 1
        path = self.env.tmp / "mods" / str(self.n) / fo.HOST_MODULE
        path.parent.mkdir(parents=True)
        path.write_text(text)
        return path

    def run_with(self, path, name="health"):
        self.env.sandbox.host_module = path
        return self.env.run_op(name)

    def broken(self, extra):
        return self.module(fakes.FAKE_HOST.read_text() + "\n" + extra + "\n")

    def test_the_fake_host_passes(self):
        self.assertEqual(self.run_with(fakes.FAKE_HOST).status, "done")

    def test_it_loads_by_path_never_through_sys_path(self):
        decoy = self.module(POISON)
        sys.path.insert(0, str(decoy.parent))
        self.addCleanup(sys.path.remove, str(decoy.parent))
        sys.modules.pop("factory_op_host", None)
        res = self.run_with(fakes.FAKE_HOST)
        self.assertEqual(res.status, "done", res.why)
        self.assertNotIn("factory_op_host", sys.modules)

    def test_a_missing_primitive_fails_the_step(self):
        for name in ("client", "preflight", "latest", "deployments", "serving", "reports", "heartbeat", "capture"):
            with self.subTest(name):
                res = self.run_with(self.broken(f"del {name}"))
                self.assertEqual(res.status, "failed")
                self.assertIn(name, res.why)

    def test_a_primitive_that_isnt_callable_fails_the_step(self):
        res = self.run_with(self.broken("serving = 3"))
        self.assertEqual(res.status, "failed")
        self.assertIn("serving", res.why)

    def test_ops_must_be_exactly_the_blocks_host_ops(self):
        for text in ("OPS = {'snapshot-status': op_snapshot_status}",
                     "OPS = {**OPS, 'snapshot-drop': op_snapshot_now}", "OPS = []"):
            with self.subTest(text):
                res = self.run_with(self.broken(text))
                self.assertEqual(res.status, "failed")
                self.assertIn("OPS", res.why)

    def test_a_host_op_or_diagnostic_named_like_a_generic_op_fails(self):
        for text in ("OPS = {**OPS, 'health': op_snapshot_status}", "DIAGNOSTICS = {**DIAGNOSTICS, 'drift-scan': check_token}"):
            with self.subTest(text):
                self.assertEqual(self.run_with(self.broken(text)).status, "failed")

    def test_a_diagnostic_must_be_an_internal_op(self):
        res = self.run_with(self.broken("DIAGNOSTICS = {**DIAGNOSTICS, 'undeclared': check_token}"))
        self.assertEqual(res.status, "failed")
        self.assertIn("DIAGNOSTICS", res.why)

    def test_a_missing_module_fails_the_step(self):
        res = self.run_with(self.env.tmp / "nowhere" / fo.HOST_MODULE)
        self.assertEqual(res.status, "failed")
        self.assertIn("host module", res.why)

    def test_a_module_that_raises_on_import_fails_the_step_with_one_line(self):
        res = self.run_with(self.module(POISON))
        self.assertEqual(res.status, "failed")
        self.assertIn("RuntimeError", res.why)
        self.assertNotIn("\n", res.why)

    def test_the_module_may_import_only_the_host_api_from_the_broker(self):
        for text in ("from factory_op import Sandbox", "import factory_op", "from factory_op import *"):
            with self.subTest(text):
                res = self.run_with(self.module(text + "\n" + fakes.FAKE_HOST.read_text()))
                self.assertEqual(res.status, "failed")
                self.assertIn("HOST_API", res.why)

    def test_op_main_refuses_root_before_reading_or_loading_anything(self):
        poison = self.module(POISON)
        with mock.patch("os.geteuid", return_value=0), mock.patch("pathlib.Path.read_text") as read:
            rc = fo.op_main("health", environ={"FACTORY_STEP_DIR": "/x"}, stderr=io.StringIO(), host_module=poison)
        self.assertEqual(rc, 2)
        read.assert_not_called()

    def test_the_host_api_is_exactly_the_contracts_names(self):
        self.assertEqual(fo.HOST_API, ("StepFailed", "Unavailable", "HostError", "Deployment", "STATUSES", "Deadline",
                                       "NETWORK_ERRORS", "SHA", "safe", "parse_ts", "canonical"))
        for name in fo.HOST_API:
            self.assertTrue(hasattr(fo, name), name)
        self.assertEqual(fo.STATUSES, ("waiting", "success", "skipped", "failed", "crashed"))
        self.assertTrue(issubclass(fo.Unavailable, fo.StepFailed))


class NoRollbackTest(PoisonedBase):
    """A checks-only broker runs no rollback: a request carrying one is refused for every kind, before the start line,
    so nothing is left unfinished. gates.build_request already refuses one when the catalog says rollbacks false, so
    these requests are built by hand."""

    def setUp(self):
        super().setUp()
        self.baseline()
        self.runs_before = len(self.env.sandbox.runs)

    def request(self, kind):
        steps = [] if kind == "cd" else [{"id": "h", "op": "health", "with": {}}]
        req = {"pr": 7, "gate": "G1", "issue": 3, "attempt": 1, "digest": "d" * 64, "head": self.env.repo.head(),
               "kind": kind, "plan_blob": "b" * 40, "steps": steps,
               "rollback": [{"id": "undo", "op": "health", "with": {}}]}
        if kind == "release":
            req["release"] = {"branch": "release/production", "pr": 41, "merge": self.env.repo.head()}
        return req

    def test_a_rollback_is_refused_for_every_kind(self):
        for kind in fo.REQUEST_KINDS:
            with self.subTest(kind):
                before = fo.ledger_entries(self.cfg["ledger"])
                with self.assertRaises(fo.Refused) as cm:
                    fo.execute(self.cfg, gates, self.env.cat, self.request(kind), "def", fakes.APPROVER, 55, before,
                               lambda r: r, TOKEN, self.env.services(fakes.github_for(self.cfg, self.env.repo, [])),
                               self.env.public, host_run="run1")
                self.assertIn("rollback", str(cm.exception))
                self.assertEqual(fo.ledger_entries(self.cfg["ledger"]), before)
                self.assertEqual(len(self.env.sandbox.runs), self.runs_before)

    def test_the_refusal_is_signed(self):
        routes, request = fakes.gate_routes(self.env)
        gh = fo.GitHub(self.cfg["repo"], TOKEN, opener=fakes.FakeOpener(self.cfg["repo"], routes))
        with mock.patch.object(fo, "rebuild", return_value=({**request, "rollback": [{"id": "u", "op": "health", "with": {}}]}, "def")):
            signed = fo.serve_one(self.cfg, gates, self.env.cat, json.dumps({"run_id": 55, "pr": 7, "token": TOKEN}),
                                  self.env.secret, svc_factory=lambda cfg, token: self.env.services(gh))
        receipt = gates.verify_receipt(self.env.public, signed)
        self.assertEqual(receipt["status"], "refused")
        self.assertIn("rollback", receipt["reason"])
        self.assertFalse(any(e.get("event") == "start" for e in fo.ledger_entries(self.cfg["ledger"])))

    def test_a_release_gate_is_refused_while_release_gates_is_false(self):
        cat = fakes.load(fakes.catalog_dict(release_gates=False))
        self.assertEqual(fo.broker_problems(cat), [])
        routes, request = fakes.gate_routes(self.env, kind="release")
        gh = fo.GitHub(self.cfg["repo"], TOKEN, opener=fakes.FakeOpener(self.cfg["repo"], routes))
        with mock.patch.object(fo, "rebuild", side_effect=AssertionError("rebuilt a release request")):
            signed = fo.serve_one(self.cfg, gates, cat, json.dumps({"run_id": 55, "pr": 7, "token": TOKEN}),
                                  self.env.secret, svc_factory=lambda cfg, token: self.env.services(gh))
        receipt = gates.verify_receipt(self.env.public, signed)
        self.assertEqual(receipt["status"], "refused")
        self.assertIn("release_gates", receipt["reason"])
        req = {**self.request("release"), "rollback": []}
        with self.assertRaises(fo.Refused) as cm:
            fo.execute(self.cfg, gates, cat, req, "def", fakes.APPROVER, 55, fo.ledger_entries(self.cfg["ledger"]),
                       lambda r: r, TOKEN, self.env.services(gh), self.env.public, host_run="run1")
        self.assertIn("release_gates", str(cm.exception))
        self.assertEqual(len(self.env.sandbox.runs), self.runs_before)


class BrokerProblemsTest(unittest.TestCase):
    def problems(self, **changes):
        return fo.broker_problems(fakes.load(fakes.catalog_dict(**changes)))

    def assertRefused(self, needle, **changes):
        problems = self.problems(**changes)
        self.assertTrue(any(needle in p for p in problems), problems)

    def test_the_test_catalog_passes(self):
        self.assertEqual(self.problems(), [])

    def test_release_gates_may_be_true_or_false_but_must_be_said(self):
        self.assertEqual(self.problems(release_gates=False), [])
        self.assertRefused("release_gates", release_gates=None)

    def test_a_release_service_with_no_evidence_is_refused(self):
        services = json.loads(json.dumps(fakes.SERVICES))
        services["jobs"]["evidence"] = "none"
        self.assertRefused("evidence", broker__services=services)

    def test_an_unknown_block_key_is_refused(self):
        self.assertRefused("unknown key", broker__recorded_prefix=["fp_"])

    def test_rollbacks_must_be_false(self):
        self.assertRefused("rollbacks", rollbacks=True)
        self.assertRefused("rollbacks", rollbacks=None)

    def test_each_required_operation_must_be_in_the_catalog(self):
        for name in ("release-wait", "health", "capture-state"):
            with self.subTest(name):
                cat = fakes.catalog_dict()
                del cat["operations"][name]
                cat["broker"]["op_secrets"].pop(name)
                if name == "release-wait":
                    cat.pop("release_wait")
                problems = fo.broker_problems(fakes.load(cat))
                self.assertTrue(any(name in p for p in problems), problems)

    def test_a_script_may_not_stand_in_for_a_generic_or_host_op(self):
        for name in ("release-wait", "capture-state", "snapshot-status"):
            with self.subTest(name):
                problems = fo.broker_problems(fakes.catalog(), scripts={name})
                self.assertTrue(any(name in p and "script" in p for p in problems), problems)

    def test_it_is_pure_and_never_raises(self):
        with mock.patch("os.open", side_effect=AssertionError("I/O")), mock.patch("builtins.open", side_effect=AssertionError("I/O")):
            self.assertEqual(fo.broker_problems(fakes.catalog()), [])
            for garbage in ({}, {"broker": []}, {"operations": {}, "broker": {}}, {"broker": {"services": "x"}}, None, []):
                with self.subTest(garbage):
                    self.assertTrue(fo.broker_problems(garbage))


class InstanceTest(unittest.TestCase):
    def test_the_tier_comes_from_the_install_path(self):
        for path, tier in (("/usr/local/lib/factory-prod", "factory-prod"), ("/usr/local/lib/factory-prod-two", "factory-prod-two"),
                           ("/usr/local/lib/factory-prod-x", "factory-prod-x")):
            self.assertEqual(fo.tier_of(pathlib.Path(path)), tier)
        for path in ("/usr/local/lib/production", "/usr/local/lib/factory-prod-", "/usr/local/lib/factory-prodx",
                     "/usr/local/lib/factory-prod-X", "/usr/local/lib/factory-prod-a-b", "/usr/local/lib/factory-prod-a.b",
                     "/usr/local/lib/factory-prod-abcdefghijklm"):
            self.assertIsNone(fo.tier_of(pathlib.Path(path)), path)

    def test_an_instance_named_like_another_tiers_own_names_is_refused(self):
        for name in ("op", "egress", "clone", "firewall", "runner", "step", "drift"):
            self.assertIsNone(fo.tier_of(pathlib.Path(f"/usr/local/lib/factory-prod-{name}")), name)

    def test_every_name_derives_from_the_tier(self):
        first, other = fo.tier_names("factory-prod"), fo.tier_names("factory-prod-two")
        self.assertEqual((first["instance"], other["instance"]), ("", "two"))
        self.assertEqual((first["runner_user"], first["operator_user"], first["egress_user"]),
                         ("factory-prod", "factory-prod-op", "factory-prod-egress"))
        self.assertEqual((other["runner_user"], other["operator_user"], other["egress_user"]),
                         ("factory-prod-two", "factory-prod-two-op", "factory-prod-two-egress"))
        self.assertEqual((first["command"], other["command"]), ("factory-op", "factory-op-two"))
        self.assertEqual((first["nft_table"], other["nft_table"]), ("factory_prod", "factory_prod_two"))
        self.assertEqual((first["firewall_unit"], other["runner_unit"]), ("factory-prod-firewall", "factory-prod-two-runner"))
        self.assertEqual(other["unit_prefix"], "factory-op-two-step-")
        self.assertEqual(other["config"], "/etc/factory-prod-two/config.json")
        self.assertEqual(other["lib_dir"], "/usr/local/lib/factory-prod-two")
        self.assertEqual(other["run_dir"], "/run/factory-prod-two")
        self.assertEqual(other["socket"], "/run/factory-prod-two/op.sock")

    def test_main_refuses_every_command_outside_a_tiers_install_path(self):
        for lib in ("/usr/local/lib/production", "/tmp/elsewhere/factory-prod"):
            for cmd in ("check", "serve", "baseline", "op", "egress", "pubkey"):
                with self.subTest(lib=lib, cmd=cmd), mock.patch.object(fo, "LIB", pathlib.Path(lib)), \
                        mock.patch("sys.stderr", new_callable=io.StringIO) as err:
                    self.assertEqual(fo.main(["factory_op.py", cmd, "x"]), 2)
                    self.assertIn("install path", err.getvalue())

    def test_the_configs_instance_and_paths_must_agree_with_the_tier(self):
        env = Env()
        self.addCleanup(env.close)
        names = fo.tier_names("factory-prod-two")
        cfg = {**env.cfg, "instance": "two", "operator_user": names["operator_user"], "lib_dir": names["lib_dir"],
               "ledger": names["state_dir"] + "/ledger.jsonl", "log_dir": names["log_dir"],
               "clone_dir": names["clone_base"] + "/app.git"}
        self.assertEqual(fo.config_problems(cfg, names), [])
        for key, value in (("instance", ""), ("operator_user", "factory-prod-op"), ("lib_dir", "/usr/local/lib/factory-prod"),
                           ("ledger", "/var/lib/factory-prod/ledger.jsonl"), ("clone_dir", "/var/lib/factory-prod-clone/app.git")):
            with self.subTest(key):
                self.assertTrue(fo.config_problems({**cfg, key: value}, names))

    def test_other_tiers_are_found_by_looking(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            for d in ("etc/factory-prod", "etc/factory-prod-two", "etc/factory-prodnope", "etc/factory-prod-B"):
                (root / d).mkdir(parents=True)
                (root / d / "config.json").write_text("{}")
            (root / "run" / "factory-prod-three").mkdir(parents=True)
            (root / "run" / "factory-prod-op").mkdir(parents=True)
            self.assertEqual(fo.other_tiers("factory-prod-two", root=root), ["factory-prod", "factory-prod-three"])
            self.assertEqual(fo.other_tiers("factory-prod", root=root), ["factory-prod-three", "factory-prod-two"])


class DigestTest(unittest.TestCase):
    def layouts(self, root):
        """The repository's .github/factory and the library setup installs from it, host module included."""
        factory, lib = root / "repo" / ".github" / "factory", root / "usr" / "factory-prod"
        (factory / "production").mkdir(parents=True)
        lib.mkdir(parents=True)
        for name in ("gates.py", "ed25519.py"):
            shutil.copy(fakes.FACTORY / name, factory / name)
            shutil.copy(fakes.FACTORY / name, lib / name)
        sources = {"factory_op.py": fakes.PROD / "factory_op.py", fo.HOST_MODULE: fakes.FAKE_HOST}
        for name, src in sources.items():
            shutil.copy(src, factory / "production" / name)
            shutil.copy(src, lib / name)
        for d in (factory / "production", lib):
            (d / "ops.json").write_text(json.dumps(fakes.CATALOG))
            (d / "config.json").write_text(json.dumps(fakes.make_config(root, lib)))  # beside a host module, in the digest
        return factory, lib

    def test_the_brokers_digest_of_its_installed_layout_is_the_repositorys(self):
        with tempfile.TemporaryDirectory() as tmp:
            factory, lib = self.layouts(pathlib.Path(tmp))
            repo_files = gates.repo_ops_files(factory)
            self.assertIn(fo.HOST_MODULE, repo_files)
            self.assertIn("config.json", repo_files)
            self.assertEqual(fo.installed_digest(gates, lib), gates.ops_digest(repo_files))
            (lib / fo.HOST_MODULE).write_text("# edited\n")
            self.assertNotEqual(fo.installed_digest(gates, lib), gates.ops_digest(repo_files))

    def test_the_host_module_name_is_the_one_gates_hashes(self):
        self.assertEqual(gates.BROKER_MODULES, (fo.HOST_MODULE,))


class StepPropertiesTest(unittest.TestCase):
    def test_the_sandbox_properties_are_a_constant_setup_can_compare(self):
        self.assertIsInstance(fo.STEP_PROPS, tuple)
        for prop in ("NoNewPrivileges=yes", "PrivateNetwork=yes", "RestrictAddressFamilies=AF_UNIX", "ProtectSystem=strict",
                     "ProtectHome=yes", "CapabilityBoundingSet=", "PrivateTmp=yes"):
            self.assertIn(prop, fo.STEP_PROPS)


if __name__ == "__main__":
    unittest.main()
