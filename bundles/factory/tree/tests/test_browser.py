"""The browser route (process/factory.md, D6): browser.py, which adds it to a stage's sandbox settings;
with-browser, the wrapper sandboxed Bash runs a browser command through; and browser_check.py, which judges
factory-smoke's browser-host probe. The route itself is proven only by that smoke job, against the real browser
host and sandbox; these pin what the scripts decide."""

import base64
import io
import json
import os
import struct
import zipfile
import zlib
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

FACTORY = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FACTORY))
import browser  # noqa: E402
import browser_check  # noqa: E402
import evidence  # noqa: E402
import implement_guard as guard  # noqa: E402
import render  # noqa: E402

try:
    import yaml  # noqa: F401
    import workflow_policy as policy  # noqa: E402
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

HOST = "10.20.30.40"
BASE = {"sandbox": {"network": {"strictAllowlist": True, "allowedDomains": ["localhost"]}}}


class Route(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = pathlib.Path(self.tmp.name) / "ws"
        self.client("web", "@playwright/test", "1.61.1")

    def tearDown(self):
        self.tmp.cleanup()

    def client(self, directory, name, version):
        d = self.ws / directory / "node_modules" / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "package.json").write_text(json.dumps({"name": name, "version": version}))

    def factory(self, **block):
        return {"stack": {"node": "web"}, "browser": {"host": HOST, **block}}

    def test_off_without_a_host(self):
        for factory in ({}, {"browser": {"host": ""}}, {"browser": {"_doc": "x", "host": "", "stages": []}}):
            with self.subTest(factory=factory):
                found, why = browser.route(factory, "implement", self.ws)
                self.assertIsNone(found)
                self.assertIn("no browser host", why)

    def test_a_stage_gets_it_only_once_listed_and_smoke_always(self):
        found, why = browser.route(self.factory(stages=[]), "implement", self.ws)
        self.assertIsNone(found)
        self.assertIn("doesn't list implement", why)
        found, _ = browser.route(self.factory(stages=[]), "smoke", self.ws)
        self.assertEqual(found[:3], (HOST, 3161, "1.61.1"))
        found, _ = browser.route(self.factory(stages=["implement", "revise"]), "revise", self.ws)
        self.assertEqual(found[1], 3161)

    def test_the_port_is_the_clients_minor_on_the_base(self):
        self.client("web", "@playwright/test", "1.64.0")
        self.assertEqual(browser.route(self.factory(), "smoke", self.ws)[0][1], 3164)
        self.assertEqual(browser.route(self.factory(port_base=4000), "smoke", self.ws)[0][1], 4064)
        # The client found first wins: @playwright/test, then playwright, then playwright-core.
        shutil.rmtree(self.ws / "web" / "node_modules" / "@playwright")
        self.client("web", "playwright-core", "1.56.2")
        self.assertEqual(browser.route(self.factory(), "smoke", self.ws)[0][1:3], (3156, "1.56.2"))

    def test_the_client_directory(self):
        self.client("e2e", "playwright", "1.60.0")
        found, _ = browser.route(self.factory(client="e2e"), "smoke", self.ws)
        self.assertEqual(found[1:], (3160, "1.60.0", str((self.ws / "e2e").resolve()), []))
        found, why = browser.route(self.factory(client="missing"), "smoke", self.ws)
        self.assertIsNone(found)
        self.assertIn("no Playwright client installed in missing", why)
        for bad in ("/etc", "../outside", "a/../../b", ""):
            with self.subTest(client=bad), self.assertRaises(browser.Invalid):
                browser.route(self.factory(client=bad), "smoke", self.ws)

    def test_a_bad_block_is_refused(self):
        for block, words in (({"host": "browser-host"}, "one IPv4 address"),
                             ({"host": "203.0.113.300"}, "one IPv4 address"),
                             ({"host": "203.0.113.9,203.0.113.10"}, "one IPv4 address"),
                             ({"host": "203.0.113.09"}, "one IPv4 address"),
                             ({"host": HOST, "port_base": "3100"}, "port_base"),
                             ({"host": HOST, "port_base": 80}, "port_base"),
                             ({"host": HOST, "stages": ["plan"]}, "browser.stages"),
                             ({"host": HOST, "stages": "implement"}, "browser.stages"),
                             ({"host": HOST, "gpu": "yes"}, "browser.gpu"),
                             ({"host": HOST, "proxy": "x"}, "takes only")):
            with self.subTest(block=block), self.assertRaises(browser.Invalid) as e:
                browser.route({"stack": {"node": "web"}, "browser": block}, "smoke", self.ws)
            self.assertIn(words, str(e.exception))

    def test_the_outside_hosts_cd_allowed(self):
        allow = [{"host": "cdn.example.org", "why": "read-only public images", "decided": "CD, 2026-11-20"}]
        found, _ = browser.route(self.factory(allow=allow), "smoke", self.ws)
        self.assertEqual(found[4], ["cdn.example.org"])
        out = browser.add_route(BASE, HOST, 3161, found[4])
        self.assertEqual(out["sandbox"]["network"]["allowedDomains"], ["localhost", f"{HOST}:3161", "cdn.example.org:443"])
        r, settings, conf = self.run_main(self.factory(stages=["implement"], allow=allow), "implement")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("cdn.example.org:443", settings["sandbox"]["network"]["allowedDomains"])
        self.assertIn("allow=cdn.example.org\nprobe=\n", conf.read_text())
        # The first entry's probe path, for factory-smoke's GET (D6 rule 4); a later entry's isn't fetched.
        probed = [dict(allow[0], probe="/cards/a1/front.webp?v=2"),
                  {"host": "fonts.example.org", "why": "x", "decided": "CD", "probe": "/other.css"}]
        r, _, conf = self.run_main(self.factory(stages=["implement"], allow=probed), "implement")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("allow=cdn.example.org fonts.example.org\nprobe=/cards/a1/front.webp?v=2\n", conf.read_text())
        for bad in ("cards/front.webp", "/a b", "/x\nvideo=1", "https://cdn.example.org/x", "/x#top", "/x;y", 5, ""):
            with self.subTest(probe=bad), self.assertRaises(browser.Invalid):
                browser.route(self.factory(allow=[dict(allow[0], probe=bad)]), "smoke", self.ws)
        # Each entry is one plain hostname, with why and who decided it, written out.
        for bad in ([{"host": "*.example.org", "why": "x", "decided": "CD"}],
                    [{"host": "cdn.example.org:8443", "why": "x", "decided": "CD"}],
                    [{"host": "203.0.113.5", "why": "x", "decided": "CD"}],
                    [{"host": "localhost.localdomain", "why": "x", "decided": "CD"}],
                    [{"host": "printer.local", "why": "x", "decided": "CD"}],
                    [{"host": "127.0.0.1.nip.io", "why": "x", "decided": "CD"}],
                    [{"host": "cdn.example.org\n", "why": "x", "decided": "CD"}],
                    [{"host": "https://cdn.example.org", "why": "x", "decided": "CD"}],
                    [{"host": "cdn.example.org", "why": "", "decided": "CD"}],
                    [{"host": "cdn.example.org", "why": "x"}],
                    allow * 2, "cdn.example.org"):
            with self.subTest(allow=bad), self.assertRaises(browser.Invalid):
                browser.route(self.factory(allow=bad), "smoke", self.ws)

    def test_only_a_1x_release(self):
        self.client("web", "@playwright/test", "2.0.0")
        with self.assertRaises(browser.Invalid):
            browser.route(self.factory(), "smoke", self.ws)

    def test_the_settings_gain_one_address_and_port(self):
        out = browser.add_route(BASE, HOST, 3161)
        self.assertEqual(out["sandbox"]["network"]["allowedDomains"], ["localhost", f"{HOST}:3161"])
        self.assertTrue(out["sandbox"]["network"]["strictAllowlist"])
        self.assertEqual(browser.add_route(out, HOST, 3161), out)
        self.assertEqual(BASE["sandbox"]["network"]["allowedDomains"], ["localhost"])

    def run_main(self, factory, stage):
        root = pathlib.Path(self.tmp.name)
        (root / "factory.json").write_text(json.dumps(factory))
        (root / "settings.json").write_text(json.dumps(BASE))
        conf = root / "opt" / "browser.conf"
        r = subprocess.run([sys.executable, "-I", str(FACTORY / "browser.py"), str(root / "factory.json"), stage,
                            str(self.ws), str(root / "settings.json"), str(conf)], capture_output=True, text=True)
        return r, json.loads((root / "settings.json").read_text()), conf

    def test_main_writes_the_settings_and_the_conf(self):
        r, settings, conf = self.run_main(self.factory(stages=["implement"]), "implement")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn(f"{HOST}:3161", settings["sandbox"]["network"]["allowedDomains"])
        self.assertEqual(conf.read_text(),
                         f"host={HOST}\nport=3161\nport_base=3100\nversion=1.61.1\nclient={(self.ws / 'web').resolve()}\nallow=\n"
                         "probe=\nvideo=1\n")

    def test_main_changes_nothing_when_off(self):
        r, settings, conf = self.run_main(self.factory(stages=[]), "revise")
        self.assertEqual(r.returncode, 0)
        self.assertIn("browser route for revise: off", r.stdout)
        self.assertEqual(settings, BASE)
        self.assertFalse(conf.exists())

    def test_smoke_fails_when_it_cant_build_the_route_and_skips_without_a_host(self):
        shutil.rmtree(self.ws / "web" / "node_modules")
        r, _, conf = self.run_main(self.factory(), "smoke")
        self.assertEqual(r.returncode, 1)
        self.assertFalse(conf.exists())
        r, _, _ = self.run_main({"stack": {"node": "web"}}, "smoke")
        self.assertEqual(r.returncode, 0)

    def test_smoke_records_no_video_and_the_stages_do(self):
        r, _, conf = self.run_main(self.factory(), "smoke")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertTrue(conf.read_text().endswith("video=0\n"))
        r, _, conf = self.run_main(self.factory(stages=["reproduce"]), "reproduce")
        self.assertTrue(conf.read_text().endswith("video=1\n"))

    def test_main_refuses_an_unknown_stage(self):
        r, _, _ = self.run_main(self.factory(stages=["implement"]), "plan")
        self.assertEqual(r.returncode, 2)


@unittest.skipUnless(shutil.which("curl"), "needs curl")
class Wrapper(unittest.TestCase):
    """with-browser's refusals, which need no browser host: each says UNAVAILABLE and exits 75."""

    def run_wrapper(self, conf_text, *command, proxy=""):
        with tempfile.TemporaryDirectory() as tmp:
            conf = pathlib.Path(tmp) / "browser.conf"
            if conf_text is not None:
                conf.write_text(conf_text)
            env = {k: v for k, v in os.environ.items() if k.lower() not in ("http_proxy", "https_proxy", "all_proxy")}
            env["FACTORY_BROWSER_CONF"] = str(conf)
            if proxy:
                env["HTTP_PROXY"] = proxy
            return subprocess.run(["bash", str(FACTORY / "with-browser"), *(command or ("true",))],
                                  capture_output=True, text=True, env=env, timeout=60)

    def test_no_route(self):
        r = self.run_wrapper(None)
        self.assertEqual(r.returncode, 75)
        self.assertIn("UNAVAILABLE: browser host (this stage has no browser route", r.stderr)

    def test_a_malformed_conf(self):
        for text in ("host=browser-host\nport=3161\n", "host=203.0.113.9\nport=x\n", ""):
            with self.subTest(text=text):
                r = self.run_wrapper(text)
                self.assertEqual(r.returncode, 75)
                self.assertIn("is malformed", r.stderr)

    def test_a_front_end_that_doesnt_answer(self):
        # A port on loopback nothing listens on: the wrapper gives up without running the command.
        r = self.run_wrapper("host=127.0.0.1\nport=47\nversion=1.61.1\n", "sh", "-c", "echo ran")
        self.assertEqual(r.returncode, 75)
        self.assertIn("no answer from the front end for Playwright 1.61.1 at 127.0.0.1:47", r.stderr)
        self.assertNotIn("ran", r.stdout)

    def test_no_command(self):
        r = subprocess.run(["bash", str(FACTORY / "with-browser")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)


def free_port():
    import socket
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class FakeFrontEnd:
    """A stand-in front end (404 to a plain request, as the real one answers) and, optionally, a stand-in sandbox proxy
    that tunnels CONNECT to it, or refuses with 403, recording what it was asked."""

    def __init__(self, refuse=False):
        import socketserver
        import threading
        self.front_port, self.asked = free_port(), []
        front_port, asked = self.front_port, self.asked

        class Front(socketserver.BaseRequestHandler):
            def handle(self):
                self.request.recv(65536)
                self.request.sendall(b"HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")

        class Proxy(socketserver.BaseRequestHandler):
            def handle(self):
                import socket
                head = b""
                while b"\r\n\r\n" not in head:
                    chunk = self.request.recv(4096)
                    if not chunk:
                        return
                    head += chunk
                asked.append(head.decode(errors="replace"))
                if refuse or not head.startswith(b"CONNECT "):
                    self.request.sendall(b"HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\n\r\n")
                    return
                up = socket.create_connection(("127.0.0.1", front_port))
                self.request.sendall(b"HTTP/1.1 200 Connection established\r\n\r\n")
                up.sendall(head.split(b"\r\n\r\n", 1)[1])
                for a, b in ((self.request, up), (up, self.request)):
                    threading.Thread(target=self.pipe, args=(a, b), daemon=True).start()
                threading.Event().wait(3)

            @staticmethod
            def pipe(a, b):
                try:
                    while (data := a.recv(65536)):
                        b.sendall(data)
                except OSError:
                    pass

        socketserver.ThreadingTCPServer.allow_reuse_address = True
        self.servers = [socketserver.ThreadingTCPServer(("127.0.0.1", self.front_port), Front),
                        socketserver.ThreadingTCPServer(("127.0.0.1", 0), Proxy)]
        self.proxy_port = self.servers[1].server_address[1]
        for srv in self.servers:
            srv.daemon_threads = True
            threading.Thread(target=srv.serve_forever, daemon=True).start()

    def close(self):
        for srv in self.servers:
            srv.shutdown()
            srv.server_close()


@unittest.skipUnless(shutil.which("curl"), "needs curl")
class WrapperRoute(unittest.TestCase):
    """with-browser's own path, against a stand-in front end and a stand-in sandbox proxy."""

    def setUp(self):
        self.fake = None
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        if self.fake:
            self.fake.close()
        self.tmp.cleanup()

    def run_wrapper(self, conf_text, proxy="", show=None, flags=()):
        conf = pathlib.Path(self.tmp.name) / "browser.conf"
        conf.write_text(conf_text)
        env = {k: v for k, v in os.environ.items() if k.lower() not in ("http_proxy", "https_proxy", "all_proxy", "no_proxy")}
        env["FACTORY_BROWSER_CONF"] = str(conf)
        if proxy:
            env["HTTP_PROXY"] = proxy
        show = show or 'echo "$FACTORY_BROWSER_WS_ENDPOINT|$PW_TEST_CONNECT_WS_ENDPOINT|$FACTORY_BROWSER_CLIENT|$FACTORY_BROWSER_ALLOW|${NODE_USE_ENV_PROXY:-}"'
        return subprocess.run(["bash", str(FACTORY / "with-browser"), *flags, "sh", "-c", show], capture_output=True, text=True,
                              env=env, timeout=60)

    def test_outside_the_sandbox_it_reaches_the_front_end_directly(self):
        self.fake = FakeFrontEnd()
        r = self.run_wrapper(f"host=127.0.0.1\nport={self.fake.front_port}\nversion=1.61.1\nclient=/w/web\nallow=\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        ws = f"ws://127.0.0.1:{self.fake.front_port}/"
        self.assertEqual(r.stdout.strip(), f"{ws}|{ws}|/w/web||")

    @unittest.skipUnless(shutil.which("socat"), "needs socat")
    def test_inside_it_forwards_through_the_proxy_with_its_credential(self):
        self.fake = FakeFrontEnd()
        port = free_port()
        r = self.run_wrapper(f"host=10.20.30.40\nport={port}\nversion=1.61.1\nclient=/w\nallow=cdn.example.org\n",
                             proxy=f"http://srt.abc%3D%3D:secret@127.0.0.1:{self.fake.proxy_port}")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), f"ws://127.0.0.1:{port}/|ws://127.0.0.1:{port}/|/w|cdn.example.org|1")
        connect = next(a for a in self.fake.asked if a.startswith("CONNECT "))
        self.assertTrue(connect.startswith(f"CONNECT 10.20.30.40:{port} "), connect)
        self.assertIn("proxy-authorization: basic " + base64.b64encode(b"srt.abc%3D%3D:secret").decode().lower(), connect.lower())

    def test_the_probe_path_for_smoke(self):
        self.fake = FakeFrontEnd()
        base = f"host=127.0.0.1\nport={self.fake.front_port}\nversion=1.61.1\nclient=/w\nallow=cdn.example.org\n"
        for conf, want in ((base + "probe=/cards/front.webp\n", "/cards/front.webp"), (base, "")):
            with self.subTest(conf=conf.splitlines()[-1]):
                r = self.run_wrapper(conf, show='echo "[$FACTORY_BROWSER_PROBE]"')
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertEqual(r.stdout.strip(), f"[{want}]")

    def test_the_stage_says_whether_to_record_video(self):
        self.fake = FakeFrontEnd()
        base = f"host=127.0.0.1\nport={self.fake.front_port}\nversion=1.61.1\nclient=/w\nallow=\n"
        for conf, want in ((base + "video=1\n", "1"), (base + "video=0\n", "0"), (base, "0")):
            with self.subTest(conf=conf.splitlines()[-1]):
                r = self.run_wrapper(conf, show='echo "$FACTORY_EVIDENCE_VIDEO"')
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertEqual(r.stdout.strip(), want)

    def test_film_paces_only_a_stage_that_records_video(self):
        # The filmed pass (D6 rule 7): --film sets FACTORY_EVIDENCE_PACE where the stage records video, never in smoke,
        # and never without the flag; the module the helper loads is the one beside the wrapper.
        self.fake = FakeFrontEnd()
        base = f"host=127.0.0.1\nport={self.fake.front_port}\nversion=1.61.1\nclient=/w\nallow=\n"
        for conf, flags, want in ((base + "video=1\n", ["--film"], "1"), (base + "video=1\n", [], "0"),
                                  (base + "video=0\n", ["--film"], "0"), (base, ["--film"], "0")):
            with self.subTest(conf=conf.splitlines()[-1], flags=flags):
                r = self.run_wrapper(conf, show='echo "$FACTORY_EVIDENCE_PACE|$FACTORY_EVIDENCE_FILM"', flags=flags)
                self.assertEqual(r.returncode, 0, r.stderr)
                pace, module = r.stdout.strip().split("|")
                self.assertEqual(pace, want)
                self.assertEqual(module, str((FACTORY / "evidence_film.mjs").resolve()))
                self.assertTrue(pathlib.Path(module).is_file())

    def test_film_alone_is_a_usage_error(self):
        r = subprocess.run(["bash", str(FACTORY / "with-browser"), "--film"], capture_output=True, text=True,
                           env={**os.environ, "FACTORY_BROWSER_CONF": "/nonexistent"}, timeout=30)
        self.assertEqual(r.returncode, 2)
        self.assertIn("usage: with-browser [--film]", r.stderr)

    def test_a_refusing_proxy_is_named(self):
        self.fake = FakeFrontEnd(refuse=True)
        r = self.run_wrapper(f"host=10.20.30.40\nport={free_port()}\nversion=1.61.1\nclient=/w\nallow=\n",
                             proxy=f"http://u:p@127.0.0.1:{self.fake.proxy_port}")
        self.assertEqual(r.returncode, 75)
        self.assertIn("the sandbox's proxy refuses 10.20.30.40", r.stderr)
        self.assertIn("allowedDomains doesn't name it", r.stderr)


class ThisProject(unittest.TestCase):
    """The project's own browser block loads, so a broken one fails CI on its PR rather than every stage's run."""

    @unittest.skipUnless((FACTORY / "factory.json").exists(), "needs the project's factory.json")
    def test_the_browser_block_loads(self):
        browser.block(json.loads((FACTORY / "factory.json").read_text()))


# What the probe printed in the hand test on the runner host (2026-11-20), as the control and as sandboxed Bash. The
# film lines are from a local run against Playwright 1.61.1's own server (2026-11-23): no browser host has run them yet.
CONTROL = """secret env github
secret env oauth
env-name present CLAUDE_CODE_OAUTH_TOKEN
env-name present GITHUB_TOKEN
credentials found 2 secrets checked
connect ok Chromium 149.0.7827.55
app loaded http://localhost:37735/
websocket echoed pong:ping
gpu hardware ANGLE (Apple, ANGLE Metal Renderer: Apple M1, Unspecified Version)
screenshot png 1903 bytes
trace zip 5391 bytes
video webm 2304 bytes
film-hits same plain c,c,b,b,b,c,c,c,c,b,c,c,c filmed c,c,b,b,b,c,c,c,c,b,c,c,c
film-path same 8 moves: 137.5,213.75 175,217.5 212.5,221.25 250,225 287.5,228.75 325,232.5 362.5,236.25 400,240
film-observed none body records plain 0 filmed 0; overlay elements under <html> 1
film-drawn drawn the pointer at the move's end
film-paced paced shortest gap between steps 75 ms (want at least 40)
flags present
outside-name reached http://example.com/ 200
outside-ip reached http://1.1.1.1/ 200
proxy-ip refused http://example.com/ net::ERR_PROXY_CONNECTION_FAILED
proxy-name refused http://example.com/ net::ERR_PROXY_CONNECTION_FAILED
loopback reached plain HTTP answered on 3260,3261 of 3200-3299
runserver-ws none
hostile replaced Chromium 149.0.7827.55
allowed reached cdn.example.org 403
narrow unchecked no proxy: outside the sandbox
end""".splitlines()
AGENT = """credentials clean 2 secrets checked
connect ok Chromium 149.0.7827.55
app loaded http://localhost:37299/
websocket echoed pong:ping
gpu hardware ANGLE (Apple, ANGLE Metal Renderer: Apple M1, Unspecified Version)
screenshot png 1903 bytes
trace zip 5403 bytes
video webm 2432 bytes
film-hits same plain c,c,b,b,b,c,c,c,c,b,c,c,c filmed c,c,b,b,b,c,c,c,c,b,c,c,c
film-path same 8 moves: 137.5,213.75 175,217.5 212.5,221.25 250,225 287.5,228.75 325,232.5 362.5,236.25 400,240
film-observed none body records plain 0 filmed 0; overlay elements under <html> 1
film-drawn drawn the pointer at the move's end
film-paced paced shortest gap between steps 75 ms (want at least 40)
flags present
outside-name refused http://example.com/ net::ERR_SOCKET_NOT_CONNECTED
outside-ip refused http://1.1.1.1/ net::ERR_SOCKS_CONNECTION_FAILED
proxy-ip refused http://example.com/ net::ERR_PROXY_CONNECTION_FAILED
proxy-name refused http://example.com/ net::ERR_PROXY_CONNECTION_FAILED
loopback reached plain HTTP answered on 3260,3261 of 3200-3299
runserver-ws none
hostile replaced Chromium 149.0.7827.55
allowed reached cdn.example.org 200
narrow refused 10.20.30.40:3162 403
end""".splitlines()


def swap(lines, check, line):
    return [line if l.split(" ", 1)[0] == check else l for l in lines]


class Verdict(unittest.TestCase):
    def test_the_hand_tests_pass(self):
        self.assertEqual(browser_check.judge(CONTROL, "control"), [])
        self.assertEqual(browser_check.judge(AGENT, "agent"), [])

    def test_the_outside_world_decides_the_mode(self):
        # The control must reach it (else the agent's refusal proves nothing); the agent must not.
        self.assertTrue(browser_check.judge(swap(CONTROL, "outside-name", "outside-name refused x"), "control"))
        self.assertTrue(browser_check.judge(swap(AGENT, "outside-ip", "outside-ip reached http://1.1.1.1/ 200"), "agent"))
        # A control run that judges as the agent fails, and the other way round.
        self.assertTrue(browser_check.judge(CONTROL, "agent"))
        self.assertTrue(browser_check.judge(AGENT, "control"))

    def test_every_check_is_required(self):
        for line in AGENT[:-1]:
            check = line.split(" ", 1)[0]
            with self.subTest(check=check):
                failures = browser_check.judge([l for l in AGENT if l != line], "agent", allow="cdn.example.org")
                self.assertTrue(any(f"no '{check}' line" in f for f in failures), failures)

    def test_each_boundary_failure_fails(self):
        for check, line in (("proxy-ip", "proxy-ip reached http://example.com/ 403"),
                            ("proxy-name", "proxy-name reached http://example.com/ 400"),
                            ("runserver-ws", "runserver-ws opened 3261"),
                            ("runserver-ws", "runserver-ws unchecked boom"),
                            ("loopback", "loopback unreached plain HTTP answered on no port of 3200-3299"),
                            ("hostile", "hostile honored its address"),
                            ("hostile", "hostile failed launch failed"),
                            ("narrow", "narrow allowed 10.20.30.40:3162 200"),
                            ("narrow", "narrow unchecked the proxy didn't answer"),
                            ("flags", "flags doubled 2 resolver rules"),
                            ("flags", "flags missing --host-resolver-rules=MAP * ~NOTFOUND"),
                            ("websocket", "websocket failed timeout"),
                            ("video", "video bad 0 bytes"),
                            ("credentials", "credentials found 2 secrets checked")):
            with self.subTest(line=line):
                self.assertTrue(browser_check.judge(swap(AGENT, check, line), "agent"))

    def test_the_allowed_host(self):
        # Any HTTP status means Node's fetch reached the host (through the proxy, in the agent run).
        self.assertEqual(browser_check.judge(AGENT, "agent", allow="cdn.example.org"), [])
        self.assertEqual(browser_check.judge(CONTROL, "control", allow="cdn.example.org"), [])
        refused = swap(AGENT, "allowed", "allowed unreached cdn.example.org UND_ERR_SOCKET")
        self.assertTrue(any("browser.allow" in f for f in browser_check.judge(refused, "agent", allow="cdn.example.org")))
        # With the entry's probe path, the GET must answer 2xx: another answer has its own reason.
        got = swap(AGENT, "allowed", "allowed reached cdn.example.org 200 GET /cards/front.webp")
        self.assertEqual(browser_check.judge(got, "agent", allow="cdn.example.org"), [])
        answered = browser_check.judge(swap(AGENT, "allowed", "allowed answered cdn.example.org 522 GET /cards/front.webp"),
                                       "agent", allow="cdn.example.org")
        self.assertEqual(len(answered), 1)
        self.assertIn("status other than 2xx", answered[0])
        self.assertIn("522 GET /cards/front.webp", answered[0])
        # Another host than the project's first, or none where the project allows one, fails.
        self.assertTrue(browser_check.judge(swap(AGENT, "allowed", "allowed reached other.example.org 200"), "agent",
                                            allow="cdn.example.org"))
        self.assertTrue(browser_check.judge(swap(AGENT, "allowed", "allowed none browser.allow is empty"), "agent",
                                            allow="cdn.example.org"))
        # With nothing allowed the probe says so, and a probe that reached a host anyway fails.
        none = swap(AGENT, "allowed", "allowed none browser.allow is empty")
        self.assertEqual(browser_check.judge(none, "agent", allow=""), [])
        self.assertTrue(browser_check.judge(AGENT, "agent", allow=""))
        # A missing line fails once the job names the host; an old caller that doesn't is left as it was.
        missing = [l for l in AGENT if not l.startswith("allowed ")]
        self.assertTrue(any("no 'allowed' line" in f for f in browser_check.judge(missing, "agent", allow="")))
        self.assertEqual(browser_check.judge(missing, "agent"), [])

    def test_the_smoke_job_names_the_allowed_host(self):
        text = (FACTORY / "templates" / "factory-smoke.yml").read_text()
        self.assertIn('jq -r \'.browser.allow[0].host // ""\' "$CHECKS/factory.json" > "$CHECKS/browser-allow"', text)
        self.assertEqual(text.count('"$(cat "$CHECKS/browser-allow")"'), 2)

    def test_a_visible_credential_fails_the_agent(self):
        self.assertTrue(browser_check.judge(["secret env oauth"] + AGENT, "agent"))
        self.assertTrue(browser_check.judge(["env-name present GH_TOKEN"] + AGENT, "agent"))
        # The control must see a token by value, not only by name.
        self.assertTrue(browser_check.judge([l for l in CONTROL if not l.startswith("secret ")], "control"))

    def test_the_gpu(self):
        software = swap(AGENT, "gpu", "gpu software ANGLE (Google, Vulkan 1.3.0 (SwiftShader Device))")
        self.assertTrue(browser_check.judge(software, "agent"))
        self.assertEqual(browser_check.judge(software, "agent", gpu=False), [])

    def test_a_crash_or_a_repeat_cant_hide_a_failure(self):
        self.assertTrue(browser_check.judge(AGENT[:-1] + ["probe crashed boom", "end"], "agent"))
        # The first line of a check counts: a later "ok" can't overwrite a failure.
        self.assertTrue(browser_check.judge(["runserver-ws opened 3261"] + AGENT, "agent"))

    def test_main(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = pathlib.Path(tmp) / "agent.txt"
            env = {k: v for k, v in os.environ.items() if k != "GITHUB_STEP_SUMMARY"}
            out.write_text("\n".join(AGENT) + "\n<sandbox_violations>note</sandbox_violations>\n")
            r = subprocess.run([sys.executable, "-I", str(FACTORY / "browser_check.py"), "agent", str(out)],
                               capture_output=True, text=True, env=env)
            self.assertEqual(r.returncode, 0, r.stdout)
            out.write_text("\n".join(AGENT[:-1]) + "\n")
            r = subprocess.run([sys.executable, "-I", str(FACTORY / "browser_check.py"), "agent", str(out)],
                               capture_output=True, text=True, env=env)
            self.assertEqual(r.returncode, 1)
            self.assertIn("no end marker", r.stdout)
            out.write_text("UNAVAILABLE: browser host (no answer)\n")
            r = subprocess.run([sys.executable, "-I", str(FACTORY / "browser_check.py"), "agent", str(out), "nogpu"],
                               capture_output=True, text=True, env=env)
            self.assertEqual(r.returncode, 1)
            self.assertIn("with-browser found no browser host", r.stdout)



def png(width=4, height=3, extra=b"", trailing=b"", raw=None):
    """An 8-bit RGBA PNG, with any extra chunks before the image data and bytes after its end."""
    if raw is None:
        raw = b"".join(b"\x00" + bytes(i % 256 for i in range(width * 4)) for _ in range(height))
    body = evidence.chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)) + extra
    body += evidence.chunk(b"IDAT", zlib.compress(raw)) + evidence.chunk(b"IEND", b"")
    return evidence.PNG_SIG + body + trailing


def trace(names=("trace.trace", "trace.network", "resources/abc.png")):
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        for n in names:
            z.writestr(n, b"x" * 10)
    return out.getvalue()


WEBM = b"\x1a\x45\xdf\xa3\x9f\x42\x86\x81\x01\x42\x82\x84webm" + b"\x00" * 200


class Evidence(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = pathlib.Path(self.tmp.name) / "ws"
        self.dir = self.ws / ".factory" / "evidence"
        self.dir.mkdir(parents=True)
        self.out = pathlib.Path(self.tmp.name) / "out"

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, manifest, **files):
        (self.dir / "manifest.json").write_text(json.dumps(manifest))
        for name, body in files.items():
            (self.dir / name.replace("__", ".")).write_bytes(body)

    def pack(self):
        return evidence.pack(str(self.ws), ".factory/evidence", self.out, "Issue #7, implement")

    def entry(self, f, step=1, shows="the board before the click", bug=False):
        return {"file": f, "step": step, "shows": shows, "bug": bug}

    def test_a_reproduction_is_packed(self):
        self.write([self.entry("before.png"), self.entry("after.png", 2, "the score stays at 0", True),
                    self.entry("run.webm", 3, "the whole run"), self.entry("trace.zip", 3, "the trace")],
                   before__png=png(), after__png=png(), run__webm=WEBM, trace__zip=trace())
        r = self.pack()
        self.assertEqual((r["report"], r["video"], r["video_in_report"], r["trace"]), (True, True, True, True))
        self.assertEqual(evidence.uploads(r), {"report": True, "video": False, "trace": True})
        self.assertEqual([f["file"] for f in r["files"]], ["before.png", "after.png", "run.webm", "trace.zip"])
        self.assertEqual(r["dropped"], [])
        page = (self.out / "evidence-report.html").read_text()
        self.assertIn("default-src 'none'; img-src data:; media-src data:; style-src 'unsafe-inline'", page)
        self.assertIn('name="viewport" content="width=device-width, initial-scale=1"', page)
        self.assertNotIn("<script", page.lower())
        self.assertIn("the score stays at 0", page)
        # The video plays from the page itself, with no script and nothing else to fetch: after the table, which shows
        # while it loads, and before the screenshots.
        self.assertIn('<video controls playsinline preload="metadata" src="data:video/webm;base64,', page)
        data = base64.b64decode(page.split("data:video/webm;base64,")[1].split('"')[0])
        self.assertEqual(data, WEBM)
        self.assertLess(page.index("<table"), page.index("<video"))
        self.assertLess(page.index("<video"), page.index("<img"))
        self.assertIn("<figcaption>Step 3: the whole run</figcaption>", page)
        self.assertFalse((self.out / "evidence-video.webm").exists())
        names = zipfile.ZipFile(self.out / "evidence-trace.zip").namelist()
        self.assertEqual(sorted(names), ["resources/abc.png", "trace.network", "trace.trace"])

    def test_a_video_over_the_reports_cap_goes_beside_it(self):
        self.write([self.entry("a.png"), self.entry("run.webm", 2, "the whole run")], a__png=png(), run__webm=WEBM)
        with mock.patch.object(evidence, "MAX_EMBED", len(WEBM) - 1):
            r = self.pack()
        self.assertEqual((r["video"], r["video_in_report"]), (True, False))
        self.assertEqual(evidence.uploads(r), {"report": True, "video": True, "trace": False})
        self.assertEqual((self.out / "evidence-video.webm").read_bytes(), WEBM)
        page = (self.out / "evidence-report.html").read_text()
        self.assertNotIn("<video", page)
        self.assertIn("is over the", page)
        self.assertIn("separate video artifact", page)

    def test_screenshots_lose_their_metadata_and_keep_their_pixels(self):
        text = evidence.chunk(b"tEXt", b"Comment\x00exfiltrated") + evidence.chunk(b"eXIf", b"MM\x00*")
        self.write([self.entry("a.png")], a__png=png(extra=text, trailing=b"hidden after the end"))
        self.pack()
        page = (self.out / "evidence-report.html").read_text()
        data = base64.b64decode(page.split("data:image/png;base64,")[1].split('"')[0])
        self.assertNotIn(b"exfiltrated", data)
        self.assertNotIn(b"hidden", data)
        self.assertNotIn(b"eXIf", data)
        self.assertEqual(evidence.clean_png(data), data)  # stable: a clean PNG cleans to itself
        # The pixels survive: the image data decompresses to exactly the original rows.
        idat = data[data.index(b"IDAT") + 4:data.index(b"IEND") - 8]
        self.assertEqual(zlib.decompress(idat), b"".join(b"\x00" + bytes(i % 256 for i in range(16)) for _ in range(3)))
        self.assertEqual(evidence.clean_png(png()), evidence.clean_png(png(extra=text)))

    def test_what_isnt_listed_or_doesnt_check_is_dropped(self):
        self.write([self.entry("fake.png"), self.entry("second.webm"), self.entry("first.webm"),
                    self.entry("missing.png"), self.entry("evil.zip")],
                   fake__png=b"<html>not a png</html>", first__webm=WEBM, second__webm=WEBM, stray__png=png(),
                   evil__zip=trace(("trace.trace", "../outside")))
        r = self.pack()
        why = {d["file"]: d["why"] for d in r["dropped"]}
        self.assertIn("not a PNG", why["fake.png"])
        self.assertEqual(why["stray.png"], "not in the manifest")
        self.assertIn("not there", why["missing.png"])
        self.assertIn("isn't plain", why["evil.zip"])
        self.assertIn("only one video", why["first.webm"])
        self.assertEqual([f["file"] for f in r["files"]], ["second.webm"])

    def test_links_and_odd_files_are_never_followed(self):
        outside = pathlib.Path(self.tmp.name) / "secret.png"
        outside.write_bytes(png())
        (self.dir / "link.png").symlink_to(outside)
        os.mkfifo(self.dir / "pipe.png")
        (self.dir / "sub.png").mkdir()
        self.write([self.entry("link.png"), self.entry("pipe.png"), self.entry("sub.png")])
        r = self.pack()
        self.assertEqual(r["files"], [])
        self.assertEqual(len(r["dropped"]), 3)
        # The directory itself, or a component of it, as a link: nothing is read through it.
        shutil.rmtree(self.ws / ".factory")
        (self.ws / ".factory").symlink_to(pathlib.Path(self.tmp.name))
        with self.assertRaises(evidence.Bad):
            self.pack()

    def test_a_bad_manifest_drops_everything(self):
        for manifest in ([{"file": "a.png"}], [self.entry("../a.png")], [self.entry("a.png", shows="two\nlines")],
                         [self.entry("a.png", step=0)], [self.entry("a.png", bug="yes")], {"file": "a.png"},
                         [self.entry("a.png")] * 2):
            with self.subTest(manifest=manifest):
                self.write(manifest, a__png=png())
                r = self.pack()
                self.assertEqual(r["files"], [])
                self.assertEqual(r["dropped"][0]["file"], "manifest.json")

    def test_odd_names_and_crafted_files_cost_only_themselves(self):
        try:  # a name that isn't UTF-8 (macOS refuses one; Linux, where the jobs run, doesn't)
            os.close(os.open(os.fsencode(self.dir) + b"/caf\xe9.png", os.O_CREAT | os.O_WRONLY))
            odd_name = True
        except OSError:
            odd_name = False
        # A zip whose entry claims a compression method zipfile can't read: dropped, the rest kept.
        bad = bytearray(trace(("trace.trace",)))
        central = bad.rindex(b"PK\x01\x02")
        bad[8:10] = bad[central + 10:central + 12] = (99).to_bytes(2, "little")
        self.write([self.entry("t.zip"), self.entry("a.png")], t__zip=bytes(bad), a__png=png())
        r = self.pack()
        self.assertEqual([f["file"] for f in r["files"]], ["a.png"])
        self.assertIn("t.zip", {d["file"] for d in r["dropped"]})
        if odd_name:
            odd = next(d["file"] for d in r["dropped"] if d["file"].startswith("caf"))
            self.assertEqual(odd, "caf\\udce9.png")
        # The record, and the PR lines the guard renders from it, are plain UTF-8 throughout.
        text = json.dumps(r)
        "\n".join(guard.evidence_lines(text, {"report": "1"}, RUN, "7")).encode("utf-8")

    def test_a_trace_that_would_unpack_past_its_cap_is_refused_unread(self):
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w", zipfile.ZIP_BZIP2) as z:
            z.writestr("trace.trace", b"x" * 1000)
        with self.assertRaises(evidence.Bad) as e:
            evidence.clean_trace(out.getvalue())
        self.assertIn("stored or deflated", str(e.exception))

    def test_a_palette_is_checked(self):
        def palette_png(plte):
            raw = b"\x00\x00\x01" * 2
            body = evidence.chunk(b"IHDR", struct.pack(">IIBBBBB", 2, 2, 8, 3, 0, 0, 0)) + evidence.chunk(b"PLTE", plte)
            return evidence.PNG_SIG + body + evidence.chunk(b"IDAT", zlib.compress(raw)) + evidence.chunk(b"IEND", b"")
        self.assertTrue(evidence.clean_png(palette_png(b"\x00" * 6)).startswith(evidence.PNG_SIG))
        for plte in (b"\x00" * 9000, b"\x00" * 7, b""):
            with self.subTest(size=len(plte)), self.assertRaises(evidence.Bad):
                evidence.clean_png(palette_png(plte))

    def test_text_is_printed_plain(self):
        self.assertEqual(evidence.plain("x\n::warning::forged"), "x\\n::warning::forged")
        self.assertEqual(evidence.plain("a\u202eb"), "a\\u202eb")
        # A name with a trailing newline is no name: refused, not taken for another kind.
        self.write([self.entry("a.png\n"), self.entry("b.png")], b__png=png())
        r = self.pack()
        self.assertEqual(r["files"], [])
        self.assertEqual(r["dropped"][0]["file"], "manifest.json")

    def test_no_evidence_packs_nothing(self):
        shutil.rmtree(self.ws / ".factory")
        self.assertEqual(self.pack(), {"files": [], "dropped": [], "report": False, "video": False,
                                       "video_in_report": False, "trace": False})

    def test_caps(self):
        # A header claiming more than the cap is refused before anything is decompressed.
        self.assertRaises(evidence.Bad, evidence.clean_png, png(width=5000, height=5000, raw=b"\x00"))
        # Image data that isn't the size its header says, or decompresses past it.
        self.assertRaises(evidence.Bad, evidence.clean_png, png(raw=b"\x00" * 10))
        self.assertRaises(evidence.Bad, evidence.clean_png, png(raw=b"\x00" * (3 * 17 + 1)))
        many = [self.entry(f"s{i}.png") for i in range(21)]
        self.write(many, **{f"s{i}__png": png() for i in range(21)})
        r = self.pack()
        self.assertEqual(len(r["files"]), 20)
        self.assertIn("more than 20", r["dropped"][-1]["why"])
        trash = {f"x{i}__png": b"" for i in range(40)}
        self.write([], **trash)
        r = self.pack()
        self.assertEqual(len(r["dropped"]), 21)
        self.assertIn("more files dropped", r["dropped"][-1]["why"])

    def test_main_writes_the_record_and_outputs(self):
        self.write([self.entry("a.png")], a__png=png())
        outputs = pathlib.Path(self.tmp.name) / "outputs"
        env = {**os.environ, "GITHUB_OUTPUT": str(outputs)}
        r = subprocess.run([sys.executable, "-I", str(FACTORY / "evidence.py"), str(self.ws), ".factory/evidence",
                            str(self.out), "Issue #7"], capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        lines = outputs.read_text().splitlines()
        self.assertIn("report=yes", lines)
        self.assertIn("video=no", lines)
        record = json.loads(next(l for l in lines if l.startswith("manifest="))[len("manifest="):])
        self.assertEqual(record, json.loads((self.out / "evidence.json").read_text()))


class EvidenceRecordsItsRun(unittest.TestCase):
    def test_the_issue_and_run_come_from_the_jobs_environment(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws, out = pathlib.Path(tmp) / "ws", pathlib.Path(tmp) / "out"
            (ws / ".factory" / "evidence").mkdir(parents=True)
            for env_issue, env_run, want in (("42", "123", {"issue": 42, "run": 123}), ("x", "", {})):
                env = {k: v for k, v in os.environ.items() if k not in ("GITHUB_OUTPUT",)}
                env.update(ISSUE_NUMBER=env_issue, GITHUB_RUN_ID=env_run)
                subprocess.run([sys.executable, "-I", str(FACTORY / "evidence.py"), str(ws), ".factory/evidence",
                                str(out), "t"], check=True, capture_output=True, env=env)
                rec = json.loads((out / "evidence.json").read_text())
                self.assertEqual({k: rec[k] for k in ("issue", "run") if k in rec}, want)

    def test_the_guard_takes_only_numbers_there(self):
        base = {"files": [], "dropped": [{"file": "x.png", "why": "not in the manifest"}], "report": False,
                "video": False, "trace": False}
        self.assertTrue(guard.evidence_lines(json.dumps(dict(base, issue=42, run=123)), {}, RUN, "42"))
        for bad in ({"issue": True}, {"run": "123"}, {"attempt": 2}):
            with self.subTest(bad=bad):
                lines = guard.evidence_lines(json.dumps(dict(base, **bad)), {}, RUN, "42")
                self.assertTrue(lines[0].startswith("- Not shown:"))


RUN = "https://github.com/acme/app/actions/runs/123"


class EvidenceInThePR(unittest.TestCase):
    def record(self, **changes):
        rec = {"files": [{"file": "after.png", "step": 2, "shows": "the score stays at 0", "bug": True, "kind": "screenshot"},
                         {"file": "run.webm", "step": 3, "shows": "the run", "bug": False, "kind": "video"}],
               "dropped": [{"file": "stray.png", "why": "not in the manifest"}],
               "report": True, "video": True, "trace": False}
        rec.update(changes)
        return json.dumps(rec)

    def test_the_writer_builds_the_links(self):
        lines = guard.evidence_lines(self.record(), {"report": "11", "video": "12"}, RUN, "7", "/srv/evidence")
        text = "\n".join(lines)
        self.assertIn(f"[report]({RUN}/artifacts/11)", text)
        self.assertIn(f"[video]({RUN}/artifacts/12)", text)
        self.assertNotIn("trace", text.split("\n")[0])
        self.assertIn("`/srv/evidence/app/7/123/`", text)
        self.assertIn("Step 2, `after.png` (screenshot): the score stays at 0 **Shows the bug.**", text)
        self.assertIn("Dropped by the factory: `stray.png`", text)

    def test_a_video_inside_the_report_is_linked_as_the_report(self):
        lines = guard.evidence_lines(self.record(video_in_report=True, trace=True), {"report": "11", "trace": "13"},
                                     RUN, "7", "/srv/evidence")
        text = "\n".join(lines)
        self.assertIn(f"[report, with the video]({RUN}/artifacts/11), [Playwright trace]({RUN}/artifacts/13). "
                      "The report has the video, the screenshots and what each shows.", text)
        self.assertNotIn("[video]", text)
        self.assertNotIn("video (its upload failed)", text)
        self.assertIn("the archive keeps the report, at `/srv/evidence/app/7/123/` (the trace isn't kept)", text)
        # A video beside the report is linked, and archived, on its own; an older record has no video_in_report.
        text = "\n".join(guard.evidence_lines(self.record(), {"report": "11", "video": "12"}, RUN, "7", "/srv/evidence"))
        self.assertIn(f"[report]({RUN}/artifacts/11), [video]({RUN}/artifacts/12). The report has the screenshots", text)
        self.assertIn("the archive keeps the report and the video, at", text)
        # A record that says the video is inside a report it doesn't have isn't evidence.py's.
        for bad in ({"video_in_report": True, "video": False}, {"video_in_report": True, "report": False},
                    {"video_in_report": 1}):
            with self.subTest(bad=bad):
                self.assertTrue(guard.evidence_lines(self.record(**bad), {}, RUN, "7")[0].startswith("- Not shown:"))

    def test_an_id_that_isnt_a_number_is_no_link(self):
        text = "\n".join(guard.evidence_lines(self.record(), {"report": "11)](https://evil.example/x", "video": ""},
                                               RUN, "7"))
        self.assertNotIn("evil.example", text)
        self.assertIn("report (its upload failed)", text)
        self.assertNotIn("archive", text)

    def test_a_record_that_doesnt_check_turns_the_section_into_a_line(self):
        for rec in ("not json", self.record(files=[{"file": "../x.png", "step": 1, "shows": "x", "bug": False,
                                                     "kind": "screenshot"}]),
                    self.record(files=[{"file": "a.png", "step": 1, "shows": "![x](https://evil.example/y)",
                                        "bug": False, "kind": "screenshot"}]),
                    self.record(files=[{"file": "a.webm", "step": 1, "shows": "x", "bug": False, "kind": "screenshot"}]),
                    self.record(dropped=[{"file": "x", "why": "ghp_" + "a" * 30}])):
            with self.subTest(rec=rec[:60]):
                lines = guard.evidence_lines(rec, {"report": "1"}, RUN, "7")
                self.assertEqual(len(lines), 1)
                self.assertTrue(lines[0].startswith("- Not shown:"))
        self.assertEqual(guard.evidence_lines("", {}, RUN, "7"), [])
        empty = json.dumps({"files": [], "dropped": [], "report": False, "video": False, "trace": False})
        self.assertEqual(guard.evidence_lines(empty, {}, RUN, "7"), [])

    def test_the_section_has_a_budget(self):
        files = [{"file": f"s{i}.png", "step": i + 1, "shows": "\U0001F600" * 300, "bug": False, "kind": "screenshot"}
                 for i in range(30)]
        lines = guard.evidence_lines(self.record(files=files), {"report": "1"}, RUN, "7")
        self.assertLessEqual(len("\n".join(lines).encode()), guard.MAX_EVIDENCE + 200)
        self.assertRegex(lines[-1], r"^- And \d+ more, in the report\.$")

    def test_only_ascii_digits_make_a_link(self):
        text = "\n".join(guard.evidence_lines(self.record(), {"report": "\u0661\u0662", "video": "12\n"}, RUN, "7"))
        self.assertNotIn("/artifacts/", text)

    def test_a_record_of_the_wrong_shape_never_raises(self):
        for rec in ('{"files": [{"file": "a.png", "step": 1, "shows": "x", "bug": false, "kind": ["screenshot"]}], '
                    '"dropped": [], "report": true, "video": false, "trace": false}', "[" * 5000 + "]" * 5000, "null"):
            with self.subTest(rec=rec[:40]):
                lines = guard.evidence_lines(rec, {"report": "1"}, RUN, "7")
                self.assertTrue(lines[0].startswith("- Not shown:"))

    def test_captions_are_literal(self):
        lines = guard.evidence_lines(self.record(files=[{"file": "a.png", "step": 1, "shows": "# heading [link](x) <b>",
                                                         "bug": False, "kind": "screenshot"}]), {"report": "1"}, RUN, "7")
        self.assertNotIn("[link](x)", lines[-2])
        self.assertIn("\\#", lines[-2])


@unittest.skipUnless(HAS_YAML, "needs PyYAML")
class Policy(unittest.TestCase):
    def test_uploads_from_an_agent_job(self):
        ok = [{"uses": policy.UPLOAD + "x", "with": {"path": "${{ runner.temp }}/implement/implement.bundle"}},
              {"uses": policy.UPLOAD + "x", "with": {"path": "${{ steps.claude.outputs.execution_file }}"}},
              {"uses": policy.UPLOAD + "x", "with": {"path": "${{ runner.temp }}/evidence/evidence-video.webm",
                                                     "archive": False}}]
        self.assertEqual(policy.upload_failures("j", ok, True), [])
        for step in ({"uses": policy.UPLOAD + "x", "with": {"path": ".factory/evidence"}},
                     {"uses": policy.UPLOAD + "x", "with": {"path": "${{ github.workspace }}/x"}},
                     {"uses": policy.UPLOAD + "x", "with": {"path": "${{ runner.temp }}/../__w/x"}},
                     {"uses": policy.UPLOAD + "x", "with": {"path": "${{ runner.temp }}/a\n.factory"}},
                     {"uses": policy.UPLOAD + "x", "with": {"path": "${{ runner.temp }}/evidence/x.html", "archive": "false"}}):
            with self.subTest(step=step):
                self.assertTrue(policy.upload_failures("j", [step], True))
        # Spellings GitHub reads the same way, and an archive input that's an expression.
        for step in ({"uses": "Actions/Upload-Artifact@x", "with": {"path": ".factory/evidence"}},
                     {"uses": policy.UPLOAD + "x", "with": {"Path": "${{ github.workspace }}/x"}},
                     {"uses": policy.UPLOAD + "x", "with": {"path": "${{ runner.temp }}/x.html", "Archive": False}},
                     {"uses": policy.UPLOAD + "x", "with": {"path": "${{ runner.temp }}/x.html", "archive": "${{ false }}"}}):
            with self.subTest(step=step):
                self.assertTrue(policy.upload_failures("j", [step], True))
        # A job without an agent may upload its own files, but never unzipped.
        self.assertEqual(policy.upload_failures("j", [{"uses": policy.UPLOAD + "x", "with": {"path": "fixtures"}}], False), [])
        self.assertTrue(policy.upload_failures("j", [{"uses": policy.UPLOAD + "x",
                                                      "with": {"path": "report.html", "archive": False}}], False))

    @unittest.skipUnless((FACTORY / "factory.json").exists(), "needs the project's factory.json")
    def test_the_smoke_job_runs_the_probe_in_implements_sandbox(self):
        self.assertEqual(policy.configure(FACTORY), [])
        smoke = yaml.safe_load(render.render_all(FACTORY, FACTORY / "templates")["factory-smoke.yml"])
        job = smoke["jobs"]["browser-host"]
        self.assertEqual(policy.job_failures("browser-host", job, smoke.get("env") or {}, None, FACTORY,
                                             "factory-smoke.yml", set()), [])
        steps = job["steps"]
        agent = next(s for s in steps if str(s.get("uses", "")).startswith(policy.ACTION))
        self.assertIn("implement-sandbox.settings.json", agent["with"]["settings"])
        # No secret where the project's code runs: the install, and the control (which holds a canary).
        install = [s for s in steps if 'agent_job.sh" workspace' in str(s.get("run", ""))]
        control = [s for s in steps if s.get("name") == "Control probe"]
        self.assertEqual((len(install), len(control)), (1, 1))
        for step in install + control:
            self.assertNotIn("secrets.", json.dumps(step), step.get("name"))
        self.assertNotIn("secrets.", json.dumps(job.get("env") or {}))


if __name__ == "__main__":
    unittest.main()
