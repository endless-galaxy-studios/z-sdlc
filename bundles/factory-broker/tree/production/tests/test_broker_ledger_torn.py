"""One torn ledger line stops nothing silently and breaks nothing (z-sdlc process/factory-broker.md, D4 rule 9). A broker
killed mid-append leaves a last line with no newline that doesn't parse. It is reported by `check`, refuses gates as an
interrupted run, and blocks every append (the next line would run into it); `resolve --torn-line NOTE` sets it aside into a
side file in the state directory and appends a signed note. Any other line that doesn't parse refuses everything. The
ledger's directory is fsynced when the ledger is created."""

import hashlib
import io
import json
import os
import pathlib
import stat
import unittest
from unittest import mock

import fakes
from fakes import Env, TOKEN
import factory_op as fo
import gates

TORN = b'{"at": "2026-11-05T12:00:00Z", "event": "step-fin'


class LedgerBase(unittest.TestCase):
    def setUp(self):
        self.env = Env()
        self.addCleanup(self.env.close)
        self.cfg = self.env.cfg
        self.ledger = pathlib.Path(self.cfg["ledger"])
        for name, value in (("LOCK", self.env.tmp / "run" / "broker.lock"), ("STEPS_DIR", self.env.tmp / "steps")):
            p = mock.patch.object(fo, name, value)
            p.start()
            self.addCleanup(p.stop)
        fakes.no_live_steps(self)
        self.assertEqual(fo.cmd_baseline(self.cfg, gates, self.env.cat, self.env.secret, "n", False, self.env.svc_factory(),
                                         fakes.Console()), 0)

    def tear(self, data=TORN):
        with open(self.ledger, "ab") as f:
            f.write(data)
        return self.ledger.read_bytes()

    def serve(self):
        routes, _ = fakes.gate_routes(self.env)
        gh = fo.GitHub(self.cfg["repo"], TOKEN, opener=fakes.FakeOpener(self.cfg["repo"], routes))
        signed = fo.serve_one(self.cfg, gates, self.env.cat, json.dumps({"run_id": 55, "pr": 7, "token": TOKEN}),
                              self.env.secret, svc_factory=lambda cfg, token: self.env.services(gh))
        return gates.verify_receipt(self.env.public, signed)

    def check(self):
        key = self.env.tmp / "receipt.key"
        key.write_text(self.env.secret.hex())
        with mock.patch.object(fo, "KEY", key):
            return fo.check(self.cfg, self.env.cat, gates)


class TornLineTest(LedgerBase):
    def test_a_torn_last_line_is_read_as_torn_and_the_rest_as_entries(self):
        self.tear()
        entries = fo.ledger_entries(self.ledger)
        self.assertEqual(entries.torn, TORN)
        self.assertEqual([e["event"] for e in entries], ["baseline"])
        self.assertIn("cut off mid-write", fo.torn_problem(entries))
        self.assertIsNone(fo.torn_problem(fo.ledger_entries(self.env.tmp / "absent.jsonl")))

    def test_check_reports_it(self):
        self.tear()
        self.assertTrue(any("cut off mid-write" in p and "resolve --torn-line" in p for p in self.check()), self.check())

    def test_a_gate_is_refused_as_an_interrupted_run_and_nothing_starts(self):
        before = self.tear()
        receipt = self.serve()
        self.assertEqual(receipt["status"], "refused")
        self.assertIn("interrupted", receipt["reason"])
        self.assertIn("resolve --torn-line", receipt["reason"])
        self.assertEqual(self.ledger.read_bytes(), before)
        self.assertEqual(self.env.sandbox.runs[-1][0], "capture-state")  # the baseline's: the gate ran nothing

    def test_baseline_resolve_and_drift_dont_crash_and_say_why(self):
        before = self.tear()
        with self.assertRaises(fo.Refused) as cm:
            fo.cmd_baseline(self.cfg, gates, self.env.cat, self.env.secret, "n", False, self.env.svc_factory(), fakes.Console())
        self.assertIn("cut off mid-write", str(cm.exception))
        with self.assertRaises(fo.Refused) as cm:
            fo.cmd_resolve(self.cfg, gates, self.env.secret, "r9", "n")
        self.assertIn("--torn-line", str(cm.exception))
        issues, line = fo.drift_check(self.cfg, gates, self.env.cat, self.env.secret, self.env.svc_factory(),
                                      now_dt=self.env.clock.now())
        self.assertIn("cut off mid-write", line)
        self.assertTrue(issues)
        self.assertEqual(self.ledger.read_bytes(), before)

    def test_no_line_is_ever_appended_after_it(self):
        before = self.tear()
        with self.assertRaises(fo.Refused) as cm:
            fo.ledger_append(self.ledger, {"event": "start", "run": "r1"})
        self.assertIn("cut off mid-write", str(cm.exception))
        self.assertEqual(self.ledger.read_bytes(), before)

    def test_a_whole_last_entry_that_only_lost_its_newline_counts_and_gets_one(self):
        self.tear(json.dumps({"event": "note", "run": "x"}, sort_keys=True).encode())
        entries = fo.ledger_entries(self.ledger)
        self.assertIsNone(entries.torn)
        self.assertEqual(entries[-1]["event"], "note")
        fo.ledger_append(self.ledger, {"event": "after", "run": "y"})
        self.assertEqual([e["event"] for e in fo.ledger_entries(self.ledger)], ["baseline", "note", "after"])
        self.assertTrue(self.ledger.read_bytes().endswith(b"\n"))


class ResolveTornLineTest(LedgerBase):
    def test_it_is_set_aside_with_a_signed_note_never_silently(self):
        whole = self.ledger.read_bytes()
        self.tear()
        with mock.patch.dict(os.environ, {"SUDO_USER": "cd"}):
            side = fo.cmd_resolve_torn(self.cfg, gates, self.env.secret, "the broker was killed at 12:00", lock_wait_s=0)
        self.assertEqual(side.parent, self.ledger.parent)  # in the state directory, beside the ledger
        self.assertEqual(side.read_bytes(), TORN)
        self.assertEqual(stat.S_IMODE(side.stat().st_mode), 0o600)
        data = self.ledger.read_bytes()
        self.assertTrue(data.startswith(whole))
        entries = fo.ledger_entries(self.ledger)
        self.assertIsNone(entries.torn)
        note = entries[-1]
        self.assertEqual(note["event"], "torn-line")
        receipt = gates.verify_receipt(self.env.public, note["signed"])
        self.assertEqual((receipt["kind"], receipt["bytes"], receipt["sha256"], receipt["side_file"], receipt["by"]),
                         ("torn-line", len(TORN), hashlib.sha256(TORN).hexdigest(), str(side), "cd"))
        self.assertEqual(receipt["note"], "the broker was killed at 12:00")
        # Nothing is left in the way: no problem in check, and gates run again.
        self.assertFalse(any("mid-write" in p for p in self.check()))
        self.assertEqual(self.serve()["status"], "done")

    def test_a_run_the_torn_line_belonged_to_is_still_resolved_by_hand(self):
        fo.ledger_append(self.ledger, {"event": "start", "run": "r9", "repo": self.cfg["repo"], "pr": 7, "issue": 3,
                                       "gate": "G1", "attempt": 1, "digest": "d" * 64, "github_run": 5})
        self.tear()  # its finish line, cut off
        fo.cmd_resolve_torn(self.cfg, gates, self.env.secret, "n", lock_wait_s=0)
        self.assertEqual(fo.unfinished(fo.ledger_entries(self.ledger)), ["r9"])
        self.assertIn("interrupted (r9)", self.serve()["reason"])
        self.assertEqual(fo.cmd_resolve(self.cfg, gates, self.env.secret, "r9", "n"), 0)

    def test_the_note_is_signed_before_the_ledger_is_cut(self):
        before = self.tear()
        with mock.patch.object(gates, "sign_receipt", side_effect=RuntimeError("no openssl to sign with")):
            with self.assertRaises(RuntimeError):
                fo.cmd_resolve_torn(self.cfg, gates, self.env.secret, "n", lock_wait_s=0)
        self.assertEqual(self.ledger.read_bytes(), before)  # still torn, never cut without its note
        self.assertEqual(sorted(p.name for p in self.ledger.parent.iterdir()), [self.ledger.name])  # no side file either

    def test_the_cut_and_the_note_land_together_or_not_at_all(self):
        before = self.tear()
        with mock.patch.object(fo.os, "replace", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                fo.cmd_resolve_torn(self.cfg, gates, self.env.secret, "n", lock_wait_s=0)
        self.assertEqual(self.ledger.read_bytes(), before)  # still torn: never cut without its note
        self.assertEqual(fo.ledger_entries(self.ledger).torn, TORN)
        self.assertFalse([p for p in self.ledger.parent.iterdir() if p.name.endswith(".tmp")])  # no half-written copy left
        side = fo.cmd_resolve_torn(self.cfg, gates, self.env.secret, "n", lock_wait_s=0)  # and it resolves again
        self.assertEqual(side.read_bytes(), TORN)
        self.assertEqual(fo.ledger_entries(self.ledger)[-1]["event"], "torn-line")

    def test_nothing_torn_is_refused_and_changes_nothing(self):
        before = self.ledger.read_bytes()
        with self.assertRaises(fo.Refused) as cm:
            fo.cmd_resolve_torn(self.cfg, gates, self.env.secret, "n", lock_wait_s=0)
        self.assertIn("isn't torn", str(cm.exception))
        self.assertEqual(self.ledger.read_bytes(), before)

    def test_it_takes_the_lock(self):
        self.tear()
        with mock.patch.object(fo, "live_step_units", return_value=[f"{fo.UNIT_PREFIX}x.service (active)"]):
            with self.assertRaises(fo.StepsLive):
                fo.cmd_resolve_torn(self.cfg, gates, self.env.secret, "n", lock_wait_s=0)
        self.assertIsNotNone(fo.ledger_entries(self.ledger).torn)

    def test_main_dispatches_it(self):
        self.tear()
        key = self.env.tmp / "receipt.key"
        key.write_text(self.env.secret.hex())
        out = io.StringIO()
        with mock.patch.object(fo, "LIB", pathlib.Path("/usr/local/lib/factory-prod")), \
                mock.patch("os.geteuid", return_value=0), mock.patch.object(fo, "install_root_signals"), \
                mock.patch.object(fo, "load", return_value=(self.cfg, gates, self.env.cat, [])), \
                mock.patch.object(fo, "KEY", key), mock.patch("sys.stdout", out):
            self.assertEqual(fo.main(["factory_op.py", "resolve", "--torn-line", "killed", "mid-write"]), 0)
        self.assertIn("set aside", out.getvalue())
        self.assertEqual(gates.verify_receipt(self.env.public, fo.ledger_entries(self.ledger)[-1]["signed"])["note"],
                         "killed mid-write")
        self.assertIn("resolve --torn-line NOTE", fo.__doc__)


class BrokenLineTest(LedgerBase):
    def broken(self, data):
        self.ledger.write_bytes(data)

    def test_an_unparseable_line_anywhere_else_refuses_everything(self):
        whole = self.ledger.read_bytes()
        for data in (b"not json\n" + whole, whole + b"not json\n", whole + TORN + b"\n", whole + b"[1, 2]\n" + whole,
                     whole + b"\xff\xfe\n"):
            with self.subTest(data=data[-20:]):
                self.broken(data)
                with self.assertRaises(fo.LedgerBroken):
                    fo.ledger_entries(self.ledger)
                self.assertEqual(self.serve()["status"], "refused")
                self.assertTrue(any("doesn't parse" in p for p in self.check()))
                issues, line = fo.drift_check(self.cfg, gates, self.env.cat, self.env.secret, self.env.svc_factory())
                self.assertIsNone(issues)
                self.assertIn("doesn't parse", line)
                with self.assertRaises(fo.Refused):
                    fo.cmd_baseline(self.cfg, gates, self.env.cat, self.env.secret, "n", False, self.env.svc_factory(),
                                    fakes.Console())
                with self.assertRaises(fo.LedgerBroken):
                    fo.cmd_resolve_torn(self.cfg, gates, self.env.secret, "n", lock_wait_s=0)
                self.assertEqual(self.ledger.read_bytes(), data)


class CreationTest(unittest.TestCase):
    def test_the_directory_is_fsynced_when_the_ledger_is_created_and_only_then(self):
        env = Env()
        self.addCleanup(env.close)
        ledger = env.tmp / "state" / "ledger.jsonl"
        real, kinds = os.fsync, []

        def fsync(fd):
            kinds.append("dir" if stat.S_ISDIR(os.fstat(fd).st_mode) else "file")
            return real(fd)
        with mock.patch.object(fo.os, "fsync", fsync):
            fo.ledger_append(ledger, {"event": "a", "run": "1"})
            self.assertEqual(kinds, ["file", "dir"])
            fo.ledger_append(ledger, {"event": "b", "run": "2"})
        self.assertEqual(kinds, ["file", "dir", "file"])
        self.assertEqual(stat.S_IMODE(ledger.stat().st_mode), 0o600)
        self.assertEqual([e["event"] for e in fo.ledger_entries(ledger)], ["a", "b"])


if __name__ == "__main__":
    unittest.main()
