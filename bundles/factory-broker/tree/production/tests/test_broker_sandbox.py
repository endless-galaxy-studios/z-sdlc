"""Root's side of a step (z-sdlc process/factory.md D4 rule 10): reading what the operator wrote without following a link,
blocking or reading too much; the unit's sandbox properties; each step's declared secrets, installed only from root-owned
0600 files; redaction of every installed secret's bytes from the step's log; and secrecy end to end. Carried over from the
third project's broker tests (test_review.py, test_gate.py's SecrecyTest)."""

import base64
import io
import json
import os
import pathlib
import re
import shutil
import tempfile
import threading
import unittest
from unittest import mock

import fakes
from fakes import Env
import factory_op as fo

HEALTH_OUT = "healthy=yes\nservices=4\nunhealthy=\nweb_deployment=dep-0001\njobs_deployment=dep-0002\n"


class ReadRegularTest(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def run_with_timeout(self, fn):
        box = {}
        t = threading.Thread(target=lambda: box.update(v=fn()), daemon=True)
        t.start()
        t.join(5)
        self.assertFalse(t.is_alive(), "root must never block on an operator-written file")
        return box.get("v")

    def test_a_fifo_does_not_hang_and_is_not_read(self):
        fifo = self.tmp / "out"
        os.mkfifo(fifo)
        self.assertIsNone(self.run_with_timeout(lambda: fo.read_text_limited(fifo)))

    def test_a_symlink_is_not_followed(self):
        real = self.tmp / "real"
        real.write_text("healthy=yes\n")
        (self.tmp / "out").symlink_to(real)
        self.assertIsNone(fo.read_text_limited(self.tmp / "out"))

    def test_a_device_is_not_read(self):
        self.assertIsNone(self.run_with_timeout(lambda: fo.read_text_limited("/dev/zero")))

    def test_at_most_64_kib_are_read(self):
        (self.tmp / "out").write_bytes(b"x" * (1 << 20))
        self.assertEqual(len(fo.read_text_limited(self.tmp / "out")), 65536)

    def test_a_regular_file_is_read_and_a_missing_one_is_none(self):
        (self.tmp / "out").write_text("a=1\n")
        self.assertEqual(fo.read_text_limited(self.tmp / "out"), "a=1\n")
        self.assertIsNone(fo.read_text_limited(self.tmp / "nope"))


class SandboxHelper(unittest.TestCase):
    """A Sandbox with a fake popen that lets each test act as the operator inside the step directory."""

    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.cfg = fakes.make_config(self.tmp, self.tmp / "lib")
        self.etc = self.tmp / "etc"
        self.etc.mkdir()
        for name, text in (("host.token", fakes.SENTINEL_TOKEN), ("fingerprint.key", fakes.FP_KEY.hex())):
            (self.etc / name).write_text(text)
            (self.etc / name).chmod(0o600)
        self.cat = fakes.catalog()
        self.argvs, self.listing = [], []
        self.me = (os.getuid(), os.getgid())

    def sandbox(self, act=None, rc=0, log_text="", owner=None, root=None):
        outer = self

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
                return rc
        return fo.Sandbox(self.cfg, self.cat, "r1", steps_dir=self.tmp / "steps", popen=Proc, runner=lambda *a, **k: None,
                          chown=False, secret_dir=self.etc, secret_owner=owner or self.me, root=root or self.tmp / "root")

    def run_op(self, sb, name="health", params=None, head=""):
        return sb.run(name, fo.op_of(self.cat, name), params or {}, "1", self.tmp / "log", head)

    def props(self, argv):
        return {argv[i + 1] for i, a in enumerate(argv) if a == "-p"}


class SandboxSafetyTest(SandboxHelper):
    def test_a_symlinked_out_file_is_ignored_not_followed(self):
        other = self.tmp / "other"
        other.write_text(HEALTH_OUT)

        def act(d):
            (d / "out").unlink()
            (d / "out").symlink_to(other)
        res = self.run_op(self.sandbox(act))
        self.assertEqual((res.status, res.outputs), ("failed", {}))

    def test_a_fifo_out_file_does_not_hang_root(self):
        def act(d):
            (d / "out").unlink()
            os.mkfifo(d / "out")
        box = {}
        t = threading.Thread(target=lambda: box.update(r=self.run_op(self.sandbox(act))), daemon=True)
        t.start()
        t.join(5)
        self.assertFalse(t.is_alive())
        self.assertEqual(box["r"].status, "failed")

    def test_a_detail_file_that_is_not_regular_is_ignored(self):
        def act(d):
            (d / "out").write_text(HEALTH_OUT)
            (d / "detail.json").unlink()
            (d / "detail.json").symlink_to("/dev/zero")
        res = self.run_op(self.sandbox(act))
        self.assertEqual((res.status, res.detail), ("done", {"notes": [], "rows": None}))

    def test_the_unit_has_every_sandbox_property(self):
        self.run_op(self.sandbox(lambda d: (d / "out").write_text(HEALTH_OUT)))
        props = self.props(self.argvs[0])
        self.assertTrue(set(fo.STEP_PROPS) <= props)
        hidden = next(p for p in props if p.startswith("InaccessiblePaths=")).split("=", 1)[1].split()
        for path in (*fo.HIDDEN_ALWAYS, str(pathlib.Path(self.cfg["ledger"]).parent), self.cfg["log_dir"]):
            self.assertIn("-" + path, hidden)
        self.assertIn(f"ReadOnlyPaths={pathlib.Path(self.cfg['clone_dir']).parent}", props)
        # Changed with the allowlist sandbox: /run is an empty tmpfs, so the step's directory is bound into it, not opened up.
        self.assertTrue(any(p.startswith("BindPaths=") and "/steps/" in p for p in props))
        self.assertFalse(any(p.startswith("ReadWritePaths=") for p in props))
        self.assertIn(f"BindReadOnlyPaths={fo.EGRESS_SOCK}", props)

    def test_another_tiers_directories_and_deploy_dir_are_hidden(self):
        root = self.tmp / "root"
        (root / "etc" / "factory-prod-two").mkdir(parents=True)
        (root / "etc" / "factory-prod-two" / "config.json").write_text(json.dumps({"deploy_dir": "/srv/two"}))
        self.cfg["deploy_dir"] = "/srv/mine"
        self.run_op(self.sandbox(lambda d: (d / "out").write_text(HEALTH_OUT), root=root))
        hidden = next(p for p in self.props(self.argvs[0]) if p.startswith("InaccessiblePaths=")).split("=", 1)[1].split()
        for path in ("/srv/two", "/srv/mine", "/run/factory-prod-two", "/var/lib/factory-prod-two"):
            self.assertIn("-" + path, hidden)

    def test_a_deploy_dir_that_cant_be_hidden_fails_the_step_before_it_starts(self):
        self.cfg["deploy_dir"] = "/srv/two words"
        res = self.run_op(self.sandbox())
        self.assertEqual(res.status, "failed")
        self.assertEqual(self.argvs, [])


class StepSecretsTest(SandboxHelper):
    def test_each_operation_gets_only_its_declared_secrets(self):
        params = {"release-wait": {"sha": "a" * 40}, "http-check": {"target": "web", "path": "/status", "expect_status": "200"}}
        for name, labels in self.cat["broker"]["op_secrets"].items():
            with self.subTest(name):
                self.listing.clear()
                self.run_op(self.sandbox(), name, params.get(name), head="a" * 40)
                self.assertEqual([f for f in self.listing[0] if f not in ("out", "detail.json")],
                                 sorted(f"secret-{label}" for label in labels))

    def test_a_secret_file_not_owned_by_root_is_refused(self):
        res = self.run_op(self.sandbox(owner=(0, 0)))  # the temp files belong to this user, not root
        self.assertEqual(res.status, "failed")
        self.assertIn("host.token", res.why)
        self.assertEqual(self.argvs, [])

    def test_a_secret_file_with_loose_mode_is_refused(self):
        (self.etc / "host.token").chmod(0o640)
        self.assertEqual(self.run_op(self.sandbox()).status, "failed")
        self.assertEqual(self.argvs, [])

    def test_a_symlinked_secret_is_refused(self):
        (self.etc / "real.token").write_text(fakes.SENTINEL_TOKEN)
        (self.etc / "real.token").chmod(0o600)
        (self.etc / "host.token").unlink()
        (self.etc / "host.token").symlink_to(self.etc / "real.token")
        self.assertEqual(self.run_op(self.sandbox()).status, "failed")
        self.assertEqual(self.argvs, [])

    def test_ok_with_correct_owner_and_mode(self):
        res = self.run_op(self.sandbox(lambda d: (d / "out").write_text(HEALTH_OUT)))
        self.assertEqual(res.status, "done", res.why)

    def test_an_operation_without_an_op_secrets_entry_is_refused(self):
        cat = fakes.catalog_dict()
        cat["broker"]["op_secrets"].pop("health")
        self.cat = fakes.load(cat)
        res = self.run_op(self.sandbox())
        self.assertEqual(res.status, "failed")
        self.assertEqual(self.argvs, [])

    def test_the_step_refuses_a_secret_that_doesnt_match_its_shape(self):
        env = Env()
        self.addCleanup(env.close)
        for value, needle in (("short", "token secret is unusable"), ("x" * 30 + " y", "token secret is unusable")):
            with self.subTest(value):
                env.sandbox.token_for_step = value
                res = env.run_op("health")
                self.assertEqual(res.status, "failed")
                self.assertIn(needle, res.why)
        env.sandbox.token_for_step = None
        with mock.patch.object(fakes, "FP_KEY", b"\x01" * 8):
            res = env.run_op("capture-state")
        self.assertIn("key secret is too short", res.why)


class RedactionTest(SandboxHelper):
    def test_every_installed_secret_is_redacted_from_the_log_and_the_reason(self):
        tok, key = fakes.SENTINEL_TOKEN, fakes.FP_KEY
        leaks = [tok, tok.encode().hex(), base64.b64encode(tok.encode()).decode(), key.hex(), base64.b64encode(key).decode()]
        text = "starting\n" + "\n".join(f"leak {x}" for x in leaks) + f"\nFAILED: bad credentials {tok}\n"
        res = self.run_op(self.sandbox(rc=1, log_text=text), "capture-state", head="a" * 40)
        log = (self.tmp / "log").read_text()
        for leak in leaks:
            self.assertNotIn(leak, log)
            self.assertNotIn(leak, res.why)
        self.assertIn("[redacted]", log)
        self.assertEqual(res.status, "failed")

    def test_a_secret_in_a_note_is_redacted_too(self):
        def act(d):
            (d / "out").write_text(HEALTH_OUT)
            (d / "detail.json").write_text(json.dumps({"notes": [f"the token is {fakes.SENTINEL_TOKEN}"]}))
        res = self.run_op(self.sandbox(act))
        self.assertEqual(res.detail["notes"], ["the token is [redacted]"])

    def test_redact_handles_each_encoding(self):
        out = fo.redact("a SECRETVALUE1 b " + "SECRETVALUE1".encode().hex() + " " + base64.b64encode(b"SECRETVALUE1").decode(),
                        [b"SECRETVALUE1"])
        self.assertEqual(out.count("[redacted]"), 3)

    def test_a_long_token_like_run_is_scrubbed_but_commit_ids_stay(self):
        self.assertEqual(fo.scrub(f"bad {'Z' * 30} at {'a' * 40}"), f"bad [scrubbed] at {'a' * 40}")


class SecrecyTest(unittest.TestCase):
    """Sentinel secrets never appear in stdout, stderr, OP_OUT, the step log, the ledger or a note."""

    def test_sentinels_never_leave_the_operations_or_the_broker(self):
        env = Env()
        self.addCleanup(env.close)
        out, err = io.StringIO(), io.StringIO()
        with mock.patch("sys.stdout", out), mock.patch("sys.stderr", err):
            for name in ("health", "capture-state", "snapshot-status", "snapshot-now", "drift-scan"):
                env.run_op(name)
            for name in ("host-check", "check-token"):
                env.run_op(name, release_head="")
            env.run_op("http-check", target="web", path="/status", expect_status="500")
            env.world.api = lambda *a: fakes.fake_host.Resp(500, {}, json.dumps({"error": fakes.SENTINEL_VALUE}).encode())
            env.run_op("capture-state")
        haystack = [out.getvalue(), err.getvalue(), env.sandbox.stderr.getvalue()]
        for f in env.tmp.rglob("*"):
            if f.is_file() and ".git" not in f.parts and not f.name.startswith("secret-") and f.suffix != ".pack":
                try:
                    haystack.append(f.read_text())
                except UnicodeDecodeError:
                    pass
        text = "\n".join(haystack)
        self.assertNotIn(fakes.SENTINEL_TOKEN, text)
        self.assertNotIn(fakes.SENTINEL_VALUE, text)
        self.assertNotIn(fakes.FP_KEY.hex(), text)
        # ... and the operations did print something, so the scan above is not scanning nothing.
        self.assertIn("FAILED", text)
        self.assertTrue(any(f.name == "out" and f.read_text() for f in env.tmp.rglob("out")))

    def test_fingerprints_do_not_reveal_values_and_depend_on_the_key(self):
        env = Env()
        self.addCleanup(env.close)
        a = env.run_op("capture-state").outputs
        self.assertTrue(all(re.fullmatch(r"[0-9a-f]{64}", v) for k, v in a.items() if k.startswith("fp_") and k != "fp_key_id"))
        with mock.patch.object(fakes, "FP_KEY", bytes(range(1, 33))):
            b = env.run_op("capture-state").outputs
        self.assertNotEqual(a["fp_web"], b["fp_web"])
        self.assertNotEqual(a["fp_key_id"], b["fp_key_id"])

    def test_the_github_token_is_never_recorded(self):
        env = Env()
        self.addCleanup(env.close)
        fakes.no_live_steps(self)
        with mock.patch.object(fo, "LOCK", env.tmp / "lock"), mock.patch.object(fo, "STEPS_DIR", env.tmp / "steps"):
            fo.cmd_baseline(env.cfg, fo_gates(), env.cat, env.secret, "n", False, env.svc_factory(), fakes.Console())
            routes, _ = fakes.gate_routes(env)
            gh = fo.GitHub(env.cfg["repo"], fakes.TOKEN, opener=fakes.FakeOpener(env.cfg["repo"], routes))
            fo.serve_one(env.cfg, fo_gates(), env.cat, json.dumps({"run_id": 55, "pr": 7, "token": fakes.TOKEN}), env.secret,
                         svc_factory=lambda cfg, token: env.services(gh))
        ledger = pathlib.Path(env.cfg["ledger"]).read_text()
        self.assertIn('"event": "finish"', ledger)
        self.assertNotIn(fakes.TOKEN, ledger)
        self.assertFalse(any(fakes.TOKEN in json.dumps(e) for e in env.sandbox.envs))


def fo_gates():
    import gates
    return gates


if __name__ == "__main__":
    unittest.main()
