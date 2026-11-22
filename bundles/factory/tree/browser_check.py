"""Judge browser_probe.mjs output: factory-smoke's browser-host job (process/factory.md, D6).

Usage:
  python3 -I browser_check.py control <output> [gpu|nogpu] [<first browser.allow host, or "">]
  python3 -I browser_check.py agent <output> [gpu|nogpu] [<first browser.allow host, or "">]

both:    the probe connected to the browser host's front end through with-browser. The browser loaded the app the
         probe started on its own command's loopback, with its WebSocket. WebGL renders on the GPU (unless the
         project's browser block says the host has none). A screenshot, the trace and the video came back to the
         client. The forced flags (the resolver rule, exactly once, and the WebRTC policy) are on the browser's command
         line. A context's own proxy, by address and by name, is refused. A page reaching the host's loopback (shown
         by plain HTTP answering on the run-servers' ports) opens no WebSocket to a run-server. A second client asking
         for another browser, its own launch options and loopback only, in its headers and its query, gets the
         forced Chromium and flags and none of its own. Given the project's first allowed outside host
         (browser.allow), Node's fetch reaches it, through the sandbox's proxy in the agent run: the path a project's
         route helper depends on. With the entry's probe path, the probe's GET of it must answer 2xx, so the host
         serves what specs fetch; without one, any answer to a HEAD of its root counts. With none allowed, the probe
         says so.
control: run outside the sandbox, with network and a canary credential in its environment (never a real token:
         it runs the project's own Playwright). The outside world, by name and by address, must answer through the
         tunnel, and the canary must be found, which proves the agent run's refusals and its clean environment are
         the sandbox's doing, not a broken check.
agent:   run as sandboxed agent Bash, under the implement stage's sandbox with the route added. The outside world
         must be refused, and no credential seen, by name or by value. The sandbox's proxy must refuse the browser
         host's next port, since the stage's sandbox allows the one front end's port.

The job copies this file out of the workspace before the agent runs.
"""

import os
import secrets
import sys

BOTH = {
    "connect": "ok",
    "app": "loaded",
    "websocket": "echoed",
    "screenshot": "png",
    "trace": "zip",
    "video": "webm",
    "flags": "present",
    "proxy-ip": "refused",
    "proxy-name": "refused",
    "loopback": "reached",
    "runserver-ws": "none",
    "hostile": "replaced",
}
CONTROL = {"outside-name": "reached", "outside-ip": "reached", "credentials": "found", "narrow": "unchecked"}
AGENT = {"outside-name": "refused", "outside-ip": "refused", "credentials": "clean", "narrow": "refused"}
WHY = {
    "connect": "the client could not connect to the browser host",
    "app": "the browser did not load the app from the client's loopback",
    "websocket": "the app's WebSocket did not round-trip through the tunnel",
    "screenshot": "no screenshot came back",
    "trace": "no trace came back",
    "video": "no video came back",
    "flags": "the forced Chrome flags are not on the browser's command line",
    "proxy-ip": "a context proxy by address reached the outside world",
    "proxy-name": "a context proxy by name reached the outside world",
    "loopback": "the page didn't reach the run-servers' ports on the host's loopback, so the WebSocket check below "
                "proves nothing (the ports moved, or the bypass no longer reaches loopback)",
    "runserver-ws": "a page opened a WebSocket to a run-server on the host's loopback",
    "hostile": "the browser host honoured a client's own browser or launch options",
    "narrow": "the sandbox's proxy didn't refuse the browser host's next port",
    "gpu": "WebGL renders in software",
    "allowed": "Node's fetch didn't reach the project's allowed outside host (browser.allow): a spec's context.route "
               "helper can't serve it",
}


def results(lines):
    """{check: (result, detail)} from the probe's lines, up to its end marker; a repeated check keeps its first."""
    seen = {}
    for line in lines:
        parts = line.split(" ", 2)
        if len(parts) >= 2 and parts[0] not in seen and parts[0] not in ("secret", "env-name"):
            seen[parts[0]] = (parts[1], parts[2] if len(parts) > 2 else "")
    return seen


def judge(lines, mode, gpu=True, allow=None):
    """allow: the project's first browser.allow host ("" when it has none), or None to leave the check out."""
    failures = []
    got = results(lines)
    if allow is not None:
        want_allowed, detail = ("reached", allow) if allow else ("none", "")
        if "allowed" not in got:
            failures.append("probe output has no 'allowed' line")
        elif got["allowed"][0] != want_allowed or (allow and got["allowed"][1].split(" ", 1)[0] != allow):
            reason = WHY["allowed"] if allow else "the probe saw an allowed host, but factory.json's browser.allow has none"
            if allow and got["allowed"][0] == "answered":
                reason = ("the project's allowed outside host answered browser.allow's probe path with a status other "
                          "than 2xx: it doesn't serve what the specs fetch")
            failures.append(f"{reason}: {got['allowed'][0]} {got['allowed'][1]}".rstrip())
    want = dict(BOTH, **(CONTROL if mode == "control" else AGENT))
    for check, result in want.items():
        if check not in got:
            failures.append(f"probe output has no '{check}' line")
        elif got[check][0] != result:
            detail = got[check][1]
            reason = WHY.get(check) or f"{check}: expected {result}"
            if mode == "control" and check in CONTROL:
                reason = {"outside-name": "the control could not reach the outside world by name through the tunnel",
                          "outside-ip": "the control could not reach the outside world by address through the tunnel",
                          "credentials": "the control did not see its canary credential, so a clean agent run proves nothing",
                          "narrow": "the control ran behind a proxy, so it wasn't outside the sandbox"}[check]
            elif mode == "agent" and check in ("outside-name", "outside-ip"):
                reason = f"the sandboxed client reached the outside world through the browser ({check})"
            elif mode == "agent" and check == "credentials":
                reason = "a credential is visible to sandboxed Bash"
            failures.append(f"{reason}: {got[check][0]} {detail}".rstrip())
    if gpu:
        if "gpu" not in got:
            failures.append("probe output has no 'gpu' line")
        elif got["gpu"][0] != "hardware":
            failures.append(f"{WHY['gpu']}: {got['gpu'][1]}")
    if mode == "agent":
        failures += [f"credential visible: {l}" for l in lines if l.startswith(("secret ", "env-name "))]
    elif not any(l.startswith("secret env ") for l in lines):
        failures.append("the control found no token by value in its environment")
    if "probe" in got:
        failures.append(f"the probe crashed: {got['probe'][1]}")
    return failures


def main():
    mode, path = sys.argv[1], sys.argv[2]
    gpu = (sys.argv[3] if len(sys.argv) > 3 else "gpu") != "nogpu"
    allow = sys.argv[4] if len(sys.argv) > 4 else None
    if mode not in ("control", "agent"):
        print(f"::error::unknown mode {mode!r}: control or agent")
        return 2
    shown = open(path).read().splitlines()
    failures = []
    # Claude Code appends its own notes after a command's output: judge the probe's lines up to its end marker.
    if "end" in shown:
        lines = shown[:shown.index("end") + 1]
    else:
        lines = shown
        failures.append("probe output is incomplete (no end marker)")
    if any(l.startswith("UNAVAILABLE: browser host") for l in shown):
        failures.append("with-browser found no browser host: " + next(l for l in shown if l.startswith("UNAVAILABLE")))
    failures += judge(lines, mode, gpu, allow)

    # The output is agent-influenced: stop workflow-command parsing and fence it safely.
    token = secrets.token_hex(16)
    fence = "~" * max([3] + [len(l.lstrip(" ")) - len(l.lstrip(" ").lstrip("~")) + 1 for l in shown])
    body = [f"### Browser host probe ({mode}): {'FAILED' if failures else 'passed'}", "",
            fence, *shown, fence, "", *[f"- {f}" for f in failures]]
    print(f"::stop-commands::{token}")
    print("\n".join(body))
    print(f"::{token}::")
    for f in failures:
        print(f"::error::{f}")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as s:
            s.write("\n".join(body) + "\n")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
