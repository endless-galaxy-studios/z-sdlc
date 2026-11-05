"""echo/server.py answers like the echo Worker smoke calls: the request's headers as indented JSON, one per
line (smoke greps for the injected credential's line), its query arguments, method and URL."""
import hashlib
import importlib.util
import http.server
import json
import pathlib
import threading
import unittest
import urllib.error
import urllib.request

SERVER = pathlib.Path(__file__).resolve().parents[1] / "echo" / "server.py"
spec = importlib.util.spec_from_file_location("echo_server", SERVER)
echo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(echo)


class Echo(unittest.TestCase):
    def setUp(self):
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), echo.Echo)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def test_headers_one_per_line(self):
        req = urllib.request.Request(self.url + "/headers?a=1", headers={"x-factory-probe": "masked-value"})
        with urllib.request.urlopen(req) as r:
            text = r.read().decode()
            self.assertEqual(r.headers["Content-Type"], "application/json")
        self.assertIn('    "X-Factory-Probe": "masked-value",', text.splitlines())
        body = json.loads(text)
        self.assertEqual((body["args"], body["method"], body["url"]), ({"a": "1"}, "GET", "/headers?a=1"))

    def test_post(self):
        req = urllib.request.Request(self.url + "/post", data=b"x", method="POST")
        with urllib.request.urlopen(req) as r:
            self.assertEqual(json.loads(r.read())["method"], "POST")


    def rpc(self, message, headers=None):
        req = urllib.request.Request(self.url + "/mcp", data=json.dumps(message).encode(), method="POST",
                                     headers={"Content-Type": "application/json", **(headers or {})})
        with urllib.request.urlopen(req) as r:
            return r.status, (json.loads(r.read()) if r.status != 202 else None)

    def test_mcp_stand_in(self):
        status, body = self.rpc({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}})
        self.assertEqual((status, body["result"]["protocolVersion"]), (200, "2025-06-18"))
        self.assertEqual(self.rpc({"jsonrpc": "2.0", "method": "notifications/initialized"}), (202, None))
        _, body = self.rpc({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        self.assertEqual([t["name"] for t in body["result"]["tools"]], ["header_digest", "not_allowed"])
        # The digest, never the header: smoke compares it outside the agent.
        _, body = self.rpc({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "header_digest"}},
                           {"Authorization": "Bearer throwaway"})
        text = body["result"]["content"][0]["text"]
        self.assertEqual(text, "authorization-sha256=" + hashlib.sha256(b"Bearer throwaway").hexdigest())
        self.assertNotIn("throwaway", text)
        _, body = self.rpc({"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "nope"}})
        self.assertEqual(body["error"]["code"], -32602)
        with self.assertRaises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(self.url + "/mcp")
        self.assertEqual(e.exception.code, 405)


if __name__ == "__main__":
    unittest.main()
