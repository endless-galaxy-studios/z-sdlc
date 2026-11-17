"""The broker's hardening after its security and correctness reviews (z-sdlc process/factory-broker.md, D4 rules 6, 7, 10,
12, 15): a step's sandbox as an allowlist (S2); the config.json root checks with is the hashed copy in the library (S3);
a package swapped mid-gate runs no further step (S4); host locks no other user can plant, hold or hang (S5); other tiers'
libraries hidden and the openssl that signs receipts root's alone (S8); a heartbeat that can't overrun its step's deadline,
and timeouts that hold its reads (C2); the environment approvals are checked in (C3); and the tier's own files (C5)."""

import io
import json
import os
import pathlib
import shutil
import stat
import tempfile
import threading
import types
import unittest
from unittest import mock

import fakes
from fakes import Env
import factory_op as fo
import gates
from test_broker_gate import GateBase, request
from test_broker_sandbox import HEALTH_OUT, SandboxHelper


# ---------------------------------------------------------------- S2: the step's sandbox is an allowlist

class AllowlistSandboxTest(SandboxHelper):
    def test_run_is_an_empty_read_only_tmpfs_with_only_the_egress_socket_and_the_step_dir_bound_in(self):
        self.run_op(self.sandbox(lambda d: (d / "out").write_text(HEALTH_OUT)))
        props = self.props(self.argvs[0])
        for prop in ("TemporaryFileSystem=/run:ro", "PrivateIPC=yes", "RestrictAddressFamilies=AF_UNIX", "PrivateNetwork=yes",
                     f"BindReadOnlyPaths={fo.EGRESS_SOCK}"):
            self.assertIn(prop, props)
        bound = [p.split("=", 1)[1] for p in props if p.startswith("BindPaths=")]
        self.assertEqual(len(bound), 1)
        self.assertTrue(bound[0].startswith(str(self.tmp / "steps")))
        self.assertFalse(any(p.startswith("ReadWritePaths=") for p in props))  # nothing else is writable

    def test_the_hosts_shared_memory_and_message_queues_are_hidden(self):
        for path in ("/dev/shm", "/dev/mqueue"):
            self.assertIn(path, fo.HIDDEN_ALWAYS)
        self.run_op(self.sandbox(lambda d: (d / "out").write_text(HEALTH_OUT)))
        hidden = next(p for p in self.props(self.argvs[0]) if p.startswith("InaccessiblePaths=")).split("=", 1)[1].split()
        self.assertIn("-/dev/shm", hidden)
        self.assertIn("-/dev/mqueue", hidden)

    def test_a_steps_config_is_the_hashed_copy(self):
        self.run_op(self.sandbox(lambda d: (d / "out").write_text(HEALTH_OUT)))
        argv = self.argvs[0]
        envs = [argv[i + 1] for i, a in enumerate(argv) if a == "-E"]
        self.assertIn(f"FACTORY_CONFIG={fo.NAMES['lib_config']}", envs)

    def test_the_systemd_floor_is_the_one_private_ipc_needs(self):
        self.assertIn("PrivateIPC=yes", fo.STEP_PROPS)
        self.assertEqual(fo.SYSTEMD_FLOOR, 248)


# ---------------------------------------------------------------- S3: the config root reads is the hashed copy

class HashedConfigTest(unittest.TestCase):
    def test_root_reads_the_librarys_copy_never_etcs(self):
        for tier in ("factory-prod", "factory-prod-b2"):
            n = fo.tier_names(tier)
            self.assertEqual(n["lib_config"], n["lib_dir"] + "/config.json")
            self.assertEqual(n["config"], n["etc_dir"] + "/config.json")  # where other tiers look for it
        self.assertEqual(str(fo.CONFIG), fo.NAMES["lib_config"])

    def test_an_edit_to_the_installed_copy_changes_the_digest(self):
        env = Env()
        self.addCleanup(env.close)
        shutil.copy(fakes.FAKE_HOST, env.lib / fo.HOST_MODULE)
        before = fo.installed_digest(gates, env.lib)
        self.assertIn("config.json", gates.installed_ops_files(env.lib))
        cfg = json.loads((env.lib / "config.json").read_text())
        cfg["approvers"].append(4242)
        (env.lib / "config.json").write_text(json.dumps(cfg))
        self.assertNotEqual(fo.installed_digest(gates, env.lib), before)

    def test_check_says_when_the_etc_copy_isnt_the_hashed_one(self):
        env = Env()
        self.addCleanup(env.close)
        key = env.tmp / "receipt.key"
        key.write_text(env.secret.hex())
        names = dict(fo.tier_names("factory-prod"), lib_config=str(env.lib / "config.json"), config=str(env.tmp / "etc.json"))
        (env.tmp / "etc.json").write_text((env.lib / "config.json").read_text())
        with mock.patch.object(fo, "KEY", key), mock.patch.object(fo, "config_problems", return_value=[]):
            problems = fo.check(env.cfg, env.cat, gates, names)
            self.assertFalse(any("isn't the same as" in p for p in problems), problems)
            (env.tmp / "etc.json").write_text("{}")
            problems = fo.check(env.cfg, env.cat, gates, names)
        self.assertTrue(any("isn't the same as" in p and "re-run setup" in p for p in problems), problems)


# ---------------------------------------------------------------- S4: a package swapped mid-gate runs nothing more

class PackageSwapTest(GateBase):
    def run_gate(self, steps, svc):
        return fo.execute(self.cfg, gates, self.env.cat, request(steps), "def", fakes.APPROVER, 55,
                          fo.ledger_entries(self.cfg["ledger"]), lambda r: gates.sign_receipt(self.env.secret, r), fakes.TOKEN,
                          svc, self.env.public, host_run="run1")

    def test_a_step_after_the_package_changed_doesnt_run_and_no_state_is_recorded(self):
        self.append_baseline(self.state)
        inner, ran = self.env.sandbox, []

        class Swapping:
            def run(s, name, *a, **kw):
                ran.append(name)
                res = inner.run(name, *a, **kw)
                if name == "health":  # the first step: then something rewrites the installed host module
                    (self.env.lib / fo.HOST_MODULE).write_text("# swapped in during the gate\n")
                return res
        svc = fo.Services(self.gh(), self.repo.git, lambda run: Swapping())
        steps = [{"id": "h1", "op": "health", "with": {}}, {"id": "h2", "op": "health", "with": {}}]
        receipt = self.run_gate(steps, svc)["receipt"]
        self.assertEqual(ran, ["capture-state", "health"])  # neither the second step nor the post capture ran
        self.assertEqual(receipt["status"], "failed")
        self.assertIn("installed operations changed during the gate", receipt["reason"])
        self.assertEqual([s["status"] for s in receipt["steps"]], ["done", "failed"])
        finish = fo.ledger_entries(self.cfg["ledger"])[-1]
        self.assertIsNone(finish["state_signed"])

    def test_an_unchanged_package_runs_every_step(self):
        self.append_baseline(self.state)
        steps = [{"id": "h1", "op": "health", "with": {}}, {"id": "h2", "op": "health", "with": {}}]
        receipt = self.run_gate(steps, self.services())["receipt"]
        self.assertEqual(receipt["status"], "done", receipt)

    def test_a_package_that_cant_be_read_is_refused_before_anything_runs(self):
        self.append_baseline(self.state)
        (self.env.lib / "ops.json").unlink()
        with self.assertRaises(fo.Refused) as cm:
            self.run_gate(None, self.services())
        self.assertIn("can't be read", str(cm.exception))


# ---------------------------------------------------------------- S5: host locks

class HostLockTest(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.dir = self.tmp / "locks"
        self.dir.mkdir(mode=0o755)
        self.dir.chmod(0o755)
        p = mock.patch.object(fo, "HOST_LOCK_OWNER", os.getuid())  # this test's user stands in for root
        p.start()
        self.addCleanup(p.stop)

    def opens(self, path):
        f = fo.open_host_lock(str(path))
        f.close()
        return True

    def refusal(self, path):
        with self.assertRaises(fo.LockBusy) as cm:
            fo.open_host_lock(str(path))
        return str(cm.exception)

    def test_a_lock_root_alone_can_open_is_used_and_one_it_creates_is_0600(self):
        self.assertTrue(self.opens(self.dir / "nightly.lock"))
        self.assertEqual(stat.S_IMODE((self.dir / "nightly.lock").stat().st_mode), 0o600)
        (self.dir / "open.lock").write_text("")
        (self.dir / "open.lock").chmod(0o644)
        self.dir.chmod(0o700)  # nobody else can reach it, whatever its mode
        self.assertTrue(self.opens(self.dir / "open.lock"))

    def test_a_directory_others_can_write_is_refused(self):
        for mode in (0o777, 0o1777, 0o775):
            with self.subTest(mode=oct(mode)):
                self.dir.chmod(mode)
                self.assertIn("isn't root's alone", self.refusal(self.dir / "nightly.lock"))
                self.assertFalse((self.dir / "nightly.lock").exists())

    def test_a_directory_another_user_owns_is_refused(self):
        with mock.patch.object(fo, "HOST_LOCK_OWNER", os.getuid() + 1):
            self.assertIn("isn't root's alone", self.refusal(self.dir / "nightly.lock"))

    def test_a_linked_directory_or_lock_is_refused(self):
        (self.tmp / "via").symlink_to(self.dir)
        self.assertIn("directory can't be opened", self.refusal(self.tmp / "via" / "nightly.lock"))
        (self.dir / "real.lock").write_text("")
        (self.dir / "real.lock").chmod(0o600)
        (self.dir / "link.lock").symlink_to(self.dir / "real.lock")
        self.assertIn("must be a regular file", self.refusal(self.dir / "link.lock"))

    def test_a_fifo_never_hangs_root_and_is_refused(self):
        os.mkfifo(self.dir / "fifo.lock", 0o600)
        self.assertIn("isn't a regular file", self.refusal(self.dir / "fifo.lock"))  # O_NONBLOCK: back at once

    def test_a_lock_another_user_owns_is_refused(self):
        (self.dir / "theirs.lock").write_text("")
        (self.dir / "theirs.lock").chmod(0o600)
        real = os.fstat

        def fstat(fd):
            st = real(fd)
            if stat.S_ISREG(st.st_mode):
                return types.SimpleNamespace(st_mode=st.st_mode, st_uid=st.st_uid + 1)
            return st
        with mock.patch.object(fo.os, "fstat", fstat):
            self.assertIn("isn't a regular file root owns", self.refusal(self.dir / "theirs.lock"))

    def test_a_lock_others_can_open_where_they_can_reach_it_is_refused(self):
        (self.dir / "loose.lock").write_text("")
        (self.dir / "loose.lock").chmod(0o644)
        self.assertIn("block every gate", self.refusal(self.dir / "loose.lock"))

    def test_the_broker_lock_opens_host_locks_this_way(self):
        """Through broker_lock, as a gate takes its host locks: a planted FIFO is refused at once, never waited on, and a lock
        in a directory others can write is refused before it is created."""
        fakes.no_live_steps(self)
        for name, value in (("LOCK", self.tmp / "run" / "broker.lock"), ("STEPS_DIR", self.tmp / "steps")):
            p = mock.patch.object(fo, name, value)
            p.start()
            self.addCleanup(p.stop)
        os.mkfifo(self.dir / "planted.lock", 0o600)
        box = {}

        def take():
            try:
                with fo.broker_lock(0, steps_dir=self.tmp / "steps", host_locks=[str(self.dir / "planted.lock")]):
                    box["entered"] = True
            except fo.LockBusy as e:
                box["refused"] = str(e)
        t = threading.Thread(target=take, daemon=True)
        t.start()
        t.join(5)
        if t.is_alive():  # free the blocked open, so the test ends: a writer opening the FIFO unblocks a reader
            os.close(os.open(self.dir / "planted.lock", os.O_WRONLY | os.O_NONBLOCK))
            t.join(5)
            self.fail("root's open of a planted FIFO hung")
        self.assertNotIn("entered", box)
        self.assertIn("isn't a regular file", box["refused"])
        self.dir.chmod(0o1777)
        with self.assertRaises(fo.LockBusy) as cm:
            with fo.broker_lock(0, steps_dir=self.tmp / "steps", host_locks=[str(self.dir / "nightly.lock")]):
                self.fail("took a lock in a world-writable directory")
        self.assertIn("isn't root's alone", str(cm.exception))
        self.assertFalse((self.dir / "nightly.lock").exists())

    def test_the_catalog_refuses_directories_other_users_write_by_convention(self):
        for path in ("/run/lock/nightly.lock", "/var/lock/nightly.lock", "/run/user/1000/x.lock", "/tmp/x.lock", "/run/",
                     "relative.lock"):
            with self.subTest(path=path):
                problems = fo.broker_problems(fakes.load(fakes.catalog_dict(broker__host_locks=[path])))
                self.assertTrue(any("broker.host_locks" in p for p in problems), problems)
        for path in ("/run/nightly.lock", "/run/backup/nightly.lock"):
            self.assertEqual(fo.broker_problems(fakes.load(fakes.catalog_dict(broker__host_locks=[path]))), [], path)


# ---------------------------------------------------------------- S8: other tiers' libraries; the openssl that signs

class OtherLibrariesTest(unittest.TestCase):
    def test_another_tiers_library_is_hidden_from_this_ones_steps(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "etc" / "factory-prod-b2").mkdir(parents=True)
            (root / "etc" / "factory-prod-b2" / "config.json").write_text("{}")
            cfg = fakes.make_config(root, root / "lib")
            hidden = fo.hidden_paths(cfg, own="factory-prod", root=root).split()
            self.assertIn("-/usr/local/lib/factory-prod-b2", hidden)
            self.assertNotIn("-/usr/local/lib/factory-prod", hidden)  # its own, which its steps run from


class OpensslTest(unittest.TestCase):
    def stat_of(self, table):
        def fn(path):
            uid, mode = table.get(path, (0, 0o755))
            return types.SimpleNamespace(st_uid=uid, st_mode=stat.S_IFREG | mode)
        return fn

    # Paths that exist nowhere, so realpath leaves them as they are.
    EXE, BIN = "/nonexistent-root/bin/openssl", "/nonexistent-root/bin"

    def test_root_owned_and_not_writable_by_others_passes(self):
        self.assertEqual(fo.openssl_problems([self.EXE], stat_fn=self.stat_of({}), lstat_fn=self.stat_of({})), [])

    def test_a_program_or_directory_another_user_can_change_is_a_problem(self):
        for table, what in (({self.EXE: (1000, 0o755)}, "the program"), ({self.EXE: (0, 0o775)}, "the program"),
                            ({self.BIN: (0, 0o777)}, "its directory"), ({self.BIN: (1000, 0o755)}, "its directory")):
            with self.subTest(table=table):
                problems = fo.openssl_problems([self.EXE], stat_fn=self.stat_of(table), lstat_fn=self.stat_of({}))
                self.assertTrue(any(what in p and "root-owned" in p for p in problems), problems)
        problems = fo.openssl_problems([self.EXE], stat_fn=self.stat_of({}), lstat_fn=self.stat_of({self.EXE: (1000, 0o777)}))
        self.assertTrue(any("a link another user owns" in p for p in problems), problems)

    def test_every_candidate_ed25519_may_run_is_checked(self):
        import ed25519
        other = "/nonexistent-root/opt/openssl"
        problems = fo.openssl_problems([self.EXE, other], stat_fn=self.stat_of({other: (1000, 0o755)}), lstat_fn=self.stat_of({}))
        self.assertTrue(any(other in p for p in problems))
        self.assertTrue(callable(ed25519._openssls))  # the list it signs with, in order
        self.assertEqual(fo.openssl_problems([], stat_fn=self.stat_of({})), ["no openssl to sign receipts with (ed25519.py needs OpenSSL 3)"])

    def test_check_runs_it(self):
        env = Env()
        self.addCleanup(env.close)
        key = env.tmp / "receipt.key"
        key.write_text(env.secret.hex())
        with mock.patch.object(fo, "KEY", key), mock.patch.object(fo, "openssl_problems", return_value=["openssl: planted"]):
            self.assertIn("openssl: planted", fo.check(env.cfg, env.cat, gates))


# ---------------------------------------------------------------- C2: heartbeat reads that fit the step

class HeartbeatDeadlineTest(unittest.TestCase):
    def env_with(self, ttl, health_s):
        cat = fakes.catalog_dict(broker__heartbeat_ttl_s=ttl)
        cat["operations"]["health"]["timeout_s"] = health_s
        env = Env(cat=cat)
        self.addCleanup(env.close)
        return env

    def test_a_strict_heartbeat_fails_its_step_rather_than_sleep_past_the_deadline(self):
        env = self.env_with(ttl=120, health_s=100)  # a catalog the rules below refuse, run anyway
        with mock.patch.object(fo, "broker_problems", return_value=[]):
            res = env.run_op("health", release_head="")
        self.assertEqual(res.status, "failed")  # a failed step, not a timed-out run that blocks every gate
        self.assertIn("would pass the operation's deadline", res.why)
        self.assertLess(env.clock.t, 100 / fo.DEADLINE_MARGIN)

    def test_a_timeout_that_holds_the_reads_passes(self):
        env = self.env_with(ttl=120, health_s=300)
        self.assertEqual(fo.broker_problems(env.cat), [])
        self.assertEqual(env.run_op("health", release_head="").status, "done")

    def test_a_patient_wait_never_sleeps_past_its_deadline_either(self):
        env = self.env_with(ttl=60, health_s=600)
        clock = env.clock
        ctx = types.SimpleNamespace(broker={"heartbeat_ttl_s": 60}, deadline=fo.Deadline(3, clock), clock=clock)
        host = types.SimpleNamespace(heartbeat=lambda *a: None)
        dep = fo.Deployment("dep-1", None, "success", clock.now())
        with self.assertRaises(fo.StepFailed) as cm:
            fo.heartbeat_evidence(ctx, host, "jobs", dep, patient=True)
        self.assertIn("deadline", str(cm.exception))
        self.assertEqual(clock.t, 0)  # the next pause (POLL_S) didn't fit, so it wasn't slept

    def test_health_must_hold_its_heartbeat_reads(self):
        need = -(-11 * (60 + 1 + 2 * fo.REQUEST_TIMEOUT_S) // 10)  # one heartbeat service in the test catalog
        for timeout, ok in ((need, True), (need - 1, False), (600, True)):
            with self.subTest(timeout=timeout):
                cat = fakes.catalog_dict()
                cat["operations"]["health"]["timeout_s"] = timeout
                problems = fo.broker_problems(fakes.load(cat))
                self.assertEqual(problems == [], ok, problems)
                if not ok:
                    self.assertIn(f"health's timeout_s must be at least {need}", problems[0])
        two = fakes.catalog_dict()
        two["broker"]["services"]["web"]["evidence"] = "both"
        two["operations"]["health"]["timeout_s"] = need
        self.assertTrue(any("health's timeout_s must be at least" in p for p in fo.broker_problems(fakes.load(two))))

    def test_release_waits_phases_leave_room_for_its_heartbeat_reads(self):
        room = 60 + fo.POLL_S + 2 * fo.REQUEST_TIMEOUT_S
        for after_grace, ok in ((room, True), (room - 1, False)):
            with self.subTest(after_grace=after_grace):
                cat = fakes.catalog_dict(broker__release_wait_phases={"grace_s": 120, "evidence_s": after_grace})
                problems = fo.broker_problems(fakes.load(cat))
                self.assertEqual(problems == [], ok, problems)
                if not ok:
                    self.assertIn("leave no room for the heartbeat evidence", problems[0])

    def test_without_a_heartbeat_service_neither_rule_applies(self):
        cat = fakes.catalog_dict(broker__heartbeat_ttl_s=None, broker__release_wait_phases={"grace_s": 120})
        cat["broker"]["services"]["jobs"]["evidence"] = "reports"
        cat["operations"]["health"]["timeout_s"] = 60
        self.assertEqual(fo.broker_problems(fakes.load(cat)), [])


# ---------------------------------------------------------------- C3: the environment approvals are checked in

class EnvironmentTest(unittest.TestCase):
    def cfg(self, **changes):
        cfg = fakes.make_config("/tmp/x", "/tmp/x/lib")
        cfg.update(changes)
        return cfg

    def approvals(self, env_name):
        routes = {"actions/runs/55/approvals": [{"state": "approved", "user": {"id": fakes.APPROVER},
                                                 "environments": [{"name": env_name}]}]}
        return fo.GitHub(fakes.REPO_NAME, fakes.TOKEN, opener=fakes.FakeOpener(fakes.REPO_NAME, routes))

    def test_the_default_is_the_factorys_name(self):
        self.assertEqual(fo.environment_of(self.cfg()), "factory-production")
        self.assertEqual(fo.approved(self.approvals("factory-production"), self.cfg(), 55), fakes.APPROVER)

    def test_a_renamed_environment_is_the_one_approvals_count_in(self):
        cfg = self.cfg(environment="prod-gate")
        self.assertEqual(fo.config_problems(cfg), [])
        self.assertEqual(fo.approved(self.approvals("prod-gate"), cfg, 55), fakes.APPROVER)
        self.assertIsNone(fo.approved(self.approvals("factory-production"), cfg, 55))

    def test_an_environment_that_isnt_a_name_is_refused(self):
        for value in ("", "has space", 5, None, "x" * 101):
            with self.subTest(value=value):
                self.assertTrue(any("environment" in p for p in fo.config_problems(self.cfg(environment=value))))


# ---------------------------------------------------------------- C5: the tier's own files

class TierFilesTest(unittest.TestCase):
    def test_no_secret_may_take_a_file_of_the_tiers_own(self):
        self.assertIn("github-deploy-key.pub", fo.TIER_FILES)
        for name in sorted(fo.TIER_FILES):
            with self.subTest(name=name):
                cat = fakes.catalog_dict()
                cat["broker"]["secrets"]["token"]["file"] = name
                self.assertTrue(any("not one of the tier's own" in p for p in fo.broker_problems(fakes.load(cat))))


# ---------------------------------------------------------------- N1: a command runs on the package it loaded, or not at all

class PackageSnapshotTest(unittest.TestCase):
    """A command loads config.json, ops.json and its code from one read of the installed package; once it holds the lock, a
    package that changed while it waited (setup ran) refuses it, before anything runs."""

    def setUp(self):
        self.env = Env()
        self.addCleanup(self.env.close)
        self.cfg = self.env.cfg
        for name, value in (("LOCK", self.env.tmp / "run" / "broker.lock"), ("STEPS_DIR", self.env.tmp / "steps")):
            p = mock.patch.object(fo, name, value)
            p.start()
            self.addCleanup(p.stop)
        fakes.no_live_steps(self)
        self.loaded = fo.Package(gates, self.env.lib, fo.installed_digest(gates, self.env.lib))

    def setup_ran(self):
        ops = self.env.lib / "ops.json"
        ops.write_text(ops.read_text() + "\n")  # the package setup installed while the command waited

    def test_an_unchanged_package_runs(self):
        self.assertEqual(fo.cmd_health(self.cfg, self.env.cat, self.env.svc_factory(), fakes.Console(), clock=self.env.clock,
                                       stamp=self.env.tmp / "stamp", package=self.loaded), 0)

    def test_every_command_that_waited_while_setup_ran_runs_nothing(self):
        fo.ledger_append(self.cfg["ledger"], {"event": "start", "run": "r9", "repo": self.cfg["repo"], "pr": 7, "issue": 3,
                                              "gate": "G1", "attempt": 1, "digest": "d" * 64, "github_run": 5})
        self.setup_ran()
        svc, pkg = self.env.svc_factory(), self.loaded
        calls = {
            "health": lambda: fo.cmd_health(self.cfg, self.env.cat, svc, fakes.Console(), clock=self.env.clock,
                                            stamp=self.env.tmp / "stamp", package=pkg),
            "baseline": lambda: fo.cmd_baseline(self.cfg, gates, self.env.cat, self.env.secret, "n", False, svc, fakes.Console(),
                                                package=pkg),
            "diagnose": lambda: fo.cmd_diagnose(self.cfg, self.env.cat, "host-check", svc, fakes.Console(), package=pkg),
            "fetch": lambda: fo.cmd_fetch(self.cfg, self.env.repo.git, fakes.Console(), package=pkg),
            "resolve": lambda: fo.cmd_resolve(self.cfg, gates, self.env.secret, "r9", "n", package=pkg),
            "resolve --torn-line": lambda: fo.cmd_resolve_torn(self.cfg, gates, self.env.secret, "n", package=pkg),
        }
        for name, call in calls.items():
            with self.subTest(name), self.assertRaises(fo.PackageChanged) as cm:
                call()
            self.assertIn("changed while this command waited", str(cm.exception))
        issues, line = fo.drift_check(self.cfg, gates, self.env.cat, self.env.secret, svc, package=pkg)
        self.assertIsNone(issues)
        self.assertIn("changed while this command waited", line)
        self.assertEqual(self.env.sandbox.runs, [])
        self.assertEqual(fo.unfinished(fo.ledger_entries(self.cfg["ledger"])), ["r9"])

    def test_a_gate_that_waited_while_setup_ran_is_a_signed_refusal(self):
        self.assertEqual(fo.cmd_baseline(self.cfg, gates, self.env.cat, self.env.secret, "n", False, self.env.svc_factory(),
                                         fakes.Console()), 0)
        routes, _ = fakes.gate_routes(self.env)
        self.setup_ran()
        routes, _ = fakes.gate_routes(self.env)  # the title's digest is the new package's: only the snapshot tells them apart
        gh = fo.GitHub(self.cfg["repo"], fakes.TOKEN, opener=fakes.FakeOpener(self.cfg["repo"], routes))
        signed = fo.serve_one(self.cfg, gates, self.env.cat, json.dumps({"run_id": 55, "pr": 7, "token": fakes.TOKEN}),
                              self.env.secret, svc_factory=lambda cfg, token: self.env.services(gh), package=self.loaded)
        receipt = gates.verify_receipt(self.env.public, signed)
        self.assertEqual(receipt["status"], "refused")
        self.assertIn("changed while this command waited", receipt["reason"])
        self.assertIn("factory:gate-retry", receipt["reason"])
        self.assertFalse(any(e.get("event") == "start" for e in fo.ledger_entries(self.cfg["ledger"])))

    def test_a_package_that_cant_be_read_any_more_is_refused(self):
        (self.env.lib / "ops.json").unlink()
        with self.assertRaises(fo.PackageChanged):
            fo.cmd_fetch(self.cfg, self.env.repo.git, fakes.Console(), package=self.loaded)

    def test_main_hands_every_command_the_package_it_loaded(self):
        key = self.env.tmp / "receipt.key"
        key.write_text(self.env.secret.hex())
        loaded = fo.Loaded((self.cfg, gates, self.env.cat, []))
        loaded.package = self.loaded
        self.setup_ran()

        def run(*argv):
            out, err = io.StringIO(), io.StringIO()
            with mock.patch.object(fo, "LIB", pathlib.Path("/usr/local/lib/factory-prod")), \
                    mock.patch("os.geteuid", return_value=0), mock.patch.object(fo, "install_root_signals"), \
                    mock.patch.object(fo, "load", return_value=loaded), mock.patch.object(fo, "KEY", key), \
                    mock.patch.object(fo, "real_services", lambda c, token, cat: self.env.services(fakes.github_for(c, self.env.repo, []))), \
                    mock.patch.object(fo, "Git", lambda clone: self.env.repo.git), \
                    mock.patch("sys.stdout", out), mock.patch("sys.stderr", err):
                rc = fo.main(["factory_op.py", *argv])
            return rc, out.getvalue() + err.getvalue()
        for argv in (["health"], ["diagnose", "host-check"], ["fetch"], ["baseline", "n"], ["drift-check"],
                     ["resolve", "r9", "failed", "n"], ["resolve", "--torn-line", "n"]):
            with self.subTest(argv=argv):
                rc, text = run(*argv)
                self.assertEqual(rc, 1, text)
                self.assertIn("changed while this command waited", text)
        with mock.patch.object(fo, "serve_conn") as serve, mock.patch("socket.socket"), mock.patch("os.dup", return_value=9):
            run("serve")
        self.assertIs(serve.call_args.kwargs["package"], self.loaded)


# ---------------------------------------------------------------- N2: a terminal can't kill a root command uncleanly

class SignalsTest(unittest.TestCase):
    def test_hangup_and_quit_unwind_and_the_job_control_stops_are_ignored(self):
        import signal
        old = {n: signal.getsignal(n) for n in signal.valid_signals()}
        self.addCleanup(lambda: [signal.signal(n, h) for n, h in old.items() if h is not None and n not in
                                 (signal.SIGKILL, signal.SIGSTOP)])
        fo.install_root_signals()
        # Every signal sudo relays from the agent that ran the command, and every other one whose default ends it.
        for n in ("SIGUSR1", "SIGUSR2", "SIGALRM", "SIGVTALRM", "SIGPROF", "SIGXCPU"):
            self.assertIs(signal.getsignal(getattr(signal, n)), fo.sigterm_to_exit, n)
        left = {getattr(signal, n) for n in fo.NOT_ENDING_SIGNALS + fo.FAULT_SIGNALS + fo.IGNORED_SIGNALS if hasattr(signal, n)}
        for num in signal.valid_signals():
            if num not in left:
                self.assertIs(signal.getsignal(num), fo.sigterm_to_exit, signal.Signals(num).name if num in
                              signal.Signals._value2member_map_ else num)
        self.assertEqual(signal.getsignal(signal.SIGPIPE), signal.SIG_IGN)
        for n in ("SIGTERM", "SIGHUP", "SIGQUIT"):
            self.assertIs(signal.getsignal(getattr(signal, n)), fo.sigterm_to_exit, n)
        for n in ("SIGINT", "SIGTSTP", "SIGTTIN", "SIGTTOU"):
            self.assertEqual(signal.getsignal(getattr(signal, n)), signal.SIG_IGN, n)
        with self.assertRaises(SystemExit) as cm:
            fo.sigterm_to_exit(signal.SIGHUP, None)
        self.assertEqual(cm.exception.code, 128 + signal.SIGHUP)


class HealthStampTest(unittest.TestCase):
    def test_the_stamp_is_touched_before_the_step_starts(self):
        env = Env()
        self.addCleanup(env.close)
        for name, value in (("LOCK", env.tmp / "run" / "broker.lock"), ("STEPS_DIR", env.tmp / "steps")):
            p = mock.patch.object(fo, name, value)
            p.start()
            self.addCleanup(p.stop)
        fakes.no_live_steps(self)
        stamp, seen = env.tmp / "stamp", []

        class Killed:
            def run(s, *a, **kw):
                seen.append(stamp.exists() and stamp.stat().st_mtime)
                raise SystemExit(129)  # a hangup while the step runs
        svc = lambda cfg, token: fo.Services(None, env.repo.git, lambda run: Killed())  # noqa: E731
        with self.assertRaises(SystemExit):
            fo.cmd_health(env.cfg, env.cat, svc, fakes.Console(), clock=env.clock, stamp=stamp)
        self.assertEqual(len(seen), 1)
        self.assertAlmostEqual(seen[0], env.clock.time(), delta=1)  # a run that never ends still counts against the minute
        with self.assertRaises(fo.Refused) as cm:
            fo.cmd_health(env.cfg, env.cat, env.svc_factory(), fakes.Console(), clock=env.clock, stamp=stamp)
        self.assertIn("less than 60 s ago", str(cm.exception))


# ---------------------------------------------------------------- S8: the key is handed only to root's own openssl

class OpensslGuardTest(unittest.TestCase):
    def fresh_ed25519(self):
        """A private copy of ed25519.py, so its list can be changed without touching the one every other test signs with."""
        import importlib.util
        spec = importlib.util.spec_from_file_location("ed25519_under_test", str(fakes.FACTORY / "ed25519.py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def planted(self, tmp):
        """An openssl this test's user owns: running it leaves a mark."""
        exe, mark = pathlib.Path(tmp) / "openssl", pathlib.Path(tmp) / "ran"
        exe.write_text(f"#!/bin/sh\ntouch {mark}\nexit 1\n")
        exe.chmod(0o755)
        return str(exe), mark

    def test_an_openssl_root_doesnt_own_is_never_handed_the_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe, mark = self.planted(tmp)
            module = self.fresh_ed25519()
            module._openssls = lambda: [exe]
            fo.guard_openssl(module)
            with self.assertRaises(RuntimeError):
                module.public_key(bytes(range(32)))
            self.assertFalse(mark.exists())
            # ...where without the guard it would be (the mark proves the probe can see a run).
            unguarded = self.fresh_ed25519()
            unguarded._openssls = lambda: [exe]
            with self.assertRaises(RuntimeError):
                unguarded.public_key(bytes(range(32)))
            self.assertTrue(mark.exists())

    def test_check_still_reports_a_candidate_the_guard_skips(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe, _ = self.planted(tmp)
            module = self.fresh_ed25519()
            module._openssls = lambda: [exe]
            fo.guard_openssl(module)
            self.assertEqual(module._openssls(), [])  # never run...
            problems = fo.openssl_problems(module=module)
        self.assertTrue(any(exe in p and "root-owned" in p for p in problems), problems)  # ...and still reported

    def test_the_guard_keeps_the_candidates_that_pass_and_is_installed_once(self):
        module = self.fresh_ed25519()
        module._openssls = lambda: ["/a/openssl", "/b/openssl"]
        fo.guard_openssl(module, ok=lambda exe: exe == "/b/openssl")
        self.assertEqual(module._openssls(), ["/b/openssl"])
        fo.guard_openssl(module, ok=lambda exe: False)  # already guarded: unchanged
        self.assertEqual(module._openssls(), ["/b/openssl"])

    def test_a_check_that_cant_sign_says_so(self):
        env = Env()
        self.addCleanup(env.close)
        key = env.tmp / "receipt.key"
        key.write_text(env.secret.hex())
        import ed25519
        with mock.patch.object(ed25519, "_openssls", return_value=[]):
            self.assertTrue(any("receipts can't be signed" in p for p in fo.key_problems(env.cfg, key)))


# ---------------------------------------------------------------- polls never sleep past the step's deadline

class PollPauseTest(unittest.TestCase):
    def test_a_patient_reports_wait_sleeps_no_further_than_its_deadline(self):
        clock = fakes.FakeClock()
        ctx = types.SimpleNamespace(deadline=fo.Deadline(3, clock), clock=clock)

        def reports(*a):
            raise fo.Unavailable("no usable answer")
        with self.assertRaises(fo.StepFailed) as cm:
            fo.reports_evidence(ctx, types.SimpleNamespace(reports=reports), "web", "dep-0001", patient=True)
        self.assertIn("deadline", str(cm.exception))
        self.assertEqual(clock.t, 3)  # not POLL_S (5)

    def test_the_release_wait_sleeps_no_further_than_its_deadline(self):
        cat = fakes.catalog_dict()
        cat["operations"]["release-wait"]["timeout_s"] = 140  # below the phases' rule: run anyway
        env = Env(cat=cat)
        self.addCleanup(env.close)
        head = env.repo.merge_pr({"web/app.txt": "w2"})
        env.repo.fetch()
        env.world.add("jobs", "SKIPPED", head)
        env.world.add("web", "BUILDING", head)  # never finishes
        with mock.patch.object(fo, "broker_problems", return_value=[]):
            res = env.sandbox.run("release-wait", env.cat["operations"]["release-wait"], {"sha": head}, "t",
                                  env.tmp / "logs" / "rw.log", head)
        self.assertEqual(res.status, "failed")
        self.assertIn("deadline", res.why)
        self.assertLessEqual(env.clock.t, 140 / fo.DEADLINE_MARGIN + 1e-6)


if __name__ == "__main__":
    unittest.main()
