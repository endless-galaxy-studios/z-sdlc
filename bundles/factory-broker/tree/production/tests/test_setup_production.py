"""host/setup-production.sh, the factory-broker bundle's production tier setup (process/factory-broker.md).

The script needs root, systemd and nft, so these tests check:
- what it generates: --render writes every unit, the nft table and the sudoers file under a directory;
- the names it resolves (--print-settings), for a host's first tier and a later one, side by side;
- the functions that decide something, run for real against scratch files and repositories: the settings read as text,
  the tier record, the names in use, other tiers found on the host, the request client's replacement, the staging, the
  installed files, the broker block, the runner pin, the token file, the preflight;
- what its text promises: nothing restarts nftables.service, nothing of the checkout is trusted, the sandbox the broker
  uses, the acceptance checks.
Run by CI: python3 -I -m unittest discover -s .github/factory/production/tests"""

import importlib
import ipaddress
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

TESTS = pathlib.Path(__file__).resolve().parent
PRODUCTION = TESTS.parent
FACTORY = PRODUCTION.parent
SCRIPT = FACTORY / "host" / "setup-production.sh"
SETUP_SH = FACTORY / "host" / "setup.sh"
BROKER = PRODUCTION / "factory_op.py"
TEXT = SCRIPT.read_text()
OWNER = "octo-org/example"
NOT_ROOT = os.geteuid() != 0
OVERRIDES = ("TIER_OWNER", "PRODUCTION_CONF", "OPS_JSON", "FACTORY_JSON", "FACTORY_HOST_ROOT", "REPLACE_CLIENT")


def assignment(name):
    """A top-level NAME=value or NAME="value" line's value."""
    m = re.search(rf'^{name}=(?:"([^"]*)"|(\S*))$', TEXT, re.M)
    assert m, name
    return m.group(1) if m.group(1) is not None else m.group(2)


CONF_KEYS = tuple(assignment("CONF_KEYS").split())


def function(name):
    """One function of the script, as written there."""
    m = re.search(rf"^{name}\(\) \{{[^\n]*\n.*?^\}}\n", TEXT, re.S | re.M)
    assert m, name
    return m.group(0)


def code():
    """The script without comment-only lines, so prose can name things the code must not do."""
    return "\n".join(ln for ln in TEXT.splitlines() if not ln.lstrip().startswith("#"))


def gates():
    sys.path.insert(0, str(FACTORY))
    try:
        return importlib.import_module("gates")
    finally:
        sys.path.remove(str(FACTORY))


def broker():
    """The bundle's broker, imported as its own tests import it."""
    for p in (str(PRODUCTION), str(FACTORY)):
        if p not in sys.path:
            sys.path.insert(0, p)
    return importlib.import_module("factory_op")


def needs_broker(test):
    return unittest.skipUnless(BROKER.exists(), "the broker (production/factory_op.py) isn't in this tree yet")(test)


def conf_text(**settings):
    lines = ["# a scratch tier's production.conf"]
    for key, value in settings.items():
        lines.append(f'{key}="{value}"' if " " in value else f"{key}={value}")
    return "\n".join(lines) + "\n"


# A factory.json with what setup reads of it, so no test depends on the project's (C1: a project fills its own in).
FACTORY_JSON = {"runners": {"production": "factory-prod"}, "environments": {"production": "factory-production"},
                "release": {"branch": "release/production"}}


def catalog(health=600, capture=840, drift=400, egress=("api.host.example", "status.host.example"), secrets=None,
            python="3.8"):
    """A catalog with the parts of the broker block setup reads."""
    if secrets is None:
        secrets = {"token": {"file": "api.token", "by": "cd", "hex": False},
                   "key": {"file": "state.key", "by": "setup", "hex": True}}
    read = {"kind": "read", "summary": "x", "outputs": {}}
    return {"version": 1,
            "operations": {"health": {**read, "timeout_s": health}, "capture-state": {**read, "timeout_s": capture}},
            "broker": {"egress": list(egress), "secrets": secrets, "python": python,
                       "internal_ops": {"drift-scan": {"timeout_s": drift}, "host-check": {"timeout_s": 60}}}}


class Scratch:
    """A scratch tier: its production.conf, ops.json and factory.json, and the script run against them (never as root).
    Nothing of the project's own settings is read: a project that filled in its seeds runs these tests unchanged."""

    def __init__(self, root, instance="", host_root=None, ops=None, factory_json=None, owner=OWNER, **conf):
        self.root = pathlib.Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        settings = {"PROD_INSTANCE": instance, "AGENT_USER": "agent", "PROD_RUNNER_NAME": f"host1-production{instance}",
                    "PROBE_PORTS": "22 8080", **conf}
        self.conf = self.root / "production.conf"
        self.conf.write_text(conf_text(**{k: v for k, v in settings.items() if v is not None}))
        self.ops = self.root / "ops.json"
        self.ops.write_text(json.dumps(ops or catalog()))
        self.host_root = host_root
        if factory_json is None:
            factory_json = self.root / "factory.json"
            factory_json.write_text(json.dumps(FACTORY_JSON))
        self.factory_json = factory_json
        self.owner = owner

    def run(self, *args, **env):
        e = {k: v for k, v in os.environ.items() if k not in CONF_KEYS + OVERRIDES}
        e.update(PRODUCTION_CONF=str(self.conf), OPS_JSON=str(self.ops), TIER_OWNER=self.owner)
        if self.host_root:
            e["FACTORY_HOST_ROOT"] = str(self.host_root)
        if self.factory_json:
            e["FACTORY_JSON"] = str(self.factory_json)
        e.update(env)
        return subprocess.run(["bash", str(SCRIPT), *args], capture_output=True, text=True, env=e)

    def settings(self, **env):
        r = self.run("--print-settings", **env)
        assert r.returncode == 0, r.stderr
        return dict(line.split("=", 1) for line in r.stdout.splitlines())

    def step_props(self):
        r = self.run("--print-step-props")
        assert r.returncode == 0, r.stderr
        props = {}
        for line in r.stdout.splitlines():
            assert line.startswith("-p "), line
            k, v = line[3:].split("=", 1)
            props[k] = v
        return props

    def render(self, dest):
        r = self.run("--render", str(dest), RENDER_RUID="901", RENDER_OPID="902", RENDER_EID="903")
        assert r.returncode == 0, r.stderr
        return pathlib.Path(dest)


def expected_names(instance, repo=OWNER):
    """The scheme every tier's names follow, from its instance alone (empty for the host's first tier)."""
    dash = f"-{instance}" if instance else ""
    tier = "factory-prod" + dash
    return {
        "INSTANCE": instance, "REPO": repo, "TIER_NAME": tier,
        "RUNNER_USER": tier, "OP_USER": f"{tier}-op", "EGRESS_USER": f"{tier}-egress",
        "NFT_TABLE": "factory_prod" + (f"_{instance}" if instance else ""),
        "NFT_FILE": f"/etc/factory-runner/prod{dash}-firewall.nft",
        "FW_UNIT": f"{tier}-firewall", "RUNNER_UNIT": f"{tier}-runner",
        "BROKER_UNIT": f"factory-op{dash}", "EGRESS_UNIT": f"factory-op{dash}-egress",
        "DRIFT_UNIT": f"factory-op{dash}-drift", "STEP_UNIT": f"factory-op{dash}-step",
        "LIB": f"/usr/local/lib/{tier}", "ETC": f"/etc/{tier}", "STATE": f"/var/lib/{tier}",
        "CLONE_BASE": f"/var/lib/{tier}-clone", "CLONE": f"/var/lib/{tier}-clone/{repo.split('/')[1]}.git",
        "LOGS": f"/var/log/{tier}", "RUN": f"/run/{tier}", "BROKER_CMD": f"/usr/local/sbin/factory-op{dash}",
        "SUDOERS_NAME": f"91-agent-readonly{dash}", "TIER_RECORD": f"/etc/{tier}/tier",
        "CLIENT": "/usr/local/bin/factory-op-request", "RUNNER_URL": "https://github.com/" + repo.split("/")[0],
    }


def expected_files(instance):
    n = expected_names(instance)
    unit = "etc/systemd/system/"
    return {
        n["NFT_FILE"].lstrip("/"), f"etc/polkit-1/rules.d/60-{n['TIER_NAME']}.rules",
        f"etc/sudoers.d/{n['SUDOERS_NAME']}", f"etc/tmpfiles.d/{n['TIER_NAME']}.conf",
        f"{unit}{n['DRIFT_UNIT']}.service", f"{unit}{n['DRIFT_UNIT']}.timer",
        f"{unit}{n['EGRESS_UNIT']}.socket", f"{unit}{n['EGRESS_UNIT']}@.service",
        f"{unit}{n['BROKER_UNIT']}.socket", f"{unit}{n['BROKER_UNIT']}@.service",
        f"{unit}{n['FW_UNIT']}-reapply.service", f"{unit}{n['FW_UNIT']}.service", f"{unit}{n['RUNNER_UNIT']}.service",
        f"{unit}nftables.service.d/{n['FW_UNIT']}.conf", f"{unit}tailscaled.service.d/{n['TIER_NAME']}.conf",
        n["BROKER_CMD"].lstrip("/"),
    }


def bash(script, env=None, path=None):
    """A piece of the script, with its die() and constants, under set -euo pipefail."""
    prelude = ('die() { printf "ERROR: %s\\n" "$*" >&2; exit 1; }\n'
               + "".join(f'{n}="{assignment(n)}"\n' for n in ("CONF_KEYS", "RESERVED_INSTANCES", "BROKER_MODULES", "TIER_FILES",
                                                               "DRIFT_LOCK_WAIT_S", "FETCH_TIMEOUT_S", "STEP_KILL_MARGIN_S",
                                                               "GIT_CALLS_BUDGET_S", "SYSTEMD_FLOOR")))
    e = {"PATH": path or os.environ["PATH"], "HOME": "/nonexistent", **(env or {})}
    return subprocess.run(["bash", "-c", "set -euo pipefail\n" + prelude + script], capture_output=True, text=True, env=e)


# root's `install -o root -g root`, as the plain install a test user may run
INSTALL_STUB = 'install() { local a=(); while (($#)); do case $1 in -o|-g) shift 2 ;; *) a+=("$1"); shift ;; esac; done; command install "${a[@]}"; }\n'


def git(*args, cwd, env=None, data=None):
    """git with no user or system config (no signing), as the tests' scratch repositories need."""
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", "-c", "commit.gpgsign=false",
                           "-c", "tag.gpgsign=false", *args], cwd=cwd, capture_output=True, text=True, check=True, input=data,
                          env={**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1", **(env or {})}).stdout


# ---- what it generates -------------------------------------------------------------------------------------------

@unittest.skipUnless(NOT_ROOT, "the print and render modes refuse root")
class RenderedBase:
    INSTANCE = ""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.scratch = Scratch(pathlib.Path(cls.tmp.name) / "conf", cls.INSTANCE)
        cls.root = cls.scratch.render(pathlib.Path(cls.tmp.name) / "out")
        cls.n = expected_names(cls.INSTANCE)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def read(self, rel):
        return (self.root / rel.lstrip("/")).read_text()

    def unit(self, name):
        return self.read(f"/etc/systemd/system/{name}")

    def blocked4(self):
        nft = self.read(self.n["NFT_FILE"])
        m = re.search(r"set blocked4 \{.*?elements = \{(.*?)\}", nft, re.S)
        self.assertIsNotNone(m, "the firewall file has no blocked4 elements")
        return [ipaddress.ip_network(e.strip()) for e in m.group(1).split(",") if e.strip()]

    def test_the_files_generated(self):
        got = {str(p.relative_to(self.root)) for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(got, expected_files(self.INSTANCE))

    def test_the_blocked_set_covers_the_reserved_ranges_the_broker_relies_on(self):
        nets = self.blocked4()
        for net in ("192.0.0.0/24", "198.18.0.0/15", "240.0.0.0/4", "255.255.255.255/32", "100.64.0.0/10", "169.254.0.0/16",
                    "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "127.0.0.0/8"):
            self.assertTrue(any(ipaddress.ip_network(net).subnet_of(n) for n in nets), f"{net} isn't blocked")

    def test_the_blocked_set_has_no_overlapping_ranges(self):
        # An interval set without auto-merge refuses overlapping elements ("conflicting intervals specified"), so the
        # firewall unit would fail and setup stop at step 2.
        nets = self.blocked4()
        for i, a in enumerate(nets):
            for b in nets[i + 1:]:
                self.assertFalse(a.overlaps(b), f"{a} and {b} overlap")

    def test_the_nft_table(self):
        nft, table = self.read(self.n["NFT_FILE"]), self.n["NFT_TABLE"]
        self.assertIn(f"table inet {table} {{", nft)
        self.assertIn(f"delete table inet {table}\n", nft)
        self.assertNotIn("flush ruleset", nft)
        self.assertEqual(re.findall(r"^(?:table|delete table) inet (\w+)", nft, re.M), [table] * 3)
        for uid, chain in ((901, "runner_out"), (902, "operator_out"), (903, "egress_out")):
            self.assertIn(f"meta skuid {uid} jump {chain}", nft)
        chains = dict(re.findall(r"chain (\w+_out) \{\n(.*?)\n  \}", nft, re.S))
        self.assertEqual(set(chains), {"runner_out", "operator_out", "egress_out"})
        self.assertNotIn("accept", chains["operator_out"])
        self.assertIn("reject", chains["operator_out"])
        for rule in ("th dport 53 accept", 'oifname "lo" counter reject', "ip daddr @blocked4 counter reject",
                     "meta nfproto ipv6 counter reject"):
            self.assertIn(rule, chains["runner_out"])
        egress = chains["egress_out"]
        self.assertIn("ip daddr 127.0.0.53", egress)
        self.assertIn("ip daddr != @blocked4 tcp dport 443 accept", egress)
        self.assertIn("meta nfproto ipv6 counter reject", egress)
        self.assertEqual(egress.strip().splitlines()[-1].strip(), 'counter reject comment "egress: 443 to public IPv4 only"')
        self.assertEqual(len(re.findall(r"\baccept\b", egress)), 2)

    def test_the_firewall_units_load_the_table_and_never_touch_nftables_service(self):
        nft_file, fw = self.n["NFT_FILE"], self.n["FW_UNIT"]
        unit = self.unit(f"{fw}.service")
        self.assertIn("ReloadPropagatedFrom=nftables.service", unit)
        self.assertIn("After=nftables.service", unit)
        self.assertIn(f"ExecStart=/usr/sbin/nft -f {nft_file}\n", unit)
        self.assertIn(f"ExecReload=/usr/sbin/nft -f {nft_file}\n", unit)
        self.assertIn(f"ExecStop=/usr/sbin/nft delete table inet {self.n['NFT_TABLE']}\n", unit)
        reapply = self.unit(f"{fw}-reapply.service")
        self.assertIn("WantedBy=nftables.service", reapply)
        self.assertIn(f"ExecStart=/usr/sbin/nft -f {nft_file}\n", reapply)
        dropin = self.read(f"/etc/systemd/system/nftables.service.d/{fw}.conf")
        self.assertIn(f"ExecStopPost=-/usr/sbin/nft -f {nft_file}\n", dropin)
        for text in (unit, reapply, dropin):
            self.assertNotRegex(text, r"(?m)^(?:ExecStart|ExecReload|ExecStop|ExecStopPost)=.*nftables")
            self.assertNotIn("PartOf=nftables", text)
            self.assertNotIn("BindsTo=nftables", text)

    def test_the_egress_proxy_unit(self):
        n = self.n
        sock = self.unit(f"{n['EGRESS_UNIT']}.socket")
        self.assertIn(f"ListenStream={n['RUN']}/egress.sock\n", sock)
        self.assertIn(f"SocketGroup={n['OP_USER']}\n", sock)
        self.assertIn("SocketMode=0660", sock)
        self.assertIn("Accept=yes", sock)
        svc = self.unit(f"{n['EGRESS_UNIT']}@.service")
        self.assertIn(f"User={n['EGRESS_USER']}\n", svc)
        self.assertIn(f"ExecStart=/usr/bin/python3 -I {n['LIB']}/factory_op.py egress\n", svc)
        for setting in ("NoNewPrivileges=yes", "PrivateTmp=yes", "ProtectSystem=strict", "ProtectHome=yes",
                        "RestrictAddressFamilies=AF_INET AF_UNIX", "CapabilityBoundingSet=\n"):
            self.assertIn(setting, svc)
        hidden = re.search(r"InaccessiblePaths=(.*)", svc).group(1).split()
        for path in ("/run/tailscale", "/var/run/tailscale", "/run/dbus/system_bus_socket", n["STATE"], n["LOGS"]):
            self.assertIn("-" + path, hidden)
        self.assertNotIn("AF_INET6", svc)

    def test_the_broker_units(self):
        n = self.n
        sock = self.unit(f"{n['BROKER_UNIT']}.socket")
        self.assertIn(f"ListenStream={n['RUN']}/op.sock\n", sock)
        self.assertIn(f"SocketGroup={n['RUNNER_USER']}\n", sock)
        self.assertIn("SocketMode=0660", sock)
        svc = self.unit(f"{n['BROKER_UNIT']}@.service")
        self.assertIn(f"ExecStart=/usr/bin/python3 -I {n['LIB']}/factory_op.py serve\n", svc)
        self.assertIn("User=root", svc)
        self.assertIn(f"{n['LIB']}/factory_op.py drift-check\n", self.unit(f"{n['DRIFT_UNIT']}.service"))
        timer = self.unit(f"{n['DRIFT_UNIT']}.timer")
        self.assertIn("OnCalendar=*-*-* 12:00:00 UTC", timer)
        self.assertIn("Persistent=true", timer)

    def test_the_broker_units_set_their_own_path(self):
        for unit in (f"{self.n['BROKER_UNIT']}@.service", f"{self.n['EGRESS_UNIT']}@.service", f"{self.n['DRIFT_UNIT']}.service"):
            text = self.unit(unit)
            self.assertIn("Environment=PATH=/usr/sbin:/usr/bin:/sbin:/bin\n", text, unit)
            self.assertIn("Environment=LANG=C.UTF-8\n", text, unit)
            self.assertNotIn("GIT_SSH_COMMAND", text, unit)

    def test_the_command_runs_the_broker_with_a_fixed_environment(self):
        lib = self.n["LIB"]
        wrapper = self.read(self.n["BROKER_CMD"])
        self.assertEqual(wrapper.splitlines()[0], "#!/bin/sh")
        self.assertIn("exec /usr/bin/env -i PATH=/usr/sbin:/usr/bin:/sbin:/bin LANG=C.UTF-8 ", wrapper)
        self.assertIn(f'/usr/bin/python3 -I {lib}/factory_op.py "$@"', wrapper)
        # Run it with the broker replaced by `env`: only the fixed variables (and SUDO_USER, which the ledger records) arrive.
        with tempfile.TemporaryDirectory() as scratch:
            probe = pathlib.Path(scratch) / "wrapper-probe.sh"
            probe.write_text(wrapper.replace(f"/usr/bin/python3 -I {lib}/factory_op.py", "/usr/bin/env"))
            for sudo_user, extra in (("alice", {"SUDO_USER=alice"}), ("", set())):
                env = {"PATH": "/tmp/evil:/usr/bin", "PYTHONPATH": "/tmp/evil", "LD_PRELOAD": "/tmp/evil.so", "HOME": "/tmp/evil"}
                if sudo_user:
                    env["SUDO_USER"] = sudo_user
                r = subprocess.run(["/bin/sh", str(probe)], capture_output=True, text=True, env=env)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertEqual(set(r.stdout.split()), {"PATH=/usr/sbin:/usr/bin:/sbin:/bin", "LANG=C.UTF-8"} | extra)

    def test_the_runner_unit(self):
        n = self.n
        runner = self.unit(f"{n['RUNNER_UNIT']}.service")
        self.assertIn(f"User={n['RUNNER_USER']}\n", runner)
        self.assertIn(f"Requires={n['FW_UNIT']}.service {n['BROKER_UNIT']}.socket\n", runner)
        for setting in ("NoNewPrivileges=yes", "ProtectHome=yes", "ProtectSystem=full"):
            self.assertIn(setting, runner)
        hidden = re.search(r"InaccessiblePaths=(.*)", runner).group(1).split()
        for path in ("/run/tailscale", "/var/run/tailscale", "/run/dbus/system_bus_socket"):
            self.assertIn("-" + path, hidden)
        self.assertNotIn("-" + n["RUN"], hidden)  # its own broker socket is the one it uses

    def test_the_tmpfiles_directory_for_steps(self):
        run = self.n["RUN"]
        self.assertEqual(self.read(f"/etc/tmpfiles.d/{self.n['TIER_NAME']}.conf").splitlines(),
                         [f"d {run} 0755 root root -", f"d {run}/steps 0711 root root -"])

    def test_the_sudoers_file(self):
        cmd, state = self.n["BROKER_CMD"], self.n["STATE"]
        text = self.read(f"/etc/sudoers.d/{self.n['SUDOERS_NAME']}")
        lines = [ln for ln in text.splitlines() if ln and not ln.startswith("#")]
        self.assertEqual(lines, [
            f"Defaults!{cmd} timestamp_timeout=0",
            f"agent ALL=(root) NOPASSWD: {cmd} check",
            f"agent ALL=(root) NOPASSWD: {cmd} health",
            f"agent ALL=(root) NOPASSWD: /usr/bin/cat {state}/ledger.jsonl",
        ])
        self.assertNotIn("*", "\n".join(lines))
        for word in ("baseline", "resolve", "diagnose", "fetch"):
            self.assertNotIn(word, "\n".join(lines))
        if shutil.which("visudo"):
            with tempfile.NamedTemporaryFile("w", suffix=".sudoers") as f:
                f.write(text)
                f.flush()
                r = subprocess.run(["visudo", "-cf", f.name], capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_tailscale_and_logind_are_denied_to_all_three_users(self):
        n = self.n
        ts = self.read(f"/etc/systemd/system/tailscaled.service.d/{n['TIER_NAME']}.conf")
        pk = self.read(f"/etc/polkit-1/rules.d/60-{n['TIER_NAME']}.rules")
        for user in (n["RUNNER_USER"], n["OP_USER"], n["EGRESS_USER"]):
            self.assertIn(f"u:{user}:---", ts)
            self.assertIn(f'"{user}"', pk)


class RenderedFirstTier(RenderedBase, unittest.TestCase):
    INSTANCE = ""


class RenderedLaterTier(RenderedBase, unittest.TestCase):
    INSTANCE = "b2"


@unittest.skipUnless(NOT_ROOT, "the print and render modes refuse root")
class TwoTiers(unittest.TestCase):
    """The host's first tier and a later one, each set up with the other on the host: no name in common, and each
    hides the other's directories."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        t = pathlib.Path(self.tmp.name)
        host = self.host = t / "host"
        for d in ("etc/factory-prod", "run/factory-prod", "var/lib/factory-prod", "var/lib/factory-prod-clone",
                  "etc/factory-prod-b2", "run/factory-prod-b2", "var/lib/factory-prod-b2", "var/lib/factory-prod-b2-clone",
                  # not tiers: a malformed name, a reserved instance, a prefix match, /etc without a config
                  "etc/factory-prod-Bad", "run/factory-prod-op", "run/factory-prodx", "etc/factory-runner", "etc/factory-prod-c3"):
            (host / d).mkdir(parents=True)
        (host / "etc/factory-prod-Bad/config.json").write_text("{}")
        (host / "etc/factory-prod/config.json").write_text(json.dumps({"deploy_dir": "/srv/first"}))
        (host / "etc/factory-prod-b2/config.json").write_text(json.dumps({"deploy_dir": "/srv/second/app"}))
        self.first = Scratch(t / "first", "", host_root=host)
        self.later = Scratch(t / "later", "b2", host_root=host, owner="octo-org/other")  # another project's tier

    def test_each_finds_the_other_and_nothing_else(self):
        self.assertEqual(self.first.settings()["OTHER_TIERS"], "factory-prod-b2")
        self.assertEqual(self.later.settings()["OTHER_TIERS"], "factory-prod")

    def test_no_name_in_common(self):
        a, b = self.first.settings(), self.later.settings()
        # Shared on purpose: the one request client, the organization, the agent login, the factory's runner label,
        # pin and environment name; a runner group may be too, when production.conf names one.
        shared = {"CLIENT", "RUNNER_URL", "AGENT_USER", "LAN_DNS", "PROBE_PORTS", "PROD_HOME_BASE", "RUNNER_LABELS",
                  "RUNNER_VERSION", "PROD_ENVIRONMENT", "OTHER_TIERS"}
        for key in set(a) - shared:
            self.assertNotEqual(a[key], b[key], key)
        names = lambda s: {v for k, v in s.items() if k not in shared}  # noqa: E731
        self.assertEqual(names(a) & names(b), set())
        self.assertEqual({k: a[k] for k in expected_names("")}, expected_names(""))
        self.assertEqual({k: b[k] for k in expected_names("b2", "octo-org/other")}, expected_names("b2", "octo-org/other"))

    def test_the_generated_files_are_disjoint(self):
        def files(scratch, dest):
            root = scratch.render(pathlib.Path(self.tmp.name) / dest)
            return {str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()}
        a, b = files(self.first, "ra"), files(self.later, "rb")
        self.assertEqual((a, b), (expected_files(""), expected_files("b2")))
        self.assertEqual(a & b, set())

    def assertHides(self, scratch, others, deploy, own):
        hidden = scratch.step_props()["InaccessiblePaths"].split()
        for path in others + deploy:
            self.assertIn("-" + path, hidden)
        for path in own:
            self.assertNotIn("-" + path, hidden)
        for decoy in ("/run/factory-prod-op", "/run/factory-prodx", "/run/factory-prod-Bad", "/run/factory-prod-c3",
                      "/var/lib/factory-prod-clone-clone"):
            self.assertNotIn("-" + decoy, hidden)
        root = scratch.render(pathlib.Path(self.tmp.name) / f"render-{id(scratch)}")
        n = expected_names("b2" if scratch is self.later else "")
        egress = re.search(r"InaccessiblePaths=(.*)", (root / f"etc/systemd/system/{n['EGRESS_UNIT']}@.service").read_text())
        for path in others + deploy:
            self.assertIn("-" + path, egress.group(1).split())
        runner = re.search(r"InaccessiblePaths=(.*)", (root / f"etc/systemd/system/{n['RUNNER_UNIT']}.service").read_text())
        for path in others + deploy:  # the other tier's broker socket among them
            self.assertIn("-" + path, runner.group(1).split())
        self.assertNotIn("-" + own[0], runner.group(1).split())

    @staticmethod
    def dirs(tier):
        return [f"/run/{tier}", f"/var/lib/{tier}", f"/var/log/{tier}", f"/etc/{tier}", f"/var/lib/{tier}-clone",
                f"/usr/local/lib/{tier}"]

    def test_each_hides_the_others_directories_and_every_deploy_directory(self):
        self.assertHides(self.first, self.dirs("factory-prod-b2"), ["/srv/second/app"], ["/run/factory-prod"])
        self.assertHides(self.later, self.dirs("factory-prod"), ["/srv/first"], ["/run/factory-prod-b2"])

    @needs_broker
    def test_the_hidden_paths_are_the_brokers_in_its_order(self):
        """The acceptance probe's sandbox hides what the broker's own steps hide, on the same host."""
        fo = broker()
        for scratch in (self.first, self.later):
            with self.subTest(tier=scratch.settings()["TIER_NAME"]):
                s = scratch.settings()
                cfg = {"ledger": s["STATE"] + "/ledger.jsonl", "log_dir": s["LOGS"]}
                self.assertEqual(scratch.step_props()["InaccessiblePaths"], fo.hidden_paths(cfg, s["TIER_NAME"], self.host))
                self.assertEqual(s["OTHER_TIERS"].split(), fo.other_tiers(s["TIER_NAME"], self.host))

    def test_a_deploy_directory_that_would_be_a_directive_is_refused(self):
        for bad in ("/srv/x\nExecStartPre=+/bin/sh", "/srv/a b", "relative", "/srv/../etc", "/srv/%h"):
            with self.subTest(bad=bad):
                (self.host / "etc/factory-prod-b2/config.json").write_text(json.dumps({"deploy_dir": bad}))
                r = self.first.run("--render", str(pathlib.Path(self.tmp.name) / "bad"))
                self.assertEqual(r.returncode, 1)
                self.assertIn("deploy_dir", r.stderr)
                self.assertFalse((pathlib.Path(self.tmp.name) / "bad").exists())


# ---- names and settings ----------------------------------------------------------------------------------------

@unittest.skipUnless(NOT_ROOT, "the print and render modes refuse root")
class Names(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = pathlib.Path(self.tmp.name)

    def test_every_name_of_the_first_tier_and_a_later_one(self):
        for instance in ("", "acme", "b2", "7x"):
            with self.subTest(instance=instance):
                s = Scratch(self.dir / (instance or "first"), instance).settings()
                self.assertEqual({k: s[k] for k in expected_names(instance)}, expected_names(instance))
                self.assertEqual(s["OTHER_TIERS"], "")

    @needs_broker
    def test_the_names_are_the_brokers(self):
        fo = broker()
        self.assertTrue(hasattr(fo, "tier_names"), "the broker must derive a tier's names (tier_names) as setup does")
        pairs = {"runner_user": "RUNNER_USER", "operator_user": "OP_USER", "egress_user": "EGRESS_USER", "lib_dir": "LIB",
                 "etc_dir": "ETC", "state_dir": "STATE", "log_dir": "LOGS", "run_dir": "RUN", "clone_base": "CLONE_BASE",
                 "command_path": "BROKER_CMD", "broker_unit": "BROKER_UNIT", "egress_unit": "EGRESS_UNIT",
                 "drift_unit": "DRIFT_UNIT", "nft_table": "NFT_TABLE", "firewall_unit": "FW_UNIT",
                 "runner_unit": "RUNNER_UNIT", "instance": "INSTANCE"}
        for instance in ("", "b2"):
            with self.subTest(instance=instance):
                s = Scratch(self.dir / (instance or "first"), instance).settings()
                names = fo.tier_names(s["TIER_NAME"])
                for key, setting in pairs.items():
                    self.assertEqual(names[key], s[setting], key)
                self.assertEqual(names["unit_prefix"], s["STEP_UNIT"] + "-")
                self.assertEqual(names["sudoers"], "/etc/sudoers.d/" + s["SUDOERS_NAME"])
        # Both refuse the same instances, so setup never makes a tier the broker won't run as, nor misses one it would.
        setup_reserved = set(assignment("RESERVED_INSTANCES").split())
        self.assertEqual(setup_reserved, set(fo.RESERVED_INSTANCES))

    def test_a_reserved_or_malformed_instance_is_refused(self):
        for instance in assignment("RESERVED_INSTANCES").split() + ["Acme", "a-b", "a_b", "abcdefghijklm", "a.b"]:
            with self.subTest(instance=instance):
                r = Scratch(self.dir / "bad", instance).run("--print-settings")
                self.assertEqual(r.returncode, 1, r.stdout)
                self.assertIn("PROD_INSTANCE", r.stderr)

    def test_the_reserved_words_are_exactly_the_first_tiers_name_endings(self):
        # Each derived name is a tier name plus one of these endings; an instance equal to one would give a later tier
        # the first tier's operator, egress user, clone directory, units or step units.
        first = expected_names("")
        endings = set()
        for value in first.values():
            for prefix in ("factory-prod-", "/var/lib/factory-prod-", "factory-op-"):
                if value.startswith(prefix) and "-" not in value[len(prefix):] and "/" not in value[len(prefix):]:
                    endings.add(value[len(prefix):])
        self.assertEqual(endings, set(assignment("RESERVED_INSTANCES").split()))

    def test_the_agent_login_has_no_default(self):
        r = Scratch(self.dir / "noagent", AGENT_USER=None).run("--print-settings")
        self.assertEqual(r.returncode, 1)
        self.assertIn("AGENT_USER is required", r.stderr)
        self.assertNotRegex(code(), r"AGENT_USER=\$\{AGENT_USER:-")

    def test_a_conf_that_sets_nothing_is_refused_until_it_names_the_agent_login(self):
        """Changed for C1: a scratch file in the seed's shape (every setting there, commented out or empty), never the
        project's own production.conf, which it fills in. That the bundle's seed sets nothing is z-sdlc's to test."""
        text = "# a tier's settings, as seeded\nPROD_INSTANCE=\n" + "".join(f"#{k}=\n" for k in CONF_KEYS if k != "PROD_INSTANCE")
        conf = self.dir / "seed-shaped.conf"
        conf.write_text(text)
        r = bash(function("conf_read") + f"conf_read {conf}\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(dict(line.split("=", 1) for line in r.stdout.splitlines()), {k: "" for k in CONF_KEYS})
        s = Scratch(self.dir / "seed")
        s.conf.write_text(text)
        self.assertIn("AGENT_USER is required", s.run("--print-settings").stderr)

    def test_a_setting_in_the_environment_is_refused_not_ignored(self):
        for key in CONF_KEYS:
            with self.subTest(key=key):
                r = Scratch(self.dir / "env").run("--print-settings", **{key: "x"})
                self.assertEqual(r.returncode, 1)
                self.assertIn(f"{key} is a production.conf setting", r.stderr)

    def test_the_repository_is_needed_and_comes_from_the_operator_or_the_record(self):
        s = Scratch(self.dir / "repo")
        r = s.run("--print-settings", TIER_OWNER="")
        self.assertEqual(r.returncode, 1)
        self.assertIn("no repository owns the production tier factory-prod yet", r.stderr)
        host = self.dir / "host"
        (host / "etc/factory-prod").mkdir(parents=True)
        (host / "etc/factory-prod/tier").write_text("octo-org/recorded\n")
        s.host_root = host
        self.assertEqual(s.settings(TIER_OWNER="")["REPO"], "octo-org/recorded")
        r = s.run("--print-settings")  # TIER_OWNER=octo-org/example against the record
        self.assertEqual(r.returncode, 1)
        self.assertIn("is set up from octo-org/recorded", r.stderr)

    def test_the_runner_group_and_label_are_where_bootstrap_reads_them(self):
        # Changed for C1: the test's own factory.json (FACTORY_JSON), never the project's, which may set its own group.
        cfg = json.loads(json.dumps(FACTORY_JSON))
        (self.dir / "factory.json").write_text(json.dumps(cfg))
        s = Scratch(self.dir / "group", factory_json=self.dir / "factory.json")
        self.assertEqual(s.settings()["RUNNER_GROUP"], "factory-pool-example-prod")
        self.assertEqual(s.settings()["RUNNER_LABELS"], cfg["runners"]["production"])
        # bootstrap.py's own convention, the group it checks.
        boot = (FACTORY / "bootstrap.py").read_text()
        self.assertIn('groups.get("production") or f"factory-pool-{self.name}-prod"', boot)
        cfg["runners"]["groups"] = {"production": "prod-pool"}
        cfg["runners"]["production"] = "factory-prod-b"
        (self.dir / "factory.json").write_text(json.dumps(cfg))
        s.factory_json = self.dir / "factory.json"
        self.assertEqual((s.settings()["RUNNER_GROUP"], s.settings()["RUNNER_LABELS"]), ("prod-pool", "factory-prod-b"))
        s2 = Scratch(self.dir / "group2", RUNNER_GROUP="own-pool", factory_json=self.dir / "factory.json")
        self.assertEqual(s2.settings()["RUNNER_GROUP"], "own-pool")
        cfg["runners"]["production"] = "self-hosted,linux"
        (self.dir / "factory.json").write_text(json.dumps(cfg))
        r = s.run("--print-settings")
        self.assertEqual(r.returncode, 1)
        self.assertIn("runners.production must name a runner label of the production tier's own", r.stderr)


class ConfText(unittest.TestCase):
    """production.conf is read as text, never run."""

    def read(self, text):
        with tempfile.TemporaryDirectory() as tmp:
            conf = pathlib.Path(tmp) / "production.conf"
            conf.write_text(text)
            return bash(function("conf_read") + f"conf_read {conf}\n")

    def test_what_it_reads(self):
        r = self.read('# c\n\nPROD_INSTANCE=acme\nexport AGENT_USER="agent"  # the login\nPROBE_PORTS="22  8443"\n'
                      "PROD_RUNNER_NAME='host1-prod'\nLAN_DNS=192.168.1.1\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        values = dict(line.split("=", 1) for line in r.stdout.splitlines())
        self.assertEqual(values, {"PROD_INSTANCE": "acme", "AGENT_USER": "agent", "PROD_RUNNER_NAME": "host1-prod",
                                  "RUNNER_GROUP": "", "LAN_DNS": "192.168.1.1", "PROBE_PORTS": "22 8443", "PROD_HOME_BASE": ""})
        self.assertEqual(list(values), list(CONF_KEYS))

    def test_what_it_refuses(self):
        cases = {
            "AGENT_USER=$(id)\n": "can't read this line",
            "AGENT_USER=`id`\n": "can't read this line",
            'AGENT_USER="$HOME"\n': "can't read this line",
            "AGENT_USER=a; id\n": "can't read this line",
            "source /etc/passwd\n": "can't read this line",
            "TIER_OWNER=octo-org/other\n": "isn't a production.conf setting",
            "PATH=/tmp\n": "isn't a production.conf setting",
            "AGENT_USER=a\nAGENT_USER=b\n": "set twice",
            "AGENT_USER=root\n": "AGENT_USER",
            "AGENT_USER=factory-prod\n": "AGENT_USER",
            "PROD_RUNNER_NAME=Host_1\n": "PROD_RUNNER_NAME",
            "RUNNER_GROUP=a/b\n": "RUNNER_GROUP",
            "LAN_DNS=300.1.1.1\n": "LAN_DNS",
            "LAN_DNS=10.0.0.0/8\n": "LAN_DNS",
            'PROBE_PORTS="22 70000"\n': "PROBE_PORTS",
            'PROBE_PORTS="22 22"\n': "PROBE_PORTS",
            "PROBE_PORTS=0\n": "PROBE_PORTS",
            "PROD_HOME_BASE=relative\n": "PROD_HOME_BASE",
            "PROD_HOME_BASE=/a/../etc\n": "PROD_HOME_BASE",
            "PROD_INSTANCE=op\n": "the first tier's own names end in -op",
        }
        for text, why in cases.items():
            with self.subTest(text=text):
                r = self.read(text)
                self.assertEqual(r.returncode, 1, r.stdout)
                self.assertIn(why, r.stderr)
                self.assertEqual(r.stdout, "")


# ---- the trust root: the tier record, names in use, other tiers --------------------------------------------------

class TierRecord(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        self.record = self.root / "etc" / "factory-prod" / "tier"

    def repo(self, **env):
        return bash(function("tier_repo") + f"TIER_NAME=factory-prod\ntier_repo {self.record}\n", env=env)

    def test_the_repository_is_the_records_or_the_operators_never_the_checkouts(self):
        r = self.repo()
        self.assertEqual(r.returncode, 1)
        self.assertIn("no repository owns the production tier factory-prod yet", r.stderr)
        self.assertEqual(self.repo(TIER_OWNER="octo-org/example").stdout, "octo-org/example\n")
        for bad in ("octo-org", "octo-org/example.git", "octo-org/..", "../etc/passwd", "octo-org/example/x", "a b/c"):
            with self.subTest(bad=bad):
                self.assertIn("isn't <owner>/<repository>", self.repo(TIER_OWNER=bad).stderr)
        self.record.parent.mkdir(parents=True)
        self.record.write_text("octo-org/example\n")
        self.assertEqual(self.repo().stdout, "octo-org/example\n")
        r = self.repo(TIER_OWNER="octo-org/other")
        self.assertEqual(r.returncode, 1)
        self.assertIn("is set up from octo-org/example", r.stderr)

    def claim(self, repo, **env):
        script = (INSTALL_STUB + f"ETC={self.record.parent}\nTIER_RECORD={self.record}\nTIER_NAME=factory-prod\n"
                  + function("claim_tier") + "claim_tier\n")
        return bash(script, env={**({"FACTORY_SETUP_REPO": repo} if repo else {}), **env})

    def test_a_tier_belongs_to_the_repository_that_claimed_it(self):
        r = self.claim("octo-org/example")
        self.assertEqual(r.returncode, 1)
        self.assertIn("no repository owns the production tier factory-prod yet", r.stderr)
        self.assertFalse(self.record.exists())
        r = self.claim("octo-org/example", TIER_OWNER="octo-org/example")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.record.read_text(), "octo-org/example\n")
        self.assertEqual(self.record.stat().st_mode & 0o777, 0o644)
        self.assertEqual(self.claim("octo-org/example").returncode, 0)  # the same repository, later runs
        r = self.claim("octo-org/other", TIER_OWNER="octo-org/other")
        self.assertEqual(r.returncode, 1)
        self.assertIn("is set up from octo-org/example", r.stderr)
        self.assertEqual(self.record.read_text(), "octo-org/example\n")
        r = self.claim(None)  # never the checkout's remote: only what root fetched
        self.assertIn("didn't say which repository root fetched", r.stderr)

    def names_free(self, users=(), table=False, record=None, files=(), cfg=None):
        host = self.root / "host"
        for f in files:
            (host / f.lstrip("/")).mkdir(parents=True, exist_ok=True)
        if cfg is not None:
            (host / "etc/factory-prod").mkdir(parents=True, exist_ok=True)
            (host / "etc/factory-prod/config.json").write_text(json.dumps(cfg))
        if record:
            (host / "etc/factory-prod").mkdir(parents=True, exist_ok=True)
            (host / "etc/factory-prod/tier").write_text(record + "\n")
        stubs = (f'id() {{ case $1 in {"|".join(users) or "__none__"}) return 0 ;; *) return 1 ;; esac; }}\n'
                 f'nft() {{ {"[[ $4 == factory_prod ]]" if table else "return 1"}; }}\n')
        script = (stubs + f"HOST_ROOT={host}\nINSTANCE=''\nREPO={OWNER}\n" + function("names") + "names\n"
                  + function("names_in_use") + function("check_names_free") + "check_names_free\n")
        return bash(script)

    def test_a_first_run_on_a_free_host_goes_on(self):
        r = self.names_free()
        self.assertEqual((r.returncode, r.stdout), (0, ""), r.stderr)

    def test_names_another_tier_holds_are_refused(self):
        for kwargs, shown in ((dict(users=["factory-prod-op"]), "user factory-prod-op"),
                              (dict(table=True), "nft table inet factory_prod"),
                              (dict(files=["/usr/local/lib/factory-prod"]), "/usr/local/lib/factory-prod"),
                              (dict(files=["/etc/systemd/system/factory-op.socket"]), "factory-op.socket"),
                              (dict(cfg={"repo": "octo-org/other"}), "/etc/factory-prod/config.json")):
            with self.subTest(shown=shown):
                shutil.rmtree(self.root / "host", ignore_errors=True)
                r = self.names_free(**kwargs)
                self.assertEqual(r.returncode, 1, r.stdout)
                self.assertIn("are in use, and not by octo-org/example's tier", r.stderr)
                self.assertIn(shown, r.stderr)
                self.assertIn("its own PROD_INSTANCE", r.stderr)

    def test_this_repositorys_tier_from_before_the_record_is_taken_over(self):
        r = self.names_free(users=["factory-prod", "factory-prod-op"], table=True, files=["/usr/local/lib/factory-prod"],
                            cfg={"repo": OWNER})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("before setup kept a record", r.stdout)

    def test_a_recorded_tier_is_this_ones(self):
        r = self.names_free(users=["factory-prod"], table=True, record=OWNER)
        self.assertEqual((r.returncode, r.stdout), (0, ""), r.stderr)

    def test_the_check_runs_before_the_bootstrap_makes_anything(self):
        boot = function("bootstrap_and_exec")
        first_effect = min(boot.index(x) for x in ("install -d", "exec 7>", "ensure_deploy_key", "mktemp -d"))
        self.assertLess(boot.index("check_names_free"), first_effect)
        self.assertLess(boot.index('REPO=$(tier_repo "$TIER_RECORD")'), boot.index("check_names_free"))
        # And again, as root's own copy, before the record is made.
        main = code()[code().index("WORK=$FACTORY_SETUP_STAGED"):]
        self.assertLess(main.index("check_names_free"), main.index("\nclaim_tier\n"))
        self.assertLess(main.index("\nclaim_tier\n"), main.index("useradd"))


class Discovery(unittest.TestCase):
    def test_other_tiers_are_found_by_their_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            host = pathlib.Path(tmp)
            with_config = ("etc/factory-prod", "etc/factory-prod-9z", "etc/factory-prod-drift", "etc/factory-prod-ABC",
                           "etc/factory-prod-", "etc/factory-prod-me")
            for d in with_config + ("etc/factory-prod-noconfig", "run/factory-prod-a1", "run/factory-prod-me",
                                    "var/lib/factory-prod-zz", "var/lib/factory-prod-clone", "run/factory-prodx"):
                (host / d).mkdir(parents=True)
            for d in with_config:
                (host / d / "config.json").write_text("{}")
            (host / "run/factory-prod-b").write_text("")  # a tier's /run entry counts whatever it is, as the broker's
            script = (f"HOST_ROOT={host}\nTIER_NAME=factory-prod-me\n" + function("is_tier_name") + function("discover_tiers")
                      + 'discover_tiers\nprintf "%s\\n" ${OTHER_TIERS[@]+"${OTHER_TIERS[@]}"}\n')
            r = bash(script)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(r.stdout.split(), ["factory-prod", "factory-prod-9z", "factory-prod-a1", "factory-prod-b"])
            if BROKER.exists():
                self.assertEqual(r.stdout.split(), broker().other_tiers("factory-prod-me", host))

    @needs_broker
    def test_a_tier_name_is_the_brokers(self):
        fo = broker()
        for name in ("factory-prod", "factory-prod-b2", "factory-prod-9", "factory-prod-abcdefghijkl", "factory-prod-op",
                     "factory-prod-clone", "factory-prod-", "factory-prod-Ab", "factory-prod-a-b", "factory-prod-abcdefghijklm",
                     "factory-prodx", "factory-prod-step"):
            with self.subTest(name=name):
                r = bash(function("is_tier_name") + f"is_tier_name {name}\n")
                self.assertEqual(r.returncode == 0, fo.tier_of(pathlib.Path("/usr/local/lib") / name) is not None)


# ---- the request client --------------------------------------------------------------------------------------------

class ClientRule(unittest.TestCase):
    def plan(self, installed, new, **env):
        return bash(function("client_plan") + f'client_plan {installed} {new}\necho "PLAN=$CLIENT_PLAN"\n', env=env)

    def test_absent_identical_and_different(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            new, installed = tmp / "new", tmp / "installed"
            new.write_text("#!/usr/bin/python3 -I\nprint('per-user')\n")
            r = self.plan(installed, new)
            self.assertIn("PLAN=install", r.stdout)
            installed.write_text(new.read_text())
            r = self.plan(installed, new)
            self.assertIn("PLAN=same", r.stdout)
            self.assertNotIn("differs", r.stdout)
            installed.write_text("#!/usr/bin/python3 -I\nprint('fixed path')\n")
            r = self.plan(installed, new)
            self.assertEqual(r.returncode, 1)
            self.assertIn("-print('fixed path')", r.stdout)  # the difference, shown before anything is decided
            self.assertIn("+print('per-user')", r.stdout)
            self.assertIn("run setup again with REPLACE_CLIENT=1", r.stderr)
            for value in ("yes", "0", "true"):
                self.assertEqual(self.plan(installed, new, REPLACE_CLIENT=value).returncode, 1)
            r = self.plan(installed, new, REPLACE_CLIENT="1")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("+print('per-user')", r.stdout)
            self.assertIn("PLAN=replace", r.stdout)

    def test_a_link_or_a_directory_is_never_replaced(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            new = tmp / "new"
            new.write_text("x\n")
            (tmp / "link").symlink_to(new)
            (tmp / "dir").mkdir()
            for path in ("link", "dir"):
                with self.subTest(path=path):
                    r = self.plan(tmp / path, new, REPLACE_CLIENT="1")
                    self.assertEqual(r.returncode, 1)

    def test_the_client_is_the_factory_bundles_and_no_other_projects_hash_is_kept(self):
        self.assertIn("host/factory-op-request", function("stage_tip"))
        self.assertIn('client_plan "$CLIENT" "$SCRIPT_DIR/factory-op-request"', code())
        self.assertNotRegex(TEXT, r"[0-9a-f]{64}")
        self.assertNotIn("sha256sum \"$CLIENT\"", code())
        # Decided before anything changes, and moved over the old client, never written in place.
        main = code()[code().index("WORK=$FACTORY_SETUP_STAGED"):]
        self.assertLess(main.index("client_plan"), main.index("useradd"))
        self.assertIn('install -m 755 -o root -g root "$SCRIPT_DIR/factory-op-request" "$CLIENT.new"\nmv -f "$CLIENT.new" "$CLIENT"', TEXT)
        self.assertNotRegex(TEXT, r'(?m)^install [^\n]*"\$CLIENT"$')
        self.assertIn('for v in TIER_OWNER REPLACE_CLIENT SUDO_USER SUDO_UID; do', function("bootstrap_and_exec"))
        # One file serves every tier because it finds the socket from the calling user.
        self.assertIn('f"/run/{user}/op.sock"', (FACTORY / "host" / "factory-op-request").read_text())


# ---- staging and installing ----------------------------------------------------------------------------------------

class Staging(unittest.TestCase):
    """stage_blob/stage_tip run for real against a scratch repository standing in for the root clone."""

    FILES = {"production/factory_op.py": "REAL broker\n", "production/ops.json": "{}\n", "production/config.json": "{}\n",
             "production/factory_op_host.py": "host\n",
             "gates.py": "gates\n", "ed25519.py": "ed\n", "host/setup-production.sh": "real setup\n",
             "host/production.conf": "PROD_INSTANCE=\n", "host/factory-op-request": "client\n", "host/setup.sh": "runner\n",
             "factory.json": "{}\n"}

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)

    def make(self, extra=None, drop=()):
        work = self.root / "work"
        shutil.rmtree(work, ignore_errors=True)
        shutil.rmtree(self.root / "clone.git", ignore_errors=True)
        work.mkdir()
        git("init", "-q", "-b", "main", cwd=work)
        for rel, text in {**self.FILES, **(extra or {})}.items():
            if rel in drop:
                continue
            p = work / ".github" / "factory" / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text)
        git("add", "-A", cwd=work)
        git("commit", "-q", "-m", "x", cwd=work)
        git("clone", "-q", "--bare", str(work), str(self.root / "clone.git"), cwd=self.root)
        self.tip = git("rev-parse", "HEAD", cwd=work).strip()

    def bash(self, script, bin_dir=None):
        path = os.environ["PATH"] if bin_dir is None else f"{bin_dir}:{os.environ['PATH']}"
        prelude = f'SAFE_PATH="{path}"\nFETCH_SSH=ssh\nCLONE={self.root / "clone.git"}\nTIP={self.tip}\n'
        funcs = "".join(function(n) for n in ("clean_git", "stage_blob", "stage_tip"))
        return bash(prelude + funcs + script, path=path)

    def staged(self):
        dest = self.root / "out"
        shutil.rmtree(dest, ignore_errors=True)
        r = self.bash(f"stage_tip {dest}")
        self.assertEqual(r.returncode, 0, r.stderr)
        return sorted(str(p.relative_to(dest / ".github/factory")) for p in dest.rglob("*") if p.is_file())

    def test_a_replace_ref_does_not_change_what_is_staged(self):
        self.make()
        clone = self.root / "clone.git"
        real = git("rev-parse", f"{self.tip}:.github/factory/production/factory_op.py", cwd=clone).strip()
        evil = git("hash-object", "-w", "--stdin", cwd=clone, data="EVIL broker\n").strip()
        git("replace", real, evil, cwd=clone)
        # Without the clean environment git does hand out the planted bytes: the flaw the staging avoids.
        self.assertEqual(git("show", f"{self.tip}:.github/factory/production/factory_op.py", cwd=clone), "EVIL broker\n")
        self.staged()
        self.assertEqual((self.root / "out/.github/factory/production/factory_op.py").read_text(), "REAL broker\n")

    def test_every_file_is_staged_and_only_scripts_from_ops(self):
        self.make({"production/receipt.pub": "pub\n", "production/ops/health.sh": "h\n",
                   "production/ops/notes.txt": "not a script\n", "production/stray.py": "not staged\n",
                   "production/tests/test_x.py": "not staged\n"})
        self.assertEqual(self.staged(), sorted(list(self.FILES) + ["production/receipt.pub", "production/ops/health.sh"]))

    def test_the_receipt_and_scripts_are_optional(self):
        self.make()
        self.assertEqual(self.staged(), sorted(self.FILES))

    def test_a_tip_without_its_host_module_stops_at_staging_saying_so(self):
        """Changed with the host module made required: this broker refuses every command without one, so setup stops here
        rather than install and then fail acceptance with a misleading deploy-key hint."""
        self.make(drop=("production/factory_op_host.py",))
        r = self.bash(f"stage_tip {self.root / 'out4'}")
        self.assertEqual(r.returncode, 1)
        self.assertIn("has no file .github/factory/production/factory_op_host.py", r.stderr)
        self.assertIn("runs every step through its host module", r.stderr)
        self.assertNotIn("deploy key", r.stderr)

    def test_every_required_file_is_required(self):
        for rel in self.FILES:
            with self.subTest(rel=rel):
                self.make(drop=(rel,))
                r = self.bash(f"stage_tip {self.root / 'out2'}")
                self.assertEqual(r.returncode, 1)
                self.assertIn(f"has no file .github/factory/{rel}", r.stderr)

    def test_a_staged_file_that_does_not_hash_to_its_blob_id_is_refused(self):
        self.make()
        fake = self.root / "fakebin"
        fake.mkdir()
        (fake / "git").write_text(f'#!/bin/sh\nfor a in "$@"; do [ "$a" = cat-file ] && {{ echo tampered; exit 0; }}; done\n'
                                  f'exec {shutil.which("git")} "$@"\n')
        (fake / "git").chmod(0o755)
        r = self.bash(f"stage_blob .github/factory/gates.py {self.root}/o", bin_dir=str(fake))
        self.assertEqual(r.returncode, 1)
        self.assertIn("do not hash to the blob id", r.stderr)

    def test_a_link_is_not_a_file(self):
        self.make()
        work = self.root / "work"
        target = work / ".github/factory/production/factory_op.py"
        target.unlink()
        target.symlink_to("../gates.py")
        git("add", "-A", cwd=work)
        git("commit", "-q", "-m", "link", cwd=work)
        shutil.rmtree(self.root / "clone.git")
        git("clone", "-q", "--bare", str(work), str(self.root / "clone.git"), cwd=self.root)
        self.tip = git("rev-parse", "HEAD", cwd=work).strip()
        r = self.bash(f"stage_tip {self.root / 'out3'}")
        self.assertEqual(r.returncode, 1)
        self.assertIn("not a regular file", r.stderr)


class InstalledFiles(unittest.TestCase):
    """install_broker_files, run for real with root's install made a plain one: the installed package hashes as the
    repository's, host module or not, and a module or script the tip no longer has is removed."""

    def test_the_installed_digest_is_the_repositorys(self):
        g = gates()
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            repo, lib = tmp / "repo", tmp / "lib"
            (repo / "production" / "ops").mkdir(parents=True)
            (lib / "ops").mkdir(parents=True)
            for rel, data in {"gates.py": "g\n", "ed25519.py": "e\n", "production/factory_op.py": "b\n",
                              "production/ops.json": "{}\n", "production/factory_op_host.py": "h\n",
                              "production/config.json": "{}\n", "production/ops/a.sh": "a\n"}.items():
                (repo / rel).write_text(data)
            (lib / "ops" / "stale.sh").write_text("old\n")
            (lib / "stray.py").write_text("not in the digest\n")
            run = lambda: bash(INSTALL_STUB + function("install_broker_files")  # noqa: E731
                               + f"install_broker_files {repo / 'production'} {repo} {lib}\n")
            r = run()
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertFalse((lib / "ops" / "stale.sh").exists())
            self.assertEqual(g.installed_ops_files(lib), g.repo_ops_files(repo))
            self.assertIn("factory_op_host.py", g.installed_ops_files(lib))
            # The config the broker reads is the one in the library, and with a host module it is in the digest.
            self.assertEqual((lib / "config.json").read_text(), "{}\n")
            self.assertIn("config.json", g.installed_ops_files(lib))
            # The tip drops the host module and its last script: both go from the host too.
            (repo / "production" / "factory_op_host.py").unlink()
            (repo / "production" / "ops" / "a.sh").unlink()
            r = run()
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertFalse((lib / "factory_op_host.py").exists())
            self.assertEqual(list((lib / "ops").iterdir()), [])
            self.assertEqual(g.ops_digest(g.installed_ops_files(lib)), g.ops_digest(g.repo_ops_files(repo)))

    def test_the_broker_modules_are_gates(self):
        self.assertEqual(tuple(assignment("BROKER_MODULES").split()), gates().BROKER_MODULES)
        self.assertIn("for f in $BROKER_MODULES; do", function("stage_tip"))  # required since the host module must be there
        self.assertIn("for m in $BROKER_MODULES; do", function("install_broker_files"))
        self.assertIn('install_broker_files "$PROD" "$FACTORY" "$LIB"', code())


# ---- the broker block, the drift unit, the runner pin ---------------------------------------------------------

class BlockRead(unittest.TestCase):
    def read(self, cat):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "ops.json"
            path.write_text(cat if isinstance(cat, str) else json.dumps(cat))
            return bash(function("block_read") + f"block_read {path}\n")

    def test_what_setup_takes_from_the_block(self):
        r = self.read(catalog(health=700, capture=500, drift=300))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.splitlines(), [
            "EGRESS=api.host.example status.host.example", "PYTHON=3.8", "HEALTH_TIMEOUT_S=700", "CAPTURE_TIMEOUT_S=500",
            "DRIFT_SCAN_TIMEOUT_S=300", "SECRET=token api.token cd text", "SECRET=key state.key setup hex"])

    def test_what_it_refuses(self):
        def with_block(**changes):
            cat = catalog()
            cat["broker"].update(changes)
            return cat
        secret = lambda **s: with_block(secrets={"x": {"file": "x.key", "by": "setup", "hex": True, **s}})  # noqa: E731
        cases = {
            "not json": ("{", "can't read it"),
            "no block": ({"operations": {}}, "has no broker block"),
            "no egress": (with_block(egress=[]), "1 to 16"),
            "an IP": (with_block(egress=["203.0.113.7"]), "an IP address"),
            "upper case": (with_block(egress=["API.example.com"]), "not a lower-case host name"),
            "a port": (with_block(egress=["api.example.com:443"]), "not a lower-case host name"),
            "a repeat": (with_block(egress=["a.example", "a.example"]), "1 to 16"),
            "a path": (secret(file="../shadow"), "plain file name"),
            "a slash": (secret(file="sub/x"), "plain file name"),
            "the receipt key": (secret(file="receipt.key"), "the tier's own file"),
            "the record": (secret(file="tier"), "the tier's own file"),
            "the deploy key": (secret(file="github-deploy-key"), "the tier's own file"),
            "setup writes text": (secret(hex=False), "is hex"),
            "by someone else": (secret(by="host"), "by must be cd or setup"),
            "an unknown key": (secret(mode="0644"), "nothing else"),
            "hex not a boolean": (secret(hex="true"), "hex true or false"),
            "python as a float": (with_block(python=3.11), "broker.python"),
            "python 2": (with_block(python="2.7"), "broker.python"),
            "no drift-scan": (with_block(internal_ops={"host-check": {"timeout_s": 60}}), "drift-scan needs timeout_s"),
            "a boolean timeout": (with_block(internal_ops={"drift-scan": {"timeout_s": True}}), "drift-scan needs timeout_s"),
        }
        for label, (cat, why) in cases.items():
            with self.subTest(label):
                r = self.read(cat)
                self.assertEqual(r.returncode, 1, r.stdout)
                self.assertIn(why, r.stderr)
        two = with_block(secrets={"a": {"file": "same", "by": "cd", "hex": False}, "b": {"file": "same", "by": "cd", "hex": False}})
        self.assertIn("another secret's", self.read(two).stderr)
        cat = catalog()
        del cat["operations"]["capture-state"]
        self.assertIn("operations.capture-state needs timeout_s", self.read(cat).stderr)

    def test_setup_refuses_every_file_the_broker_keeps_for_the_tier(self):
        files = set(assignment("TIER_FILES").split())
        self.assertTrue({"config.json", "receipt.key", "github-deploy-key", "github-deploy-key.pub", "known_hosts", "tier"} <= files)
        if BROKER.exists():
            self.assertEqual(set(broker().TIER_FILES), files)  # the catalog test in CI refuses what setup refuses

    def test_secrets_are_made_or_named_never_read(self):
        main = code()[code().index("WORK=$FACTORY_SETUP_STAGED"):]
        loop = main[main.index('for i in ${SECRET_LABELS[@]+'):main.index('pub=$("$BROKER_CMD" pubkey)')]
        self.assertIn('ensure_hex_secret "$f"', loop)
        self.assertIn("stat -c '%a %U:%G' \"$f\"", loop)
        self.assertIn('chmod 600 "$f"; chown root:root "$f"', loop)
        for banned in ("cat ", '<"$f"', "< \"$f\"", "$(<", "head ", "read -r secret"):
            self.assertNotIn(banned, loop)
        # A secret setup makes: 32 random bytes as hex, never through a link, root's alone.
        made = function("ensure_hex_secret")
        for needle in ("secrets.token_hex(32)", "os.O_EXCL | os.O_NOFOLLOW", "os.lstat(path)", "0o600", "os.chown(path, 0, 0"):
            self.assertIn(needle, made)

    def test_a_secret_setup_makes_is_written_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            key = pathlib.Path(tmp) / "state.key"
            script = function("ensure_hex_secret").replace("os.chown(path, 0, 0, follow_symlinks=False)", "pass")
            r = bash(script + f"ensure_hex_secret {key}\n")
            self.assertEqual(r.returncode, 0, r.stderr)
            first = key.read_text()
            self.assertRegex(first, r"^[0-9a-f]{64}\n$")
            self.assertEqual(key.stat().st_mode & 0o777, 0o600)
            self.assertEqual(bash(script + f"ensure_hex_secret {key}\n").returncode, 0)
            self.assertEqual(key.read_text(), first)
            # A declared secret named like a temporary file is never removed to make one.
            neighbour = pathlib.Path(tmp) / "other.key.new"
            neighbour.write_text("CD's\n")
            r = bash(script + f"ensure_hex_secret {pathlib.Path(tmp) / 'other.key'}\n")
            self.assertEqual((r.returncode, neighbour.read_text()), (0, "CD's\n"), r.stderr)
            key.unlink()
            key.symlink_to(pathlib.Path(tmp) / "elsewhere")
            r = bash(script + f"ensure_hex_secret {key}\n")
            self.assertEqual(r.returncode, 1)
            self.assertFalse((pathlib.Path(tmp) / "elsewhere").exists())


@unittest.skipUnless(NOT_ROOT, "the render mode refuses root")
class DriftTimeout(unittest.TestCase):
    """The drift unit's TimeoutStartSec, from the catalog's health and capture-state timeouts and the block's drift-scan."""

    CASES = ((600, 840, 400), (3000, 840, 400), (60, 3600, 3600), (1, 1, 1))

    def minutes(self, cat):
        with tempfile.TemporaryDirectory() as tmp:
            root = Scratch(pathlib.Path(tmp) / "c", ops=cat).render(pathlib.Path(tmp) / "out")
            unit = (root / "etc/systemd/system/factory-op-drift.service").read_text()
            return int(re.search(r"^TimeoutStartSec=(\d+)min$", unit, re.M).group(1))

    def test_at_least_the_drift_checks_worst_case(self):
        lock, fetch, margin, git_s = (int(assignment(n)) for n in ("DRIFT_LOCK_WAIT_S", "FETCH_TIMEOUT_S",
                                                                  "STEP_KILL_MARGIN_S", "GIT_CALLS_BUDGET_S"))
        for health, capture, drift in self.CASES:
            with self.subTest(health=health, capture=capture, drift=drift):
                worst = max(lock, health + margin + 60) + fetch + capture + drift + 2 * margin + git_s
                minutes = self.minutes(catalog(health=health, capture=capture, drift=drift))
                self.assertGreaterEqual(minutes * 60, worst)
                self.assertEqual(minutes, -(-worst // 60) + 5)

    @needs_broker
    def test_the_brokers_own_rule_fits(self):
        fo = broker()
        self.assertTrue(hasattr(fo, "drift_unit_min_s"), "the broker must say its drift check's worst case (drift_unit_min_s)")
        for name in ("DRIFT_LOCK_WAIT_S", "FETCH_TIMEOUT_S", "STEP_KILL_MARGIN_S", "GIT_CALLS_BUDGET_S"):
            self.assertEqual(int(assignment(name)), getattr(fo, name), name)
        for health, capture, drift in self.CASES:
            with self.subTest(health=health, capture=capture, drift=drift):
                cat = catalog(health=health, capture=capture, drift=drift)
                self.assertGreaterEqual(self.minutes(cat) * 60, fo.drift_unit_min_s(cat))


class RunnerPin(unittest.TestCase):
    """The runner is the factory bundle's: its version and checksum come from host/setup.sh, never a copy here."""

    def setup_sh_pin(self):
        text = SETUP_SH.read_text()
        return (re.search(r"(?m)^RUNNER_VERSION=(\S+)$", text).group(1), re.search(r"(?m)^RUNNER_SHA256=(\S+)$", text).group(1))

    def test_the_pin_is_read_from_the_factorys_setup(self):
        r = bash(function("runner_pin") + f"runner_pin {SETUP_SH}\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(tuple(r.stdout.split()), self.setup_sh_pin())
        self.assertNotRegex(TEXT, r"(?m)^\s*RUNNER_(VERSION|SHA256)=")
        self.assertIn("host/setup.sh", function("stage_tip"))
        self.assertIn('resolve_settings "$FACTORY/factory.json" "$SCRIPT_DIR/setup.sh"', code())

    @unittest.skipUnless(NOT_ROOT, "the print modes refuse root")
    def test_the_settings_show_the_factorys_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(Scratch(tmp).settings()["RUNNER_VERSION"], self.setup_sh_pin()[0])

    def test_an_unclear_pin_is_refused(self):
        version, sha = self.setup_sh_pin()
        for text in (f"RUNNER_VERSION={version}\n", f"RUNNER_VERSION={version}\nRUNNER_VERSION=1.0.0\nRUNNER_SHA256={sha}\n",
                     f"RUNNER_VERSION=latest\nRUNNER_SHA256={sha}\n", f"RUNNER_VERSION={version}\nRUNNER_SHA256=abc\n",
                     f"RUNNER_VERSION={version}\nRUNNER_SHA256={sha}\n  RUNNER_VERSION=$(id)\n"):
            with self.subTest(text=text), tempfile.TemporaryDirectory() as tmp:
                path = pathlib.Path(tmp) / "setup.sh"
                path.write_text(text)
                r = bash(function("runner_pin") + f"runner_pin {path}\n")
                self.assertEqual(r.returncode, 1, r.stdout)
                self.assertIn("doesn't pin the runner", r.stderr)

    def test_the_runner_libraries_are_the_factorys_list(self):
        def groups(text):
            body = re.search(r"^runner_deps\(\) \{\n.*?^\}\n", text, re.S | re.M).group(0)
            loop = re.search(r"for group in (.*?); do", body, re.S).group(1)
            return re.findall(r'"([^"]*)"', loop)
        self.assertEqual(groups(TEXT), ["acl"] + groups(SETUP_SH.read_text()))

    def test_registration_keeps_the_token_out_of_argv_and_never_replaces(self):
        c = code()
        self.assertNotIn("--token", c)
        self.assertNotIn("--replace", c)
        self.assertIn("ACTIONS_RUNNER_INPUT_TOKEN=$token runuser", c)
        # The installed version is root's record, never the runner's own (writable) files.
        self.assertIn("VERSION_FILE=$STATE/runner.version", c)
        self.assertNotIn("Runner.Listener' --version", c)
        # Values reach the runner user's commands as arguments, never inside a shell string.
        for m in re.finditer(r"runuser -u \"\$RUNNER_USER\" -- /bin/bash -c '([^']*)'", c):
            self.assertNotIn("$RUNNER", m.group(1))


# ---- the token file, the preflight --------------------------------------------------------------------------------

class TokenFile(unittest.TestCase):
    """copy_token_file on real files: the sudo user (here, this test's own uid) or root may own it."""

    def run_copy(self, make, mode=0o600, sudo_uid=None):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            target = make(tmp)
            if target.is_file() and not target.is_symlink():
                target.chmod(mode)
            dest = tmp / "copy"
            r = bash(function("copy_token_file") + f"copy_token_file {target} {dest}\n",
                     env={"SUDO_UID": str(os.getuid() if sudo_uid is None else sudo_uid)})
            r.copy = dest.read_text() if dest.exists() else None
            r.copy_mode = (dest.stat().st_mode & 0o777) if dest.exists() else None
            return r

    @staticmethod
    def write(text):
        def make(tmp):
            f = tmp / "reg-token"
            f.write_text(text)
            return f
        return make

    def test_a_good_token_file_is_copied_root_only(self):
        good = "A" * 29 + "7"
        r = self.run_copy(self.write(good + "\n"))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((r.copy, r.copy_mode), (good, 0o600))
        self.assertEqual(self.run_copy(self.write(good), mode=0o400).returncode, 0)

    def test_everything_else_dies_and_copies_nothing(self):
        good = "B" * 30
        cases = {
            "another owner": dict(make=self.write(good), sudo_uid=os.getuid() + 1 if os.getuid() else 1),
            "group-readable": dict(make=self.write(good), mode=0o640),
            "world-readable": dict(make=self.write(good), mode=0o644),
            "executable": dict(make=self.write(good), mode=0o700),
            "too short": dict(make=self.write("A" * 19)),
            "not alphanumeric": dict(make=self.write("A" * 30 + "; rm -rf /")),
            "two lines": dict(make=self.write(good + "\n" + good)),
            "empty": dict(make=self.write("")),
        }

        def link(tmp):
            (tmp / "real").write_text(good)
            (tmp / "reg-token").symlink_to(tmp / "real")
            return tmp / "reg-token"

        def directory(tmp):
            (tmp / "reg-token").mkdir()
            return tmp / "reg-token"
        cases["a link"] = dict(make=link)
        cases["a directory"] = dict(make=directory)
        for label, kwargs in cases.items():
            if label == "another owner" and os.getuid() == 0:
                continue  # root owns every file it makes
            with self.subTest(label):
                r = self.run_copy(**kwargs)
                self.assertEqual(r.returncode, 1)
                self.assertIsNone(r.copy)

    def test_the_bootstrap_checks_it_once_and_hands_on_the_copy(self):
        boot = function("bootstrap_and_exec")
        self.assertIn('copy_token_file "$TOKEN_FILE" "$token_copy"', boot)
        self.assertIn('"FACTORY_SETUP_TOKEN_COPY=$token_copy"', boot)
        self.assertLess(boot.index("copy_token_file"), boot.index("exec env -i"))
        c = code()
        self.assertIn('token=$(<"$FACTORY_SETUP_TOKEN_COPY")', c)
        self.assertIn('[[ $FACTORY_SETUP_TOKEN_COPY == "$WORK/reg-token" ]]', c)
        self.assertNotIn('$(<"$TOKEN_FILE")', c)
        self.assertIn("os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK", function("copy_token_file"))


class Preflight(unittest.TestCase):
    """check_settings with every required command stubbed and stand-ins for the openssl programs; check_python with a
    stand-in for /usr/bin/python3."""

    GOOD_SSL = "OpenSSL 3.0.13 30 Jan 2024 (Library: OpenSSL 3.0.13 30 Jan 2024)"

    def run_check(self, ssl_version=GOOD_SSL, ssl_on_path=False, runner_name="host1-production", agent="agent"):
        text = function("check_settings")
        tools = [t for t in re.search(r"for c in (.*?); do", text, re.S).group(1).split() if t != "\\"]
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            (tmp / "bin").mkdir()
            for t in tools:
                (tmp / "bin" / t).write_text("#!/bin/sh\nexit 0\n")
                (tmp / "bin" / t).chmod(0o755)
            ssl = tmp / "found" / "openssl" if ssl_on_path else tmp / "openssl"
            ssl.parent.mkdir(exist_ok=True)
            if ssl_version is not None:
                ssl.write_text(f"#!/bin/sh\necho '{ssl_version}'\n")
                ssl.chmod(0o755)
            candidates = "/usr/bin/openssl /usr/local/bin/openssl /opt/homebrew/bin/openssl"
            self.assertIn(candidates, text)
            script = (f"RUNNER_NAME={runner_name} AGENT_USER={agent}\n"
                      f"BROKER_PATH={tmp / 'found' if ssl_on_path else tmp / 'empty'}\n"
                      + text.replace(candidates, str(tmp / "absent" if ssl_on_path else ssl)) + "check_settings\n")
            return bash(script, path=f"{tmp / 'bin'}:{os.environ['PATH']}")

    def test_a_host_without_openssl_3_is_refused(self):
        for version in ("LibreSSL 3.3.6", "OpenSSL 1.1.1w  11 Sep 2023", None):
            with self.subTest(version=version):
                r = self.run_check(ssl_version=version)
                self.assertEqual(r.returncode, 1, r.stderr)
                self.assertIn("OpenSSL 3 or newer (not LibreSSL) is required", r.stderr)

    def test_openssl_3_and_later_pass(self):
        for version in ("OpenSSL 3.0.13 30 Jan 2024", "OpenSSL 4.0.3 29 Sep 2026"):
            with self.subTest(version=version):
                self.assertEqual(self.run_check(ssl_version=version).returncode, 0)
        self.assertEqual(self.run_check(ssl_on_path=True).returncode, 0)

    def test_the_runner_name_and_agent_login_are_required(self):
        r = self.run_check(runner_name="")
        self.assertEqual(r.returncode, 1)
        self.assertIn("PROD_RUNNER_NAME is required", r.stderr)
        r = self.run_check(agent="")
        self.assertEqual(r.returncode, 1)
        self.assertIn("AGENT_USER is required", r.stderr)

    def test_the_python_floor_is_the_blocks_compared_as_numbers(self):
        check = function("check_python")
        self.assertIn("/usr/bin/python3 -I", check)
        script = check.replace("/usr/bin/python3", sys.executable)
        here = f"{sys.version_info[0]}.{sys.version_info[1]}"
        for floor, ok in (("3.8", True), (here, True), (f"3.{sys.version_info[1] + 1}", False), ("3.99", False)):
            with self.subTest(floor=floor):
                r = bash(script + f"check_python {floor}\n")
                self.assertEqual(r.returncode == 0, ok, r.stderr)
                if not ok:
                    self.assertIn(f"Python {floor} or newer", r.stderr)

    def test_the_preflight_runs_before_anything_changes(self):
        main = code()[code().index("WORK=$FACTORY_SETUP_STAGED"):]
        first_change = main.index("\nclaim_tier\n")
        for check in ("\ncheck_settings\n", 'check_python "$PYTHON_MIN"', 'load_block "$PROD/ops.json"', "CONFIG_PY",
                      "check_runner_name_free", 'id "$AGENT_USER"', "\ncheck_systemd\n", "config_matches_factory"):
            self.assertLess(main.index(check), first_change, check)


# ---- the sandbox ---------------------------------------------------------------------------------------------------

@unittest.skipUnless(NOT_ROOT, "the print modes refuse root")
class StepProps(unittest.TestCase):
    # The configuration's paths, which the broker adds itself (BindReadOnlyPaths, the tier's egress socket, came with the
    # allowlist sandbox: /run is empty but for it).
    SETUP_ONLY = {"ReadOnlyPaths", "InaccessiblePaths", "BindReadOnlyPaths"}

    def props(self):
        with tempfile.TemporaryDirectory() as tmp:
            return Scratch(tmp).step_props()

    def test_the_sandbox_properties_of_an_operator_step(self):
        props = self.props()
        for key, value in {"NoNewPrivileges": "yes", "PrivateTmp": "yes", "ProtectSystem": "strict", "ProtectHome": "yes",
                           "RestrictAddressFamilies": "AF_UNIX", "PrivateNetwork": "yes", "KillMode": "control-group",
                           "ProtectProc": "invisible", "PrivateDevices": "yes", "RestrictNamespaces": "yes",
                           "CapabilityBoundingSet": "", "SystemCallFilter": "@system-service",
                           "SystemCallArchitectures": "native", "LockPersonality": "yes", "MemoryMax": "512M",
                           "TasksMax": "64", "LimitFSIZE": "1M", "SystemCallErrorNumber": "EPERM",
                           "RestrictSUIDSGID": "yes", "UMask": "0077", "ReadOnlyPaths": "/var/lib/factory-prod-clone"}.items():
            self.assertEqual(props.get(key), value, key)
        hidden = props["InaccessiblePaths"].split()
        for path in ("/run/tailscale", "/var/run/tailscale", "/run/dbus/system_bus_socket", "/run/systemd/resolve",
                     "/var/lib/factory-prod", "/var/log/factory-prod"):
            self.assertIn("-" + path, hidden)
        self.assertIn('systemd-run --unit="$STEP_UNIT-setup-', TEXT)
        self.assertIn('--uid="$OP_USER" --gid="$OP_USER"', TEXT)

    @needs_broker
    def test_setups_step_properties_equal_the_brokers(self):
        """The acceptance probes run under setup's properties, the broker's steps under its STEP_PROPS: the same."""
        fo = broker()
        self.assertTrue(hasattr(fo, "STEP_PROPS"), "the broker must expose its step's sandbox as STEP_PROPS")
        props = self.props()
        self.assertEqual({k: v for k, v in props.items() if k not in self.SETUP_ONLY},
                         dict(p.split("=", 1) for p in fo.STEP_PROPS))
        self.assertEqual(props["BindReadOnlyPaths"], fo.tier_names("factory-prod")["egress_socket"])
        if hasattr(fo, "HIDDEN_ALWAYS"):
            self.assertTrue({"-" + p for p in fo.HIDDEN_ALWAYS} <= set(props["InaccessiblePaths"].split()))


# ---- what the text promises ----------------------------------------------------------------------------------------

class ScriptText(unittest.TestCase):
    def test_nftables_service_is_never_restarted_or_reloaded(self):
        c = code()
        self.assertNotRegex(c, r"systemctl\s+(?:-\S+\s+)*(?:restart|reload|stop|try-restart|reload-or-restart|kill)\s+[^\n]*nftables")
        self.assertNotRegex(c, r"(?:service|systemctl)\s[^\n]*\bnftables(?:\.service)?\b[^\n]*(?:restart|reload)")
        for banned in ("flush ruleset", "nft flush", "iptables -F"):
            self.assertNotIn(banned, c)
        # The one table this tier ever deletes is its own (the firewall unit's stop, and the file's own reload).
        self.assertEqual(set(re.findall(r"delete table inet (\S+)", c)), {"$NFT_TABLE"})
        self.assertIn('nft -f "$NFT_FILE"', c)
        self.assertIn('systemctl start "$FW_UNIT.service"', c)

    def test_every_systemctl_change_is_of_this_tiers_units(self):
        for m in re.finditer(r"systemctl\s+(?:restart|stop|start|enable(?:\s+--now)?|reload|disable)\s+([^\n;&|]*)", code()):
            for arg in m.group(1).split():
                if arg.startswith("-") or arg.startswith("2>") or arg == ">/dev/null":
                    continue
                self.assertRegex(arg, r'^"?\$(?:FW_UNIT|RUNNER_UNIT|BROKER_UNIT|EGRESS_UNIT|DRIFT_UNIT)'
                                      r'(?:\.service|\.socket|\.timer|-reapply\.service)?"?$', m.group(0))

    def test_nothing_the_checkout_owner_controls_is_trusted_for_content(self):
        c = code()
        for banned in ("remote get-url", "ls-files", "status --porcelain", 'source "', ". \"$SCRIPT_DIR", "eval "):
            self.assertNotIn(banned, c)
        # Every git call goes through clean_git (the clean environment) against the root clone.
        outside = c.replace(function("clean_git"), "")
        self.assertEqual(re.findall(r"(?m)^\s*(?:\S+=\S+\s+)*git\s", outside), [])
        clean = function("clean_git")
        for setting in ("env -i", "GIT_CONFIG_NOSYSTEM=1", "GIT_CONFIG_GLOBAL=/dev/null", "HOME=/nonexistent",
                        "GIT_NO_REPLACE_OBJECTS=1", "GIT_LITERAL_PATHSPECS=1", "GIT_TERMINAL_PROMPT=0",
                        "GIT_SSH_COMMAND=$FETCH_SSH"):
            self.assertIn(setting, clean)
        # The URL is the tier record's repository, the branch is GitHub's default for it, and the SSH command is pinned.
        self.assertEqual(TEXT.count("git@github.com:"), 1)
        self.assertIn("REMOTE_URL=git@github.com:$REPO.git", TEXT)
        self.assertIn('BRANCH=$(default_branch "$REMOTE_URL")', function("bootstrap_and_exec"))
        self.assertIn("clean_git ls-remote --symref", function("default_branch"))
        self.assertIn('"$REMOTE_URL" "+refs/heads/$BRANCH:$SETUP_REF"', function("fetch_tip"))
        ssh = re.search(r'FETCH_SSH="(.*)"$', TEXT, re.M).group(1)
        for opt in ("-F /dev/null", "-i $ETC/github-deploy-key", "-o IdentitiesOnly=yes", "-o BatchMode=yes",
                    "-o StrictHostKeyChecking=yes", "-o UserKnownHostsFile=$ETC/known_hosts", "-o GlobalKnownHostsFile=/dev/null"):
            self.assertIn(opt, ssh)
        # The bootstrap reads production.conf as text; the staged copy reads the staged one, and agrees on the instance.
        self.assertIn('load_conf "$SCRIPT_DIR/production.conf"', function("bootstrap_and_exec"))
        self.assertIn('[[ $INSTANCE == "${FACTORY_SETUP_INSTANCE-}" ]]', c)

    def test_the_stages_run_in_the_documented_order(self):
        c = code()
        boot = function("bootstrap_and_exec")
        order = ["load_conf", "check_settings", 'REPO=$(tier_repo "$TIER_RECORD")', "check_names_free", 'exec 7> "$SETUP_LOCK"', "mktemp -d",
                 'install -d -m 755 -o root -g root "$ETC" "$CLONE_BASE"', "ensure_deploy_key", "ensure_known_hosts",
                 "default_branch", "fetch_tip", "stage_tip", 'cmp -s "$stage/.github/factory/host/setup-production.sh"',
                 'cmp -s "$stage/.github/factory/host/production.conf"', "exec env -i"]
        positions = [boot.index(x) for x in order]
        self.assertEqual(positions, sorted(positions))
        for passed in ('"FACTORY_SETUP_STAGED=$WORK"', '"FACTORY_SETUP_REPO=$REPO"', '"FACTORY_SETUP_BRANCH=$BRANCH"',
                       '"FACTORY_SETUP_INSTANCE=$INSTANCE"', '/bin/bash "$stage/.github/factory/host/setup-production.sh" "$@"'):
            self.assertIn(passed, boot)
        self.assertIn('if [[ -z ${FACTORY_SETUP_STAGED:-} ]]; then\n  bootstrap_and_exec "$@"', c)
        staged = function("staged_checks")
        self.assertIn('[[ ${BASH_SOURCE[0]} == "$WORK/stage/.github/factory/host/setup-production.sh" ]]', staged)
        self.assertIn("stat.S_IMODE(st.st_mode) == 0o700", staged)
        self.assertIn("[[ /dev/fd/7 -ef $SETUP_LOCK ]]", staged)
        # Nothing removes $WORK until it is known to be the bootstrap's root-only directory.
        main = c[c.index("WORK=$FACTORY_SETUP_STAGED"):]
        self.assertLess(main.index("\nstaged_checks\n"), main.index("trap cleanup EXIT"))
        self.assertNotIn("rm -rf", c[c.index("WORK=$FACTORY_SETUP_STAGED"):c.index("\nstaged_checks\n", c.index("WORK=$FACTORY_SETUP_STAGED"))])
        # Nothing with an effect on the host comes before the hand-over.
        handover = c.index('bootstrap_and_exec "$@"   ')
        for effect in ("useradd --create-home", "systemctl enable", 'nft -f "$NFT_FILE"', "apt-get install -y", "visudo -cf",
                       "install_broker_files \"$PROD\"", "\nclaim_tier\n"):
            self.assertGreater(c.index(effect), handover, effect)
        after = c[handover:]
        self.assertNotIn("ensure_deploy_key\n", after)
        self.assertNotIn("ssh-keygen -q", after)

    def test_after_the_hand_over_nothing_is_installed_from_the_checkout(self):
        c = code()
        after = c[c.index("WORK=$FACTORY_SETUP_STAGED"):]
        self.assertNotIn("$checkout/.github", after)
        self.assertNotIn("FACTORY_SETUP_CHECKOUT/", after)
        self.assertIn('[[ $(clean_git -C "$CLONE" hash-object --no-filters "$dest") == "$blob" ]]', c)

    def test_the_environment_is_fixed_before_anything_runs(self):
        top = TEXT[TEXT.index("set -euo pipefail"):TEXT.index("() {")]
        self.assertIn("SAFE_PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin\nPATH=$SAFE_PATH\nunset TMPDIR BASH_ENV ENV CDPATH\n", top)
        self.assertEqual(TEXT.count("SAFE_PATH=/usr/local"), 1)
        self.assertIn('env -i "PATH=$SAFE_PATH" LANG=C.UTF-8 python3 -I -c \'import json, urllib.request', TEXT)

    def test_the_print_and_render_modes_need_no_root_and_root_needs_no_override(self):
        c = code()
        self.assertIn('[[ $EUID -ne 0 ]] || die "run $1 without sudo', c)
        self.assertIn("for v in PRODUCTION_CONF OPS_JSON FACTORY_JSON FACTORY_HOST_ROOT; do", c)
        modes = c.index("--print-settings|--print-step-props|--print-egress-hidden|--render)")
        self.assertLess(modes, c.index('bootstrap_and_exec "$@"   '))
        # Only those modes take the overrides; root's paths have no prefix.
        for v in ("PRODUCTION_CONF", "OPS_JSON", "FACTORY_JSON", "FACTORY_HOST_ROOT"):
            for m in re.finditer(rf"\$\{{{v}:-", c):
                self.assertLess(m.start(), c.index("exit 0 ;;\nesac"), v)

    def test_the_wrapper_is_installed_from_the_rendered_text(self):
        self.assertIn('render_wrapper ""\nchown root:root "$BROKER_CMD"; chmod 755 "$BROKER_CMD"', TEXT)
        self.assertNotIn("printf '#!/bin/sh", code())

    def test_the_clone_is_the_operators_to_read_and_nobody_elses(self):
        self.assertIn('chown -R "root:$OP_USER" "$CLONE"; chmod 755 "$CLONE_BASE"; chmod 750 "$CLONE"', TEXT)
        self.assertNotIn("core.sshCommand", code())

    def test_refusals_before_anything_changes(self):
        main = code()[code().index("WORK=$FACTORY_SETUP_STAGED"):]
        first = main.index("useradd --create-home")
        for needle in ("staged_checks", "disagrees with this tier's names", "release_branch isn't set", "a deploy directory",
                       "check_names_free", "check_runner_name_free", "client_plan", "claim_tier", "snapshot_firewall"):
            self.assertLess(main.index(needle), first, needle)
        self.assertIn('add this as a read-only deploy key, then run setup again:\n$(cat "$ETC/github-deploy-key.pub")', TEXT)

    def test_idempotence_markers(self):
        for needle in ('if ! id "$RUNNER_USER"', 'if ! id "$u"', "[[ -d $CLONE ]] || clean_git init", "[[ ! -f $RUNNER_DIR/.runner ]]",
                       "st is None or st.st_size == 0", "install -d"):
            self.assertIn(needle, TEXT)

    def test_the_operator_and_egress_users_cannot_log_in(self):
        self.assertIn("--shell /usr/sbin/nologin", TEXT)
        self.assertIn('passwd -l "$u"', TEXT)

    def test_acceptance_checks(self):
        for needle in ("snapshot_firewall", 'tier_state "$n"', 'probe_isolation "$n"', 'probe_isolation "$RUNNER_USER"',
                       'probe_isolation "$u"', 'op_step sandbox "$SANDBOX_PY"', 'op_step proxy "$PROXY_PY"',
                       "check_socket_groups", "check_groups", '"$LIB/factory_op.py" fetch', "HOSTS_PY",
                       "a request client with a fixed path fails closed"):
            self.assertIn(needle, TEXT)
        self.assertIn('((failed == 0)) || die "acceptance checks failed', TEXT)
        probe = function("probe_isolation")
        self.assertIn("tailscaled.sock", probe)
        self.assertIn("$PROBE_PORTS", probe)
        for needle in ("/run/dbus/system_bus_socket", "/run/systemd/resolve/io.systemd.Resolve", "AF_INET", "AF_NETLINK",
                       '${SECRET_FILES[@]+"${SECRET_FILES[@]}"}'):
            self.assertIn(needle, TEXT)
        # The proxy probe takes its hosts from the block, and its off-list hosts are never on it.
        self.assertIn('op_step proxy "$PROXY_PY" "$RUN/egress.sock" "$off_list" "${EGRESS[@]}"', TEXT)
        self.assertIn('for h in example.com example.org api.github.com; do [[ " ${EGRESS[*]} " == *" $h "* ]] ||', TEXT)
        # Another tier's command is run only when root owns it and nobody else can write it.
        self.assertIn("st.st_uid == 0 and not st.st_mode & 0o022", function("tier_state"))
        # The setup lock (fd 7) and the broker lock the probes hold (fd 9) are different descriptors.
        self.assertIn('exec 7> "$SETUP_LOCK"', TEXT)
        self.assertIn('exec 9>>"$RUN/broker.lock"', TEXT)

    def test_runner_files_are_read_as_the_runner(self):
        self.assertIn('runuser -u "$1" -- timeout 10 python3 -I', function("runner_field_is"))
        self.assertIn("os.O_NOFOLLOW | os.O_NONBLOCK", function("runner_field_is"))
        self.assertIn('runner_field_is "$RUNNER_USER" "$RUNNER_DIR/.runner" gitHubUrl "$RUNNER_URL"', TEXT)
        self.assertIn('runner_field_is "$n" "$home/actions-runner/.runner" agentName "$RUNNER_NAME"', TEXT)


# ---- the review's fixes: the lock across the install, live steps, the systemd floor, the sandbox probe ----------------

def stub_bin(tmp, name, script):
    d = pathlib.Path(tmp) / "bin"
    d.mkdir(exist_ok=True)
    (d / name).write_text("#!/bin/sh\n" + script)
    (d / name).chmod(0o755)
    return f"{d}:{os.environ['PATH']}"


def staged_main():
    return code()[code().index("WORK=$FACTORY_SETUP_STAGED"):]


class BrokerLockAcrossInstall(unittest.TestCase):
    """S4: setup holds the broker's own lock from before it installs anything until the broker's own fetch, so a gate's
    later steps never run a package swapped under them; and S1: it never installs beside a step that outlived its broker."""

    def test_the_lock_is_taken_before_the_install_and_given_back_before_the_brokers_fetch(self):
        main = staged_main()
        order = ['client_plan "$CLIENT"', 'install -d -m 755 -o root -g root "$RUN"', "umask 077", 'exec 9>>"$RUN/broker.lock"',
                 "umask 022", "flock -w 120 9 ||", "\nrefuse_live_steps\n", "\nclaim_tier\n", "useradd --create-home",
                 'nft -f "$NFT_FILE"', 'install_broker_files "$PROD" "$FACTORY" "$LIB"',
                 'render_broker_units ""', "runner_deps\n", 'op_step sandbox "$SANDBOX_PY"', 'op_step proxy "$PROXY_PY"',
                 "flock -u 9; exec 9>&-", '"$LIB/factory_op.py" fetch']
        positions = [main.index(x) for x in order]
        self.assertEqual(positions, sorted(positions))
        self.assertEqual(TEXT.count("exec 9>>"), 1)  # one lock, held across the install and the probes
        self.assertIn("a gate (or another broker command) is running. Nothing has changed", main)

    def run_live(self, listing, rc=0):
        with tempfile.TemporaryDirectory() as tmp:
            path = stub_bin(tmp, "systemctl", f"cat <<'OUT'\n{listing}OUT\nexit {rc}\n")
            return bash("TIER_NAME=factory-prod STEP_UNIT=factory-op-step\n" + function("refuse_live_steps")
                        + "refuse_live_steps\necho clear\n", path=path)

    def test_a_live_step_unit_stops_setup_naming_it(self):
        unit = "factory-op-step-20261105T120000Z-7-G1-a1-1.service"
        for listing, ok in (("", True), (f"{unit} loaded inactive dead x\n", True), (f"{unit} loaded failed failed x\n", True),
                            (f"{unit} loaded active running x\n", False), (f"{unit} loaded deactivating stop-sigterm x\n", False)):
            with self.subTest(listing=listing):
                r = self.run_live(listing)
                self.assertEqual(r.returncode == 0, ok, r.stderr)
                if not ok:
                    self.assertIn(unit, r.stderr)
                    self.assertIn("still running", r.stderr)

    def test_an_answer_setup_cant_read_stops_it(self):
        self.assertIn("can't ask systemd", self.run_live("", rc=1).stderr)
        self.assertIn("can't read", self.run_live("other.service loaded active running x\n").stderr)

    @needs_broker
    def test_the_unit_names_are_the_brokers(self):
        self.assertEqual(expected_names("")["STEP_UNIT"] + "-", broker().tier_names("factory-prod")["unit_prefix"])


class SystemdFloor(unittest.TestCase):
    """S2: a step's sandbox needs systemd 248 (PrivateIPC=); setup refuses an older one, clearly, before anything changes."""

    def check(self, version_line):
        with tempfile.TemporaryDirectory() as tmp:
            path = stub_bin(tmp, "systemctl", f"echo '{version_line}'\necho '+PAM +AUDIT'\n")
            return bash(function("check_systemd") + "check_systemd\n", path=path)

    def test_older_than_the_floor_is_refused_and_the_floor_and_newer_pass(self):
        for line, ok in (("systemd 247 (247.3-7+deb11u4)", False), ("systemd 248 (248.3-1ubuntu8)", True),
                         ("systemd 255 (255.4-1ubuntu8)", True), ("not systemd at all", False)):
            with self.subTest(line=line):
                r = self.check(line)
                self.assertEqual(r.returncode == 0, ok, r.stderr)
                if not ok:
                    self.assertTrue("systemd 248 or newer is required" in r.stderr or "can't read systemd's version" in r.stderr)

    @needs_broker
    def test_the_floor_is_the_brokers(self):
        self.assertEqual(int(assignment("SYSTEMD_FLOOR")), broker().SYSTEMD_FLOOR)

    def test_it_runs_before_anything_changes(self):
        boot = function("bootstrap_and_exec")
        self.assertLess(boot.index("check_systemd"), boot.index("install -d"))
        main = staged_main()
        self.assertLess(main.index("\ncheck_systemd\n"), main.index("\nclaim_tier\n"))


class SandboxProbe(unittest.TestCase):
    """S2: the acceptance probe proves the allowlist: no host socket answers (journald's among them, stream or datagram),
    the host's shared memory is unreadable, and /run holds only this tier's egress socket and the probe's directory."""

    def probe_source(self):
        m = re.search(r"^SANDBOX_PY=\$\(cat <<'PY'\n(.*?)\nPY\n\)", TEXT, re.S | re.M)
        self.assertIsNotNone(m)
        return m.group(1)

    def run_probe(self, **spec):
        """The probe's lines about `spec`, run here without its IP-family checks (outside a sandbox those always work, and
        AF_NETLINK is Linux's alone)."""
        families = 'for name in ("AF_INET", "AF_INET6", "AF_NETLINK", "AF_PACKET"):'
        source = self.probe_source()
        self.assertIn(families, source)
        full = {"uid": os.geteuid(), "sockets": [], "files": [], "dirs": [], "only": [], **spec}
        r = subprocess.run([sys.executable, "-I", "-c", source.replace(families, "for name in ():"), json.dumps(full)],
                           capture_output=True, text=True)
        self.assertEqual(r.stderr, "")
        return r.stdout.splitlines()

    def test_a_reachable_socket_of_either_kind_fails_it(self):
        import socket
        with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
            dgram, stream = os.path.join(tmp, "d.sock"), os.path.join(tmp, "s.sock")
            d = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
            d.bind(dgram)
            st = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            st.bind(stream)
            st.listen(1)
            try:
                for path in (dgram, stream):
                    with self.subTest(path=path):
                        self.assertEqual(self.run_probe(sockets=[path]), [f"FAILED    connect {path}: it worked"])
                absent = os.path.join(tmp, "absent.sock")
                self.assertEqual(self.run_probe(sockets=[absent]), [f"ok        connect {absent}: ENOENT"])
            finally:
                d.close()
                st.close()

    def test_anything_in_run_beyond_the_allowlist_fails_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = pathlib.Path(tmp)
            (run / "factory-prod").mkdir()
            self.assertEqual(self.run_probe(only=[[str(run), ["factory-prod"]]]), [f"ok        {run} holds only factory-prod"])
            (run / "systemd").mkdir()
            self.assertEqual(self.run_probe(only=[[str(run), ["factory-prod"]]]),
                             [f"FAILED    {run} holds systemd, beyond factory-prod"])
            self.assertEqual(self.run_probe(only=[[str(run / "absent"), []]]), [f"FAILED    list {run / 'absent'}: ENOENT"])

    def test_what_setup_probes(self):
        main = staged_main()
        for needle in ("/run/systemd/journal/socket", "/run/systemd/journal/stdout", "/dev/log", "/run/nscd/socket",
                       "/run/systemd/userdb/io.systemd.Multiplexer", "socket.SOCK_DGRAM", "shm_marker=/dev/shm/$TIER_NAME-probe-$$",
                       'files+=("$shm_marker")', "for d in /dev/shm /dev/mqueue", '"only": [["/run", [tier]]',
                       '[run, ["egress.sock", "steps"]]', '[run + "/steps", [probe]]'):
            self.assertIn(needle, main)
        self.assertIn('-p "BindPaths=$PROBE_DIR"', function("op_step"))
        self.assertNotIn("ReadWritePaths", code())

    @unittest.skipUnless(NOT_ROOT, "the print modes refuse root")
    def test_setups_steps_get_the_allowlist(self):
        with tempfile.TemporaryDirectory() as tmp:
            props = Scratch(tmp).step_props()
        self.assertEqual(props["TemporaryFileSystem"], "/run:ro")
        self.assertEqual(props["PrivateIPC"], "yes")
        self.assertEqual(props["BindReadOnlyPaths"], "/run/factory-prod/egress.sock")
        hidden = props["InaccessiblePaths"].split()
        self.assertIn("-/dev/shm", hidden)
        self.assertIn("-/dev/mqueue", hidden)


class EgressLoopback(unittest.TestCase):
    """S6: the egress user reaches nothing on this host, its own public addresses included (they go out on lo)."""

    @unittest.skipUnless(NOT_ROOT, "the render mode refuses root")
    def test_the_egress_chain_rejects_lo_before_it_accepts_443(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Scratch(pathlib.Path(tmp) / "c").render(pathlib.Path(tmp) / "out")
            nft = (root / "etc/factory-runner/prod-firewall.nft").read_text()
        egress = re.search(r"chain egress_out \{\n(.*?)\n  \}", nft, re.S).group(1)
        self.assertIn('oifname "lo" counter reject', egress)
        self.assertLess(egress.index('oifname "lo"'), egress.index("tcp dport 443 accept"))

    def test_acceptance_probes_it(self):
        main = staged_main()
        self.assertIn('nft list chain inet "$NFT_TABLE" egress_out', main)
        self.assertIn('grep -q \'oifname "lo" .*reject\' <<< "$egress_chain"', main)  # no pipe: pipefail
        self.assertIn('connects "$EGRESS_USER" "$ip" 443', main)


class ConfigAgainstFactory(unittest.TestCase):
    """C3: the environment the broker checks approvals in, and its release branch, are factory.json's."""

    def run_check(self, cfg, env="factory-production", release="release/production"):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "config.json"
            path.write_text(json.dumps(cfg))
            return bash(f"PROD_ENVIRONMENT={env}\nFACTORY_RELEASE_BRANCH={release}\n" + function("config_matches_factory")
                        + f"config_matches_factory {path}\n")

    def test_matching_settings_pass(self):
        self.assertEqual(self.run_check({"release_branch": "release/production"}).returncode, 0)
        r = self.run_check({"release_branch": "release/production", "environment": "prod-gate"}, env="prod-gate")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_a_different_environment_or_release_branch_is_refused(self):
        cases = (
            ({"release_branch": "release/production"}, "prod-gate", "release/production", "Set config.json's environment"),
            ({"release_branch": "release/production", "environment": "prod-gate"}, "factory-production", "release/production",
             "environments.production is 'factory-production'"),
            ({"release_branch": "release/live"}, "factory-production", "release/production", "release.branch is 'release/production'"),
            ({"release_branch": "release/production"}, "factory-production", "", "the fallback"),
        )
        for cfg, env, release, why in cases:
            with self.subTest(why=why):
                r = self.run_check(cfg, env, release)
                self.assertEqual(r.returncode, 1, r.stdout)
                self.assertIn(why, r.stderr)

    def test_factory_read_gives_the_release_branch(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "factory.json"
            for release, want in (({"branch": "release/production"}, "RELEASE=release/production"), (None, "RELEASE="),
                                  ({"branch": ""}, "RELEASE=")):
                cfg = dict(FACTORY_JSON)
                if release is None:
                    cfg.pop("release")
                else:
                    cfg["release"] = release
                path.write_text(json.dumps(cfg))
                r = bash(function("factory_read") + f"factory_read {path}\n")
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertIn(want + "\n", r.stdout)
            path.write_text(json.dumps({**FACTORY_JSON, "release": {"branch": "a b"}}))
            self.assertIn("release.branch must be a branch name", bash(function("factory_read") + f"factory_read {path}\n").stderr)

    def test_it_is_checked_before_anything_changes(self):
        main = staged_main()
        self.assertLess(main.index('config_matches_factory "$PROD/config.json"'), main.index("\nclaim_tier\n"))

    @needs_broker
    def test_the_default_is_the_brokers(self):
        self.assertIn('cfg.get("environment", "factory-production")', function("config_matches_factory"))
        self.assertEqual(broker().ENVIRONMENT, "factory-production")


class ConfigCopies(unittest.TestCase):
    """S3: config.json is installed twice from one staged blob: in the library, where the broker reads it and the digest
    covers it, and in /etc, where other tiers find this one."""

    def test_both_copies_come_from_the_staged_blob(self):
        main = staged_main()
        self.assertIn('"$prod/config.json"', function("install_broker_files"))
        self.assertIn('install -m 644 -o root -g root "$PROD/config.json" "$ETC/config.json"', main)
        self.assertLess(main.index('install_broker_files "$PROD"'), main.index('"$PROD/config.json" "$ETC/config.json"'))
        # Discovery and the takeover check still read the /etc copy.
        self.assertIn('"$HOST_ROOT"/etc/factory-prod*/config.json', function("discover_tiers"))
        self.assertIn('"$HOST_ROOT$ETC/config.json"', function("check_names_free"))


class Tooling(unittest.TestCase):
    @unittest.skipUnless(shutil.which("shellcheck"), "shellcheck is not installed")
    def test_shellcheck_is_clean(self):
        r = subprocess.run(["shellcheck", "-x", str(SCRIPT)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_bash_parses(self):
        r = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    @unittest.skipUnless(NOT_ROOT, "running as root")
    def test_refuses_without_root(self):
        env = {k: v for k, v in os.environ.items() if k not in CONF_KEYS + OVERRIDES}
        r = subprocess.run(["bash", str(SCRIPT)], capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 1)
        self.assertIn("run as root", r.stderr)


if __name__ == "__main__":
    unittest.main()
