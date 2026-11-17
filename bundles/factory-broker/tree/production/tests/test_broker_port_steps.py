"""Steps and requests (z-sdlc process/factory.md D4 rules 7, 10 and 15), the part the other broker tests don't hold: which
services release-wait lifts the serving check for, patterns matched whole, the step unit's hardening and its cleanup on an
interrupt, what root keeps of a step's detail file, the in-process sandbox's own fidelity, release-wait's shortcut for a
service the release didn't touch, request kinds, and config.json's start commit. Real git repositories, a mocked GitHub,
the fake host. Carried over from the third project's broker tests (test_review.py: SkipServing, Pattern; test_round2.py:
SandboxV2, UntrustedDetail, FakeSandbox, ShortcutLatestRule, Config; test_round4.py: UnknownKind)."""

import io
import json
import pathlib
import signal
import subprocess
import unittest
from unittest import mock

import fakes
from fakes import Env, TOKEN
import factory_op as fo
import gates
from test_broker_gate import GateBase, request
from test_broker_ops import OpTest
from test_broker_sandbox import HEALTH_OUT, SandboxHelper

UUID = "12345678-9abc-4def-8123-456789abcdef"  # a made-up one


class SkipServingTest(GateBase):
    """A gate that opens with release-wait lifts the serving check for the release services only (the wait covers them)."""

    def test_every_release_service_mid_deploy_is_lifted_by_a_first_release_wait(self):
        for svc in fo.services_of(self.block, "release"):
            with self.subTest(svc):
                self.setUp()
                self.w.add(svc, "BUILDING", self.repo.base)
                self.assertIn(f"{svc}: a release is deploying", self.refused())
                head, _, _ = self.pregate(ops=("release-wait", "health"))
                self.assertEqual(head, self.repo.base)

    def test_a_checked_service_that_isnt_a_release_service_keeps_its_content_check_with_release_wait(self):
        sha = self.merge({"proxy/p.txt": "p2"})
        msg = self.refused(merges=[(sha, 1, None)], ops=("release-wait",))
        self.assertTrue(msg.startswith("proxy:"), msg)
        self.assertIn("isn't serving", msg)

    def test_content_equal_but_not_an_ancestor_does_not_count_as_released(self):
        self.repo.sh("checkout", "-q", "-b", "side")
        self.repo.direct_commit({"README": "side"})
        side = self.repo.sh("rev-parse", "HEAD")
        self.repo.sh("checkout", "-q", "release/production")
        self.repo.git.fetch("x", "+refs/heads/side:refs/factory/side")
        head = self.merge({"README": "r2"})
        self.repo.fetch()
        self.w.deployments["web"][0]["commit"] = side
        self.assertTrue(self.repo.git.content_equal(side, head, self.block["services"]["web"]["patterns"]))
        self.assertFalse(self.repo.git.is_ancestor(side, head))
        res = self.env.sandbox.run("release-wait", self.env.cat["operations"]["release-wait"], {"sha": head}, "t",
                                   self.env.tmp / "logs" / "rw.log", head)
        self.assertEqual(res.status, "failed")
        self.assertIn("no deployment created for web", res.why)


class PatternTest(unittest.TestCase):
    def test_a_trailing_newline_does_not_pass_a_pattern_in_the_step(self):
        env = Env()
        self.addCleanup(env.close)
        res = env.run_op("http-check", release_head="", target="web", path="/ready\n", expect_status="200")
        self.assertEqual(res.status, "failed")
        self.assertIn("parameters aren't the operation's", res.why)
        self.assertEqual(env.world.app_calls, [])

    def test_commit_ids_tokens_and_ids_must_match_exactly(self):
        for pattern, ok in ((fo.SHA, "a" * 40), (fo.UUID, UUID), (fo.TOKEN, "t" * 30), (fo.FIELD, "web_commit"),
                            (fo.STEP_ID, "h1"), (fo.RUN_ID, "run-1"), (fo.PIN, gates.pin_branch(7, "G1", "a" * 40))):
            with self.subTest(pattern=pattern.pattern):
                self.assertTrue(pattern.fullmatch(ok))
                self.assertIsNone(pattern.fullmatch(ok + "\n"))

    def test_no_dollar_anchored_pattern_is_matched_with_re_match(self):
        src = (fakes.PROD / "factory_op.py").read_text()
        self.assertEqual(fo.re.findall(r"\bre\.match\(", src), [])
        self.assertEqual(fo.re.findall(r"\b[A-Z_]+\.match\(", src), [])  # a compiled pattern: fullmatch, never match


class StepsHelper(SandboxHelper):
    """SandboxHelper's real Sandbox, with a process double whose wait can raise, and the units it stops recorded."""

    def sandbox(self, act=None, rc=0, log_text="", owner=None, root=None, wait=None, stops=None):
        outer, waiter = self, wait

        class Proc:
            def __init__(s, argv, **kw):
                outer.argvs.append(argv)
                d = pathlib.Path(next(a for a in argv if a.startswith("--working-directory=")).split("=", 1)[1])
                outer.listing.append(sorted(p.name for p in d.iterdir()))
                if act:
                    act(d)
                kw["stdout"].write(log_text.encode())
                kw["stdout"].flush()

            def wait(s, timeout=None):
                return waiter() if waiter else rc

            def kill(s):
                pass
        def runner(argv, **k):
            # Changed with the fix that a step a stop can't confirm gone keeps its directory: systemd says the unit is gone.
            if argv[1] == "show":
                return subprocess.CompletedProcess(argv, 0, "inactive\n", "")
            if stops is not None:
                stops.append(argv)
        return fo.Sandbox(self.cfg, self.cat, "r1", steps_dir=self.tmp / "steps", popen=Proc, runner=runner, chown=False,
                          secret_dir=self.etc, secret_owner=owner or self.me, root=root or self.tmp / "root")


class SandboxParamTest(SandboxHelper):
    def test_the_sandbox_refuses_a_param_with_a_trailing_newline_before_starting(self):
        res = self.run_op(self.sandbox(), "release-wait", {"sha": "a" * 40 + "\n"}, head="a" * 40)
        self.assertEqual(res.status, "failed")
        self.assertEqual(self.argvs, [])


class SandboxHardeningTest(StepsHelper):
    def unit(self):
        return f"{fo.UNIT_PREFIX}r1-1"

    def test_the_step_unit_filters_syscalls_hides_processes_and_caps_files_without_procsubset(self):
        self.run_op(self.sandbox(lambda d: (d / "out").write_text(HEALTH_OUT)))
        props = self.props(self.argvs[0])
        for p in ("SystemCallErrorNumber=EPERM", "RestrictSUIDSGID=yes", "UMask=0077", "ProtectProc=invisible",
                  "SystemCallFilter=@system-service", "LimitFSIZE=1M", "PrivateDevices=yes", "MemoryMax=512M", "TasksMax=64"):
            self.assertIn(p, props)
        self.assertFalse(any(p.startswith("ProcSubset=") for p in props))
        self.assertFalse(any(p.startswith("ProcSubset=") for p in fo.STEP_PROPS))

    def test_an_interrupt_stops_the_unit_redacts_the_log_and_removes_the_step_dir(self):
        stops = []

        def interrupted():
            raise KeyboardInterrupt()
        sb = self.sandbox(wait=interrupted, log_text=f"token: {fakes.SENTINEL_TOKEN}\n", stops=stops)
        with self.assertRaises(KeyboardInterrupt):
            self.run_op(sb)
        self.assertEqual(stops, [[fo.SYSTEMCTL, "stop", self.unit()]])
        log = (self.tmp / "log").read_text()
        self.assertNotIn(fakes.SENTINEL_TOKEN, log)
        self.assertIn("[redacted]", log)
        self.assertEqual(list((self.tmp / "steps").iterdir()), [])

    def test_an_exception_while_starting_also_stops_the_unit_and_removes_the_step_dir(self):
        stops = []
        sb = self.sandbox(stops=stops)

        def popen(argv, **kw):
            raise OSError("fork failed")
        sb.popen = popen
        with self.assertRaises(OSError):
            self.run_op(sb)
        self.assertEqual(stops, [[fo.SYSTEMCTL, "stop", self.unit()]])
        self.assertEqual(list((self.tmp / "steps").iterdir()), [])

    def test_root_commands_ignore_sigint_and_turn_sigterm_into_exit(self):
        old = (signal.getsignal(signal.SIGINT), signal.getsignal(signal.SIGTERM))
        self.addCleanup(lambda: (signal.signal(signal.SIGINT, old[0]), signal.signal(signal.SIGTERM, old[1])))
        fo.install_root_signals()
        self.assertEqual(signal.getsignal(signal.SIGINT), signal.SIG_IGN)
        self.assertIs(signal.getsignal(signal.SIGTERM), fo.sigterm_to_exit)

    def test_main_installs_them_for_root_commands_only(self):
        lib = pathlib.Path(fo.tier_names("factory-prod")["lib_dir"])
        with mock.patch.object(fo, "LIB", lib), mock.patch.object(fo, "install_root_signals") as install, \
                mock.patch("sys.stderr", new_callable=io.StringIO), mock.patch("sys.stdout", new_callable=io.StringIO):
            with mock.patch("os.geteuid", return_value=1000):
                for cmd in ("check", "fetch", "serve"):
                    self.assertEqual(fo.main(["factory_op.py", cmd]), 2, cmd)  # not root: refused before anything
            with mock.patch("os.geteuid", return_value=0):
                self.assertEqual(fo.main(["factory_op.py", "op", "health"]), 2)  # the step and the proxy refuse root
                self.assertEqual(fo.main(["factory_op.py", "egress"]), 2)
            install.assert_not_called()
            with mock.patch("os.geteuid", return_value=0), mock.patch.object(fo, "load", return_value=({}, gates, None, ["x"])):
                self.assertEqual(fo.main(["factory_op.py", "fetch"]), 1)
            install.assert_called_once_with()

    def test_redaction_uses_the_bytes_that_were_installed_not_a_re_read(self):
        def act(d):  # the source changes after the copy; the log still holds what was copied
            (self.etc / "host.token").write_text("a-completely-different-token-value-0123456789")
        res = self.run_op(self.sandbox(act, rc=1, log_text=f"seen {fakes.SENTINEL_TOKEN}\n"), "capture-state", head="a" * 40)
        self.assertNotIn(fakes.SENTINEL_TOKEN, (self.tmp / "log").read_text())
        self.assertNotIn(fakes.SENTINEL_TOKEN, res.why)
        self.assertIn("[redacted]", res.why)

    def test_why_scrubs_long_token_like_runs_but_keeps_commit_ids_and_uuids(self):
        sha = "a" * 40
        res = self.run_op(self.sandbox(rc=1, log_text=f"FAILED: head {sha} dep {UUID} oops Zm9vYmFyYmF6cXV4cXV1eEFCQ0RFRg== end\n"))
        self.assertEqual(res.status, "failed")
        self.assertIn(sha, res.why)
        self.assertIn(UUID, res.why)
        self.assertIn("[scrubbed]", res.why)
        self.assertNotIn("Zm9vYmFy", res.why)

    def test_a_log_over_1_mib_is_cut_with_a_marker_after_redaction(self):
        text = f"{fakes.SENTINEL_TOKEN}\n" + "x" * (2 << 20) + f"\n{fakes.SENTINEL_TOKEN}\n"
        self.run_op(self.sandbox(rc=1, log_text=text))
        log = (self.tmp / "log").read_text()
        self.assertNotIn(fakes.SENTINEL_TOKEN, log)
        self.assertIn("log truncated", log)
        self.assertLess(len(log), (1 << 20) + 200)


class UntrustedDetailTest(SandboxHelper):
    """Root reads a step's detail file, which the operator wrote, down to {notes, rows}: changed on purpose from the third
    project's broker, whose capture-state detail carried commits, ids and latest statuses. Here those are typed outputs,
    filtered by the catalog's patterns, and a step's detail holds only display notes and, for drift-scan, its rows."""

    EMPTY = {"notes": [], "rows": None}

    def detail_from(self, content, name="capture-state"):
        def act(d):
            (d / "out").write_text(HEALTH_OUT)
            (d / "detail.json").write_text(content)
        return self.run_op(self.sandbox(act), name, head="a" * 40).detail

    def test_capture_states_detail_keeps_its_notes_and_nothing_else(self):
        sha = "b" * 40
        detail = {"notes": ["web: builds from web/**", 5, None, "jobs: builds from jobs/**"],
                  "commits": {"web": sha, "jobs": None}, "ids": {"web": "dep-0001"}, "latest": {"web": "SUCCESS"},
                  "rows": {"web": [{"id": "dep-0001", "commit": sha, "created": "2026-11-05T11:00:00Z", "branch": "release/production"}]},
                  "extra": 1}
        self.assertEqual(self.detail_from(json.dumps(detail)),
                         {"notes": ["web: builds from web/**", "jobs: builds from jobs/**"], "rows": None})

    def test_wrong_top_level_or_member_types_give_an_empty_detail(self):
        for content in ("[]", '"x"', "5", "null", "true", '{"notes": "x"}', '{"notes": {"a": 1}}', '{"rows": []}'):
            with self.subTest(content=content):
                self.assertEqual(self.detail_from(content), self.EMPTY)
        for content in ('{"rows": []}', '{"rows": "x"}', '{"rows": null}'):
            with self.subTest(content=content):
                self.assertEqual(self.detail_from(content, "drift-scan"), self.EMPTY)

    def test_deeply_nested_objects_do_not_crash_root(self):
        for name in ("capture-state", "drift-scan"):
            with self.subTest(name):
                self.assertEqual(self.detail_from('{"a":' * 20000, name), self.EMPTY)
                self.assertEqual(self.detail_from('{"rows": ' + '{"web": ' * 20000, name), self.EMPTY)

    def test_drift_scan_rows_are_validated(self):
        good = {"id": "dep-0001", "commit": "c" * 40, "created": "2026-11-05T11:00:00Z", "branch": "release/production", "extra": 1}
        rows = {"web": [good, "junk", {"id": 5, "commit": "zzz"}], "nope": [{"id": "1"}], "jobs": "not a list"}
        d = self.detail_from(json.dumps({"rows": rows}), "drift-scan")
        self.assertEqual(sorted(d["rows"]), ["web"])
        self.assertEqual(d["rows"]["web"], [{k: good[k] for k in ("id", "commit", "created", "branch")},
                                            {"id": None, "commit": None, "created": None, "branch": None}])

    def test_strings_from_the_step_cannot_carry_control_characters(self):
        rows = {"web": [{"id": "dep\x07", "commit": None, "created": "2026\x1b[2J", "branch": "release\x00/production"}]}
        d = self.detail_from(json.dumps({"notes": ["MISMATCH \x1b[2Jevil", "bell\x07", "nul\x00"], "rows": rows}), "drift-scan")
        self.assertEqual(len(d["notes"]), 3)
        self.assertFalse([c for c in json.dumps(d, ensure_ascii=False) if ord(c) < 32 or ord(c) == 127])

    def test_the_stale_step_sweep_survives_errors(self):
        steps = self.tmp / "steps"
        (steps / "a").mkdir(parents=True)
        (steps / "b").mkdir()
        (steps / "f").write_text("x")
        with mock.patch.object(fo.shutil, "rmtree", side_effect=PermissionError("nope")), mock.patch("sys.stderr"):
            fo.clear_stale_steps(steps)  # must not raise
        with mock.patch.object(pathlib.Path, "unlink", side_effect=PermissionError("nope")), mock.patch("sys.stderr"):
            fo.clear_stale_steps(steps)
        fo.clear_stale_steps(steps)
        self.assertEqual(list(steps.iterdir()), [])

    def test_infinity_in_the_request_is_a_malformed_request(self):
        env = Env()
        self.addCleanup(env.close)
        for number in ("Infinity", "-Infinity", "NaN", "1e999"):
            with self.subTest(number):
                line = '{"run_id": %s, "pr": 1, "token": "%s"}' % (number, "t" * 30)
                receipt = gates.verify_receipt(env.public, fo.serve_one(env.cfg, gates, env.cat, line, env.secret))
                self.assertEqual(receipt["status"], "refused")
                self.assertIn("malformed", receipt["reason"])


class FakeSandboxTest(unittest.TestCase):
    def test_the_in_process_sandbox_requires_an_op_secrets_entry_like_the_real_one(self):
        env = Env()
        self.addCleanup(env.close)
        with self.assertRaises(KeyError):
            env.sandbox.run("mystery", {"kind": "read", "timeout_s": 5, "params": {}, "outputs": {}}, {}, "t",
                            env.tmp / "logs" / "m.log")
        self.assertEqual(env.sandbox.runs, [])


class ShortcutLatestRuleTest(OpTest):
    """release-wait's shortcut: a release service with no deployment of the head is done when what it serves is in the
    head's history and has its content, unless its newest deployment says otherwise."""

    def setUp(self):
        super().setUp()
        self.head = self.merge({"README": "r2"})  # touches no service's files: every service is content-equal

    def wait(self, sha=None):
        return self.env.sandbox.run("release-wait", self.env.cat["operations"]["release-wait"], {"sha": sha or self.head}, "t",
                                    self.env.tmp / "logs" / "rw.log", self.head)

    def test_a_crashed_newest_deployment_fails_the_shortcut_even_with_the_heads_content(self):
        self.w.add("web", "CRASHED", self.repo.base)
        res = self.wait()
        self.assertEqual(res.status, "failed")
        self.assertIn("web: its newest deployment crashed", res.why)

    def test_a_deploy_in_progress_is_not_done_yet(self):
        self.w.add("web", "BUILDING", self.repo.base)
        res = self.wait()
        self.assertEqual(res.status, "failed")
        self.assertIn("no deployment created for web", res.why)  # it waited out the grace and never took the shortcut
        self.assertGreater(self.clock.t, self.env.cat["broker"]["release_wait_phases"]["grace_s"])

    def test_an_older_commit_already_in_the_branch_history_passes(self):
        res = self.wait(sha=self.repo.base)
        self.assertEqual(res.status, "done", res.why)
        self.assertEqual((res.outputs["head"], res.outputs["deployed"]), (self.head, ""))


class UnknownKindTest(GateBase):
    def run_kind(self, kind, steps=None):
        req = request(steps)
        req["kind"] = kind
        return fo.execute(self.cfg, gates, self.env.cat, req, "def", fakes.APPROVER, 55, fo.ledger_entries(self.cfg["ledger"]),
                          lambda r: gates.sign_receipt(self.env.secret, r), TOKEN, self.services(), self.env.public, host_run="run1")

    def test_an_unknown_kind_is_refused_before_anything_is_recorded(self):
        self.append_baseline(self.state)
        before, runs = fo.ledger_entries(self.cfg["ledger"]), len(self.env.sandbox.runs)
        for kind in ("deploy", "", None, "OPS", "cd ", 5, "release ", ["ops"]):
            with self.subTest(kind=kind):
                with self.assertRaises(fo.Refused) as cm:
                    self.run_kind(kind)
                self.assertIn("unknown request kind", str(cm.exception))
        self.assertEqual(fo.ledger_entries(self.cfg["ledger"]), before)
        self.assertEqual(len(self.env.sandbox.runs), runs)

    def test_a_cd_gate_runs_nothing_and_is_recorded_start_and_finish(self):
        before = len(self.env.sandbox.runs)
        receipt = self.run_kind("cd", steps=[])["receipt"]
        self.assertEqual((receipt["status"], receipt["steps"]), ("done", []))
        self.assertEqual(len(self.env.sandbox.runs), before)
        self.assertEqual([e["event"] for e in fo.ledger_entries(self.cfg["ledger"])], ["start", "finish"])


class ConfigTest(unittest.TestCase):
    def setUp(self):
        self.env = Env()
        self.addCleanup(self.env.close)
        self.cfg = json.loads(json.dumps(self.env.cfg))

    def test_release_head_start_is_validated(self):
        self.assertEqual(fo.config_problems(self.cfg), [])
        for bad in (None, "", "zz", "abc", "g" * 8, "a" * 41, "ABCDEF0", 1234567, "0123abc\n"):
            with self.subTest(bad=bad):
                self.cfg["release_head_start"] = bad
                self.assertTrue(any("release_head_start" in p for p in fo.config_problems(self.cfg)), bad)
        del self.cfg["release_head_start"]
        self.assertTrue(any("release_head_start" in p for p in fo.config_problems(self.cfg)))
        for good in ("0123abc", "0123abcd", "a" * 40):
            with self.subTest(good=good):
                self.cfg["release_head_start"] = good
                self.assertEqual(fo.config_problems(self.cfg), [])

    def test_a_missing_value_is_a_clean_signed_refusal(self):
        del self.cfg["release_head_start"]
        signed = fo.serve_one(self.cfg, gates, self.env.cat, json.dumps({"run_id": 1, "pr": 2, "token": TOKEN}), self.env.secret)
        receipt = gates.verify_receipt(self.env.public, signed)
        self.assertEqual(receipt["status"], "refused")
        self.assertIn("release_head_start", receipt["reason"])


if __name__ == "__main__":
    unittest.main()
