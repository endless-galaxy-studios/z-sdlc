"""An in-memory host for the broker's tests (z-sdlc's factory-broker bundle).

Two halves:

- `HostWorld` is the host: each service's deployments, its settings, the shared settings, snapshots, and what the
  running services answer. A test changes it as it likes. Steps reach it only over the wire, through the broker's
  own egress path (`ctx.https`, so the egress allowlist applies), never through module state: a step loads this file
  by its path, so it is a separate module object from the one a test imports.
- The module-level functions are the host module itself: the contract a project's `production/factory_op_host.py`
  implements (`client`, `preflight`, `latest`, `deployments`, `serving`, `reports`, `heartbeat`, `capture`, `OPS`,
  `DIAGNOSTICS`), for a host with a JSON API at `api.host.example` and an app at `web.example.com`.

The declared services (fakes.CATALOG's block): `web` is a release service that reports its deployment on the app's
/ready; `jobs` is a release service with a heartbeat, which the app's /ready carries too; `proxy` is checked but
deployed by hand; `cache` is neither.
"""

import datetime
import hashlib
import hmac
import json
import os

from factory_op import NETWORK_ERRORS, SHA, Deployment, HostError, StepFailed, Unavailable, canonical, parse_ts, safe

API = "api.host.example"
APP = "web.example.com"
USER_AGENT = "factory-op-test"
# The host's own words for a deployment's state, and the contract's. Anything else is "failed".
STATUS = {"SUCCESS": "success", "SKIPPED": "skipped", "FAILED": "failed", "CRASHED": "crashed", "REMOVED": "failed",
          "BUILDING": "waiting", "QUEUED": "waiting", "DEPLOYING": "waiting"}
TERMINAL = ("success", "skipped", "failed", "crashed")
KEY_ID_LABEL = b"fake host fp_key_id"
# (requests, waiting seconds) of each operation's worst case, for the budget fitness test.
BUDGET = {"health": (12, 61), "release-wait": (0, 600), "http-check": (1, 0), "capture-state": (8, 0),
          "snapshot-status": (2, 0), "snapshot-now": (2, 0), "drift-scan": (5, 0), "host-check": (1, 0),
          "check-token": (1, 0)}


def status_of(word):
    return STATUS.get(word, "failed")


# ---------------------------------------------------------------- the host module (what a step loads)

class Client:
    """Read-only: GETs. The one POST is built only by the operation that changes something."""

    def __init__(self, ctx, token):
        self.ctx, self.token = ctx, token

    def get(self, path):
        return self._send("GET", path, None)

    def _send(self, method, path, body):
        headers = {"Authorization": f"Bearer {self.token}", "Accept": "application/json", "User-Agent": USER_AGENT}
        if body is not None:
            headers["Content-Type"] = "application/json"
        try:
            status, _, data = self.ctx.https(API, method, path, headers, body, max_bytes=1 << 20)
        except NETWORK_ERRORS as e:
            raise HostError(f"the host API is unreachable: {safe(e, 60)}") from None
        if status != 200:
            raise HostError(f"the host API answered HTTP {status}")
        try:
            return json.loads(data)
        except ValueError:
            raise HostError("the host API's answer wasn't JSON") from None


class ChangeClient(Client):
    def post(self, path, body):
        return self._send("POST", path, json.dumps(body).encode())


def client(ctx):
    return Client(ctx, ctx.secret("token") if ctx.has_secret("token") else "")


def preflight(ctx):
    host = ctx.host
    services = host.get("services")
    if not isinstance(host.get("project"), str) or not hasattr(services, "keys") or set(services) != set(ctx.services):
        raise StepFailed("config.json's host block doesn't name exactly the declared services")
    if ctx.has_secret("token") and ctx.client.get("/v1/whoami").get("project") != host["project"]:
        raise StepFailed("the token isn't for the configured project")


def deployment_of(row):
    try:
        created = parse_ts(row.get("created"))
    except StepFailed:
        created = None
    return Deployment(id=row.get("id"), commit=row.get("commit"), status=status_of(row.get("status")), created=created,
                      branch=row.get("branch"))


def latest(ctx):
    return {svc: (status_of(word) if word else None) for svc, word in ctx.client.get("/v1/latest").items()}


def deployments(ctx, svc):
    return [deployment_of(row) for row in ctx.client.get(f"/v1/services/{svc}/deployments")]


def serving(ctx, svc):
    row = ctx.client.get(f"/v1/services/{svc}/serving")
    return deployment_of(row) if row else None


def read_app(ctx):
    try:
        status, _, data = ctx.https(APP, "GET", f"/ready?_={os.urandom(6).hex()}",
                                    {"Accept": "application/json", "Cache-Control": "no-cache", "User-Agent": USER_AGENT},
                                    None, max_bytes=1 << 16)
    except (HostError, *NETWORK_ERRORS) as e:
        raise Unavailable(f"the app's /ready read failed: {safe(e, 60)}") from None
    if status != 200:
        raise Unavailable(f"the app's /ready answered HTTP {status}")
    try:
        doc = json.loads(data)
    except ValueError:
        raise Unavailable("the app's /ready answer wasn't JSON") from None
    if not isinstance(doc, dict):
        raise Unavailable("the app's /ready answer wasn't an object")
    return doc


def reports(ctx, svc, deployment_id):
    if svc != "web":
        raise StepFailed(f"{safe(svc, 30)} reports no deployment id")
    doc = read_app(ctx)
    return doc.get("deployment_id") == deployment_id and doc.get("status") == "ready"


def heartbeat(ctx, svc, deployment_id, patient):
    if svc != "jobs":
        raise StepFailed(f"{safe(svc, 30)} has no heartbeat")
    doc = read_app(ctx)
    if doc.get("jobs_deployment_id") != deployment_id:
        return None
    state = doc.get("jobs_state")
    if state == "failed":
        raise StepFailed("jobs: its startup failed")
    if state != "ready":
        if patient:
            return None
        raise StepFailed(f"jobs: its state is {safe(state, 20)!r}, not 'ready'")
    try:
        return parse_ts(doc.get("jobs_started_at")), parse_ts(doc.get("jobs_written_at"))
    except StepFailed:
        return None


def fingerprint(key, obj):
    return hmac.new(key, canonical(obj).encode(), hashlib.sha256).hexdigest()


def capture(ctx):
    if not SHA.fullmatch(ctx.release_head or ""):
        raise StepFailed("capture-state needs the release branch's head")
    state = ctx.client.get("/v1/state")
    services = state["services"]
    for svc, declared in ctx.services.items():
        if declared["release"]:
            builds = services[svc].get("patterns") or []
            ctx.note(f"{svc}: builds from {', '.join(builds)}")
            if sorted(builds) != sorted(declared["patterns"]):
                raise StepFailed(f"{svc}: the host builds it from patterns other than the declared ones")
    now = latest(ctx)
    key = ctx.secret("key")
    out = {}
    for svc, declared in ctx.services.items():
        if declared["checked"]:
            dep = serving(ctx, svc)
            if dep is None or (declared["release"] and dep.commit is None):
                raise StepFailed(f"{svc}: no serving deployment with a commit")
            out[f"{svc}_commit"] = dep.commit or ""
            out[f"{svc}_settled"] = "yes" if now.get(svc) in TERMINAL else "no"
        out[f"fp_{svc}"] = fingerprint(key, services[svc]["settings"])
    out["fp_shared"] = fingerprint(key, state["shared"])
    out["fp_key_id"] = hmac.new(key, KEY_ID_LABEL, hashlib.sha256).hexdigest()[:8]
    out["staged"], out["mode"], out["mode_source"] = state["staged"], state["mode"], state["mode_source"]
    return out


def op_snapshot_status(ctx):
    rows = ctx.client.get("/v1/snapshots")
    if not rows:
        raise StepFailed("the host has no snapshot")
    newest = max(rows, key=lambda r: r["at"])
    age = (ctx.clock.now() - parse_ts(newest["at"])).total_seconds()
    out = {"last_at": newest["at"], "fresh": "yes" if age < 26 * 3600 else "no"}
    if out["fresh"] != "yes":
        raise StepFailed("the newest snapshot is over 26 hours old", out)
    return out


def op_snapshot_now(ctx):
    row = ChangeClient(ctx, ctx.secret("token")).post("/v1/snapshots", {"name": f"factory {ctx.run}"})
    return {"snapshot_id": row["id"]}


def check_token(ctx):
    who = ctx.client.get("/v1/whoami")
    ctx.note(f"the token's project: {safe(who.get('project'), 60)}")
    if who.get("project") != ctx.host.get("project"):
        raise StepFailed("the token is for another project")


OPS = {"snapshot-status": op_snapshot_status, "snapshot-now": op_snapshot_now}
DIAGNOSTICS = {"check-token": check_token}


# ---------------------------------------------------------------- the world (what a test changes)

SENTINEL_TOKEN = "sentinel-host-token-0123456789abcdef"
SENTINEL_VALUE = "sentinel-setting-value-do-not-print"


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")


class Resp:
    def __init__(self, status, headers, data):
        self.status, self._headers, self._data = status, headers, data

    def getheaders(self):
        return list(self._headers.items())

    def read(self, n=-1):
        return self._data if n < 0 else self._data[:n]


class Conn:
    def __init__(self, world, host):
        self.world, self.host = world, host

    def request(self, method, path, body=None, headers=None):
        self.call = (method, path, body, headers or {})

    def getresponse(self):
        return self.world.serve(self.host, *self.call)

    def close(self):
        pass


class HostWorld:
    """The host and its running services, as one mutable fake of production."""

    def __init__(self, cfg, clock, commit, services):
        self.cfg, self.clock, self.services = cfg, clock, services
        self.token, self.project = SENTINEL_TOKEN, cfg["host"]["project"]
        self.deployments = {svc: [] for svc in services}
        self.settings = {svc: {"replicas": 1, "SECRET": SENTINEL_VALUE} for svc in services}
        self.patterns = {svc: list(d["patterns"]) for svc, d in services.items() if d["release"]}
        self.shared = {"SHARED": SENTINEL_VALUE}
        self.staged, self.mode, self.mode_source = "none", "auto", "the service settings"
        self.snapshots = [{"id": "snap-0001", "at": (clock.now() - datetime.timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%SZ")}]
        self.requests, self.app_calls, self.hooks, self.script, self.created = [], [], [], [], []
        self.latency, self.headers, self.n = 0.2, {}, 0
        for svc, declared in services.items():
            self.add(svc, "SUCCESS", commit if declared["checked"] else None, age=3 * 3600)
        self.ready = self.default_ready
        self.page = lambda path: Resp(200, {}, b"ok")

    def add(self, svc, status, commit=None, age=0, branch=None):
        self.n += 1
        row = {"id": f"dep-{self.n:04d}", "status": status,
               "created": iso(self.clock.now() - datetime.timedelta(seconds=age)), "commit": commit,
               "branch": (branch or self.cfg["release_branch"]) if commit else branch}
        self.deployments[svc].insert(0, row)
        return row

    def serving(self, svc):
        return next((r for r in self.deployments[svc] if r["status"] == "SUCCESS"), None)

    def default_ready(self):
        web, jobs = self.serving("web") or {}, self.serving("jobs") or {}
        return {"status": "ready", "deployment_id": web.get("id"), "jobs_deployment_id": jobs.get("id"),
                "jobs_state": "ready", "jobs_started_at": jobs.get("created"), "jobs_written_at": iso(self.clock.now())}

    def connect(self, host, timeout):
        return Conn(self, host)

    # -- the wire
    def serve(self, host, method, path, body, headers):
        self.clock.sleep(self.latency)
        for hook in list(self.hooks):
            hook(self)
        if self.script:
            return Resp(self.script.pop(0), {}, b"{}")
        if host == API:
            return self.api(method, path, body, headers)
        self.app_calls.append((host, method, path, headers))
        if path.startswith("/ready?"):
            value = self.ready()
            return value if isinstance(value, Resp) else Resp(200, dict(self.headers), json.dumps(value).encode())
        return self.page(path)

    def api(self, method, path, body, headers):
        if headers.get("Authorization") != f"Bearer {self.token}":
            return Resp(401, {}, b"{}")
        self.requests.append((method, path))
        parts = path.split("/")
        if method == "GET" and path == "/v1/whoami":
            value = {"project": self.project}
        elif method == "GET" and path == "/v1/latest":
            value = {svc: (rows[0]["status"] if rows else None) for svc, rows in self.deployments.items()}
        elif method == "GET" and len(parts) == 5 and parts[:3] == ["", "v1", "services"] and parts[3] in self.deployments:
            if parts[4] == "deployments":
                value = self.deployments[parts[3]][:20]
            elif parts[4] == "serving":
                value = self.serving(parts[3])
            else:
                return Resp(404, {}, b"{}")
        elif method == "GET" and path == "/v1/state":
            value = {"services": {svc: {"settings": self.settings[svc], "patterns": self.patterns.get(svc)}
                                  for svc in self.services},
                     "shared": self.shared, "staged": self.staged, "mode": self.mode, "mode_source": self.mode_source}
        elif method == "GET" and path == "/v1/snapshots":
            value = self.snapshots
        elif method == "POST" and path == "/v1/snapshots":
            row = {"id": f"snap-{len(self.snapshots) + 1:04d}", "at": self.clock.now().strftime("%Y-%m-%dT%H:%M:%SZ")}
            self.created.append(json.loads(body))
            self.snapshots.append(row)
            value = row
        else:
            return Resp(404, {}, b"{}")
        return Resp(200, {}, json.dumps(value).encode())
