"""host/ci_launcher.py: a cycle mints a JIT config, starts one disposable runner, watches it against every limit,
removes it and its registration; a stop or a SIGTERM cleans up; resolve finds the App's installation and the runner
group; the check and the firewall check trip on any failure, their own included. GitHub is a local fake whose
answers follow the fake container's state, docker a script that records its calls, setpriv one that execs, openssl
the real one with a generated key."""

import base64
import contextlib
import fcntl
import http.server
import io
import json
import os
import pathlib
import re
import shutil
import signal
import struct
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import unittest
import urllib.parse
from unittest import mock

HOST = pathlib.Path(__file__).resolve().parents[1] / "host"
sys.path.insert(0, str(HOST))
import ci_launcher as launcher  # noqa: E402

OPENSSL = shutil.which("openssl")
ONLINE, OFFLINE = {"status": "online", "busy": False}, {"status": "offline", "busy": False}
BUSY = {"status": "online", "busy": True}


class FakeGitHub(http.server.BaseHTTPRequestHandler):
    calls = []
    jit_status = 201
    jit_answer = None  # a 201's body in place of the usual one
    jit_delay = 0
    jit_gate = None  # a threading.Event the answer waits for, after jit_delay
    delete_status = 204
    delete_body = {"message": "refused"}
    deleted = set()
    registered = {}  # runner ID: name, as generate-jitconfig registered them (the runner list's answer)
    minted = 0
    revoked = set()  # tokens GitHub answers 401 to
    # [callable]: the runner's GET answer, a dict, an HTTP status, "garbage" (a 200 that isn't JSON) or "short"
    # (a body cut off).
    view = [lambda: 404]
    views = {}  # runner ID: its GET answer, in place of view's
    installation ={"id": 9, "permissions": {"organization_self_hosted_runners": "write"}}
    groups = [{"id": 5, "name": "factory-ci", "visibility": "selected", "allows_public_repositories": False}]

    def reply(self, status, body=None):
        data = b"" if body is None else json.dumps(body).encode()
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass  # the launcher stopped mid-call

    def raw(self, data, length):
        self.send_response(200)
        self.send_header("Content-Length", str(length))
        self.end_headers()
        self.wfile.write(data)

    def handle_one(self, method):
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length)) if length else None
        FakeGitHub.calls.append((method, self.path, self.headers.get("Authorization"), body))
        runner = re.fullmatch(r"/orgs/acme/actions/runners/(\d+)", self.path)
        if method == "POST" and self.path == "/app/installations/9/access_tokens":
            FakeGitHub.minted += 1
            token = "inst-token" if FakeGitHub.minted == 1 else f"inst-token-{FakeGitHub.minted}"
            return self.reply(201, {"token": token, "expires_at": "2099-01-01T00:00:00Z"})
        if (self.headers.get("Authorization") or "").removeprefix("Bearer ") in FakeGitHub.revoked:
            return self.reply(401, {"message": "Bad credentials"})
        url = urllib.parse.urlsplit(self.path)
        if method == "GET" and url.path == "/orgs/acme/actions/runners":
            name = urllib.parse.parse_qs(url.query).get("name", [None])[0]
            found = [{"id": i, "name": n} for i, n in sorted(FakeGitHub.registered.items())
                     if i not in FakeGitHub.deleted and name in (None, n)]
            return self.reply(200, {"total_count": len(found), "runners": found})
        if method == "POST" and self.path == "/orgs/acme/actions/runners/generate-jitconfig":
            # The runner is registered when GitHub answers, after jit_delay and jit_gate: a cycle stopped while it
            # waits never hears its ID, and a lookup before then finds nothing yet.
            if FakeGitHub.jit_delay:  # never time.sleep(0): tests patch the time module's sleep
                time.sleep(FakeGitHub.jit_delay)
            if FakeGitHub.jit_gate is not None:
                FakeGitHub.jit_gate.wait(60)
            if FakeGitHub.jit_status != 201:
                return self.reply(FakeGitHub.jit_status, {"message": "nope"})
            answer = FakeGitHub.jit_answer or {"runner": {"id": 42}, "encoded_jit_config": "SklUQ09ORklH"}
            runner_id = (answer.get("runner") or {}).get("id") if isinstance(answer.get("runner"), dict) else None
            if isinstance(runner_id, int):
                FakeGitHub.registered[runner_id] = body["name"]
            return self.reply(201, answer)
        if runner and method == "DELETE":
            if FakeGitHub.delete_status == 204:
                FakeGitHub.deleted.add(int(runner.group(1)))
                return self.reply(204)
            return self.reply(FakeGitHub.delete_status, FakeGitHub.delete_body)
        if runner and method == "GET":
            if int(runner.group(1)) in FakeGitHub.deleted:
                return self.reply(404, {"message": "Not Found"})
            answer = FakeGitHub.views.get(int(runner.group(1))) or FakeGitHub.view[0]()
            if answer == "garbage":
                return self.raw(b"<html>", 6)
            if answer == "short":
                return self.raw(b'{"id"', 100)
            if answer == "list":
                return self.reply(200, [{"status": "online"}])
            if isinstance(answer, int):
                return self.reply(answer, {"message": "no"})
            return self.reply(200, {"id": int(runner.group(1)), **answer})
        if method == "GET" and self.path == "/orgs/acme/installation":
            return self.reply(200, FakeGitHub.installation)
        if method == "GET" and self.path == "/orgs/acme/actions/runner-groups/5":
            return self.reply(200, FakeGitHub.groups[0]) if FakeGitHub.groups else self.reply(404)
        if method == "GET" and self.path.startswith("/orgs/acme/actions/runner-groups"):
            return self.reply(200, {"runner_groups": FakeGitHub.groups})
        return self.reply(404, {"message": "Not Found"})

    def do_GET(self):
        self.handle_one("GET")

    def do_POST(self):
        self.handle_one("POST")

    def do_DELETE(self):
        self.handle_one("DELETE")

    def log_message(self, *args):
        pass


# docker: records each call (argv, pid, and the env file's mode and contents at `run`), answers from control files.
# `wait` lasts wait_sleep seconds (then marks the container exited) or until `docker kill`.
FAKE_DOCKER = r'''#!/usr/bin/env python3
import json, os, sys, time
d = os.path.dirname(os.path.abspath(sys.argv[0]))
args = sys.argv[1:]
def path(name):
    return os.path.join(d, name)
def control(name, default="0"):
    return open(path(name)).read() if os.path.exists(path(name)) else default
rec = {"argv": args, "env": sorted(os.environ), "pid": os.getpid(), "exited": os.path.exists(path("exited"))}
if args[:1] == ["run"] and "--env-file" in args:
    f = args[args.index("--env-file") + 1]
    rec["env_file"] = {"mode": oct(os.stat(f).st_mode & 0o777), "text": open(f).read()}
with open(path("calls.jsonl"), "a") as log:
    log.write(json.dumps(rec) + "\n")
if args[:2] == ["network", "inspect"]:
    sys.exit(1)
if args[:1] == ["rm"] and "-check-" not in args[-1]:
    for marker in ("killed", "exited"):
        if os.path.exists(path(marker)):
            os.unlink(path(marker))
if args[:1] == ["kill"]:
    open(path("killed"), "w").close()
if args[:1] == ["run"] and "-d" in args and "--entrypoint" not in args:
    time.sleep(float(control("run_sleep")))
if args[:2] == ["network", "create"] and "--subnet" in args:
    sys.exit(int(control("netcreate_rc")))
if args[:1] == ["wait"]:
    end = time.time() + float(control("wait_sleep"))
    while time.time() < end and not os.path.exists(path("killed")):
        time.sleep(0.02)
    if os.path.exists(path("killed")):
        print("137")
    else:
        open(path("exited"), "w").close()
        print(control("wait_out"))
if args[:1] == ["info"]:
    sys.exit(int(control("info_rc")))
if args[:1] == ["run"] and "--entrypoint" in args and "-d" not in args:
    if args[args.index("--entrypoint") + 1] == "sh":
        device = args[args.index("--device") + 1] if "--device" in args else ""
        if device in control("gpu_fail", "").split():
            sys.exit(1)
        name = device.split("=", 1)[-1]
        report = json.loads(control("gpu_reports", "{}")).get(device)
        print(report if report is not None else name if name.startswith(("GPU-", "MIG-")) else "GPU-" + name.replace(":", "-"))
        sys.exit(0)
    network = args[args.index("--network") + 1]
    sys.exit(int(control("reach_rc" if network.endswith("-check-a") else "probe_rc")))
'''
# setpriv: logs its options, then execs what follows `--` (the launcher's env -i keeps the test's environment out).
FAKE_SETPRIV = ('#!/usr/bin/env bash\nopts=()\nwhile [[ $1 != -- ]]; do opts+=("$1"); shift; done; shift\n'
                'printf "%s\\n" "${opts[*]}" >> "$(dirname "$0")/setpriv.log"\nexec "$@"\n')
# python, for the host-side probe: records its arguments, exits host_rc.
FAKE_PYTHON = r'''#!/usr/bin/env python3
import json, os, sys
d = os.path.dirname(os.path.abspath(sys.argv[0]))
with open(os.path.join(d, "python.jsonl"), "a") as log:
    log.write(json.dumps(sys.argv[1:]) + "\n")
p = os.path.join(d, "host_rc")
sys.exit(int(open(p).read()) if os.path.exists(p) else 0)
'''
# nft, systemctl and loginctl: record their arguments, print <name>.out, exit <name>.rc.
FAKE_RECORDER = ('#!/usr/bin/env bash\nprintf "%s\\n" "$*" >> "$(dirname "$0")/$(basename "$0").log"\n'
                 'printf "%s %s\\n" "$(basename "$0")" "$*" >> "$(dirname "$0")/all.log"\n'
                 'cat "$(dirname "$0")/$(basename "$0").out" 2>/dev/null\n'
                 'exit "$(cat "$(dirname "$0")/$(basename "$0").rc" 2>/dev/null || echo 0)"\n')
# For the real-daemon test: a static Linux program that only exits 0 (the exit system call with 0), by the daemon's
# architecture as `docker info` names it: (ELF machine, code).
EXIT_ZERO = {
    "x86_64": (0x3E, bytes.fromhex("31ff" "b83c000000" "0f05")),  # xor edi, edi; mov eax, 60; syscall
    "aarch64": (0xB7, struct.pack("<3I", 0xD2800000, 0xD2800BA8, 0xD4000001)),  # mov x0, #0; mov x8, #93; svc #0
}


def exit_zero_elf(machine, code):
    """A 64-bit little-endian ELF executable: its header, one loadable segment (the whole file, read and execute) and
    the code, which starts straight after them."""
    base, header_size, segment_size = 0x400000, 64, 56
    size = header_size + segment_size + len(code)
    ident = b"\x7fELF" + bytes([2, 1, 1, 0]) + bytes(8)  # 64-bit, little-endian, version 1, System V
    header = ident + struct.pack("<HHIQQQIHHHHHH", 2, machine, 1, base + header_size + segment_size, header_size, 0,
                                 0, header_size, segment_size, 1, 0, 0, 0)  # an executable; no section headers
    segment = struct.pack("<IIQQQQQQ", 1, 5, 0, base, base, size, size, 0x1000)  # PT_LOAD, R+X, the whole file
    return header + segment + code


ROUTES = ("Iface\tDestination\tGateway \tFlags\tRefCnt\tUse\tMetric\tMask\t\tMTU\tWindow\tIRTT\n"
          "eth0\t0002A8C0\t00000000\t0001\t0\t0\t100\t00FFFFFF\t0\t0\t0\n"
          "eth0\t00000000\t0101A8C0\t0003\t0\t0\t100\t00000000\t0\t0\t0\n")


@unittest.skipUnless(OPENSSL, "needs openssl")
class Launcher(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), FakeGitHub)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.keydir = tempfile.TemporaryDirectory()
        cls.key = pathlib.Path(cls.keydir.name) / "app.pem"
        subprocess.run([OPENSSL, "genrsa", "-out", str(cls.key), "2048"], check=True, capture_output=True)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.keydir.cleanup()

    def setUp(self):
        FakeGitHub.calls = []
        FakeGitHub.jit_status = 201
        FakeGitHub.jit_answer = None
        FakeGitHub.jit_delay = 0
        FakeGitHub.jit_gate = None
        FakeGitHub.delete_status = 204
        FakeGitHub.delete_body = {"message": "refused"}
        FakeGitHub.deleted = set()
        FakeGitHub.registered = {}
        FakeGitHub.minted = 0
        FakeGitHub.revoked = set()
        FakeGitHub.view = [self.container_view]
        FakeGitHub.views = {}
        self.tmp = tempfile.TemporaryDirectory()
        root = pathlib.Path(self.tmp.name)
        self.bin = root / "bin"
        self.bin.mkdir()
        for name, text in (("docker", FAKE_DOCKER), ("setpriv", FAKE_SETPRIV), ("python", FAKE_PYTHON),
                           ("nft", FAKE_RECORDER), ("systemctl", FAKE_RECORDER), ("loginctl", FAKE_RECORDER)):
            (self.bin / name).write_text(text)
            (self.bin / name).chmod(0o755)
        self.state = root / "state"
        self.state.mkdir()
        self.state.chmod(0o711)
        self.cgroup = root / "cgroup"
        (self.cgroup / f"user@{os.getuid()}.service").mkdir(parents=True)
        (self.cgroup / "memory.max").write_text("17179869184\n")
        (self.cgroup / "cpu.max").write_text("800000 100000\n")
        (self.cgroup / f"user@{os.getuid()}.service" / "cgroup.controllers").write_text("cpuset cpu io memory pids\n")
        (root / "route").write_text(ROUTES)
        self.wants = root / "wants"
        self.wants.mkdir()
        for name in ("factory-ci-slot@1.service", "factory-ci-slot@2.service", "other.service"):
            (self.wants / name).touch()
        self.conf = {
            "api": f"http://127.0.0.1:{self.server.server_address[1]}", "org": "acme", "client_id": "Iv23abc",
            "key": str(self.key), "openssl": OPENSSL, "installation_id": 9, "group": "factory-ci", "group_id": 5,
            "labels": ["factory-ci"], "name_prefix": "box-ci", "container": "factory-ci", "image": "sha256:" + "d" * 64,
            "user": "factory-ci", "uid": os.getuid(), "gid": os.getgid(), "home": str(root),
            "setpriv": str(self.bin / "setpriv"), "env": shutil.which("env"), "docker": str(self.bin / "docker"),
            "python": str(self.bin / "python"), "nft": str(self.bin / "nft"), "systemctl": str(self.bin / "systemctl"),
            "loginctl": str(self.bin / "loginctl"), "wants_dir": str(self.wants), "fw_retry_seconds": 0,
            "job": {"cpus": 4, "memory": "8g", "pids": 8192, "shm": "1g", "hours": 6},
            "idle_hours": 24, "min_free_gb": 0, "tick_seconds": 0.05, "poll_seconds": 0.1, "gone_checks": 2,
            "gone_delay": 0, "docker_wait_seconds": 0, "state_owner": os.getuid(),
            "state_dir": str(self.state), "tripped": str(self.state / "tripped"), "unit": "factory-ci",
            "firewall_table": "factory_ci", "cgroup": str(self.cgroup), "route_file": str(root / "route"),
            "probe": {"targets": "127.0.0.1 10.0.2.2 2606:4700:4700::1111", "ports": "22 5432"}}

    def tearDown(self):
        self.tmp.cleanup()

    def container_view(self):
        """GitHub's view of the runner, following the fake container: online and idle while it runs, removed once it
        ran to its end (for good, a kill after that included), registered but offline once killed mid-run."""
        if (self.bin / "exited").exists():
            return 404
        return OFFLINE if (self.bin / "killed").exists() else ONLINE

    def control(self, name, value):
        (self.bin / name).write_text(str(value))

    def calls(self):
        path = self.bin / "calls.jsonl"
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def argvs(self, verb):
        return [c["argv"] for c in self.calls() if c["argv"][:1] == [verb]]

    def kills_while_running(self):
        """Kills of a running container. A poll can land between the container's exit and the launcher seeing it, and
        GitHub has removed the runner by then: that kill finds the container gone, and is no kill of a job."""
        return [c["argv"] for c in self.calls() if c["argv"][:1] == ["kill"] and not c["exited"]]

    def records(self, slot):
        """What the state holds for the slot, but its lock (slot-N.lock, which stays)."""
        return sorted(p.name for p in self.state.glob(f"slot-{slot}.*") if p.name != f"slot-{slot}.lock")

    def github(self, method=None):
        return [(m, p) for m, p, _, _ in FakeGitHub.calls if method in (None, m)]

    def fails(self, slot=1):
        return (self.state / f"slot-{slot}.fails").read_text()

    def trip_steps(self):
        """systemctl's part of a trip: the slots stopped, then the slots, the gate and the timers disabled (nothing
        starts the runner user's manager at boot), then that manager stopped."""
        return ["stop factory-ci-slot@*.service", "disable factory-ci-slot@1.service factory-ci-slot@2.service",
                "disable factory-ci-gate.service factory-ci-check.timer factory-ci-fw.timer",
                "stop factory-ci-check.timer factory-ci-fw.timer",
                f"stop user@{os.getuid()}.service"]

    def test_a_cycle(self):
        with mock.patch.dict(os.environ, {"LAUNCHER_ONLY": "secret"}):
            self.assertEqual(launcher.run(self.conf, 1), 0)
        # One token for the cycle; GitHub removed the runner after its job, so there's nothing to deregister. The
        # launcher polls the runner every poll_seconds until docker wait returns, so the polls before the fake docker
        # has started and returned depend on how fast the machine starts a process: one or more, and nothing else.
        calls = self.github()
        self.assertEqual(calls[:2], [("POST", "/app/installations/9/access_tokens"),
                                     ("POST", "/orgs/acme/actions/runners/generate-jitconfig")])
        self.assertGreaterEqual(len(calls), 3)
        self.assertEqual(set(calls[2:]), {("GET", "/orgs/acme/actions/runners/42")})
        self.assertEqual(FakeGitHub.calls[0][3], {"permissions": {"organization_self_hosted_runners": "write"}})
        jit_body = FakeGitHub.calls[1][3]
        # self-hosted too: a just-in-time runner gets only the labels it's registered with, and the tier's jobs ask
        # for [self-hosted, factory-ci].
        self.assertEqual((jit_body["runner_group_id"], jit_body["labels"]), (5, ["self-hosted", "factory-ci"]))
        self.assertRegex(jit_body["name"], r"^box-ci-1-[0-9a-f]{6}$")
        self.assertEqual(FakeGitHub.calls[1][2], "Bearer inst-token")
        run = [c for c in self.calls() if c["argv"][:1] == ["run"]][0]
        argv = run["argv"]
        for flag, value in (("--cpus", "4"), ("--memory", "8g"), ("--memory-swap", "8g"), ("--pids-limit", "8192"),
                            ("--shm-size", "1g"), ("--security-opt", "no-new-privileges"), ("--network", "factory-ci-1"),
                            ("--name", "factory-ci-1"), ("--log-driver", "local")):
            self.assertEqual(argv[argv.index(flag) + 1], value, flag)
        self.assertIn("max-size=20m", argv)
        self.assertEqual([argv[i + 1] for i, a in enumerate(argv) if a == "--cap-drop"], ["NET_RAW", "MKNOD"])
        self.assertEqual(argv[-1], self.conf["image"])
        # The JIT config only in a 0600 file, gone once docker run returns; never on a command line.
        self.assertEqual(run["env_file"]["mode"], "0o600")
        self.assertIn("ACTIONS_RUNNER_INPUT_JITCONFIG=SklUQ09ORklH", run["env_file"]["text"])
        self.assertFalse(any("SklUQ09ORklH" in a for c in self.calls() for a in c["argv"]))
        self.assertEqual(list(self.state.glob("*.env")), [])
        # The runner's name was marked pending while GitHub was asked, and the marker went once its ID was recorded.
        self.assertEqual(list(self.state.glob("slot-1.pending-*")), [])
        # docker as the runner user through setpriv, with a fixed environment and nothing of the launcher's.
        self.assertEqual(set((self.bin / "setpriv.log").read_text().splitlines()),
                         {f"--reuid={os.getuid()} --regid={os.getgid()} --clear-groups --inh-caps=-all"})
        self.assertTrue({"DOCKER_HOST", "HOME", "PATH", "XDG_RUNTIME_DIR"} <= set(run["env"]))
        self.assertNotIn("LAUNCHER_ONLY", run["env"])
        self.assertEqual(len(self.argvs("wait")), 1)
        self.assertEqual(self.argvs("rm")[-1], ["rm", "-f", "-v", "factory-ci-1"])
        self.assertEqual(self.fails(), "0")
        self.assertFalse((self.state / "slot-1.runner").exists())

    def test_the_log_options_are_ones_the_local_driver_takes(self):
        # One log file, uncompressed: the local driver compresses rotated files by default, which takes at least two,
        # and refuses max-file=1 with it (Docker 29: "compression cannot be enabled when max file count is 1"). Job
        # containers and the check's own take the same flags.
        flags = launcher.job_flags(self.conf)
        self.assertEqual(flags[flags.index("--log-driver") + 1], "local")
        opts = dict(flags[i + 1].split("=", 1) for i, flag in enumerate(flags) if flag == "--log-opt")
        self.assertEqual(opts, {"max-size": "20m", "max-file": "1", "compress": "false"})

    def test_setup_restarts_only_a_slot_whose_runner_is_retired(self):
        conf_file = pathlib.Path(self.tmp.name) / "launcher.json"
        conf_file.write_text(json.dumps(self.conf))
        def retire(conf=str(conf_file), slot="1"):
            with contextlib.redirect_stderr(io.StringIO()):
                return launcher.main(["ci_launcher.py", "retire", conf, slot])
        self.assertEqual(retire(), launcher.IDLE)  # no runner: between cycles
        (self.state / "slot-1.runner").write_text("42")
        self.assertEqual(retire(), launcher.IDLE)  # deregistered (204): nothing can be assigned to it now
        self.assertIn(42, FakeGitHub.deleted)
        FakeGitHub.deleted, FakeGitHub.delete_status = set(), 422  # GitHub: it's running a job
        self.assertEqual(retire(), 0)
        FakeGitHub.delete_status = 500
        self.assertEqual(retire(), 0)
        FakeGitHub.delete_status = 204
        self.state.chmod(0o777)  # a state that isn't root's alone: unknown, so not idle
        self.assertEqual(retire(), 0)
        self.state.chmod(0o711)
        self.assertEqual(retire(str(conf_file) + ".missing"), 0)
        self.assertEqual(retire(slot="x"), 0)

    def test_retire_asks_github_before_it_deregisters(self):
        conf_file = pathlib.Path(self.tmp.name) / "launcher.json"
        conf_file.write_text(json.dumps(self.conf))
        def retire():
            with contextlib.redirect_stderr(io.StringIO()):
                return launcher.main(["ci_launcher.py", "retire", str(conf_file), "1"])
        (self.state / "slot-1.runner").write_text("42")
        FakeGitHub.view = [lambda: BUSY]  # GitHub says it's running a job: no removal tried
        self.assertEqual(retire(), 0)
        self.assertNotIn("DELETE", [m for m, _ in self.github()])
        FakeGitHub.view = [lambda: 404]  # gone already
        self.assertEqual(retire(), launcher.IDLE)
        (self.state / "slot-1.runner").unlink()
        # A runner a stopped cycle asked for under a pending marker counts too, found by its name: busy, it keeps the
        # slot; idle, it's removed. The marker stays: its cycle may still be running, and the slot's stop resolves it.
        FakeGitHub.registered[43] = "box-ci-1-feed00"
        marker = self.state / "slot-1.pending-feed00"
        marker.write_text("box-ci-1-feed00")
        FakeGitHub.view = [lambda: BUSY]
        self.assertEqual(retire(), 0)
        FakeGitHub.view = [lambda: ONLINE]
        self.assertEqual(retire(), launcher.IDLE)
        self.assertIn(43, FakeGitHub.deleted)
        self.assertTrue(marker.exists())
        marker.unlink()
        (self.state / "slot-1.runner").write_text("42")
        # A cycle that registered a new runner while retire removed the old one: not idle.
        FakeGitHub.view = [lambda: ONLINE]
        real = launcher.Tokens.call
        def call(tokens, method, path, body=None):
            result = real(tokens, method, path, body)
            if method == "DELETE":
                (self.state / "slot-1.runner").write_text("99")
            return result
        with mock.patch.object(launcher.Tokens, "call", call):
            self.assertEqual(retire(), 0)
        # A state directory that's missing is unknown, not idle.
        missing = {**self.conf, "state_dir": str(pathlib.Path(self.tmp.name) / "gone")}
        conf_file.write_text(json.dumps(missing))
        self.assertEqual(retire(), 0)

    def test_a_leftover_github_no_longer_has_is_dropped(self):
        (self.state / "slot-1.leftover-55").write_text("55")
        FakeGitHub.delete_status = 500
        FakeGitHub.view = [lambda: 404]
        with contextlib.redirect_stderr(io.StringIO()):
            launcher.stop(self.conf, 1)
        self.assertFalse((self.state / "slot-1.leftover-55").exists())
        # The current record of one that won't go yet becomes a leftover, for a later cycle.
        (self.state / "slot-1.runner").write_text("56")
        FakeGitHub.view = [lambda: ONLINE]
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(launcher.stop(self.conf, 1), 0)
        self.assertEqual((self.state / "slot-1.leftover-56").read_text(), "56")
        self.assertFalse((self.state / "slot-1.runner").exists())

    def test_a_404_counts_as_gone_only_where_github_shows_the_organization(self):
        # GitHub answers 404 for an organization the App can't see too: a wrong org in the settings must not make every
        # runner read as gone, its registration forgotten and retire answer idle.
        conf_file = pathlib.Path(self.tmp.name) / "launcher.json"
        conf_file.write_text(json.dumps({**self.conf, "org": "other"}))
        (self.state / "slot-1.runner").write_text("42")
        with contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(launcher.main(["ci_launcher.py", "retire", str(conf_file), "1"]), 0)
        self.assertIn("a 404 on one of its runners proves nothing", err.getvalue())
        with contextlib.redirect_stderr(io.StringIO()):
            launcher.stop({**self.conf, "org": "other"}, 1)
        self.assertEqual((self.state / "slot-1.leftover-42").read_text(), "42")  # kept for a later cycle
        # The right organization: its list answers, so the same 404 is a runner that's gone.
        FakeGitHub.view = [lambda: 404]
        FakeGitHub.delete_status = 404
        with contextlib.redirect_stderr(io.StringIO()):
            launcher.stop(self.conf, 1)
        self.assertEqual(self.records(1), [])
        self.assertIn(("GET", "/orgs/acme/actions/runners?per_page=1"), self.github())

    def test_a_slot_beyond_the_count_starts_no_cycle(self):
        # Setup lowered CI_RUNNERS: the slot's next cycle exits at once, with the status its unit never restarts after.
        conf_file = pathlib.Path(self.tmp.name) / "launcher.json"
        conf_file.write_text(json.dumps({**self.conf, "slots": 1}))
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(launcher.main(["ci_launcher.py", "run", str(conf_file), "2"]), launcher.RETIRED)
        self.assertEqual((self.github(), self.calls()), ([], []))
        unit = (HOST / "setup-ci.sh").read_text()
        for line in (f"SuccessExitStatus={launcher.RETIRED}", f"RestartPreventExitStatus={launcher.RETIRED}"):
            self.assertIn(line, unit)
        # Within the count, or settings written before there was one: a cycle as usual.
        self.assertEqual(launcher.run({**self.conf, "slots": 2}, 2), 0)
        self.assertEqual(launcher.run(self.conf, 3), 0)

    def test_slot_1_removes_what_a_slot_beyond_the_count_left(self):
        # Slot 2 was retired: a registration GitHub made after its stop looked, and one it wouldn't remove then, would
        # otherwise stay, since slot 2 never runs again. Slot 1's next cycle removes both.
        FakeGitHub.registered[43] = "box-ci-2-feed00"
        (self.state / "slot-2.pending-feed00").write_text("box-ci-2-feed00")
        (self.state / "slot-2.leftover-44").write_text("44")
        (self.state / "slot-2.fails").write_text("0")
        conf = {**self.conf, "slots": 1}
        self.assertEqual(launcher.retired_slots(conf), [2])
        self.assertEqual(launcher.run(conf, 1), 0)
        self.assertTrue({43, 44} <= FakeGitHub.deleted)
        self.assertEqual(launcher.retired_slots(conf), [])
        self.assertEqual(self.records(2), [])  # its failure count too, which no cycle of its reads again
        # A container a killed cycle left still running its job (no process holds the slot's lock): GitHub is asked
        # first, and its busy runner gets no DELETE and keeps its record.
        (self.state / "slot-2.runner").write_text("46")
        FakeGitHub.views[46] = BUSY
        self.assertEqual(launcher.run(conf, 1), 0)
        self.assertNotIn(("DELETE", "/orgs/acme/actions/runners/46"), self.github())
        self.assertEqual((self.state / "slot-2.runner").read_text(), "46")
        # Idle when asked, but it takes a job before the removal (GitHub refuses it, 422): its record stays where retire
        # and the slot's stop read it, never moved to a leftover.
        FakeGitHub.views[46] = ONLINE
        FakeGitHub.delete_status = 422
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(launcher.run(conf, 1), 0)
        self.assertEqual((self.state / "slot-2.runner").read_text(), "46")
        self.assertEqual(list(self.state.glob("slot-2.leftover-*")), [])
        # Idle, it goes: the slot is beyond the count, so its runner mustn't take another job.
        FakeGitHub.delete_status = 204
        self.assertEqual(launcher.run(conf, 1), 0)
        self.assertIn(46, FakeGitHub.deleted)
        self.assertFalse((self.state / "slot-2.runner").exists())
        # The count is read again from the settings' file at the sweep: raised to 2 since slot 1's cycle started (a
        # backoff can be ten minutes), slot 2 is no longer retired, and its live cycle's marker is left alone.
        conf_file = pathlib.Path(self.tmp.name) / "launcher.json"
        conf_file.write_text(json.dumps({**self.conf, "slots": 2}))
        FakeGitHub.registered[47] = "box-ci-2-beef00"
        (self.state / "slot-2.pending-beef00").write_text("box-ci-2-beef00")
        self.assertEqual(launcher.run(conf, 1, conf_path=str(conf_file)), 0)
        self.assertNotIn(47, FakeGitHub.deleted)
        self.assertTrue((self.state / "slot-2.pending-beef00").exists())
        (self.state / "slot-2.pending-beef00").unlink()
        # Only slot 1 does it, and only for slots beyond the count.
        (self.state / "slot-3.leftover-45").write_text("45")
        launcher.run({**self.conf, "slots": 2}, 2)
        self.assertNotIn(45, FakeGitHub.deleted)
        self.assertEqual(launcher.retired_slots({**self.conf, "slots": 3}), [])
        self.assertEqual(launcher.retired_slots(self.conf), [])  # settings from before the count: none

    def test_a_marker_the_sweep_resolved_first_doesnt_fail_the_cycle(self):
        # Whatever removed a cycle's marker between minting its runner and recording it, the cycle carries on with its
        # runner, and its record, as usual.
        real = launcher.jitconfig
        def jitconfig(conf, tokens, name):
            result = real(conf, tokens, name)
            for marker in self.state.glob("slot-2.pending-*"):
                marker.unlink()
            return result
        with mock.patch.object(launcher, "jitconfig", jitconfig):
            self.assertEqual(launcher.run(self.conf, 2), 0)
        self.assertEqual(self.fails(2), "0")

    def test_a_record_is_written_whole_under_a_name_no_glob_reads(self):
        # A record is written through a temporary name of the writing process's own, so a kill mid-write leaves no
        # half-written record, and no record's glob takes the temporary for one.
        written, seen = [], []
        real = os.replace
        def replace(src, dst):
            written.append(pathlib.Path(src).name)
            # While the temporary file is there: no record's glob takes it for a record (retired_slots counts it, so
            # slot 1's sweep tidies a retired slot's).
            seen.append((launcher.record_files(self.conf, 2), launcher.pending_files(self.conf, 2)))
            return real(src, dst)
        with mock.patch.object(launcher.os, "replace", replace):
            launcher.record_runner(self.state / "slot-2.leftover-46", 46)
        self.assertEqual(written, [f".slot-2.leftover-46.{os.getpid()}.new"])
        self.assertEqual(seen, [([self.state / "slot-2.runner"], [])])
        self.assertEqual(launcher.record_files(self.conf, 2), [self.state / "slot-2.runner",
                                                               self.state / "slot-2.leftover-46"])
        # One a killed process left goes at the slot's next cycle, under its lock.
        (self.state / f".slot-1.leftover-5.{os.getpid() + 1}.new").write_text("5")
        self.assertEqual(launcher.run(self.conf, 1), 0)
        self.assertEqual(list(self.state.glob(".slot-1.*")), [])

    def test_a_pending_registration_github_never_made_is_forgotten_once_old(self):
        marker = self.state / "slot-1.pending-abc123"
        marker.write_text("box-ci-1-abc123")
        launcher.stop(self.conf, 1)
        self.assertTrue(marker.exists())  # the request may still have been in flight
        old = time.time() - launcher.PENDING_SETTLE - 60
        os.utime(marker, (old, old))
        with contextlib.redirect_stderr(io.StringIO()):
            launcher.stop({**self.conf, "org": "other"}, 1)  # GitHub can't answer: kept, however old
        self.assertTrue(marker.exists())
        launcher.stop(self.conf, 1)
        self.assertFalse(marker.exists())
        self.assertNotIn("DELETE", [m for m, _ in self.github()])

    def test_a_slot_1_sweep_leaves_a_slot_its_own_process_holds(self):
        # A retired slot whose own process still runs (a last cycle on the settings it started with, or its stop) holds
        # its lock: slot 1's sweep sends nothing for it, so it never works on records that process is rewriting.
        (self.state / "slot-2.leftover-49").write_text("49")
        conf = {**self.conf, "slots": 1}
        with open(self.state / "slot-2.lock", "a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            self.assertEqual(launcher.run(conf, 1), 0)
            self.assertFalse([p for m, p in self.github() if "/runners/49" in p])
            self.assertEqual((self.state / "slot-2.leftover-49").read_text(), "49")
        self.assertEqual(launcher.run(conf, 1), 0)  # released: the next sweep removes it
        self.assertIn(49, FakeGitHub.deleted)
        self.assertEqual(self.records(2), [])

    def test_a_cycle_and_a_stop_hold_their_slots_lock(self):
        # The other half of the sweep's lock: while a cycle or a stop runs, the slot's lock is taken.
        held = []
        real_jit, real_leftover = launcher.jitconfig, launcher.deregister_leftover
        def jitconfig(conf, tokens, name):
            with launcher.slot_lock(conf, 1, wait=False) as free:
                held.append(("cycle", not free))
            return real_jit(conf, tokens, name)
        def deregister_leftover(conf, slot, tokens, spare_busy=False):
            with launcher.slot_lock(conf, slot, wait=False) as free:
                held.append(("stop", not free))
            return real_leftover(conf, slot, tokens, spare_busy)
        with mock.patch.object(launcher, "jitconfig", jitconfig):
            self.assertEqual(launcher.run(self.conf, 1), 0)
        with mock.patch.object(launcher, "deregister_leftover", deregister_leftover):
            launcher.stop(self.conf, 1)
        self.assertEqual(held, [("cycle", True), ("stop", True)])
        # A stop waiting behind the lock (a sweep slow on GitHub) has already removed the container.
        lock = open(self.state / "slot-1.lock", "a")
        fcntl.flock(lock, fcntl.LOCK_EX)
        stopper = threading.Thread(target=launcher.stop, args=(self.conf, 1))
        try:
            removals = len(self.argvs("rm"))
            stopper.start()
            deadline = time.monotonic() + 10
            while len(self.argvs("rm")) == removals and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertEqual(self.argvs("rm")[removals:], [["rm", "-f", "-v", "factory-ci-1"]])
            self.assertTrue(stopper.is_alive())
        finally:
            lock.close()
            if stopper.is_alive() or stopper.ident:
                stopper.join(10)
        self.assertFalse(stopper.is_alive())

    def test_a_cleanly_retired_slot_is_tidied_too(self):
        # A retired slot whose stop removed every registration leaves its failure count, and maybe a killed write's
        # temporary: slot 1's sweep removes those too, and its lock stays.
        conf = {**self.conf, "slots": 2}
        (self.state / "slot-3.lock").touch()
        self.assertEqual(launcher.retired_slots(conf), [])  # a lock alone is nothing to tidy
        for leftover in ("slot-3.fails", ".slot-3.runner.4321.new"):  # each on its own gets the slot swept
            (self.state / leftover).write_text("2")
            self.assertEqual(launcher.retired_slots(conf), [3])
            self.assertEqual(launcher.run(conf, 1), 0)
            self.assertEqual(launcher.retired_slots(conf), [])
            self.assertFalse((self.state / leftover).exists())
        self.assertTrue((self.state / "slot-3.lock").exists())

    def test_slot_1_finds_a_retired_slots_registration_by_its_marker_alone(self):
        # A retired slot's stop interrupted its last cycle inside generate-jitconfig, and GitHub registered the runner
        # after the stop looked: its pending marker is all that's left, and slot 1's sweep finds the runner by its name.
        FakeGitHub.registered[48] = "box-ci-2-cafe01"
        (self.state / "slot-2.pending-cafe01").write_text("box-ci-2-cafe01")
        conf = {**self.conf, "slots": 1}
        self.assertEqual(launcher.retired_slots(conf), [2])
        self.assertEqual(launcher.run(conf, 1), 0)
        self.assertIn(48, FakeGitHub.deleted)
        self.assertEqual(self.records(2), [])

    def test_failed_cycles_leave_no_markers_to_pile_up(self):
        # GitHub refusing the registration (a wrong organization, a 4xx) or no token at all: the cycle asked for
        # nothing GitHub made, so it keeps no marker, and later cycles don't look the name up again and again.
        with contextlib.redirect_stderr(io.StringIO()), mock.patch.object(launcher.time, "sleep"):
            for conf in ({**self.conf, "org": "other"}, {**self.conf, "installation_id": 99}):
                for _ in range(3):
                    self.assertEqual(launcher.run(conf, 1), 1)
                self.assertEqual(list(self.state.glob("slot-1.pending-*")), [])
            self.assertEqual(FakeGitHub.minted, 3)  # one token a cycle, none looked up again for old markers
            self.assertNotIn("/orgs/acme/actions/runners/generate-jitconfig", [p for _, p in self.github()])
            # An answer that doesn't rule a registration out keeps the marker: a 5xx, or a 409 (that name exists).
            for status in (502, 409):
                FakeGitHub.jit_status = status
                self.assertEqual(launcher.run(self.conf, 1), 1)
                self.assertEqual(len(list(self.state.glob("slot-1.pending-*"))), 1)
                for marker in self.state.glob("slot-1.pending-*"):
                    marker.unlink()

    def test_a_lookup_that_fails_ends_the_markers_pass(self):
        # GitHub out of reach: each lookup would wait out a timeout, and a slot's stop has six minutes. The first
        # failure ends the pass, and every marker is kept for a later one.
        for suffix in ("aaaaa1", "aaaaa2", "aaaaa3"):
            (self.state / f"slot-1.pending-{suffix}").write_text(f"box-ci-1-{suffix}")
        with contextlib.redirect_stderr(io.StringIO()):
            launcher.stop({**self.conf, "org": "other"}, 1)
        lookups = [p for m, p in self.github("GET") if p.startswith("/orgs/other/actions/runners?name=")]
        self.assertEqual(len(lookups), 1)
        self.assertEqual(len(list(self.state.glob("slot-1.pending-*"))), 3)

    def test_retire_survives_the_sweep_removing_the_record_it_reads(self):
        # Slot 1's sweep can remove a retired slot's record between a look and a read: the record is then gone, and
        # retire goes on as for no record, never ending in FileNotFoundError.
        with mock.patch.object(launcher.pathlib.Path, "exists", lambda self: True):  # there at the look, gone at the read
            self.assertEqual(launcher.retire(self.conf, 2), (True, ""))

    def test_two_groups_of_the_tiers_name_are_refused(self):
        with mock.patch.object(FakeGitHub, "groups", [FakeGitHub.groups[0], {**FakeGitHub.groups[0], "id": 6}]):
            with self.assertRaisesRegex(launcher.Failed, "2 runner groups are named factory-ci"):
                launcher.resolve(self.conf)

    def test_a_registration_github_wont_remove_doesnt_stop_the_cycle(self):
        (self.state / "slot-1.runner").write_text("77")
        FakeGitHub.delete_status = 422  # a dead runner GitHub still calls busy
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(launcher.run(self.conf, 1), 0)  # the cycle ran its job all the same
        self.assertEqual((self.state / "slot-1.leftover-77").read_text(), "77")
        self.assertEqual(self.fails(), "0")
        FakeGitHub.delete_status = 204
        launcher.stop(self.conf, 1)
        self.assertFalse((self.state / "slot-1.leftover-77").exists())
        self.assertIn(77, FakeGitHub.deleted)

    @unittest.skipUnless(os.environ.get("FACTORY_DOCKER_SMOKE") == "1" and shutil.which("docker"),
                         "FACTORY_DOCKER_SMOKE=1 where a Docker daemon runs (a GitHub-hosted runner)")
    def test_a_real_daemon_takes_the_job_flags(self):
        # The fakes can't refuse a flag the way a daemon does: the log options that stopped every job on the first
        # real run (2026-10-14) passed every test here. The image is made here, from nothing but a program that exits
        # 0, so the test pulls nothing (Docker Hub's rate limit failed it for reasons that weren't the flags).
        arch = subprocess.run(["docker", "info", "--format", "{{.Architecture}}"], capture_output=True, text=True,
                              timeout=60).stdout.strip()
        if arch not in EXIT_ZERO:
            self.skipTest(f"no exit-0 program for the daemon's architecture ({arch!r})")
        program = exit_zero_elf(*EXIT_ZERO[arch])
        archive = io.BytesIO()
        with tarfile.open(fileobj=archive, mode="w") as tar:
            info = tarfile.TarInfo("true")
            info.size, info.mode = len(program), 0o755
            tar.addfile(info, io.BytesIO(program))
        image = f"factory-ci-smoke:{os.getpid()}"
        r = subprocess.run(["docker", "import", "-", image], input=archive.getvalue(), capture_output=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stderr)
        try:
            conf = {**self.conf, "job": {"cpus": 1, "memory": "256m", "pids": 256, "shm": "64m", "hours": 1}}
            r = subprocess.run(["docker", "run", "--rm", *launcher.job_flags(conf), "--entrypoint", "/true", image],
                               capture_output=True, text=True, timeout=300)
            self.assertEqual(r.returncode, 0, r.stderr)
        finally:
            subprocess.run(["docker", "image", "rm", image], capture_output=True, timeout=120)

    UUID = "GPU-00000000-0000-4000-8000-000000000001"
    OTHER = "GPU-00000000-0000-4000-8000-000000000002"

    def gpu_conf(self, gpus, slots=2):
        return {**self.conf, "slots": slots, "job": {**self.conf["job"], "gpus": gpus}}

    def gpu_flags(self, conf, slot):
        """What a slot's flags add to the job flags every container gets."""
        base = launcher.job_flags(conf)
        flags = launcher.job_flags(conf, slot)
        self.assertEqual(flags[:len(base)], base)
        return flags[len(base):]

    def test_with_no_gpus_the_flags_are_what_they_were(self):
        # The default: nothing about a GPU, for a slot's job or a probe, and the settings carry no "gpus" key.
        expected = ["--cpus", "4", "--memory", "8g", "--memory-swap", "8g", "--pids-limit", "8192", "--shm-size", "1g",
                    "--security-opt", "no-new-privileges", "--log-driver", "local", "--log-opt", "max-size=20m",
                    "--log-opt", "max-file=1", "--log-opt", "compress=false", "--cap-drop", "NET_RAW", "--cap-drop", "MKNOD"]
        for slot in (None, 1, 2):
            self.assertEqual(launcher.job_flags(self.conf, slot), expected)
        self.assertEqual(launcher.job_flags(self.conf), expected)
        self.assertEqual(launcher.job_flags({**self.conf, "job": {**self.conf["job"], "gpus": []}}, 1), expected)

    def test_each_slot_gets_its_own_gpu_and_nothing_else_does(self):
        conf = self.gpu_conf(["0", self.UUID])
        self.assertEqual(self.gpu_flags(conf, 1), ["--device", "nvidia.com/gpu=0", "-e", "NVIDIA_VISIBLE_DEVICES=void"])
        self.assertEqual(self.gpu_flags(conf, 2), ["--device", f"nvidia.com/gpu={self.UUID}", "-e",
                                                   "NVIDIA_VISIBLE_DEVICES=void"])
        # Not for a container that isn't a slot's job, and never "all".
        self.assertEqual(launcher.job_flags(conf), launcher.job_flags(self.conf))
        for slot in (1, 2):
            self.assertEqual(len([a for a in launcher.job_flags(conf, slot) if a == "--device"]), 1)
        self.assertEqual(self.gpu_flags(self.gpu_conf(["0:1"]), 1)[1], "nvidia.com/gpu=0:1")
        for name in ("MIG-" + self.UUID[4:], "GPU-" + "a" * 80, "999", "0:0"):
            with self.subTest(name=name):
                self.assertEqual(self.gpu_flags(self.gpu_conf([name]), 1)[1], f"nvidia.com/gpu={name}")

    def test_a_gpu_name_is_one_argument_or_no_job(self):
        too_long = "GPU-" + "a" * 81
        for bad in ("all", "0 --privileged", "0,1", "", " 0", "0\n", "-1", "GPU-a b", "../0", "nvidia.com/gpu=0", 0, None,
                    "1000", "0:1000", too_long, "MIG-" + "a" * 81, self.UUID + "\n", self.UUID + " ", "gpu-abc", "GPU-"):
            with self.subTest(name=bad):
                with self.assertRaises(launcher.Failed):
                    launcher.job_flags(self.gpu_conf([bad]), 1)
        for slot in (0, 3, -1):
            with self.subTest(slot=slot), self.assertRaises(launcher.Failed):
                launcher.job_flags(self.gpu_conf(["0", "1"]), slot)
        with self.assertRaises(launcher.Failed):
            launcher.job_flags({**self.conf, "job": {**self.conf["job"], "gpus": "0"}}, 1)

    def test_a_cycle_starts_its_job_on_its_slots_gpu(self):
        self.conf = self.gpu_conf(["0", self.UUID])
        self.assertEqual(launcher.run(self.conf, 1), 0)
        argv = self.argvs("run")[0]
        self.assertEqual(argv[argv.index("--device") + 1], "nvidia.com/gpu=0")
        self.assertIn("NVIDIA_VISIBLE_DEVICES=void", argv)
        self.assertEqual(argv[-1], self.conf["image"])

    def test_a_slot_with_no_gpu_in_the_settings_registers_nothing(self):
        # Slot 2 beyond the list: the cycle fails before GitHub is asked for a registration, and no container starts.
        self.assertEqual(launcher.run(self.gpu_conf(["0"], slots=2), 2), 1)
        self.assertEqual([c for c in self.github() if "generate-jitconfig" in c[1]], [])
        self.assertEqual(self.argvs("run"), [])

    def test_the_check_runs_each_slots_job_with_its_gpu(self):
        self.assertEqual(launcher.check(self.gpu_conf(["0", self.UUID])), 0)
        runs = self.argvs("run")
        self.assertEqual(len(runs), 5)  # the listener, the reach test, the probe container, then one per slot's GPU
        # The isolation probe is a job's flags with no GPU: a stale CDI spec is the GPU check's to report, once.
        self.assertNotIn("--device", runs[2])
        self.assertEqual(runs[2][runs[2].index("--entrypoint") + 1], "python3")
        for argv, gpu in zip(runs[3:], ("0", self.UUID)):
            self.assertEqual(argv[argv.index("--device") + 1], f"nvidia.com/gpu={gpu}")
            self.assertEqual(argv[argv.index("--network") + 1], "none")
            self.assertEqual(argv[argv.index("--entrypoint") + 1], "sh")
            self.assertEqual(argv[argv.index(launcher.GPU_PROBE) + 1:], ["gpu-probe", gpu])

    def test_the_check_trips_when_a_slot_does_not_see_exactly_its_gpu(self):
        conf = self.gpu_conf(["0", self.UUID])
        # Each slot's own failure is reported (the other slot's passing hides neither one).
        for failing, slot, gpu in ((f"nvidia.com/gpu={self.UUID}", 2, self.UUID), ("nvidia.com/gpu=0", 1, "0")):
            with self.subTest(slot=slot):
                (self.state / "tripped").unlink(missing_ok=True)
                self.control("gpu_fail", failing)
                self.assertEqual(launcher.check(conf), 1)
                tripped = (self.state / "tripped").read_text()
                self.assertIn(f"slot {slot}'s job container doesn't see exactly its GPU {gpu}", tripped)
                self.assertNotIn(f"slot {3 - slot}'s job container doesn't see", tripped)
        (self.state / "tripped").unlink(missing_ok=True)
        # Fewer GPUs than slots is refused, as setup refuses it.
        self.control("gpu_fail", "")
        self.assertEqual(launcher.check(self.gpu_conf(["0"], slots=2)), 1)
        self.assertIn("2 slot(s) but 1 GPU(s)", (self.state / "tripped").read_text())

    def test_two_slots_on_one_card_trip_the_check_whatever_their_names(self):
        for what, names, reports in (
                ("an index and that card's UUID", ["0", self.UUID],
                 {"nvidia.com/gpu=0": self.UUID}),
                ("the same UUID in two cases", [self.UUID, "0"],
                 {"nvidia.com/gpu=0": self.UUID.replace("GPU-0000", "GPU-ABCD").lower().replace("gpu-", "GPU-"),
                  f"nvidia.com/gpu={self.UUID}": self.UUID.replace("GPU-0000", "GPU-ABCD")}),
                ("two names the card answers to", ["0", "0:0"], {"nvidia.com/gpu=0:0": "GPU-0"})):
            with self.subTest(what=what):
                (self.state / "tripped").unlink(missing_ok=True)
                self.control("gpu_reports", json.dumps(reports))
                self.assertEqual(launcher.check(self.gpu_conf(names)), 1)
                self.assertIn("slots 1 and 2 reach the same GPU", (self.state / "tripped").read_text())
        (self.state / "tripped").unlink(missing_ok=True)
        # Different cards pass; so do two MIG devices of one card, which are separate instances.
        self.control("gpu_reports", json.dumps({}))
        self.assertEqual(launcher.check(self.gpu_conf(["0", "1"])), 0)
        self.assertEqual(launcher.check(self.gpu_conf(["MIG-a", "MIG-b"])), 0)

    def test_a_container_that_reports_no_uuid_trips_the_check(self):
        for report in ("", "not a uuid", "GPU-" + "a" * 81, "rm -rf /", "gpu-abc"):
            with self.subTest(report=report):
                (self.state / "tripped").unlink(missing_ok=True)
                self.control("gpu_reports", json.dumps({"nvidia.com/gpu=0": report}))
                self.assertEqual(launcher.check(self.gpu_conf(["0"], slots=1)), 1)
                self.assertIn("slot 1's job container reported no GPU UUID", (self.state / "tripped").read_text())

    def test_the_gpu_probe_reads_only_what_the_container_shows(self):
        # GPU_PROBE with a stand-in nvidia-smi: exactly one GPU (and at most one MIG device), and for a UUID, that one;
        # what it prints last is the UUID of what it sees.
        smi = self.bin / "nvidia-smi"
        mig = "GPU-00000000-0000-4000-8000-0000000000aa"
        listing = {"one": f"GPU 0: Test GPU (UUID: {self.UUID})\n",
                   "two": f"GPU 0: Test GPU (UUID: {self.UUID})\nGPU 1: Test GPU (UUID: {self.OTHER})\n",
                   "none": "", "other": f"GPU 0: Test GPU (UUID: {self.OTHER})\n",
                   "mig": f"GPU 0: Test GPU (UUID: {mig})\n  MIG 1g.5gb Device 0: (UUID: MIG-one)\n",
                   "migs": f"GPU 0: Test GPU (UUID: {mig})\n  MIG 1g.5gb Device 0: (UUID: MIG-one)\n"
                           f"  MIG 1g.5gb Device 1: (UUID: MIG-two)\n"}

        def probe(shows, name, tool=True):
            if tool:
                smi.write_text("#!/bin/sh\nprintf '" + listing[shows].replace("\n", "\\n") + "'\n")
                smi.chmod(0o755)
            else:
                smi.unlink(missing_ok=True)
            r = subprocess.run(["sh", "-c", launcher.GPU_PROBE, "gpu-probe", name], capture_output=True, text=True,
                               env={"PATH": f"{self.bin}:/usr/bin:/bin"})
            return r.returncode, r.stdout
        self.assertEqual(probe("one", self.UUID), (0, self.UUID + "\n"))
        self.assertEqual(probe("one", "0"), (0, self.UUID + "\n"))  # an index: whatever the one GPU is, it reports it
        self.assertEqual(probe("two", self.UUID)[0], 1)
        self.assertEqual(probe("two", "0")[0], 1)
        self.assertEqual(probe("none", "0")[0], 1)
        self.assertEqual(probe("other", self.UUID)[0], 1)
        self.assertEqual(probe("one", "0", tool=False)[0], 1)
        self.assertEqual(probe("mig", "MIG-one"), (0, "MIG-one\n"))
        self.assertEqual(probe("mig", "MIG-two")[0], 1)  # not the device the container shows
        self.assertEqual(probe("migs", "MIG-one")[0], 1)  # several MIG devices visible
        self.assertEqual(launcher.GPU_REPORT.fullmatch(probe("one", "0")[1].strip()) is not None, True)

    def test_the_gpu_layer_changes_the_job_images_inputs_only_when_it_is_staged(self):
        # setup-ci.sh stages the layer's Dockerfile under <build>/gpu only with GPUs; the image's fingerprint covers
        # everything staged, so it is what it was without them and different with them.
        text = (HOST / "setup-ci.sh").read_text()
        layer = re.search(r"<<'GPUEOF'\n(.*?)\nGPUEOF", text, re.S).group(1) + "\n"
        root = pathlib.Path(self.tmp.name)

        def staged(name, gpu):
            build = root / name
            (build / "toolchain").mkdir(parents=True)
            (build / "toolchain" / "a.txt").write_text("a")
            (build / "toolchain.Dockerfile").write_text("FROM x\n")
            (build / "runner").mkdir()
            (build / "runner" / "Dockerfile").write_text("FROM ${BASE}\n")
            if gpu:
                (build / "gpu").mkdir()
                (build / "gpu" / "Dockerfile").write_text(layer)
            return str(build)
        args = ("--build-arg=A=1", "2.338.0", "abc")
        plain, again, with_gpu, with_gpu_again = (staged("p1", False), staged("p2", False), staged("g1", True),
                                                  staged("g2", True))
        self.assertEqual(launcher.build_inputs(plain, *args), launcher.build_inputs(again, *args))
        self.assertEqual(launcher.build_inputs(with_gpu, *args), launcher.build_inputs(with_gpu_again, *args))
        self.assertNotEqual(launcher.build_inputs(plain, *args), launcher.build_inputs(with_gpu, *args))
        (pathlib.Path(with_gpu_again) / "gpu" / "Dockerfile").write_text(layer.replace("libegl1", "libegl2"))
        self.assertNotEqual(launcher.build_inputs(with_gpu, *args), launcher.build_inputs(with_gpu_again, *args))

    def test_the_job_images_inputs_are_fingerprinted(self):
        def tree(root):
            (root / "ctx" / "sub").mkdir(parents=True)
            (root / "ctx" / "sub" / "a.txt").write_text("a")
            (root / "ctx" / "b.sh").write_text("b")
            (root / "ctx" / "b.sh").chmod(0o755)
            (root / "ctx" / "link").symlink_to("b.sh")
            (root / "Dockerfile").write_text("FROM x\n")
            return root
        one = tree(pathlib.Path(self.tmp.name) / "one")
        two = tree(pathlib.Path(self.tmp.name) / "two")  # the same inputs, wherever setup copied them
        fingerprint = launcher.build_inputs(str(one), "--build-arg=A=1", "2.338.0")
        self.assertEqual(launcher.build_inputs(str(two), "--build-arg=A=1", "2.338.0"), fingerprint)
        changes = [
            lambda: (two / "ctx" / "sub" / "a.txt").write_text("A"),
            lambda: (two / "ctx" / "b.sh").chmod(0o644),
            lambda: ((two / "ctx" / "link").unlink(), (two / "ctx" / "link").symlink_to("sub")),
            lambda: (two / "ctx" / "new").write_text(""),
        ]
        for change in changes:
            with self.subTest(change=change):
                two = tree(pathlib.Path(tempfile.mkdtemp(dir=self.tmp.name)))
                change()
                self.assertNotEqual(launcher.build_inputs(str(two), "--build-arg=A=1", "2.338.0"), fingerprint)
        self.assertNotEqual(launcher.build_inputs(str(one), "--build-arg=A=2", "2.338.0"), fingerprint)
        self.assertNotEqual(launcher.build_inputs(str(one), "--build-arg=A=1", "2.339.0"), fingerprint)

    def test_self_hosted_is_registered_once(self):
        self.assertEqual(launcher.jit_labels({**self.conf, "labels": ["factory-ci"]}), ["self-hosted", "factory-ci"])
        self.assertEqual(launcher.jit_labels({**self.conf, "labels": ["factory-ci", "self-hosted"]}),
                         ["self-hosted", "factory-ci"])
        self.assertEqual(launcher.jit_labels({**self.conf, "labels": ["Self-Hosted", "factory-ci"]}),
                         ["self-hosted", "factory-ci"])  # GitHub's labels ignore case
        for labels in (["self-hosted"], ["Linux", "X64"], []):  # no label of the tier's own: any job would do
            with self.subTest(labels=labels), self.assertRaisesRegex(launcher.Failed, "no runner label of its own"):
                launcher.jit_labels({**self.conf, "labels": labels})

    def test_one_wait_per_cycle_and_no_docker_left_behind(self):
        self.control("wait_sleep", 0.6)  # a dozen ticks
        self.assertEqual(launcher.run(self.conf, 1), 0)
        self.assertEqual(len(self.argvs("wait")), 1)
        for call in self.calls():
            with self.assertRaises(ProcessLookupError, msg=call["argv"][:2]):
                os.kill(call["pid"], 0)

    def test_a_runner_that_never_ran_its_job_backs_off(self):
        FakeGitHub.view = [lambda: OFFLINE]  # still registered after its container ended
        self.control("wait_out", 3)
        self.assertEqual(launcher.run(self.conf, 2), 1)
        self.assertIn(("DELETE", "/orgs/acme/actions/runners/42"), self.github())
        self.assertEqual(self.fails(2), "1")
        self.control("wait_out", "0\nrm -rf /")  # anything but an integer
        FakeGitHub.deleted = set()
        with mock.patch.object(launcher.time, "sleep") as sleep:
            self.assertEqual(launcher.run(self.conf, 2), 1)
        # The backoff is the cycle's first sleep. (The patch is the time module's, so subprocess's own wait loop can add
        # short sleeps after it: count only the first.)
        self.assertEqual(sleep.call_args_list[0], mock.call(20))
        self.assertEqual(self.argvs("rm")[-1], ["rm", "-f", "-v", "factory-ci-2"])
        self.assertIn(42, FakeGitHub.deleted)
        self.assertEqual(self.fails(2), "2")

    def test_no_jit_config_no_container(self):
        FakeGitHub.jit_status = 422
        self.assertEqual(launcher.run(self.conf, 1), 1)
        self.assertEqual(self.argvs("run"), [])
        self.assertNotIn("DELETE", [m for m, _ in self.github()])
        self.assertEqual(self.fails(), "1")

    def test_an_idle_runner_waits_as_long_as_it_takes(self):
        self.control("wait_sleep", 1)  # ten polls, all idle
        self.conf["job"]["hours"] = 0.0001  # 0.36 s: idle time isn't job time
        self.assertEqual(launcher.run(self.conf, 1), 0)
        self.assertEqual(self.kills_while_running(), [])
        self.assertGreater(len(self.github("GET")), 3)
        self.assertEqual(self.fails(), "0")

    def test_a_job_that_outruns_its_hours_is_killed(self):
        self.control("wait_sleep", 30)
        answers = [ONLINE, BUSY]
        FakeGitHub.view = [lambda: answers.pop(0) if answers else OFFLINE if (self.bin / "killed").exists() else BUSY]
        self.conf["job"]["hours"] = 0.0001
        self.assertEqual(launcher.run(self.conf, 1), 0)
        self.assertEqual(self.argvs("kill"), [["kill", "factory-ci-1"]])
        self.assertIn(("DELETE", "/orgs/acme/actions/runners/42"), self.github())
        self.assertEqual(self.fails(), "0")  # an overrun is the job's, not a failure of the slot: no backoff

    def test_a_container_that_outlives_its_runner_is_killed(self):
        # The job ended inside one poll (never seen busy), and its container stays up: GitHub's 404 ends it.
        self.control("wait_sleep", 30)
        FakeGitHub.view = [lambda: 404]
        started = time.monotonic()
        self.assertEqual(launcher.run(self.conf, 1), 0)
        self.assertLess(time.monotonic() - started, 10)
        self.assertEqual(self.argvs("kill"), [["kill", "factory-ci-1"]])
        self.assertNotIn("DELETE", [m for m, _ in self.github()])
        self.assertEqual(self.fails(), "0")

    def test_a_runner_offline_twice_after_being_online_is_killed(self):
        self.control("wait_sleep", 30)
        answers = [ONLINE, OFFLINE, ONLINE, OFFLINE]  # one offline poll is an update; two in a row are not
        FakeGitHub.view = [lambda: answers.pop(0) if answers else OFFLINE]
        self.assertEqual(launcher.run(self.conf, 1), 1)
        self.assertEqual(self.argvs("kill"), [["kill", "factory-ci-1"]])
        self.assertGreaterEqual(len(self.github("GET")), 6)
        self.assertIn(("DELETE", "/orgs/acme/actions/runners/42"), self.github())
        self.assertEqual(self.fails(), "1")

    def test_a_runner_that_never_comes_online_is_killed(self):
        self.control("wait_sleep", 30)
        FakeGitHub.view = [lambda: OFFLINE]
        self.conf["start_grace_seconds"] = 0.3
        self.assertEqual(launcher.run(self.conf, 1), 1)
        self.assertEqual(self.argvs("kill"), [["kill", "factory-ci-1"]])
        self.assertEqual(self.fails(), "1")

    def test_an_idle_runner_is_recycled_unless_it_took_a_job(self):
        self.control("wait_sleep", 30)
        self.conf["idle_hours"] = 0.0001
        self.assertEqual(launcher.run(self.conf, 1), 0)
        # Deregistered first, so GitHub assigns it nothing while it's killed.
        self.assertIn(42, FakeGitHub.deleted)
        self.assertEqual(self.argvs("kill"), [["kill", "factory-ci-1"]])
        self.assertEqual(self.fails(), "0")
        # GitHub refuses to remove a busy runner: it took a job, which then runs to its end.
        FakeGitHub.deleted, FakeGitHub.delete_status = set(), 422
        self.control("wait_sleep", 0.6)
        (self.bin / "calls.jsonl").unlink()
        self.assertEqual(launcher.run(self.conf, 1), 0)
        self.assertEqual(self.kills_while_running(), [])

    def test_the_lifetime_cap_holds_when_github_cant_answer(self):
        self.control("wait_sleep", 30)
        FakeGitHub.view = [lambda: 500]
        FakeGitHub.delete_status = 500
        self.conf["idle_hours"] = self.conf["job"]["hours"] = 0.0001  # 0.72 s together
        self.assertEqual(launcher.run(self.conf, 1), 0)
        self.assertEqual(self.argvs("kill"), [["kill", "factory-ci-1"]])
        self.assertEqual(self.fails(), "0")  # a recycle, not a failure
        # The registration GitHub wouldn't remove waits for the next cycle, which removes it first.
        self.assertEqual((self.state / "slot-1.runner").read_text(), "42")
        FakeGitHub.delete_status = 204
        FakeGitHub.view = [self.container_view]
        self.control("wait_sleep", 0)
        FakeGitHub.calls = []
        self.assertEqual(launcher.run(self.conf, 1), 0)
        self.assertEqual(self.github()[:2], [("POST", "/app/installations/9/access_tokens"),
                                             ("DELETE", "/orgs/acme/actions/runners/42")])

    def test_strange_answers_while_polling_are_survived(self):
        self.control("wait_sleep", 0.6)
        answers = ["garbage", "short", 502, "list", ONLINE]
        FakeGitHub.view = [lambda: answers.pop(0) if answers else self.container_view()]
        self.assertEqual(launcher.run(self.conf, 1), 0)
        self.assertEqual(self.kills_while_running(), [])
        self.assertEqual(answers, [])

    def test_low_disk_starts_no_job_and_kills_a_running_one(self):
        self.conf["min_free_gb"] = 10 ** 9
        self.assertEqual(launcher.run(self.conf, 1), 1)
        self.assertEqual(self.argvs("run"), [])
        self.assertNotIn(("POST", "/orgs/acme/actions/runners/generate-jitconfig"), self.github())
        self.conf["min_free_gb"] = 0
        self.control("wait_sleep", 30)
        answers = [False, False, True]
        with mock.patch.object(launcher, "low_disk", side_effect=lambda conf: answers.pop(0) if answers else True):
            with mock.patch.object(launcher.time, "sleep"):
                launcher.run(self.conf, 1)
        self.assertEqual(self.argvs("kill"), [["kill", "factory-ci-1"]])

    def test_sigterm_mid_job_cleans_up(self):
        self.control("wait_sleep", 60)
        conf_file = pathlib.Path(self.tmp.name) / "launcher.json"
        conf_file.write_text(json.dumps(self.conf))
        p = subprocess.Popen([sys.executable, "-I", str(HOST / "ci_launcher.py"), "run", str(conf_file), "1"],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        deadline = time.monotonic() + 20
        while not self.argvs("wait") and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertTrue(self.argvs("wait"), "the cycle never reached its wait")
        p.send_signal(signal.SIGTERM)
        out, err = p.communicate(timeout=30)
        self.assertEqual(p.returncode, 0, err)
        self.assertEqual(self.argvs("rm")[-1], ["rm", "-f", "-v", "factory-ci-1"])
        self.assertIn(42, FakeGitHub.deleted)
        self.assertFalse((self.state / "slot-1.runner").exists())
        self.assertEqual(self.fails(), "0")
        for call in self.calls():
            with self.assertRaises(ProcessLookupError):
                os.kill(call["pid"], 0)

    def test_a_slots_stop_removes_what_its_cycle_left(self):
        (self.state / "slot-3.runner").write_text("77")
        self.assertEqual(launcher.stop(self.conf, 3), 0)
        self.assertEqual(self.argvs("rm"), [["rm", "-f", "-v", "factory-ci-3"]])
        self.assertIn(77, FakeGitHub.deleted)
        self.assertFalse((self.state / "slot-3.runner").exists())

    def test_the_state_directory_is_roots_alone(self):
        self.state.chmod(0o777)
        with self.assertRaisesRegex(launcher.Failed, "only root can write"):
            launcher.run(self.conf, 1)
        self.state.chmod(0o711)
        with self.assertRaisesRegex(launcher.Failed, "only root can write"):
            launcher.run({**self.conf, "state_owner": os.getuid() + 1}, 1)
        self.assertEqual(self.github(), [])

    def test_the_jwt_is_the_apps(self):
        jwt = launcher.app_jwt(self.conf, now=1_700_000_000)
        header, claims, sig = jwt.split(".")
        pad = lambda s: s + "=" * (-len(s) % 4)  # noqa: E731
        self.assertEqual(json.loads(base64.urlsafe_b64decode(pad(header))), {"alg": "RS256", "typ": "JWT"})
        self.assertEqual(json.loads(base64.urlsafe_b64decode(pad(claims))),
                         {"iat": 1_699_999_940, "exp": 1_700_000_540, "iss": "Iv23abc"})
        pub = pathlib.Path(self.tmp.name) / "pub.pem"
        subprocess.run([OPENSSL, "rsa", "-in", str(self.key), "-pubout", "-out", str(pub)], check=True, capture_output=True)
        sigfile = pathlib.Path(self.tmp.name) / "sig"
        sigfile.write_bytes(base64.urlsafe_b64decode(pad(sig)))
        r = subprocess.run([OPENSSL, "dgst", "-sha256", "-verify", str(pub), "-signature", str(sigfile)],
                           input=f"{header}.{claims}".encode(), capture_output=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_resolve(self):
        self.assertEqual(launcher.resolve({**self.conf, "installation_id": None}), {"installation_id": 9, "group_id": 5})
        with mock.patch.object(FakeGitHub, "installation", {"id": 9, "permissions": {"organization_administration": "write"}}):
            with self.assertRaisesRegex(launcher.Failed, "lacks organization_self_hosted_runners"):
                launcher.resolve(self.conf)
        with mock.patch.object(FakeGitHub, "groups", []):
            with self.assertRaisesRegex(launcher.Failed, "no runner group factory-ci"):
                launcher.resolve(self.conf)
        with mock.patch.object(FakeGitHub, "groups", [{**FakeGitHub.groups[0], "allows_public_repositories": True}]):
            with self.assertRaisesRegex(launcher.Failed, "open beyond its selected private repositories"):
                launcher.resolve(self.conf)

    def test_the_check(self):
        self.assertEqual(launcher.check(self.conf), 0)
        self.assertFalse((self.state / "tripped").exists())
        # On the host, as the runner user, no Docker: every target, the LAN gateway and IPv6 among them, no caps.
        host = [json.loads(line) for line in (self.bin / "python.jsonl").read_text().splitlines()]
        self.assertEqual(len(host), 1)
        self.assertEqual(host[0][:3], ["-I", "-c", launcher.PROBE])
        self.assertEqual(host[0][3].split(), ["127.0.0.1", "10.0.2.2", "2606:4700:4700::1111", "192.168.1.1"])
        self.assertEqual(host[0][5], "")
        listener, reach, probe = self.argvs("run")
        self.assertEqual(listener[listener.index("--ip") + 1], launcher.LISTENER_IP)
        self.assertEqual(reach[reach.index("--network") + 1], "factory-ci-check-a")
        # The probe container: the job's own flags and caps, a slot-like network, the other network's listener.
        self.assertEqual(probe[probe.index("--network") + 1], "factory-ci-check")
        self.assertEqual(probe[probe.index("--cpus") + 1], "4")
        self.assertIn("--cap-drop", probe)
        args = probe[probe.index(launcher.PROBE) + 1:]
        self.assertEqual(args[0].split(), ["127.0.0.1", "10.0.2.2", "192.168.1.1", launcher.LISTENER_IP])
        self.assertIn("8080", args[1].split())
        self.assertEqual(args[2], "4 8589934592 8192")
        create = [a for a in self.argvs("network") if a[1] == "create" and "--subnet" in a]
        self.assertEqual(create, [["network", "create", "--label", "factory-ci", "--subnet", launcher.CHECK_SUBNET,
                                   "factory-ci-check-a"]])
        self.assertEqual(self.argvs("rm")[-1], ["rm", "-f", "-v", "factory-ci-check-listen"])

    def test_the_check_trips_on_any_failure(self):
        controllers = self.cgroup / f"user@{os.getuid()}.service" / "cgroup.controllers"
        cases = [
            ("nft.rc", "1", "firewall table factory_ci isn't loaded"),
            ("probe_rc", "1", "the probe container"),
            ("host_rc", "1", "the host-side probe"),
            ("reach_rc", "1", "can't be reached on its own network"),
            ("info_rc", "1", "Docker daemon doesn't answer"),
            ("netcreate_rc", "1", "couldn't create the check's network"),
            (controllers, "pids\n", "the cpu controller isn't delegated"),
            (self.cgroup / "memory.max", None, "the check couldn't finish: FileNotFoundError"),
            ("groups", [{**FakeGitHub.groups[0], "visibility": "all"}], "open beyond its selected"),
            ("groups", [], "runner group factory-ci is gone"),
            ("docker", subprocess.TimeoutExpired("docker", 120), "the check couldn't finish: TimeoutExpired"),
        ]
        for what, value, message in cases:
            with self.subTest(message=message):
                for name in ("nft.rc", "probe_rc", "host_rc", "reach_rc", "info_rc", "netcreate_rc", "systemctl.log",
                             "loginctl.log"):
                    (self.bin / name).unlink(missing_ok=True)
                (self.state / "tripped").unlink(missing_ok=True)
                controllers.write_text("cpuset cpu io memory pids\n")
                (self.cgroup / "memory.max").write_text("17179869184\n")
                patches = []
                if what == "groups":
                    patches.append(mock.patch.object(FakeGitHub, "groups", value))
                elif what == "docker":
                    patches.append(mock.patch.object(launcher, "docker", side_effect=value))
                elif value is None:
                    what.unlink()
                elif isinstance(what, pathlib.Path):
                    what.write_text(value)
                else:
                    self.control(what, value)
                for p in patches:
                    p.start()
                try:
                    self.assertEqual(launcher.check(self.conf), 1)
                finally:
                    for p in patches:
                        p.stop()
                self.assertIn(message, (self.state / "tripped").read_text())
                self.assertEqual((self.bin / "systemctl.log").read_text().splitlines(), self.trip_steps())
                self.assertEqual((self.bin / "loginctl.log").read_text().splitlines(), ["disable-linger factory-ci"])

    def test_liveness_isnt_isolation(self):
        # No internet from either probe, and GitHub out of reach: noted, not tripped.
        self.control("probe_rc", 2)
        self.control("host_rc", 2)
        with mock.patch.object(launcher, "Tokens") as tokens:
            tokens.return_value.get.side_effect = launcher.Failed("GitHub out of reach")
            self.assertEqual(launcher.check(self.conf), 0)
        self.assertFalse((self.state / "tripped").exists())

    def test_the_trip_unit_keeps_what_a_check_found(self):
        conf_file = pathlib.Path(self.tmp.name) / "launcher.json"
        conf_file.write_text(json.dumps(self.conf))
        self.assertEqual(launcher.main(["ci_launcher.py", "trip", str(conf_file)]), 0)
        self.assertIn("didn't finish: journalctl -u factory-ci-gate", (self.state / "tripped").read_text())
        (self.state / "tripped").write_text("the probe container: REACHABLE 10.0.0.1:22\n")
        self.assertEqual(launcher.main(["ci_launcher.py", "trip", str(conf_file)]), 0)
        self.assertEqual((self.state / "tripped").read_text(), "the probe container: REACHABLE 10.0.0.1:22\n")
        self.assertEqual((self.bin / "systemctl.log").read_text().count("stop factory-ci-slot@*.service"), 2)

    def test_the_firewall_check(self):
        self.assertEqual(launcher.fwcheck(self.conf), 0)
        self.assertFalse((self.bin / "systemctl.log").exists())
        self.assertEqual((self.bin / "nft.log").read_text().splitlines(), ["-j list table inet factory_ci"])
        self.control("nft.rc", 1)
        self.assertEqual(launcher.fwcheck(self.conf), 1)
        self.assertIn("firewall table factory_ci isn't loaded", (self.state / "tripped").read_text())
        self.assertEqual((self.bin / "systemctl.log").read_text().splitlines(), self.trip_steps())
        self.assertEqual(len((self.bin / "nft.log").read_text().splitlines()), 1 + 4)  # looked at again 3 times

    def test_the_firewall_check_rides_out_nftables_restarting(self):
        # nftables.service's restart flushes the ruleset until the reapply unit loads the table again.
        answers = ["firewall table factory_ci isn't loaded", None]
        with mock.patch.object(launcher, "firewall_problem", side_effect=lambda conf: answers.pop(0)):
            self.assertEqual(launcher.fwcheck(self.conf), 0)
        self.assertFalse((self.state / "tripped").exists())

    def listing(self, elements=("10.0.0.0/8",), rules=2, packets=0, handle=1):
        """A table as `nft -j` lists it: a set of blocked addresses and a chain whose rules reject them."""
        rule = {"family": "inet", "table": "factory_ci", "chain": "output", "handle": handle,
                "expr": [{"match": {"op": "==", "left": {"meta": {"key": "skuid"}}, "right": 1001}},
                         {"counter": {"packets": packets, "bytes": packets * 60}}, {"reject": None}]}
        return json.dumps({"nftables": [
            {"metainfo": {"version": "1.0.9", "release_name": "Old Doc Yak #3", "json_schema_version": 1}},
            {"table": {"family": "inet", "name": "factory_ci", "handle": handle}},
            {"set": {"family": "inet", "name": "blocked4", "table": "factory_ci", "type": "ipv4_addr",
                     "handle": handle, "flags": ["interval"], "elem": [{"prefix": {"addr": e.split("/")[0], "len": 8}}
                                                                       for e in elements]}},
            {"chain": {"family": "inet", "table": "factory_ci", "name": "output", "handle": handle}},
        ] + [{"rule": rule}] * rules})

    def test_a_flushed_chain_or_set_is_a_lost_firewall(self):
        self.control("nft.out", self.listing())
        self.conf["firewall_fingerprint"] = launcher.fingerprint(self.listing())
        self.assertEqual(launcher.fwcheck(self.conf), 0)
        self.assertEqual(launcher.check(self.conf), 0)
        # Counters, handles and nft's own version change on their own: the same table.
        self.control("nft.out", self.listing(packets=99, handle=7).replace("1.0.9", "1.1.1"))
        self.assertEqual(launcher.fwcheck(self.conf), 0)
        for changed in (self.listing(rules=0), self.listing(elements=())):  # nft flush chain; nft flush set
            with self.subTest(changed=changed[-80:]):
                (self.state / "tripped").unlink(missing_ok=True)
                self.control("nft.out", changed)
                self.assertEqual(launcher.fwcheck(self.conf), 1)
                self.assertIn("isn't what setup loaded", (self.state / "tripped").read_text())
        (self.state / "tripped").unlink()
        self.control("nft.out", "not json")
        self.assertEqual(launcher.fwcheck(self.conf), 1)
        self.assertIn("listing isn't readable", (self.state / "tripped").read_text())

    def test_setup_fingerprints_the_table_it_loaded(self):
        self.control("nft.out", self.listing())
        out = io.StringIO()
        with mock.patch.dict(os.environ, {"PATH": f"{self.bin}:{os.environ['PATH']}"}), \
                contextlib.redirect_stdout(out):
            self.assertEqual(launcher.main(["ci_launcher.py", "fingerprint", "factory_ci"]), 0)
        self.assertEqual(out.getvalue().strip(), launcher.fingerprint(self.listing()))
        self.assertIn("-j list table inet factory_ci", (self.bin / "nft.log").read_text())

    def test_a_refused_token_is_minted_again(self):
        # Revoked, or expired early: a 401 drops the cached token, and the call is made again with a new one.
        FakeGitHub.revoked = {"inst-token"}
        self.assertEqual(launcher.run(self.conf, 1), 0)
        self.assertEqual(self.github()[:4], [("POST", "/app/installations/9/access_tokens"),
                                             ("POST", "/orgs/acme/actions/runners/generate-jitconfig"),
                                             ("POST", "/app/installations/9/access_tokens"),
                                             ("POST", "/orgs/acme/actions/runners/generate-jitconfig")])
        self.assertEqual(FakeGitHub.calls[3][2], "Bearer inst-token-2")
        self.assertEqual(self.fails(), "0")

    def test_a_rate_limit_mints_no_token(self):
        # GitHub answers 403 to a rate limit too: no new token for it, and the cycle backs off as for any refusal.
        FakeGitHub.jit_status = 403
        self.assertEqual(launcher.run(self.conf, 1), 1)
        self.assertEqual(FakeGitHub.minted, 1)
        self.assertEqual(self.fails(), "1")

    def test_a_token_refused_twice_fails_the_call(self):
        FakeGitHub.revoked = {"inst-token", "inst-token-2"}
        self.assertEqual(launcher.run(self.conf, 1), 1)
        self.assertEqual(FakeGitHub.minted, 2)  # once again, not without end
        self.assertEqual(self.argvs("run"), [])

    def test_a_trip_runs_its_steps_in_order(self):
        launcher.trip(self.conf, ["a check failed"])
        self.assertEqual((self.bin / "all.log").read_text().splitlines(),
                         [f"systemctl {step}" for step in self.trip_steps()[:-1]]
                         + ["loginctl disable-linger factory-ci", f"systemctl {self.trip_steps()[-1]}"])

    def test_the_token_lasts_by_the_monotonic_clock(self):
        tokens = launcher.Tokens(self.conf)
        tokens.get()
        with mock.patch.object(launcher.time, "time", return_value=4102444800 + 10 ** 6):  # the wall clock jumps
            tokens.get()
        self.assertEqual(FakeGitHub.minted, 1)

    def test_answers_that_arent_objects_end_no_cycle_badly(self):
        # A runner that isn't an object: no container, a failure counted.
        FakeGitHub.jit_answer = {"runner": "42", "encoded_jit_config": "SklUQ09ORklH"}
        self.assertEqual(launcher.run(self.conf, 1), 1)
        self.assertEqual(self.argvs("run"), [])
        self.assertEqual(self.fails(), "1")
        # A refusal whose body is a list: the cleanup still reports, and the failure is still counted.
        FakeGitHub.jit_answer = None
        FakeGitHub.view = [lambda: OFFLINE]
        FakeGitHub.delete_status, FakeGitHub.delete_body = 500, [1, 2]
        self.control("wait_out", 3)
        with mock.patch.object(launcher.time, "sleep"):
            self.assertEqual(launcher.run(self.conf, 1), 1)
        self.assertEqual(self.fails(), "2")
        self.assertEqual((self.state / "slot-1.runner").read_text(), "42")

    def test_github_out_of_reach_doesnt_make_an_idle_runner_busy(self):
        self.control("wait_sleep", 30)
        self.conf["idle_hours"] = 0.0001
        real = launcher.deregister
        failures = [launcher.Failed("DELETE /orgs/acme/actions/runners/42: URLError: timed out")]

        def deregister(conf, runner_id, tokens):
            if failures:
                raise failures.pop()
            return real(conf, runner_id, tokens)

        started = time.monotonic()
        with mock.patch.object(launcher, "deregister", side_effect=deregister):
            self.assertEqual(launcher.run(self.conf, 1), 0)
        self.assertLess(time.monotonic() - started, 10)  # recycled at the next poll, not left to CI_JOB_HOURS
        self.assertEqual(self.argvs("kill"), [["kill", "factory-ci-1"]])
        self.assertIn(42, FakeGitHub.deleted)
        self.assertEqual(self.fails(), "0")

    def test_polls_that_fail_through_the_grace_window_kill_nothing(self):
        # never-online needs GitHub's word: with every poll failing, only the lifetime cap holds.
        self.control("wait_sleep", 1)
        FakeGitHub.view = [lambda: 500]
        self.conf["start_grace_seconds"] = 0.2
        self.assertEqual(launcher.run(self.conf, 1), 1)  # its end unconfirmed, the cycle counts as failed
        self.assertEqual(self.kills_while_running(), [])

    def test_low_disk_is_noted_by_the_check_not_tripped(self):
        with mock.patch.object(launcher, "low_disk", return_value=True):
            self.assertEqual(launcher.check(self.conf), 0)
        self.assertFalse((self.state / "tripped").exists())

    def test_a_memory_cap_is_whole_pages(self):
        page = os.sysconf("SC_PAGE_SIZE")
        self.assertEqual(launcher.memory_bytes("8g"), 8 * 1024 ** 3)
        odd = launcher.memory_bytes("6001k")
        self.assertEqual(odd % page, 0)
        self.assertTrue(6001 * 1024 - page < odd <= 6001 * 1024)

    def test_a_leftover_jit_config_is_removed(self):
        (self.state / "slot-1.env").write_text("ACTIONS_RUNNER_INPUT_JITCONFIG=old\n")
        FakeGitHub.jit_status = 422
        launcher.run(self.conf, 1)
        self.assertFalse((self.state / "slot-1.env").exists())
        (self.state / "slot-2.env").write_text("ACTIONS_RUNNER_INPUT_JITCONFIG=old\n")
        launcher.stop(self.conf, 2)
        self.assertFalse((self.state / "slot-2.env").exists())

    def sigterm_during(self, ready):
        """Runs a cycle in its own process, sends it SIGTERM once ready() holds, and checks it cleaned up."""
        conf_file = pathlib.Path(self.tmp.name) / "launcher.json"
        conf_file.write_text(json.dumps(self.conf))
        p = subprocess.Popen([sys.executable, "-I", str(HOST / "ci_launcher.py"), "run", str(conf_file), "1"],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        deadline = time.monotonic() + 20
        while not ready() and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertTrue(ready(), "the cycle never got there")
        p.send_signal(signal.SIGTERM)
        out, err = p.communicate(timeout=30)
        self.assertEqual(p.returncode, 0, err)
        self.assertEqual(self.argvs("rm")[-1], ["rm", "-f", "-v", "factory-ci-1"])
        self.assertEqual(self.fails(), "0")
        self.assertEqual(list(self.state.glob("*.env")), [])
        for call in self.calls():
            with self.assertRaises(ProcessLookupError):
                os.kill(call["pid"], 0)

    def test_sigterm_during_docker_run_cleans_up(self):
        self.control("run_sleep", 30)
        self.sigterm_during(lambda: bool(self.argvs("run")))
        self.assertIn(42, FakeGitHub.deleted)  # registered before its container started
        self.assertFalse((self.state / "slot-1.runner").exists())

    def test_sigterm_during_an_api_call_cleans_up(self):
        # GitHub's answer, and the registration with it, waits for the gate: the cycle is stopped while it waits.
        FakeGitHub.jit_gate = gate = threading.Event()
        self.addCleanup(gate.set)
        self.sigterm_during(lambda: ("POST", "/orgs/acme/actions/runners/generate-jitconfig") in self.github())
        self.assertEqual(self.argvs("run"), [])
        self.assertNotIn("DELETE", [m for m, _ in self.github()])
        # GitHub registers the runner after the cycle stopped listening: its ID never reached the cycle, but its name
        # was marked pending before the call.
        markers = list(self.state.glob("slot-1.pending-*"))
        self.assertEqual(len(markers), 1)
        name = markers[0].read_text()
        self.assertRegex(name, r"^box-ci-1-[0-9a-f]{6}$")
        # The slot's stop, before GitHub has it: the marker is kept, since the request may still be in flight.
        launcher.stop(self.conf, 1)
        self.assertTrue(markers[0].exists())
        gate.set()
        deadline = time.monotonic() + 20
        while 42 not in FakeGitHub.registered and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertEqual(FakeGitHub.registered.get(42), name)
        # Once it has, the next look finds it by its name and removes it.
        launcher.stop(self.conf, 1)
        self.assertIn(42, FakeGitHub.deleted)
        self.assertEqual([p for p in self.records(1) if p != "slot-1.fails"], [])


if __name__ == "__main__":
    unittest.main()
