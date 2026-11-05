#!/usr/bin/env python3
"""The factory's echo service as a small HTTP server, for anywhere that runs a container or a process
behind HTTPS (z-sdlc factory bundle; factory.json's smoke.echo_host). It answers like echo/worker.js:
the method, URL, query arguments and request headers as indented JSON, one header per line, so smoke can
read what the sandbox proxy injected. It stores and logs nothing. Standard library only.

/mcp is the same stand-in MCP server as the Worker's (streamable HTTP, stateless, JSON responses):
header_digest returns the SHA-256 of the Authorization header it received, never the header; not_allowed
is a tool the factory must refuse to call, and says so if it ever runs.

    python3 server.py [port]      (default 8080; put TLS in front, smoke calls https://<host>/headers)
"""
import hashlib
import http.server
import json
import sys
import urllib.parse

TOOLS = [
    {"name": "header_digest", "description": "The SHA-256 of the Authorization header this request carried.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "not_allowed", "description": "A tool the factory's tool list leaves out; calling it must be refused.",
     "inputSchema": {"type": "object", "properties": {}}},
]


class Echo(http.server.BaseHTTPRequestHandler):
    def send(self, status, body=None, headers=()):
        data = b"" if body is None else (json.dumps(body, indent=2) + "\n").encode()
        self.send_response(status)
        for name, value in headers:
            self.send_header(name, value)
        if body is not None:
            self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def answer(self):
        url = urllib.parse.urlsplit(self.path)
        if url.path == "/mcp":
            return self.mcp()
        headers = {"-".join(part.capitalize() for part in name.split("-")): value for name, value in self.headers.items()}
        self.send(200, {"args": dict(urllib.parse.parse_qsl(url.query)), "headers": headers,
                        "method": self.command, "url": self.path})

    def mcp(self):
        if self.command != "POST":
            return self.send(405, headers=[("Allow", "POST")])
        try:
            message = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"null")
            assert isinstance(message, dict)
        except (ValueError, AssertionError):
            return self.send(400, {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}})
        if message.get("id") is None:
            return self.send(202)
        params = message.get("params") or {}
        method = message.get("method")
        if method == "initialize":
            result = {"protocolVersion": params.get("protocolVersion") or "2025-06-18", "capabilities": {"tools": {}},
                      "serverInfo": {"name": "factory-echo", "version": "1"}}
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {"tools": TOOLS}
        elif method == "tools/call" and params.get("name") == "header_digest":
            digest = hashlib.sha256((self.headers.get("Authorization") or "").encode()).hexdigest()
            result = {"content": [{"type": "text", "text": f"authorization-sha256={digest}"}]}
        elif method == "tools/call" and params.get("name") == "not_allowed":
            result = {"content": [{"type": "text", "text": "not_allowed ran: the factory let a refused tool through"}]}
        else:
            code, text = (-32602, "unknown tool") if method == "tools/call" else (-32601, "method not found")
            return self.send(200, {"jsonrpc": "2.0", "id": message["id"], "error": {"code": code, "message": text}})
        self.send(200, {"jsonrpc": "2.0", "id": message["id"], "result": result})

    do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = answer

    def log_message(self, *args):  # store and log nothing
        pass


def main(port=8080):
    http.server.ThreadingHTTPServer(("", port), Echo).serve_forever()


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 8080)
