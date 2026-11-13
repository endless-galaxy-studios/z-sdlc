#!/usr/bin/env python3
"""Create the factory's GitHub App from its manifest (z-sdlc process/factory.md, Enablement step 5).

    python3 .github/factory/create_app.py <organization> [--name NAME] [--key-out PATH]
    python3 .github/factory/create_app.py <organization> --runners [--name NAME] [--key-out PATH]
    python3 .github/factory/create_app.py <organization> --auditor [--name NAME] [--key-out PATH]
    python3 .github/factory/create_app.py <organization> --sessions [--name NAME] [--key-out PATH]

Opens GitHub's create-an-App page for the organization with the factory's manifest filled in (a local
page posts it); you confirm it there. GitHub sends the browser back to this script, which converts the
result into the App's private key (written to --key-out, mode 600; by default in your home directory,
outside any checkout) and client ID, writes the App's bot
user into factory.json, and prints the install link and the commands that store the key and the client
ID in the factory-writer environment. The App gets exactly the permissions bootstrap.py checks for
(contents, issues and pull requests write, metadata read) and no webhook. Standard library only.

--runners creates the CI tier's runner-registration App instead (process/factory.md, Enablement step 10, The CI
tier). Its one permission is the organization's self-hosted runners, and GitHub has no narrower one that registers
runners: it reaches every runner group in the organization (registering runners into any of them, moving runners,
changing a group's restrictions). So its key goes to the runner host root-only, never into a checkout, and every
other copy is deleted. factory.json is left alone.

--auditor creates the runner audit's App instead (process/factory.md, Enablement step 12, The runner audit): read
access to the organization's self-hosted runners, nothing else. runner_audit.py's workflow uses it from one
repository, on GitHub-hosted runners only, so its key goes into that repository's secrets and nowhere else.
factory.json is left alone.

--sessions creates the sessions App instead (process/factory.md, Enablement step 13): the identity Claude Code
sessions on CD's machine work as in the product's repositories (session_identity.py). It may write contents, pull
requests and issues and read Actions, checks and statuses; never workflows, administration, secrets or
environments, which are infra and setup, CD's own login. Its key stays on CD's machine (by default
~/.config/agent-sessions/<organization>.pem). factory.json is left alone.
"""
import argparse
import html
import http.server
import json
import os
import pathlib
import re
import secrets
import subprocess
import sys
import threading
import urllib.parse
import urllib.request
import webbrowser

import session_identity

FACTORY = pathlib.Path(__file__).resolve().parent
API = "https://api.github.com"
PERMISSIONS = {"contents": "write", "issues": "write", "pull_requests": "write", "metadata": "read"}
RUNNER_PERMISSIONS = {"organization_self_hosted_runners": "write"}
AUDITOR_PERMISSIONS = {"organization_self_hosted_runners": "read"}
SESSIONS_PERMISSIONS = dict(session_identity.SESSION_PERMISSIONS)


def manifest(name, org, port, permissions=PERMISSIONS):
    """The App as the factory needs it: private, no webhook, nothing beyond its permissions."""
    return {"name": name, "url": f"https://github.com/{org}", "public": False,
            "redirect_url": f"http://127.0.0.1:{port}/created",
            "default_permissions": dict(permissions), "default_events": []}


def page(org, state, app_manifest):
    """The local page that posts the manifest to GitHub's create-an-App form for the organization."""
    action = f"https://github.com/organizations/{urllib.parse.quote(org)}/settings/apps/new?state={state}"
    return (f'<!doctype html><meta charset="utf-8"><title>Create the factory App</title>'
            f'<form id="f" method="post" action="{html.escape(action)}">'
            f'<input type="hidden" name="manifest" value="{html.escape(json.dumps(app_manifest))}">'
            f'<p>Sending the factory App\'s manifest to GitHub. <button>Continue</button></p></form>'
            f'<script>document.getElementById("f").submit()</script>')


def request(method, url, data=None):
    req = urllib.request.Request(url, data=data, method=method, headers={"Accept": "application/vnd.github+json",
                                                                          "User-Agent": "z-sdlc-factory"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def convert(code, call=request):
    """GitHub's half of the manifest flow: the App's id, slug, client ID and private key."""
    return call("POST", f"{API}/app-manifests/{urllib.parse.quote(code)}/conversions", b"")


def bot_user_id(slug, call=request):
    return call("GET", f"{API}/users/{urllib.parse.quote(slug + '[bot]')}")["id"]


def write_app(factory_json, slug, user_id):
    """Set factory.json's app.user_id and app.login, leaving the rest of the file as it is."""
    path = pathlib.Path(factory_json)
    text = path.read_text()
    text, n1 = re.subn(r'("user_id"\s*:\s*)-?\d+', rf"\g<1>{user_id}", text, count=1)
    text, n2 = re.subn(r'("login"\s*:\s*)"[^"]*"', rf'\g<1>"{slug}[bot]"', text, count=1)
    data = json.loads(text)
    if (n1, n2) != (1, 1) or data["app"] != {"user_id": user_id, "login": f"{slug}[bot]"}:
        raise SystemExit("create_app: couldn't set app.user_id and app.login in factory.json; set them by hand")
    path.write_text(text)


def wait_for_code(org, name, open_browser=webbrowser.open, permissions=PERMISSIONS):
    """Serve the page, open it, and wait for GitHub's redirect; returns the conversion code."""
    state, result = secrets.token_urlsafe(16), {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            url = urllib.parse.urlsplit(self.path)
            query = dict(urllib.parse.parse_qsl(url.query))
            if url.path == "/":
                body = page(org, state, manifest(name, org, self.server.server_port, permissions))
            elif url.path == "/created" and query.get("state") == state and query.get("code"):
                result["code"] = query["code"]
                body = "<!doctype html><p>The App is created. Return to the terminal.</p>"
                threading.Thread(target=self.server.shutdown, daemon=True).start()
            else:
                self.send_error(400)
                return
            data = body.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    url = f"http://127.0.0.1:{server.server_port}/"
    print(f"Opening {url} to create the App in {org} (open it yourself if no browser appears).")
    open_browser(url)
    try:
        server.serve_forever()
    finally:
        server.server_close()
    return result["code"]


def repository():
    r = subprocess.run(["git", "-C", str(FACTORY), "remote", "get-url", "origin"], capture_output=True, text=True)
    m = re.search(r"github\.com[:/]([^/]+/[^/.]+)", r.stdout)
    return m.group(1) if m else "<owner>/<repository>"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("organization")
    ap.add_argument("--name", help="the App's name (default: <organization>-factory)")
    ap.add_argument("--key-out", help="where to write the private key (default: ~/<name>.private-key.pem)")
    kind = ap.add_mutually_exclusive_group()
    kind.add_argument("--runners", action="store_true", help="the CI tier's runner-registration App instead")
    kind.add_argument("--auditor", action="store_true", help="the runner audit's read-only App instead")
    kind.add_argument("--sessions", action="store_true", help="the App Claude Code sessions work as instead")
    args = ap.parse_args(argv)
    if args.sessions:
        name = args.name or f"{args.organization}-agent-sessions"
        default_key = pathlib.Path.home() / ".config" / "agent-sessions" / f"{args.organization}.pem"
    else:
        suffix = "-runners" if args.runners else "-runner-audit" if args.auditor else ""
        name = args.name or f"{args.organization}-factory{suffix}"
        default_key = pathlib.Path.home() / f"{name}.private-key.pem"
    # Outside the repository by default, so no `git add` can pick the key up.
    args.key_out = args.key_out or str(default_key)
    if pathlib.Path(args.key_out).exists():
        raise SystemExit(f"create_app: {args.key_out} exists; move it or pass --key-out")
    permissions = (RUNNER_PERMISSIONS if args.runners else AUDITOR_PERMISSIONS if args.auditor
                   else SESSIONS_PERMISSIONS if args.sessions else PERMISSIONS)
    app = convert(wait_for_code(args.organization, name, permissions=permissions))
    key = pathlib.Path(args.key_out)
    key.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Created here, readable only by you; an existing file is never overwritten.
    with os.fdopen(os.open(key, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as f:
        f.write(app["pem"])
    if args.runners:
        return runners_done(app, key)
    if args.auditor:
        return auditor_done(app, key, args.organization)
    if args.sessions:
        return sessions_done(app, key, args.organization)
    user_id = bot_user_id(app["slug"])
    write_app(FACTORY / "factory.json", app["slug"], user_id)
    repo = repository()
    print(f"""
Created {app['slug']} (bot user {user_id}); factory.json's app is set, and its private key is {key}.
1. Install it on the repository: https://github.com/apps/{app['slug']}/installations/new
2. After bootstrap.py --apply has created the factory-writer environment, store the key and client ID,
   then delete the key file:
     gh secret set FACTORY_APP_PRIVATE_KEY --env factory-writer --repo {repo} < {key}
     gh variable set FACTORY_APP_CLIENT_ID --env factory-writer --repo {repo} --body {app['client_id']}
3. Run python3 .github/factory/render.py and commit factory.json and the workflows.""")
    return 0


def runners_done(app, key):
    """The runner-registration App: say where its key and client ID go on the runner host."""
    granted = app.get("permissions") or {}
    if granted and {k: v for k, v in granted.items() if k != "metadata"} != RUNNER_PERMISSIONS:
        print(f"create_app: the App has {granted}, not just {RUNNER_PERMISSIONS}: fix it in its settings before use")
    print(f"""
Created {app['slug']}, the CI tier's runner-registration App; its private key is {key}. The key can register
runners into every runner group in the organization: keep it only where step 2 puts it.
1. Install it on the organization (it needs no repository): https://github.com/apps/{app['slug']}/installations/new
2. Copy the key to the runner host and install it root-only, never in a checkout (factory-ci-<instance> for another
   organization's runners on that host), then delete every other copy, {key} included:
     sudo install -D -m 600 -o root -g root <the copied key> /etc/factory-runner/factory-ci/app.pem
3. Set CI_APP_CLIENT_ID={app['client_id']} in the CI tier's checkout's .github/factory/host/host.conf, and run
   sudo TIER=ci TIER_OWNER=<owner>/<repository> bash .github/factory/host/setup.sh there; TIER_OWNER names that
   checkout's repository, and only the first run needs it (process/factory.md, Enablement step 10).""")
    return 0


def auditor_done(app, key, org):
    """The runner audit's App: where its key and client ID go, and how the audit's workflow is made."""
    granted = app.get("permissions") or {}
    if granted and {k: v for k, v in granted.items() if k != "metadata"} != AUDITOR_PERMISSIONS:
        print(f"create_app: the App has {granted}, not just {AUDITOR_PERMISSIONS}: fix it in its settings before use")
    print(f"""
Created {app['slug']}, the runner audit's App (read access to the organization's self-hosted runners); its
private key is {key}. Pick the one repository the audit runs in, <repo> below: a private one, its alarms are
issues there, so ideally one the factory's App isn't installed on (a factory token could otherwise close or bury
them; a failed run also emails whoever last changed its schedule). Never a runner host for its key.
1. Install it on the organization, for that repository only: https://github.com/apps/{app['slug']}/installations/new
2. Store its client ID and key in that repository, then delete the key file:
     gh variable set RUNNER_AUDIT_APP_CLIENT_ID --repo {org}/<repo> --body {app['client_id']}
     gh secret set RUNNER_AUDIT_APP_KEY --repo {org}/<repo> < {key}
   and, optionally, who an alarm mentions: gh variable set RUNNER_AUDIT_NOTIFY --repo {org}/<repo> --body "<logins>"
3. From your own machine (snapshot reads with your gh login, never a runner host's), take the organization's runner
   groups as they are, review them (and turn the CI tier's group's runners into a pattern, such as
   ^<prefix>-ci-[0-9]+-[0-9a-f]{{6}}$, a most-at-once and labels), then write the workflow and commit it to <repo>:
     python3 .github/factory/runner_audit.py snapshot {org} > expected.json
     python3 .github/factory/runner_audit.py workflow expected.json > .github/workflows/factory-runner-audit.yml
   (in <repo>'s checkout for the second), and run it once: gh workflow run factory-runner-audit.yml --repo {org}/<repo>
   (process/factory.md, Enablement step 12).""")
    return 0


def sessions_done(app, key, org):
    """The sessions App: where it's installed, and how CD's machine starts using it."""
    granted = app.get("permissions") or {}
    if granted and granted != SESSIONS_PERMISSIONS:
        print(f"create_app: the App has {granted}, not {SESSIONS_PERMISSIONS}: fix it in its settings before use")
    print(f"""
Created {app['slug']}, the App Claude Code sessions on your machine work as in the product's repositories; its
private key is {key}, readable by you only. Infra and setup stay your own login.
1. Install it on the organization, for the product's repositories only (Only select repositories), never the
   ones that hold infra or setup: https://github.com/apps/{app['slug']}/installations/new
2. Record it on this machine, naming the same repositories; new sessions in their clones then work as the App:
     python3 .github/factory/session_identity.py install {org} --client-id {app['client_id']} --key {key} \
       --repo <repository> [--repo <repository> ...]
   (process/factory.md, Enablement step 13).""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
