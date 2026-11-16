"""The CI tier's launcher: one disposable runner per job (z-sdlc process/factory.md, Enablement step 10, The CI tier).

Usage: python3 -I ci_launcher.py run <launcher.json> <slot>     one cycle; the slot's systemd unit starts the next
       python3 -I ci_launcher.py stop <launcher.json> <slot>    after a slot stops: its container and registration
       python3 -I ci_launcher.py resolve <launcher.json>        the App's installation and the runner group's IDs
       python3 -I ci_launcher.py check <launcher.json>          the tier's isolation check; on failure, its kill switch
       python3 -I ci_launcher.py fwcheck <launcher.json>        the firewall table alone (every minute)
       python3 -I ci_launcher.py trip <launcher.json>           the kill switch, for a check that failed or hung
       python3 -I ci_launcher.py fingerprint <table>            the firewall table's fingerprint (setup records it)
       python3 -I ci_launcher.py inputs <dir> [<arg>...]           the job image's build inputs' fingerprint
       python3 -I ci_launcher.py retire <launcher.json> <slot>  for setup: exit 10 when the slot may restart (its runner
                                                                is deregistered, or it has none), anything else when not
A slot beyond the settings' slot count (setup lowered CI_RUNNERS) starts no cycle: run exits 12, which its unit never
restarts after.

A cycle mints a just-in-time (JIT) runner config with the runner-registration App. The App's one permission, the
organization's self-hosted runners, reaches every runner group in the organization, so its key (root-only, read by
openssl alone) is the most sensitive thing on the host. The cycle starts a fresh container from the tier's image
as the runner user and watches it until its one job ends. GitHub, never the daemon, says whether the runner is
online and busy, and the container is killed when:
- its job has run CI_JOB_HOURS (the job's own timeout-minutes is the first limit; this is the backstop);
- its runner has idled CI_IDLE_HOURS (recycled);
- GitHub has removed its runner (the job is over), its runner went offline after being online, or its runner
  never came online;
- it is older than CI_IDLE_HOURS + CI_JOB_HOURS, whatever GitHub says;
- the runner home's free space falls below CI_MIN_FREE_GB (and no cycle starts below it).
While GitHub can't be read (an outage, a revoked key), the gone, offline, never-online, idle and job-hours limits all
wait on an answer: the lifetime cap and the disk floor are what bound a container then.
Then it removes the container and the runner's registration. The job runs inside the container, runner and all:
whatever a pull request's code does there, to the runner's own processes included, ends with the container.

Root-side rules (the job owns its container, so root trusts nothing that comes out of it):
- root reads one thing from the daemon, `docker wait`'s exit status, and only as an integer; containers are
  addressed by the names this script gives them, never by an ID the daemon returns. The check's probes answer
  with their exit status; their output is only logged, as printable ASCII;
- the installation token lives only in this process. The JIT config reaches the container through a 0600 file the
  runner user owns, created in a directory only root can write and deleted once `docker run` returns. Inside the
  container it stays readable to the job (run.sh's environment, the container's config) until the container is
  removed: it is single-use, and registers only the runner the job is already running on;
- every docker call runs as the runner user with a fixed environment and a timeout, never as root. setpriv execs
  docker (runuser would fork a parent that a timeout kills, orphaning docker).
A container escape is a compromise of the runner user, held by the outer boundary: its own user, the firewall,
the caps. Tested by tests/test_ci_launcher.py.
"""

import base64
import contextlib
import datetime
import fcntl
import hashlib
import http.client
import ipaddress
import json
import os
import pathlib
import re
import secrets
import signal
import socket
import stat
import struct
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ACCEPT = "application/vnd.github+json"
API_VERSION = "2022-11-28"
DROPPED_CAPS = ("NET_RAW", "MKNOD")
LOG_MAX = "20m"
# The check's inter-slot test: a listener at a fixed address on a network of its own (outside Docker's default
# address pools, so no slot network has it), which a container on another network must not reach.
CHECK_SUBNET, LISTENER_IP, LISTENER_PORT = "10.254.254.0/24", "10.254.254.10", 8080
REASONS = {
    "job-hours": "the job outran CI_JOB_HOURS",
    "idle": "the runner idled CI_IDLE_HOURS (recycled)",
    "lifetime": "the container outlived CI_IDLE_HOURS + CI_JOB_HOURS",
    "gone": "GitHub removed the runner (its job is over) but its container still runs",
    "offline": "the runner went offline after being online, but its container still runs",
    "never-online": "the runner never came online",
    "disk": "free space under the runner home fell below CI_MIN_FREE_GB",
}
# A recycle or an overrun, not a failure of the slot: the backoff counter stays as it is.
NEUTRAL = ("idle", "lifetime", "job-hours")
# The labels GitHub gives every self-hosted runner (self-hosted, its OS, its architecture): a tier's own label must be
# something else. The same set is in setup.sh, workflow_policy.py, runner_audit.py and process/factory.md (Enablement
# step 8), and tests/test_runner_labels.py holds them to it.
SELF_HOSTED_DEFAULTS = {"self-hosted", "linux", "windows", "macos", "x64", "x86", "arm", "arm64"}
# run's exit for a slot beyond the settings' slot count: its unit's RestartPreventExitStatus, so it isn't restarted.
RETIRED = 12
# A registration a stopped cycle asked for may still be made after the cycle stops looking (the request was in
# flight): its marker is kept, and looked for again, until it's this old.
PENDING_SETTLE = 300

# The isolation probe: every target closed; with expected caps (in a job's container), cpu.max, memory.max and
# pids.max set to them. Exit 1 on any of those, else exit 2 if the internet is out of reach (liveness, not
# isolation), else 0.
PROBE = r"""
import socket, sys
bad = 0
for h in sys.argv[1].split():
    for p in [int(x) for x in sys.argv[2].split()]:
        try:
            socket.create_connection((h, p), timeout=3).close()
            print(f"REACHABLE {h}:{p}"); bad += 1
        except OSError:
            pass
if sys.argv[3]:
    cpus, memory, pids = sys.argv[3].split()
    def read(name):
        try:
            return open("/sys/fs/cgroup/" + name).read().split()
        except OSError:
            return ["max"]
    quota = read("cpu.max")
    try:
        capped = quota[0] != "max" and abs(int(quota[0]) / int(quota[1]) - float(cpus)) < 0.01
    except (IndexError, ValueError):
        capped = False
    if not capped:
        print(f"cpu.max is {' '.join(quota)}, not {cpus} CPUs"); bad += 1
    for name, want in (("memory.max", memory), ("pids.max", pids)):
        if read(name)[0] != want:
            print(f"{name} is {read(name)[0]}, not {want}"); bad += 1
if bad:
    sys.exit(1)
try:
    socket.create_connection(("api.github.com", 443), timeout=10).close()
except OSError as e:
    print(f"no internet: {e}"); sys.exit(2)
"""
LISTEN = r"""
import socket, sys
s = socket.socket()
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(("0.0.0.0", int(sys.argv[1])))
s.listen(8)
while True:
    s.accept()[0].close()
"""
REACH = r"""
import socket, sys, time
for _ in range(15):
    try:
        socket.create_connection((sys.argv[1], int(sys.argv[2])), timeout=3).close()
        sys.exit(0)
    except OSError:
        time.sleep(1)
sys.exit(1)
"""


class Failed(Exception):
    pass


class Stopped(BaseException):
    """SIGTERM, the slot's unit stopping: unwinds through every finally, so the cycle cleans up after itself."""


def on_sigterm(signum, frame):
    signal.signal(signal.SIGTERM, signal.SIG_IGN)  # one unwind; the cleanup isn't interrupted again
    raise Stopped()


def load(path):
    with open(path) as f:
        return json.load(f)


def printable(text, limit=300):
    """Output from a container or GitHub, as it may appear in a log or the tripped marker."""
    return " ".join("".join(c if 32 <= ord(c) < 127 else " " for c in str(text)).split())[:limit]


def b64url(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def app_jwt(conf, now=None):
    """The App's JWT (RS256), signed by openssl with the root-only key."""
    now = int(now if now is not None else time.time())
    header = b64url(json.dumps({"alg": "RS256", "typ": "JWT"}).encode())
    claims = b64url(json.dumps({"iat": now - 60, "exp": now + 540, "iss": conf["client_id"]}).encode())
    signing_input = f"{header}.{claims}".encode()
    r = subprocess.run([conf["openssl"], "dgst", "-sha256", "-sign", conf["key"]], input=signing_input,
                       capture_output=True, timeout=30)
    if r.returncode or not r.stdout:
        raise Failed(f"openssl couldn't sign with {conf['key']}: {r.stderr.decode(errors='replace').strip()}")
    return f"{header}.{claims}.{b64url(r.stdout)}"


def api(conf, method, path, bearer, body=None):
    """GitHub's answer, as (HTTP status, a JSON object or None). Every endpoint used here answers with an object: a
    success whose body is anything else is Failed, like anything short of an answer, and an error's is its message."""
    request = urllib.request.Request(conf["api"] + path, method=method,
                                     data=None if body is None else json.dumps(body).encode(),
                                     headers={"Accept": ACCEPT, "X-GitHub-Api-Version": API_VERSION,
                                              "Authorization": f"Bearer {bearer}", "User-Agent": "z-sdlc-factory-ci"})
    try:
        with urllib.request.urlopen(request, timeout=30) as r:
            status, text = r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        status = e.code
        try:
            text = e.read().decode(errors="replace")
        except (OSError, http.client.HTTPException):
            text = ""
    except (OSError, ValueError, http.client.HTTPException) as e:
        raise Failed(f"{method} {path}: {type(e).__name__}: {printable(e, 200)}") from None
    try:
        data = json.loads(text) if text else None
    except ValueError:
        data = text
    if data is None or isinstance(data, dict):
        return status, data
    if status < 300:
        raise Failed(f"{method} {path}: HTTP {status}, but not a JSON object: {printable(text, 200)}")
    return status, {"message": printable(text, 200)}


def installation_token(conf):
    """An installation token narrowed to the one permission, and when it expires."""
    status, data = api(conf, "POST", f"/app/installations/{conf['installation_id']}/access_tokens", app_jwt(conf),
                       {"permissions": {"organization_self_hosted_runners": "write"}})
    if status != 201 or not isinstance(data, dict) or not data.get("token"):
        raise Failed(f"installation token: HTTP {status} {printable((data or {}).get('message', ''))}")
    try:
        expires = datetime.datetime.fromisoformat(str(data["expires_at"]).replace("Z", "+00:00")).timestamp()
    except (KeyError, ValueError):
        expires = time.time() + 3600
    return data["token"], expires


class Tokens:
    """A cycle's installation token, in memory only, minted again five minutes before it expires, and at once when
    GitHub refuses it. How long it lasts is counted on the monotonic clock, so a step of the wall clock can't keep a
    dead token in use."""

    def __init__(self, conf):
        self.conf, self.token, self.until = conf, None, 0.0
        self.org_seen = False  # the organization's runner list answered 200 (org_answers)

    def get(self):
        if self.token is None or time.monotonic() > self.until:
            self.token, expires = installation_token(self.conf)
            self.until = time.monotonic() + max(0.0, expires - time.time() - 300)
        return self.token

    def call(self, method, path, body=None):
        """api() with the token. A 401 drops it (revoked, or expired early) and tries once more with a new one: a
        cached dead token would otherwise fail every poll, and every limit that waits on one, for an hour. Not a 403,
        which is also GitHub's rate limit: minting more then only adds calls."""
        status, data = api(self.conf, method, path, self.get(), body)
        if status == 401:
            self.token = None
            status, data = api(self.conf, method, path, self.get(), body)
        return status, data


def jit_labels(conf):
    """The runner's labels. A just-in-time runner gets only the labels it's registered with, never the self-hosted
    one config.sh adds, and every job on the tier asks for [self-hosted, <label>]: so self-hosted comes first."""
    own = [label for label in conf["labels"] if label.lower() not in SELF_HOSTED_DEFAULTS]  # labels ignore case
    if not own:
        raise Failed("the tier has no runner label of its own: its runners would take any self-hosted job")
    return ["self-hosted"] + [label for label in conf["labels"] if label.lower() != "self-hosted"]


def jitconfig(conf, tokens, name):
    status, data = tokens.call("POST", f"/orgs/{conf['org']}/actions/runners/generate-jitconfig",
                               {"name": name, "runner_group_id": conf["group_id"], "labels": jit_labels(conf),
                                "work_folder": "_work"})
    if status != 201 or not isinstance(data, dict) or not data.get("encoded_jit_config"):
        raise Failed(f"JIT config: HTTP {status} {printable((data or {}).get('message', ''))}")
    runner = data.get("runner")
    if not isinstance(runner, dict) or not isinstance(runner.get("id"), int):
        raise Failed("JIT config: no runner ID in GitHub's answer")
    return runner["id"], data["encoded_jit_config"]


def runner_state(conf, runner_id, tokens):
    """GitHub's view of the runner, {"online", "busy"}; None once GitHub has removed it."""
    status, data = tokens.call("GET", f"/orgs/{conf['org']}/actions/runners/{runner_id}")
    if status == 404:
        return None
    if status != 200 or not isinstance(data, dict):
        raise Failed(f"runner {runner_id}: HTTP {status}")
    return {"online": data.get("status") == "online", "busy": data.get("busy") is True}


def ran_its_job(conf, runner_id, tokens):
    """After the container ends: GitHub removes a JIT runner once it has run its job, so one still registered
    never ran one (a bad config, a crash), and the next cycle backs off."""
    for attempt in range(int(conf.get("gone_checks", 4))):
        if attempt:
            time.sleep(float(conf.get("gone_delay", 5)))
        try:
            if runner_state(conf, runner_id, tokens) is None:
                return True
        except Failed as e:
            print(f"runner {runner_id}: {e}", file=sys.stderr)
    return False


def deregister(conf, runner_id, tokens):
    """Remove the runner's registration, and return GitHub's status. 404: already gone (org_answers says when that's
    so). GitHub refuses a busy runner."""
    status, data = tokens.call("DELETE", f"/orgs/{conf['org']}/actions/runners/{runner_id}")
    if status not in (204, 404):
        raise Failed(f"deregister runner {runner_id}: HTTP {status} {printable((data or {}).get('message', ''))}")
    return status


def org_answers(conf, tokens):
    """Before a 404 on a runner is taken to mean it's gone: GitHub also answers 404 for an organization the App can't
    see (a wrong org in the settings), where every runner would read as gone and its registration be forgotten. So
    the organization's runner list must answer 200, once per call of the launcher."""
    if not tokens.org_seen:
        status, _ = tokens.call("GET", f"/orgs/{conf['org']}/actions/runners?per_page=1")
        if status != 200:
            raise Failed(f"{conf['org']}'s runner list: HTTP {status}, so a 404 on one of its runners proves nothing")
        tokens.org_seen = True


def runners_named(conf, name, tokens):
    """The IDs GitHub has for runners of exactly this name."""
    status, data = tokens.call("GET", f"/orgs/{conf['org']}/actions/runners?name={urllib.parse.quote(name)}&per_page=100")
    if status != 200 or not isinstance(data, dict) or not isinstance(data.get("runners"), list):
        raise Failed(f"runners named {name}: HTTP {status}")
    tokens.org_seen = True
    return [r["id"] for r in data["runners"]
            if isinstance(r, dict) and r.get("name") == name and isinstance(r.get("id"), int)]


def runner_argv(conf, *command):
    """A command as the runner user, with a fixed environment. setpriv execs it: no parent left to orphan it."""
    uid = conf["uid"]
    return [conf["setpriv"], f"--reuid={uid}", f"--regid={conf['gid']}", "--clear-groups", "--inh-caps=-all", "--",
            conf["env"], "-i", "PATH=/usr/bin:/bin", f"HOME={conf['home']}", f"XDG_RUNTIME_DIR=/run/user/{uid}",
            f"DOCKER_HOST=unix:///run/user/{uid}/docker.sock", *command]


def docker(conf, *args, timeout=120):
    return subprocess.run(runner_argv(conf, conf["docker"], *args), capture_output=True, text=True, timeout=timeout)


def names(conf, slot):
    """The slot's container and its own network (concurrent jobs can't reach each other)."""
    name = f"{conf['container']}-{slot}"
    return name, name


def memory_bytes(text):
    """A size as memory.max holds it: the kernel rounds a cap down to whole pages (6001k isn't a whole number of
    pages), so the check compares against what it keeps, not what was asked."""
    page = os.sysconf("SC_PAGE_SIZE")
    return int(text[:-1]) * 1024 ** "kmg".index(text[-1].lower()) * 1024 // page * page


def job_flags(conf):
    """Every job container's caps and hardening. The check's probe runs with the same flags, so it proves them."""
    job = conf["job"]
    flags = ["--cpus", str(job["cpus"]), "--memory", job["memory"], "--memory-swap", job["memory"],
             "--pids-limit", str(job["pids"]), "--shm-size", job["shm"], "--security-opt", "no-new-privileges",
             "--log-driver", "local", "--log-opt", f"max-size={LOG_MAX}", "--log-opt", "max-file=1",
             # The local driver compresses rotated files by default, which takes at least two of them: with one, Docker
             # refuses to start the container ("compression cannot be enabled when max file count is 1").
             "--log-opt", "compress=false"]
    for cap in DROPPED_CAPS:
        flags += ["--cap-drop", cap]
    return flags


def state_dir(conf):
    """The launcher's directory, which the JIT config and the runner IDs pass through: only root may write it."""
    path = pathlib.Path(conf["state_dir"])
    st = os.lstat(path)
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != conf.get("state_owner", 0) or st.st_mode & 0o022:
        raise Failed(f"{path} must be a directory only root can write")
    return path


def record_files(conf, slot):
    """Every record of a registration the slot may hold: its current one, and any an earlier cycle couldn't remove
    (slot-N.leftover-<id>)."""
    state = state_dir(conf)
    return [state / f"slot-{slot}.runner", *sorted(state.glob(f"slot-{slot}.leftover-*"))]


def retired_slots(conf):
    """Slots beyond the settings' slot count whose registrations are still on record (a current record, a leftover, a
    pending marker): no cycle of theirs runs again to remove them."""
    if "slots" not in conf:
        return []
    found = set()
    for path in state_dir(conf).glob("slot-*"):
        m = re.fullmatch(r"slot-(\d+)\.(runner|leftover-\d+|pending-[0-9a-f]+)", path.name)
        if m and int(m.group(1)) > int(conf["slots"]):
            found.add(int(m.group(1)))
    return sorted(found)


def pending_files(conf, slot):
    """Markers of registrations the slot's cycles asked GitHub for and may not have heard back about
    (slot-N.pending-<suffix>, each holding the runner's name): a cycle stopped inside generate-jitconfig."""
    return sorted(state_dir(conf).glob(f"slot-{slot}.pending-*"))


def low_disk(conf):
    st = os.statvfs(conf["home"])
    return st.f_bavail * st.f_frsize < float(conf.get("min_free_gb", 20)) * 2 ** 30


def write_env_file(conf, path, jit):
    """The JIT config for `docker run --env-file`: created fresh (no link followed), 0600, owned by the runner user."""
    with contextlib.suppress(FileNotFoundError):
        os.unlink(path)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        os.fchown(fd, conf["uid"], conf["gid"])
        os.write(fd, f"ACTIONS_RUNNER_INPUT_JITCONFIG={jit}\nRUNNER_ALLOW_RUNASROOT=1\n".encode())
    finally:
        os.close(fd)


def record_runner(path, value):
    """A record in the state, written whole: the cycle's runner ID, kept before its container starts so a killed
    cycle's registration is removed later, or the name of a runner a cycle is asking GitHub for."""
    # A temporary name of this process's own, hidden from the records' globs: slot 1's sweep and a retired slot's stop
    # can write the same record at once.
    new = path.with_name(f".{path.name}.{os.getpid()}.new")
    new.write_text(str(value))
    os.replace(new, path)


def resolve_pending(conf, slot, tokens):
    """A registration a stopped cycle asked for and never heard back about (pending_files): once GitHub has a runner
    of its name, it becomes a leftover record (slot-N.leftover-<id>); with none, its marker goes once it's
    PENDING_SETTLE old, since the request may still have been in flight. Unknown (GitHub out of reach): kept."""
    state = state_dir(conf)
    settle = float(conf.get("pending_settle_seconds", PENDING_SETTLE))
    for path in pending_files(conf, slot):
        try:
            name = path.read_text().strip()
            age = time.time() - path.stat().st_mtime
        except FileNotFoundError:
            continue
        try:
            ids = runners_named(conf, name, tokens) if name else []
        except Failed as e:
            print(f"slot {slot}: {e}; the marker for {printable(name)} is kept for a later cycle", file=sys.stderr)
            continue
        for runner_id in ids:
            record_runner(state / f"slot-{slot}.leftover-{runner_id}", runner_id)
        if ids or age > settle:
            path.unlink(missing_ok=True)


def deregister_leftover(conf, slot, tokens, spare_busy=False):
    """Registrations a stopped or killed cycle left behind (record_files, and resolve_pending's). One GitHub won't
    remove now (it can still call a dead runner busy for a while) is kept as slot-N.leftover-<id> for a later cycle,
    never a reason to stop this one; one GitHub no longer has is dropped. spare_busy, for another slot's records (slot
    1's sweep of a retired slot, whose last cycle may still be running its job): GitHub is asked first, as retire asks,
    and a registration it calls busy is left as it is, record and all, as is one whose removal fails (it may have taken
    a job since): a record moved from under a live cycle would let retire answer idle."""
    state = state_dir(conf)
    resolve_pending(conf, slot, tokens)
    for path in record_files(conf, slot):
        try:
            runner_id = int(path.read_text())
        except FileNotFoundError:
            continue
        except ValueError:
            path.unlink()
            continue
        if spare_busy:
            try:
                runner = runner_state(conf, runner_id, tokens)
            except Failed as e:
                print(f"slot {slot}: {e}; kept for a later cycle", file=sys.stderr)
                continue
            if runner is not None and runner["busy"]:
                continue
        try:
            if deregister(conf, runner_id, tokens) == 404:
                org_answers(conf, tokens)
            path.unlink(missing_ok=True)
            continue
        except Failed as e:
            print(f"slot {slot}: {e}; kept for a later cycle", file=sys.stderr)
        with contextlib.suppress(Failed):
            if runner_state(conf, runner_id, tokens) is None:  # gone after all
                org_answers(conf, tokens)
                path.unlink(missing_ok=True)
                continue
        leftover = state / f"slot-{slot}.leftover-{runner_id}"
        if path != leftover and not spare_busy:
            record_runner(leftover, runner_id)
            path.unlink(missing_ok=True)


def run(conf, slot, conf_path=None):
    """One job's cycle. Returns 0 when the runner ran its job or was recycled, 1 otherwise (the next cycle backs
    off), and RETIRED for a slot beyond the settings' slot count, which then stays stopped. conf_path: the settings'
    file, read again for slot 1's sweep (setup may have changed the slot count since this cycle started)."""
    if "slots" in conf and slot > int(conf["slots"]):
        print(f"slot {slot}: beyond CI_RUNNERS ({conf['slots']}), so it starts no cycle", file=sys.stderr)
        return RETIRED
    state = state_dir(conf)
    fails_file = state / f"slot-{slot}.fails"
    runner_file = state / f"slot-{slot}.runner"
    try:
        fails = int(fails_file.read_text())
    except (OSError, ValueError):
        fails = 0
    if fails:
        # A failing cycle (the API, the image, the group) must not hammer generate-jitconfig: GitHub answers 422.
        time.sleep(min(600, 10 * 2 ** min(fails, 6)))
    tokens = Tokens(conf)
    name, network = names(conf, slot)
    outcome, runner_id = "failed", None
    with contextlib.suppress(FileNotFoundError):
        os.unlink(state / f"slot-{slot}.env")  # a JIT config a crashed cycle left on disk
    try:
        deregister_leftover(conf, slot, tokens)
        if slot == 1:
            # A slot beyond the count never runs again, so what its last cycle and its stop couldn't remove (a
            # registration GitHub made after the stop looked, one it wouldn't remove yet) is slot 1's to remove. Only
            # slot 1, so no two cycles do it at once; never a reason to fail this cycle. A registration GitHub calls
            # busy is spared: the retired slot's last cycle may still be running its job. The count is read again
            # here, since this cycle may have waited out its backoff while setup changed it.
            try:
                now = load(conf_path) if conf_path else conf
                retired = retired_slots({**conf, "slots": now["slots"]}) if "slots" in now else []
            except (OSError, ValueError, TypeError) as e:
                print(f"slot {slot}: the settings' slot count: {printable(e)}", file=sys.stderr)
                retired = []
            for other in retired:
                try:
                    deregister_leftover(conf, other, tokens, spare_busy=True)
                except (Failed, OSError) as e:
                    print(f"slot {slot}: slot {other}'s registrations: {printable(e)}", file=sys.stderr)
        docker(conf, "rm", "-f", "-v", name)  # a container a crash left behind
        if docker(conf, "network", "inspect", network).returncode:
            docker(conf, "network", "create", "--label", "factory-ci", network)
        if low_disk(conf):
            raise Failed(f"less than CI_MIN_FREE_GB free under {conf['home']}: no job starts")
        suffix = secrets.token_hex(3)
        # The name is recorded before GitHub is asked: a SIGTERM inside the call leaves a registration whose ID this
        # cycle never hears, which a later cycle, the slot's stop or retire finds by its name (resolve_pending).
        pending = state / f"slot-{slot}.pending-{suffix}"
        record_runner(pending, f"{conf['name_prefix']}-{slot}-{suffix}")
        runner_id, jit = jitconfig(conf, tokens, f"{conf['name_prefix']}-{slot}-{suffix}")
        record_runner(runner_file, runner_id)
        pending.unlink(missing_ok=True)  # slot 1's sweep may have resolved it first, for a slot retired meanwhile
        env_file = state / f"slot-{slot}.env"
        write_env_file(conf, env_file, jit)
        try:
            started = docker(conf, "run", "-d", "--name", name, "--network", network, "--label", "factory-ci",
                             *job_flags(conf), "--env-file", str(env_file), conf["image"])
        finally:
            with contextlib.suppress(FileNotFoundError):
                os.unlink(env_file)
        if started.returncode:
            raise Failed(f"docker run: {printable(started.stderr)}")
        reason, status = watch(conf, slot, name, runner_id, tokens)
        print(f"slot {slot}: " + (f"the runner exited with {status}" if reason is None else REASONS[reason]))
        if ran_its_job(conf, runner_id, tokens):
            outcome = "ran"
        elif reason in NEUTRAL:
            outcome = "recycled"
    except Stopped:
        outcome = "stopped"
        raise
    except (Failed, ValueError, KeyError, OSError, subprocess.TimeoutExpired) as e:
        print(f"slot {slot}: {printable(e)}", file=sys.stderr)
    finally:
        cleanup(conf, slot, name, runner_file, runner_id, tokens, removed=outcome == "ran")
        with contextlib.suppress(OSError):
            fails_file.write_text(str(0 if outcome == "ran" else fails if outcome in ("recycled", "stopped")
                                      else fails + 1))
    return 1 if outcome == "failed" else 0


def watch(conf, slot, name, runner_id, tokens):
    """Wait for the container's one job, killing it on any limit in this file's docstring. Returns (the limit, None)
    for a killed container, or (None, its exit status)."""
    tick = float(conf.get("tick_seconds", 30))
    poll = float(conf.get("poll_seconds", 120))
    job_limit = float(conf["job"]["hours"]) * 3600
    idle_limit = float(conf.get("idle_hours", 24)) * 3600
    grace = float(conf.get("start_grace_seconds", 600))
    started = last_poll = time.monotonic()
    seen_online, busy_since, offline_polls, reason = False, None, 0, None
    # One `docker wait` for the cycle, never killed by a timeout: it returns when the container ends, killed or not.
    waiter = subprocess.Popen(runner_argv(conf, conf["docker"], "wait", name), stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, text=True)
    try:
        while reason is None:
            try:
                out, _ = waiter.communicate(timeout=tick)
                return None, int(out.strip())  # the only thing root reads from the daemon
            except subprocess.TimeoutExpired:
                pass
            now = time.monotonic()
            if low_disk(conf):
                reason = "disk"
            elif now - started > idle_limit + job_limit:
                reason = "lifetime"
            elif busy_since is not None and now - busy_since > job_limit:
                reason = "job-hours"
            elif now - last_poll >= poll:
                last_poll = now
                try:
                    runner = runner_state(conf, runner_id, tokens)
                except Failed as e:
                    print(f"slot {slot}: {e}", file=sys.stderr)  # unknown: the lifetime cap still holds
                    continue
                if runner is None:
                    reason = "gone"
                    continue
                if runner["online"] or runner["busy"]:
                    seen_online, offline_polls = True, 0
                elif seen_online:
                    offline_polls += 1  # one offline poll can be the runner updating itself
                if runner["busy"] and busy_since is None:
                    busy_since = now
                if offline_polls >= 2:
                    reason = "offline"
                elif not seen_online and now - started > grace:
                    reason = "never-online"
                elif busy_since is None and now - started > idle_limit:
                    try:
                        deregister(conf, runner_id, tokens)  # first, so GitHub assigns it nothing meanwhile
                        reason = "idle"
                    except Failed as e:
                        # GitHub refuses to remove a busy runner, but a failure to reach it says nothing: ask again,
                        # and count it busy only on GitHub's word. Otherwise the next poll tries the removal again.
                        print(f"slot {slot}: {e}", file=sys.stderr)
                        with contextlib.suppress(Failed):
                            runner = runner_state(conf, runner_id, tokens)
                            if runner is None:
                                reason = "gone"
                            elif runner["busy"]:
                                busy_since = now
        print(f"slot {slot}: {REASONS[reason]}; killing its container", file=sys.stderr)
        docker(conf, "kill", name)
        with contextlib.suppress(subprocess.TimeoutExpired):
            waiter.communicate(timeout=60)
        return reason, None
    finally:
        if waiter.poll() is None:
            waiter.kill()
            waiter.wait()


def cleanup(conf, slot, name, runner_file, runner_id, tokens, removed):
    """The container, then the registration (unless GitHub has removed it): each on its own, so one failing doesn't
    skip the other. A registration left over stays in slot-N.runner for the next cycle or the slot's stop."""
    try:
        docker(conf, "rm", "-f", "-v", name)
    except (OSError, subprocess.TimeoutExpired) as e:
        print(f"slot {slot}: docker rm: {e}", file=sys.stderr)
    if runner_id is None:
        return
    try:
        if not removed:
            deregister(conf, runner_id, tokens)
        runner_file.unlink(missing_ok=True)
    except (Failed, OSError) as e:
        print(f"slot {slot}: {e}", file=sys.stderr)


IDLE = 10  # retire's one answer that lets setup restart a slot: every other exit, an error's included, means don't


def retire(conf, slot):
    """For setup, which restarts a slot whose runner isn't running a job, so it takes setup's launcher and settings now
    and not at its next cycle (an idle runner's can be CI_IDLE_HOURS away). Returns (idle, why not). Each registration
    the slot holds (record_files, and any GitHub has under a pending marker's name) must be gone, or idle and then
    deregistered: GitHub's word that it's busy, its refusal to remove it (422), or a new cycle's record turning up
    meanwhile all mean not idle. Deregistering before the restart means no job can be assigned between the look and the
    restart. A 404 counts as gone only once the organization's runner list has answered (org_answers). The markers stay
    as they are: the cycle that wrote one may still be running, and the restart's stop resolves them."""
    state = state_dir(conf)  # missing, or not root's alone: an error, so not idle
    tokens = Tokens(conf)
    current = state / f"slot-{slot}.runner"
    before = current.read_text() if current.exists() else None
    ids = []
    for path in record_files(conf, slot):
        try:
            ids.append(int(path.read_text()))
        except FileNotFoundError:
            continue
    for path in pending_files(conf, slot):
        with contextlib.suppress(FileNotFoundError):
            ids += runners_named(conf, path.read_text().strip(), tokens)
    for runner_id in ids:
        runner = runner_state(conf, runner_id, tokens)
        if runner is None:
            org_answers(conf, tokens)
            continue
        if runner["busy"]:
            return False, f"runner {runner_id} is running a job"
        status, _ = tokens.call("DELETE", f"/orgs/{conf['org']}/actions/runners/{runner_id}")
        if status == 422:
            return False, f"GitHub won't remove runner {runner_id}: it took a job"
        if status == 404:
            org_answers(conf, tokens)
        elif status != 204:
            return False, f"removing runner {runner_id}: HTTP {status}"
    after = current.read_text() if current.exists() else None
    if after not in (None, before):
        return False, "a new cycle registered a runner meanwhile"
    return True, ""


def stop(conf, slot):
    """After a slot stops (its unit's ExecStopPost): its container and any registration its cycle left."""
    state = state_dir(conf)
    docker(conf, "rm", "-f", "-v", names(conf, slot)[0])
    with contextlib.suppress(FileNotFoundError):
        os.unlink(state / f"slot-{slot}.env")
    deregister_leftover(conf, slot, Tokens(conf))
    return 0


def find_group(conf, token):
    """The runner group by its name, which must be one group's alone: an organization can share a name with a group
    its enterprise shares."""
    page, found = 1, []
    while True:
        status, groups = api(conf, "GET", f"/orgs/{conf['org']}/actions/runner-groups?per_page=100&page={page}", token)
        if status != 200 or not isinstance(groups, dict):
            raise Failed(f"runner groups: HTTP {status}")
        items = groups.get("runner_groups")
        if not isinstance(items, list):
            raise Failed("runner groups: no list in GitHub's answer")
        found += [g for g in items if isinstance(g, dict) and g.get("name") == conf["group"]]
        if len(items) < 100:
            break
        page += 1
    if not found:
        raise Failed(f"no runner group {conf['group']}: bootstrap.py --apply creates it once a workflow uses the label")
    if len(found) > 1:
        raise Failed(f"{len(found)} runner groups are named {conf['group']} (IDs "
                     f"{', '.join(str(g.get('id')) for g in found)}): give the tier's a name of its own")
    return found[0]


def group_problem(group, name):
    if group.get("visibility") != "selected" or group.get("allows_public_repositories"):
        return f"runner group {name} is open beyond its selected private repositories"
    return None


def resolve(conf):
    """The App's installation on the organization and the runner group's ID (setup writes them into the conf)."""
    status, data = api(conf, "GET", f"/orgs/{conf['org']}/installation", app_jwt(conf))
    if status != 200 or not isinstance(data, dict) or "id" not in data:
        raise Failed(f"the runner-registration App isn't installed on {conf['org']}: HTTP {status}")
    if (data.get("permissions") or {}).get("organization_self_hosted_runners") != "write":
        raise Failed("the runner-registration App's installation lacks organization_self_hosted_runners: write")
    conf = {**conf, "installation_id": int(data["id"])}
    group = find_group(conf, installation_token(conf)[0])
    problem = group_problem(group, conf["group"])
    if problem:
        raise Failed(problem)
    return {"installation_id": conf["installation_id"], "group_id": int(group["id"])}


def fingerprint(listing):
    """The table as `nft -j` lists it, without what changes on its own (handles, counters, nft's own version): its
    chains, rules and sets, set elements included. Flushing a chain, or a set like the blocked addresses, leaves the
    table in place and changes this."""
    def clean(node):
        if isinstance(node, dict):
            return {k: (None if k == "counter" else clean(v)) for k, v in node.items() if k != "handle"}
        if isinstance(node, list):
            return [clean(x) for x in node]
        return node
    items = [clean(item) for item in json.loads(listing)["nftables"] if "metainfo" not in item]
    return hashlib.sha256(json.dumps(items, sort_keys=True).encode()).hexdigest()


def build_inputs(root, *args):
    """The fingerprint of an image's build inputs: setup's copy of the context and Dockerfiles (each entry's path, mode,
    and contents or link target, wherever the copy is) and the build's arguments. Setup keeps the job image while this
    is unchanged: a rebuild of the same inputs still makes a new image (package steps resolve again)."""
    h = hashlib.sha256()
    for arg in args:
        h.update(arg.encode() + b"\0")
    for dirpath, dirnames, filenames in os.walk(root):  # links to directories are listed, never followed
        dirnames.sort()
        for name in sorted(dirnames + filenames):
            path = os.path.join(dirpath, name)
            st = os.lstat(path)
            h.update(f"{os.path.relpath(path, root)}\0{st.st_mode:o}\0".encode())
            if stat.S_ISLNK(st.st_mode):
                h.update(os.readlink(path).encode())
            elif stat.S_ISREG(st.st_mode):
                with open(path, "rb") as f:
                    for chunk in iter(lambda: f.read(1 << 20), b""):
                        h.update(chunk)
            h.update(b"\0")
    return h.hexdigest()


def firewall_problem(conf):
    """None when the tier's table is loaded as setup loaded it, else what's wrong. The table's presence alone isn't
    enough: setup records its fingerprint."""
    r = subprocess.run([conf["nft"], "-j", "list", "table", "inet", conf["firewall_table"]], capture_output=True,
                       text=True, timeout=30)
    if r.returncode:
        return f"firewall table {conf['firewall_table']} isn't loaded"
    want = conf.get("firewall_fingerprint")
    if want is None:  # settings from before the fingerprint
        return None
    try:
        have = fingerprint(r.stdout)
    except (ValueError, KeyError, TypeError, AttributeError):
        return f"firewall table {conf['firewall_table']}: nft's listing isn't readable"
    if have != want:
        # An nftables upgrade can list the same table differently, and trips the tier the same way (Enablement step 10).
        return (f"firewall table {conf['firewall_table']} isn't what setup loaded (a chain or set flushed or changed; "
                "after an nftables upgrade, its listing may be what changed: check the table, then run setup again)")
    return None


def gateway(conf):
    """The default IPv4 gateway, if it's a private address: a LAN target that isn't this host's (whose addresses
    all meet the firewall's loopback rule), so the blocked set itself is tested."""
    try:
        for line in pathlib.Path(conf.get("route_file", "/proc/net/route")).read_text().splitlines()[1:]:
            fields = line.split()
            if len(fields) > 2 and fields[1] == "00000000":
                ip = socket.inet_ntoa(struct.pack("<L", int(fields[2], 16)))
                return ip if ipaddress.ip_address(ip).is_private else None
    except (OSError, ValueError):
        pass
    return None


def check(conf):
    """The outer boundary, every few hours and before any slot starts. Anything that stops the check finishing
    counts as a failure. On failure, trip(): a tripped marker the slot units won't start past, and the tier stopped
    and disabled down to the runner user's session, so a reboot brings none of it back. Only setup does."""
    problems, notes = [], []
    try:
        with open(state_dir(conf) / "check.lock", "w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            inspect(conf, problems, notes)
    except Exception as e:  # noqa: BLE001 - a check that can't finish has failed
        problems.append(f"the check couldn't finish: {type(e).__name__}: {printable(e)}")
    for note in notes:
        print(f"CI tier check: {note}", file=sys.stderr)
    if problems:
        trip(conf, problems)
        return 1
    print("CI tier check: ok")
    return 0


def inspect(conf, problems, notes):
    problem = firewall_problem(conf)
    if problem:
        problems.append(problem)
    cgroup = pathlib.Path(conf["cgroup"])
    for name in ("memory.max", "cpu.max"):
        if (cgroup / name).read_text().split()[0] == "max":
            problems.append(f"no {name} on {cgroup}")
    controllers = (cgroup / f"user@{conf['uid']}.service" / "cgroup.controllers").read_text().split()
    for c in ("cpu", "memory", "pids"):
        if c not in controllers:
            problems.append(f"the {c} controller isn't delegated to the runner user")
    if low_disk(conf):
        # Liveness, not isolation: no cycle starts below the floor and a running job is killed, so it needs no trip.
        notes.append(f"less than CI_MIN_FREE_GB free under {conf['home']}: no job starts until there's room")
    # The group as setup found it. GitHub out of reach is liveness, not isolation: noted, not tripped.
    try:
        status, group = api(conf, "GET", f"/orgs/{conf['org']}/actions/runner-groups/{conf['group_id']}",
                            Tokens(conf).get())
        if status == 200 and isinstance(group, dict):
            problem = group_problem(group, conf["group"])
            problems += [problem] if problem else []
        elif status == 404:
            problems.append(f"runner group {conf['group']} is gone")
        else:
            notes.append(f"runner group {conf['group']}: HTTP {status}")
    except Failed as e:
        notes.append(f"couldn't read runner group {conf['group']}: {e}")

    def judge(what, result):
        if result.returncode == 2:
            notes.append(f"{what}: {printable(result.stdout)}")
        elif result.returncode:
            problems.append(f"{what}: {printable(result.stdout) or f'exit {result.returncode}'}")

    targets = conf["probe"]["targets"].split()
    gw = gateway(conf)
    targets += [gw] if gw and gw not in targets else []
    ports = conf["probe"]["ports"].split()
    ports += [] if str(LISTENER_PORT) in ports else [str(LISTENER_PORT)]
    # On the host, as the runner user, with no Docker in the way: the firewall itself, IPv6 included.
    host_probe = runner_argv(conf, conf["python"], "-I", "-c", PROBE, " ".join(targets), " ".join(ports), "")
    judge("the host-side probe", subprocess.run(host_probe, capture_output=True, text=True, timeout=300))
    # At boot the gate can run before the runner user's daemon is up: it gets ten minutes (the gate's own timeout is
    # 30), and a daemon that hasn't answered by then is a failure.
    deadline = time.monotonic() + float(conf.get("docker_wait_seconds", 600))
    while docker(conf, "info", timeout=15).returncode:
        if time.monotonic() > deadline:
            problems.append("the runner user's Docker daemon doesn't answer")
            return
        time.sleep(2)
    own, other = f"{conf['container']}-check-a", f"{conf['container']}-check"
    listener = f"{conf['container']}-check-listen"
    docker(conf, "rm", "-f", "-v", listener)
    docker(conf, "network", "rm", own)
    if docker(conf, "network", "create", "--label", "factory-ci", "--subnet", CHECK_SUBNET, own).returncode:
        problems.append(f"couldn't create the check's network {own} ({CHECK_SUBNET})")
        return
    if docker(conf, "network", "inspect", other).returncode:
        docker(conf, "network", "create", "--label", "factory-ci", other)
    job = conf["job"]
    caps = f"{job['cpus']} {memory_bytes(job['memory'])} {job['pids']}"
    v4 = [t for t in targets if ipaddress.ip_address(t).version == 4]
    try:
        if docker(conf, "run", "-d", "--name", listener, "--network", own, "--ip", LISTENER_IP, *job_flags(conf),
                  "--entrypoint", "python3", conf["image"], "-c", LISTEN, str(LISTENER_PORT)).returncode:
            problems.append("the check's listener container didn't start")
            return
        if docker(conf, "run", "--rm", "--network", own, *job_flags(conf), "--entrypoint", "python3", conf["image"],
                  "-c", REACH, LISTENER_IP, str(LISTENER_PORT), timeout=120).returncode:
            problems.append("the check's listener can't be reached on its own network, so the slots' isolation "
                            "from each other is untested")
            return
        # A job's container: the job's flags, a network like a slot's, and another network's listener closed to it.
        judge("the probe container", docker(conf, "run", "--rm", "--network", other, *job_flags(conf),
                                            "--entrypoint", "python3", conf["image"], "-c", PROBE,
                                            " ".join(v4 + [LISTENER_IP]), " ".join(ports), caps, timeout=300))
    finally:
        docker(conf, "rm", "-f", "-v", listener)


def fwcheck(conf):
    """Every minute: the firewall table, which anything that flushes the ruleset would drop. nftables.service's own
    restart flushes it for a moment, until the reapply unit loads it again, so a problem is looked at again a few
    seconds on before it trips the tier."""
    try:
        problem = firewall_problem(conf)
        for _ in range(int(conf.get("fw_retries", 3))):
            if problem is None:
                return 0
            time.sleep(float(conf.get("fw_retry_seconds", 2)))
            problem = firewall_problem(conf)
        if problem is None:
            return 0
    except Exception as e:  # noqa: BLE001 - a check that can't finish has failed
        problem = f"the firewall check couldn't finish: {type(e).__name__}: {printable(e)}"
    trip(conf, [problem])
    return 1


def trip(conf, problems, keep=False):
    """keep: a marker a check already wrote says more than this caller can (the trip unit, after a failure)."""
    tripped = pathlib.Path(conf["tripped"])
    try:
        if not (keep and tripped.exists()):
            tripped.write_text("".join(f"{printable(p, 1000)}\n" for p in problems))
    except OSError as e:
        print(f"couldn't write {tripped}: {e}", file=sys.stderr)
    print("CI tier check FAILED:\n  " + "\n  ".join(printable(p, 1000) for p in problems), file=sys.stderr)
    unit, systemctl = conf["unit"], conf["systemctl"]
    # The slots first (their stop removes their containers and registrations). Then everything that would start the
    # runner user's manager again is disabled: a unit's condition doesn't stop its Requires= from starting, so at boot
    # an enabled slot or gate would bring the manager back, and linger would too. The gate is only disabled, never
    # stopped here: a trip can be running inside it (its own check failed), and stopping the manager stops it anyway.
    # Then that manager: its daemon and every container in it, a job included. Setup enables all of it again.
    wants = pathlib.Path(conf.get("wants_dir", "/etc/systemd/system/multi-user.target.wants"))
    slots = sorted(p.name for p in wants.glob(f"{unit}-slot@*.service"))
    steps = [[systemctl, "stop", f"{unit}-slot@*.service"]]
    steps += [[systemctl, "disable", *slots]] if slots else []
    steps += [[systemctl, "disable", f"{unit}-gate.service", f"{unit}-check.timer", f"{unit}-fw.timer"],
              [systemctl, "stop", f"{unit}-check.timer", f"{unit}-fw.timer"],
              [conf.get("loginctl", "/usr/bin/loginctl"), "disable-linger", conf["user"]],
              [systemctl, "stop", f"user@{conf['uid']}.service"]]
    for argv in steps:
        with contextlib.suppress(OSError, subprocess.TimeoutExpired):
            subprocess.run(argv, capture_output=True, timeout=300)
    print(f"{unit}: stopped and disabled, and held by {tripped} until someone fixes the cause and runs setup",
          file=sys.stderr)


def main(argv):
    commands = ("run", "stop", "resolve", "check", "fwcheck", "trip", "fingerprint", "retire", "inputs")
    if len(argv) < 3 or argv[1] not in commands or (argv[1] in ("run", "stop", "retire") and len(argv) < 4):
        print(__doc__.split("\n\n")[1], file=sys.stderr)
        return 2
    if argv[1] == "retire":
        try:
            idle, why = retire(load(argv[2]), int(argv[3]))
        except Exception as e:  # noqa: BLE001 - unknown: the slot stays as it is
            idle, why = False, f"{type(e).__name__}: {e}"
        if not idle:
            print(f"ci_launcher retire: slot {printable(argv[3])} not idle: {printable(why)}", file=sys.stderr)
        return IDLE if idle else 0
    if argv[1] == "inputs":
        print(build_inputs(argv[2], *argv[3:]))
        return 0
    if argv[1] == "fingerprint":
        r = subprocess.run(["nft", "-j", "list", "table", "inet", argv[2]], capture_output=True, text=True, timeout=30)
        if r.returncode:
            print(f"ci_launcher fingerprint: no table inet {printable(argv[2])}", file=sys.stderr)
            return 1
        print(fingerprint(r.stdout))
        return 0
    if argv[1] == "run":
        signal.signal(signal.SIGTERM, on_sigterm)
    try:
        conf = load(argv[2])
        if argv[1] == "run":
            return run(conf, int(argv[3]), conf_path=argv[2])
        if argv[1] == "stop":
            return stop(conf, int(argv[3]))
        if argv[1] == "resolve":
            print(json.dumps(resolve(conf)))
            return 0
        if argv[1] == "trip":
            unit = conf["unit"]
            trip(conf, [f"an isolation check failed or didn't finish: journalctl -u {unit}-gate -u {unit}-check "
                        f"-u {unit}-fw"], keep=True)
            return 0
        return check(conf) if argv[1] == "check" else fwcheck(conf)
    except Stopped:
        return 0
    except (Failed, OSError, ValueError, KeyError, IndexError, subprocess.TimeoutExpired) as e:
        print(f"ci_launcher {argv[1]}: {printable(e)}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
