#!/usr/bin/env python3
"""Who a Claude Code session on CD's machine works as (z-sdlc process/factory.md, D2 rule 6 and Enablement step 13).

    python3 .github/factory/session_identity.py install <owner> --client-id ID --key PATH --repo NAME [--repo NAME ...]
    session_identity.py session-start                 the SessionStart hook install adds to Claude Code's settings
    session_identity.py status [DIR]                  who a session started in DIR works as
    session_identity.py as-owner -- COMMAND [ARG...]  run one command as CD's own login, inside an App session
    session_identity.py token OWNER/REPO              print a token for one repository (GH_TOKEN's source)
    session_identity.py git-credential get            git's credential helper, inside an App session

A session started in a clone of one of the listed repositories works as the sessions App: its git commits, pushes
and gh calls go out as the App's bot, with a token for that repository only that lasts an hour, and its commits
aren't signed (CD's key would sign them otherwise). The App deals with the product's code. Infra and setup stay
CD's own login: a change to a path CODEOWNERS gives an owner, and anything outside the repository's files
(settings, rulesets, secrets, environments, Apps, hosts). The session makes those in a branch and PR of their own,
running each git or gh command for them through as-owner. Every other session is CD's, as before.

install copies this file to ~/.config/agent-sessions/, records the App there (config.json: its client ID, its
key's path, its bot user and the repositories), and adds the SessionStart hook to Claude Code's user settings.
The key stays where it is, readable by CD only. session-start puts the App's identity in the session's
environment (CLAUDE_ENV_FILE), never in the clone's git config, so CD's own terminal in the same clone is CD.
When the App's token can't be had, GitHub calls fail loudly rather than falling back to CD's login. An identity
of its own shows who acted, but contains nothing: the session can still reach CD's login, as-owner says how.
Standard library and openssl only.
"""
import argparse
import base64
import calendar
import json
import os
import pathlib
import re
import shlex
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

API = "https://api.github.com"
# What a session's token may do: the product's code, its PRs and issues, and reading CI. Never workflows,
# administration, secrets or environments: those are infra and setup, CD's own login. A token is narrowed to
# these (and to what the App has) whatever else the App is granted.
SESSION_PERMISSIONS = {"contents": "write", "pull_requests": "write", "issues": "write", "metadata": "read",
                       "actions": "read", "checks": "read", "statuses": "read"}
LEVELS = {"read": 1, "write": 2, "admin": 3}
FAILED = "session-identity-no-token"  # GH_TOKEN when no token could be had: gh fails instead of using CD's login
# Removed from an App session's commands: gh falls back to it after GH_TOKEN, and other tools read it as "the" token.
# A variable a project's own scripts read by another name stays, and so does what an MCP server was started with.
UNSET = ("GITHUB_TOKEN",)


def home():
    return pathlib.Path(os.environ.get("AGENT_SESSIONS_HOME", "~/.config/agent-sessions")).expanduser()


def cache_dir():
    return pathlib.Path(os.environ.get("AGENT_SESSIONS_CACHE", "~/.cache/agent-sessions")).expanduser()


def claude_settings():
    return pathlib.Path(os.environ.get("CLAUDE_CONFIG_DIR", "~/.claude")).expanduser() / "settings.json"


def load_config():
    path = home() / "config.json"
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return {"owners": {}}
    except ValueError as e:
        raise SystemExit(f"session_identity: {path} isn't JSON ({e})")


def app_for(repo, config=None):
    """The App entry that covers owner/name, or None: only the listed repositories are the App's."""
    owner, _, name = repo.partition("/")
    entry = ((config or load_config()).get("owners") or {}).get(owner)
    if entry and name.lower() in {r.lower() for r in entry.get("repos") or []}:
        return entry
    return None


def github_repo(url):
    """owner/name of a GitHub remote URL (https, ssh or scp form), or None."""
    m = re.match(r"^(?:https://(?:[^@/]+@)?github\.com/|ssh://git@github\.com/|git@github\.com:)"
                 r"([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?$", url.strip())
    return f"{m.group(1)}/{m.group(2)}" if m else None


def origin_of(directory):
    r = subprocess.run(["git", "-C", str(directory), "remote", "get-url", "origin"], capture_output=True, text=True,
                       env={k: v for k, v in os.environ.items() if not k.startswith("GIT_CONFIG_")})
    return github_repo(r.stdout) if r.returncode == 0 else None


# ---- GitHub

def b64url(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def app_jwt(entry):
    """A JWT for the App, signed with its key by openssl (RS256), valid for nine minutes."""
    now = int(time.time())
    header = b64url(json.dumps({"alg": "RS256", "typ": "JWT"}).encode())
    claims = b64url(json.dumps({"iat": now - 60, "exp": now + 540, "iss": entry["client_id"]}).encode())
    key = pathlib.Path(entry["key"]).expanduser()
    r = subprocess.run(["openssl", "dgst", "-sha256", "-sign", str(key)], input=f"{header}.{claims}".encode(),
                       capture_output=True, timeout=30)
    if r.returncode or not r.stdout:
        raise SystemExit(f"session_identity: openssl couldn't sign with the App's key {key}")
    return f"{header}.{claims}.{b64url(r.stdout)}"


def api(method, path, bearer=None, body=None):
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28",
               "User-Agent": "z-sdlc-session-identity"}
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    req = urllib.request.Request(API + path, method=method, headers=headers,
                                 data=None if body is None else json.dumps(body).encode())
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"null")
        except ValueError:
            return e.code, None
    except (urllib.error.URLError, TimeoutError) as e:
        return 0, {"message": str(e)}


def narrowed(granted):
    """SESSION_PERMISSIONS, each at most what the installation has; the rest left out."""
    out = {}
    for name, level in SESSION_PERMISSIONS.items():
        have = (granted or {}).get(name)
        if have in LEVELS:
            out[name] = level if LEVELS[have] >= LEVELS[level] else have
    return out


def mint(repo, entry, call=None):
    """A fresh installation token for one repository, with the session's permissions only."""
    call = call or api
    owner, name = repo.split("/", 1)
    jwt = app_jwt(entry)
    status, inst = call("GET", f"/repos/{owner}/{name}/installation", jwt)
    if status != 200:
        raise SystemExit(f"session_identity: the App isn't installed on {repo} (HTTP {status})")
    status, data = call("POST", f"/app/installations/{inst['id']}/access_tokens", jwt,
                        {"repositories": [name], "permissions": narrowed(inst.get("permissions"))})
    if status != 201:
        raise SystemExit(f"session_identity: no token for {repo} (HTTP {status}: {(data or {}).get('message')})")
    return data["token"], calendar.timegm(time.strptime(data["expires_at"], "%Y-%m-%dT%H:%M:%SZ"))


def token(repo, config=None, call=None, now=time.time):
    """The repository's token, from the cache while it has ten minutes left. Only a listed repository has one."""
    entry = app_for(repo, config)
    if not entry:
        raise SystemExit(f"session_identity: {repo} isn't one of the App's repositories ({home() / 'config.json'})")
    cache = cache_dir()
    cache.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = cache / f"{repo.replace('/', '__').lower()}.json"
    try:
        data = json.loads(path.read_text())
        if data["expires"] - now() > 600:
            return data["token"]
    except (OSError, ValueError, KeyError, TypeError):
        pass
    value, expires = mint(repo, entry, call)
    fd, tmp = tempfile.mkstemp(dir=cache, prefix=".token-")
    with os.fdopen(fd, "w") as f:  # mkstemp creates it 600
        json.dump({"token": value, "expires": expires}, f)
    os.replace(tmp, path)
    return value


# ---- the session

def bot_email(bot):
    return f"{bot['id']}+{bot['login']}@users.noreply.github.com"


def environment(repo, entry, helper):
    """The lines CLAUDE_ENV_FILE gets: run before each of the session's Bash commands, so every git and gh command
    is the App's. Git's config comes from the environment (GIT_CONFIG_*), the clone's own is never changed."""
    py, me = "python3", shlex.quote(str(helper))  # python3 from PATH: an interpreter's own path moves on upgrade
    bot = entry["bot"]
    config = [("credential.helper", ""),  # an empty value drops CD's helpers (keychain, gh) for these commands
              ("credential.helper", f"!{py} {me} git-credential"),
              ("credential.useHttpPath", "true"),
              ("url.https://github.com/.insteadOf", "git@github.com:"),  # SSH would push with CD's key
              ("url.https://github.com/.insteadOf", "ssh://git@github.com/"),
              ("commit.gpgSign", "false"), ("tag.gpgSign", "false")]
    lines = ["# session_identity.py: this session works as the sessions App (as-owner runs a command as CD)",
             f"export AGENT_SESSION_REPO={shlex.quote(repo)}",
             f"unset {' '.join(UNSET)}",
             f'export GH_TOKEN="$({py} {me} token {shlex.quote(repo)} 2>/dev/null || echo {FAILED})"',
             f"export GIT_AUTHOR_NAME={shlex.quote(bot['login'])} GIT_COMMITTER_NAME={shlex.quote(bot['login'])}",
             f"export GIT_AUTHOR_EMAIL={shlex.quote(bot_email(bot))} GIT_COMMITTER_EMAIL={shlex.quote(bot_email(bot))}",
             "export GIT_TERMINAL_PROMPT=0",
             f"export GIT_CONFIG_COUNT={len(config)}"]
    for i, (key, value) in enumerate(config):
        lines.append(f"export GIT_CONFIG_KEY_{i}={shlex.quote(key)} GIT_CONFIG_VALUE_{i}={shlex.quote(value)}")
    return "\n".join(lines) + "\n"


def context(repo, entry, helper, problem=None):
    me = f"python3 {shlex.quote(str(helper))}"
    text = (f"This session works as {entry['bot']['login']} (the sessions App) in {repo}: its git commits, pushes "
            "and gh calls go out as the App, with a token for this repository only, and its commits aren't signed. "
            "The App deals with the product's code. Infra and setup are CD's own login: a change to a path "
            "CODEOWNERS gives an owner (.github/, .claude/, CLAUDE.md, the SDLC's process files, the test and build "
            "configuration; read CODEOWNERS when unsure, the last matching line wins), and anything outside the "
            "repository's files (settings, rulesets, secrets, environments, Apps, hosts). Make those in a branch "
            f"and PR of their own, and run each git or gh command for them as `{me} as-owner -- <command>`. "
            "GitHub refuses the App a push that changes .github/workflows/. MCP servers keep the credentials "
            "they started with (a GitHub one configured with CD's token acts as CD): write to GitHub with git and "
            "gh only. Never use CD's login for the product's code: if a GitHub or git command fails for lack of "
            "credentials, tell CD.")
    if problem:
        text = (f"The sessions App's token couldn't be had for {repo} ({problem}), so this session's GitHub and "
                "git commands will fail rather than use CD's login. Tell CD before doing anything on GitHub. "
                + text)
    return text


def session_start(stdin=sys.stdin, out=sys.stdout, env=os.environ, config=None, get_token=None):
    """The SessionStart hook: nothing for a repository that isn't the App's; otherwise the App's identity in the
    session's environment and a word to the session on what it is."""
    try:
        event = json.loads(stdin.read() or "{}")
    except ValueError:
        event = {}
    repo = origin_of(event.get("cwd") or os.getcwd())
    entry = app_for(repo, config) if repo else None
    if not entry:
        return 0
    helper = home() / "session_identity.py"
    problem = None
    try:
        (get_token or token)(repo, config)
    except SystemExit as e:
        problem = str(e.code).removeprefix("session_identity: ")
    except Exception as e:  # whatever it is, the session must hear of it rather than quietly be CD's
        problem = f"{type(e).__name__}: {e}"
    env_file = env.get("CLAUDE_ENV_FILE")
    if env_file:
        with open(env_file, "a") as f:
            f.write(environment(repo, entry, helper))
        text = context(repo, entry, helper, problem)
    else:  # nothing to put the identity in: the session is CD's, and must know it
        text = (f"{repo} is one of the sessions App's repositories, but this Claude Code gave the session-start "
                "hook no CLAUDE_ENV_FILE, so this session works as CD's own login, as before the App. Tell CD "
                "before committing or opening a PR: the product's code should be the App's.")
    json.dump({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text}}, out)
    return 0


def git_credential(argv, stdin=sys.stdin, out=sys.stdout, config=None, get_token=None):
    """git's credential helper: the App's token for the App's own repositories, nothing for any other (git then
    fails: in an App session there is no other helper, and no prompt)."""
    if argv != ["get"]:
        return 0
    fields = dict(line.split("=", 1) for line in stdin.read().splitlines() if "=" in line)
    if fields.get("protocol") != "https" or fields.get("host") != "github.com":
        return 0
    repo = github_repo(f"https://github.com/{fields.get('path', '')}")
    if not repo or not app_for(repo, config):
        return 0
    try:
        value = (get_token or token)(repo, config)
    except SystemExit as e:
        print(e.code, file=sys.stderr)
        return 0
    out.write(f"username=x-access-token\npassword={value}\n")
    return 0


def owner_env(env):
    """The environment without the App's identity: CD's own git config, credentials and gh login apply again."""
    drop = {"GH_TOKEN", "GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL",
            "GIT_TERMINAL_PROMPT", "GIT_CONFIG_COUNT"}
    return {k: v for k, v in env.items() if k not in drop and not k.startswith(("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_"))}


def as_owner(argv):
    if argv[:1] == ["--"]:
        argv = argv[1:]
    if not argv:
        raise SystemExit("usage: session_identity.py as-owner -- COMMAND [ARG...]")
    print(f"as-owner: running {argv[0]} as CD's own login", file=sys.stderr)
    os.execvpe(argv[0], argv, owner_env(os.environ))


def status(directory, config=None):
    repo = origin_of(directory)
    entry = app_for(repo, config) if repo else None
    if not entry:
        print(f"{repo or directory}: not one of the App's repositories; a session here is CD's own login")
        return 0
    print(f"{repo}: a session here works as {entry['bot']['login']}")
    try:
        token(repo, config)
        print("  the App's token: ok")
    except SystemExit as e:
        print(f"  the App's token: {e.code}")
        return 1
    return 0


# ---- install

HOOK_MARK = "session_identity.py session-start"


def add_hook(settings_path, helper):
    """Add the SessionStart hook to Claude Code's user settings once, keeping everything else in the file."""
    try:
        settings = json.loads(settings_path.read_text())
    except FileNotFoundError:
        settings = {}
    except ValueError as e:
        raise SystemExit(f"session_identity: {settings_path} isn't JSON ({e}); add the hook by hand")
    starts = settings.setdefault("hooks", {}).setdefault("SessionStart", [])
    if any(HOOK_MARK in (h.get("command") or "") for group in starts for h in group.get("hooks") or []):
        return False
    command = f"python3 {shlex.quote(str(helper))} session-start"
    starts.append({"hooks": [{"type": "command", "command": command, "timeout": 30}]})
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=settings_path.parent, prefix=".settings-")
    with os.fdopen(fd, "w") as f:
        f.write(json.dumps(settings, indent=2) + "\n")
    if settings_path.exists():
        os.chmod(tmp, settings_path.stat().st_mode & 0o777)
    os.replace(tmp, settings_path)
    return True


def install(args, call=None):
    call = call or api  # looked up now, so a test's fake is the one used
    key = pathlib.Path(args.key).expanduser().resolve()
    if not key.is_file():
        raise SystemExit(f"session_identity: no key at {key}")
    if key.stat().st_mode & 0o077:
        raise SystemExit(f"session_identity: {key} is readable by others: chmod 600 it first")
    entry = {"client_id": args.client_id, "key": str(key), "repos": sorted(set(args.repo))}
    status, app = call("GET", "/app", app_jwt(entry))
    if status != 200:
        raise SystemExit(f"session_identity: the key and client ID don't sign in as an App (HTTP {status})")
    status, user = call("GET", f"/users/{app['slug']}%5Bbot%5D")
    if status != 200:
        raise SystemExit(f"session_identity: can't read {app['slug']}[bot] (HTTP {status})")
    entry["bot"] = {"login": user["login"], "id": user["id"]}
    beyond = {k: v for k, v in (app.get("permissions") or {}).items()
              if LEVELS.get(v, 0) > LEVELS.get(SESSION_PERMISSIONS.get(k), 0)}
    if beyond:
        print(f"note: {app['slug']} also has {beyond}; a session's token never gets them, but the key can: remove "
              "them in the App's settings (infra and setup are CD's own login)")
    missing = [r for r in entry["repos"] if call("GET", f"/repos/{args.owner}/{r}/installation", app_jwt(entry))[0] != 200]
    if missing:
        print(f"note: {app['slug']} isn't installed on {', '.join(missing)}: sessions there fail until it is")
    base = home()
    base.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(base, 0o700)
    helper = base / "session_identity.py"
    if pathlib.Path(__file__).resolve() != helper.resolve():
        helper.write_bytes(pathlib.Path(__file__).read_bytes())
    os.chmod(helper, 0o700)
    config = load_config()
    config.setdefault("owners", {})[args.owner] = entry
    fd, tmp = tempfile.mkstemp(dir=base, prefix=".config-")
    with os.fdopen(fd, "w") as f:
        f.write(json.dumps(config, indent=2) + "\n")
    os.replace(tmp, base / "config.json")
    added = add_hook(claude_settings(), helper)
    print(f"Sessions in {', '.join(f'{args.owner}/{r}' for r in entry['repos'])} now work as {user['login']}"
          f" (new sessions; {'hook added to' if added else 'hook already in'} {claude_settings()}).\n"
          f"Check one: python3 {helper} status <a clone>")
    return 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["session-start"]:
        return session_start()
    if argv[:1] == ["git-credential"]:
        return git_credential(argv[1:])
    if argv[:1] == ["as-owner"]:
        return as_owner(argv[1:])
    if argv[:1] == ["token"] and len(argv) == 2:
        print(token(argv[1]))
        return 0
    if argv[:1] == ["status"]:
        return status(argv[1] if len(argv) > 1 else os.getcwd())
    ap = argparse.ArgumentParser(prog="session_identity.py", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="command", required=True)
    ins = sub.add_parser("install", help="record the App and add the SessionStart hook")
    ins.add_argument("owner", help="the organization or user the App and repositories belong to")
    ins.add_argument("--client-id", required=True, help="the App's client ID")
    ins.add_argument("--key", required=True, help="the App's private key (stays where it is; chmod 600)")
    ins.add_argument("--repo", action="append", required=True, help="a repository whose sessions work as the App")
    args = ap.parse_args(argv)
    return install(args)


if __name__ == "__main__":
    sys.exit(main())
