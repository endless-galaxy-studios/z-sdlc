"""The browser route for a stage's sandbox (process/factory.md, D6).

Usage: python3 -I browser.py <factory.json> <stage> <workspace> <settings> <conf-out>

Run by agent_job.sh browser, outside the sandbox, after the project's dependencies are installed and before the
agent starts. When factory.json's browser block names a browser host and lists the stage (smoke always counts):
- finds the project's Playwright client (browser.client, or stack.node, below the workspace) and its version: the
  browser host serves Playwright 1.<minor> on one front-end port, port_base + minor, since a client's major.minor
  must match its server's;
- adds that one address and port to the stage's sandbox settings (network.allowedDomains, as "<host>:<port>"), so
  the sandbox's proxy lets a sandboxed command reach that front end and nothing else on the host;
- adds each outside host CD approved for the browser route (browser.allow: one host each, port 443, with why and who
  decided it; D6 rule 6) to the same list, so a sandboxed command can fetch from it through the proxy;
- writes <conf-out> (host, port, version, the client's directory, the allowed hosts, the first one's probe path
  for factory-smoke, and video: 1 for the stages whose reproducing and verifying runs record video, 0 for smoke),
  which with-browser reads.
Otherwise it changes nothing and says why: with no browser.conf, with-browser reports the browser host unavailable,
and a stage reports `blocked`, never that a bug was reproduced or ruled out.

The route is the strict tier's one network opening (D6). The runner host's firewall must allow the same address
and ports (host.conf's STRICT_BROWSER_HOST and STRICT_BROWSER_PORTS); when they disagree, the connection is
refused. That holds because the address must be a private or tailnet one, which the firewall otherwise rejects: a
public address would be reached as the internet is, so it's refused here. Nothing relies on the route until factory-smoke's browser-host job passes: a stage gets it only once CD
lists it in browser.stages.
"""

import ipaddress
import json
import pathlib
import re
import sys

STAGES = {"reproduce", "implement", "execute", "revise"}
CLIENTS = ("@playwright/test", "playwright", "playwright-core")
VERSION = re.compile(r"1\.(\d{1,2})\.\d+(-[0-9A-Za-z.-]+)?")
KEYS = {"_doc", "host", "port_base", "gpu", "stages", "client", "allow"}
# The ranges the strict tier's firewall rejects but for this opening (host/setup.sh's blocked4, less loopback and the
# like): a browser host anywhere else would be reached without the firewall's say.
PRIVATE = [ipaddress.IPv4Network(n) for n in ("10.0.0.0/8", "100.64.0.0/10", "172.16.0.0/12", "192.168.0.0/16")]
ALLOW_KEYS = {"host", "why", "decided"}
# An entry's optional probe: a path on the host that answers 2xx to a GET, which factory-smoke fetches from the first
# entry (D6 rule 4). Plain path and query characters only, since it becomes a browser.conf line and a URL.
ALLOW_PROBE = re.compile(r"/[A-Za-z0-9._~%/+-]{0,400}(\?[A-Za-z0-9._~%&=+/-]{0,400})?")
# One plain hostname: no wildcard, port, scheme or address (an address would pass the sandbox's own address checks).
ALLOW_HOST = re.compile(r"(?=.{1,253}\Z)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}")
# Names that mean this machine or the local network. The strict tier's firewall rejects private addresses and the
# sandbox's proxy loopback ones, whatever a name resolves to; these are refused here so a review never has to ask.
LOCAL_NAME = re.compile(r"(^|\.)(localhost|localdomain|local|internal|lan|home\.arpa|nip\.io|sslip\.io)\Z")


class Invalid(Exception):
    pass


def block(factory):
    """factory.json's browser block, validated: None when there's no browser host (the route is off)."""
    b = factory.get("browser")
    if b is None:
        return None
    if not isinstance(b, dict) or set(b) - KEYS:
        raise Invalid(f"factory.json's browser block takes only {sorted(KEYS - {'_doc'})}")
    host = b.get("host", "")
    if host in ("", None):
        return None
    try:
        if not isinstance(host, str) or ipaddress.IPv4Address(host).version != 4 or host != str(ipaddress.IPv4Address(host)):
            raise ValueError
    except ValueError:
        raise Invalid(f"browser.host must be one IPv4 address, as host.conf's STRICT_BROWSER_HOST: got {host!r}")
    if not any(ipaddress.IPv4Address(host) in n for n in PRIVATE):
        raise Invalid(f"browser.host must be a private or tailnet address (10/8, 100.64/10, 172.16/12, 192.168/16), "
                      f"which the strict tier's firewall rejects but for this opening: got {host!r}")
    base = b.get("port_base", 3100)
    if not isinstance(base, int) or isinstance(base, bool) or not 1024 <= base <= 65435:
        raise Invalid(f"browser.port_base must be a whole number from 1024 to 65435: got {base!r}")
    stages = b.get("stages", [])
    if not isinstance(stages, list) or not set(stages) <= STAGES:
        raise Invalid(f"browser.stages lists only {sorted(STAGES)}: got {stages!r}")
    gpu = b.get("gpu", True)
    if not isinstance(gpu, bool):
        raise Invalid("browser.gpu must be true or false")
    client = b.get("client")
    if client is not None and (not isinstance(client, str) or not client or client.startswith("/") or ".." in client.split("/")):
        raise Invalid(f"browser.client must be a directory below the repository: got {client!r}")
    allow = b.get("allow", [])
    if not isinstance(allow, list):
        raise Invalid("browser.allow must be a list")
    hosts = []
    for entry in allow:
        if not isinstance(entry, dict) or not ALLOW_KEYS <= set(entry) <= ALLOW_KEYS | {"probe"} \
                or not all(isinstance(entry[k], str) and entry[k].strip() for k in ALLOW_KEYS):
            raise Invalid('each browser.allow entry is {"host", "why", "decided"}, each one written out, and optionally '
                          '"probe" (D6 rule 6)')
        if "probe" in entry and not (isinstance(entry["probe"], str) and ALLOW_PROBE.fullmatch(entry["probe"])):
            raise Invalid(f"browser.allow's probe is a path on the host, starting with /: got {entry['probe']!r}")
        if not ALLOW_HOST.fullmatch(entry["host"]) or LOCAL_NAME.search(entry["host"]) or entry["host"] in hosts:
            raise Invalid(f"browser.allow names one plain hostname per entry, once: got {entry['host']!r}")
        hosts.append(entry["host"])
    probe = allow[0].get("probe", "") if allow else ""
    return {"host": host, "port_base": base, "stages": stages, "gpu": gpu, "client": client, "allow": hosts,
            "probe": probe}


def client_version(directory):
    """The version of the project's Playwright client installed in <directory>/node_modules, or None."""
    for name in CLIENTS:
        try:
            data = json.loads((directory / "node_modules" / name / "package.json").read_text())
        except (OSError, ValueError):
            continue
        version = data.get("version") if isinstance(data, dict) else None
        if isinstance(version, str):
            return version
    return None


def route(factory, stage, workspace):
    """(host, port, version, client directory, allowed hosts) for the stage, or (None, why) when the route is off."""
    b = block(factory)
    if b is None:
        return None, "factory.json names no browser host"
    if stage != "smoke" and stage not in b["stages"]:
        return None, f"browser.stages doesn't list {stage} (factory-smoke's browser-host job must pass first)"
    rel = b["client"] or (factory.get("stack") or {}).get("node") or "."
    directory = (workspace / rel).resolve()
    if workspace.resolve() not in (directory, *directory.parents):
        raise Invalid(f"the Playwright client's directory {rel!r} is outside the workspace")
    version = client_version(directory)
    if version is None:
        return None, f"no Playwright client installed in {rel} ({', '.join(CLIENTS)})"
    m = VERSION.fullmatch(version)
    if not m:
        raise Invalid(f"Playwright {version} isn't a 1.x release, which the browser host serves")
    port = b["port_base"] + int(m.group(1))
    return (b["host"], port, version, str(directory), b["allow"]), None


def add_route(settings, host, port, allow=()):
    out = json.loads(json.dumps(settings))
    network = out.setdefault("sandbox", {}).setdefault("network", {})
    allowed = list(network.get("allowedDomains", []))
    for entry in [f"{host}:{port}"] + [f"{h}:443" for h in allow]:
        if entry not in allowed:
            allowed.append(entry)
    network["allowedDomains"] = allowed
    return out


def main():
    factory_path, stage, workspace, settings_path, conf_path = sys.argv[1:6]
    if stage != "smoke" and stage not in STAGES:
        print(f"::error::browser: unknown stage {stage!r}")
        return 2
    try:
        factory = json.loads(pathlib.Path(factory_path).read_text())
        found, why = route(factory, stage, pathlib.Path(workspace))
        if found is None:
            print(f"browser route for {stage}: off ({why})")
            # The smoke job exists to prove the route: being unable to build it there is a failure.
            return 1 if stage == "smoke" and "no browser host" not in why else 0
        host, port, version, client, allow = found
        settings = json.loads(pathlib.Path(settings_path).read_text())
        pathlib.Path(settings_path).write_text(json.dumps(add_route(settings, host, port, allow), indent=2) + "\n")
        conf = pathlib.Path(conf_path)
        conf.parent.mkdir(parents=True, exist_ok=True)
        b = block(factory)
        conf.write_text(f"host={host}\nport={port}\nport_base={b['port_base']}\nversion={version}\n"
                        f"client={client}\nallow={' '.join(allow)}\nprobe={b['probe']}\n"
                        f"video={0 if stage == 'smoke' else 1}\n")
        conf.chmod(0o644)
    except (Invalid, OSError, ValueError) as e:
        print(f"::error::browser: {e}")
        return 1
    print(f"browser route for {stage}: {host}:{port} (Playwright {version})"
          + (f"; outside hosts CD allowed: {', '.join(allow)}" if allow else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
