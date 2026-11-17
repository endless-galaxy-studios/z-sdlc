"""The egress proxy and the connection class, with socket pairs and a fake resolver/connector (no network). The hosts are
the block's egress list, never names in the broker. Carried over from the third project's broker tests (test_egress.py)."""

import http.client
import io
import ipaddress
import json
import os
import pathlib
import socket
import ssl
import tempfile
import threading
import unittest
from unittest import mock

import fakes
import factory_op as fo

HOST = fakes.CATALOG["broker"]["egress"][0]
ALLOWED = frozenset(fakes.CATALOG["broker"]["egress"])
PUBLIC = "93.184.216.34"  # example.com's address (IANA): public, unlike the documentation ranges, which aren't global
SHARED = str(ipaddress.IPv4Address(0x64400001))  # the first address of RFC 6598's shared space (carrier-grade NAT)


def client_hello(host):
    """A real TLS ClientHello record for `host`, from the ssl module's memory BIO."""
    inc, out = ssl.MemoryBIO(), ssl.MemoryBIO()
    obj = ssl.create_default_context().wrap_bio(inc, out, server_hostname=host)
    try:
        obj.do_handshake()
    except ssl.SSLWantReadError:
        pass
    return out.read()


class Proxy:
    """Runs egress_serve on one end of a socket pair; the test is the client on the other."""

    def __init__(self, resolver=None, allowed=ALLOWED):
        self.resolver_calls, self.connector_calls, self.logs = [], [], []
        self.resolver_impl = resolver or (lambda host, port, **kw: [(2, 1, 6, "", (PUBLIC, 443))])
        self.client, server = socket.socketpair()
        self.client.settimeout(5)
        self.up_proxy_side, self.up_server_side = socket.socketpair()
        self.up_server_side.settimeout(5)

        def resolver(host, port, **kw):
            self.resolver_calls.append((host, port, kw))
            return self.resolver_impl(host, port, **kw)

        def connector(addr, timeout=None):
            self.connector_calls.append(addr)
            return self.up_proxy_side
        self.thread = threading.Thread(target=fo.egress_serve, args=(server,), daemon=True,
                                       kwargs=dict(allowed=allowed, resolver=resolver, connector=connector,
                                                   log=self.logs.append, timeout=3))
        self.thread.start()

    def connect(self, line):
        self.client.sendall(line)
        reply = b""
        while b"\r\n\r\n" not in reply:
            chunk = self.client.recv(1024)
            if not chunk:
                break
            reply += chunk
        return reply

    def finish(self):
        self.client.close()
        self.up_server_side.close()
        self.thread.join(5)
        self.up_proxy_side.close()
        assert not self.thread.is_alive()


class EgressTest(unittest.TestCase):
    def proxy(self, **kw):
        p = Proxy(**kw)
        self.addCleanup(p.finish)
        return p

    def test_unlisted_host_is_refused_before_any_resolution(self):
        p = self.proxy()
        self.assertTrue(p.connect(b"CONNECT www.example.org:443 HTTP/1.1\r\n\r\n").startswith(b"HTTP/1.1 403"))
        p.thread.join(5)
        self.assertEqual((p.resolver_calls, p.connector_calls), ([], []))

    def test_lookalike_hosts_are_refused(self):
        for host in (HOST + ".evil.example", HOST.upper(), "evil-" + HOST, HOST + "."):
            with self.subTest(host):
                p = Proxy()
                self.assertTrue(p.connect(f"CONNECT {host}:443 HTTP/1.1\r\n\r\n".encode()).startswith(b"HTTP/1.1 403"))
                p.finish()
                self.assertEqual(p.resolver_calls, [])

    def test_only_port_443(self):
        p = self.proxy()
        self.assertTrue(p.connect(f"CONNECT {HOST}:8443 HTTP/1.1\r\n\r\n".encode()).startswith(b"HTTP/1.1 403"))
        p.thread.join(5)
        self.assertEqual(p.resolver_calls, [])

    def test_not_a_connect_is_refused(self):
        p = self.proxy()
        self.assertTrue(p.connect(f"GET http://{HOST}/ HTTP/1.1\r\n\r\n".encode()).startswith(b"HTTP/1.1 403"))

    def test_with_nothing_allowed_everything_is_refused(self):
        p = self.proxy(allowed=frozenset())
        self.assertTrue(p.connect(f"CONNECT {HOST}:443 HTTP/1.1\r\n\r\n".encode()).startswith(b"HTTP/1.1 403"))

    def test_private_loopback_link_local_shared_and_documentation_resolutions_are_refused(self):
        for ip in ("10.1.2.3", "127.0.0.1", "169.254.169.254", "172.16.0.9", "192.168.1.1", SHARED, "0.0.0.0", "224.0.0.1",
                   "203.0.113.7"):
            with self.subTest(ip):
                p = Proxy(resolver=lambda host, port, ip=ip, **kw: [(2, 1, 6, "", (ip, 443))])
                self.assertTrue(p.connect(f"CONNECT {HOST}:443 HTTP/1.1\r\n\r\n".encode()).startswith(b"HTTP/1.1 403"))
                p.finish()
                self.assertEqual(p.connector_calls, [])

    def test_one_private_address_among_public_ones_refuses_all(self):
        mixed = lambda host, port, **kw: [(2, 1, 6, "", (PUBLIC, 443)), (2, 1, 6, "", ("10.0.0.1", 443))]  # noqa: E731
        p = Proxy(resolver=mixed)
        self.assertTrue(p.connect(f"CONNECT {HOST}:443 HTTP/1.1\r\n\r\n".encode()).startswith(b"HTTP/1.1 403"))
        p.finish()
        self.assertEqual(p.connector_calls, [])

    def test_no_a_record_is_refused(self):
        p = Proxy(resolver=lambda host, port, **kw: [])
        self.assertTrue(p.connect(f"CONNECT {HOST}:443 HTTP/1.1\r\n\r\n".encode()).startswith(b"HTTP/1.1 403"))
        p.finish()

    def test_sni_mismatch_is_refused_before_any_connection(self):
        p = Proxy()
        self.assertTrue(p.connect(f"CONNECT {HOST}:443 HTTP/1.1\r\n\r\n".encode()).startswith(b"HTTP/1.1 200"))
        p.client.sendall(client_hello("www.example.org"))
        self.assertEqual(p.client.recv(100), b"HTTP/1.1 403 Forbidden\r\n\r\n")
        p.finish()
        self.assertEqual(p.connector_calls, [])

    def test_another_allowed_host_in_the_sni_is_still_a_mismatch(self):
        other = sorted(ALLOWED - {HOST})[0]
        p = Proxy()
        p.connect(f"CONNECT {HOST}:443 HTTP/1.1\r\n\r\n".encode())
        p.client.sendall(client_hello(other))
        self.assertEqual(p.client.recv(100), b"HTTP/1.1 403 Forbidden\r\n\r\n")
        p.finish()
        self.assertEqual(p.connector_calls, [])

    def test_missing_sni_is_refused(self):
        p = Proxy()
        p.connect(f"CONNECT {HOST}:443 HTTP/1.1\r\n\r\n".encode())
        p.client.sendall(b"\x16\x03\x01\x00\x05\x01\x00\x00\x01\x00")
        p.client.recv(100)
        p.finish()
        self.assertEqual(p.connector_calls, [])

    def test_resolves_once_a_records_only_and_connects_to_the_checked_address(self):
        p = Proxy()
        self.assertTrue(p.connect(f"CONNECT {HOST}:443 HTTP/1.1\r\n\r\n".encode()).startswith(b"HTTP/1.1 200"))
        hello = client_hello(HOST)
        p.client.sendall(hello)
        self.assertEqual(p.up_server_side.recv(len(hello)), hello)  # forwarded unchanged, after the checks
        p.up_server_side.sendall(b"PONG")
        self.assertEqual(p.client.recv(10), b"PONG")
        p.client.sendall(b"secret-payload-ping")
        self.assertEqual(p.up_server_side.recv(100), b"secret-payload-ping")
        p.client.shutdown(socket.SHUT_WR)
        p.finish()
        self.assertEqual(len(p.resolver_calls), 1)
        host, port, kw = p.resolver_calls[0]
        self.assertEqual((host, port, kw["family"]), (HOST, 443, socket.AF_INET))
        self.assertEqual(p.connector_calls, [(PUBLIC, 443)])  # the address it checked, as a literal

    def test_logs_host_and_byte_counts_never_content(self):
        p = Proxy()
        p.connect(f"CONNECT {HOST}:443 HTTP/1.1\r\n\r\n".encode())
        p.client.sendall(client_hello(HOST))
        p.up_server_side.recv(4096)
        p.client.sendall(b"Authorization: Bearer sentinel-secret")
        p.up_server_side.recv(4096)
        p.up_server_side.close()
        p.finish()
        text = "\n".join(p.logs)
        self.assertIn(f"host={HOST}", text)
        self.assertRegex(text, r"up=\d+ down=\d+ seconds=")
        self.assertNotIn("sentinel", text)

    def test_refusal_logs_a_sanitised_host(self):
        p = Proxy()
        p.connect(b"CONNECT bad-host.example:443 HTTP/1.1\r\n\r\n")
        p.finish()
        self.assertIn("refused", p.logs[0])

    def test_sni_parser_reads_a_real_hello_and_survives_garbage(self):
        self.assertEqual(fo.sni_of(client_hello("Web.Example.com")), "web.example.com")
        for junk in (b"", b"\x16", b"\x16\x03\x01\x00\x10" + b"\x01" * 3, os.urandom(64), client_hello(HOST)[:30]):
            self.assertIsNone(fo.sni_of(junk))

    def test_public_v4_classification(self):
        self.assertTrue(fo.public_v4(PUBLIC))
        for bad in ("10.0.0.1", str(ipaddress.IPv4Address(0x64640001)), "::1", "2001:db8::1", "not-an-ip", "169.254.1.1",
                    "203.0.113.1"):
            self.assertFalse(fo.public_v4(bad), bad)

    def test_egress_main_reads_the_blocks_hosts_and_refuses_as_root_or_with_a_broken_catalog(self):
        with mock.patch("os.geteuid", return_value=0), mock.patch("sys.stderr", new_callable=io.StringIO):
            self.assertEqual(fo.egress_main(), 2)
        with tempfile.TemporaryDirectory() as tmp:
            (pathlib.Path(tmp) / "ops.json").write_text(json.dumps(fakes.catalog_dict(rollbacks=True)))
            with mock.patch("os.geteuid", return_value=1000), mock.patch("sys.stderr", new_callable=io.StringIO) as err, \
                    mock.patch.object(fo, "egress_serve") as serve:
                self.assertEqual(fo.egress_main(lib=tmp), 2)
            serve.assert_not_called()
            self.assertIn("rollbacks", err.getvalue())
            (pathlib.Path(tmp) / "ops.json").write_text(json.dumps(fakes.CATALOG))
            with mock.patch("os.geteuid", return_value=1000), mock.patch.object(fo, "egress_serve") as serve, \
                    mock.patch("socket.socket"), mock.patch("os.dup", return_value=9):
                self.assertEqual(fo.egress_main(lib=tmp), 0)
            self.assertEqual(serve.call_args.kwargs["allowed"], ALLOWED)


class HostNamesTest(unittest.TestCase):
    def test_an_egress_entry_must_be_a_name_never_an_address(self):
        for bad in ("203.0.113.5", "127.1", "0x7f.1", "Web.Example.com", "web.example.com.", "localhost", "a..b", "-a.example"):
            with self.subTest(bad):
                self.assertFalse(fo.host_name_ok(bad))
        for good in ("api.host.example", "web.example.com", "a-b.c-d.example"):
            self.assertTrue(fo.host_name_ok(good), good)


class ConnectionTest(unittest.TestCase):
    def test_refuses_a_host_off_the_list(self):
        for host in ("example.com", "localhost"):
            with self.subTest(host), self.assertRaises(fo.HostError):
                fo.EgressConnection(host, 5, allowed=ALLOWED)

    def test_is_https_on_443_with_verification_on(self):
        conn = fo.EgressConnection(HOST, 5, allowed=ALLOWED)
        self.assertIsInstance(conn, http.client.HTTPSConnection)
        self.assertEqual(conn.port, 443)
        self.assertTrue(conn._context.check_hostname)
        self.assertEqual(conn._context.verify_mode, ssl.CERT_REQUIRED)

    def test_sends_connect_to_the_socket_and_fails_closed_on_a_refusal(self):
        d = tempfile.mkdtemp()
        path = str(pathlib.Path(d) / "e.sock")
        srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        srv.bind(path)
        srv.listen(1)
        got = []

        def serve():
            c, _ = srv.accept()
            got.append(c.recv(1024))
            c.sendall(b"HTTP/1.1 403 Forbidden\r\n\r\n")
            c.close()
        t = threading.Thread(target=serve, daemon=True)
        t.start()
        conn = fo.EgressConnection(HOST, 5, allowed=ALLOWED, sock_path=path)
        with self.assertRaises(fo.HostError):
            conn.connect()
        t.join(5)
        srv.close()
        self.assertEqual(got[0], f"CONNECT {HOST}:443 HTTP/1.1\r\nHost: {HOST}:443\r\n\r\n".encode())

    def test_no_proxy_variables_are_consulted(self):
        self.assertNotIn("getproxies", fo.__dict__)
        self.assertNotIn("proxy", fo.EgressConnection.__init__.__code__.co_names)

    def test_the_source_names_no_host_but_githubs(self):
        import re
        src = pathlib.Path(fo.__file__).read_text()
        self.assertEqual(set(re.findall(r"https?://[A-Za-z0-9.-]+", src)), {"https://api.github.com", "https://github.com"})
        self.assertEqual(set(re.findall(r"git@[A-Za-z0-9.-]+:", src)), {"git@github.com:"})


if __name__ == "__main__":
    unittest.main()
