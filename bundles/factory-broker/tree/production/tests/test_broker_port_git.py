"""Root's git, provenance against main, absolute paths and the drift check's lock (z-sdlc process/factory.md D4 rules 7,
12 and 14), the part the other broker tests don't hold: the exact ssh command and the deploy key, `fetch` into an empty
clone and the timeouts git calls get, a git call's whole process group killed at its timeout, a release merge's second
parent checked against main, every argv and environment variable root uses, and the drift check's wait. Real git
repositories, a mocked GitHub, the fake host. Carried over from the third project's broker tests (test_review.py:
SshHostKeys, Fetch; test_round2.py: ProvenanceMain, BaselineMain, GitTimeout, DriftLock; test_round4.py:
AbsolutePaths, DriftCoverage)."""

import ast
import contextlib
import fcntl
import inspect
import io
import os
import pathlib
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

import fakes
from fakes import Env, TOKEN
import factory_op as fo
import gates
from test_broker_gate import GateBase

SOURCE = (fakes.PROD / "factory_op.py").read_text()
FIRST = fo.tier_names("factory-prod")


def spy_git(repo):
    """A Git whose every call is recorded and answers a commit id, without running git."""
    calls = []

    def runner(argv, **kw):
        calls.append((argv, kw))
        return subprocess.CompletedProcess(argv, 0, "a" * 40 + "\n", "")
    return fo.Git(repo.clone, runner=runner), calls


class SshHostKeysTest(unittest.TestCase):
    def setUp(self):
        self.env = Env()
        self.addCleanup(self.env.close)

    def test_the_ssh_command_pins_host_keys_and_ignores_user_and_system_config(self):
        git, calls = spy_git(self.env.repo)
        key = FIRST["deploy_key"]
        git.fetch("o/r", "+refs/heads/x:refs/y", ssh_key=key)
        command = calls[0][1]["env"]["GIT_SSH_COMMAND"]
        self.assertEqual(command, f"/usr/bin/ssh -F /dev/null -i {key} -o IdentitiesOnly=yes -o BatchMode=yes "
                                  f"-o StrictHostKeyChecking=yes -o UserKnownHostsFile={FIRST['known_hosts']} "
                                  f"-o GlobalKnownHostsFile=/dev/null")
        # Outside a tier's install path (a checkout, CI) the names are the first tier's.
        self.assertEqual(fo.KNOWN_HOSTS, pathlib.Path(FIRST["known_hosts"]))
        self.assertEqual(fo.DEPLOY_KEY, pathlib.Path(FIRST["deploy_key"]))

    def test_fetch_refs_pins_the_deploy_key(self):
        git, calls = spy_git(self.env.repo)
        fo.fetch_refs(self.env.cfg, git)
        fetches = [(argv, kw) for argv, kw in calls if "fetch" in argv]
        self.assertEqual(len(fetches), 1)
        self.assertIn(f"-i {fo.DEPLOY_KEY} ", fetches[0][1]["env"]["GIT_SSH_COMMAND"])
        self.assertIn(fo.default_ssh_remote(self.env.cfg["repo"]), fetches[0][0])


class FetchTest(GateBase):
    def empty_clone(self):
        shutil.rmtree(self.repo.clone)
        subprocess.run([fo.GIT_BIN, *fakes.Repo.NO_SIGN, "init", "-q", "--bare", str(self.repo.clone)], check=True,
                       env=fakes.Repo.ENV)
        self.assertFalse(self.repo.git.has(self.repo.base))

    def test_fetch_populates_an_empty_clone_and_prints_refs_and_shas(self):
        self.empty_clone()
        console = fakes.Console()
        self.assertEqual(fo.cmd_fetch(self.cfg, self.repo.git, console), 0)
        self.assertIn(f"release/production {self.repo.base}", console.lines)
        self.assertIn(f"main {self.repo.base}", console.lines)
        self.assertTrue(self.repo.git.has(self.repo.base))

    def test_fetch_failure_exits_nonzero(self):
        git = fo.Git(self.repo.clone, remote=lambda r: "/nonexistent", ssh_remote=lambda r: "/nonexistent")
        console = fakes.Console()
        self.assertEqual(fo.cmd_fetch(self.cfg, git, console), 1)
        self.assertTrue(any(line.startswith("fetch failed") for line in console.lines), console.lines)

    def test_only_the_fetch_gets_the_long_timeout(self):
        git, calls = spy_git(self.repo)
        fo.fetch_refs(self.cfg, git)
        git.has(self.repo.base)
        self.assertEqual([kw["timeout"] for argv, kw in calls if "fetch" in argv], [fo.FETCH_TIMEOUT_S])
        self.assertEqual({kw["timeout"] for argv, kw in calls if "fetch" not in argv}, {fo.GIT_TIMEOUT_S})

    def test_baseline_fetches_before_it_resolves_the_start_commit(self):
        self.empty_clone()
        self.assertEqual(fo.cmd_baseline(self.cfg, gates, self.env.cat, self.env.secret, "first", False,
                                         self.env.svc_factory(), fakes.Console(["yes"])), 0)
        state = fo.recorded_state(fo.ledger_entries(self.cfg["ledger"]), gates, self.env.public)
        self.assertEqual(state["release_head"], self.repo.base)


class GitTimeoutTest(unittest.TestCase):
    def test_every_git_call_runs_in_its_own_process_group(self):
        self.assertIs(fo.Git(".")._run, fo.run_in_group)

    def test_a_timed_out_git_call_kills_the_whole_process_group(self):
        tmp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        pidfile = tmp / "pid"
        with self.assertRaises(subprocess.TimeoutExpired):
            fo.run_in_group(["/bin/sh", "-c", f"sleep 30 >/dev/null 2>&1 & echo $! > {pidfile}; wait"], env={"PATH": "/usr/bin:/bin"},
                            timeout=0.5, stdin=subprocess.DEVNULL)
        pid = int(pidfile.read_text())
        deadline, alive = time.monotonic() + 3, True
        while alive and time.monotonic() < deadline:
            try:
                os.kill(pid, 0)
                time.sleep(0.05)
            except ProcessLookupError:
                alive = False
        if alive:
            os.kill(pid, signal.SIGKILL)
        self.assertFalse(alive, "ssh (git's child) must die with the git call")

    def test_a_normal_call_returns_its_output_and_exit_code(self):
        r = fo.run_in_group(["/bin/sh", "-c", "echo hi; echo err >&2; exit 3"], env={"PATH": "/usr/bin:/bin"}, timeout=5,
                            stdin=subprocess.DEVNULL)
        self.assertEqual((r.returncode, r.stdout, r.stderr), (3, "hi\n", "err\n"))

    def test_a_timeout_is_a_git_error_not_a_crash(self):
        def runner(argv, **kw):
            raise subprocess.TimeoutExpired(argv, kw["timeout"])
        with self.assertRaises(fo.GitError):
            fo.Git("/nonexistent.git", runner=runner).run("rev-parse", "HEAD")


class ProvenanceMainTest(GateBase):
    """A merge commit proves who merged; its second parent must also be in main, or unreviewed code rides in."""

    def test_a_release_merge_from_main_passes(self):
        sha = self.merge({"README": "r2"})
        head, _, _ = self.pregate(merges=[(sha, 1, None)])
        self.assertEqual(head, sha)
        self.assertTrue(self.repo.git.is_ancestor(self.repo.git.parents(sha)[1], self.repo.git.main_sha()))

    def test_a_commit_with_one_parent_is_refused_even_when_a_merged_pr_claims_it(self):
        sha = self.repo.direct_commit({"README": "x"})
        routes = {f"commits/{sha}/pulls": [{"number": 3, "merge_commit_sha": sha}],
                  "pulls/3": {"merged": True, "merge_commit_sha": sha, "base": {"ref": "release/production"},
                              "merged_by": {"id": fakes.APPROVER}}}
        msg = self.refused(extra=routes)
        self.assertIn(f"release without a PR: {sha}", msg)
        self.assertIn("not a merge commit", msg)

    def test_pregate_fetches_main_with_the_release_branch(self):
        git, calls = spy_git(self.repo)
        fo.fetch_release(self.cfg, git, token=TOKEN)
        argv = calls[0][0]
        self.assertIn(f"+refs/heads/release/production:{fo.RELEASE_REF}", argv)
        self.assertIn(f"+refs/heads/main:{fo.MAIN_REF}", argv)


class BaselineMainTest(GateBase):
    def baseline(self, console, advance=False, merges=()):
        def factory(cfg, token):
            return fo.Services(self.gh(merges), self.repo.git, lambda run: self.env.sandbox)
        return fo.cmd_baseline(self.cfg, gates, self.env.cat, self.env.secret, "n", advance, factory, console)

    def recorded(self):
        return fo.recorded_state(fo.ledger_entries(self.cfg["ledger"]), gates, self.env.public)

    def test_a_hotfix_merged_from_a_branch_main_never_saw_needs_an_accept_for_its_sha(self):
        self.baseline(fakes.Console(["yes"]))
        sha = self.repo.merge_pr({"README": "hotfix"}, via_main=False)
        merges = [(sha, 1, None)]  # an approver merged its PR: who merged is fine, what was merged isn't in main
        console = fakes.Console(["yes", "yes"])
        with self.assertRaises(fo.Refused):
            self.baseline(console, advance=True, merges=merges)
        self.assertTrue(any("merged a branch that is not in main" in line for line in console.lines), console.lines)
        self.assertEqual(self.recorded()["release_head"], self.repo.base)
        self.baseline(fakes.Console([f"accept {sha}", "yes"]), advance=True, merges=merges)
        self.assertEqual(self.recorded()["release_head"], sha)


class AbsolutePathsTest(unittest.TestCase):
    def test_the_constants(self):
        self.assertEqual((fo.SYSTEMD_RUN, fo.SYSTEMCTL, fo.SSH_BIN, fo.PYTHON),
                         ("/usr/bin/systemd-run", "/usr/bin/systemctl", "/usr/bin/ssh", "/usr/bin/python3"))
        self.assertTrue(fo.GIT_BIN.startswith("/"))

    def test_the_sandbox_starts_systemd_run_and_its_step_and_stops_units_by_absolute_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = fakes.make_config(tmp, pathlib.Path(tmp) / "lib")
            calls = []
            sb = fo.Sandbox(cfg, fakes.catalog(), "run", runner=lambda argv, **kw: calls.append(argv), root=tmp)
            argv = sb.argv("u", "/run/x/s", 60, sb.script("health"), {}, hidden="")
            self.assertEqual(argv[0], fo.SYSTEMD_RUN)
            self.assertEqual(argv[-5:], [fo.PYTHON, "-I", f"{cfg['lib_dir']}/factory_op.py", "op", "health"])
            sb.stop_unit("u")
            self.assertEqual(calls, [[fo.SYSTEMCTL, "stop", "u"]])

    def test_roots_git_calls_have_an_absolute_binary_a_fixed_path_and_an_absolute_ssh(self):
        seen = []

        def runner(argv, **kw):
            seen.append((argv, kw["env"]))
            return subprocess.CompletedProcess(argv, 0, "", "")
        git = fo.Git("/nonexistent/clone.git", runner=runner)
        with mock.patch.dict(os.environ, {"PATH": "/nonexistent/evil:/usr/bin"}):
            git.run("rev-parse", "HEAD")
            git.fetch("o/r", "+a:b", ssh_key="/k")
        for argv, env in seen:
            self.assertTrue(argv[0].startswith("/"), argv[0])
            self.assertEqual(env["PATH"], fo.STEP_PATH)
        self.assertTrue(seen[-1][1]["GIT_SSH_COMMAND"].startswith("/usr/bin/ssh -F /dev/null "))

    def test_no_subprocess_argv_in_the_module_starts_with_a_bare_name(self):
        tree = ast.parse(SOURCE)
        launchers = {"runner", "_run", "popen", "Popen", "run_in_group", "stop_unit", "run", "check_call", "check_output"}
        bad = []
        for call in [n for n in ast.walk(tree) if isinstance(n, ast.Call)]:
            name = call.func.attr if isinstance(call.func, ast.Attribute) else getattr(call.func, "id", "")
            if name in launchers and call.args and isinstance(call.args[0], ast.List) and call.args[0].elts:
                first = call.args[0].elts[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str) and not first.value.startswith("/"):
                    bad.append(first.value)
        self.assertEqual(bad, [])
        self.assertNotIn("shutil.which", SOURCE)
        self.assertNotRegex(SOURCE, r'\["(?:systemd-run|systemctl|git|ssh|python3|bash)"')

    def test_the_module_runs_with_only_the_wrappers_path(self):
        """setup's wrapper runs the broker with `env -i PATH=...`. Changed on purpose from the third project's broker: outside a
        tier's install path every command is refused first, so this proves the module loads and refuses cleanly with nothing
        but PATH (the next test proves nothing else is read)."""
        wrapper_env = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin"}
        for argv in (["check"], ["op", "health"], ["egress"]):
            with self.subTest(argv=argv):
                r = subprocess.run([sys.executable, "-I", "-B", str(fakes.PROD / "factory_op.py"), *argv], env=wrapper_env,
                                   capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)
                self.assertEqual(r.returncode, 2, r.stderr)
                self.assertIn("install path", r.stderr)
                self.assertNotIn("Traceback", r.stderr)

    def test_a_step_with_nothing_but_path_fails_closed_with_one_line(self):
        """The in-process half of the wrapper case: `op <name>` with no config it can read exits 1 with one FAILED line and
        writes nothing, never a traceback."""
        with tempfile.TemporaryDirectory() as tmp:
            for environ in ({"PATH": fo.STEP_PATH}, {"PATH": fo.STEP_PATH, "FACTORY_CONFIG": f"{tmp}/missing.json"}):
                with self.subTest(environ=sorted(environ)):
                    err = io.StringIO()
                    with mock.patch("os.geteuid", return_value=1000), \
                            mock.patch.object(fo, "CONFIG", pathlib.Path(tmp) / "no-config.json"):
                        self.assertEqual(fo.op_main("health", environ=environ, stderr=err), 1)
                    lines = err.getvalue().splitlines()
                    self.assertEqual(len(lines), 1, lines)
                    self.assertTrue(lines[0].startswith("FAILED: "), lines)
                    self.assertNotIn("Traceback", err.getvalue())
            self.assertEqual(sorted(pathlib.Path(tmp).iterdir()), [])

    def test_the_module_reads_no_environment_variable_but_sudo_user_and_its_own_step_variables(self):
        names = set(re.findall(r'environ(?:\.get)?\(\s*["\']([A-Z_]+)["\']', SOURCE)) | set(re.findall(r'environ\[["\']([A-Z_]+)["\']\]', SOURCE))
        self.assertTrue(names)
        self.assertLessEqual(names, {"SUDO_USER", "FACTORY_CONFIG", "FACTORY_STEP_DIR", "FACTORY_CLONE", "FACTORY_RELEASE_HEAD",
                                     "FACTORY_RUN", "OP_OUT", "OP_DETAIL"})
        self.assertNotIn("os.getenv", SOURCE)


class DriftLockTest(unittest.TestCase):
    def setUp(self):
        self.env = Env()
        self.addCleanup(self.env.close)
        self.lock = self.env.tmp / "run" / "broker.lock"
        for name, value in (("LOCK", self.lock), ("STEPS_DIR", self.env.tmp / "steps")):
            p = mock.patch.object(fo, name, value)
            p.start()
            self.addCleanup(p.stop)
        fakes.no_live_steps(self)

    def catalog(self, health=None, capture=None):
        cat = fakes.catalog_dict()
        if health:
            cat["operations"]["health"]["timeout_s"] = health
        if capture:
            cat["operations"]["capture-state"]["timeout_s"] = capture
            cat["gate_overhead_s"] = fo.LOCK_WAIT_S + fo.FETCH_TIMEOUT_S + fo.RELEASE_SLACK_S + 2 * (capture + fo.STEP_KILL_MARGIN_S)
        return fakes.load(cat)

    def test_drift_waits_longer_than_a_health_run_can_take(self):
        for health in (60, 600, 900, 2000, 3600):
            with self.subTest(health=health):
                cat = self.catalog(health=health)
                self.assertGreater(fo.drift_lock_wait_s(cat), health + fo.STEP_KILL_MARGIN_S)
                self.assertGreaterEqual(fo.drift_lock_wait_s(cat), fo.DRIFT_LOCK_WAIT_S)

    def test_drift_check_waits_its_catalogs_bound_by_default(self):
        self.assertIsNone(inspect.signature(fo.drift_check).parameters["lock_wait_s"].default)
        seen = []

        @contextlib.contextmanager
        def lock(wait_s, *a, **kw):
            seen.append(wait_s)
            raise fo.LockBusy("held")
            yield  # noqa: unreachable, makes this a generator
        cat = self.catalog(health=2000)
        with mock.patch.object(fo, "broker_lock", lock):
            issues, line = fo.drift_check(self.env.cfg, gates, cat, self.env.secret, self.env.svc_factory())
        self.assertEqual(seen, [fo.drift_lock_wait_s(cat)])
        self.assertEqual((issues, line), (None, "drift: held; nothing was checked"))

    def test_the_bounds_follow_the_catalogs_timeouts(self):
        """Changed on purpose from the third project's broker, which kept module copies of the catalog's timeouts and a test
        tying them: here every bound is computed from the catalog itself."""
        small, large = self.catalog(capture=60), self.catalog(capture=600)
        self.assertEqual(fo.min_gate_overhead_s(large) - fo.min_gate_overhead_s(small), 2 * 540)
        self.assertEqual(fo.drift_unit_min_s(large) - fo.drift_unit_min_s(small), 540)
        self.assertEqual(fo.drift_lock_wait_s(self.catalog(health=3600)) - fo.drift_lock_wait_s(self.catalog(health=3000)), 600)

    def test_the_drift_units_worst_case_adds_up(self):
        for cat in (fakes.catalog(), self.catalog(health=3600, capture=900)):
            with self.subTest():
                floor = (fo.drift_lock_wait_s(cat) + fo.FETCH_TIMEOUT_S + cat["operations"]["capture-state"]["timeout_s"]
                         + cat["broker"]["internal_ops"]["drift-scan"]["timeout_s"] + 2 * fo.STEP_KILL_MARGIN_S)
                self.assertGreaterEqual(fo.drift_unit_min_s(cat), floor + fo.GIT_CALLS_BUDGET_S)
        self.assertEqual(fo.HEALTH_LOCK_WAIT_S, 60)

    def test_resolve_takes_the_lock(self):
        fo.ledger_append(self.env.cfg["ledger"], {"event": "start", "run": "r1", "repo": self.env.cfg["repo"], "pr": 1, "issue": 1,
                                                  "gate": "G1", "attempt": 1, "digest": "d" * 64, "github_run": 5})
        self.lock.parent.mkdir(parents=True)
        held = open(self.lock, "a")
        self.addCleanup(held.close)
        fcntl.flock(held, fcntl.LOCK_EX)
        with self.assertRaises(fo.Refused):
            fo.cmd_resolve(self.env.cfg, gates, self.env.secret, "r1", "note", lock_wait_s=0)
        self.assertEqual(fo.unfinished(fo.ledger_entries(self.env.cfg["ledger"])), ["r1"])
        fcntl.flock(held, fcntl.LOCK_UN)
        self.assertEqual(fo.cmd_resolve(self.env.cfg, gates, self.env.secret, "r1", "note", lock_wait_s=0), 0)
        self.assertEqual(fo.unfinished(fo.ledger_entries(self.env.cfg["ledger"])), [])

    def test_our_lock_is_flock_compatible_with_bash_flock(self):
        with fo.broker_lock(0, steps_dir=self.env.tmp / "steps"):
            other = open(self.lock, "a")
            self.addCleanup(other.close)
            with self.assertRaises(BlockingIOError):
                fcntl.flock(other, fcntl.LOCK_EX | fcntl.LOCK_NB)  # flock(2), as bash `flock -w` takes it
        fcntl.flock(other, fcntl.LOCK_EX | fcntl.LOCK_NB)


class DriftCoverageTest(GateBase):
    def setUp(self):
        super().setUp()
        self.append_baseline(self.state)

    def drift(self):
        svc = fo.Services(self.gh(), self.repo.git, lambda run: self.env.sandbox)
        return fo.drift_check(self.cfg, gates, self.env.cat, self.env.secret, lambda c, t: svc, now_dt=self.clock.now())

    def test_a_release_through_main_raises_no_alarm_and_a_hotfix_is_named_by_its_merge(self):
        self.merge({"README": "r2"})
        self.assertEqual(self.drift(), ([], "drift: ok"))
        sha = self.repo.merge_pr({"README": "hotfix"}, via_main=False)
        self.assertIn(f"release {sha[:12]} merged a branch that is not in main", self.drift()[1])


if __name__ == "__main__":
    unittest.main()
