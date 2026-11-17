"""factory-op: a checks-only production broker (z-sdlc process/factory.md D4, the release branch model; the
factory-broker bundle, process/factory-broker.md).

Production deploys itself: the host deploys the release branch when CD merges a pull request into it. This broker
deploys nothing and rolls nothing back. It is a root service, installed by `sudo bash host/setup-production.sh` into
/usr/local/lib/factory-prod[-<instance>] (with gates.py, ed25519.py, ops.json, config.json, the project's factory_op_host.py
and any ops/*.sh), that checks provenance and the recorded state, runs typed read operations and the host's own operations
in plan gates CD approves, and signs every result.

Root runs no project code. Root's commands read config.json's generic keys, ops.json (the catalog and its `broker`
block) and the ledger, and never import the host module: every check root makes about the host is generic code over
a step's typed outputs, or data the block declares. Only `op <name>`, run as the operator user inside a sandboxed
systemd unit with no IP network, loads factory_op_host.py, by its path, after refusing to run as root. The ops digest
(gates.ops_digest) covers this file, the host module (gates.BROKER_MODULES), the config.json installed beside it (the copy
root reads), ops.json and ops/*.sh.

The instance comes from the install path: this file's directory must be factory-prod or factory-prod-<instance>, and
every user, unit, path and table name derives from it (tier_names). Other tiers on the host are found by looking.

Who runs what:
  root       serve, check, pubkey, fetch, baseline, health, diagnose, drift-check, resolve
  operator   `op <name>` (sandboxed; refuses root)
  egress     `egress` (the only way out of the sandbox: the block's egress hosts, port 443)

Usage (root): factory-op[-<instance>] serve                    (systemd, one connection on stdin/stdout)
              factory-op[-<instance>] check | pubkey | fetch | health | drift-check
              factory-op[-<instance>] diagnose NAME            (host-check, or a host diagnostic)
              factory-op[-<instance>] resolve RUN_ID failed NOTE
              factory-op[-<instance>] resolve --torn-line NOTE  (sets a ledger line cut off mid-write aside)
              factory-op[-<instance>] baseline [--advance-release-head] NOTE
"""

import ast
import base64
import collections
import contextlib
import datetime
import fcntl
import functools
import getpass
import glob
import grp
import hashlib
import http.client
import importlib.util
import ipaddress
import json
import os
import pathlib
import pwd
import re
import select
import shutil
import signal
import socket
import ssl
import stat
import struct
import subprocess
import sys
import time
import types
import urllib.error
import urllib.parse
import urllib.request

# ---------------------------------------------------------------- the tier, from the install path (D4 rule 16)

LIB = pathlib.Path(__file__).resolve().parent
try:  # the bytes this process runs, read as it starts: load() requires them to be the installed package's
    SELF_BYTES = pathlib.Path(__file__).read_bytes()
except OSError:
    SELF_BYTES = None
HOST_MODULE = "factory_op_host.py"  # gates.BROKER_MODULES hashes it by this name
# A tier is factory-prod (the first on a host) or factory-prod-<instance>. The instance is short, so the longest
# derived user name (factory-prod-<instance>-egress) fits Linux's 32 characters, and it may not be a word the first
# tier's own names end in: factory-prod-op would be the first tier's operator, factory-prod-clone its clone directory.
TIER_RE = re.compile(r"factory-prod(?:-([a-z0-9]{1,12}))?")
RESERVED_INSTANCES = frozenset({"op", "egress", "clone", "firewall", "runner", "step", "drift"})


def tier_of(lib_dir):
    """The tier this library directory is, or None: its name must be factory-prod or factory-prod-<instance>."""
    name = pathlib.Path(lib_dir).name
    m = TIER_RE.fullmatch(name)
    if not m or (m.group(1) or "") in RESERVED_INSTANCES:
        return None
    return name


def tier_names(tier):
    """Every name a tier's broker, setup and units use, derived from the tier alone. Setup derives the same."""
    m = TIER_RE.fullmatch(tier or "")
    if not m or (m.group(1) or "") in RESERVED_INSTANCES:
        raise ValueError(f"not a tier name: {tier!r}")
    instance = m.group(1) or ""
    suffix = f"-{instance}" if instance else ""
    etc, run, lib = f"/etc/{tier}", f"/run/{tier}", f"/usr/local/lib/{tier}"
    return types.MappingProxyType({
        "tier": tier, "instance": instance,
        "runner_user": tier, "operator_user": f"{tier}-op", "egress_user": f"{tier}-egress",
        # Two copies of config.json, from one staged blob: the library's is in the ops digest and is the one this broker
        # reads; the /etc one is where other tiers' brokers and setups look for this tier (other_tiers, its deploy_dir).
        "lib_dir": lib, "lib_config": f"{lib}/config.json",
        "etc_dir": etc, "config": f"{etc}/config.json", "key": f"{etc}/receipt.key",
        "deploy_key": f"{etc}/github-deploy-key", "known_hosts": f"{etc}/known_hosts",
        "state_dir": f"/var/lib/{tier}", "log_dir": f"/var/log/{tier}", "run_dir": run, "clone_base": f"/var/lib/{tier}-clone",
        "socket": f"{run}/op.sock", "egress_socket": f"{run}/egress.sock", "steps_dir": f"{run}/steps",
        "lock": f"{run}/broker.lock", "health_stamp": f"{run}/health.stamp",
        "command": f"factory-op{suffix}", "command_path": f"/usr/local/sbin/factory-op{suffix}",
        "broker_unit": f"factory-op{suffix}", "egress_unit": f"factory-op{suffix}-egress",
        "drift_unit": f"factory-op{suffix}-drift", "unit_prefix": f"factory-op{suffix}-step-",
        "nft_table": "factory_prod" + (f"_{instance}" if instance else ""),
        "firewall_unit": f"{tier}-firewall", "runner_unit": f"{tier}-runner",
        "sudoers": f"/etc/sudoers.d/91-agent-readonly{suffix}",
    })


TIER = tier_of(LIB)
# Outside a tier's install path (a repository checkout, CI) the names are the first tier's, for tests; main() refuses
# every command there, so none of them is ever used for real.
NAMES = tier_names(TIER or "factory-prod")
CONFIG = pathlib.Path(NAMES["lib_config"])  # the hashed copy (gates.installed_ops_files), never /etc's
KEY = pathlib.Path(NAMES["key"])
DEPLOY_KEY = pathlib.Path(NAMES["deploy_key"])
KNOWN_HOSTS = pathlib.Path(NAMES["known_hosts"])
ETC_DIR = pathlib.Path(NAMES["etc_dir"])
STATE_DIR = pathlib.Path(NAMES["state_dir"])
LOGS_DIR = pathlib.Path(NAMES["log_dir"])
RUN_DIR = pathlib.Path(NAMES["run_dir"])
EGRESS_SOCK = NAMES["egress_socket"]
STEPS_DIR = pathlib.Path(NAMES["steps_dir"])
LOCK = pathlib.Path(NAMES["lock"])
HEALTH_STAMP = pathlib.Path(NAMES["health_stamp"])
RUNNER_USER = NAMES["runner_user"]
UNIT_PREFIX = NAMES["unit_prefix"]
USER_AGENT = NAMES["command"]
# The files of a tier's /etc directory that are its own, so a declared secret can't be one of them (setup's TIER_FILES).
TIER_FILES = frozenset({"config.json", "receipt.key", "github-deploy-key", "github-deploy-key.pub", "known_hosts", "tier"})

# Root runs these by absolute path: sudo's PATH may not be the one expected, and a bare name would be a lookup.
SYSTEMD_RUN = "/usr/bin/systemd-run"
SYSTEMCTL = "/usr/bin/systemctl"
SSH_BIN = "/usr/bin/ssh"
PYTHON = "/usr/bin/python3"
GITHUB_API = "https://api.github.com"
WORKFLOW = ".github/workflows/factory-gate.yml"
# The gate run's environment: config.json's `environment` (factory.json's environments.production, which setup checks), or
# the factory's default name.
ENVIRONMENT = "factory-production"
ENVIRONMENT_RE = re.compile(r"^[A-Za-z0-9._-]{1,100}$")
BRANCH = re.compile(r"^factory/([0-9]+)-impl$")
RAW_HEADER = re.compile(r"^:[0-7]{6} [0-7]{6} [0-9a-f]{40} [0-9a-f]{40} [ADMTUX]$")  # git diff --raw -z --no-renames
# A release gate's pinned branch, factory/release/<execution PR>-<gate>-<first 12 of the commit>; a test ties it to gates.PIN.
PIN = re.compile(r"^factory/release/([0-9]+)-(G[1-9][0-9]?)-([0-9a-f]{12})$")
OUT_LINE = re.compile(r"^([a-z][a-z0-9_]{0,31})=(.*)$")
TOKEN = re.compile(r"^[A-Za-z0-9_.-]{20,4096}$")
SHA = re.compile(r"^[0-9a-f]{40}$")
UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
# gates.FIELD and gates.STEP_ID, copied so a step and a project's CI can validate without importing gates (a test ties them).
FIELD = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
STEP_ID = re.compile(r"^[a-z][a-z0-9-]{0,31}$")
RUN_ID = re.compile(r"^[A-Za-z0-9-]{1,80}$")
PRINTABLE = re.compile(r"^[ -~]*$")
SAFE_PATH = re.compile(r"^/[A-Za-z0-9._/@+-]{0,250}$")
STEP_PATH = "/usr/local/bin:/usr/bin:/bin"
LOCK_WAIT_S = 1800
HEALTH_LOCK_WAIT_S = 60
GIT_TIMEOUT_S = 120
FETCH_TIMEOUT_S = 600  # a first full fetch; every other git call keeps GIT_TIMEOUT_S
READ_LIMIT = 65536  # the most root reads of a file the operator wrote
DETAIL_LIMIT = 1 << 20  # a step's notes and drift rows
SERVE_READ_TIMEOUT_S = 30
# After a step's timeout: `systemctl stop` (50 s; the unit's TimeoutStopSec SIGKILLs it at 30 s), SIGKILL and the wait until
# systemd says it is gone (35 s, then SIGKILL again for as long as it takes), its client (5 s).
STEP_KILL_MARGIN_S = 90
STOP_TIMEOUT_S, UNIT_GONE_WAIT_S, CLIENT_WAIT_S = 50, 35, 5
# A passwordless `health` can hold the lock for its whole timeout plus the kill margin; the daily drift check waits longer
# than any health timeout the catalog allows (3600 s is gates' limit, the drift wait is checked against health's own).
DRIFT_LOCK_WAIT_S = 1000
GIT_CALLS_BUDGET_S = 600  # the drift check's many short local git calls, bounded generously
DRIFT_WINDOW_S = 25 * 3600  # deployments the daily drift check looks at
REQUEST_TIMEOUT_S = 30
MAX_RESPONSE = 16 << 20  # the most one ctx.https request may read
MAX_APP_BODY = 1 << 20  # http-check's body
POLL_S = 5
DEADLINE_MARGIN = 1.1  # a step's internal deadline is timeout_s / this, so it exits 1 before the broker's kill
MAX_NOTES, NOTE_LIMIT = 50, 300
MAX_ROWS = 200
# The oldest Python the broker and its steps run on (gates.py's own floor): broker.python may only raise it.
PYTHON_FLOOR = (3, 8)

# A release gate's run is one job of factory-gate.yml with timeout-minutes 300, and the broker's lock wait, its fetch, both
# captures and every step sit inside it. A request whose worst case doesn't fit is refused before anything runs.
GATE_JOB_S = 300 * 60
RELEASE_SLACK_S = 1200  # the GitHub reads and local git calls of a release gate's checks
# The checks before a release gate runs anything stop at a deadline, checked between calls, in two windows of this length: from
# the start of the rebuild to the fetch of the release branch (the release PR reads), and from the fetch to the end of provenance
# (the git comparisons and the commit-by-commit reads). The fetch has its own bound (FETCH_TIMEOUT_S).
PRE_RUN_BUDGET_S = 480

# `release` is a release gate's run (D4 rule 13). ops.json's `release_gates` says whether this broker takes one yet.
REQUEST_KINDS = ("ops", "cd", "release")

# The step's sandbox, less the paths that depend on the configuration (hidden_paths and Sandbox.argv). setup-production.sh
# builds the same properties for its acceptance probe, and its test compares them with this constant.
# AF_UNIX stays allowed (the egress proxy is a Unix socket), so what a step can reach locally is an allowlist, not a list of
# sockets to hide: /run (and /var/run, its link) is an empty read-only tmpfs, into which Sandbox.argv binds only the egress
# socket (read-only) and the step's own directory; PrivateIPC gives the step its own SysV and POSIX IPC; /dev/shm and
# /dev/mqueue, which PrivateDevices binds from the host, are hidden (HIDDEN_ALWAYS). PrivateIPC needs systemd 248, the floor
# setup checks (SYSTEMD_FLOOR). TimeoutStopSec bounds a stop, so a timed-out step is gone within the kill margin.
# ProcSubset=pid is left out on purpose: systemd calls it unsuitable for most non-trivial programs, and it hides /proc/sys.
# A syscall outside @system-service returns EPERM instead of killing the step with SIGSYS.
STEP_PROPS = ("NoNewPrivileges=yes", "PrivateTmp=yes", "ProtectSystem=strict", "ProtectHome=yes", "RestrictAddressFamilies=AF_UNIX",
              "PrivateNetwork=yes", "PrivateIPC=yes", "TemporaryFileSystem=/run:ro", "KillMode=control-group",
              "TimeoutStopSec=30", "ProtectProc=invisible", "PrivateDevices=yes",
              "RestrictNamespaces=yes", "CapabilityBoundingSet=", "SystemCallFilter=@system-service", "SystemCallErrorNumber=EPERM",
              "SystemCallArchitectures=native", "LockPersonality=yes", "RestrictSUIDSGID=yes", "UMask=0077",
              "MemoryMax=512M", "TasksMax=64", "LimitFSIZE=1M")
SYSTEMD_FLOOR = 248  # PrivateIPC= (setup-production.sh's SYSTEMD_FLOOR)
# What a step can't see beyond other tiers' directories: the host's network control sockets (under /run, so the empty /run
# hides them too: these stay for a host whose systemd ignored it), and the host's shared memory and message queues.
HIDDEN_ALWAYS = ("/run/tailscale", "/var/run/tailscale", "/run/dbus/system_bus_socket", "/run/systemd/resolve", "/dev/shm",
                 "/dev/mqueue")

# The generic operations: catalog operations whose code is this file's, and internal operations (outside the catalog,
# which plans can't name) the broker runs itself. A host diagnostic is any other internal operation.
GENERIC_OPS = ("release-wait", "health", "http-check", "capture-state")
GENERIC_INTERNAL = ("drift-scan", "host-check")
STATUSES = ("waiting", "success", "skipped", "failed", "crashed")
EVIDENCE = ("reports", "heartbeat", "both", "none")
# What the host module may import from this one (the contract, process/factory-broker.md § The host module).
HOST_API = ("StepFailed", "Unavailable", "HostError", "Deployment", "STATUSES", "Deadline", "NETWORK_ERRORS", "SHA", "safe",
            "parse_ts", "canonical")
PRIMITIVES = ("client", "preflight", "latest", "deployments", "serving", "reports", "heartbeat", "capture")


class Refused(Exception):
    """A broker-side check failed: nothing runs."""


class LockBusy(Refused):
    """The broker lock stayed held for the whole wait."""


class StepFailed(Exception):
    """An operation failed (exit 1). The message is printed, so it must never carry a secret (root redacts the installed
    secrets from the step's log anyway). `outputs` are written, and root keeps those the catalog allows."""

    def __init__(self, message, outputs=None):
        super().__init__(message)
        self.outputs = outputs or {}


class Unavailable(StepFailed):
    """A running service gave no usable answer (unreachable, not 200, cached, not JSON): patient waits go on, strict reads fail."""


class HostError(Exception):
    """The host's API failed."""


Deployment = collections.namedtuple("Deployment", "id commit status created branch", defaults=(None,))


def now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def safe(text, limit=200):
    """Only printable ASCII leaves a message, so a response can't smuggle control characters into a log."""
    return re.sub(r"[^ -~]", "?", str(text))[:limit]


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def parse_ts(text):
    if not isinstance(text, str):
        raise StepFailed("a timestamp from the host or a service wasn't text")
    try:
        parsed = datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        raise StepFailed("a timestamp from the host or a service didn't parse") from None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=datetime.timezone.utc)


def frozen(obj):
    """A read-only copy: dicts become mapping proxies, lists tuples."""
    if isinstance(obj, dict):
        return types.MappingProxyType({k: frozen(v) for k, v in obj.items()})
    if isinstance(obj, (list, tuple)):
        return tuple(frozen(v) for v in obj)
    return obj


# ---------------------------------------------------------------- configuration (config.json's generic keys)

REPO_RE = re.compile(r"^[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}$")
GIT_BRANCH = re.compile(r"^[A-Za-z0-9._/-]{1,100}$")  # gates.BRANCH


def plain_path(value):
    return isinstance(value, str) and bool(SAFE_PATH.fullmatch(value)) and ".." not in value.split("/")


def config_problems(cfg, names=None):
    """What stops config.json from being trusted, from its generic keys: every command but `check` refuses until there are
    none. `names` (the tier's) also requires the instance and every path to be the tier's own, so an edit to the checkout's
    copy can't point root at another tier's ledger or clone. The `host` block is the host module's to check (preflight)."""
    if not isinstance(cfg, dict):
        return ["config.json isn't an object"]
    problems = []

    def need(key, ok, what):
        if not ok(cfg.get(key)):
            problems.append(f"config.json's {key} must be {what}")

    need("repo", lambda v: isinstance(v, str) and REPO_RE.fullmatch(v), "owner/name")
    for key in ("default_branch", "release_branch"):
        need(key, lambda v: isinstance(v, str) and GIT_BRANCH.fullmatch(v) and ".." not in v, "a branch name")
    need("release_head_start", lambda v: isinstance(v, str) and re.fullmatch(r"[0-9a-f]{7,40}", v),
         "7 to 40 hex characters (the commit the release branch was created at)")
    need("app_bot_id", lambda v: type(v) is int and v > 0, "the factory App's GitHub user id")
    need("approvers", lambda v: isinstance(v, list) and v and all(type(a) is int and a > 0 for a in v), "a list of GitHub user ids")
    need("operator_user", lambda v: isinstance(v, str) and re.fullmatch(r"[a-z][a-z0-9-]{0,31}", v), "a user name")
    for key in ("lib_dir", "ledger", "log_dir", "clone_dir"):
        need(key, plain_path, "an absolute path of plain characters")
    need("deploy_dir", lambda v: v is None or plain_path(v), "an absolute path of plain characters, when given")
    need("instance", lambda v: isinstance(v, str) and re.fullmatch(r"([a-z0-9]{1,12})?", v), "the tier's instance ('' for the first)")
    need("host", lambda v: isinstance(v, dict), "an object (the host module's settings)")
    if "environment" in cfg and not (isinstance(cfg["environment"], str) and ENVIRONMENT_RE.fullmatch(cfg["environment"])):
        problems.append("config.json's environment must be an environment name (factory.json's environments.production), "
                        f"when given; without it the gate run's environment is {ENVIRONMENT}")
    if names and not problems:
        mine = {"instance": names["instance"], "operator_user": names["operator_user"], "lib_dir": names["lib_dir"],
                "log_dir": names["log_dir"]}
        for key, want in mine.items():
            if cfg[key] != want:
                problems.append(f"config.json's {key} is {safe(cfg[key], 80)!r}, not this tier's {want!r} (from its install path)")
        for key, parent in (("ledger", names["state_dir"]), ("clone_dir", names["clone_base"])):
            if str(pathlib.PurePosixPath(cfg[key]).parent) != parent:
                problems.append(f"config.json's {key} must be in {parent}")
    return problems


def environment_of(cfg):
    """The deployment environment an approver approves a gate run in."""
    return cfg.get("environment", ENVIRONMENT)


# ---------------------------------------------------------------- the catalog's broker block (process/factory-broker.md)

HOSTNAME = re.compile(r"^(?=.{1,253}$)[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)+$")
SECRET_LABEL = re.compile(r"^[a-z][a-z0-9_]{0,15}$")
SECRET_FILE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
SERVICE = re.compile(r"^[a-z][a-z0-9_]{0,20}$")  # <svc>_deployment fits FIELD
TARGET = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
PHASE = re.compile(r"^[a-z][a-z0-9_]{0,29}_s$")
GLOB = re.compile(r"^/?[A-Za-z0-9_.*-][A-Za-z0-9_./*-]*$")
PYTHON_VERSION = re.compile(r"^3\.([0-9]{1,2})$")
WHY = re.compile(r"^[ -~]{1,200}$")
SHA_PATTERN, MAYBE_SHA_PATTERN, YES_NO = "^[0-9a-f]{40}$", "^([0-9a-f]{40})?$", "^(yes|no)$"
# key: required. Unknown keys are refused, so a typo can't turn a check off.
BLOCK_KEYS = {"egress": True, "http_targets": False, "secrets": True, "op_secrets": True, "host_ops": True, "services": True,
              "heartbeat_ttl_s": False, "release_wait_phases": True, "recorded": True, "invariants": False,
              "internal_ops": True, "python": True, "host_locks": False}


def is_int(value, low, high):
    return type(value) is int and low <= value <= high


def accepts(pattern, value):
    try:
        return isinstance(pattern, str) and re.fullmatch(pattern, value) is not None
    except re.error:
        return False


def anchored(pattern):
    if not isinstance(pattern, str) or not pattern.startswith("^") or not pattern.endswith("$"):
        return False
    try:
        re.compile(pattern)
    except re.error:
        return False
    return True


def host_name_ok(name):
    """A lower-case DNS name that can't be read as an address: its last label starts with a letter (getaddrinfo reads
    "127.1" or "0x7f.1" as an IPv4 address)."""
    if not isinstance(name, str) or not HOSTNAME.fullmatch(name) or not re.fullmatch(r"[a-z][a-z0-9-]*", name.rsplit(".", 1)[-1]):
        return False
    try:
        ipaddress.ip_address(name)
    except ValueError:
        return True
    return False


def services_of(block, key=None):
    """The declared services in order, or those whose `key` (release or checked) is true."""
    return [s for s, d in block["services"].items() if key is None or d[key]]


def op_of(catalog, name):
    """A catalog operation, or an internal one as the sandbox runs it (no params, no outputs), or None."""
    if name in catalog["operations"]:
        return catalog["operations"][name]
    spec = catalog.get("broker", {}).get("internal_ops", {}).get(name)
    return {"kind": "read", "timeout_s": spec["timeout_s"], "params": {}, "outputs": {}} if spec else None


def min_gate_overhead_s(catalog):
    """The broker's worst case around a gate's steps: the lock wait, the fetch, a release gate's checks and both captures,
    each capture with its kill margin. The catalog's gate_overhead_s must be at least this (the plan guard's budget)."""
    return LOCK_WAIT_S + FETCH_TIMEOUT_S + RELEASE_SLACK_S + 2 * (catalog["operations"]["capture-state"]["timeout_s"]
                                                                   + STEP_KILL_MARGIN_S)


def drift_lock_wait_s(catalog):
    """Longer than a passwordless `health` can hold the lock, so one started just before the daily check can't starve it."""
    return max(DRIFT_LOCK_WAIT_S, catalog["operations"]["health"]["timeout_s"] + STEP_KILL_MARGIN_S + 60)


def drift_unit_min_s(catalog):
    """The drift unit's worst case: the lock wait, a first full fetch, capture-state and drift-scan with their kill margins,
    and the local git calls. Setup's TimeoutStartSec for the drift unit must be at least this."""
    return (drift_lock_wait_s(catalog) + FETCH_TIMEOUT_S + catalog["operations"]["capture-state"]["timeout_s"]
            + catalog["broker"]["internal_ops"]["drift-scan"]["timeout_s"] + 2 * STEP_KILL_MARGIN_S + GIT_CALLS_BUDGET_S)


def lib_scripts(lib_dir):
    """The names of the ops/<name>.sh files installed beside the broker (a project's own operations)."""
    try:
        return frozenset(p.stem for p in (pathlib.Path(lib_dir) / "ops").glob("*.sh"))
    except OSError:
        return frozenset()


def broker_problems(catalog, scripts=()):
    """Everything wrong with ops.json's broker block and the catalog keys this broker requires, as messages ([] when
    nothing is). Pure, no I/O, and never raises, so root's load, `check` and a project's CI test can all call it on the
    catalog gates.load_catalog returns. `scripts`: the names of the ops/<name>.sh files the project keeps."""
    try:
        return _broker_problems(catalog, frozenset(scripts))
    except Exception as e:  # a shape the checks didn't foresee is a problem, never a crash or a pass
        return [f"ops.json couldn't be checked ({type(e).__name__}): fix its broker block"]


def _broker_problems(catalog, scripts):
    if not isinstance(catalog, dict) or not isinstance(catalog.get("operations"), dict):
        return ["ops.json needs an operations object"]
    ops, block = catalog["operations"], catalog.get("broker")
    if not isinstance(block, dict):
        return ["ops.json needs a broker block (an object)"]
    p = []
    unknown = sorted(set(block) - set(BLOCK_KEYS))
    if unknown:
        p.append(f"broker: unknown key {', '.join(safe(k, 40) for k in unknown)}")
    missing = [k for k, required in BLOCK_KEYS.items() if required and k not in block]
    if missing:
        return p + [f"broker: missing {', '.join(missing)}"]

    # The catalog keys this broker requires.
    if type(catalog.get("release_gates")) is not bool:
        p.append("release_gates must be true or false (false while the broker is being enabled, then true)")
    if catalog.get("rollbacks") is not False:
        p.append("rollbacks must be false: a checks-only broker runs no rollback, so the plan guard refuses one")
    if catalog.get("release_wait") != "release-wait":
        p.append('release_wait must be "release-wait", the broker\'s own wait')
    for name in ("release-wait", "health", "capture-state"):
        if not isinstance(ops.get(name), dict):
            p.append(f"the catalog needs the generic operation {name}")
    for name, op in ops.items():
        if not isinstance(op, dict):
            return p + [f"operation {safe(name, 40)} isn't an object"]
        if op.get("rollback_only"):
            p.append(f"{safe(name, 40)} is rollback_only: this broker runs no rollback")
        if name in GENERIC_OPS and op.get("kind") != "read":
            p.append(f"{name} must be a read operation")
    if isinstance(ops.get("capture-state"), dict) and is_int(ops["capture-state"].get("timeout_s"), 1, 3600):
        if not is_int(catalog.get("gate_overhead_s"), min_gate_overhead_s(catalog), GATE_JOB_S):
            p.append(f"gate_overhead_s must be at least {min_gate_overhead_s(catalog)}, the broker's own worst case around a "
                     f"gate's steps with this capture-state timeout")
    if not is_int(catalog.get("step_margin_s"), STEP_KILL_MARGIN_S, 3600):
        p.append(f"step_margin_s must be at least {STEP_KILL_MARGIN_S}, the broker's kill margin")

    # egress and http_targets
    egress = block["egress"]
    if not isinstance(egress, list) or not 1 <= len(egress) <= 16:
        p.append("broker.egress: 1 to 16 host names")
        egress = []
    for host in egress:
        if not host_name_ok(host):
            p.append(f"broker.egress: {safe(host, 80)!r} isn't a lower-case host name (no address literals)")
    if len(set(map(str, egress))) != len(egress):
        p.append("broker.egress: a host is listed twice")
    targets = block.get("http_targets", {})
    if not isinstance(targets, dict):
        p.append("broker.http_targets must be an object")
        targets = {}
    for name, host in targets.items():
        if not TARGET.fullmatch(name) or host not in egress:
            p.append(f"broker.http_targets.{safe(name, 40)}: a lower-case name for a host in broker.egress")
    if targets:
        check = ops.get("http-check")
        if not isinstance(check, dict):
            p.append("broker.http_targets needs the http-check operation")
        else:
            if set(check.get("params", {})) != {"target", "path", "expect_status"}:
                p.append("http-check takes exactly target, path and expect_status")
            if not {"status", "latency_ms", "body_sha256"} <= set(check.get("outputs", {})):
                p.append("http-check must output status, latency_ms and body_sha256")
            for name in targets:
                if not accepts(check.get("params", {}).get("target"), name):
                    p.append(f"http-check's target pattern refuses the declared target {safe(name, 40)}")

    # secrets
    secrets = block["secrets"]
    if not isinstance(secrets, dict):
        p.append("broker.secrets must be an object")
        secrets = {}
    files = []
    for label, spec in secrets.items():
        where = f"broker.secrets.{safe(label, 20)}"
        if not SECRET_LABEL.fullmatch(label):
            p.append(f"{where}: labels are lower-case, up to 16 characters")
        if not isinstance(spec, dict) or set(spec) - {"file", "by", "hex", "pattern"} or not {"file", "by", "hex"} <= set(spec):
            p.append(f"{where}: {{file, by, hex, pattern?}}")
            continue
        if not isinstance(spec["file"], str) or not SECRET_FILE.fullmatch(spec["file"]) or spec["file"] in TIER_FILES:
            p.append(f"{where}.file: a plain file name in the tier's /etc directory, not one of the tier's own")
        files.append(spec["file"])
        if spec["by"] not in ("cd", "setup"):
            p.append(f"{where}.by: cd or setup")
        if type(spec["hex"]) is not bool:
            p.append(f"{where}.hex: true or false")
        elif spec["by"] == "setup" and not spec["hex"]:
            p.append(f"{where}: a secret setup generates is hex")
        if "pattern" in spec and (spec["hex"] is not False or not anchored(spec["pattern"])):
            p.append(f"{where}.pattern: an anchored pattern, for a secret that isn't hex")
    if len(set(map(str, files))) != len(files):
        p.append("broker.secrets: two secrets name one file")

    # internal operations, op_secrets, host_ops and scripts
    internal = block["internal_ops"]
    if not isinstance(internal, dict):
        p.append("broker.internal_ops must be an object")
        internal = {}
    for name in GENERIC_INTERNAL:
        if name not in internal:
            p.append(f"broker.internal_ops needs {name}")
    for name, spec in internal.items():
        if not STEP_ID.fullmatch(name) or name in ops:
            p.append(f"broker.internal_ops.{safe(name, 40)}: an operation name that isn't in the catalog")
        if not isinstance(spec, dict) or set(spec) != {"timeout_s"} or not is_int(spec.get("timeout_s"), 1, 3600):
            p.append(f"broker.internal_ops.{safe(name, 40)}: {{timeout_s}} between 1 and 3600")
    op_secrets = block["op_secrets"]
    if not isinstance(op_secrets, dict):
        p.append("broker.op_secrets must be an object")
        op_secrets = {}
    everything = set(ops) | set(internal)
    if set(op_secrets) != everything:
        gone, extra = sorted(everything - set(op_secrets)), sorted(set(op_secrets) - everything)
        p.append("broker.op_secrets lists every operation, catalog and internal, once"
                 + (f" (missing {', '.join(gone)})" if gone else "") + (f" (unknown {', '.join(map(safe, extra))})" if extra else ""))
    for name, labels in op_secrets.items():
        if not isinstance(labels, list) or len(set(map(str, labels))) != len(labels) or any(lb not in secrets for lb in labels):
            p.append(f"broker.op_secrets.{safe(name, 40)}: a list of declared secret labels, each once")
    host_ops = block["host_ops"]
    if not isinstance(host_ops, list) or len(set(map(str, host_ops))) != len(host_ops):
        p.append("broker.host_ops must be a list of operation names, each once")
        host_ops = []
    for name in host_ops:
        if name not in ops or name in GENERIC_OPS:
            p.append(f"broker.host_ops: {safe(name, 40)} must be a catalog operation that isn't a generic one")
    for name in ops:
        if name not in GENERIC_OPS and name not in host_ops and name not in scripts:
            p.append(f"{safe(name, 40)} is neither a generic operation, nor in broker.host_ops, nor an ops/{safe(name, 40)}.sh")
    for name in sorted(scripts):
        if name in GENERIC_OPS or name in host_ops or name in internal:
            p.append(f"ops/{safe(name, 40)}.sh: a script can't stand in for {safe(name, 40)}, which the broker or the host module runs")
        elif name not in ops:
            p.append(f"ops/{safe(name, 40)}.sh names no catalog operation")

    # services, heartbeat, the release wait
    services = block["services"]
    if not isinstance(services, dict) or not 1 <= len(services) <= 32:
        p.append("broker.services: 1 to 32 services")
        services = {}
    release, checked, beats = [], [], False
    for svc, spec in services.items():
        where = f"broker.services.{safe(svc, 30)}"
        if not SERVICE.fullmatch(svc):
            p.append(f"{where}: a lower-case name of up to 21 characters")
        if not isinstance(spec, dict) or set(spec) - {"release", "checked", "evidence", "patterns"} \
                or not {"release", "checked", "evidence"} <= set(spec) \
                or type(spec["release"]) is not bool or type(spec["checked"]) is not bool:
            p.append(f"{where}: {{release, checked, evidence, patterns}} with release and checked true or false")
            continue
        if spec["release"] and not spec["checked"]:
            p.append(f"{where}: a release service is checked too")
        if spec["evidence"] not in EVIDENCE:
            p.append(f"{where}.evidence: one of {', '.join(EVIDENCE)}")
        elif spec["release"] and spec["evidence"] == "none":
            p.append(f"{where}: a release service needs evidence that it serves the new release (reports, heartbeat or "
                     f"both; D4 rule 15)")
        elif not spec["release"] and spec["evidence"] != "none":
            p.append(f"{where}: only a release service has evidence")
        beats = beats or spec["evidence"] in ("heartbeat", "both")
        if spec["checked"]:
            pats = spec.get("patterns")
            if not isinstance(pats, list) or not 1 <= len(pats) <= 64 \
                    or not all(isinstance(g, str) and GLOB.fullmatch(g) and ".." not in g for g in pats):
                p.append(f"{where}.patterns: 1 to 64 globs such as web/** (a leading slash is optional)")
            checked.append(svc)
        elif "patterns" in spec:
            p.append(f"{where}: patterns are for a checked service")
        if spec["release"]:
            release.append(svc)
    if services and not release:
        p.append("broker.services: at least one release service")
    ttl = block.get("heartbeat_ttl_s")
    if (beats and ttl is None) or (ttl is not None and not is_int(ttl, 1, 3600)):
        p.append("broker.heartbeat_ttl_s: 1 to 3600 seconds, required when a service's evidence is a heartbeat")
    phases = block["release_wait_phases"]
    phases_ok = isinstance(phases, dict) and is_int(phases.get("grace_s"), 1, 3600) \
        and all(isinstance(k, str) and PHASE.fullmatch(k) and is_int(v, 0, 3600) for k, v in phases.items())
    if not phases_ok:
        p.append("broker.release_wait_phases: {grace_s, <name>_s} in whole seconds, 0 to 3600, grace_s at least 1")
    elif isinstance(ops.get("release-wait"), dict) and is_int(ops["release-wait"].get("timeout_s"), 1, 3600) \
            and ops["release-wait"]["timeout_s"] * 10 < 11 * sum(phases.values()):
        p.append(f"release-wait's timeout_s must be at least 1.1 times the release wait's phases ({sum(phases.values())} s)")
    # D4 rule 15's two heartbeat reads more than heartbeat_ttl_s apart, for each release service whose evidence is a heartbeat,
    # one service after another. health reads strictly: a read, a pause of heartbeat_ttl_s + 1, a read. release-wait reads
    # patiently, one read every POLL_S, so its second good read comes up to heartbeat_ttl_s + POLL_S after the first. Each read
    # may take REQUEST_TIMEOUT_S. A health whose timeout can't hold them fails every time; phases that leave them no room
    # make every release gate's wait fail.
    beating = [s for s in release if services[s]["evidence"] in ("heartbeat", "both")]
    if beating and is_int(ttl, 1, 3600):
        reads = 2 * REQUEST_TIMEOUT_S
        need = len(beating) * (ttl + 1 + reads)
        check = ops.get("health")
        if isinstance(check, dict) and is_int(check.get("timeout_s"), 1, 3600) and check["timeout_s"] * 10 < 11 * need:
            p.append(f"health's timeout_s must be at least {-(-11 * need // 10)}, 1.1 times its heartbeat reads: for each of "
                     f"{', '.join(beating)}, two reads of up to {REQUEST_TIMEOUT_S} s, heartbeat_ttl_s + 1 s apart")
        room = len(beating) * (ttl + POLL_S + reads)
        if phases_ok and sum(phases.values()) - phases["grace_s"] < room:
            p.append(f"broker.release_wait_phases leave no room for the heartbeat evidence: the phases after grace_s must add up "
                     f"to at least {room} s (for each of {', '.join(beating)}, two reads of up to {REQUEST_TIMEOUT_S} s, more "
                     f"than heartbeat_ttl_s apart)")

    # the generic operations' parameters and outputs
    def outputs_of(name):
        op = ops.get(name)
        return op.get("outputs", {}) if isinstance(op, dict) and isinstance(op.get("outputs", {}), dict) else {}

    def need_outputs(name, fields):
        gone = [f for f in fields if f not in outputs_of(name)]
        if gone and isinstance(ops.get(name), dict):
            p.append(f"{name} must output {', '.join(gone)}")

    wait, health, capture = ops.get("release-wait"), ops.get("health"), ops.get("capture-state")
    joined = ",".join(release)
    if isinstance(wait, dict):
        if wait.get("params") != {"sha": SHA_PATTERN}:
            p.append(f"release-wait takes exactly {{sha: {SHA_PATTERN}}}")
        need_outputs("release-wait", ["head", "deployed"] + [f"{s}_deployment" for s in release])
        if "head" in outputs_of("release-wait") and outputs_of("release-wait")["head"] != SHA_PATTERN:
            p.append(f"release-wait's head output is {SHA_PATTERN}")
        if "deployed" in outputs_of("release-wait") and not all(accepts(outputs_of("release-wait")["deployed"], v)
                                                                for v in ["", joined, *release]):
            p.append("release-wait's deployed pattern must accept the release services, comma-separated in declared order")
    if isinstance(health, dict):
        if health.get("params", {}) != {}:
            p.append("health takes no parameters")
        need_outputs("health", ["healthy", "services", "unhealthy"] + [f"{s}_deployment" for s in release])
        outs = outputs_of("health")
        if "healthy" in outs and outs["healthy"] != YES_NO:
            p.append(f"health's healthy output is {YES_NO}")
        if "services" in outs and not accepts(outs["services"], str(len(services))):
            p.append("health's services pattern must accept the number of declared services")
        if "unhealthy" in outs and not all(accepts(outs["unhealthy"], v) for v in ["", ",".join(services), *services]):
            p.append("health's unhealthy pattern must accept the declared services, comma-separated")
    capture_outs = outputs_of("capture-state")
    if isinstance(capture, dict):
        if capture.get("params", {}) != {}:
            p.append("capture-state takes no parameters")
        for svc in checked:
            want = (SHA_PATTERN,) if svc in release else (SHA_PATTERN, MAYBE_SHA_PATTERN)
            if capture_outs.get(f"{svc}_commit") not in want:
                p.append(f"capture-state must output {svc}_commit as {' or '.join(want)}")
            if capture_outs.get(f"{svc}_settled") != YES_NO:
                p.append(f"capture-state must output {svc}_settled as {YES_NO}")
    moving = {f"{s}_{k}" for s in services for k in ("commit", "settled", "deployment")}

    # recorded and invariants
    recorded = block["recorded"]
    if not isinstance(recorded, list) or not recorded or len(set(map(str, recorded))) != len(recorded):
        p.append("broker.recorded: a non-empty list of capture-state outputs, each once")
        recorded = []
    invariants = block.get("invariants", {})
    if not isinstance(invariants, dict):
        p.append("broker.invariants must be an object")
        invariants = {}
    for name in recorded:
        if name not in capture_outs or name in moving or name in invariants:
            p.append(f"broker.recorded: {safe(name, 40)} must be a capture-state output that isn't an invariant, a commit, "
                     f"a settledness or a deployment")
    for name, rule in invariants.items():
        where = f"broker.invariants.{safe(name, 40)}"
        if name not in capture_outs or name in moving or name in recorded:
            p.append(f"{where}: a capture-state output that isn't recorded, a commit, a settledness or a deployment")
        if not isinstance(rule, dict) or set(rule) - {"is", "in", "why", "show"} or ("is" in rule) == ("in" in rule):
            p.append(f"{where}: {{is or in, why, show?}}")
            continue
        values = [rule["is"]] if "is" in rule else rule["in"]
        if not isinstance(values, list) or not values or len(set(map(str, values))) != len(values) \
                or not all(isinstance(v, str) and accepts(capture_outs.get(name), v) for v in values):
            p.append(f"{where}: each expected value must be text its capture-state pattern accepts")
        if not isinstance(rule.get("why"), str) or not WHY.fullmatch(rule["why"]):
            p.append(f"{where}.why: printable text, 1 to 200 characters")
        show = rule.get("show", [])
        if not isinstance(show, list) or not all(isinstance(s, str) and s in capture_outs and s != name for s in show):
            p.append(f"{where}.show: other capture-state outputs")
        else:
            for s in show:
                if s not in capture_outs:
                    p.append(f"{where}.show: {safe(s, 40)} isn't a capture-state output")

    # python, host locks
    py = block["python"]
    m = PYTHON_VERSION.fullmatch(py) if isinstance(py, str) else None
    if not m or (3, int(m.group(1))) < PYTHON_FLOOR:
        p.append(f"broker.python: \"3.<n>\", at least {PYTHON_FLOOR[0]}.{PYTHON_FLOOR[1]}")
    locks = block.get("host_locks", [])
    if not isinstance(locks, list) or len(set(map(str, locks))) != len(locks) \
            or not all(host_lock_path_ok(x) for x in locks):
        p.append("broker.host_locks: absolute paths in a root-owned directory under /run/ (not /run/lock/, /run/user/ or "
                 "/var/lock/, which other users can write), each once")
    return p


def host_lock_path_ok(path):
    """A host lock's path, as data: plain, absolute, under /run/, and not in a directory other users can write by convention.
    broker_lock checks the directory and the file themselves (host_lock_problem)."""
    return plain_path(path) and path.startswith("/run/") and not path.startswith(("/run/lock/", "/run/user/")) \
        and path.count("/") >= 2 and not path.endswith("/")


# ---------------------------------------------------------------- the connection: only through the egress proxy

class EgressConnection(http.client.HTTPSConnection):
    """HTTPS to one of the block's egress hosts, tunnelled through the egress proxy's Unix socket. Certificates and host
    names are verified; there is no proxy-variable lookup and no redirect following (http.client does neither)."""

    def __init__(self, host, timeout, allowed=(), sock_path=None):
        if host not in allowed:
            raise HostError("host isn't one of the egress hosts this broker may reach")
        super().__init__(host, 443, timeout=timeout, context=ssl.create_default_context())
        self._sock_path = sock_path or EGRESS_SOCK

    def connect(self):
        raw = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            raw.settimeout(self.timeout)
            raw.connect(self._sock_path)
            raw.sendall(f"CONNECT {self.host}:443 HTTP/1.1\r\nHost: {self.host}:443\r\n\r\n".encode())
            reply = b""
            while b"\r\n\r\n" not in reply and len(reply) < 4096:
                chunk = raw.recv(1024)
                if not chunk:
                    break
                reply += chunk
            if not reply.startswith(b"HTTP/1.1 200"):
                raise HostError("the egress proxy refused the tunnel")
            self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
        except BaseException:
            raw.close()
            raise


def http_exchange(connect, allowed, host, method, path, headers, body, timeout, max_bytes):
    """One request. Refuses a host off the list, a relative path, a redirect and a body over max_bytes. Returns
    (status, lower-cased headers, body)."""
    if host not in allowed:
        raise HostError("host isn't one of the egress hosts this broker may reach")
    if not isinstance(path, str) or not path.startswith("/") or any(c in path for c in "\r\n "):
        raise HostError("path must be absolute, with no spaces or line breaks")
    conn = connect(host, timeout)
    try:
        conn.request(method, path, body=body, headers=headers)
        resp = conn.getresponse()
        if 300 <= resp.status < 400:
            raise HostError("redirects are refused")
        data = resp.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise HostError(f"response is over {max_bytes} bytes")
        return resp.status, {k.lower(): v for k, v in resp.getheaders()}, data
    finally:
        conn.close()


NETWORK_ERRORS = (OSError, http.client.HTTPException)


class Deadline:
    def __init__(self, seconds, clock):
        self.clock, self.end = clock, clock.monotonic() + seconds

    def left(self):
        return self.end - self.clock.monotonic()

    def check(self):
        if self.left() <= 0:
            raise StepFailed("the operation's deadline passed")


# ---------------------------------------------------------------- git (read-only, in the broker's bare clone)

GIT_BIN = next((p for p in ("/usr/bin/git", "/usr/local/bin/git", "/bin/git") if os.access(p, os.X_OK)), "/usr/bin/git")
DIFF_FLAGS = ("--no-renames", "--no-ext-diff", "--no-textconv")


class GitError(Exception):
    pass


def default_remote(repo):
    return f"https://github.com/{repo}.git"


def default_ssh_remote(repo):
    # The daily drift timer has no job token, only the read-only deploy key, and GIT_SSH_COMMAND does nothing for https.
    return f"git@github.com:{repo}.git"


def run_in_group(argv, *, env, capture_output=True, text=True, timeout, stdin=None):
    """subprocess.run, except a timeout (or any interruption) kills the whole process group. `git fetch` over ssh starts an
    ssh child; killing only git would leave ssh holding the connection (and the lock's time) open."""
    proc = subprocess.Popen(argv, env=env, stdin=stdin, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=text,
                            start_new_session=True)
    try:
        out, err = proc.communicate(timeout=timeout)
    except BaseException:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.communicate()
        raise
    return subprocess.CompletedProcess(argv, proc.returncode, out, err)


class Git:
    """Every git call goes through run(): a fixed environment (no user or system config, no prompts), the clone
    marked safe for the operator, and diff always without renames, external diff drivers and textconv. A token
    reaches a fetch only through GIT_CONFIG_* variables, never argv."""

    def __init__(self, gitdir, runner=run_in_group, remote=default_remote, ssh_remote=default_ssh_remote):
        self.gitdir, self._run, self.remote, self.ssh_remote = str(gitdir), runner, remote, ssh_remote

    def run(self, *args, token=None, ssh_key=None, timeout=GIT_TIMEOUT_S):
        argv = [GIT_BIN, "--git-dir", self.gitdir]
        args = list(args)
        if args and args[0] == "diff":
            args[1:1] = DIFF_FLAGS
        env = {"PATH": STEP_PATH, "LANG": "C.UTF-8", "HOME": "/nonexistent", "GIT_CONFIG_NOSYSTEM": "1",
               "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_COUNT": "1",
               "GIT_CONFIG_KEY_0": "safe.directory", "GIT_CONFIG_VALUE_0": self.gitdir, "GIT_NO_REPLACE_OBJECTS": "1"}
        if token:
            basic = base64.b64encode(f"x-access-token:{token}".encode()).decode()
            env.update({"GIT_CONFIG_COUNT": "2", "GIT_CONFIG_KEY_1": "http.extraheader",
                        "GIT_CONFIG_VALUE_1": f"AUTHORIZATION: basic {basic}"})
        if ssh_key:
            # No user ssh config, and only the host keys setup pinned: a first connection can't be talked into trusting a stranger.
            env["GIT_SSH_COMMAND"] = (f"{SSH_BIN} -F /dev/null -i {ssh_key} -o IdentitiesOnly=yes -o BatchMode=yes "
                                      f"-o StrictHostKeyChecking=yes -o UserKnownHostsFile={KNOWN_HOSTS} -o GlobalKnownHostsFile=/dev/null")
        try:
            return self._run(argv + args, env=env, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL)
        except (subprocess.TimeoutExpired, OSError) as e:
            raise GitError(f"git {safe(args[0] if args else '')} didn't run: {safe(e, 80)}") from None

    def fetch(self, repo, *refspecs, token=None, ssh_key=None):
        url = self.ssh_remote(repo) if ssh_key else self.remote(repo)
        r = self.run("fetch", "--no-tags", "--quiet", url, *refspecs, token=token, ssh_key=ssh_key, timeout=FETCH_TIMEOUT_S)
        if r.returncode != 0:
            raise GitError("git fetch failed")

    def has(self, sha):
        return isinstance(sha, str) and bool(SHA.fullmatch(sha)) and self.run("cat-file", "-e", f"{sha}^{{commit}}").returncode == 0

    def is_ancestor(self, older, newer):
        if not (isinstance(older, str) and isinstance(newer, str) and SHA.fullmatch(older) and SHA.fullmatch(newer)):
            return False
        return self.run("merge-base", "--is-ancestor", older, newer).returncode == 0

    def content_equal(self, a, b, patterns):
        """Same files at a and b under a service's patterns (the paths the host builds it from)."""
        if not (isinstance(a, str) and isinstance(b, str) and SHA.fullmatch(a) and SHA.fullmatch(b)):
            raise GitError("not a commit id")
        if not patterns or not all(isinstance(p, str) and GLOB.fullmatch(p) and ".." not in p for p in patterns):
            raise GitError("not a list of globs")
        r = self.run("diff", "--quiet", a, b, "--", *[":(glob)" + p.lstrip("/") for p in patterns])
        if r.returncode not in (0, 1):
            raise GitError("git diff failed")
        return r.returncode == 0

    def main_sha(self):
        return self.resolve(self.run("rev-parse", MAIN_REF).stdout.strip())

    def blob(self, rev, path):
        """A file's contents at a commit (cat-file: no filters, no textconv). Both arguments are checked first."""
        if not (isinstance(rev, str) and isinstance(path, str) and SHA.fullmatch(rev)
                and re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_./-]{0,150}", path) and ".." not in path):
            raise GitError("not a commit id or a plain repository path")
        r = self.run("cat-file", "blob", f"{rev}:{path}")
        if r.returncode != 0:
            raise GitError(f"{path} isn't in {rev[:12]}")
        return r.stdout

    def first_parent_after(self, base, head):
        if not (isinstance(base, str) and isinstance(head, str) and SHA.fullmatch(base) and SHA.fullmatch(head)):
            raise GitError("not a commit id")
        r = self.run("rev-list", "--first-parent", "--reverse", f"{base}..{head}")
        if r.returncode != 0:
            raise GitError("git rev-list failed")
        return r.stdout.split()

    def resolve(self, name):
        if not isinstance(name, str) or not re.fullmatch(r"^[0-9a-f]{7,40}$", name):
            raise GitError("not a commit id")
        r = self.run("rev-parse", "--verify", "--quiet", f"{name}^{{commit}}")
        out = r.stdout.strip()
        if r.returncode != 0 or not SHA.fullmatch(out):
            raise GitError(f"can't resolve {name}")
        return out

    def subject(self, sha):
        return safe(self.run("log", "-1", "--format=%s", sha).stdout.strip(), 100)

    def parents(self, sha):
        if not (isinstance(sha, str) and SHA.fullmatch(sha)):
            raise GitError("not a commit id")
        return self.run("rev-list", "--parents", "-n", "1", sha).stdout.split()[1:]

    def merge_base(self, a, b):
        r = self.run("merge-base", a, b) if SHA.fullmatch(a) and SHA.fullmatch(b) else None
        out = r.stdout.strip() if r else ""
        if not r or r.returncode != 0 or not SHA.fullmatch(out):
            raise GitError("git merge-base found no common ancestor")
        return out

    def diff_paths(self, a, b):
        """The paths whose blob or mode differs between two commits. NUL-separated, so git's quoting of unusual names can't
        hide one; a name that isn't valid UTF-8 fails closed."""
        if not (SHA.fullmatch(a) and SHA.fullmatch(b)):
            raise GitError("not a commit id")
        try:
            r = self.run("diff", "--raw", "--no-abbrev", "-z", a, b)
        except UnicodeDecodeError:
            raise GitError("a path in the diff isn't valid UTF-8") from None
        if r.returncode != 0:
            raise GitError("git diff failed")
        parts = r.stdout.split("\0")
        if parts.pop() != "" or len(parts) % 2:
            raise GitError("git diff --raw -z gave a record this broker doesn't recognise")
        paths = set()
        for header, path in zip(parts[0::2], parts[1::2]):  # ":<modes> <blobs> <status>", then one path (no renames)
            if not RAW_HEADER.fullmatch(header) or not path:
                raise GitError("git diff --raw -z gave a record this broker doesn't recognise")
            paths.add(path)
        return paths

    def changed_files(self, left, right):
        r = self.run("diff", "--name-only", f"{left}...{right}")
        if r.returncode != 0:
            raise GitError("git diff failed")
        return r.stdout.split()


class GitView:
    """What a step's host module may do with the broker's clone: read, never write (its directory is read-only to the step
    anyway)."""

    def __init__(self, git):
        self._git = git

    def __getattr__(self, name):
        if name in ("has", "is_ancestor", "content_equal", "blob", "resolve", "parents", "first_parent_after"):
            return getattr(self._git, name)
        raise AttributeError(name)


MAIN_REF, RELEASE_REF = "refs/factory/main", "refs/factory/release-production"


# ---------------------------------------------------------------- GitHub, read-only (root, with the gate job's token)

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class GitHub:
    def __init__(self, repo, token, opener=None, api=GITHUB_API):
        self.repo, self.token, self.api = repo, token, api
        self.opener = opener or urllib.request.build_opener(_NoRedirect)

    def get(self, path, params=None):
        url = f"{self.api}/repos/{self.repo}/{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        out, pages = [], 0
        while url:
            if not url.startswith(f"{self.api}/"):
                raise Refused(f"unexpected API URL {safe(url, 80)}")
            req = urllib.request.Request(url, headers={
                "Authorization": f"Bearer {self.token}", "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28", "User-Agent": USER_AGENT})
            try:
                with self.opener.open(req, timeout=30) as r:
                    body = json.loads(r.read())
                    link = r.headers.get("Link", "")
            except urllib.error.HTTPError as e:
                raise Refused(f"GitHub answered {e.code} for {safe(path, 80)}") from None
            except (urllib.error.URLError, TimeoutError, ValueError, OSError) as e:
                raise Refused(f"GitHub unreachable or unreadable for {safe(path, 80)}: {safe(e, 80)}") from None
            if not isinstance(body, list):
                return body
            out += body
            pages += 1
            m = re.search(r'<([^>]+)>;\s*rel="next"', link)
            url = m.group(1) if m and pages < 50 else None
        return out


def branch_head(gh, cfg):
    quoted = urllib.parse.quote(cfg["release_branch"], safe="")
    b = gh.get(f"branches/{quoted}")
    sha = (b.get("commit") or {}).get("sha", "") if isinstance(b, dict) else ""
    if not isinstance(sha, str) or not SHA.fullmatch(sha) or b.get("name") != cfg["release_branch"]:
        raise Refused(f"can't read {cfg['release_branch']}'s head from GitHub")
    return sha


class PreRunBudget:
    """A deadline for the checks before a release gate runs anything, checked between calls. Past it the gate is refused:
    nothing has run, so asking again is safe."""

    def __init__(self, seconds, clock=time):
        self.seconds, self.clock = seconds, clock
        self.restart()

    def restart(self):
        """A new window: the fetch of the release branch, which has its own bound, doesn't spend the one after it."""
        self.end = self.clock.monotonic() + self.seconds

    def check(self, doing):
        if self.clock.monotonic() > self.end:
            raise Refused(f"the release gate's checks ran past {self.seconds} s ({doing}); nothing has run, so add "
                          f"factory:gate-retry to ask again")


def pinned_release_problem(cfg, gh, release_pr, pinned):
    """Why a merged PR into the release branch isn't a release gate's release PR for the commit it brought in (`pinned`), or None.
    A release gate's pinned commit is on the execution PR's branch, not on main yet, so (2) of provenance can't be met by
    ancestry: the name, author and head of the PR stand in for it. The pinned branch can't move (a ruleset), so what GitHub
    records for the PR now is what it was merged at. The gate id in the name can't be checked here: it belongs to a plan."""
    head = release_pr.get("head") or {}
    m = PIN.fullmatch(head.get("ref") or "")
    if not m:
        return "its PR is not from a factory/release/ pinned branch"
    if (release_pr.get("user") or {}).get("id") != cfg["app_bot_id"]:
        return "its release PR is not the factory App's"
    if (head.get("repo") or {}).get("full_name") != cfg["repo"]:
        return "its release PR is not from this repository"
    if head.get("sha") != pinned or m.group(3) != pinned[:12]:
        return "the pinned branch's name and head are not the commit it brought in"
    execution = gh.get(f"pulls/{int(m.group(1))}")
    if not isinstance(execution, dict) or not BRANCH.fullmatch((execution.get("head") or {}).get("ref") or "") \
            or (execution.get("user") or {}).get("id") != cfg["app_bot_id"] \
            or ((execution.get("head") or {}).get("repo") or {}).get("full_name") != cfg["repo"]:
        return f"the pinned branch names PR #{m.group(1)}, which is not a factory execution PR"
    return None


def provenance_failures(cfg, gh, git, base, head, budget=None):
    """[(sha, reason)] for every first-parent commit after `base` up to `head` that is not (1) the merge commit of a PR merged
    into the release branch by an approver, and (2) a merge whose second parent, the branch it brought in, is already in main
    or is a release gate's pinned commit (the head of a release PR the App opened from a factory/release/ branch, D4 rule 13).
    Who merged says nothing about what was merged: without (2) an approver's merge button could ship a branch nobody put
    through main's review. A hotfix that skips main needs `baseline --advance-release-head` and an `accept <sha>`.
    Raises Refused when `base` isn't an ancestor of `head` (the branch was rewritten)."""
    if not git.is_ancestor(base, head):
        raise Refused(f"the last recorded release head {base[:12]} isn't an ancestor of {head[:12]}: the branch was rewritten")
    main = git.main_sha()
    fails = []
    for sha in git.first_parent_after(base, head):
        if budget:
            budget.check(f"provenance of {sha[:12]}")
        reason, matched = "no merged PR has this commit as its merge commit", None
        for pr in gh.get(f"commits/{sha}/pulls"):
            if not isinstance(pr, dict) or pr.get("merge_commit_sha") != sha:
                continue
            full = gh.get(f"pulls/{pr.get('number')}")
            if not isinstance(full, dict) or not full.get("merged") or full.get("merge_commit_sha") != sha \
                    or (full.get("base") or {}).get("ref") != cfg["release_branch"]:
                continue
            if (full.get("merged_by") or {}).get("id") not in cfg["approvers"]:
                reason = "its PR was merged by someone who isn't an approver"
                continue
            reason, matched = None, full
            break
        if reason is None:
            parents = git.parents(sha)
            if len(parents) != 2:
                reason = "it is not a merge commit"
            elif not git.is_ancestor(parents[1], main):
                reason = "it merged a branch that is not in main"
                if PIN.fullmatch((matched.get("head") or {}).get("ref") or ""):
                    problem = pinned_release_problem(cfg, gh, matched, parents[1])
                    if budget:
                        budget.check(f"provenance of {sha[:12]}")
                    reason = None if problem is None else f"{reason}, and not a release gate's pinned commit ({problem})"
        if reason:
            fails.append((sha, reason))
    return fails


def fetch_refs(cfg, git, ssh_key=None):
    """Fetch the release branch and main into the broker's clone with the read-only deploy key: the one code path the
    `fetch` command, `baseline` and the daily drift check share. Returns {branch: sha}."""
    git.fetch(cfg["repo"], f"+refs/heads/{cfg['release_branch']}:{RELEASE_REF}",
              f"+refs/heads/{cfg['default_branch']}:{MAIN_REF}", ssh_key=str(ssh_key or DEPLOY_KEY))
    got = {}
    for branch, ref in ((cfg["release_branch"], RELEASE_REF), (cfg["default_branch"], MAIN_REF)):
        got[branch] = git.resolve(git.run("rev-parse", ref).stdout.strip())
    return got


def cmd_fetch(cfg, git, console, lock_wait_s=60, package=None):
    with broker_lock(lock_wait_s, package=package):
        return fetch_locked(cfg, git, console)


def fetch_locked(cfg, git, console):
    try:
        got = fetch_refs(cfg, git)
    except GitError as e:
        console.say(f"fetch failed: {e}")
        return 1
    for branch, sha in got.items():
        console.say(f"{branch} {sha}")
    return 0


def fetch_release(cfg, git, token=None, ssh_key=None):
    """The release branch and main (the provenance check compares the one against the other)."""
    git.fetch(cfg["repo"], f"+refs/heads/{cfg['release_branch']}:{RELEASE_REF}",
              f"+refs/heads/{cfg['default_branch']}:{MAIN_REF}", token=token, ssh_key=ssh_key)


# ---------------------------------------------------------------- the ledger and recorded state

class LedgerBroken(Refused):
    """A ledger line that doesn't parse and isn't a torn last line: every command refuses until CD looks at it by hand."""


class Entries(list):
    """The ledger's entries, and `torn`: the bytes of a last line cut off mid-write (no newline, doesn't parse), or None."""

    torn = None


TORN_HINT = "check production, then run `sudo {cmd} resolve --torn-line <note>`, and resolve any run it leaves unfinished"


def parsed_line(raw):
    """One ledger line as its entry, or None when it isn't a JSON object."""
    try:
        entry = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError, RecursionError):
        return None
    return entry if isinstance(entry, dict) else None


def ledger_entries(path):
    """Every entry, in order. A last line with no newline that doesn't parse is a write the broker didn't finish (it was
    killed mid-append): it is set aside as `torn`, never read, and every gate refuses until CD resolves it. Any other line
    that doesn't parse raises LedgerBroken."""
    out = Entries()
    try:
        data = pathlib.Path(path).read_bytes()
    except FileNotFoundError:
        return out
    lines = data.split(b"\n")
    tail = lines.pop()  # what follows the last newline: nothing, in a ledger whose writes all finished
    for n, raw in enumerate(lines, 1):
        if raw.strip():
            entry = parsed_line(raw)
            if entry is None:
                raise LedgerBroken(f"line {n} of the ledger {path} doesn't parse: it isn't the last line, so it isn't a write cut "
                                   f"off by a crash. Nothing runs until CD repairs the ledger by hand")
            out.append(entry)
    if tail.strip():
        entry = parsed_line(tail)
        if entry is None:
            out.torn = tail
        else:
            out.append(entry)  # a whole entry that lost only its newline; ledger_append writes that newline first
    return out


def torn_problem(entries):
    """What a torn last line means, for a refusal, `check` and the drift line; None without one."""
    torn = getattr(entries, "torn", None)
    if torn is None:
        return None
    return (f"the ledger's last line was cut off mid-write ({len(torn)} bytes, no newline: the broker was stopped while it "
            f"wrote), so the run it belonged to is unknown: " + TORN_HINT.format(cmd=USER_AGENT))


def ledger_append(path, entry):
    """Append one entry and fsync it (and the directory, when this creates the file). Refuses after a torn last line: the new
    line would run into it and make a line in the middle that doesn't parse. `resolve --torn-line` sets that line aside."""
    p = pathlib.Path(path)
    p.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    created = False
    try:
        fd = os.open(p, os.O_RDWR | os.O_APPEND | os.O_NOFOLLOW)
    except FileNotFoundError:
        fd = os.open(p, os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        created = True
    with os.fdopen(fd, "r+b") as f:
        size, prefix = os.fstat(fd).st_size, b""
        if size and os.pread(fd, 1, size - 1) != b"\n":
            chunk = os.pread(fd, min(size, READ_LIMIT * 16), max(0, size - READ_LIMIT * 16))
            cut = chunk.rfind(b"\n")
            if (cut < 0 and size > len(chunk)) or parsed_line(chunk[cut + 1:]) is None:
                raise Refused("can't append to the ledger: its last line was cut off mid-write; " + TORN_HINT.format(cmd=USER_AGENT))
            prefix = b"\n"
        f.write(prefix + json.dumps(entry, sort_keys=True).encode() + b"\n")
        f.flush()
        os.fsync(f.fileno())
    if created:
        fsync_dir(p.parent)


def fsync_dir(path):
    dfd = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(dfd)
    finally:
        os.close(dfd)


def runs(entries):
    out = {}
    for e in entries:
        if e.get("event") in ("start", "finish"):
            r = out.setdefault(e["run"], {"start": None, "finish": None})
            r[e["event"]] = e
    return out


def unfinished(entries):
    return [run for run, r in runs(entries).items() if r["start"] and not r["finish"]]


def done_runs(entries, repo, pr):
    out = {}
    for r in runs(entries).values():
        f = r["finish"]
        if f and f.get("repo") == repo and f.get("pr") == pr and f.get("status") == "done":
            out[f["gate"]] = f
    return out


def done_outputs(entries, repo, pr):
    return {g: f.get("outputs", {}) for g, f in done_runs(entries, repo, pr).items()}


def stored_receipt(entries, digest):
    for r in runs(entries).values():
        if r["finish"] and r["finish"].get("digest") == digest and r["finish"].get("signed"):
            return r["finish"]["signed"]
    return None


def to_state(deployed):
    """A signed record's deployed_state as {release_head, recorded}, or None when it has neither shape. The new shape is
    {release_head, recorded: {output: value}}. A ledger written before the generic broker records {fingerprints: {name:
    hash}, fp_key_id, seen: {release_head, <service>: commit or null}}: fingerprints.<name> was output fp_<name>, fp_key_id
    stays fp_key_id, and the serving commits in `seen` are dropped (nothing reads them). Only root writes signed records, so
    a record that maps but doesn't match the block can only come from a broker or catalog change: state_problem says so."""
    if not isinstance(deployed, dict):
        return None
    if set(deployed) == {"release_head", "recorded"}:
        head, rec = deployed["release_head"], deployed["recorded"]
    elif set(deployed) == {"fingerprints", "fp_key_id", "seen"}:
        fps, seen = deployed["fingerprints"], deployed["seen"]
        if not isinstance(fps, dict) or not isinstance(seen, dict) or "key_id" in fps:  # fp_ + key_id would collide
            return None
        if any(k != "release_head" and v is not None and not (isinstance(v, str) and SHA.fullmatch(v)) for k, v in seen.items()):
            return None
        head = seen.get("release_head")
        rec = {**{"fp_" + str(n): v for n, v in fps.items()}, "fp_key_id": deployed["fp_key_id"]}
    else:
        return None
    if not (isinstance(head, str) and SHA.fullmatch(head)) or not isinstance(rec, dict) \
            or not all(isinstance(k, str) and FIELD.fullmatch(k) and isinstance(v, str) for k, v in rec.items()):
        return None
    return {"release_head": head, "recorded": dict(rec)}


def verified(gates, public, signed, kind):
    try:
        receipt = gates.verify_receipt(public, signed)
    except (gates.Invalid, AttributeError, TypeError):
        return None
    return receipt if receipt.get("kind") == kind else None


def recorded_state(entries, gates, public):
    """The record: the latest deployed state, from a baseline or the state a gate recorded after it ran (bound to that
    run), each carrying a signature that verifies with the broker's key, in either shape (to_state). An unsigned or wrongly
    signed line is ignored, so a forged or edited ledger line can't reset what gates expect (a rotated key makes every older
    record unverifiable: `check` lists them). Whether it matches the block is state_problem's question: baseline takes the
    record's release head even when it doesn't, so a catalog change costs one baseline, not the provenance base."""
    state = None
    for e in entries:
        candidate = None
        if e.get("event") == "baseline":
            receipt = verified(gates, public, e.get("signed"), "baseline")
            candidate = receipt.get("deployed_state") if receipt else None
        elif e.get("event") == "finish":
            receipt = verified(gates, public, e.get("state_signed"), "state")
            candidate = receipt.get("deployed_state") if receipt and receipt.get("run") == e.get("run") else None
        mapped = to_state(candidate)
        if mapped is not None:
            state = mapped
    return state


def state_problem(state, catalog):
    """Why the record can't be what gates compare against now, or None: its recorded outputs must be exactly the block's,
    each matching its capture-state pattern."""
    block, patterns = catalog["broker"], catalog["operations"]["capture-state"].get("outputs", {})
    want, have = set(block["recorded"]), set(state["recorded"])
    if want != have:
        added, dropped = sorted(want - have), sorted(have - want)
        parts = ([f"added {', '.join(added)}"] if added else []) + ([f"dropped {', '.join(map(safe, dropped))}"] if dropped else [])
        return f"the recorded outputs changed since the last record ({'; '.join(parts)}): CD runs `baseline`"
    bad = [n for n in block["recorded"] if not accepts(patterns.get(n), state["recorded"][n])]
    if bad:
        return f"the last record's {', '.join(bad)} don't match capture-state's patterns now: CD runs `baseline`"
    return None


def unverified_records(entries, gates, public):
    """[(event, run)] for baselines and recorded gate states whose signature doesn't verify."""
    bad = []
    for e in entries:
        if e.get("event") == "baseline" and verified(gates, public, e.get("signed"), "baseline") is None:
            bad.append(("baseline", e.get("run")))
        elif e.get("event") == "finish" and (e.get("state_signed") is not None or e.get("deployed_state") is not None) \
                and verified(gates, public, e.get("state_signed"), "state") is None:
            bad.append(("finish", e.get("run")))
    return bad


def baseline_times(entries, gates, public):
    """When each verified baseline was recorded, whatever its state's shape."""
    out = []
    for e in entries:
        if e.get("event") == "baseline":
            receipt = verified(gates, public, e.get("signed"), "baseline")
            try:
                out.append(parse_ts(receipt["at"]))
            except (StepFailed, KeyError, TypeError):
                continue
    return out


def state_from(out, release_head, block):
    return {"release_head": release_head, "recorded": {n: out[n] for n in block["recorded"]}}


# ---------------------------------------------------------------- the check before every gate (D4 rule 7)

def invariant_problems(block, out):
    """Each declared invariant capture-state's outputs break, in declared order: what it found, what it needed, the
    outputs it shows, and why."""
    problems = []
    for name, rule in block.get("invariants", {}).items():
        value = out.get(name)
        if ("is" in rule and value == rule["is"]) or ("in" in rule and value in rule["in"]):
            continue
        expected = repr(rule["is"]) if "is" in rule else "one of " + ", ".join(repr(v) for v in rule["in"])
        shown = "".join(f" ({s}: {safe(out.get(s), 100)!r})" for s in rule.get("show", []))
        problems.append(f"{name} is {safe(value, 100)!r}, not {expected}{shown}: {rule['why']}")
    return problems


def recorded_moved(block, state, out):
    return [n for n in block["recorded"] if state["recorded"].get(n) != out.get(n)]


def gate_checks(cfg, block, git, state, out, head, skip_serving):
    """Production serves the branch head and is as last recorded, from capture-state's typed outputs. Each checked
    service is settled, serves a commit in the head's history and is content-equal to the head under its patterns;
    `skip_serving` (a gate that opens with release-wait) lifts that for the release services, which the wait covers.
    Then every invariant, and the recorded outputs, refused once with every problem found."""
    names = [s for s in services_of(block, "checked") if not (skip_serving and block["services"][s]["release"])]
    for name in names:
        if out.get(f"{name}_settled") != "yes":
            raise Refused(f"{name}: a release is deploying: wait, or use a release-wait gate")
    for name in names:
        commit = out.get(f"{name}_commit")
        if not commit or not git.is_ancestor(commit, head):
            raise Refused(f"{name}: production runs a commit that isn't on {cfg['release_branch']}")
        try:
            equal = git.content_equal(commit, head, block["services"][name]["patterns"])
        except GitError as e:
            raise Refused(f"{name}: can't compare its commit with the branch head: {e}") from None
        if not equal:
            raise Refused(f"{name}: production isn't serving {cfg['release_branch']}'s head: the last release failed, "
                          f"or someone deployed outside the branch")
    problems = invariant_problems(block, out)
    moved = recorded_moved(block, state, out)
    if moved:
        problems.append(f"settings changed outside a release ({', '.join(moved)}): CD records them with `baseline`")
    if problems:
        raise Refused("; ".join(problems))


def pregate(cfg, block, gh, git, state, run_capture, ops, token, release_check=None, budget=None, wait="release-wait"):
    """Checks before a gate runs anything. Returns (head, capture outputs, notes). `run_capture(head)` runs capture-state
    sandboxed. A release gate's `release_check(head)` runs once the branch is fetched and before provenance, so its reasons
    are the specific ones."""
    if wait in ops and ops[0] != wait:
        raise Refused(f"{wait} must be the first step of its gate: it lifts the serving check for the steps after it only")
    head = branch_head(gh, cfg)
    if budget:
        budget.check("reading the release branch")
    try:
        fetch_release(cfg, git, token=token)
    except GitError as e:
        raise Refused(f"can't fetch {cfg['release_branch']}: {e}") from None
    if not git.has(head):
        raise Refused(f"the broker's clone doesn't have {head[:12]} after fetching")
    if budget:
        budget.restart()
    if release_check:
        try:
            release_check(head)
        except GitError as e:
            raise Refused(f"can't check the release against {cfg['release_branch']}: {e}") from None
    try:
        fails = provenance_failures(cfg, gh, git, state["release_head"], head, budget=budget)
    except GitError as e:
        raise Refused(f"can't check provenance: {e}") from None
    if fails:
        raise Refused(f"release without a PR: {fails[0][0]} ({fails[0][1]})")
    out, notes = run_capture(head)
    gate_checks(cfg, block, git, state, out, head, skip_serving=wait in ops)
    return head, out, notes


# ---------------------------------------------------------------- a step (`op <name>`, as the operator, in the sandbox)

class Clock:
    def monotonic(self):
        return time.monotonic()

    def sleep(self, seconds):
        time.sleep(seconds)

    def now(self):
        return datetime.datetime.now(datetime.timezone.utc)


class Ctx:
    """What a step's code is given (process/factory-broker.md § The host module). Everything but `client` is read-only."""

    def __init__(self, op, params, config, catalog, release_head, run, git, clock, deadline, secrets, egress, connect):
        self.op, self.params = op, types.MappingProxyType(dict(params))
        self.config = frozen(config)
        self.host = self.config["host"]
        self.broker = frozen(catalog["broker"])
        self.services = self.broker["services"]
        self.release_head, self.run, self.git, self.clock, self.deadline = release_head, run, git, clock, deadline
        self.client = None
        self._secrets, self._egress, self._connect = dict(secrets), frozenset(egress), connect
        self.notes, self.rows = [], None

    def secret(self, label):
        if label not in self._secrets:
            raise StepFailed(f"this step isn't given the secret {safe(label, 20)} (broker.op_secrets)")
        return self._secrets[label]

    def has_secret(self, label):
        return label in self._secrets

    def connect(self, host, timeout):
        """The raw egress connection, for a client that needs its own transport."""
        if host not in self._egress:
            raise HostError("host isn't one of the egress hosts this broker may reach")
        return self._connect(host, timeout)

    def https(self, host, method, path, headers, body=None, *, max_bytes, timeout=None):
        """One request through the egress proxy: (status, {lower-case name: value}, body). Refuses a host outside
        broker.egress, a relative path, a redirect and a body over max_bytes; its timeout is at most the deadline's."""
        left = self.deadline.left()
        if left <= 0:
            raise StepFailed("the operation's deadline passed")
        if not is_int(max_bytes, 0, MAX_RESPONSE):
            raise HostError(f"max_bytes must be at most {MAX_RESPONSE}")
        wait = min(REQUEST_TIMEOUT_S if timeout is None else timeout, left)
        return http_exchange(self._connect, self._egress, host, method, path, dict(headers), body, max(0.1, wait), max_bytes)

    def note(self, text):
        """A display line: root keeps at most 50, printable, at most 300 characters, prints them, and never decides on them."""
        if len(self.notes) < MAX_NOTES:
            self.notes.append(safe(text, NOTE_LIMIT))


def host_import_problems(text):
    """What the host module imports from this one beyond HOST_API (the contract's names, kept stable across releases)."""
    try:
        tree = ast.parse(text)
    except SyntaxError as e:
        return [f"it doesn't parse (line {e.lineno})"]
    bad = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            bad += [f"import {a.name}" for a in node.names if a.name.split(".")[0] in ("factory_op", "__main__")]
        elif isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] in ("factory_op", "__main__"):
            bad += [f"from {node.module} import {a.name}" for a in node.names if a.name not in HOST_API]
    return bad


def host_interface_problems(module, block):
    problems = [f"{name} is missing or not callable" for name in PRIMITIVES if not callable(getattr(module, name, None))]
    ops, diagnostics = getattr(module, "OPS", None), getattr(module, "DIAGNOSTICS", {})
    generic = set(GENERIC_OPS) | set(GENERIC_INTERNAL)
    if not isinstance(ops, dict) or not all(isinstance(k, str) and callable(v) for k, v in ops.items()):
        problems.append("OPS must be a dict of callables")
        ops = {}
    elif set(ops) != set(block["host_ops"]):
        problems.append(f"OPS must be exactly broker.host_ops ({', '.join(block['host_ops']) or 'none'})")
    if not isinstance(diagnostics, dict) or not all(isinstance(k, str) and callable(v) for k, v in diagnostics.items()):
        problems.append("DIAGNOSTICS must be a dict of callables")
        diagnostics = {}
    elif set(diagnostics) - set(block["internal_ops"]):
        problems.append("DIAGNOSTICS must be operations broker.internal_ops declares")
    if (set(ops) | set(diagnostics)) & generic:
        problems.append("OPS and DIAGNOSTICS can't name a generic operation")
    return problems


def load_host(path, block):
    """The host module, loaded from its path, never through sys.path, and checked against the contract. Raises
    StepFailed. Only op_main calls it, after refusing to run as root."""
    path = pathlib.Path(path)
    try:
        text = path.read_text()
    except (OSError, UnicodeDecodeError):
        raise StepFailed(f"the host module ({HOST_MODULE}) can't be read") from None
    bad = host_import_problems(text)
    if bad:
        raise StepFailed(f"the host module imports what isn't in factory_op.HOST_API: {safe(', '.join(bad[:3]), 150)}")
    # The module's `from factory_op import ...` must get this module's own classes, so its StepFailed is ours.
    sys.modules.setdefault("factory_op", sys.modules[__name__])
    spec = importlib.util.spec_from_file_location("factory_op_host", str(path))
    if spec is None or spec.loader is None:
        raise StepFailed("the host module can't be loaded")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except (Exception, SystemExit) as e:
        raise StepFailed(f"the host module failed to load: {type(e).__name__}: {safe(e, 100)}") from None
    problems = host_interface_problems(module, block)
    if problems:
        raise StepFailed("the host module doesn't meet the contract: " + "; ".join(problems[:3]))
    return module


# What the broker checks of every answer the host module gives (it is the project's code; root trusts only the typed
# outputs it filters itself, but a well-formed answer keeps a broken module from passing by accident).
DEP_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}$")


def aware(value):
    return isinstance(value, datetime.datetime) and value.utcoffset() is not None


def checked_deployment(dep, svc, what):
    if not isinstance(dep, Deployment):
        raise StepFailed(f"{svc}: the host module's {what} didn't give a Deployment")
    if not isinstance(dep.id, str) or not DEP_ID.fullmatch(dep.id):
        raise StepFailed(f"{svc}: a deployment id from {what} isn't plain text of up to 64 characters")
    if dep.commit is not None and not (isinstance(dep.commit, str) and SHA.fullmatch(dep.commit)):
        raise StepFailed(f"{svc}: a deployment's commit from {what} isn't a commit id")
    if dep.status not in STATUSES:
        raise StepFailed(f"{svc}: a deployment's status from {what} isn't one of {', '.join(STATUSES)}")
    if dep.created is not None and not aware(dep.created):
        raise StepFailed(f"{svc}: a deployment's time from {what} isn't an aware datetime")
    if dep.branch is not None and not (isinstance(dep.branch, str) and len(dep.branch) <= 100 and PRINTABLE.fullmatch(dep.branch)):
        raise StepFailed(f"{svc}: a deployment's branch from {what} isn't printable text")
    return dep


def newest_first(deps):
    """By time, newest first, a deployment with no usable time last: the host's order isn't trusted."""
    return sorted(deps, key=lambda d: (d.created is None, -d.created.timestamp() if d.created else 0.0))


def host_deployments(ctx, host, svc):
    deps = host.deployments(ctx, svc)
    if not isinstance(deps, list) or len(deps) > MAX_ROWS:
        raise StepFailed(f"{svc}: deployments must be a list of at most {MAX_ROWS}")
    return newest_first([checked_deployment(d, svc, "deployments") for d in deps])


def host_serving(ctx, host, svc):
    dep = host.serving(ctx, svc)
    if dep is None:
        return None
    dep = checked_deployment(dep, svc, "serving")
    if dep.status != "success":
        raise StepFailed(f"{svc}: serving gave a deployment that isn't successful")
    return dep


def host_latest(ctx, host):
    got = host.latest(ctx)
    if not isinstance(got, dict) or set(got) - set(ctx.services) or any(v is not None and v not in STATUSES for v in got.values()):
        raise StepFailed(f"latest must map declared services to one of {', '.join(STATUSES)} or None")
    return {svc: got.get(svc) for svc in ctx.services}


def host_reports(ctx, host, svc, deployment_id):
    got = host.reports(ctx, svc, deployment_id)
    if type(got) is not bool:
        raise StepFailed(f"{svc}: reports must answer True or False")
    return got


def host_heartbeat(ctx, host, svc, deployment_id, patient):
    got = host.heartbeat(ctx, svc, deployment_id, patient)
    if got is not None and not (isinstance(got, tuple) and len(got) == 2 and all(aware(t) for t in got)):
        raise StepFailed(f"{svc}: heartbeat must answer None or (started, written), two aware datetimes")
    return got


def typed_outputs(out, what):
    if not isinstance(out, dict) or not all(isinstance(k, str) and FIELD.fullmatch(k) and isinstance(v, str) and len(v) <= 1000
                                            and PRINTABLE.fullmatch(v) for k, v in out.items()):
        raise StepFailed(f"{what} must return {{field: one line of printable text}}")
    return dict(out)


def reports_evidence(ctx, host, svc, dep_id, patient):
    """The service reports the deployment it should. Patient: an old replica may still answer during the overlap, so keep
    reading until the deadline."""
    while True:
        try:
            if host_reports(ctx, host, svc, dep_id):
                return
            if not patient:
                raise StepFailed(f"{svc} doesn't report deployment {dep_id[:12]} (or isn't ready)")
        except Unavailable:
            if not patient:
                raise
        ctx.deadline.check()
        pause(ctx, POLL_S)


def pause(ctx, seconds):
    """A poll's wait, never past the step's own deadline: the next read is the last, and the deadline check after it fails
    the step before the broker would kill it."""
    ctx.clock.sleep(max(0.0, min(seconds, ctx.deadline.left())))


def heartbeat_evidence(ctx, host, svc, dep, patient):
    """D4 rule 15: two reads more than one heartbeat time-to-live apart, both this deployment's, with the same start, the
    write newer than the deployment and still moving. Strict (health): the first two reads must be good. Patient
    (release-wait): reads that aren't this deployment's yet are skipped."""
    if dep.created is None:
        raise StepFailed(f"{svc}: the deployment has no usable time, so its heartbeat can't be dated against it")
    ttl = ctx.broker["heartbeat_ttl_s"]
    first = None
    while True:
        try:
            read = host_heartbeat(ctx, host, svc, dep.id, patient)
        except Unavailable:
            if not patient:
                raise
            read = None
        if read is not None and not read[1] > dep.created:
            read = None  # written before this deployment began: not its heartbeat
        at = ctx.clock.monotonic()
        if read is None:
            if not patient:
                raise StepFailed(f"{svc}: the heartbeat is missing or isn't this deployment's")
        elif first is None or read[0] != first[0]:
            if first is not None and not patient:
                raise StepFailed(f"{svc} restarted between reads")
            first = (read[0], read[1], at)
        elif at - first[2] > ttl:
            if read[1] > first[1]:
                return
            if not patient:
                raise StepFailed(f"{svc}: the heartbeat isn't advancing")
        ctx.deadline.check()
        # The step fails itself rather than sleep past its own deadline: the broker would kill it there, leaving a timed-out
        # run that blocks every gate until CD resolves it, for what is only a failed read.
        pause = ttl + 1 if (first is not None and not patient) else POLL_S
        if pause >= ctx.deadline.left():
            raise StepFailed(f"{svc}: the heartbeat's next read, {pause} s away, would pass the operation's deadline"
                             + ("" if patient else " (health's timeout_s must cover heartbeat_ttl_s for each heartbeat service)"))
        ctx.clock.sleep(pause)


def evidence(ctx, host, svc, dep, patient):
    kind = ctx.services[svc]["evidence"]
    if kind in ("reports", "both"):
        reports_evidence(ctx, host, svc, dep.id, patient)
    if kind in ("heartbeat", "both"):
        heartbeat_evidence(ctx, host, svc, dep, patient)


def release_services(ctx):
    return [s for s, d in ctx.services.items() if d["release"]]


def op_health(ctx, host):
    """Every declared service serves a successful deployment that isn't crashed, and each release service proves it runs
    that deployment (strict evidence). The host's status is read again at the end: a service can crash after the wait."""
    services, release = list(ctx.services), release_services(ctx)
    bad, found, reasons = set(), {}, []
    latest = host_latest(ctx, host)
    for svc in services:
        dep = host_serving(ctx, host, svc)
        if dep is None or latest[svc] == "crashed":
            bad.add(svc)
        else:
            found[svc] = dep
    for svc in release:  # still the one serving: a re-read, as cheap as asking for the deployment by id
        if svc in found:
            again = host_serving(ctx, host, svc)
            if again is None or again.id != found[svc].id:
                bad.add(svc)
    out = {"services": str(len(services))}
    if not bad:
        for svc in release:
            try:
                evidence(ctx, host, svc, found[svc], patient=False)
            except StepFailed as e:
                reasons.append(f"{svc}: {safe(e)}")
                bad.add(svc)
        end = host_latest(ctx, host)
        bad |= {svc for svc in release if end[svc] == "crashed"}
    names = [svc for svc in services if svc in bad]
    out.update({"healthy": "no" if names else "yes", "unhealthy": ",".join(names)})
    if names:
        raise StepFailed(f"unhealthy: {','.join(names)}" + "".join(f"; {r}" for r in reasons), out)
    out.update({f"{svc}_deployment": found[svc].id for svc in release})
    return out


def op_release_wait(ctx, host):
    """Wait for the release containing `sha` to be live, with D4 rule 15's evidence. For each release service: its
    deployment of the branch head succeeds (then its evidence, patiently), or it has none and what it serves is in the
    head's history and content-equal to it (the host skipped it), within grace_s; a crashed or failed one fails. At the end,
    each deployment waited for must still be the one serving."""
    git, sha, head = ctx.git, ctx.params["sha"], ctx.release_head
    if not SHA.fullmatch(sha) or not SHA.fullmatch(head):
        raise StepFailed("sha or the branch head isn't a commit id")
    if not git.is_ancestor(sha, head):
        raise StepFailed("release PR not merged yet: the commit isn't in the release branch's history")
    grace, release = ctx.broker["release_wait_phases"]["grace_s"], release_services(ctx)
    start = ctx.clock.monotonic()
    done, waiting, deployed, deps = {}, list(release), [], {}
    while waiting:
        for svc in list(waiting):
            recent = host_deployments(ctx, host, svc)
            mine = [d for d in recent if d.commit == head]
            status = mine[0].status if mine else None
            if status == "success":
                done[svc], deps[svc] = mine[0].id, mine[0]
                deployed.append(svc)
                waiting.remove(svc)
            elif status == "waiting":
                continue
            elif status in (None, "skipped"):
                # No build of the head: fine only if what serves has the head's content (a host skips a service the merge
                # didn't touch, and may not have created the row yet).
                newest = recent[0].status if recent else None
                if newest == "crashed":
                    raise StepFailed(f"{svc}: its newest deployment crashed")
                if newest == "waiting":  # a deploy is in progress: not done, and not yet a reason to fail
                    if ctx.clock.monotonic() - start > grace:
                        raise StepFailed(f"no deployment created for {svc} at {head[:12]}")
                    continue
                node = host_serving(ctx, host, svc)
                commit = node.commit if node else None
                # Content-equal only counts if what serves is part of the branch's history, not a look-alike elsewhere.
                if commit and git.is_ancestor(commit, head) and git.content_equal(commit, head, ctx.services[svc]["patterns"]):
                    done[svc] = node.id
                    waiting.remove(svc)
                elif status == "skipped":
                    raise StepFailed(f"{svc}: the host skipped the deployment but the content differs from the head")
                elif ctx.clock.monotonic() - start > grace:
                    raise StepFailed(f"no deployment created for {svc} at {head[:12]}")
            else:
                raise StepFailed(f"{svc}: its deployment of {head[:12]} {status}")
        if waiting:
            ctx.deadline.check()
            pause(ctx, POLL_S)
    for svc in deployed:
        evidence(ctx, host, svc, deps[svc], patient=True)
    for svc in deployed:
        node = host_serving(ctx, host, svc)
        if not node or node.id != done[svc]:
            raise StepFailed(f"{svc}: the deployment isn't successful and serving at the end of the wait")
    return {"head": head, "deployed": ",".join(s for s in release if s in deployed),
            **{f"{s}_deployment": done[s] for s in release}}


def op_http_check(ctx, host):
    target, path, expect = ctx.params["target"], ctx.params["path"], ctx.params["expect_status"]
    targets = ctx.broker.get("http_targets", {})
    if target not in targets or not re.fullmatch(r"^/[a-z0-9_./-]{0,80}$", path) or ".." in path \
            or not re.fullmatch(r"^[1-5][0-9]{2}$", expect):
        raise StepFailed("a parameter doesn't match its pattern")
    t0 = ctx.clock.monotonic()
    try:
        status, _, data = ctx.https(targets[target], "GET", path, {"Accept": "*/*", "User-Agent": USER_AGENT}, None,
                                    max_bytes=MAX_APP_BODY, timeout=max(1.0, min(REQUEST_TIMEOUT_S, ctx.deadline.left())))
    except (HostError, *NETWORK_ERRORS) as e:
        raise StepFailed(f"the request failed: {safe(e, 100)}") from None
    out = {"status": str(status), "latency_ms": str(min(999999, int((ctx.clock.monotonic() - t0) * 1000))),
           "body_sha256": hashlib.sha256(data).hexdigest()}
    if status != int(expect):
        raise StepFailed(f"status {status}, expected {expect}", out)
    return out


def op_capture_state(ctx, host):
    """The host's capture, with the outputs root needs present and shaped: <svc>_commit and <svc>_settled for each checked
    service, and every recorded, invariant and shown output. Root then keeps only what the catalog's patterns allow."""
    if not SHA.fullmatch(ctx.release_head or ""):
        raise StepFailed("capture-state needs the release branch's head")
    out = typed_outputs(host.capture(ctx), "capture")
    block = ctx.broker
    checked = [s for s, d in ctx.services.items() if d["checked"]]
    need = [f"{s}_{k}" for s in checked for k in ("commit", "settled")] + list(block["recorded"])
    for name, rule in block.get("invariants", {}).items():
        need += [name, *rule.get("show", ())]
    missing = [n for n in dict.fromkeys(need) if n not in out]
    if missing:
        raise StepFailed(f"capture didn't give {', '.join(missing[:8])}")
    for svc in checked:
        commit = out[f"{svc}_commit"]
        if not (SHA.fullmatch(commit) or (commit == "" and not ctx.services[svc]["release"])):
            raise StepFailed(f"{svc}_commit must be a commit id" + ("" if ctx.services[svc]["release"] else ", or empty"))
        if out[f"{svc}_settled"] not in ("yes", "no"):
            raise StepFailed(f"{svc}_settled must be yes or no")
    return out


def op_drift_scan(ctx, host):
    """Every declared service's recent deployments, for the daily drift check's rows (read by the broker, never a plan)."""
    cutoff = ctx.clock.now() - datetime.timedelta(seconds=DRIFT_WINDOW_S + 3600)
    rows = {}
    for svc in ctx.services:
        rows[svc] = [{"id": d.id, "commit": d.commit, "branch": d.branch,
                      "created": d.created.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if d.created else None}
                     for d in host_deployments(ctx, host, svc) if d.created is None or d.created >= cutoff]
    ctx.rows = rows
    return {}


def op_host_check(ctx, host):
    """The module loaded and met the contract, and preflight passed: nothing more to do (`diagnose host-check`)."""
    return {}


GENERIC = {"release-wait": op_release_wait, "health": op_health, "http-check": op_http_check,
           "capture-state": op_capture_state, "drift-scan": op_drift_scan, "host-check": op_host_check}
# The steps that read the release branch's head; the others are run with none (health and diagnostics, outside a gate).
NEEDS_HEAD = ("release-wait", "capture-state", "drift-scan")


def read_secrets(step_dir, block, name):
    """The secrets root installed for this step, checked: hex ones as bytes (at least 16), the rest as stripped text
    matching their pattern (or a token's shape)."""
    out = {}
    for label in block["op_secrets"].get(name, []):
        spec = block["secrets"][label]
        text = (read_text_limited(pathlib.Path(step_dir) / f"secret-{label}", 8192) or "").strip()
        if spec["hex"]:
            try:
                value = bytes.fromhex(text)
            except ValueError:
                raise StepFailed(f"the {label} secret is unusable") from None
            if len(value) < 16:
                raise StepFailed(f"the {label} secret is too short")
        else:
            if not re.fullmatch(spec.get("pattern", TOKEN.pattern), text):
                raise StepFailed(f"the {label} secret is unusable")
            value = text
        out[label] = value
    return out


class _UnknownOperation(Exception):
    pass


def op_main(name, environ=None, connect=None, clock=None, stderr=None, host_module=None):
    """Runs one operation as the operator user, inside the sandbox: the params and secrets, then the host module (by its
    path), its client, its preflight (but for a host diagnostic), the operation, and the typed outputs to OP_OUT and notes
    and rows to OP_DETAIL. Failure messages go to stderr, one sanitized line. Returns the exit code."""
    stderr = stderr or sys.stderr
    if os.geteuid() == 0:
        print("factory_op.py op refuses to run as root", file=stderr)
        return 2
    environ = os.environ if environ is None else environ
    clock = clock or Clock()
    out, notes, rows = {}, [], None
    try:
        cfg = json.loads(pathlib.Path(environ.get("FACTORY_CONFIG", str(CONFIG))).read_text())
        catalog = json.loads((pathlib.Path(cfg["lib_dir"]) / "ops.json").read_text())
        problems = broker_problems(catalog, lib_scripts(cfg["lib_dir"]))
        if problems:
            raise StepFailed("ops.json isn't usable: " + "; ".join(problems[:3]))
        op = op_of(catalog, name)
        if op is None:
            raise _UnknownOperation()
        block = catalog["broker"]
        params = {k[3:].lower(): v for k, v in environ.items() if k.startswith("OP_") and k not in ("OP_OUT", "OP_DETAIL")}
        declared = op.get("params", {})
        if set(params) != set(declared) or not all(accepts(declared[k], v) for k, v in params.items()):
            raise StepFailed("the step's parameters aren't the operation's")
        secrets = read_secrets(environ["FACTORY_STEP_DIR"], block, name)
        release_head, run = environ.get("FACTORY_RELEASE_HEAD", ""), environ.get("FACTORY_RUN", "")
        if (release_head or name in NEEDS_HEAD) and not SHA.fullmatch(release_head):
            raise StepFailed(f"{name} needs the release branch's head as a commit id")
        if not RUN_ID.fullmatch(run):
            raise StepFailed("the step's run id isn't plain")
        deadline = Deadline(op["timeout_s"] / DEADLINE_MARGIN, clock)
        raw = connect or functools.partial(EgressConnection, allowed=frozenset(block["egress"]))
        git = GitView(Git(environ.get("FACTORY_CLONE") or cfg["clone_dir"]))
        ctx = Ctx(name, params, cfg, catalog, release_head, run, git, clock, deadline, secrets, block["egress"], raw)
        try:
            host = load_host(host_module or LIB / HOST_MODULE, block)
            ctx.client = host.client(ctx)
            diagnostics = getattr(host, "DIAGNOSTICS", {})
            if name in GENERIC:
                host.preflight(ctx)
                out = GENERIC[name](ctx, host)
            elif name in host.OPS:
                host.preflight(ctx)
                out = typed_outputs(host.OPS[name](ctx), name)
            elif name in diagnostics:
                diagnostics[name](ctx)  # no preflight: a diagnostic must run with wrong ids, and fails its own step
                out = {}
            else:
                raise StepFailed(f"the host module has no operation {name}")
        finally:
            notes, rows = ctx.notes, ctx.rows
    except _UnknownOperation:
        print("unknown operation", file=stderr)
        return 2
    except StepFailed as e:
        print(f"FAILED: {safe(e)}", file=stderr)
        out, code = e.outputs, 1
    except (Exception, SystemExit) as e:  # the host module's code: anything it raises fails the step, closed
        print(f"FAILED: {type(e).__name__}: {safe(e, 100)}", file=stderr)
        out, code = {}, 1
    else:
        code = 0
    out = {k: v for k, v in (out if isinstance(out, dict) else {}).items()
           if isinstance(k, str) and FIELD.fullmatch(k) and isinstance(v, str) and PRINTABLE.fullmatch(v)}
    try:
        if environ.get("OP_OUT"):
            pathlib.Path(environ["OP_OUT"]).write_text("".join(f"{k}={v}\n" for k, v in out.items()))
        if environ.get("OP_DETAIL") and (notes or rows is not None):
            pathlib.Path(environ["OP_DETAIL"]).write_text(json.dumps({"notes": notes, "rows": rows}))
    except (OSError, TypeError, ValueError) as e:
        print(f"FAILED: can't write the step's results: {type(e).__name__}", file=stderr)
        code = 1
    return code


# ---------------------------------------------------------------- the egress proxy (runs as the egress user)

SHARED_SPACE = ipaddress.IPv4Network((0x64400000, 10))  # RFC 6598's shared address space (carrier-grade NAT)


def public_v4(text):
    try:
        ip = ipaddress.ip_address(text)
    except ValueError:
        return False
    return (ip.version == 4 and ip.is_global and ip not in SHARED_SPACE
            and not (ip.is_multicast or ip.is_reserved or ip.is_loopback or ip.is_link_local or ip.is_private or ip.is_unspecified))


def sni_of(record):
    """The server name in a TLS ClientHello record, lower-cased, or None."""
    try:
        if record[0] != 0x16 or record[5] != 0x01:
            return None
        p = 9 + 2 + 32
        p += 1 + record[p]
        p += 2 + int.from_bytes(record[p:p + 2], "big")
        p += 1 + record[p]
        end = p + 2 + int.from_bytes(record[p:p + 2], "big")
        p += 2
        while p + 4 <= end:
            kind, size = int.from_bytes(record[p:p + 2], "big"), int.from_bytes(record[p + 2:p + 4], "big")
            p += 4
            if kind == 0:
                if record[p + 2] != 0:
                    return None
                n = int.from_bytes(record[p + 3:p + 5], "big")
                return record[p + 5:p + 5 + n].decode("ascii").lower()
            p += size
    except (IndexError, UnicodeDecodeError):
        return None
    return None


def read_exact(conn, n):
    data = b""
    while len(data) < n:
        chunk = conn.recv(n - len(data))
        if not chunk:
            raise OSError("closed")
        data += chunk
    return data


def pipe(a, b, idle=60, cap=64 << 20):
    up = down = 0
    while up + down < cap:
        ready, _, _ = select.select([a, b], [], [], idle)
        if not ready:
            break
        for s in ready:
            data = s.recv(65536)
            if not data:
                return up, down
            (b if s is a else a).sendall(data)
            if s is a:
                up += len(data)
            else:
                down += len(data)
    return up, down


def egress_serve(conn, allowed=frozenset(), resolver=socket.getaddrinfo, connector=socket.create_connection, log=None, timeout=10):
    """One CONNECT. The host must be one of `allowed` (broker.egress) and the port 443. It resolves once, A records only,
    refuses a non-public address, waits for the TLS ClientHello and requires its SNI to equal the host, then connects to
    exactly the address it checked and copies bytes. Logs host, byte counts and duration, never content."""
    log = log or (lambda line: print(line, file=sys.stderr, flush=True))
    started = time.monotonic()
    host = "?"

    def refuse(reason, code=b"403 Forbidden"):
        log(f"egress refused host={safe(host, 80)} reason={reason}")
        try:
            conn.sendall(b"HTTP/1.1 " + code + b"\r\n\r\n")
        except OSError:
            pass

    try:
        conn.settimeout(timeout)
        head = b""
        while b"\r\n\r\n" not in head and len(head) < 2048:
            chunk = conn.recv(512)
            if not chunk:
                return refuse("closed before CONNECT")
            head += chunk
        m = re.fullmatch(rb"CONNECT ([A-Za-z0-9.-]{1,253}):([0-9]{1,5}) HTTP/1\.[01]", head.split(b"\r\n")[0])
        if not m:
            return refuse("not a CONNECT")
        host, port = m.group(1).decode(), int(m.group(2))
        if host not in allowed or port != 443:
            return refuse("host or port not allowed")
        infos = resolver(host, 443, family=socket.AF_INET, type=socket.SOCK_STREAM)
        addrs = sorted({i[4][0] for i in infos})
        if not addrs or not all(public_v4(a) for a in addrs):
            return refuse("resolved to a non-public or missing address")
        target = addrs[0]
        conn.sendall(b"HTTP/1.1 200 Connection established\r\n\r\n")
        header = read_exact(conn, 5)
        if header[0] != 0x16 or int.from_bytes(header[3:5], "big") > 16384 + 256:
            return refuse("not a TLS ClientHello")
        hello = header + read_exact(conn, int.from_bytes(header[3:5], "big"))
        if sni_of(hello) != host:
            return refuse("SNI differs from the CONNECT host")
        upstream = connector((target, 443), timeout=timeout)
        try:
            upstream.sendall(hello)
            conn.settimeout(None)
            up, down = pipe(conn, upstream)
        finally:
            upstream.close()
        log(f"egress host={host} up={up} down={down} seconds={time.monotonic() - started:.1f}")
    except OSError as e:
        refuse(f"i/o error {type(e).__name__}", b"502 Bad Gateway")
    finally:
        conn.close()


def egress_main(lib=None):
    """The egress proxy: the block's egress list, read from the installed ops.json as data. A catalog with problems refuses
    every connection. It never loads the host module."""
    if os.geteuid() == 0:
        print("factory_op.py egress refuses to run as root", file=sys.stderr)
        return 2
    try:
        catalog = json.loads((pathlib.Path(lib or LIB) / "ops.json").read_text())
    except (OSError, ValueError):
        print("egress: ops.json isn't readable", file=sys.stderr)
        return 2
    problems = broker_problems(catalog, lib_scripts(lib or LIB))
    if problems:
        print(f"egress: ops.json isn't usable: {problems[0]}", file=sys.stderr)
        return 2
    egress_serve(socket.socket(fileno=os.dup(0)), allowed=frozenset(catalog["broker"]["egress"]))
    return 0


# ---------------------------------------------------------------- running steps (root)

def read_text_limited(path, limit=READ_LIMIT):
    """Text from a regular file, at most `limit` bytes; None for anything else. Root calls this on files in a directory the
    operator owns, so it never follows a symlink, never blocks on a FIFO or device, and never reads more than `limit`."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        return None
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            return None
        data = b""
        while len(data) < limit:
            chunk = os.read(fd, limit - len(data))
            if not chunk:
                break
            data += chunk
        return data.decode("utf-8", "replace")
    except OSError:
        return None
    finally:
        os.close(fd)


def redact(text, secrets):
    """Replace each secret (bytes) in `text`, as raw text, hex and base64, with [redacted]."""
    for secret in secrets:
        variants = {secret.decode("latin-1"), secret.hex(), base64.b64encode(secret).decode()}
        try:
            variants.add(secret.decode("utf-8"))
        except UnicodeDecodeError:
            pass
        for v in sorted((v for v in variants if len(v) >= 8), key=len, reverse=True):
            text = text.replace(v, "[redacted]")
    return text


def secrets_to_redact(installed):
    """The byte strings to redact for the secrets installed in a step: [(label, bytes, hex)]. A hex secret is also
    redacted as the bytes it decodes to."""
    out = []
    for _label, data, hexed in installed:
        text = data.decode("utf-8", "replace").strip()
        if text:
            out.append(text.encode())
            if hexed:
                try:
                    out.append(bytes.fromhex(text))
                except ValueError:
                    pass
    return out


LONG_RUN = re.compile(r"[A-Za-z0-9+/=_-]{20,}")


def scrub(text):
    """A reason that reaches a receipt keeps no long token-like run (a secret in a form redaction didn't know), except the
    40-hex commit ids and UUIDs that are the point of the message."""
    return LONG_RUN.sub(lambda m: m.group() if SHA.fullmatch(m.group()) or UUID.fullmatch(m.group()) else "[scrubbed]", text)


def _text(value, limit=200):
    return safe(value, limit) if isinstance(value, str) else None


def sha_or_none(value):
    return value if isinstance(value, str) and SHA.fullmatch(value) else None


def clean_detail(name, detail, services, installed=()):
    """What root keeps of a step's detail file, which the operator wrote: notes (at most 50 printable lines of at most 300
    characters, redacted and scrubbed, printed and never decided on) and, for drift-scan, rows keyed by declared services
    in a fixed shape. Anything else is dropped, so a hostile step can't hand root a type it doesn't expect."""
    out = {"notes": [], "rows": None}
    if not isinstance(detail, dict):
        return out
    secrets = secrets_to_redact(installed)
    notes = detail.get("notes")
    if isinstance(notes, list):
        out["notes"] = [scrub(safe(redact(n, secrets), NOTE_LIMIT)) for n in notes[:MAX_NOTES] if isinstance(n, str)]
    rows = detail.get("rows")
    if name == "drift-scan" and isinstance(rows, dict):
        out["rows"] = {svc: [{"id": _text(r.get("id"), 64), "commit": sha_or_none(r.get("commit")),
                              "created": _text(r.get("created"), 40), "branch": _text(r.get("branch"), 100)}
                             for r in rows[svc][:MAX_ROWS] if isinstance(r, dict)]
                       for svc in services if isinstance(rows.get(svc), list)}
    return out


def read_step_files(name, op, out_text, detail_text, services, installed=()):
    """(outputs, detail) from a step's out and detail files: only outputs the operation declares, matching their patterns,
    each written once (a repeated name is dropped), and clean_detail's detail."""
    outputs, seen, repeated = {}, set(), set()
    for line in (out_text or "").splitlines():
        m = OUT_LINE.fullmatch(line)
        if not m:
            continue
        field, value = m.groups()
        if field in seen:
            repeated.add(field)
        seen.add(field)
        if field in op.get("outputs", {}) and accepts(op["outputs"][field], value):
            outputs[field] = value
    for field in repeated:
        outputs.pop(field, None)
    try:
        detail = json.loads(detail_text or "{}")
    except (ValueError, RecursionError):  # the operator controls this file: absurd nesting must not crash root
        detail = {}
    return outputs, clean_detail(name, detail, services, installed)


def other_tiers(own, root="/"):
    """The other tiers on this host, found by looking (/etc/factory-prod*/config.json, /run/factory-prod*), never named."""
    root = pathlib.Path(root)
    found = {pathlib.Path(p).parent.name for p in glob.glob(str(root / "etc" / "factory-prod*" / "config.json"))}
    found |= {pathlib.Path(p).name for p in glob.glob(str(root / "run" / "factory-prod*"))}
    return sorted(t for t in found if tier_of(t) == t and t != own)


def hidden_paths(cfg, own=None, root="/"):
    """What a step can't see: the network control sockets, the host's shared memory and message queues, this tier's state
    and logs, every other tier's directories (its library, its config and host module among them), and
    every deploy directory named in this tier's or another's config (setup builds the same list). Raises Refused for a
    path that can't be named in the property (it is one space-separated value) or another tier's config that won't parse."""
    own = own or TIER or "factory-prod"
    paths = list(HIDDEN_ALWAYS) + [str(pathlib.PurePosixPath(cfg["ledger"]).parent), cfg["log_dir"]]
    deploy_dirs = [cfg.get("deploy_dir")]
    for other in other_tiers(own, root):
        n = tier_names(other)
        paths += [n["run_dir"], n["state_dir"], n["log_dir"], n["etc_dir"], n["clone_base"], n["lib_dir"]]
        text = read_text_limited(pathlib.Path(root) / n["config"].lstrip("/"))
        if text is None:
            continue
        try:
            other_cfg = json.loads(text)
        except (ValueError, RecursionError):
            raise Refused(f"{other}'s config.json doesn't parse, so its deploy directory can't be hidden from steps") from None
        deploy_dirs.append(other_cfg.get("deploy_dir") if isinstance(other_cfg, dict) else None)
    for d in deploy_dirs:
        if d is not None and not plain_path(d):
            raise Refused("a deploy_dir isn't an absolute path of plain characters, so it can't be hidden from steps")
        if d is not None:
            paths.append(d)
    for p in paths:
        if not plain_path(p):
            raise Refused(f"{safe(p, 80)} can't be hidden from steps: not an absolute path of plain characters")
    return " ".join("-" + p for p in dict.fromkeys(paths))


class StepResult:
    def __init__(self, status, outputs=None, detail=None, why=""):
        self.status, self.outputs, self.why = status, outputs or {}, why
        self.detail = detail or {"notes": [], "rows": None}


def last_line(path):
    try:
        lines = [x for x in pathlib.Path(path).read_text(errors="replace").splitlines() if x.strip()]
    except OSError:
        return ""
    return safe(lines[-1], 160) if lines else ""


class Sandbox:
    """Runs one operation as a transient systemd unit: the operator user, no IP network, only the egress proxy's socket."""

    LOG_LIMIT = 1 << 20

    def __init__(self, cfg, catalog, run_id, steps_dir=None, popen=subprocess.Popen, runner=subprocess.run, chown=True,
                 secret_dir=None, secret_owner=(0, 0), root="/", clock=time):
        self.cfg, self.catalog, self.run_id = cfg, catalog, run_id
        self.steps_dir = pathlib.Path(steps_dir if steps_dir is not None else STEPS_DIR)
        self.popen, self.runner, self.chown, self.root, self.clock = popen, runner, chown, root, clock
        self.secret_dir = pathlib.Path(secret_dir if secret_dir is not None else ETC_DIR)
        self.secret_owner = tuple(secret_owner)

    def argv(self, unit, step_dir, timeout_s, script, env, hidden=None):
        argv = [SYSTEMD_RUN, f"--unit={unit}", f"--uid={self.cfg['operator_user']}", f"--gid={self.cfg['operator_user']}",
                "--pipe", "--wait", "--collect", "--quiet", f"--working-directory={step_dir}"]
        hidden = hidden if hidden is not None else hidden_paths(self.cfg, root=self.root)
        # /run is an empty tmpfs (STEP_PROPS): the step's own directory and the egress socket are all it holds.
        props = [*STEP_PROPS, f"BindPaths={step_dir}", f"BindReadOnlyPaths={EGRESS_SOCK}",
                 f"ReadOnlyPaths={pathlib.Path(self.cfg['clone_dir']).parent}", f"InaccessiblePaths={hidden}",
                 f"RuntimeMaxSec={timeout_s + 60}"]
        for prop in props:
            argv += ["-p", prop]
        for k, v in sorted(env.items()):
            argv += ["-E", f"{k}={v}"]
        return argv + script

    def script(self, name):
        """`python3 -I factory_op.py op <name>`, unless the project keeps ops/<name>.sh for one of its own operations
        (never for a generic, host or internal one: broker_problems refuses that)."""
        lib = pathlib.Path(self.cfg["lib_dir"])
        block, script = self.catalog["broker"], lib / "ops" / f"{name}.sh"
        if name in self.catalog["operations"] and name not in GENERIC_OPS and name not in block["host_ops"] and script.is_file():
            return ["/bin/bash", str(script)]
        return [PYTHON, "-I", str(lib / "factory_op.py"), "op", name]

    def install_secret(self, label, dst, ids):
        """Copy one declared secret into the step dir, only from a regular root-owned 0600 file that isn't a symlink (`check`
        requires the same). Returns the bytes installed: redaction uses exactly those."""
        spec = self.catalog["broker"]["secrets"][label]
        src = self.secret_dir / spec["file"]
        try:
            fd = os.open(src, os.O_RDONLY | os.O_NOFOLLOW)
        except OSError:
            raise Refused(f"{spec['file']}: the source file can't be opened") from None
        try:
            st = os.fstat(fd)
            if not stat.S_ISREG(st.st_mode) or (st.st_uid, st.st_gid) != self.secret_owner or stat.S_IMODE(st.st_mode) != 0o600:
                raise Refused(f"{spec['file']}: the source file must be a regular file owned "
                              f"{self.secret_owner[0]}:{self.secret_owner[1]} with mode 0600")
            data = os.read(fd, 8192)
        finally:
            os.close(fd)
        out = os.open(dst, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(out, "wb") as f:
            f.write(data)
        if ids:
            os.chown(dst, ids.pw_uid, ids.pw_gid)
        return data

    def stop_unit(self, unit):
        try:
            self.runner([SYSTEMCTL, "stop", unit], capture_output=True, timeout=STOP_TIMEOUT_S)
        except Exception:  # the unit may not exist yet (the start failed): nothing to stop
            pass

    def unit_state(self, unit):
        """The unit's ActiveState as systemd reports it ("inactive" for a unit that is gone), or None when it can't say."""
        try:
            r = self.runner([SYSTEMCTL, "show", "-p", "ActiveState", "--value", unit], capture_output=True, text=True, timeout=10)
            state = r.stdout.strip() if r.returncode == 0 else None
        except Exception:
            return None
        return state if state and re.fullmatch(r"[a-z-]{1,20}", state) else None

    def kill_unit(self, unit):
        try:
            self.runner([SYSTEMCTL, "kill", "--signal=SIGKILL", unit], capture_output=True, timeout=10)
        except Exception:
            pass

    def stop_and_confirm(self, unit, bounded):
        """Stop the unit, kill what is left, and wait until systemd says it is gone (inactive, or failed: its processes are
        gone). After a timeout the step comes back only then (`bounded` false): SIGKILL again every UNIT_GONE_WAIT_S, for as
        long as it takes, with the broker's lock held, so nothing runs beside it. A broker that is itself being stopped
        (`bounded`) waits UNIT_GONE_WAIT_S at most and returns False for a unit still there: its directory stays (the step may
        still use it), and the next broker command refuses while the unit runs (broker_lock)."""
        self.stop_unit(unit)
        if self.unit_state(unit) in ("inactive", "failed"):
            return True
        self.kill_unit(unit)
        end = self.clock.monotonic() + UNIT_GONE_WAIT_S
        while True:
            if self.unit_state(unit) in ("inactive", "failed"):
                return True
            if self.clock.monotonic() >= end:
                if bounded:
                    return False
                self.kill_unit(unit)
                end = self.clock.monotonic() + UNIT_GONE_WAIT_S
            self.clock.sleep(1)

    def run(self, name, op, params, tag, log_path, release_head=""):
        cfg, block = self.cfg, self.catalog["broker"]
        for field, value in params.items():
            if field not in op.get("params", {}) or not accepts(op["params"][field], value):
                return StepResult("failed", why=f"{field} doesn't match its pattern at run time")
        if set(params) != set(op.get("params", {})):
            return StepResult("failed", why="the step's parameters aren't the operation's")
        if name not in block["op_secrets"]:
            return StepResult("failed", why=f"broker.op_secrets has no entry for {name}")
        try:
            hidden = hidden_paths(cfg, root=self.root)
        except Refused as e:
            return StepResult("failed", why=str(e))
        step_dir = self.steps_dir / f"{self.run_id}-{tag}"
        ids = pwd.getpwnam(cfg["operator_user"]) if self.chown else None
        step_dir.mkdir(mode=0o700, parents=True)
        installed, unit_live = [], False
        try:
            if ids:
                os.chown(step_dir, ids.pw_uid, ids.pw_gid)
            try:
                for label in block["op_secrets"][name]:
                    data = self.install_secret(label, step_dir / f"secret-{label}", ids)
                    installed.append((label, data, block["secrets"][label]["hex"]))
            except Refused as e:
                return StepResult("failed", why=str(e))
            out_file, detail_file = step_dir / "out", step_dir / "detail.json"
            for f in (out_file, detail_file):
                f.touch(mode=0o600)
                if ids:
                    os.chown(f, ids.pw_uid, ids.pw_gid)
            env = {"PATH": STEP_PATH, "LANG": "C.UTF-8", "OP_OUT": str(out_file), "OP_DETAIL": str(detail_file),
                   "FACTORY_STEP_DIR": str(step_dir), "FACTORY_CLONE": cfg["clone_dir"], "FACTORY_CONFIG": str(CONFIG),
                   "FACTORY_RELEASE_HEAD": release_head, "FACTORY_RUN": self.run_id}
            env.update({f"OP_{k.upper()}": v for k, v in params.items()})
            unit = f"{UNIT_PREFIX}{self.run_id}-{tag}"
            timed_out = False
            try:
                with open(log_path, "ab") as log:
                    proc = self.popen(self.argv(unit, step_dir, op["timeout_s"], env=env, script=self.script(name), hidden=hidden),
                                      stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                    try:
                        rc = proc.wait(timeout=op["timeout_s"])
                    except subprocess.TimeoutExpired:
                        # Back only once the unit is gone: the next step, a capture or another command must never run
                        # beside it, nor its directory go while it may still use it.
                        timed_out = True
                        self.stop_and_confirm(unit, bounded=False)
                        try:
                            rc = proc.wait(timeout=CLIENT_WAIT_S)
                        except subprocess.TimeoutExpired:
                            proc.kill()
                            rc = proc.wait()
            except BaseException:
                # An interrupt or an error here must not leave the unit running with its secrets and no one to collect it.
                unit_live = not self.stop_and_confirm(unit, bounded=True)
                raise
            finally:
                self.redact_log(log_path, installed)
            outputs, detail = read_step_files(name, op, read_text_limited(out_file), read_text_limited(detail_file, DETAIL_LIMIT),
                                              block["services"], installed)
            if timed_out:
                return StepResult("timed-out", outputs, detail, f"timed out after {op['timeout_s']} s")
            if rc != 0:
                return StepResult("failed", outputs, detail, scrub(last_line(log_path)) or f"exit {rc}")
            missing = sorted(set(op.get("outputs", {})) - set(outputs))
            if missing:
                return StepResult("failed", outputs, detail, f"missing or refused outputs: {', '.join(missing)}")
            return StepResult("done", outputs, detail)
        finally:
            if not unit_live:  # a live step's directory stays; the first broker command after the unit is gone removes it
                shutil.rmtree(step_dir, ignore_errors=True)

    def redact_log(self, log_path, installed):
        """A step shouldn't print a secret, but the log (and the receipt's reason, taken from it) is root's to keep clean.
        Redacts exactly the bytes that were installed. A log over the limit is cut, with a marker saying so."""
        secrets = secrets_to_redact(installed)
        try:
            size = os.path.getsize(log_path)
        except OSError:
            return
        text = read_text_limited(log_path, self.LOG_LIMIT)
        if not text:
            return
        cut = size > self.LOG_LIMIT
        if cut:
            text = text[:-4096]  # a secret split by the cut would leave a fragment
        text = redact(text, secrets)
        if cut:
            text += f"\n[log truncated at {self.LOG_LIMIT} bytes; the rest was discarded]\n"
        pathlib.Path(log_path).write_text(text)


def capture_runner(cfg, catalog, sandbox, log_dir, tag):
    """A run_capture(head) callable for pregate, the post-gate record, baseline and drift: (outputs, notes)."""
    def run_capture(head):
        res = sandbox.run("capture-state", catalog["operations"]["capture-state"], {}, tag, pathlib.Path(log_dir) / f"{tag}.log", head)
        if res.status != "done":
            raise Refused(f"capture-state didn't complete ({res.status}: {res.why})")
        return res.outputs, res.detail.get("notes", [])
    return run_capture


# ---------------------------------------------------------------- checks of the run and the request (D4 rule 7)

def installed_digest(gates, lib_dir):
    """The ops digest of the installed package, the host module and the config.json beside it included
    (gates.BROKER_MODULES)."""
    return gates.ops_digest(gates.installed_ops_files(lib_dir))


def package_digest(gates, cfg):
    """installed_digest, or None when the package can't be read (a file gone mid-swap): never equal to a digest."""
    try:
        return installed_digest(gates, cfg["lib_dir"])
    except OSError:
        return None


def approved(gh, cfg, run_id):
    for a in gh.get(f"actions/runs/{run_id}/approvals"):
        envs = {e.get("name") for e in a.get("environments") or []}
        if a.get("state") == "approved" and (a.get("user") or {}).get("id") in cfg["approvers"] and environment_of(cfg) in envs:
            return a["user"]["id"]
    return None


def gate_def(gates, g):
    return gates.canonical({"title": g["title"], "block": g["block"]})


def check_run(cfg, gates, gh, run_id, pr):
    run = gh.get(f"actions/runs/{run_id}")
    workflow, _, ref = (run.get("path") or "").partition("@")
    branch = cfg["default_branch"]
    if workflow != WORKFLOW or (ref and ref not in (branch, f"refs/heads/{branch}")) \
            or run.get("head_branch") != branch or run.get("event") != "workflow_dispatch" \
            or (run.get("repository") or {}).get("full_name") != cfg["repo"]:
        raise Refused("the run isn't factory-gate.yml dispatched on the default branch")
    if run.get("status") != "in_progress":
        raise Refused("the run isn't in progress")
    try:
        title = gates.parse_title(run.get("display_title"))
    except gates.Invalid as e:
        raise Refused(str(e)) from None
    if title["pr"] != pr:
        raise Refused("the run's title names another PR")
    approver = approved(gh, cfg, run_id)
    if approver is None:
        raise Refused(f"no approver approved this run's {safe(environment_of(cfg), 100)} deployment")
    return title, approver


def release_binding_for(cfg, gates, gh, pr, gate, head, budget=None):
    """{branch, pr, merge} of the merged release PR from the gate's pinned branch at `head`, read from GitHub. The broker has
    only the run's title, so it finds the PR itself; execute() then checks everything about it again. When none is merged at
    this head, a release PR merged at an older pinned commit of the same gate is reported as that: production runs it."""
    branch, pin = cfg["release_branch"], gates.pin_branch(pr, gate, head)
    owner = cfg["repo"].split("/")[0]
    rows = gh.get("pulls", {"state": "all", "head": f"{owner}:{pin}", "base": branch, "per_page": 100})
    if budget:
        budget.check("listing the gate's release PRs")
    mine = [p for p in rows if isinstance(p, dict) and (p.get("head") or {}).get("ref") == pin
            and (p.get("base") or {}).get("ref") == branch and (p.get("user") or {}).get("id") == cfg["app_bot_id"]
            and ((p.get("head") or {}).get("repo") or {}).get("full_name") == cfg["repo"]]
    merged = [p for p in mine if p.get("merged_at")]
    if len(merged) > 1:
        raise Refused(f"more than one merged release PR from {pin}: {', '.join('#' + str(p.get('number')) for p in merged)}")
    if not merged:
        opened = [p for p in mine if p.get("state") == "open"]
        if opened:
            raise Refused(f"release PR #{opened[0].get('number')} isn't merged into {branch} yet: CD merges it (that is the "
                          f"deploy), then adds factory:gate-retry to #{pr}")
        if mine:  # factory-gate-request.yml opens a new release PR when none is open or merged, so the pin is not lost
            raise Refused(f"release PR #{mine[0].get('number')} was closed without merging: reopen and merge it, or add "
                          f"factory:gate-retry to #{pr} and the factory opens a new one from {pin}; merging is the deploy")
        listed = gh.get("pulls", {"state": "closed", "base": branch, "sort": "updated", "direction": "desc", "per_page": 100})
        if budget:
            budget.check("listing the release branch's merged PRs")
        older = [p for p in listed
                 if isinstance(p, dict) and p.get("merged_at")
                 and re.fullmatch(rf"factory/release/{pr}-{re.escape(gate)}-[0-9a-f]{{12}}", (p.get("head") or {}).get("ref") or "")]
        if older:
            n, ref = older[0].get("number"), (older[0].get("head") or {}).get("ref")
            raise Refused(f"release PR #{n} ({safe(ref, 80)}) was merged at an older commit than PR #{pr}'s head {head[:12]}: "
                          f"production runs that older commit, not this one, so a gate for this head can't check it. Add "
                          f"factory:gate-retry to #{pr} for a release PR at the new head")
        raise Refused(f"no release PR from {pin} into {branch}: the factory opens it when execution stops at the gate")
    rec = gh.get(f"pulls/{merged[0].get('number')}")
    if budget:
        budget.check("reading the release PR")
    merge, number = rec.get("merge_commit_sha") or "", rec.get("number")
    if rec.get("merged") is not True or not SHA.fullmatch(merge) or type(number) is not int:
        raise Refused(f"release PR #{merged[0].get('number')} isn't merged")
    return {"branch": branch, "pr": number, "merge": merge}


def rebuild(cfg, gates, catalog, gh, pr, title, entries, budget=None):
    p = gh.get(f"pulls/{pr}")
    m = BRANCH.fullmatch((p.get("head") or {}).get("ref", ""))
    if not m or p.get("state") != "open" or (p.get("user") or {}).get("id") != cfg["app_bot_id"] \
            or ((p.get("head") or {}).get("repo") or {}).get("full_name") != cfg["repo"]:
        raise Refused(f"PR #{pr} isn't an open factory execution PR")
    issue, head = int(m.group(1)), p["head"]["sha"]
    public = (pathlib.Path(cfg["lib_dir"]) / "receipt.pub").read_text().strip()
    state = gates.pr_state(gh.get(f"issues/{pr}/comments", {"per_page": 100}), cfg["app_bot_id"], public, pr)
    plan = (state["tracker"] or {}).get("plan", "")
    if not isinstance(plan, str) or not gates.PLAN_PATH.fullmatch(plan):
        raise Refused("the PR names no plan")
    meta = gh.get(f"contents/{urllib.parse.quote(plan)}", {"ref": cfg["default_branch"]})
    if meta.get("encoding") != "base64":
        raise Refused("can't read the plan")
    plan_text = base64.b64decode(meta["content"]).decode()
    try:
        release = release_binding_for(cfg, gates, gh, pr, title["gate"], head, budget) if title["kind"] == "release" else None
        request = gates.build_request(
            repo=cfg["repo"], issue=issue, pr=pr, plan=plan, plan_blob=meta["sha"], plan_text=plan_text,
            gate_id=title["gate"], attempt=title["attempt"], head=head, catalog=catalog,
            gate_outputs=done_outputs(entries, cfg["repo"], pr),
            ops_digest=installed_digest(gates, cfg["lib_dir"]), release=release)
    except gates.Invalid as e:
        raise Refused(f"can't rebuild the request: {e}") from None
    if request["digest"] != title["digest"] or request["kind"] != title["kind"]:
        raise Refused("the approved request isn't what the plan, the PR head, this host's results and its installed "
                      "operations give now (something changed since approval). If production/ops.json, config.json, factory_op.py "
                      "or factory_op_host.py changed since this host was set up, its installed copy is older than the plan's "
                      "digest: CD re-runs setup on the production host")
    return request, earlier_gates(gates, plan_text, request["gate"], done_runs(entries, cfg["repo"], pr))


def gate_kind(g):
    """The kind of request the plan gives a gate now, as gates.build_request decides it: a release gate, a CD gate (no
    gate-ops block) or an ops gate."""
    return "release" if g["release"] is not None else ("cd" if g["block"] is None else "ops")


def earlier_gates(gates, plan_text, gate_id, done):
    """The gate's definition, once every gate before it in the plan is done on this host as the plan defines it now
    (D4 rule 7): the same title and block, and the same kind. A gate the plan has since made a release gate, or stopped
    making one, must run again: its result is of another kind, without (or with) the release's own checks."""
    for g in gates.parse_gates(plan_text):
        if g["id"] == gate_id:
            return gate_def(gates, g)
        if g["id"] not in done:
            raise Refused(f"{g['id']} isn't done on this host")
        if done[g["id"]].get("gate_def") != gate_def(gates, g):
            raise Refused(f"{g['id']} changed in the plan since it ran; it must run again")
        if done[g["id"]].get("kind") != gate_kind(g):
            raise Refused(f"{g['id']} ran as a {safe(done[g['id']].get('kind'), 20)} gate, and the plan now makes it a "
                          f"{gate_kind(g)} gate; it must run again")
    raise Refused(f"the plan has no gate {gate_id}")


# ---------------------------------------------------------------- executing a gate

class Services:
    """What execute() needs from outside: GitHub, git and the sandbox. Tests swap in fakes."""

    def __init__(self, gh, git, sandbox_for, clock=time):
        self.gh, self.git, self.sandbox_for, self.clock = gh, git, sandbox_for, clock


def needs_cd(text):
    return f"PRODUCTION NEEDS CD: {text}"


NO_ROLLBACK = ("this broker runs no rollback (ops.json's rollbacks is false): a failed gate is CD's to undo, so a request "
               "with one is refused before anything runs")
RELEASE_GATES_OFF = ("this broker doesn't take release gates yet (ops.json's release_gates is false): CD turns them on as "
                     "the last step of enabling it")


def budget_problem(catalog, request):
    """The gate run's job allows GATE_JOB_S for the broker's own time (the catalog's gate_overhead_s, at least its own worst
    case) and every step with its kill margin, a release gate's wait included. A request that could outrun it is refused
    before anything runs, not killed by the job's limit part-way."""
    ops = [s["op"] for s in request["steps"]]
    if request["kind"] == "release" and not waits_first(request["steps"], catalog):
        ops.insert(0, catalog["release_wait"])
    if not ops:
        return None
    overhead = max(catalog.get("gate_overhead_s", 0), min_gate_overhead_s(catalog))
    margin = max(catalog.get("step_margin_s", 0), STEP_KILL_MARGIN_S)
    worst = overhead + sum(catalog["operations"][op]["timeout_s"] + margin for op in ops)
    if worst > GATE_JOB_S:
        return (f"this gate's steps could take {worst} s with the broker's own time, more than the gate run's {GATE_JOB_S} s: "
                f"use fewer or shorter steps")
    return None


def release_shape_problem(cfg, catalog, request):
    """Why a release request can't run, from the request alone: its binding, or a block of anything but read operations (the
    broker can't deploy, so a release gate only checks)."""
    rel = request.get("release")
    if not isinstance(rel, dict) or set(rel) != {"branch", "pr", "merge"} or rel["branch"] != cfg["release_branch"] \
            or type(rel["pr"]) is not int or not SHA.fullmatch(str(rel["merge"])):
        return f"a release gate's request needs its merged release PR into {cfg['release_branch']}"
    for step in request["steps"]:
        op = catalog["operations"].get(step["op"])
        if not op or op.get("kind") != "read":
            return f"a release gate runs only read operations, and {safe(step['op'], 40)} isn't one"
    return None


def waits_first(steps, catalog):
    """Whether the block's first step is the release wait: then it is the gate's wait, and the broker adds none of its own."""
    return bool(steps) and steps[0]["op"] == catalog["release_wait"]


def check_release_pr(cfg, gates, gh, request, budget=None):
    """The release PR, read from GitHub by its number (the request's binding) and the execution PR's head, read the same
    way. Raises Refused for the first thing that isn't so; nothing has run yet."""
    pr, gate, head, bound = request["pr"], request["gate"], request["head"], request["release"]
    execution = gh.get(f"pulls/{pr}")
    if budget:
        budget.check("reading the execution PR")
    # An execution PR that is merged has its commits in the default branch: there is nothing left to tell its content by.
    if execution.get("state") != "open" or execution.get("merged") is True or execution.get("merged_at"):
        raise Refused(f"PR #{pr} isn't open and unmerged, so there is no execution PR whose content the release could be checked against")
    now_head = ((execution.get("head") or {}).get("sha")) or ""
    if now_head != head:
        raise Refused(f"PR #{pr}'s head moved since the request: it was {head[:12]}, it is {safe(now_head, 12)} now. Add "
                      f"factory:gate-retry for a request at the new head")
    try:
        pin = gates.pin_branch(pr, gate, head)
    except gates.Invalid as e:
        raise Refused(str(e)) from None
    n = bound["pr"]
    rec = gh.get(f"pulls/{n}")
    if budget:
        budget.check("reading the release PR")
    h, b = rec.get("head") or {}, rec.get("base") or {}
    older = re.fullmatch(rf"factory/release/{pr}-{re.escape(gate)}-([0-9a-f]{{12}})", h.get("ref") or "")
    if h.get("ref") != pin:
        if older and rec.get("merged") is True:
            raise Refused(f"release PR #{n} was merged at an older commit ({safe(h.get('sha'), 12)}) than PR #{pr}'s head "
                          f"{head[:12]}: production runs that commit, not this one")
        raise Refused(f"release PR #{n} isn't from the gate's pinned branch {pin}")
    if h.get("sha") != head:
        raise Refused(f"release PR #{n}'s branch is at {safe(h.get('sha'), 12)}, not PR #{pr}'s head {head[:12]}")
    if (h.get("repo") or {}).get("full_name") != cfg["repo"]:
        raise Refused(f"release PR #{n} isn't from this repository")
    if (rec.get("user") or {}).get("id") != cfg["app_bot_id"]:
        raise Refused(f"release PR #{n} isn't the factory App's")
    if b.get("ref") != cfg["release_branch"]:
        raise Refused(f"release PR #{n} isn't into {cfg['release_branch']}")
    if rec.get("merged") is not True:
        raise Refused(f"release PR #{n} isn't merged")
    if (rec.get("merged_by") or {}).get("id") not in cfg["approvers"]:
        raise Refused(f"release PR #{n} was merged by someone who isn't an approver")
    if rec.get("merge_commit_sha") != bound["merge"]:
        raise Refused(f"release PR #{n}'s merge commit isn't the one the request binds ({bound['merge'][:12]})")


def check_release_history(cfg, git, request, branch_head, budget=None):
    """The merge commit against the broker's clone, once the release branch is fetched: its second parent is the gate's
    commit, it is on the branch's first-parent history at or before the head, and the head still has the gate's content."""
    merge, head, branch = request["release"]["merge"], request["head"], cfg["release_branch"]

    def step(doing):
        if budget:
            budget.check(doing)

    for sha in (merge, head):
        if not git.has(sha):
            raise Refused(f"the broker's clone doesn't have {sha[:12]} after fetching {branch}")
    parents = git.parents(merge)
    step("reading the merge commit")
    if len(parents) != 2 or parents[1] != head:
        raise Refused(f"release PR #{request['release']['pr']}'s merge commit {merge[:12]} doesn't bring in the gate's commit "
                      f"{head[:12]} as its second parent")
    # On the first-parent line: the commit just after the merge on that line has the merge as its first parent. An ancestor
    # that arrived through some other merge's second parent isn't a release that was merged into the branch itself.
    if merge != branch_head:
        if not git.is_ancestor(merge, branch_head):
            raise Refused(f"the merge commit {merge[:12]} isn't in {branch}'s history")
        step("walking the release branch")
        after = git.first_parent_after(merge, branch_head)
        step("walking the release branch")
        if not after or git.parents(after[0])[:1] != [merge]:
            raise Refused(f"the merge commit {merge[:12]} isn't on {branch}'s first-parent history: it came in some other way")
    # What the execution PR's commits up to the gate changed, from where its branch left the default branch (a path changed and
    # changed back leaves no difference, so it isn't in the set; with nothing changed there is nothing of the gate's to compare).
    touched = git.diff_paths(git.merge_base(head, git.main_sha()), head)
    step("comparing the execution PR with the default branch")
    # The contract's check: the head has the gate's commit's blob. Comparing with the merge commit instead would pass a revert
    # that predates the merge (a recovery's revert, kept by a later clean merge), so the cost is a refusal when the release
    # branch had already changed a path the PR touches, and its recovery is on the PR's side.
    gone = sorted(touched & git.diff_paths(head, branch_head))
    if gone:
        more = f" and {len(gone) - 1} more" if len(gone) > 1 else ""
        default = cfg["default_branch"]
        raise Refused(f"{branch}'s head {branch_head[:12]} no longer has this gate's content: {safe(gone[0], 120)}{more} differs "
                      f"from the gate's commit {head[:12]}. It was reverted, or a release changed it (before this one merged, or "
                      f"since). If the release branch had changed it before, bring {default} into the execution branch, push, "
                      f"and add factory:gate-retry for a release at the new head; if it was reverted, CD decides (factory.md "
                      f"D4 rule 13: revert the revert and record a baseline)")


def head_moved_result(gh, cfg, head, res):
    """A release-wait that finished is only good if the branch head is still the one it waited for."""
    try:
        now_head = branch_head(gh, cfg)
    except Refused as e:
        return StepResult("failed", res.outputs, why=f"can't re-read the branch head: {e}")
    if now_head != head:
        return StepResult("failed", res.outputs, why=f"head moved: {head[:12]} to {now_head[:12]}; retry with factory:gate-retry")
    return res


def execute(cfg, gates, catalog, request, definition, approver, run_id, entries, sign, token, svc, public, host_run=None,
            budget=None):
    """Run the request (the caller holds the broker's lock). Returns the signed receipt. Every refusal comes before the
    ledger's start line, so a refused request leaves nothing unfinished. A CD gate has no steps. A release gate is checked
    first (its release PR, the merge, the content), then waits for production to serve the branch's head, then runs its read
    steps. The wait is the block's first step when that is the release wait, a receipt step with its evidence; otherwise it
    is the broker's own, outside the request's steps (their receipt must be the request's), with its outputs in the
    receipt's release_gate. `budget` is the pre-run deadline serve_one started at the rebuild."""
    block, kind = catalog["broker"], request.get("kind")
    if kind not in REQUEST_KINDS:
        raise Refused(f"unknown request kind {safe(repr(kind), 40)}: only ops, cd and release gates exist")
    if request.get("rollback"):
        raise Refused(NO_ROLLBACK)
    if kind == "release" and not gates.takes_release_gates(catalog):
        raise Refused(RELEASE_GATES_OFF)
    if kind == "cd" and request["steps"]:
        raise Refused("a CD gate runs no steps")
    for step in request["steps"]:
        if step.get("op") not in catalog["operations"]:
            raise Refused(f"{safe(step.get('op'), 40)} isn't in the installed catalog")
    pr = request["pr"]
    release = kind == "release"
    host_run = host_run or f"{datetime.datetime.now(datetime.timezone.utc):%Y%m%dT%H%M%SZ}-{pr}-{request['gate']}-a{request['attempt']}"
    base = {"repo": cfg["repo"], "pr": pr, "issue": request["issue"], "gate": request["gate"], "kind": kind,
            "attempt": request["attempt"], "digest": request["digest"], "head": request["head"], "run": host_run,
            "github_run": run_id}
    head = deployed_state = None
    log_dir = pathlib.Path(cfg["log_dir"]) / host_run
    to_run = [(s, False) for s in request["steps"]]
    wait = catalog["release_wait"]
    began = None  # the installed package's digest when the gate began: rebuild bound the request to it
    if kind in ("ops", "release"):
        began = package_digest(gates, cfg)
        if began is None:
            raise Refused("the installed operations can't be read: CD re-runs setup on the production host")
        state = recorded_state(entries, gates, public)
        if state is None:
            raise Refused(f"no recorded state: CD runs `sudo {USER_AGENT} baseline <note>` first")
        problem = state_problem(state, catalog) or budget_problem(catalog, request)
        if problem:
            raise Refused(problem)
        release_check = None
        budget = budget if release else None
        if release:
            problem = release_shape_problem(cfg, catalog, request)
            if problem:
                raise Refused(problem)
            budget = budget or PreRunBudget(PRE_RUN_BUDGET_S, svc.clock)
            check_release_pr(cfg, gates, svc.gh, request, budget)
            # The broker waits for rule 15's evidence itself, so a block can't forget to or reorder it (pregate wants it first).
            # A block that opens with its own release wait has that as the gate's wait (a receipt step, evidence and all); the
            # id of the broker's is not a valid step id, so no block step can share it.
            if not waits_first(request["steps"], catalog):
                to_run.insert(0, ({"id": "release_wait", "op": wait, "with": {"sha": request["head"]}}, True))
            release_check = functools.partial(check_release_history, cfg, svc.git, request, budget=budget)
        sandbox = svc.sandbox_for(host_run)
        log_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        ops = [s["op"] for s, _ in to_run]
        head, pre, _ = pregate(cfg, block, svc.gh, svc.git, state, capture_runner(cfg, catalog, sandbox, log_dir, "pre"), ops,
                               token, release_check=release_check, budget=budget, wait=wait)
    ledger_append(cfg["ledger"], {**base, "event": "start", "at": now(), "approver": approver})
    steps_out, outputs, status, reason, wait_out = [], {}, "done", None, {}
    changes = sorted({s["op"] for s in request["steps"] if catalog["operations"][s["op"]].get("kind") == "change"})
    if release:
        unchanged = "The release is live from CD's merge and this gate changed nothing"
        what = "The release is live from CD's merge and nothing this gate ran changed production"
    elif changes:
        unchanged = f"Nothing in production was changed except by this gate's change operations ({', '.join(changes)})"
        what = f"Nothing but this gate's change operations ({', '.join(changes)}) changes production"
    else:
        unchanged = what = "Nothing in production was changed: this gate's operations only read"
    if kind in ("ops", "release"):
        for n, (step, internal) in enumerate(to_run, 1):
            started = now()
            label = "the release wait" if internal else step["id"]
            ledger_append(cfg["ledger"], {**base, "event": "step-start", "step": step["id"], "at": started})
            if package_digest(gates, cfg) != began:
                # Setup takes the broker's lock, so this is a package swapped some other way: the step would run code CD
                # didn't approve, so it doesn't run.
                res = StepResult("failed", why=f"the installed operations changed during the gate (their digest isn't the one "
                                               f"the gate began with): {label} didn't run")
            else:
                res = sandbox.run(step["op"], catalog["operations"][step["op"]], step["with"], str(n),
                                  log_dir / f"{n:02d}-{step['id']}.log", head)
            if res.status == "done" and step["op"] == wait:
                res = head_moved_result(svc.gh, cfg, head, res)
            if step["op"] == wait and (internal or n == 1):
                wait_out = res.outputs
            if not internal:
                outputs[step["id"]] = res.outputs
                steps_out.append({"id": step["id"], "op": step["op"], "status": res.status, "started": started,
                                  "finished": now(), "outputs": res.outputs, "why": res.why})
            ledger_append(cfg["ledger"], {**base, "event": "step-finish", "step": step["id"], "status": res.status, "at": now()})
            if res.status == "timed-out":
                timed_out = {**base, "v": 1, "status": "timed-out", "steps": steps_out, "rollback": [], "at": now(),
                             "reason": needs_cd(f"{label} timed out. {what}, so read the step log, then run "
                                                f"`sudo {USER_AGENT} resolve {host_run} failed <note>`")}
                if release:  # the same evidence a failed release gate's receipt carries
                    timed_out["release_head"] = head
                    timed_out["release_gate"] = {"release_pr": request["release"]["pr"], "merge": request["release"]["merge"],
                                                 "wait": wait_out}
                return sign(timed_out)
            if res.status != "done":
                status, reason = "failed", needs_cd(f"{label} failed: {res.why}. {unchanged}")
                break
        if release and status == "done":
            # What the gate vouches for is the branch head it checked and the PR head it was asked about: both are re-read
            # after the last step, since a merge or a push can land at any time during the wait.
            try:
                still = ((svc.gh.get(f"pulls/{pr}").get("head") or {}).get("sha")) or ""
                branch_now = branch_head(svc.gh, cfg)
            except Refused as e:
                status, reason = "failed", needs_cd(f"can't re-read GitHub after the last step: {e}. {unchanged}")
            else:
                if still != request["head"]:
                    status, reason = "failed", needs_cd(f"PR #{pr}'s head moved during the gate: {request['head'][:12]} to "
                                                        f"{safe(still, 12)}. {unchanged}; add factory:gate-retry for the new head")
                elif branch_now != head:
                    status, reason = "failed", needs_cd(f"{cfg['release_branch']}'s head moved during the gate: {head[:12]} to "
                                                        f"{branch_now[:12]}. {unchanged}; add factory:gate-retry to check the new head")
        # Record the state only when the gate left every recorded output where it found it, from the code it began with.
        try:
            if package_digest(gates, cfg) != began:
                raise Refused("the installed operations changed during the gate")
            post, _ = capture_runner(cfg, catalog, sandbox, log_dir, "post")(head)
            if all(post.get(n) == pre.get(n) for n in block["recorded"]):
                deployed_state = state_from(post, head, block)
        except Refused:
            deployed_state = None
    receipt = {**base, "v": 1, "status": status, "steps": steps_out, "rollback": [], "at": now()}
    if reason:
        receipt["reason"] = reason
    if head:
        receipt["release_head"] = head  # the branch head this gate checked; gates.py's verification takes extra fields
    if release:
        # Not a step of the request (a receipt's steps must be the request's), so the wait's evidence rides beside them.
        receipt["release_gate"] = {"release_pr": request["release"]["pr"], "merge": request["release"]["merge"], "wait": wait_out}
    signed = sign(receipt)
    state_signed = sign({"v": 1, "kind": "state", "run": host_run, "deployed_state": deployed_state}) if deployed_state else None
    ledger_append(cfg["ledger"], {**base, "event": "finish", "at": now(), "status": status,
                                  "outputs": outputs if status == "done" else {}, "state_signed": state_signed,
                                  "plan_blob": request["plan_blob"], "gate_def": definition, "signed": signed})
    return signed


# ---------------------------------------------------------------- the lock, signals and serving

def flock_wait(f, seconds, clock=time):
    deadline = clock.monotonic() + seconds
    while True:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except BlockingIOError:
            if clock.monotonic() >= deadline:
                return False
            clock.sleep(5)


def clear_stale_steps(steps_dir):
    """Step directories left behind by a killed broker hold copies of secrets. broker_lock calls this only once no step unit
    of this tier is running, so none of them is in use."""
    d = pathlib.Path(steps_dir)
    try:
        children = list(d.iterdir()) if d.is_dir() else []
    except OSError:
        return
    for child in children:
        try:  # one stubborn entry must not stop the sweep, or the lock
            if child.is_dir() and not child.is_symlink():
                shutil.rmtree(child, ignore_errors=True)
            else:
                child.unlink(missing_ok=True)
        except Exception as e:
            print(f"stale step sweep: {safe(child.name, 60)}: {type(e).__name__}", file=sys.stderr)


class StepsLive(LockBusy):
    """A step unit of this tier is still running (its broker was killed), or systemd can't say: nothing may run beside it."""


class PackageChanged(LockBusy):
    """The installed package isn't the one this command loaded: setup ran while it waited for the lock."""


# What a root command loaded, from one read of the installed package (load): gates, the library and that read's digest.
Package = collections.namedtuple("Package", "gates lib digest")


class Loaded(tuple):
    """load()'s (cfg, gates, catalog, problems), with the Package they came from (None when it couldn't be read)."""

    package = None


def refuse_changed_package(package):
    """Once the lock is ours: the installed package must still be the bytes the command loaded its config, catalog and code
    from. A command that waited while setup swapped it would otherwise run on the old approvers, App id, environment,
    op_secrets and host locks, and the old gates.py and factory_op.py, beside the new host module."""
    try:
        now_digest = package.gates.ops_digest(package.gates.installed_ops_files(package.lib))
    except OSError:
        now_digest = None
    if now_digest != package.digest:
        raise PackageChanged("the installed package changed while this command waited for the broker's lock (setup ran): "
                             "nothing ran, so run it again")


def live_step_units(runner=subprocess.run, prefix=None):
    """This tier's step units that systemd doesn't report gone, as "unit (state)". A step is a transient unit tied to nothing:
    a broker killed mid-step leaves it running, with its secrets and egress, until its RuntimeMaxSec. Raises StepsLive when
    systemd's answer can't be read, so a broken answer never reads as "none"."""
    prefix = prefix or UNIT_PREFIX
    try:
        r = runner([SYSTEMCTL, "list-units", "--all", "--plain", "--no-legend", "--no-pager", "--full", "--type=service",
                    f"{prefix}*"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as e:
        raise StepsLive(f"can't ask systemd whether a step of this tier is still running: {safe(e, 80)}") from None
    if r.returncode != 0 or not isinstance(r.stdout, str):
        raise StepsLive("can't ask systemd whether a step of this tier is still running: systemctl list-units failed")
    live = []
    for line in r.stdout.splitlines():
        parts = line.split()
        if not parts:
            continue
        if len(parts) < 4 or not parts[0].startswith(prefix):
            raise StepsLive(f"systemctl's list of this tier's step units has a line this broker can't read: {safe(line, 80)}")
        if parts[2] not in ("inactive", "failed"):
            live.append(f"{safe(parts[0], 100)} ({safe(parts[2], 20)})")
    return live


def refuse_live_steps():
    live = live_step_units()
    if live:
        raise StepsLive(f"a step of this tier is still running ({', '.join(live[:3])}): its broker was stopped before it was. "
                        f"Nothing runs beside it; wait for it to end (its RuntimeMaxSec), or stop it with `sudo systemctl stop "
                        f"{live[0].split(' ')[0]}`, then try again")


# Who must own a host lock and its directory (root; a test points it at its own uid).
HOST_LOCK_OWNER = 0


def open_host_lock(path):
    """A host lock, opened so no other local user can block every gate or hang root: its directory is a real directory that
    root owns and no one else can write, opened without following a link; the file is opened in it without following a link
    or blocking (a FIFO can't hang root), must be a regular file root owns, and no one but root may open it (anyone who can
    open it can hold it). Returns the open file; raises LockBusy saying what is wrong."""
    where = safe(path, 80)
    parent, name = os.path.split(path)
    try:
        dfd = os.open(parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | os.O_NOFOLLOW)
    except OSError as e:
        raise LockBusy(f"the host lock {where}: its directory can't be opened ({type(e).__name__})") from None
    try:
        st = os.fstat(dfd)
        if not stat.S_ISDIR(st.st_mode) or st.st_uid != HOST_LOCK_OWNER or st.st_mode & 0o022:
            raise LockBusy(f"the host lock {where} is in a directory that isn't root's alone (root-owned, not group- or "
                           f"world-writable): another user could plant or hold it")
        try:
            fd = os.open(name, os.O_RDONLY | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600, dir_fd=dfd)
        except OSError as e:
            raise LockBusy(f"the host lock {where} can't be opened ({type(e).__name__}): it must be a regular file") from None
    finally:
        os.close(dfd)
    try:
        fst = os.fstat(fd)
        if not stat.S_ISREG(fst.st_mode) or fst.st_uid != HOST_LOCK_OWNER:
            raise LockBusy(f"the host lock {where} isn't a regular file root owns")
        if fst.st_mode & 0o066 and st.st_mode & 0o011:
            raise LockBusy(f"the host lock {where} is mode {stat.S_IMODE(fst.st_mode):o} in a directory others can enter: any "
                           f"user who can open it can hold it and block every gate. Make it 0600, or its directory 0700")
    except BaseException:
        os.close(fd)
        raise
    return os.fdopen(fd, "r")


@contextlib.contextmanager
def broker_lock(wait_s, steps_dir=None, clock=time, host_locks=(), package=None):
    """The one lock every command that runs steps holds (this tier serializes its own gates), and, for a gate, each of the
    block's host_locks too (D4 rule 12: never during the host's own job), all within the one wait. The broker's lock file is
    0600. Once the locks are ours, it refuses when the installed package isn't the `package` the command loaded
    (refuse_changed_package; main passes it to every command), and while any step unit of this tier still runs
    (refuse_live_steps); then it removes stale step directories: none of them is in use then."""
    path = pathlib.Path(LOCK)
    if not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        os.chmod(path.parent, 0o755)  # the runner's socket lives beside the lock; the lock file itself is 0600
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    os.fchmod(fd, 0o600)
    f = os.fdopen(fd, "a")
    held = []
    try:
        deadline = clock.monotonic() + wait_s
        if not flock_wait(f, wait_s, clock):
            raise LockBusy("another broker command holds the production lock")
        for lock in host_locks:
            h = open_host_lock(lock)
            held.append(h)
            if not flock_wait(h, max(0.0, deadline - clock.monotonic()), clock):
                raise LockBusy(f"the host's own job held {safe(lock, 80)} for the whole wait")
        if package is not None:
            refuse_changed_package(package)
        refuse_live_steps()
        clear_stale_steps(steps_dir if steps_dir is not None else STEPS_DIR)
        yield
    finally:
        for h in held:
            h.close()
        f.close()


# What anyone who can signal a root command can send it (sudo relays SIGHUP, SIGQUIT, SIGTERM, SIGUSR1, SIGUSR2, SIGALRM and
# more from the agent that ran it): every catchable signal whose default action ends the process unwinds it instead, so its
# step is stopped and its lock and directory released. Ignored: SIGINT (a Ctrl-C can't orphan a step), the job-control
# stops (a step's unit is never left waiting on a stopped broker), and SIGPIPE and SIGXFSZ (Python ignores both already:
# a write fails instead). Left as they are: signals whose default doesn't end the process, the uncatchable ones, and the
# faults a process raises on itself, where a deferred Python handler can't run.
IGNORED_SIGNALS = ("SIGINT", "SIGTSTP", "SIGTTIN", "SIGTTOU", "SIGPIPE", "SIGXFSZ")
NOT_ENDING_SIGNALS = ("SIGCHLD", "SIGCLD", "SIGCONT", "SIGURG", "SIGWINCH", "SIGINFO", "SIGKILL", "SIGSTOP")
FAULT_SIGNALS = ("SIGSEGV", "SIGBUS", "SIGFPE", "SIGILL", "SIGTRAP", "SIGSYS", "SIGABRT")


def unwind_signals():
    """The signal numbers install_root_signals routes to sigterm_to_exit: every valid one but those above."""
    keep = {getattr(signal, n) for n in IGNORED_SIGNALS + NOT_ENDING_SIGNALS + FAULT_SIGNALS if hasattr(signal, n)}
    return sorted(set(signal.valid_signals()) - keep)


def install_root_signals():
    """Every catchable signal whose default ends the process unwinds it (so step dirs and units are cleaned up); SIGINT,
    the job-control stops, SIGPIPE and SIGXFSZ are ignored."""
    for num in unwind_signals():
        try:
            signal.signal(num, sigterm_to_exit)
        except (OSError, ValueError, RuntimeError):  # one the platform keeps for itself
            pass
    for name in IGNORED_SIGNALS:
        if hasattr(signal, name):
            signal.signal(getattr(signal, name), signal.SIG_IGN)


def sigterm_to_exit(signum, frame):
    """SIGTERM from systemd, or any ending signal relayed by sudo or a terminal, becomes SystemExit, so `finally` blocks (step
    dirs, the lock) run."""
    raise SystemExit(128 + signum)


def real_services(cfg, token, catalog):
    git = Git(cfg["clone_dir"])
    return Services(GitHub(cfg["repo"], token), git, lambda host_run: Sandbox(cfg, catalog, host_run))


def refusal_receipt(gates, secret, reason, title=None):
    t = title or {}
    return gates.sign_receipt(secret, {"v": 1, "status": "refused", "reason": safe(reason, 2000), "digest": t.get("digest", ""),
                                       "pr": t.get("pr"), "gate": t.get("gate"), "steps": [], "rollback": [], "at": now()})


def serve_one(cfg, gates, catalog, line, secret, svc_factory=None, unusable=None, package=None):
    """One request from the runner: {"run_id", "pr", "token"} -> a signed receipt. `unusable`: what root's load found
    wrong with config.json or ops.json, answered with a signed refusal."""
    import ed25519
    public = ed25519.public_key(secret).hex()
    svc_factory = svc_factory or (lambda c, token: real_services(c, token, catalog))

    def sign(receipt):
        return gates.sign_receipt(secret, receipt)

    def refusal(reason, title=None):
        return refusal_receipt(gates, secret, reason, title)

    try:
        msg = json.loads(line)
        run_id, pr, token = int(msg["run_id"]), int(msg["pr"]), str(msg["token"])
    except Exception:  # nesting too deep (RecursionError), Infinity (OverflowError), wrong types: all just malformed
        return refusal("a malformed request")
    if not TOKEN.fullmatch(token):
        return refusal("no usable token")
    problems = unusable if unusable is not None else config_problems(cfg) + broker_problems(catalog, lib_scripts(cfg["lib_dir"]))
    if problems:
        return refusal("this broker's configuration isn't usable: " + "; ".join(problems[:3]))
    try:
        with broker_lock(LOCK_WAIT_S, host_locks=catalog["broker"].get("host_locks", []), package=package):
            svc = svc_factory(cfg, token)
            title = None
            try:
                title, approver = check_run(cfg, gates, svc.gh, run_id, pr)
                entries = ledger_entries(cfg["ledger"])
                stored = stored_receipt(entries, title["digest"])
                if stored:
                    return stored
                if title["kind"] == "release" and not gates.takes_release_gates(catalog):
                    return refusal(RELEASE_GATES_OFF, title)
                torn = torn_problem(entries)
                if torn:
                    return refusal(f"an earlier broker command was interrupted: {torn}", title)
                stuck = unfinished(entries)
                if stuck:
                    return refusal(f"an earlier gate run was interrupted ({stuck[0]}); its outcome is unknown. Inspect "
                                   f"production, then run `sudo {USER_AGENT} resolve {stuck[0]} failed <note>` on the host", title)
                budget = PreRunBudget(PRE_RUN_BUDGET_S, svc.clock)
                request, definition = rebuild(cfg, gates, catalog, svc.gh, pr, title, entries, budget)
                return execute(cfg, gates, catalog, request, definition, approver, run_id, entries, sign, token, svc, public,
                               budget=budget)
            except (Refused, GitError) as e:
                return refusal(str(e), title)
    except PackageChanged as e:
        return refusal(f"{e} (factory:gate-retry asks for a fresh gate run)")
    except StepsLive as e:
        return refusal(str(e))
    except LockBusy as e:
        return refusal(f"{e}: a gate waits {LOCK_WAIT_S // 60} minutes at most")


def peer_uid(sock):
    """The uid of the process on the other end of a Unix socket (Linux SO_PEERCRED)."""
    return struct.unpack("3i", sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i")))[1]


def read_request_line(conn, timeout, limit=65536):
    """One request line within `timeout` seconds in total: a deadline for the whole read, not a timeout per recv, which a
    sender trickling one byte at a time could keep resetting."""
    deadline = time.monotonic() + timeout
    data = b""
    try:
        while b"\n" not in data and len(data) < limit:
            left = deadline - time.monotonic()
            if left <= 0:
                return None
            conn.settimeout(left)
            chunk = conn.recv(min(4096, limit - len(data)))
            if not chunk:
                break
            data += chunk
    except OSError:  # includes the read timeout
        return None
    return data.decode("utf-8", "replace") if data else None


def serve_conn(cfg, gates, catalog, conn, secret, runner_uid=None, peer_uid_fn=peer_uid, read_timeout=SERVE_READ_TIMEOUT_S,
               svc_factory=None, unusable=None, package=None):
    """Serve one connection: the caller must be the runner user (the socket's mode says so too), and must send its
    request line within `read_timeout` seconds."""
    try:
        runner_uid = pwd.getpwnam(RUNNER_USER).pw_uid if runner_uid is None else runner_uid
        caller = peer_uid_fn(conn)
    except (KeyError, OSError, AttributeError):
        runner_uid, caller = -1, None
    if caller != runner_uid:
        out = refusal_receipt(gates, secret, "the caller isn't the runner user")
    else:
        line = read_request_line(conn, read_timeout)
        out = refusal_receipt(gates, secret, f"no request within {read_timeout} s") if line is None \
            else serve_one(cfg, gates, catalog, line, secret, svc_factory, unusable, package=package)
    try:
        conn.sendall((json.dumps(out, sort_keys=True) + "\n").encode())
    except OSError:
        pass  # the runner may drop the connection (a cancelled job); the gate still finished and is recorded


# ---------------------------------------------------------------- host commands (root)

class Console:
    def say(self, text):
        print(text)

    def ask(self, prompt):
        return input(prompt).strip()

    def secret(self, prompt):
        return getpass.getpass(prompt).strip()


def run_name(prefix, at=None):
    return f"{prefix}-{(at or datetime.datetime.now(datetime.timezone.utc)):%Y%m%dT%H%M%SZ}"


def cmd_baseline(cfg, gates, catalog, secret, note, advance, svc_factory, console, sandbox=None, lock_wait_s=60, package=None):
    """Record the state CD wants gates to expect. Keeps the record's release head unless `advance`, which runs the full
    provenance check first; every failing commit needs its own `accept <sha>`. Holds the broker lock throughout."""
    with broker_lock(lock_wait_s, package=package):
        return baseline_locked(cfg, gates, catalog, secret, note, advance, svc_factory, console, sandbox)


def baseline_locked(cfg, gates, catalog, secret, note, advance, svc_factory, console, sandbox):
    import ed25519
    problems = config_problems(cfg) + broker_problems(catalog, lib_scripts(cfg["lib_dir"]))
    if problems:
        raise Refused("this broker's configuration isn't usable: " + "; ".join(problems[:3]))
    block = catalog["broker"]
    public = ed25519.public_key(secret).hex()
    entries = ledger_entries(cfg["ledger"])
    if torn_problem(entries):
        raise Refused(torn_problem(entries))
    stuck = unfinished(entries)
    if stuck:
        raise Refused(f"gate run {stuck[0]} is unfinished: resolve it first")
    prev = recorded_state(entries, gates, public)
    run = run_name("baseline")
    svc = svc_factory(cfg, None)
    try:  # a fresh clone is empty: the start commit can't resolve before the first fetch
        fetched = fetch_refs(cfg, svc.git)
    except GitError as e:
        raise Refused(f"can't fetch the branches (`{USER_AGENT} fetch` shows why): {e}") from None
    sandbox = sandbox or svc.sandbox_for(run)
    log_dir = pathlib.Path(cfg["log_dir"]) / run
    log_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    out, notes = capture_runner(cfg, catalog, sandbox, log_dir, "baseline")(fetched[cfg["release_branch"]])
    problems = invariant_problems(block, out)
    if problems:
        raise Refused("; ".join(problems))
    unsettled = [s for s in services_of(block, "checked") if out.get(f"{s}_settled") != "yes"]
    if unsettled:
        raise Refused(f"a release is mid-deploy ({', '.join(unsettled)}): wait for it, then baseline")
    old = prev["recorded"] if prev else {}
    changed = [n for n in block["recorded"] if old.get(n) != out[n]]
    dropped = sorted(set(old) - set(block["recorded"]))
    console.say("recorded outputs that would change: " + (", ".join(changed) or "none")
                + (f"; no longer recorded: {', '.join(dropped)}" if dropped else ""))
    for name in catalog["operations"]["capture-state"].get("outputs", {}):
        if name not in block["recorded"] and name in out:
            console.say(f"{name}={out[name]}")
    for line in notes:
        console.say(line)
    git, accepted = svc.git, []
    if prev:
        base = prev["release_head"]
    else:
        try:
            base = git.resolve(cfg["release_head_start"])
        except GitError as e:
            raise Refused(f"can't resolve release_head_start {cfg['release_head_start']} in the clone: {e}") from None
    if not git.has(base):
        raise Refused(f"the clone doesn't have {base[:12]}")
    release_head = base
    if advance:
        token = console.secret("read-only GitHub token for the provenance check: ")
        if not TOKEN.fullmatch(token):
            raise Refused("no usable token")
        gh = svc_factory(cfg, token).gh
        head = branch_head(gh, cfg)
        try:
            fetch_release(cfg, git, token=token)
            fails = provenance_failures(cfg, gh, git, base, head)
        except GitError as e:
            raise Refused(f"provenance check couldn't run: {e}") from None
        for sha, reason in fails:
            console.say(f"{sha} {git.subject(sha)}: {reason}")
            if console.ask(f"type 'accept {sha}' to accept this commit: ") != f"accept {sha}":
                raise Refused(f"{sha} not accepted: baseline not recorded")
            accepted.append(sha)
        release_head = head
    if console.ask("type 'yes' to record this baseline: ") != "yes":
        raise Refused("baseline not confirmed")
    state = state_from(out, release_head, block)
    signed = gates.sign_receipt(secret, {"v": 1, "kind": "baseline", "run": run, "deployed_state": state, "accepted": accepted,
                                         "note": note, "by": os.environ.get("SUDO_USER", "root"), "at": now()})
    ledger_append(cfg["ledger"], {"event": "baseline", "run": run, "repo": cfg["repo"], "at": now(), "signed": signed})
    console.say(f"baseline recorded: release head {release_head[:12]}, {len(accepted)} commit(s) accepted by sha")
    return 0


def cmd_health(cfg, catalog, svc_factory, console, clock=time, stamp=None, package=None):
    """The health operation for CD (and agent sessions, passwordless): read-only, nothing recorded, at most once a minute.
    The minute is measured from the end of the previous run, and checked under the lock. The stamp is touched before the
    step starts too, so a run killed outright (SIGKILL: nothing unwinds) still counts against the minute."""
    stamp = pathlib.Path(stamp if stamp is not None else HEALTH_STAMP)
    with broker_lock(HEALTH_LOCK_WAIT_S, clock=clock, package=package):
        if stamp.exists() and clock.time() - stamp.stat().st_mtime < 60:
            raise Refused("health ran less than 60 s ago")
        stamp.parent.mkdir(parents=True, exist_ok=True)
        stamp.touch()
        started_at = clock.time()
        os.utime(stamp, (started_at, started_at))
        run = run_name("health")
        log_dir = pathlib.Path(cfg["log_dir"]) / run
        log_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        try:
            res = svc_factory(cfg, None).sandbox_for(run).run("health", catalog["operations"]["health"], {}, "1",
                                                             log_dir / "01-health.log")
        finally:
            stamp.parent.mkdir(parents=True, exist_ok=True)
            stamp.touch()
            done_at = clock.time()
            os.utime(stamp, (done_at, done_at))
    for k, v in sorted(res.outputs.items()):
        console.say(f"{k}={v}")
    console.say(f"health: {res.status}" + (f" ({res.why})" if res.why else ""))
    return 0 if res.status == "done" else 1


def cmd_diagnose(cfg, catalog, name, svc_factory, console, lock_wait_s=60, package=None):
    """`diagnose host-check` (the host module loads and meets the contract, and its preflight passes) or a host diagnostic
    (DIAGNOSTICS, run without preflight, so it runs with wrong ids): its notes, then its status."""
    internal = catalog["broker"]["internal_ops"]
    if name not in internal or name == "drift-scan":
        raise Refused(f"diagnose runs host-check or a host diagnostic in broker.internal_ops "
                      f"({', '.join(n for n in internal if n != 'drift-scan')})")
    run = run_name("diagnose")
    log_dir = pathlib.Path(cfg["log_dir"]) / run
    log_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    with broker_lock(lock_wait_s, package=package):
        res = svc_factory(cfg, None).sandbox_for(run).run(name, op_of(catalog, name), {}, "1", log_dir / "01-diagnose.log")
    for line in res.detail.get("notes", []):
        console.say(line)
    console.say(f"{name}: {res.status}" + (f" ({res.why})" if res.why else ""))
    return 0 if res.status == "done" else 1


def cmd_resolve(cfg, gates, secret, run, note, lock_wait_s=60, package=None):
    """Close an interrupted run as failed. Under the lock, so it can never close a run that is still going."""
    with broker_lock(lock_wait_s, package=package):
        entries = ledger_entries(cfg["ledger"])
        if torn_problem(entries):
            raise Refused(f"set the ledger's torn last line aside first (`sudo {USER_AGENT} resolve --torn-line <note>`): "
                          f"it may be this run's own last record")
        r = runs(entries).get(run)
        if not r or not r["start"] or r["finish"]:
            raise Refused("no unfinished run by that name")
        base = {k: r["start"][k] for k in ("repo", "pr", "issue", "gate", "attempt", "digest", "run", "github_run")}
        receipt = {**base, "v": 1, "status": "failed", "steps": [], "rollback": [], "at": now(),
                   "reason": f"interrupted; resolved by {os.environ.get('SUDO_USER', 'root')}: {note}"}
        ledger_append(cfg["ledger"], {**base, "event": "finish", "at": now(), "status": "failed", "outputs": {},
                                      "resolved": True, "signed": gates.sign_receipt(secret, receipt)})
    return 0


def cmd_resolve_torn(cfg, gates, secret, note, lock_wait_s=60, package=None):
    """`resolve --torn-line NOTE`: set the ledger's torn last line aside, never silently. Under the lock (and with no step of
    this tier running), the torn bytes go to a side file in the ledger's directory, the ledger is cut back to its last whole
    line, and a signed note records what was set aside, where, its hash, who and why: the cut and the note land together, in
    one rename. Returns the side file's path. Any other
    line that doesn't parse is refused (LedgerBroken): that one is CD's to repair by hand."""
    with broker_lock(lock_wait_s, package=package):
        path = pathlib.Path(cfg["ledger"])
        entries = ledger_entries(path)
        if entries.torn is None:
            raise Refused("the ledger's last line isn't torn: there is nothing to set aside")
        data = path.read_bytes()
        cut = data.rfind(b"\n") + 1
        torn = data[cut:]
        if torn != entries.torn:
            raise Refused("the ledger changed while it was read: run resolve --torn-line again")
        run = run_name("torn")
        side = path.parent / f"{path.name}.{run}"  # ledger.jsonl.torn-<time>, beside the ledger in the state dir
        # Signed before anything changes: a signer that fails leaves the ledger as it was, never cut without its note.
        note_receipt = {"v": 1, "kind": "torn-line", "run": run, "side_file": str(side), "bytes": len(torn),
                        "sha256": hashlib.sha256(torn).hexdigest(), "note": note,
                        "by": os.environ.get("SUDO_USER", "root"), "at": now()}
        signed = gates.sign_receipt(secret, note_receipt)
        try:
            out = os.open(side, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        except FileExistsError:  # an earlier attempt that stopped before its rename left this same side file: keep it
            fd = os.open(side, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(fd, "rb") as f:
                if f.read(len(torn) + 1) != torn:
                    raise Refused(f"{side} already exists with other bytes: move it aside, then run resolve --torn-line again")
        else:
            with os.fdopen(out, "wb") as f:
                f.write(torn)
                f.flush()
                os.fsync(f.fileno())
        fsync_dir(path.parent)
        # The cut ledger and its note replace the ledger in one rename: a crash at any point leaves either the torn ledger
        # as it was (and a side file to resolve again) or the whole lines with the note, never a cut without the note.
        entry = {"event": "torn-line", "run": run, "repo": cfg["repo"], "at": now(), "signed": signed}
        tmp = path.parent / f".{path.name}.{run}.tmp"
        try:
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, "wb") as f:
                f.write(data[:cut] + json.dumps(entry, sort_keys=True).encode() + b"\n")
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, path)
        finally:
            with contextlib.suppress(FileNotFoundError):
                os.unlink(tmp)
        fsync_dir(path.parent)
    return side


# GitHub's subject for a merged PR's merge commit, naming a release gate's pinned branch in this repository.
PIN_MERGE = re.compile(r"^Merge pull request #[0-9]+ from ([A-Za-z0-9_.-]+)/(factory/release/[0-9]+-G[1-9][0-9]?-[0-9a-f]{12})$")


# How long a release gate's pinned commit may be in production without being in main: its execution PR merges in days, so
# one still missing after this was most likely abandoned, and its code stays in production unreviewed by main's merge.
PIN_BOUND_S = 14 * 24 * 3600


def gate_merges(entries, gates, public):
    """{merge commit: when its gate ran} for the release gates this broker ran and recorded: a finish whose signed receipt
    verifies and is a release gate's, with its release PR's merge commit (which the gate checked against GitHub:
    check_release_pr). A merge's subject alone proves nothing: a branch can be named after the commit it holds."""
    out = {}
    for e in entries:
        if e.get("event") != "finish":
            continue
        receipt = verified(gates, public, e.get("signed"), "release")
        merge = ((receipt or {}).get("release_gate") or {}).get("merge")
        if not (isinstance(merge, str) and SHA.fullmatch(merge)):
            continue
        try:
            at = parse_ts(receipt.get("at"))
        except StepFailed:
            continue
        out[merge] = min(out.get(merge, at), at)
    return out


def pinned_merge(cfg, git, sha, parents, merges):
    """Whether a first-parent merge on the release branch is a release gate's: the broker recorded a release gate whose merge
    commit it is (`merges`, gate_merges), its subject names this repository's pinned branch, and that name ends in the first
    12 characters of the commit the merge brought in, its second parent."""
    if len(parents) != 2 or sha not in merges:
        return False
    r = git.run("log", "-1", "--format=%s", sha)
    m = PIN_MERGE.fullmatch(r.stdout.strip()) if r.returncode == 0 else None
    pin = PIN.fullmatch(m.group(2)) if m and m.group(1) == cfg["repo"].split("/")[0] else None
    return bool(pin) and pin.group(3) == parents[1][:12]


def release_pins(cfg, git, main_sha, head, merges, now_dt):
    """(pins, stale): the pinned commits recorded release gates brought into the release branch that main doesn't have yet,
    and [(merge, pin, when)] for those still missing from main PIN_BOUND_S after their gate, which no longer count."""
    pins, stale = [], []
    for sha in git.first_parent_after(main_sha, head):
        parents = git.parents(sha)
        if len(parents) == 2 and not git.is_ancestor(parents[1], main_sha) and pinned_merge(cfg, git, sha, parents, merges):
            if (now_dt - merges[sha]).total_seconds() > PIN_BOUND_S:
                stale.append((sha, parents[1], merges[sha]))
            else:
                pins.append(parents[1])
    return pins, stale


def drift_check(cfg, gates, catalog, secret, svc_factory, now_dt=None, lock_wait_s=None, package=None):
    """The daily alarm. Returns (issues, line); the line is the one journal line. It waits a bounded time for the lock (a
    gate may be running) and reports that instead of waiting on."""
    try:
        with broker_lock(drift_lock_wait_s(catalog) if lock_wait_s is None else lock_wait_s, package=package):
            return drift_locked(cfg, gates, catalog, secret, svc_factory, now_dt)
    except LockBusy as e:
        return None, f"drift: {e}; nothing was checked"


def drift_locked(cfg, gates, catalog, secret, svc_factory, now_dt):
    import ed25519
    block = catalog["broker"]
    public = ed25519.public_key(secret).hex()
    now_dt = now_dt or datetime.datetime.now(datetime.timezone.utc)
    svc = svc_factory(cfg, None)
    git = svc.git
    try:
        head = fetch_refs(cfg, git)[cfg["release_branch"]]
    except GitError as e:
        return None, f"drift: can't fetch: {e}"
    try:
        entries = ledger_entries(cfg["ledger"])
    except LedgerBroken as e:
        return None, f"drift: {e}"
    state = recorded_state(entries, gates, public)
    if state is None:
        return None, "drift: no recorded state"
    issues = [torn_problem(entries)] if torn_problem(entries) else []
    mismatch = state_problem(state, catalog)
    if mismatch:
        issues.append(mismatch)
    run = run_name("drift", now_dt)
    log_dir = pathlib.Path(cfg["log_dir"]) / run
    log_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    sandbox = svc.sandbox_for(run)
    try:
        out, _ = capture_runner(cfg, catalog, sandbox, log_dir, "capture")(head)
    except Refused as e:
        return None, f"drift: {e}"
    scan = sandbox.run("drift-scan", op_of(catalog, "drift-scan"), {}, "scan", log_dir / "scan.log", head)
    if not mismatch:
        moved = recorded_moved(block, state, out)
        if moved:
            issues.append("settings moved: " + ",".join(moved))
    issues += invariant_problems(block, out)
    for name in services_of(block, "checked"):
        if out.get(f"{name}_settled") != "yes":
            continue
        commit = out.get(f"{name}_commit")
        try:
            if not commit or not git.is_ancestor(commit, head) or not git.content_equal(commit, head, block["services"][name]["patterns"]):
                issues.append(f"{name} isn't content-equal to the branch head")
        except GitError:
            issues.append(f"{name} can't be compared with the branch head")
    baselines = baseline_times(entries, gates, public)
    if scan.status != "done":
        issues.append(f"deployment scan failed ({scan.why})")
    rows = scan.detail.get("rows") or {}
    try:
        for name in services_of(block):
            if scan.status == "done" and name not in rows:
                issues.append(f"{name}: the deployment scan gave no rows")
            for row in rows.get(name, []):
                try:
                    at = parse_ts(row.get("created"))
                except StepFailed:
                    issues.append(f"{name}: a deployment has no usable time")
                    continue
                if (now_dt - at).total_seconds() > DRIFT_WINDOW_S:
                    continue
                if block["services"][name]["checked"]:
                    if row.get("branch") != cfg["release_branch"] or not row.get("commit") or not git.is_ancestor(row["commit"], head):
                        issues.append(f"{name}: deployment {safe(row.get('id'), 16)} isn't from {cfg['release_branch']}")
                elif not any(b >= at for b in baselines):
                    issues.append(f"{name}: deployment {safe(row.get('id'), 16)} in the last 25 h isn't explained by a baseline")
    except GitError:
        issues.append("a deployment's commit couldn't be compared with the branch head")
    base = state["release_head"]
    merges = gate_merges(entries, gates, public)
    current = {m: at for m, at in merges.items() if (now_dt - at).total_seconds() <= PIN_BOUND_S}
    try:
        main_sha = git.main_sha()
        if git.is_ancestor(base, head):
            for sha in git.first_parent_after(base, head):
                parents = git.parents(sha)
                if len(parents) != 2 or not git.subject(sha).startswith("Merge pull request #"):
                    issues.append(f"release without a PR: {sha[:12]}")
                elif not git.is_ancestor(parents[1], main_sha) and not pinned_merge(cfg, git, sha, parents, current):
                    issues.append(f"release {sha[:12]} merged a branch that is not in main")
        else:
            issues.append(f"recorded release head {base[:12]} isn't an ancestor of the branch head: rewritten")
        pins, stale = release_pins(cfg, git, main_sha, head, merges, now_dt)
        for merge, pin, at in stale:
            issues.append(f"release gate's pinned commit {pin[:12]} (merged as {merge[:12]} on {at:%Y-%m-%d}) is still not in "
                          f"main after {PIN_BOUND_S // 86400} days: merge its execution PR, or revert it from "
                          f"{cfg['release_branch']} and record a baseline")
        extra = git.changed_files(MAIN_REF, RELEASE_REF)
        if extra:
            # A release gate's pinned commit is on its execution PR's branch, not in main until CD merges that PR (D4 rule 13):
            # the paths it changed, where the branch head still has its content, are its code, not code main lacks.
            explained = set()
            for pin in pins:
                explained |= git.diff_paths(git.merge_base(pin, main_sha), pin) - git.diff_paths(pin, head)
            extra = [f for f in extra if f not in explained]
    except GitError:
        issues.append("provenance or main comparison couldn't run")
        extra = []
    if extra:
        issues.append(f"production carries code main lacks ({len(extra)} files, e.g. {safe(extra[0], 60)})")
    return issues, "drift: " + ("; ".join(issues) if issues else "ok")


# ---------------------------------------------------------------- check (offline: no lock, no token, no request)

def checked_modes(cfg, block, names):
    """(path, mode, group, exact): root-owned; `exact` demands that mode, otherwise it is the widest allowed. `group` names
    the owning group (None: root's). Secrets are exact 0600 root:root, the same rule Sandbox.install_secret enforces."""
    etc = pathlib.Path(names["etc_dir"])
    return (
        (pathlib.Path(names["deploy_key"]), 0o600, None, True), (pathlib.Path(names["key"]), 0o600, None, True),
        *((etc / s["file"], 0o600, None, True) for s in block["secrets"].values()),
        (pathlib.Path(names["known_hosts"]), 0o644, None, False), (pathlib.Path(names["config"]), 0o644, None, False),
        (etc, 0o755, None, False), (pathlib.Path(names["state_dir"]), 0o700, None, False),
        (pathlib.Path(names["log_dir"]), 0o700, None, False), (pathlib.Path(names["run_dir"]), 0o755, None, False),
        (pathlib.Path(names["steps_dir"]), 0o711, None, False), (pathlib.Path(names["clone_base"]), 0o755, None, False),
        (pathlib.Path(cfg["clone_dir"]), 0o750, names["operator_user"], True),
        (pathlib.Path(names["socket"]), 0o660, names["runner_user"], True),
        (pathlib.Path(names["egress_socket"]), 0o660, names["operator_user"], True),
        (pathlib.Path(names["sudoers"]), 0o440, None, True), (pathlib.Path(names["command_path"]), 0o755, None, False),
        (pathlib.Path("/usr/local/bin/factory-op-request"), 0o755, None, False),
    )


def owner_problems(items, stat_fn=os.stat, gid_of=None):
    """Each (path, mode[, group, exact]) must exist, be owned by root (and the named group), and have exactly that mode, or
    no bit beyond it."""
    gid_of = gid_of or (lambda name: grp.getgrnam(name).gr_gid)
    problems = []
    for item in items:
        path, mode, group, exact = (*item, None, False) if len(item) == 2 else item
        try:
            st = stat_fn(path)
        except OSError:
            problems.append(f"no {path}")
            continue
        try:
            want_gid = 0 if group is None else gid_of(group)
        except KeyError:
            problems.append(f"no group {group} for {path}")
            continue
        if (st.st_uid, st.st_gid) != (0, want_gid):
            problems.append(f"{path} must belong to root:{group or 'root'}")
        have = stat.S_IMODE(st.st_mode)
        if (exact and have != mode) or (not exact and have & ~mode):
            problems.append(f"{path} is mode {have:o}, {'not' if exact else 'wider than'} {mode:o}")
    return problems


def group_problems(names, getgrnam=grp.getgrnam):
    """The sockets' groups hold exactly one account each: who may open them is the whole access control."""
    problems = []
    for group in (names["runner_user"], names["operator_user"]):
        try:
            extra = sorted(set(getgrnam(group).gr_mem) - {group})
        except KeyError:
            problems.append(f"no group {group}")
            continue
        if extra:
            problems.append(f"group {group} has members beyond {group}: {', '.join(extra)}")
    return problems


def key_problems(cfg, key=None):
    import ed25519
    key = pathlib.Path(key or KEY)
    try:
        public = ed25519.public_key(bytes.fromhex(key.read_text().strip())).hex()
    except (OSError, ValueError):
        return [f"no usable receipt.key at {key}"]
    except RuntimeError as e:  # no openssl left to sign with (guard_openssl), or none that can
        return [f"receipts can't be signed: {safe(e, 200)}"]
    pub = pathlib.Path(cfg["lib_dir"]) / "receipt.pub"
    if not pub.is_file() or pub.read_text().strip() != public:
        return ["receipt.pub doesn't match the signing key"]
    return []


def openssl_problems(candidates=None, stat_fn=os.stat, lstat_fn=os.lstat, module=None):
    """Every openssl ed25519.py may sign receipts with (its _openssls(): it runs the first that can) must be root's alone:
    the program, following links, and the directory it is in, root-owned and not group- or world-writable. Another user's
    openssl would be handed the receipt key on a pipe."""
    if candidates is None:
        if module is None:
            import ed25519 as module
        # The list ed25519.py has, not the one guard_openssl narrowed it to: a candidate it skips is still reported.
        candidates = getattr(module, "_factory_op_all_openssls", module._openssls)()
    if not candidates:
        return ["no openssl to sign receipts with (ed25519.py needs OpenSSL 3)"]
    problems = []
    for exe in candidates:
        real = os.path.realpath(exe)
        for path, what in ((real, "the program"), (os.path.dirname(real), "its directory"),
                           (os.path.dirname(os.path.abspath(exe)), "the directory it is found in")):
            try:
                st = stat_fn(path)
            except OSError:
                problems.append(f"openssl {safe(exe, 80)}: {what} ({safe(path, 80)}) can't be read")
                continue
            if st.st_uid != 0 or st.st_mode & 0o022:
                problems.append(f"openssl {safe(exe, 80)}, which ed25519.py may sign receipts with: {what} ({safe(path, 80)}) "
                                f"must be root-owned and not group- or world-writable")
        try:
            if lstat_fn(exe).st_uid != 0:
                problems.append(f"openssl {safe(exe, 80)} is a link another user owns")
        except OSError:
            pass
    return list(dict.fromkeys(problems))


def guard_openssl(ed25519, ok=None):
    """Narrow the openssl programs ed25519.py hands the receipt key to (its _openssls(), which it tries in turn) to the
    ones openssl_problems passes, before root signs anything (load). ed25519.py itself is unchanged: its list is."""
    if getattr(ed25519, "_factory_op_guarded", False):
        return
    ok = ok or (lambda exe: not openssl_problems([exe]))
    candidates = ed25519._openssls
    ed25519._factory_op_all_openssls = candidates  # the whole list, which `check` reports from
    ed25519._openssls = lambda: [exe for exe in candidates() if ok(exe)]
    ed25519._factory_op_guarded = True


def check(cfg, catalog, gates, names=None):
    """Everything wrong with this tier's install, offline: no lock, no token, no request, and never the host module (agent
    sessions run it without a password, and another tier's setup reads it before and after)."""
    import ed25519
    strict = names is not None
    names = names or NAMES
    lib = pathlib.Path(cfg["lib_dir"])
    block_problems = broker_problems(catalog, lib_scripts(lib))
    problems = config_problems(cfg, names if strict else None) + block_problems
    block_ok = not block_problems
    if block_ok:
        want = (3, int(catalog["broker"]["python"].split(".")[1]))
        if sys.version_info[:2] < want:
            problems.append(f"this Python is {sys.version_info[0]}.{sys.version_info[1]}, below broker.python {want[0]}.{want[1]}")
    for path in (lib, *lib.rglob("*")):
        st = path.lstat()
        if st.st_uid != 0 or st.st_mode & 0o022:
            problems.append(f"{path} must be root-owned and not group- or world-writable")
    if not (lib / HOST_MODULE).is_file():
        problems.append(f"no {HOST_MODULE} in {lib}: every step would fail")
    if block_ok:
        problems += owner_problems(checked_modes(cfg, catalog["broker"], names))
    for user in (names["operator_user"], names["egress_user"]):
        try:
            pwd.getpwnam(user)
        except KeyError:
            problems.append(f"no user {user}")
    problems += group_problems(names)
    for binary in (SYSTEMD_RUN, SYSTEMCTL, SSH_BIN, GIT_BIN, PYTHON):
        if not os.access(binary, os.X_OK):
            problems.append(f"no {binary}")
    if not pathlib.Path(cfg["clone_dir"]).is_dir():
        problems.append(f"no clone at {cfg['clone_dir']}")
    problems += openssl_problems()
    lib_cfg, etc_cfg = pathlib.Path(names["lib_config"]), pathlib.Path(names["config"])
    if strict and (read_text_limited(lib_cfg, 1 << 20) or "") != (read_text_limited(etc_cfg, 1 << 20) or ""):
        problems.append(f"{etc_cfg} isn't the same as {lib_cfg} (the copy this broker reads and hashes): other tiers read the "
                        f"/etc copy, so re-run setup, which writes both from one blob")
    key = key_problems(cfg)
    problems += key
    try:
        entries = ledger_entries(cfg["ledger"])
    except LedgerBroken as e:
        problems.append(str(e))
        entries = Entries()
    if torn_problem(entries):
        problems.append(torn_problem(entries))
    if not key:
        public = ed25519.public_key(bytes.fromhex(KEY.read_text().strip())).hex()
        for event, run in unverified_records(entries, gates, public):
            problems.append(f"ledger {event} record {run} fails signature verification (a rotated key?): "
                            f"gates ignore it until CD runs `baseline`")
        state = recorded_state(entries, gates, public)  # none yet is no problem: setup's check comes before the first baseline
        if state is not None and block_ok and state_problem(state, catalog):
            problems.append(state_problem(state, catalog))
    for stuck in unfinished(entries):
        problems.append(f"interrupted gate run {stuck} needs resolving: check production, then "
                        f"sudo {USER_AGENT} resolve {stuck} failed <note>")
    return problems


# ---------------------------------------------------------------- the command line

def read_package(lib):
    """The package's files as gates.installed_ops_files names them, read without gates: load reads them before it imports
    gates and ed25519, and compares them with what gates reads after."""
    d, out = pathlib.Path(lib), {}
    for name in ("gates.py", "ed25519.py", "factory_op.py", "ops.json", HOST_MODULE, "config.json"):
        try:
            out[name] = (d / name).read_bytes()
        except FileNotFoundError:
            pass
    for script in sorted((d / "ops").glob("*.sh")):
        out[f"ops/{script.name}"] = script.read_bytes()
    return out


def load(names):
    """config.json, gates and the catalog, as root reads them: a Loaded (cfg, gates, catalog, problems) with its Package.
    The installed package is read once (gates.installed_ops_files) and config.json and ops.json are parsed from those very
    bytes, whose digest the Package keeps: broker_lock refuses, once the lock is ours, when the package on disk isn't those
    bytes any more. factory_op.py itself must be the bytes this process started from. Every command but `check` refuses
    while there are problems, and `serve` answers each request with a signed refusal. The openssl programs ed25519.py may
    sign with are narrowed to root's own (guard_openssl) before anything is signed."""
    problems, cfg, catalog, package, files = [], {}, None, None, None
    try:  # before gates and ed25519 are imported: read again after, the code imported is the code hashed
        before = read_package(LIB)
    except OSError:
        before = None
    if str(LIB) not in sys.path:
        sys.path.insert(0, str(LIB))  # gates.py and ed25519.py, the installed copies beside this file
    import gates  # noqa: E402
    import ed25519  # noqa: E402
    guard_openssl(ed25519)
    try:
        files = gates.installed_ops_files(LIB)
    except OSError as e:
        problems.append(f"the installed package in {LIB} can't be read ({type(e).__name__}): CD re-runs setup")
    if files is not None:
        package = Package(gates, LIB, gates.ops_digest(files))
        if before is None or any(before.get(name) != data for name, data in files.items()):
            problems.append("the installed package changed while this command loaded it (setup ran): run it again")
        if files.get("factory_op.py") != SELF_BYTES:
            problems.append("factory_op.py on disk isn't the one this command started from (setup ran as it started): run "
                            "it again")
        if HOST_MODULE not in files:
            problems.append(f"no {HOST_MODULE} in {LIB}, so config.json isn't in the operations digest and every step "
                            f"would fail: CD re-runs setup")
    raw = (files or {}).get("config.json")
    try:
        cfg = json.loads(raw if raw is not None else CONFIG.read_bytes())
    except (OSError, ValueError):
        problems.append(f"{CONFIG} isn't readable JSON")
        cfg = {}
    problems += config_problems(cfg, names)
    try:
        if files is None:
            raise OSError("the package can't be read")
        catalog = gates.load_catalog(files["ops.json"].decode("utf-8"))
    except (OSError, UnicodeDecodeError, gates.Invalid) as e:
        problems.append(f"ops.json isn't usable: {safe(e, 200)}")
    if catalog is not None:
        problems += broker_problems(catalog, lib_scripts(LIB))
    out = Loaded((cfg, gates, catalog, problems))
    out.package = package
    return out


def main(argv):
    cmd = argv[1] if len(argv) > 1 else ""
    tier = tier_of(LIB)
    if tier is None or str(LIB) != tier_names(tier)["lib_dir"]:
        print(f"factory_op.py runs only from a tier's install path, /usr/local/lib/factory-prod or "
              f"/usr/local/lib/factory-prod-<instance>, not {safe(LIB, 120)}", file=sys.stderr)
        return 2
    names = tier_names(tier)
    if cmd == "op":
        return op_main(argv[2] if len(argv) > 2 else "")
    if cmd == "egress":
        return egress_main()
    if os.geteuid() != 0:
        print(f"{names['command']} runs as root", file=sys.stderr)
        return 2
    install_root_signals()
    loaded = load(names)
    cfg, gates, catalog, problems = loaded
    package = getattr(loaded, "package", None)  # every command checks it once it holds the lock

    def secret():
        return bytes.fromhex(KEY.read_text().strip())

    try:
        if cmd == "pubkey":
            import ed25519
            print(ed25519.public_key(secret()).hex())
            return 0
        if cmd == "check":
            if catalog is not None and not config_problems(cfg, names):
                problems = check(cfg, catalog, gates, names)
            digest = package.digest if package else None  # the bytes check read
            print(json.dumps({"ok": not problems, "problems": problems, "ops_digest": digest}, indent=2))
            return 0 if not problems else 1
        if cmd == "serve":
            signal.signal(signal.SIGPIPE, signal.SIG_IGN)
            conn = socket.socket(fileno=os.dup(0))  # systemd (Accept=yes) hands over the connection as stdin
            serve_conn(cfg, gates, catalog, conn, secret(), unusable=problems, package=package)
            return 0
        if cmd in ("fetch", "baseline", "health", "diagnose", "drift-check", "resolve") and problems:
            raise Refused("this broker's configuration isn't usable (run check): " + "; ".join(problems[:3]))
        def factory(c, token):
            return real_services(c, token, catalog)

        if cmd == "fetch":
            return cmd_fetch(cfg, Git(cfg["clone_dir"]), Console(), package=package)
        if cmd == "baseline" and len(argv) >= 3:
            advance = argv[2] == "--advance-release-head"
            note = " ".join(argv[3 if advance else 2:])
            return cmd_baseline(cfg, gates, catalog, secret(), note, advance, factory, Console(), package=package)
        if cmd == "health":
            return cmd_health(cfg, catalog, factory, Console(), package=package)
        if cmd == "diagnose" and len(argv) == 3:
            return cmd_diagnose(cfg, catalog, argv[2], factory, Console(), package=package)
        if cmd == "drift-check":
            issues, line = drift_check(cfg, gates, catalog, secret(), factory, package=package)
            print(line)
            return 0 if issues == [] else 1
        if cmd == "resolve" and len(argv) >= 4 and argv[2] == "--torn-line":
            side = cmd_resolve_torn(cfg, gates, secret(), " ".join(argv[3:]), package=package)
            print(f"the ledger's torn last line is set aside in {side}, with a signed note in the ledger; now resolve any run "
                  f"it leaves unfinished (check lists them)")
            return 0
        if cmd == "resolve" and len(argv) >= 4 and argv[3] == "failed":
            cmd_resolve(cfg, gates, secret(), argv[2], " ".join(argv[4:]), package=package)
            print(f"{argv[2]} resolved as failed; add factory:gate-retry on the PR for a fresh attempt")
            return 0
    except Refused as e:
        print(f"refused: {e}", file=sys.stderr)
        return 1
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
