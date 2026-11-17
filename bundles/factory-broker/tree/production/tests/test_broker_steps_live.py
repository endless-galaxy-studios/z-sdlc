"""A step can't outlive its broker unseen (z-sdlc process/factory-broker.md, D4 rules 9 and 12). Each step is a transient
systemd unit tied to nothing: a broker killed mid-step leaves it running, with its secrets and egress, while the broker's
lock is free. So every command that runs steps, and `resolve`, refuses once it holds the lock while any of this tier's step
units still runs, naming it, and never removes a live step's directory; and a step that times out comes back only once its
unit is gone (or, past the kill margin, keeps its directory and leaves the refusal to the next command)."""

import fcntl
import json
import pathlib
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

import fakes
from fakes import Env, TOKEN
import factory_op as fo
import gates

UNIT = f"{fo.UNIT_PREFIX}20261105T120000Z-7-G1-a1-1.service"


def listing(*rows):
    """systemctl list-units --plain --no-legend output: one `unit load active sub description` row each."""
    return "".join(f"{unit} loaded {active} {sub} /usr/bin/python3 -I factory_op.py op health\n" for unit, active, sub in rows)


def runner_answering(stdout, rc=0, seen=None):
    def run(argv, **kw):
        if seen is not None:
            seen.append(argv)
        return subprocess.CompletedProcess(argv, rc, stdout, "")
    return run


class ListingTest(unittest.TestCase):
    def test_a_running_stopping_or_starting_unit_is_live_and_a_gone_one_isnt(self):
        seen = []
        out = listing((UNIT, "active", "running"), (fo.UNIT_PREFIX + "b-2.service", "deactivating", "stop-sigterm"),
                      (fo.UNIT_PREFIX + "c-3.service", "activating", "start"), (fo.UNIT_PREFIX + "d-4.service", "inactive", "dead"),
                      (fo.UNIT_PREFIX + "e-5.service", "failed", "failed"))
        live = fo.live_step_units(runner=runner_answering(out, seen=seen))
        self.assertEqual(live, [f"{UNIT} (active)", f"{fo.UNIT_PREFIX}b-2.service (deactivating)",
                                f"{fo.UNIT_PREFIX}c-3.service (activating)"])
        # Asked of systemd by this tier's prefix alone, by absolute path, inactive units included.
        self.assertEqual(seen[0][0], fo.SYSTEMCTL)
        self.assertIn(f"{fo.UNIT_PREFIX}*", seen[0])
        self.assertIn("--all", seen[0])
        self.assertEqual(fo.live_step_units(runner=runner_answering("")), [])

    def test_an_answer_that_cant_be_read_is_never_none(self):
        for runner in (runner_answering("", rc=1), runner_answering("garbage\n"),
                       runner_answering(listing(("other-unit.service", "active", "running")))):
            with self.subTest(), self.assertRaises(fo.StepsLive):
                fo.live_step_units(runner=runner)

        def missing(argv, **kw):
            raise FileNotFoundError(argv[0])
        with self.assertRaises(fo.StepsLive):
            fo.live_step_units(runner=missing)
        self.assertTrue(issubclass(fo.StepsLive, fo.LockBusy))  # refused like a held lock, wherever one is

    def test_another_tiers_prefix_isnt_this_ones(self):
        later = fo.tier_names("factory-prod-b2")["unit_prefix"]
        self.assertFalse(later.startswith(fo.UNIT_PREFIX))
        self.assertFalse(fo.UNIT_PREFIX.startswith(later))


class LiveBase(unittest.TestCase):
    """A tier whose systemd reports one of its step units still running."""

    def setUp(self):
        self.env = Env()
        self.addCleanup(self.env.close)
        self.cfg = self.env.cfg
        self.steps = self.env.tmp / "steps"
        for name, value in (("LOCK", self.env.tmp / "run" / "broker.lock"), ("STEPS_DIR", self.steps)):
            p = mock.patch.object(fo, name, value)
            p.start()
            self.addCleanup(p.stop)
        self.live = [f"{UNIT} (active)"]
        p = mock.patch.object(fo, "live_step_units", side_effect=lambda: list(self.live))
        p.start()
        self.addCleanup(p.stop)
        # The live step's own directory, with its secret, as a killed broker left it.
        self.step_dir = self.steps / "20261105T120000Z-7-G1-a1-1"
        self.step_dir.mkdir(parents=True)
        (self.step_dir / "secret-token").write_text("in use")

    def baseline(self):
        self.live = []
        self.assertEqual(fo.cmd_baseline(self.cfg, gates, self.env.cat, self.env.secret, "n", False, self.env.svc_factory(),
                                         fakes.Console()), 0)
        self.live = [f"{UNIT} (active)"]

    def assertNamesTheUnit(self, text):
        self.assertIn("still running", text)
        self.assertIn(UNIT, text)


class RefusalTest(LiveBase):
    def test_the_lock_refuses_naming_the_unit_and_keeps_its_directory(self):
        with self.assertRaises(fo.StepsLive) as cm:
            with fo.broker_lock(0, steps_dir=self.steps):
                self.fail("ran beside a live step")
        self.assertNamesTheUnit(str(cm.exception))
        self.assertEqual((self.step_dir / "secret-token").read_text(), "in use")
        # The lock itself is free again: nothing waits on the refusal.
        with open(fo.LOCK, "a") as f:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(f, fcntl.LOCK_UN)
        self.live = []
        with fo.broker_lock(0, steps_dir=self.steps):
            self.assertFalse(self.step_dir.exists())  # once it is gone, its directory is a stale one

    def test_a_gate_is_a_signed_refusal_and_nothing_starts(self):
        self.baseline()
        routes, _ = fakes.gate_routes(self.env)
        gh = fo.GitHub(self.cfg["repo"], TOKEN, opener=fakes.FakeOpener(self.cfg["repo"], routes))
        signed = fo.serve_one(self.cfg, gates, self.env.cat, json.dumps({"run_id": 55, "pr": 7, "token": TOKEN}),
                              self.env.secret, svc_factory=lambda cfg, token: self.env.services(gh))
        receipt = gates.verify_receipt(self.env.public, signed)
        self.assertEqual(receipt["status"], "refused")
        self.assertNamesTheUnit(receipt["reason"])
        self.assertNotIn("minutes at most", receipt["reason"])  # it isn't a lock that was held too long
        self.assertFalse(any(e.get("event") == "start" for e in fo.ledger_entries(self.cfg["ledger"])))

    def test_resolve_never_closes_a_run_whose_step_still_runs(self):
        fo.ledger_append(self.cfg["ledger"], {"event": "start", "run": "r9", "repo": self.cfg["repo"], "pr": 7, "issue": 3,
                                              "gate": "G1", "attempt": 1, "digest": "d" * 64, "github_run": 5})
        with self.assertRaises(fo.StepsLive) as cm:
            fo.cmd_resolve(self.cfg, gates, self.env.secret, "r9", "looked", lock_wait_s=0)
        self.assertNamesTheUnit(str(cm.exception))
        self.assertEqual(fo.unfinished(fo.ledger_entries(self.cfg["ledger"])), ["r9"])
        self.live = []
        self.assertEqual(fo.cmd_resolve(self.cfg, gates, self.env.secret, "r9", "looked", lock_wait_s=0), 0)

    def test_every_command_that_runs_steps_refuses(self):
        svc = self.env.svc_factory()
        calls = {
            "baseline": lambda: fo.cmd_baseline(self.cfg, gates, self.env.cat, self.env.secret, "n", False, svc, fakes.Console()),
            "health": lambda: fo.cmd_health(self.cfg, self.env.cat, svc, fakes.Console(), clock=self.env.clock,
                                            stamp=self.env.tmp / "stamp"),
            "diagnose": lambda: fo.cmd_diagnose(self.cfg, self.env.cat, "host-check", svc, fakes.Console()),
            "fetch": lambda: fo.cmd_fetch(self.cfg, self.env.repo.git, fakes.Console()),
        }
        for name, call in calls.items():
            with self.subTest(name), self.assertRaises(fo.Refused) as cm:
                call()
            self.assertNamesTheUnit(str(cm.exception))
        issues, line = fo.drift_check(self.cfg, gates, self.env.cat, self.env.secret, svc)
        self.assertIsNone(issues)
        self.assertNamesTheUnit(line)
        self.assertEqual(self.env.sandbox.runs, [])
        self.assertTrue(self.step_dir.exists())


class TimeoutTest(unittest.TestCase):
    """The real Sandbox with systemd-run and systemctl doubled: a timed-out step comes back once its unit is gone."""

    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.cfg = fakes.make_config(self.tmp, self.tmp / "lib")
        (self.tmp / "lib").mkdir()
        self.etc = self.tmp / "etc"
        self.etc.mkdir()
        (self.etc / "host.token").write_text(fakes.SENTINEL_TOKEN)
        (self.etc / "host.token").chmod(0o600)
        self.cat = fakes.catalog()
        self.calls, self.clock, self.dirs = [], fakes.FakeClock(), []

    def sandbox(self, states, wait=None):
        """`states`: what `systemctl show -p ActiveState` answers, one per call (the last repeats)."""
        outer, answers = self, list(states)

        def runner(argv, **kw):
            outer.calls.append((outer.clock.t, argv[1]))
            if argv[1] == "show":
                return subprocess.CompletedProcess(argv, 0, (answers.pop(0) if len(answers) > 1 else answers[0]) + "\n", "")
            return subprocess.CompletedProcess(argv, 0, "", "")

        class Proc:
            def __init__(s, argv, **kw):
                outer.dirs.append(pathlib.Path(next(a for a in argv if a.startswith("--working-directory=")).split("=", 1)[1]))
                s.n = 0

            def wait(s, timeout=None):
                s.n += 1
                if wait:
                    return wait(s, timeout)
                if s.n == 1:
                    raise subprocess.TimeoutExpired("x", timeout)
                return -9

            def kill(s):
                outer.calls.append((outer.clock.t, "client-kill"))
        return fo.Sandbox(self.cfg, self.cat, "r1", steps_dir=self.tmp / "steps", popen=Proc, runner=runner, chown=False,
                          secret_dir=self.etc, secret_owner=(fo.os.getuid(), fo.os.getgid()), root=self.tmp / "root",
                          clock=self.clock)

    def run_health(self, sb):
        return sb.run("health", self.cat["operations"]["health"], {}, "1", self.tmp / "log")

    def test_it_returns_only_once_the_unit_is_inactive(self):
        res = self.run_health(self.sandbox(["deactivating", "deactivating", "deactivating", "inactive"]))
        self.assertEqual(res.status, "timed-out")
        verbs = [v for _, v in self.calls]
        self.assertEqual(verbs[:3], ["stop", "show", "kill"])  # stopped, still there, so killed outright
        self.assertEqual(verbs[-1], "show")
        self.assertEqual(verbs.count("show"), 4)  # back only after systemd said inactive
        self.assertNotIn("still running", res.why)
        self.assertFalse(self.dirs[0].exists())  # gone, so its directory goes too

    def test_a_unit_that_stops_at_once_isnt_killed(self):
        res = self.run_health(self.sandbox(["inactive"]))
        self.assertEqual(res.status, "timed-out")
        self.assertEqual([v for _, v in self.calls], ["stop", "show"])

    def test_a_unit_slow_to_go_is_killed_again_and_waited_for_past_the_margin(self):
        states = ["deactivating"] * 100 + ["inactive"]  # gone only after 99 one-second polls
        res = self.run_health(self.sandbox(states))
        self.assertEqual(res.status, "timed-out")
        verbs = [v for _, v in self.calls]
        self.assertEqual(verbs.count("show"), 101)
        self.assertEqual(verbs.count("kill"), 3)  # at once, then every UNIT_GONE_WAIT_S it is still there
        self.assertGreater(self.clock.t, fo.UNIT_GONE_WAIT_S)
        self.assertFalse(self.dirs[0].exists())
        self.assertLessEqual(fo.STOP_TIMEOUT_S + fo.UNIT_GONE_WAIT_S + fo.CLIENT_WAIT_S, fo.STEP_KILL_MARGIN_S)

    def test_an_unreadable_state_is_never_taken_for_gone(self):
        res = self.run_health(self.sandbox(["weird state!"] * 5 + ["inactive"]))
        self.assertEqual(res.status, "timed-out")
        self.assertEqual([v for _, v in self.calls].count("show"), 6)  # waited through every answer it couldn't read
        self.assertFalse(self.dirs[0].exists())

    def test_an_interrupted_broker_stops_the_unit_before_it_goes(self):
        def interrupted(proc, timeout):
            raise SystemExit(143)
        with self.assertRaises(SystemExit):
            self.run_health(self.sandbox(["deactivating", "inactive"], wait=interrupted))
        self.assertEqual([v for _, v in self.calls][:3], ["stop", "show", "kill"])
        self.assertFalse(self.dirs[0].exists())

    def test_an_interrupted_broker_whose_unit_wont_stop_keeps_its_directory(self):
        def interrupted(proc, timeout):
            raise SystemExit(143)
        with self.assertRaises(SystemExit):
            self.run_health(self.sandbox(["active"], wait=interrupted))
        self.assertTrue(self.dirs[0].exists())


if __name__ == "__main__":
    unittest.main()
