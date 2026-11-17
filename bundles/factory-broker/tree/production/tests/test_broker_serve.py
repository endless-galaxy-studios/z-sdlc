"""Serving a request (z-sdlc process/factory.md D4 rules 7-9, 12): the caller must be the runner user, one deadline for the
request line, signed refusals, never twice, an interrupted run blocks every gate until `resolve`; the broker's lock and
the block's host locks; health's rate limit; and the root commands. Carried over from the third project's broker tests
(test_review.py, test_round2.py)."""

import fcntl
import io
import json
import os
import socket
import stat
import threading
import time
import unittest
from unittest import mock

import fakes
from fakes import Env, TOKEN
import factory_op as fo
import gates


class EnvBase(unittest.TestCase):
    def setUp(self):
        self.env = Env()
        self.addCleanup(self.env.close)
        self.cfg = self.env.cfg
        self.lock = self.env.tmp / "run" / "broker.lock"
        for name, value in (("LOCK", self.lock), ("STEPS_DIR", self.env.tmp / "steps")):
            p = mock.patch.object(fo, name, value)
            p.start()
            self.addCleanup(p.stop)
        fakes.no_live_steps(self)

    def hold(self, path=None):
        path = path or self.lock
        path.parent.mkdir(parents=True, exist_ok=True)
        held = open(path, "a")
        self.addCleanup(held.close)
        fcntl.flock(held, fcntl.LOCK_EX)

    def baseline(self):
        self.assertEqual(fo.cmd_baseline(self.cfg, gates, self.env.cat, self.env.secret, "n", False, self.env.svc_factory(),
                                         fakes.Console()), 0)

    def serve(self, routes=None, cat=None, run_id=55):
        routes = routes if routes is not None else fakes.gate_routes(self.env)[0]
        gh = fo.GitHub(self.cfg["repo"], TOKEN, opener=fakes.FakeOpener(self.cfg["repo"], routes))
        signed = fo.serve_one(self.cfg, gates, cat or self.env.cat, json.dumps({"run_id": run_id, "pr": 7, "token": TOKEN}),
                              self.env.secret, svc_factory=lambda cfg, token: self.env.services(gh))
        return gates.verify_receipt(self.env.public, signed)


class ServeConnTest(EnvBase):
    def setUp(self):
        super().setUp()
        self.a, self.b = socket.socketpair()
        self.addCleanup(self.a.close)
        self.addCleanup(self.b.close)

    def serve_conn(self, uid, runner=1000, timeout=5, unusable=None):
        return fo.serve_conn(self.cfg, gates, self.env.cat, self.b, self.env.secret, runner_uid=runner,
                             peer_uid_fn=lambda sock: uid, read_timeout=timeout, unusable=unusable)

    def receipt(self):
        return gates.verify_receipt(self.env.public, json.loads(self.a.recv(1 << 16)))

    def test_a_caller_that_is_not_the_runner_user_is_refused(self):
        self.a.sendall(json.dumps({"run_id": 1, "pr": 2, "token": TOKEN}).encode() + b"\n")
        self.serve_conn(uid=4242)
        receipt = self.receipt()
        self.assertEqual(receipt["status"], "refused")
        self.assertIn("runner", receipt["reason"])

    def test_the_runner_user_gets_through_to_the_normal_checks(self):
        self.a.sendall(b"garbage\n")
        self.serve_conn(uid=1000)
        self.assertIn("malformed", self.receipt()["reason"])

    def test_a_silent_caller_times_out(self):
        self.serve_conn(uid=1000, timeout=0.2)
        self.assertIn("no request", self.receipt()["reason"])

    def test_what_roots_load_found_is_a_signed_refusal(self):
        self.a.sendall(json.dumps({"run_id": 1, "pr": 2, "token": TOKEN}).encode() + b"\n")
        self.serve_conn(uid=1000, unusable=["ops.json isn't usable: rollbacks must be false"])
        receipt = self.receipt()
        self.assertEqual(receipt["status"], "refused")
        self.assertIn("rollbacks must be false", receipt["reason"])
        self.assertTrue(gates.unbound_refusal(receipt))

    def test_deeply_nested_json_is_a_malformed_request_not_a_crash(self):
        signed = fo.serve_one(self.cfg, gates, self.env.cat, "[" * 200000, self.env.secret)
        self.assertIn("malformed", gates.verify_receipt(self.env.public, signed)["reason"])

    def test_the_peer_uid_helper_reads_so_peercred(self):
        if not hasattr(socket, "SO_PEERCRED"):
            self.skipTest("Linux only")
        self.assertEqual(fo.peer_uid(self.a), os.getuid())

    def test_sigterm_becomes_system_exit_so_cleanup_runs(self):
        with self.assertRaises(SystemExit):
            fo.sigterm_to_exit(15, None)


class ReadDeadlineTest(unittest.TestCase):
    def test_one_deadline_covers_the_whole_request_read(self):
        a, b = socket.socketpair()
        self.addCleanup(a.close)
        self.addCleanup(b.close)
        stop = threading.Event()

        def trickle():
            while not stop.is_set():
                try:
                    a.sendall(b"x")
                except OSError:
                    return
                time.sleep(0.1)
        threading.Thread(target=trickle, daemon=True).start()
        box = {}
        started = time.monotonic()
        reader = threading.Thread(target=lambda: box.update(line=fo.read_request_line(b, timeout=0.5)), daemon=True)
        reader.start()
        reader.join(3)  # a per-recv timeout would keep resetting and read for as long as the sender trickles
        stop.set()
        self.assertFalse(reader.is_alive(), "the read must end at its deadline")
        self.assertIsNone(box.get("line", "unset"))
        self.assertLess(time.monotonic() - started, 2)

    def test_a_prompt_request_is_read(self):
        a, b = socket.socketpair()
        self.addCleanup(a.close)
        self.addCleanup(b.close)
        a.sendall(b'{"x": 1}\n')
        self.assertEqual(fo.read_request_line(b, timeout=2), '{"x": 1}\n')


class ServeOneTest(EnvBase):
    def test_a_gate_runs_once_and_its_digest_returns_the_stored_receipt(self):
        self.baseline()
        first = self.serve()
        self.assertEqual(first["status"], "done", first.get("reason"))
        runs = len(self.env.sandbox.runs)
        again = self.serve()
        self.assertEqual(again, first)
        self.assertEqual(len(self.env.sandbox.runs), runs)  # never twice

    def test_an_interrupted_run_blocks_every_gate_until_resolve(self):
        self.baseline()
        fo.ledger_append(self.cfg["ledger"], {"event": "start", "run": "r9", "repo": self.cfg["repo"], "pr": 7, "issue": 3,
                                              "gate": "G0", "attempt": 1, "digest": "e" * 64, "github_run": 5, "kind": "ops",
                                              "head": "a" * 40, "at": "x", "approver": 1})
        receipt = self.serve()
        self.assertEqual(receipt["status"], "refused")
        self.assertIn("interrupted (r9)", receipt["reason"])
        self.assertIn(f"sudo {fo.USER_AGENT} resolve r9 failed", receipt["reason"])
        self.assertEqual(fo.cmd_resolve(self.cfg, gates, self.env.secret, "r9", "checked by hand"), 0)
        finish = fo.ledger_entries(self.cfg["ledger"])[-1]
        self.assertTrue(finish["resolved"])
        self.assertEqual(gates.verify_receipt(self.env.public, finish["signed"])["status"], "failed")
        self.assertEqual(self.serve()["status"], "done")

    def test_resolve_refuses_a_run_that_isnt_unfinished(self):
        with self.assertRaises(fo.Refused):
            fo.cmd_resolve(self.cfg, gates, self.env.secret, "nope", "n")

    def test_no_recorded_state_is_a_signed_refusal(self):
        receipt = self.serve()
        self.assertEqual(receipt["status"], "refused")
        self.assertIn("baseline", receipt["reason"])
        self.assertEqual((receipt["pr"], receipt["gate"]), (7, "G1"))

    def test_a_run_that_isnt_approved_is_refused(self):
        self.baseline()
        routes, _ = fakes.gate_routes(self.env)
        routes["actions/runs/55/approvals"] = [{"state": "approved", "user": {"id": 999}, "environments": [{"name": "factory-production"}]}]
        receipt = self.serve(routes)
        self.assertEqual(receipt["status"], "refused")
        self.assertIn("no approver", receipt["reason"])

    def test_a_changed_package_digest_refuses_and_says_to_rerun_setup(self):
        self.baseline()
        routes, _ = fakes.gate_routes(self.env)
        (self.env.lib / fo.HOST_MODULE).write_text("# installed after approval\n")
        receipt = self.serve(routes)
        self.assertEqual(receipt["status"], "refused")
        self.assertIn("re-runs setup", receipt["reason"])

    def test_a_held_lock_is_a_signed_refusal(self):
        self.hold()
        with mock.patch.object(fo, "LOCK_WAIT_S", 0):
            receipt = self.serve()
        self.assertEqual(receipt["status"], "refused")
        self.assertIn("lock", receipt["reason"])
        self.assertTrue(gates.unbound_refusal(receipt))

    def test_a_held_host_lock_refuses_before_anything_runs(self):
        host_lock = self.env.tmp / "run" / "nightly.lock"
        cat = fakes.load(fakes.catalog_dict(broker__host_locks=["/run/nightly.lock"]))
        self.assertEqual(fo.broker_problems(cat), [])
        cat["broker"]["host_locks"] = [str(host_lock)]  # the same rule, at a path this test can create
        self.baseline()
        self.hold(host_lock)
        # Changed with the fix that a host lock must be root's alone: this test's user stands in for root, and the lock is
        # one no one else can open.
        host_lock.chmod(0o600)
        with mock.patch.object(fo, "LOCK_WAIT_S", 0), mock.patch.object(fo, "broker_problems", return_value=[]), \
                mock.patch.object(fo, "HOST_LOCK_OWNER", os.getuid()):
            receipt = self.serve(cat=cat)
        self.assertEqual(receipt["status"], "refused")
        self.assertIn("host's own job", receipt["reason"])
        self.assertFalse(any(e.get("event") == "start" for e in fo.ledger_entries(self.cfg["ledger"])))


class LockAndHealthStampTest(EnvBase):
    def test_lock_file_is_created_0600_in_a_0755_run_dir(self):
        with fo.broker_lock(0, steps_dir=self.env.tmp / "steps"):
            pass
        self.assertEqual(stat.S_IMODE(self.lock.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.lock.parent.stat().st_mode), 0o755)

    def test_a_lock_file_that_exists_with_a_loose_mode_ends_0600(self):
        self.lock.parent.mkdir(parents=True)
        self.lock.write_text("")
        self.lock.chmod(0o644)
        with fo.broker_lock(0, steps_dir=self.env.tmp / "steps"):
            pass
        self.assertEqual(stat.S_IMODE(self.lock.stat().st_mode), 0o600)

    def test_a_busy_lock_gives_up_after_a_bounded_wait(self):
        self.hold()
        with self.assertRaises(fo.LockBusy) as cm:
            with fo.broker_lock(0, steps_dir=self.env.tmp / "steps"):
                self.fail("entered a held lock")
        self.assertIn("another broker command", str(cm.exception))

    def test_stale_step_dirs_are_removed_under_the_lock(self):
        steps = self.env.tmp / "steps"
        (steps / "old-1").mkdir(parents=True)
        (steps / "old-1" / "secret-token").write_text("leftover")
        with fo.broker_lock(0, steps_dir=steps):
            self.assertEqual(list(steps.iterdir()), [])

    def test_every_command_that_runs_steps_takes_the_lock(self):
        self.hold()
        svc = self.env.svc_factory()
        with self.assertRaises(fo.Refused):
            fo.cmd_baseline(self.cfg, gates, self.env.cat, self.env.secret, "n", False, svc, fakes.Console(), lock_wait_s=0)
        issues, line = fo.drift_check(self.cfg, gates, self.env.cat, self.env.secret, svc, lock_wait_s=0)
        self.assertIsNone(issues)
        self.assertIn("lock", line)
        with self.assertRaises(fo.Refused):
            fo.cmd_diagnose(self.cfg, self.env.cat, "host-check", svc, fakes.Console(), lock_wait_s=0)
        with self.assertRaises(fo.Refused):
            fo.cmd_fetch(self.cfg, self.env.repo.git, fakes.Console(), lock_wait_s=0)
        with self.assertRaises(fo.Refused):
            fo.cmd_resolve(self.cfg, gates, self.env.secret, "r9", "n", lock_wait_s=0)
        self.assertEqual(self.env.sandbox.runs, [])

    def stamp(self, age):
        stamp = self.env.tmp / "stamp"
        stamp.touch()
        t = self.env.clock.time() - age
        os.utime(stamp, (t, t))
        return stamp

    def health(self, stamp, console=None):
        return fo.cmd_health(self.cfg, self.env.cat, self.env.svc_factory(), console or fakes.Console(), clock=self.env.clock,
                             stamp=stamp)

    def test_health_is_refused_30_s_after_the_last_run_and_allowed_61_s_after(self):
        with self.assertRaises(fo.Refused):
            self.health(self.stamp(30))
        self.assertEqual(self.env.sandbox.runs, [])
        console = fakes.Console()
        self.assertEqual(self.health(self.stamp(61), console), 0)
        self.assertIn("healthy=yes", console.lines)
        self.assertEqual(self.env.sandbox.envs[-1]["FACTORY_RELEASE_HEAD"], "")

    def test_the_stamp_is_written_when_the_run_ends_not_when_it_starts(self):
        stamp = self.stamp(120)
        start = self.env.clock.time()
        self.health(stamp)
        self.assertAlmostEqual(stamp.stat().st_mtime, self.env.clock.time(), delta=1)
        self.assertGreater(stamp.stat().st_mtime, start + self.env.cat["broker"]["heartbeat_ttl_s"])
        with self.assertRaises(fo.Refused):
            self.health(stamp)

    def test_the_stamp_is_checked_inside_the_lock(self):
        self.hold()
        with mock.patch.object(fo, "HEALTH_LOCK_WAIT_S", 0), self.assertRaises(fo.Refused) as cm:
            self.health(self.stamp(30))
        self.assertIn("lock", str(cm.exception))
        self.assertNotIn("60 s ago", str(cm.exception))


class DiagnoseTest(EnvBase):
    def test_diagnose_prints_the_notes_and_the_status(self):
        console = fakes.Console()
        self.assertEqual(fo.cmd_diagnose(self.cfg, self.env.cat, "check-token", self.env.svc_factory(), console), 0)
        self.assertEqual(console.lines, ["the token's project: proj-1", "check-token: done"])
        self.env.world.project = "proj-2"
        console = fakes.Console()
        self.assertEqual(fo.cmd_diagnose(self.cfg, self.env.cat, "check-token", self.env.svc_factory(), console), 1)

    def test_diagnose_runs_only_host_check_or_a_declared_diagnostic(self):
        for name in ("drift-scan", "health", "nope"):
            with self.subTest(name), self.assertRaises(fo.Refused):
                fo.cmd_diagnose(self.cfg, self.env.cat, name, self.env.svc_factory(), fakes.Console())


class CommandsTest(unittest.TestCase):
    def test_broker_commands_refuse_to_run_unless_root(self):
        with mock.patch.object(fo, "LIB", fo.pathlib.Path("/usr/local/lib/factory-prod")):
            for cmd in ("check", "serve", "baseline", "health", "diagnose", "drift-check", "pubkey", "resolve", "fetch"):
                with mock.patch("os.geteuid", return_value=1000), mock.patch("sys.stderr", new_callable=io.StringIO) as err:
                    self.assertEqual(fo.main(["factory_op.py", cmd, "x"]), 2, cmd)
                self.assertIn("runs as root", err.getvalue())

    def test_op_and_egress_refuse_to_run_as_root(self):
        with mock.patch.object(fo, "LIB", fo.pathlib.Path("/usr/local/lib/factory-prod")):
            for cmd, needle in (("op", "refuses to run as root"), ("egress", "refuses to run as root")):
                with mock.patch("os.geteuid", return_value=0), mock.patch("sys.stderr", new_callable=io.StringIO) as err:
                    self.assertEqual(fo.main(["factory_op.py", cmd, "health"]), 2)
                self.assertIn(needle, err.getvalue())

    def test_an_unknown_op_name_is_refused(self):
        env = Env()
        self.addCleanup(env.close)
        env.sandbox.cfg_file.write_text(json.dumps(env.cfg))
        with mock.patch("os.geteuid", return_value=1000):
            rc = fo.op_main("deploy", environ={"FACTORY_CONFIG": str(env.sandbox.cfg_file)}, stderr=io.StringIO())
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
