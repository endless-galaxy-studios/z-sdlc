"""Test doubles for the checks-only broker: a fake clock, a mocked GitHub API, real throwaway git repositories, an
installed library directory in a temp dir, and an in-process sandbox that runs the real step code (`op_main`, with the
host module loaded by its path) against fake_host's world, so a test exercises the path a step takes, without systemd
or a network. Every value is a documentation value: example.com hosts, made-up ids, services `web`, `jobs`, `proxy`
and `cache`."""

import base64
import copy
import datetime
import io
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
from unittest import mock

PROD = pathlib.Path(__file__).resolve().parents[1]
FACTORY = PROD.parent
TESTS = pathlib.Path(__file__).resolve().parent
for p in (str(PROD), str(FACTORY)):
    if p not in sys.path:
        sys.path.insert(0, p)
import ed25519  # noqa: E402
import factory_op as fo  # noqa: E402
import fake_host  # noqa: E402
import gates  # noqa: E402

UTC = datetime.timezone.utc
FAKE_HOST = TESTS / "fake_host.py"
SENTINEL_TOKEN = fake_host.SENTINEL_TOKEN
SENTINEL_VALUE = fake_host.SENTINEL_VALUE
FP_KEY = bytes(range(32))
REPO_NAME = "example/app"
APP_ID, APPROVER = 1001, 2002
TOKEN = "ghs_" + "x" * 30
DEP = "^dep-[0-9]{4}$"
SHA40 = "^[0-9a-f]{40}$"
FP = "^[0-9a-f]{64}$"

SERVICES = {
    "web": {"release": True, "checked": True, "evidence": "reports", "patterns": ["web/**", "shared/**"]},
    "jobs": {"release": True, "checked": True, "evidence": "heartbeat", "patterns": ["jobs/**", "shared/**"]},
    "proxy": {"release": False, "checked": True, "evidence": "none", "patterns": ["/proxy/**"]},
    "cache": {"release": False, "checked": False, "evidence": "none"},
}

# The broker's own worst case around a gate's steps for this catalog: the lock wait, the fetch, the release gate's
# checks' slack, and two captures, each with the kill margin (fo.min_gate_overhead_s).
CAPTURE_TIMEOUT_S = 300
GATE_OVERHEAD_S = 1800 + 600 + 1200 + 2 * (CAPTURE_TIMEOUT_S + 90)

CATALOG = {
    "version": 1,
    "release_gates": True,
    "rollbacks": False,
    "release_wait": "release-wait",
    "gate_overhead_s": GATE_OVERHEAD_S,
    "step_margin_s": 90,
    "operations": {
        "health": {
            "kind": "read", "summary": "Every service serves a successful deployment and the release services prove it",
            "params": {},
            "outputs": {"healthy": "^(yes|no)$", "services": "^[0-9]{1,2}$", "unhealthy": "^[a-z0-9_,]{0,200}$",
                        "web_deployment": DEP, "jobs_deployment": DEP},
            "timeout_s": 600},
        "release-wait": {
            "kind": "read", "summary": "Wait for the release that contains the commit to be live, with evidence",
            "params": {"sha": SHA40},
            "outputs": {"head": SHA40, "deployed": "^((web|jobs)(,(web|jobs))?)?$", "web_deployment": DEP,
                        "jobs_deployment": DEP},
            "timeout_s": 900},
        "http-check": {
            "kind": "read", "summary": "One unauthenticated GET to a declared target",
            "params": {"target": "^(web)$", "path": "^/(?!.*\\.\\.)[a-z0-9_./-]{0,80}$", "expect_status": "^[1-5][0-9]{2}$"},
            "outputs": {"status": "^[0-9]{3}$", "latency_ms": "^[0-9]{1,6}$", "body_sha256": FP},
            "timeout_s": 60},
        "capture-state": {
            "kind": "read", "summary": "What the host serves and a keyed hash of each service's settings",
            "params": {},
            "outputs": {"web_commit": SHA40, "jobs_commit": SHA40, "proxy_commit": "^([0-9a-f]{40})?$",
                        "web_settled": "^(yes|no)$", "jobs_settled": "^(yes|no)$", "proxy_settled": "^(yes|no)$",
                        "fp_web": FP, "fp_jobs": FP, "fp_proxy": FP, "fp_cache": FP, "fp_shared": FP,
                        "fp_key_id": "^[0-9a-f]{8}$", "staged": "^(none|pending)$", "mode": "^(auto|locked|manual)$",
                        "mode_source": "^[ -~]{0,100}$"},
            "timeout_s": CAPTURE_TIMEOUT_S},
        "snapshot-status": {
            "kind": "read", "summary": "The newest snapshot and whether it is fresh",
            "params": {}, "outputs": {"last_at": "^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$",
                                      "fresh": "^(yes|no)$"},
            "timeout_s": 90},
        "snapshot-now": {
            "kind": "change", "summary": "Take one snapshot", "params": {}, "outputs": {"snapshot_id": "^snap-[0-9]{4}$"},
            "timeout_s": 600},
    },
    "broker": {
        "egress": ["api.host.example", "web.example.com"],
        "http_targets": {"web": "web.example.com"},
        "secrets": {"token": {"file": "host.token", "by": "cd", "hex": False},
                    "key": {"file": "fingerprint.key", "by": "setup", "hex": True}},
        "op_secrets": {"health": ["token"], "release-wait": ["token"], "http-check": [], "capture-state": ["token", "key"],
                       "snapshot-status": ["token"], "snapshot-now": ["token"], "drift-scan": ["token"],
                       "host-check": ["token"], "check-token": ["token"]},
        "host_ops": ["snapshot-status", "snapshot-now"],
        "services": SERVICES,
        "heartbeat_ttl_s": 60,
        "release_wait_phases": {"grace_s": 120, "build_s": 300, "evidence_s": 180},
        "recorded": ["fp_web", "fp_jobs", "fp_proxy", "fp_cache", "fp_shared", "fp_key_id"],
        "invariants": {
            "staged": {"is": "none", "why": "the host has a staged change: apply or discard it first"},
            "mode": {"in": ["auto", "locked"], "show": ["mode_source"], "why": "a service deploys by hand: set it back"},
        },
        "internal_ops": {"drift-scan": {"timeout_s": 300}, "host-check": {"timeout_s": 60}, "check-token": {"timeout_s": 120}},
        "python": "3.8",
        "host_locks": [],
    },
}


def catalog_dict(**changes):
    """A deep copy of CATALOG; `broker__<key>=value` changes a block key (None deletes it), any other a catalog key."""
    cat = copy.deepcopy(CATALOG)
    for key, value in changes.items():
        target, name = (cat["broker"], key[len("broker__"):]) if key.startswith("broker__") else (cat, key)
        if value is None:
            target.pop(name, None)
        else:
            target[name] = value
    return cat


def load(cat):
    return gates.load_catalog(json.dumps(cat))


def catalog():
    return load(catalog_dict())


def no_live_steps(test):
    """systemd isn't here: report no step unit of the tier running (fo.live_step_units), for the test's duration. Tests of
    the check itself (test_broker_steps_live.py) patch it their own way."""
    p = mock.patch.object(fo, "live_step_units", return_value=[])
    p.start()
    test.addCleanup(p.stop)


class FakeClock:
    def __init__(self):
        self.t = 0.0
        self.base = datetime.datetime(2026, 11, 5, 12, 0, 0, tzinfo=UTC)

    def monotonic(self):
        return self.t

    def sleep(self, seconds):
        self.t += seconds

    def now(self):
        return self.base + datetime.timedelta(seconds=self.t)

    def time(self):
        return self.now().timestamp()


def make_config(tmp, lib):
    tmp = pathlib.Path(tmp)
    return {"repo": REPO_NAME, "default_branch": "main", "release_branch": "release/production",
            "release_head_start": "0" * 10, "app_bot_id": APP_ID, "approvers": [APPROVER],
            "operator_user": "factory-prod-op", "lib_dir": str(lib), "ledger": str(tmp / "state" / "ledger.jsonl"),
            "log_dir": str(tmp / "logs"), "clone_dir": str(tmp / "clone.git"), "instance": "",
            "host": {"project": "proj-1", "services": {svc: f"svc-{svc}" for svc in SERVICES}}}


class Seq(list):
    """Successive answers for one GitHub path (the last repeats)."""


class FakeOpener:
    """The GitHub API: {path after /repos/<repo>/: JSON body}; a missing path answers 404."""

    def __init__(self, repo, routes):
        self.prefix, self.routes, self.calls = f"{fo.GITHUB_API}/repos/{repo}/", routes, []

    def open(self, req, timeout=None):
        self.calls.append(req.full_url)
        path = req.full_url[len(self.prefix):].split("?")[0] if req.full_url.startswith(self.prefix) else None
        if path is None or path not in self.routes:
            raise urllib.error.HTTPError(req.full_url, 404, "nope", {}, None)
        value = self.routes[path]
        if isinstance(value, Seq):
            value = value.pop(0) if len(value) > 1 else value[0]
        body, headers = value if isinstance(value, tuple) else (value, {})
        payload, hdrs = json.dumps(body).encode(), dict(headers)

        class R:
            headers = hdrs

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return payload
        return R()


class Repo:
    """A throwaway "remote" with a release/production branch of merge commits, plus a bare clone fed from it. git never
    reads the user's or the system's config (no signing, no hooks)."""

    ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@example.com", "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1",
           "HOME": "/nonexistent", "PATH": os.environ.get("PATH", "")}
    NO_SIGN = ("-c", "commit.gpgsign=false", "-c", "tag.gpgsign=false")

    def __init__(self, tmp):
        self.tmp = pathlib.Path(tmp)
        self.work = self.tmp / "work"
        self.work.mkdir()
        self.sh("init", "-q", "-b", "release/production")
        self.write({"web/app.txt": "w1", "jobs/work.txt": "j1", "shared/lib.txt": "s1", "proxy/p.txt": "p1", "README": "r"})
        self.sh("add", "-A")
        self.sh("commit", "-q", "-m", "base")
        self.base = self.sh("rev-parse", "HEAD")
        self.sh("branch", "main")
        self.n = 0
        self.clone = self.tmp / "clone.git"
        subprocess.run([fo.GIT_BIN, *self.NO_SIGN, "init", "-q", "--bare", str(self.clone)], check=True, env=self.ENV)
        self.git = fo.Git(self.clone, remote=lambda repo: str(self.work), ssh_remote=lambda repo: str(self.work))

    def sh(self, *args):
        return subprocess.run([fo.GIT_BIN, *self.NO_SIGN, "-C", str(self.work), *args], check=True, capture_output=True,
                              text=True, env=self.ENV).stdout.strip()

    def write(self, files):
        for path, text in files.items():
            p = self.work / path
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text)

    def head(self):
        return self.sh("rev-parse", "release/production")

    def merge_pr(self, files, number=None, via_main=True):
        """A PR branch merged with a merge commit, as GitHub's merge button does. Returns the merge commit. By default the
        PR was merged into main first (the normal path); via_main=False is a branch main never saw (a hotfix)."""
        self.n += 1
        number = number or self.n
        self.sh("checkout", "-q", "-b", f"pr{number}")
        self.write(files)
        self.sh("add", "-A")
        self.sh("commit", "-q", "-m", f"work {number}")
        if via_main:
            self.sh("checkout", "-q", "main")
            self.sh("merge", "-q", "--no-ff", "-m", f"Merge pull request #{number} into main", f"pr{number}")
        self.sh("checkout", "-q", "release/production")
        self.sh("merge", "-q", "--no-ff", "-m", f"Merge pull request #{number} from x/pr{number}", f"pr{number}")
        return self.head()

    def direct_commit(self, files):
        self.write(files)
        self.sh("add", "-A")
        self.sh("commit", "-q", "-m", "direct push")
        return self.head()

    def fetch(self):
        self.git.fetch("x", f"+refs/heads/release/production:{fo.RELEASE_REF}", f"+refs/heads/main:{fo.MAIN_REF}")


def github_for(cfg, repo, merges, approver=None, extra=None):
    """Routes for the pregate: branch head and, for each (sha, number, merged_by) in `merges`, its PR."""
    approver = approver or cfg["approvers"][0]
    routes = {"branches/release%2Fproduction": {"name": "release/production", "commit": {"sha": repo.head()}}}
    for sha, number, by in merges:
        routes[f"commits/{sha}/pulls"] = [{"number": number, "merge_commit_sha": sha}]
        routes[f"pulls/{number}"] = {"merged": True, "merge_commit_sha": sha, "base": {"ref": "release/production"},
                                      "merged_by": {"id": by if by is not None else approver}}
    routes.update(extra or {})
    return fo.GitHub(cfg["repo"], TOKEN, opener=FakeOpener(cfg["repo"], routes))


OPS_PLAN_PATH = "docs/current_work/planning/d99_thing_plan.md"
OPS_PLAN = """# D99: Thing

### Phase 1: Code

Write it.

### Gate G1: Production is healthy

**After:** Phase 1. **Changes production:** no.

```gate-ops
{"steps": [{"op": "health"}]}
```

### Phase 2: Records

Write the result.
"""


def gate_routes(env, plan=OPS_PLAN, pr=7, issue=3, gate="G1", run_id=55, head="a" * 40, kind=None, request=None):
    """GitHub, for one gate run end to end through serve_one: the run, its approval, the execution PR, its tracker and
    the plan on the default branch. Returns (routes, request); `kind` overrides the run title's kind."""
    cfg = env.cfg
    if request is None:
        request = gates.build_request(repo=cfg["repo"], issue=issue, pr=pr, plan=OPS_PLAN_PATH, plan_blob="b" * 40,
                                      plan_text=plan, gate_id=gate, attempt=1, head=head, catalog=env.cat, gate_outputs={},
                                      ops_digest=gates.ops_digest(gates.installed_ops_files(cfg["lib_dir"])))
    title = gates.run_title({**request, "kind": kind or request["kind"]})
    tracker = {"id": 1, "created_at": "2026-11-05T00:00:00Z", "user": {"type": "Bot", "id": cfg["app_bot_id"]},
               "body": gates.marker(gates.TRACKER, {"v": 1, "issue": issue, "plan": OPS_PLAN_PATH, "stopped_at": gate})}
    routes = {
        f"actions/runs/{run_id}": {"path": ".github/workflows/factory-gate.yml@refs/heads/main", "head_branch": "main",
                                   "event": "workflow_dispatch", "repository": {"full_name": cfg["repo"]},
                                   "status": "in_progress", "display_title": title},
        f"actions/runs/{run_id}/approvals": [{"state": "approved", "user": {"id": cfg["approvers"][0]},
                                              "environments": [{"name": "factory-production"}]}],
        f"pulls/{pr}": {"head": {"ref": f"factory/{issue}-impl", "sha": head, "repo": {"full_name": cfg["repo"]}},
                        "state": "open", "user": {"id": cfg["app_bot_id"]}},
        f"issues/{pr}/comments": [tracker],
        f"contents/{urllib.parse.quote(OPS_PLAN_PATH)}": {"encoding": "base64", "content": base64.b64encode(plan.encode()).decode(),
                                                          "sha": "b" * 40},
        "branches/release%2Fproduction": {"name": "release/production", "commit": {"sha": env.repo.head()}},
    }
    return routes, request


class InProcessSandbox:
    """Runs the real step code in this process, with the step directory, environment, secrets and output files the real
    sandbox gives it, against the fake world, and reads its files back with root's own filters."""

    def __init__(self, world, cfg, cat, tmp, run_id="r1", host_module=FAKE_HOST):
        self.world, self.cfg, self.cat, self.tmp, self.run_id = world, cfg, cat, pathlib.Path(tmp), run_id
        self.host_module = host_module
        self.cfg_file = self.tmp / "config.json"
        self.cfg_file.write_text(json.dumps(cfg))
        self.stderr = io.StringIO()
        self.out_files, self.runs, self.token_for_step, self.envs = [], [], None, []

    def secret_value(self, label):
        return {"token": self.token_for_step or self.world.token, "key": FP_KEY.hex()}[label]

    def run(self, name, op, params, tag, log_path, release_head=""):
        self.cfg_file.write_text(json.dumps(self.cfg))
        step = self.tmp / f"step-{self.run_id}-{tag}-{len(self.runs)}"
        step.mkdir()
        block = self.cat["broker"]
        installed = []
        for label in block["op_secrets"][name]:  # an operation without an entry is an error, as in the real sandbox
            data = self.secret_value(label).encode()
            (step / f"secret-{label}").write_bytes(data)
            installed.append((label, data, block["secrets"][label]["hex"]))
        env = {"OP_OUT": str(step / "out"), "OP_DETAIL": str(step / "detail.json"), "FACTORY_STEP_DIR": str(step),
               "FACTORY_CLONE": self.cfg["clone_dir"], "FACTORY_CONFIG": str(self.cfg_file),
               "FACTORY_RELEASE_HEAD": release_head, "FACTORY_RUN": self.run_id}
        env.update({f"OP_{k.upper()}": v for k, v in params.items()})
        self.envs.append(env)
        err = io.StringIO()
        with mock.patch("os.geteuid", return_value=1000):
            rc = fo.op_main(name, env, connect=self.world.connect, clock=self.world.clock, stderr=err,
                            host_module=self.host_module)
        self.stderr.write(err.getvalue())
        pathlib.Path(log_path).write_text(fo.redact(err.getvalue(), fo.secrets_to_redact(installed)))
        self.out_files.append(step / "out")
        self.runs.append((name, rc))
        out_text = (step / "out").read_text() if (step / "out").exists() else ""
        detail_text = (step / "detail.json").read_text() if (step / "detail.json").exists() else ""
        outputs, detail = fo.read_step_files(name, op, out_text, detail_text, block["services"], installed)
        if rc != 0:
            return fo.StepResult("failed", outputs, detail, fo.scrub(fo.last_line(log_path)) or f"exit {rc}")
        missing = sorted(set(op.get("outputs", {})) - set(outputs))
        if missing:
            return fo.StepResult("failed", outputs, detail, f"missing or refused outputs: {', '.join(missing)}")
        return fo.StepResult("done", outputs, detail)


class Console:
    def __init__(self, answers=None, secret=TOKEN):
        self.lines, self.answers, self._secret, self.asked = [], list(answers or []), secret, []

    def say(self, text):
        self.lines.append(text)

    def ask(self, prompt):
        self.asked.append(prompt)
        return self.answers.pop(0) if self.answers else "yes"

    def secret(self, prompt):
        return self._secret


class Env:
    """A complete test environment: a temp dir, an installed library (gates.py, ed25519.py, factory_op.py, ops.json,
    config.json and receipt.pub, as setup installs them), config, clock, the fake host's world on the repository's base
    commit, git and the in-process sandbox."""

    def __init__(self, cat=None, host_module=FAKE_HOST):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = pathlib.Path(self._tmp.name)
        self.repo = Repo(self.tmp)
        self.lib = self.tmp / "lib"
        self.lib.mkdir()
        for name in ("gates.py", "ed25519.py"):
            shutil.copy(FACTORY / name, self.lib / name)
        shutil.copy(PROD / "factory_op.py", self.lib / "factory_op.py")
        self.cat_dict = cat or catalog_dict()
        (self.lib / "ops.json").write_text(json.dumps(self.cat_dict, indent=1))
        self.secret = bytes(range(1, 33))
        self.public = ed25519.public_key(self.secret).hex()
        (self.lib / "receipt.pub").write_text(self.public + "\n")
        self.cfg = make_config(self.tmp, self.lib)
        self.cfg["release_head_start"] = self.repo.base[:10]
        (self.lib / "config.json").write_text(json.dumps(self.cfg))  # the copy setup installs beside the broker, which it reads
        self.clock = FakeClock()
        self.cat = gates.load_catalog((self.lib / "ops.json").read_text())
        self.world = fake_host.HostWorld(self.cfg, self.clock, self.repo.base, self.cat["broker"]["services"])
        self.sandbox = InProcessSandbox(self.world, self.cfg, self.cat, self.tmp, host_module=host_module)
        self.repo.fetch()
        (self.tmp / "logs").mkdir()

    def close(self):
        self._tmp.cleanup()

    def run_op(self, name, release_head=None, **params):
        op = fo.op_of(self.cat, name)
        head = self.repo.head() if release_head is None else release_head
        return self.sandbox.run(name, op, params, "t", self.tmp / "logs" / f"{name}.log", head)

    def services(self, gh):
        return fo.Services(gh, self.repo.git, lambda run: self.sandbox)

    def svc_factory(self, gh=None):
        return lambda cfg, token: fo.Services(gh or github_for(cfg, self.repo, []), self.repo.git, lambda run: self.sandbox)

    def capture_state(self, release_head=None):
        res = self.run_op("capture-state", release_head=release_head)
        assert res.status == "done", res.why
        return fo.state_from(res.outputs, release_head or self.repo.base, self.cat["broker"])

    def append_baseline(self, state, secret=None, at="2026-11-05T11:00:00Z"):
        signed = gates.sign_receipt(secret or self.secret, {"v": 1, "kind": "baseline", "run": "b", "deployed_state": state,
                                                            "accepted": [], "note": "n", "by": "t", "at": at})
        fo.ledger_append(self.cfg["ledger"], {"event": "baseline", "run": "b", "repo": self.cfg["repo"], "at": at,
                                              "signed": signed})
