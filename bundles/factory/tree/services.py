"""External services for factory agents (.github/factory/services.json; README § Services).

Usage: python3 -I services.py <services.json> <stage> <base-settings> <out-settings> <context-out> <mcp-config>

Builds a stage's sandbox settings from a frozen base file plus the services that stage may use, writes
a non-secret services context for the agent, and adds MCP servers to the MCP config. Credentials sit
in fixed slots, GitHub secrets the agent step's env references literally (a workflow can't name a secret
at runtime): FACTORY_SVC_1..4 for the planning stages (plan, spec; the factory-planning environment's
secrets) and FACTORY_EXEC_SVC_1..2 for the execution stages (implement, execute, revise; repository
secrets). The slot values never pass through this script.

- env services (planning only): the slot is masked in the Bash sandbox (sandboxed commands see a
  placeholder) and the proxy injects the real value only on requests to the service's domains, which
  are allowed.
- mcp services: an HTTP MCP server in the main process's config with the slot in its Authorization
  header, as Context7 has its key. The sandbox never sees the value. The header is Authorization and
  nothing else: Node's fetch, which the MCP client is built on, drops Authorization on a redirect to
  another origin but keeps a custom header, so the credential reaches no URL but the configured one.
  The tools the agent may call are the entry's `tools` (all the server's when an entry gives none, for
  planning only): they go into the settings' permissions.allow, and auto mode can't prompt for others.
- Every slot is masked in every run, configured or not, so a secret set for a service another stage
  uses never reaches sandboxed Bash in plain text (the env scrub only strips credential-shaped names).
- A service is wired only for the stages it lists, and an entry's stages come from one tier: planning
  credentials never reach a strict-tier job (process/factory.md, D3). An execution entry must be an mcp
  service with a tools list (CD 2026-11-05; planning-only before, CD 2026-10-10).
- Masking limits where a credential goes, not what it can do: every entry must declare read_only, CD's
  attestation that the credential itself is read-only at its source (the key can't write on the server,
  a database login has only SELECT; a service's own read-only mode or a tools list isn't enough, D2 rule
  8). A response that echoes request headers back would show the agent the real value, so never point a
  real credential at one.
"""

import json
import pathlib
import re
import sys

SLOTS = [f"FACTORY_SVC_{n}" for n in range(1, 5)]
EXEC_SLOTS = [f"FACTORY_EXEC_SVC_{n}" for n in range(1, 3)]
STAGES = {"plan", "spec"}
EXEC_STAGES = {"implement", "execute", "revise"}
NAME = re.compile(r"^[a-z][a-z0-9-]{0,30}$")
TOOL = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
HOST = re.compile(r"^(\*\.)?([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")


class Invalid(Exception):
    pass


def load(path):
    """services.json, validated. Raises Invalid with the reason."""
    try:
        data = json.loads(pathlib.Path(path).read_text())
    except (OSError, ValueError) as e:
        raise Invalid(f"can't read {path}: {e}")
    services = data.get("services") if isinstance(data, dict) else None
    if not isinstance(services, list) or set(data) != {"services"}:
        raise Invalid('services.json must be {"services": [...]}')
    names, slots = set(), set()
    for s in services:
        if not isinstance(s, dict):
            raise Invalid("each service must be an object")
        name = s.get("name")
        if not isinstance(name, str) or not NAME.match(name) or name in names:
            raise Invalid(f"bad or duplicate service name {name!r}")
        names.add(name)
        where = f"service {name}"
        allowed = {"name", "stages", "slot", "attach", "read_only", "domains", "auth"} if s.get("attach") == "env" \
            else {"name", "stages", "slot", "attach", "read_only", "url", "header", "prefix", "tools"}
        if set(s) - allowed:
            raise Invalid(f"{where}: unknown fields {sorted(set(s) - allowed)}")
        stages = s.get("stages")
        if not isinstance(stages, list) or not stages or not (set(stages) <= STAGES or set(stages) <= EXEC_STAGES):
            raise Invalid(f"{where}: stages must be a non-empty subset of {sorted(STAGES)} (planning) or of "
                          f"{sorted(EXEC_STAGES)} (execution), never both")
        execution = set(stages) <= EXEC_STAGES
        tier_slots = EXEC_SLOTS if execution else SLOTS
        slot = s.get("slot")
        if slot not in tier_slots or slot in slots:
            raise Invalid(f"{where}: slot must be one of {tier_slots}, each used once")
        slots.add(slot)
        if s.get("read_only") is not True:
            raise Invalid(f"{where}: read_only must be true (the credential is read-only at its source; masking "
                          f"limits where it goes, not what it can do)")
        if execution and s.get("attach") != "mcp":
            raise Invalid(f"{where}: an execution stage's service must be attach mcp (Bash runs agent-written code)")
        if "tools" in s or execution:
            tools = s.get("tools")
            if not isinstance(tools, list) or not tools or not all(isinstance(t, str) and TOOL.match(t) for t in tools) \
                    or len(set(tools)) != len(tools):
                raise Invalid(f"{where}: tools must be a non-empty list of distinct tool names"
                              f"{' (required for an execution stage)' if execution else ''}")
        if s.get("attach") == "env":
            domains = s.get("domains")
            if not isinstance(domains, list) or not domains or not all(isinstance(d, str) and HOST.match(d) for d in domains):
                raise Invalid(f"{where}: domains must be host names (a leading *. is allowed; no bare *)")
            if not isinstance(s.get("auth", ""), str) or len(s.get("auth", "")) > 200:
                raise Invalid(f"{where}: auth must be a short description of how to send the credential")
        elif s.get("attach") == "mcp":
            url = s.get("url")
            if not isinstance(url, str) or not re.match(r"^https://[a-z0-9.-]+(:[0-9]+)?(/[\w./-]*)?$", url):
                raise Invalid(f"{where}: url must be an https URL")
            if s.get("header") != "Authorization":
                raise Invalid(f"{where}: header must be Authorization (fetch drops it on a redirect to another "
                              f"origin; it keeps any other header)")
            if not isinstance(s.get("prefix", ""), str) or not re.match(r"^[A-Za-z]{0,20} ?$", s.get("prefix", "")):
                raise Invalid(f"{where}: prefix must be a short scheme such as 'Bearer '")
        else:
            raise Invalid(f"{where}: attach must be env or mcp")
    return services


def for_stage(services, stage):
    return [s for s in services if stage in s["stages"]]


def mcp_tools(services, stage):
    """The MCP tools the stage's agent may call: each entry's tools, or its whole server when it lists none."""
    names = []
    for s in for_stage(services, stage):
        if s["attach"] == "mcp":
            names += [f"mcp__{s['name']}__{t}" for t in s["tools"]] if s.get("tools") else [f"mcp__{s['name']}"]
    return names


def settings(base, services, stage):
    """The stage's sandbox settings: the base, every slot masked, env services' domains allowed and
    injected, and the stage's MCP tools allowed."""
    out = json.loads(json.dumps(base))
    sandbox = out.setdefault("sandbox", {})
    network = sandbox.setdefault("network", {})
    creds = sandbox.setdefault("credentials", {})
    every = SLOTS + EXEC_SLOTS
    env_vars = [v for v in creds.get("envVars", []) if v.get("name") not in every]
    wired = {s["slot"]: s for s in for_stage(services, stage) if s["attach"] == "env"}
    for slot in every:
        hosts = wired[slot]["domains"] if slot in wired else []
        env_vars.append({"name": slot, "mode": "mask", "injectHosts": hosts})
    creds["envVars"] = env_vars
    if wired:
        allowed = list(network.get("allowedDomains", []))
        for s in wired.values():
            allowed += [d for d in s["domains"] if d not in allowed]
        network["allowedDomains"] = allowed
        network.setdefault("tlsTerminate", {})
    tools = mcp_tools(services, stage)
    if tools:
        allow = out.setdefault("permissions", {}).setdefault("allow", [])
        allow += [t for t in tools if t not in allow]
    return out


def context(services, stage):
    """What the agent may know: names, how to call them, which variable to use. No values."""
    entries = []
    for s in for_stage(services, stage):
        if s["attach"] == "env":
            entries.append({"name": s["name"], "variable": s["slot"], "domains": s["domains"],
                            "how": s.get("auth", "") or f"send ${s['slot']} as the service's credential",
                            "note": "the variable holds a placeholder; the proxy swaps in the real value "
                                    "only on requests to these domains"})
        else:
            entries.append({"name": s["name"], "mcp_server": s["name"], "tools": s.get("tools", []),
                            "note": "use its MCP tools (the listed ones, or all of the server's when none are listed); "
                                    "its credential never reaches the sandbox"})
    return {"services": entries}


def mcp_servers(services, stage):
    return {s["name"]: {"type": "http", "url": s["url"],
                        "headers": {s["header"]: f"{s.get('prefix', '')}${{{s['slot']}}}"}}
            for s in for_stage(services, stage) if s["attach"] == "mcp"}


def main():
    path, stage, base_path, out_path, context_path, mcp_path = sys.argv[1:7]
    try:
        services = load(path)
        base = json.loads(pathlib.Path(base_path).read_text())
        pathlib.Path(out_path).write_text(json.dumps(settings(base, services, stage), indent=2) + "\n")
        pathlib.Path(context_path).write_text(json.dumps(context(services, stage), indent=2) + "\n")
        mcp = json.loads(pathlib.Path(mcp_path).read_text())
        extra = mcp_servers(services, stage)
        clash = set(extra) & set(mcp.get("mcpServers", {}))
        if clash:
            raise Invalid(f"service names clash with existing MCP servers: {sorted(clash)}")
        mcp.setdefault("mcpServers", {}).update(extra)
        pathlib.Path(mcp_path).write_text(json.dumps(mcp) + "\n")
    except (Invalid, OSError, ValueError) as e:
        print(f"::error::services: {e}")
        return 1
    wired = [s["name"] for s in for_stage(services, stage)]
    print(f"services for {stage}: {', '.join(wired) or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
