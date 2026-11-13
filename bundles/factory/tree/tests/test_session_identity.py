"""session_identity.py: who a Claude Code session on CD's machine works as. GitHub is faked; git, bash and openssl
are real, and the session's environment file is run the way Claude Code runs it before each Bash command."""
import base64
import contextlib
import io
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

FACTORY = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FACTORY))
import create_app  # noqa: E402
import session_identity as si  # noqa: E402

BOT = {"login": "acme-agent-sessions[bot]", "id": 4242}
INSTALLED = {"contents": "write", "pull_requests": "write", "issues": "write", "metadata": "read", "checks": "read",
             "workflows": "write", "administration": "write", "secrets": "write"}


class FakeGitHub:
    def __init__(self, installed=("acme/widget",), permissions=None, app_permissions=None):
        self.installed, self.calls = set(installed), []
        self.permissions = dict(INSTALLED if permissions is None else permissions)
        self.app_permissions = dict(si.SESSION_PERMISSIONS if app_permissions is None else app_permissions)

    def __call__(self, method, path, bearer=None, body=None):
        self.calls.append((method, path, bearer, body))
        if path.startswith("/repos/") and path.endswith("/installation"):
            repo = path[len("/repos/"):-len("/installation")]
            if repo in self.installed:
                return 200, {"id": 99, "permissions": self.permissions}
            return 404, {"message": "Not Found"}
        if path == "/app/installations/99/access_tokens":
            return 201, {"token": f"ghs_minted{len(self.calls)}", "expires_at": "2100-01-01T00:00:00Z"}
        if path == "/app":
            return 200, {"slug": "acme-agent-sessions", "permissions": self.app_permissions}
        if path == "/users/acme-agent-sessions%5Bbot%5D":
            return 200, dict(BOT)
        return 404, {"message": "Not Found"}

    def posts(self):
        return [c for c in self.calls if c[0] == "POST"]


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.keys = tempfile.TemporaryDirectory()
        cls.key = pathlib.Path(cls.keys.name) / "app.pem"
        subprocess.run(["openssl", "genrsa", "-out", str(cls.key), "2048"], check=True, capture_output=True)
        os.chmod(cls.key, 0o600)

    @classmethod
    def tearDownClass(cls):
        cls.keys.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        patch = mock.patch.dict(os.environ, {"AGENT_SESSIONS_HOME": str(self.root / "home"),
                                             "AGENT_SESSIONS_CACHE": str(self.root / "cache"),
                                             "CLAUDE_CONFIG_DIR": str(self.root / "claude"),
                                             "GITHUB_TOKEN": "cd-own-token", "GITHUB_PAT": "cd-pat",
                                             "GIT_CONFIG_NOSYSTEM": "1",
                                             "HOME": str(self.root / "cd")})
        patch.start()
        self.addCleanup(patch.stop)
        (self.root / "cd").mkdir()
        # CD's own git: a name, a helper and signing, all of which an App session must not use.
        (self.root / "cd" / ".gitconfig").write_text(
            "[user]\n\tname = CD\n\temail = cd@example.com\n[credential]\n\thelper = cd-keychain\n"
            "[commit]\n\tgpgsign = true\n")
        self.config = {"owners": {"acme": {"client_id": "Iv1.abc", "key": str(self.key), "bot": dict(BOT),
                                           "repos": ["widget"]}}}

    def tearDown(self):
        self.tmp.cleanup()

    def clone(self, url, name="clone"):
        path = self.root / name
        subprocess.run(["git", "init", "-q", str(path)], check=True)
        subprocess.run(["git", "-C", str(path), "remote", "add", "origin", url], check=True)
        return path

    def write_config(self):
        home = self.root / "home"
        home.mkdir(parents=True, exist_ok=True)
        (home / "config.json").write_text(json.dumps(self.config))
        shutil.copy(FACTORY / "session_identity.py", home / "session_identity.py")
        return home / "session_identity.py"

    def cache_token(self, repo="acme/widget", value="ghs_cached", expires=4102444800):
        cache = self.root / "cache"
        cache.mkdir(parents=True, exist_ok=True)
        (cache / f"{repo.replace('/', '__')}.json").write_text(json.dumps({"token": value, "expires": expires}))

    def start(self, directory, get_token=None):
        env_file = self.root / "session.env"
        env_file.touch()
        out = io.StringIO()
        code = si.session_start(stdin=io.StringIO(json.dumps({"cwd": str(directory), "source": "startup"})),
                                out=out, env={"CLAUDE_ENV_FILE": str(env_file)}, config=self.config,
                                get_token=get_token or (lambda repo, config: "ghs_x"))
        return code, out.getvalue(), env_file.read_text()

    def bash(self, env_text, command, cwd):
        """A Bash command as Claude Code runs it: the session's environment file first, then the command."""
        script = self.root / "cmd.sh"
        script.write_text(env_text + "\n" + command + "\n")
        return subprocess.run(["bash", str(script)], cwd=cwd, capture_output=True, text=True)


class Repositories(Base):
    def test_every_github_remote_form_names_its_repository(self):
        for url in ["git@github.com:acme/widget.git", "git@github.com:acme/widget", "https://github.com/acme/widget",
                    "https://github.com/acme/widget.git", "https://x-access-token@github.com/acme/widget.git",
                    "ssh://git@github.com/acme/widget.git", "https://github.com/acme/widget/"]:
            with self.subTest(url):
                self.assertEqual(si.github_repo(url), "acme/widget")
        for url in ["git@gitlab.com:acme/widget.git", "https://github.com.evil.example/acme/widget",
                    "https://github.com/acme", "/srv/widget.git", ""]:
            with self.subTest(url):
                self.assertIsNone(si.github_repo(url))

    def test_only_the_listed_repositories_are_the_apps(self):
        self.assertIs(si.app_for("acme/widget", self.config), self.config["owners"]["acme"])
        self.assertIs(si.app_for("acme/Widget", self.config), self.config["owners"]["acme"])
        self.assertIsNone(si.app_for("acme/infra", self.config))
        self.assertIsNone(si.app_for("other/widget", self.config))


class Tokens(Base):
    def test_a_token_is_for_one_repository_and_the_sessions_permissions_only(self):
        gh = FakeGitHub()
        value = si.token("acme/widget", self.config, call=gh)
        self.assertEqual(value, "ghs_minted2")
        (_, path, jwt, body), = gh.posts()
        self.assertEqual(path, "/app/installations/99/access_tokens")
        self.assertEqual(body["repositories"], ["widget"])
        # Never workflows, administration or secrets, whatever the App was granted; nothing the App lacks either.
        self.assertEqual(body["permissions"], {"contents": "write", "pull_requests": "write", "issues": "write",
                                               "metadata": "read", "checks": "read"})
        # The JWT is the App's (its client ID), signed with its key.
        header, claims, sig = jwt.split(".")
        pad = lambda s: base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))  # noqa: E731
        self.assertEqual(json.loads(pad(header))["alg"], "RS256")
        self.assertEqual(json.loads(pad(claims))["iss"], "Iv1.abc")
        pub = self.root / "pub.pem"
        subprocess.run(["openssl", "rsa", "-in", str(self.key), "-pubout", "-out", str(pub)], check=True,
                       capture_output=True)
        (self.root / "sig").write_bytes(pad(sig))
        r = subprocess.run(["openssl", "dgst", "-sha256", "-verify", str(pub), "-signature", str(self.root / "sig")],
                           input=f"{header}.{claims}".encode(), capture_output=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_a_read_only_installation_gives_a_read_only_token(self):
        gh = FakeGitHub(permissions={"contents": "read", "metadata": "read"})
        si.token("acme/widget", self.config, call=gh)
        self.assertEqual(gh.posts()[0][3]["permissions"], {"contents": "read", "metadata": "read"})

    def test_a_token_is_reused_until_ten_minutes_before_it_expires(self):
        gh = FakeGitHub()
        first = si.token("acme/widget", self.config, call=gh, now=lambda: 4102444800 - 3600)
        self.assertEqual(si.token("acme/widget", self.config, call=gh, now=lambda: 4102444800 - 3600), first)
        self.assertEqual(len(gh.posts()), 1)
        self.assertEqual(oct((self.root / "cache" / "acme__widget.json").stat().st_mode & 0o777), "0o600")
        si.token("acme/widget", self.config, call=gh, now=lambda: 4102444800 - 300)
        self.assertEqual(len(gh.posts()), 2)

    def test_no_token_for_a_repository_that_isnt_the_apps_or_where_it_isnt_installed(self):
        gh = FakeGitHub(installed=())
        with self.assertRaisesRegex(SystemExit, "isn't one of the App's repositories"):
            si.token("acme/infra", self.config, call=gh)
        self.assertEqual(gh.calls, [])
        with self.assertRaisesRegex(SystemExit, "the App isn't installed on acme/widget"):
            si.token("acme/widget", self.config, call=gh)


class SessionStart(Base):
    def test_a_repository_that_isnt_the_apps_is_left_as_cds(self):
        for url in ["git@github.com:acme/infra.git", "git@github.com:other/widget.git", "/srv/widget.git"]:
            with self.subTest(url):
                code, out, env = self.start(self.clone(url, name=url.replace("/", "_")))
                self.assertEqual((code, out, env), (0, "", ""))
        code, out, env = self.start(self.root)  # not a clone at all
        self.assertEqual((code, out, env), (0, "", ""))

    def test_the_session_is_told_who_it_is_and_what_is_cds(self):
        code, out, env = self.start(self.clone("git@github.com:acme/widget.git"))
        self.assertEqual(code, 0)
        context = json.loads(out)["hookSpecificOutput"]
        self.assertEqual(context["hookEventName"], "SessionStart")
        text = context["additionalContext"]
        self.assertIn("works as acme-agent-sessions[bot] (the sessions App) in acme/widget", text)
        self.assertIn("a path CODEOWNERS gives an owner", text)
        self.assertIn("as-owner -- <command>", text)
        self.assertNotIn("couldn't be had", text)

    def test_git_and_gh_are_the_apps_and_cds_own_identity_is_out_of_reach(self):
        helper = self.write_config()
        self.cache_token()
        clone = self.clone("git@github.com:acme/widget.git")
        code, out, env = self.start(clone)
        self.assertIn(str(helper), env)
        r = self.bash(env, "echo \"token=$GH_TOKEN github_token=${GITHUB_TOKEN-unset} pat=${GITHUB_PAT-unset}\"\n"
                           "git remote get-url --push origin\n"
                           "printf 'protocol=https\\nhost=github.com\\npath=acme/widget.git\\n\\n' | git credential fill\n"
                           "git -c user.useConfigOnly=false commit -q --allow-empty -m probe\n"
                           "git log -1 --format='%an <%ae> %cn signed=%G?'", clone)
        self.assertEqual(r.returncode, 0, r.stderr)
        lines = r.stdout.splitlines()
        # gh's fallback is gone; a variable only the project's own scripts read stays.
        self.assertEqual(lines[0], "token=ghs_cached github_token=unset pat=cd-pat")
        self.assertEqual(lines[1], "https://github.com/acme/widget.git")  # never SSH, which would push with CD's key
        self.assertIn("username=x-access-token", lines)
        self.assertIn("password=ghs_cached", lines)  # CD's keychain helper never asked
        self.assertEqual(lines[-1], "acme-agent-sessions[bot] <4242+acme-agent-sessions[bot]@users.noreply.github.com> "
                                    "acme-agent-sessions[bot] signed=N")
        # The clone's own config is untouched: CD's terminal in it is still CD.
        local = subprocess.run(["git", "-C", str(clone), "config", "--local", "--list"], capture_output=True, text=True)
        self.assertNotIn("credential", local.stdout)
        self.assertNotIn("user.", local.stdout)

    def test_without_the_apps_token_github_fails_instead_of_using_cds_login(self):
        helper = self.write_config()  # no cached token, and the fake key path makes minting fail
        self.config["owners"]["acme"]["key"] = str(self.root / "missing.pem")
        (helper.parent / "config.json").write_text(json.dumps(self.config))

        def no_token(repo, config):
            raise SystemExit("session_identity: openssl couldn't sign with the App's key")
        clone = self.clone("https://github.com/acme/widget.git")
        code, out, env = self.start(clone, get_token=no_token)
        self.assertEqual(code, 0)
        self.assertIn("couldn't be had for acme/widget (openssl couldn't sign", json.loads(out)["hookSpecificOutput"]
                      ["additionalContext"])
        r = self.bash(env, "echo \"$GH_TOKEN\"\n"
                           "printf 'protocol=https\\nhost=github.com\\npath=acme/widget.git\\n\\n' | git credential fill",
                      clone)
        self.assertTrue(r.stdout.startswith(si.FAILED + "\n"), r.stdout)
        self.assertNotEqual(r.returncode, 0)  # no password from anyone, and no prompt
        self.assertNotIn("password=", r.stdout)

    def test_any_failure_is_told_to_the_session(self):
        def broken(repo, config):
            raise KeyError("client_id")
        code, out, env = self.start(self.clone("git@github.com:acme/widget.git"), get_token=broken)
        self.assertIn("KeyError", json.loads(out)["hookSpecificOutput"]["additionalContext"])
        self.assertIn(f"echo {si.FAILED}", env)


    def test_without_an_environment_file_the_session_is_told_it_is_cds(self):
        out = io.StringIO()
        si.session_start(stdin=io.StringIO(json.dumps({"cwd": str(self.clone("git@github.com:acme/widget.git"))})),
                         out=out, env={}, config=self.config, get_token=lambda repo, config: "ghs_x")
        text = json.loads(out.getvalue())["hookSpecificOutput"]["additionalContext"]
        self.assertIn("this session works as CD's own login", text)
        self.assertNotIn("works as acme-agent-sessions[bot]", text)


class AsOwner(Base):
    def test_as_owner_gives_one_command_cds_own_login_back(self):
        helper = self.write_config()
        self.cache_token()
        clone = self.clone("git@github.com:acme/widget.git")
        _, _, env = self.start(clone)
        r = self.bash(env, f"python3 {helper} as-owner -- bash -c 'echo \"token=${{GH_TOKEN-unset}}\"; "
                           "git config --get-all credential.helper; git var GIT_AUTHOR_IDENT; "
                           "git remote get-url --push origin; git config commit.gpgsign'", clone)
        self.assertEqual(r.returncode, 0, r.stderr)
        lines = r.stdout.splitlines()
        self.assertEqual(lines[0], "token=unset")
        self.assertEqual(lines[1], "cd-keychain")
        self.assertTrue(lines[2].startswith("CD <cd@example.com>"), lines[2])
        self.assertEqual(lines[3], "git@github.com:acme/widget.git")
        self.assertEqual(lines[4], "true")
        self.assertIn("as-owner: running bash as CD's own login", r.stderr)

    def test_owner_env_drops_only_the_apps_identity(self):
        env = {"PATH": "/bin", "GH_TOKEN": "t", "GIT_AUTHOR_NAME": "bot", "GIT_COMMITTER_EMAIL": "e",
               "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "k", "GIT_CONFIG_VALUE_0": "v", "GIT_TERMINAL_PROMPT": "0",
               "GIT_DIR": "/x", "AGENT_SESSION_REPO": "acme/widget"}
        self.assertEqual(si.owner_env(env), {"PATH": "/bin", "GIT_DIR": "/x", "AGENT_SESSION_REPO": "acme/widget"})


class GitCredential(Base):
    def ask(self, text, argv=("get",)):
        out = io.StringIO()
        si.git_credential(list(argv), stdin=io.StringIO(text), out=out, config=self.config,
                          get_token=lambda repo, config: f"tok-{repo}")
        return out.getvalue()

    def test_only_the_apps_repositories_get_its_token(self):
        self.assertEqual(self.ask("protocol=https\nhost=github.com\npath=acme/widget.git\n"),
                         "username=x-access-token\npassword=tok-acme/widget\n")
        for name, text, argv in [
                ("another repository", "protocol=https\nhost=github.com\npath=acme/infra.git\n", ("get",)),
                ("another host", "protocol=https\nhost=github.com.evil.example\npath=acme/widget.git\n", ("get",)),
                ("plain http", "protocol=http\nhost=github.com\npath=acme/widget.git\n", ("get",)),
                ("no path", "protocol=https\nhost=github.com\n", ("get",)),
                ("store", "protocol=https\nhost=github.com\npath=acme/widget.git\n", ("store",))]:
            with self.subTest(name):
                self.assertEqual(self.ask(text, argv), "")


class Install(Base):
    def run_install(self, gh, *extra, key=None):
        out = io.StringIO()
        args = ["install", "acme", "--client-id", "Iv1.abc", "--key", str(key or self.key), "--repo", "widget", *extra]
        with mock.patch.object(si, "api", gh), contextlib.redirect_stdout(out):
            code = si.main(args)
        return code, out.getvalue()

    def test_install_records_the_app_and_adds_the_hook_once(self):
        settings = self.root / "claude" / "settings.json"
        settings.parent.mkdir()
        mine = {"type": "command", "command": "echo hello"}
        settings.write_text(json.dumps({"model": "x", "hooks": {"SessionStart": [{"hooks": [mine]}]}}))
        gh = FakeGitHub(installed=("acme/widget",))
        code, out = self.run_install(gh, "--repo", "gadget")
        self.assertEqual(code, 0, out)
        self.assertIn("isn't installed on gadget", out)
        config = json.loads((self.root / "home" / "config.json").read_text())
        self.assertEqual(config["owners"]["acme"], {"client_id": "Iv1.abc", "key": str(self.key.resolve()),
                                                    "repos": ["gadget", "widget"], "bot": BOT})
        helper = self.root / "home" / "session_identity.py"
        self.assertEqual(helper.read_bytes(), (FACTORY / "session_identity.py").read_bytes())
        self.assertEqual(oct(helper.stat().st_mode & 0o777), "0o700")
        data = json.loads(settings.read_text())
        self.assertEqual(data["model"], "x")
        commands = [h["command"] for g in data["hooks"]["SessionStart"] for h in g["hooks"]]
        self.assertEqual(commands, ["echo hello", f"python3 {helper} session-start"])
        code, out = self.run_install(gh)
        data = json.loads(settings.read_text())
        self.assertEqual(len([h for g in data["hooks"]["SessionStart"] for h in g["hooks"]]), 2)
        self.assertIn("hook already in", out)

    def test_install_refuses_a_key_others_can_read(self):
        shared = self.root / "shared.pem"
        shutil.copy(self.key, shared)
        os.chmod(shared, 0o644)
        with self.assertRaisesRegex(SystemExit, "readable by others"):
            self.run_install(FakeGitHub(), key=shared)

    def test_install_names_what_the_app_has_beyond_a_sessions_needs(self):
        code, out = self.run_install(FakeGitHub(app_permissions=dict(si.SESSION_PERMISSIONS, workflows="write")))
        self.assertEqual(code, 0, out)
        self.assertIn("also has {'workflows': 'write'}", out)

    def test_create_app_makes_the_sessions_app_with_exactly_these_permissions(self):
        m = create_app.manifest("acme-agent-sessions", "acme", 4321, create_app.SESSIONS_PERMISSIONS)
        self.assertEqual(m["default_permissions"], si.SESSION_PERMISSIONS)
        for never in ("workflows", "administration", "secrets", "environments"):
            self.assertNotIn(never, m["default_permissions"])


if __name__ == "__main__":
    unittest.main()
