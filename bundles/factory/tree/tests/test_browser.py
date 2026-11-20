"""The browser route (process/factory.md, D6): browser.py, which adds it to a stage's sandbox settings;
with-browser, the wrapper sandboxed Bash runs a browser command through; and browser_check.py, which judges
factory-smoke's browser-host probe. The route itself is proven only by that smoke job, against the real browser
host and sandbox; these pin what the scripts decide."""

import base64
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

FACTORY = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FACTORY))
import browser  # noqa: E402
import browser_check  # noqa: E402
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
        self.assertIn("allow=cdn.example.org\n", conf.read_text())
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
                         f"host={HOST}\nport=3161\nport_base=3100\nversion=1.61.1\nclient={(self.ws / 'web').resolve()}\nallow=\n")

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

    def run_wrapper(self, conf_text, proxy=""):
        conf = pathlib.Path(self.tmp.name) / "browser.conf"
        conf.write_text(conf_text)
        env = {k: v for k, v in os.environ.items() if k.lower() not in ("http_proxy", "https_proxy", "all_proxy", "no_proxy")}
        env["FACTORY_BROWSER_CONF"] = str(conf)
        if proxy:
            env["HTTP_PROXY"] = proxy
        show = 'echo "$FACTORY_BROWSER_WS_ENDPOINT|$PW_TEST_CONNECT_WS_ENDPOINT|$FACTORY_BROWSER_CLIENT|$FACTORY_BROWSER_ALLOW|${NODE_USE_ENV_PROXY:-}"'
        return subprocess.run(["bash", str(FACTORY / "with-browser"), "sh", "-c", show], capture_output=True, text=True,
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


# What the probe printed in the hand test on the runner host (2026-11-20), as the control and as sandboxed Bash.
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
flags present
outside-name reached http://example.com/ 200
outside-ip reached http://1.1.1.1/ 200
proxy-ip refused http://example.com/ net::ERR_PROXY_CONNECTION_FAILED
proxy-name refused http://example.com/ net::ERR_PROXY_CONNECTION_FAILED
loopback reached plain HTTP answered on 3260,3261 of 3200-3299
runserver-ws none
hostile replaced Chromium 149.0.7827.55
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
flags present
outside-name refused http://example.com/ net::ERR_SOCKET_NOT_CONNECTED
outside-ip refused http://1.1.1.1/ net::ERR_SOCKS_CONNECTION_FAILED
proxy-ip refused http://example.com/ net::ERR_PROXY_CONNECTION_FAILED
proxy-name refused http://example.com/ net::ERR_PROXY_CONNECTION_FAILED
loopback reached plain HTTP answered on 3260,3261 of 3200-3299
runserver-ws none
hostile replaced Chromium 149.0.7827.55
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
                failures = browser_check.judge([l for l in AGENT if l != line], "agent")
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


@unittest.skipUnless(HAS_YAML, "needs PyYAML")
class Policy(unittest.TestCase):
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
