#!/usr/bin/env bash
# A checks-only production tier's host setup (z-sdlc's factory-broker bundle: process/factory-broker.md, and
# process/factory.md's D4). It deploys nothing: the host deploys the release branch by itself, and this tier's broker
# runs the checks and the host's own read operations a production gate asks for.
#
# ONE HOST, SEVERAL TIERS. Every name comes from the tier's instance, host/production.conf's PROD_INSTANCE. The host's
# first tier leaves it empty and gets the plain names; each later tier sets a short name of its own:
#                       first tier (PROD_INSTANCE=)          instance x
#   runner user         factory-prod                         factory-prod-x  (and /etc, /var/lib, /var/log, /run dirs)
#   operator, egress    factory-prod-op, factory-prod-egress factory-prod-x-op, factory-prod-x-egress
#   broker command      factory-op (and its units)           factory-op-x
#   nft table           factory_prod                         factory_prod_x
#   firewall, runner    factory-prod-firewall, -runner       factory-prod-x-firewall, factory-prod-x-runner
# Other tiers are found on the host (/etc/factory-prod*, /run/factory-prod*, /var/lib/factory-prod*), never named here.
# Their runtime and state directories and their deploy directories are hidden from this tier's steps, egress proxy and
# runner. Their own `check` and isolation probes are taken before this runs, and must be no worse after. A tier whose
# names another tier holds is refused before anything changes.
#
# WHAT IT TRUSTS. Run as root from a checkout of the project's repository. Nothing in that checkout, its git metadata
# or its config is trusted for content: the login that owns the checkout can change all of it, and an agent session
# may run as that login. (A git "replace ref" lets its owner make `git show HEAD:file` return other bytes than the
# commit holds, while every check that asks the same copy stays clean.) So setup works in two stages:
#
#   BOOTSTRAP (runs from the checkout; as short as it can be, and it ends in exec or die):
#     - reads the tier's instance from the checkout's production.conf, as text, to find the tier;
#     - takes the repository from the tier's root-owned record (/etc/<tier>/tier), or, on the tier's first run, from
#       TIER_OWNER on the command line. Never from the checkout: an edit there would point root's fetch at another
#       repository that holds this same script and a hostile host module;
#     - refuses names another tier holds; creates /etc/<tier>, the read-only deploy key and GitHub's host keys
#       (fetched over TLS);
#     - root asks GitHub for the repository's default branch and fetches it into the root-owned bare clone, with a clean
#       git environment and the deploy key (a failed fetch prints the key to add as a read-only deploy key and stops:
#       nothing else is installed);
#     - stages every file to install, this script included, from that clone into a root-only temporary directory, each
#       file's `git hash-object` checked against the blob id the tree names;
#     - dies unless the running script and production.conf are byte-identical to the staged ones, then RE-EXECUTES the
#       staged copy with a clean environment.
#   STAGED COPY (everything with an effect): reads only the staged files and root's clone, and from the checkout only
#     the registration token, which the bootstrap checked and copied.
#
# RESIDUAL. The bootstrap still runs from the checkout: anyone who can write that file in the seconds before it runs
# gets root. Run setup only from a checkout no agent session can write, such as a fresh clone made just before.
#
#   1. three system users: the runner (it runs the gate job), the operator that runs the sandboxed steps, and the
#      egress proxy's. None has sudo, docker or a group this script didn't create (checked).
#   2. the firewall: its own nft table, loaded with `nft -f` only. Neither nftables.service nor any other table is
#      restarted, reloaded or flushed.
#   3. Tailscale, logind and linger denials for all three users.
#   4. the broker, under its own lock (a gate holds it for all its steps, so setup waits up to 120 s and stops rather than
#      swap the package under one): /usr/local/lib/<tier> (with config.json, the copy the broker reads, in the ops
#      digest), /usr/local/sbin/factory-op[-x], the per-user request client (the factory bundle's host/factory-op-request,
#      one per host), /etc/<tier> (config.json again, from the same blob, where other tiers find this one; the receipt
#      key, and the secrets ops.json's broker block declares: setup writes the ones it makes, and names the ones CD
#      writes), state and log directories.
#   5. systemd: the broker socket, the egress proxy's socket, the daily drift timer.
#   6. the GitHub Actions runner, at the factory bundle's pinned version (host/setup.sh's RUNNER_VERSION).
#   7. sudoers for the agent login: check and health without a password, everything else with one every time.
#   8. acceptance checks; any failure fails the setup.
#
# Idempotent. Re-run after changing anything under .github/factory/production/ or gates.py (a gate request's digest
# covers the installed operations, config.json included). A run while a gate is running stops before installing
# anything, as does one while a step of this tier outlived its broker. Needs systemd 248 or newer.
#
#   sudo TIER_OWNER=<owner>/<repository> bash setup-production.sh     (the tier's first run)
#   sudo bash setup-production.sh                                     (every run after)
#   (a registration token in <this dir>/reg-token registers the runner: a regular file, not a link, owned by root or
#    the sudo user, mode 0600 or tighter, holding only the token)
#   sudo REPLACE_CLIENT=1 bash setup-production.sh                    (replace a request client that differs, once
#                                                                      setup has shown the difference)
#
# Settings: host/production.conf, committed to the default branch and read as text (see the file). Setup refuses a
# checkout whose copy isn't the default branch's, and a setting given in the environment instead.
#
# --print-settings, --print-step-props and --print-egress-hidden print what setup resolves; --render DIR writes every
# generated file under DIR. None of them needs root or touches the host (the tests use them), and as root they're
# refused: as root, setup reads only the default branch's files. Without root they read the checkout's files, or the
# ones PRODUCTION_CONF, OPS_JSON and FACTORY_JSON name, and the repository from TIER_OWNER or the tier's record.
set -euo pipefail
# A fixed environment before anything else runs: sudo may keep the caller's PATH and TMPDIR, and bash itself reads BASH_ENV/ENV.
SAFE_PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
PATH=$SAFE_PATH
unset TMPDIR BASH_ENV ENV CDPATH
umask 022

BROKER_PATH=/usr/sbin:/usr/bin:/sbin:/bin  # the PATH the broker's units and wrapper run with
CLIENT=/usr/local/bin/factory-op-request
SETUP_REF=refs/factory/setup-tip
# One setup at a time on a host, shared with the factory bundle's host/setup.sh: a runner setup changing its own table
# while this one runs would read as a change to the host's firewall in this one's acceptance check.
SETUP_LOCK_DIR=/run/factory-runner
SETUP_LOCK=$SETUP_LOCK_DIR/setup.lock
# What production.conf may set (read as text by conf_read, never run).
CONF_KEYS="PROD_INSTANCE AGENT_USER PROD_RUNNER_NAME RUNNER_GROUP LAN_DNS PROBE_PORTS PROD_HOME_BASE"
# Instances that would make one tier's names another's: the first tier's operator is factory-prod-op, its clone
# /var/lib/factory-prod-clone, its egress unit factory-op-egress.
RESERVED_INSTANCES="op egress clone runner firewall drift step"
# The broker's own modules beside factory_op.py (gates.py's BROKER_MODULES, which the ops digest hashes when present):
# staged and installed when the tip has them, removed when it doesn't, so the repository's digest and the host's agree.
BROKER_MODULES="factory_op_host.py"
# The tier's own files in /etc/<tier>: a declared secret is never one of them.
TIER_FILES="config.json receipt.key github-deploy-key github-deploy-key.pub known_hosts tier"
# The broker's own timing constants that size the daily drift check (factory_op.py's; a test ties them): its least
# wait for the broker lock, a first full fetch, the kill margin after each step's timeout, and its many short local git
# calls. The rest is data: the catalog's health and capture-state timeouts and the broker block's drift-scan timeout.
DRIFT_LOCK_WAIT_S=1000
FETCH_TIMEOUT_S=600
STEP_KILL_MARGIN_S=90
GIT_CALLS_BUDGET_S=600
# The oldest systemd a step's sandbox runs on: PrivateIPC= came in systemd 248 (factory_op.py's SYSTEMD_FLOOR; a test ties them).
SYSTEMD_FLOOR=248

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
FACTORY=$(cd "$SCRIPT_DIR/.." && pwd)
PROD=$FACTORY/production
HOST_ROOT=  # where the host's directories are looked for: always / as root; the tests point it elsewhere

log() { printf '\n==> %s\n' "$*"; }
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

# ---- settings, read as data ---------------------------------------------------------------------------------

# production.conf ($1) read as text, never run: each line is blank, a comment, or KEY=value for one of CONF_KEYS (once
# each), the value plain or quoted, and checked here. Prints KEY=value for every key, in CONF_KEYS' order.
conf_read() {
  python3 -I - "$1" "$CONF_KEYS" "$RESERVED_INSTANCES" <<'PY'
import ipaddress, re, sys
path, keys, reserved = sys.argv[1], sys.argv[2].split(), sys.argv[3].split()
try:
    with open(path, encoding="utf-8") as f:
        text = f.read()
except (OSError, UnicodeDecodeError) as e:
    sys.exit(f"can't read {path}: {e}")
line_re = re.compile(r"""\s*(?:export\s+)?([A-Z_][A-Z0-9_]*)=(?:"([^"$`\\]*)"|'([^'\\]*)'|([^\s"'$`\\#;&|<>(){}]*))\s*(?:#.*)?""")
values = {}
for n, line in enumerate(text.splitlines(), 1):
    if not line.strip() or line.lstrip().startswith("#"):
        continue
    m = line_re.fullmatch(line)
    if not m:
        sys.exit(f"{path}:{n}: setup reads this file as text and can't read this line: write KEY=value ({line.strip()!r})")
    key, value = m.group(1), next(v for v in m.group(2, 3, 4) if v is not None)
    if key not in keys:
        sys.exit(f"{path}:{n}: {key} isn't a production.conf setting (they are {', '.join(keys)})")
    if key in values:
        sys.exit(f"{path}:{n}: {key} is set twice")
    values[key] = value

def refuse(key, why):
    sys.exit(f"{path}: {key} {why}")

instance = values.get("PROD_INSTANCE", "")
if instance and not re.fullmatch(r"[a-z0-9]{1,12}", instance):
    refuse("PROD_INSTANCE", "must be empty (the host's first tier) or 1 to 12 lowercase letters or digits")
if instance in reserved:
    refuse("PROD_INSTANCE", f"can't be {instance}: the first tier's own names end in -{instance}")
user = values.get("AGENT_USER", "")
if user and (not re.fullmatch(r"[a-z_][a-z0-9_-]{0,31}", user) or user == "root" or user.startswith("factory-")):
    refuse("AGENT_USER", "must be the plain login name of the agent sessions' user (not root, not a factory user)")
name = values.get("PROD_RUNNER_NAME", "")
if name and not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", name):
    refuse("PROD_RUNNER_NAME", "must be lowercase letters, digits and dashes (at most 64)")
group = values.get("RUNNER_GROUP", "")
if group and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}", group):
    refuse("RUNNER_GROUP", "must be letters, digits, '.', '_' and '-'")
dns = values.get("LAN_DNS", "")
if dns:
    try:
        ok = re.fullmatch(r"[0-9]{1,3}(\.[0-9]{1,3}){3}", dns) and ipaddress.IPv4Address(dns)
    except ValueError:
        ok = False
    if not ok:
        refuse("LAN_DNS", "must be one IPv4 address")
ports = values.get("PROBE_PORTS", "").split()
if (len(ports) > 32 or len(set(ports)) != len(ports)
        or not all(re.fullmatch(r"[1-9][0-9]{0,4}", p) and int(p) <= 65535 for p in ports)):
    refuse("PROBE_PORTS", "must be up to 32 different port numbers, separated by spaces")
values["PROBE_PORTS"] = " ".join(ports)
base = values.get("PROD_HOME_BASE", "")
if base and not re.fullmatch(r"(/[A-Za-z0-9_][A-Za-z0-9._-]*)+", base):
    refuse("PROD_HOME_BASE", "must be an absolute path of letters, digits, '.', '_', '-' and '/'")
for key in keys:
    print(f"{key}={values.get(key, '')}")
PY
}

# The settings from production.conf ($1), as conf_read checked them.
load_conf() {
  local out line
  out=$(conf_read "$1") || exit 1
  while IFS= read -r line; do
    case ${line%%=*} in
      PROD_INSTANCE) INSTANCE=${line#*=} ;;
      AGENT_USER) AGENT_USER=${line#*=} ;;
      PROD_RUNNER_NAME) RUNNER_NAME=${line#*=} ;;
      RUNNER_GROUP) CONF_RUNNER_GROUP=${line#*=} ;;
      LAN_DNS) LAN_DNS=${line#*=} ;;
      PROBE_PORTS) PROBE_PORTS=${line#*=} ;;
      PROD_HOME_BASE) PROD_HOME_BASE=${line#*=} ;;
      *) die "conf_read printed '$line'" ;;
    esac
  done <<< "$out"
  PROD_HOME_BASE=${PROD_HOME_BASE:-/var/lib/factory}
}

# Every name of this tier, from its instance ($INSTANCE) and repository ($REPO, owner/name; empty until it's known).
names() {
  local dash=${INSTANCE:+-$INSTANCE} under=${INSTANCE:+_$INSTANCE}
  TIER_NAME=factory-prod$dash
  RUNNER_USER=$TIER_NAME OP_USER=$TIER_NAME-op EGRESS_USER=$TIER_NAME-egress
  NFT_TABLE=factory_prod$under NFT_FILE=/etc/factory-runner/prod$dash-firewall.nft
  FW_UNIT=$TIER_NAME-firewall RUNNER_UNIT=$TIER_NAME-runner
  BROKER_UNIT=factory-op$dash
  EGRESS_UNIT=$BROKER_UNIT-egress DRIFT_UNIT=$BROKER_UNIT-drift STEP_UNIT=$BROKER_UNIT-step
  LIB=/usr/local/lib/$TIER_NAME ETC=/etc/$TIER_NAME STATE=/var/lib/$TIER_NAME CLONE_BASE=/var/lib/$TIER_NAME-clone
  LOGS=/var/log/$TIER_NAME RUN=/run/$TIER_NAME BROKER_CMD=/usr/local/sbin/$BROKER_UNIT
  SUDOERS_NAME=91-agent-readonly$dash
  TIER_RECORD=$ETC/tier
  FETCH_SSH="ssh -F /dev/null -i $ETC/github-deploy-key -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=$ETC/known_hosts -o GlobalKnownHostsFile=/dev/null -o ConnectTimeout=30"
  CLONE='' REMOTE_URL='' RUNNER_URL=''
  if [[ -n ${REPO:-} ]]; then
    CLONE=$CLONE_BASE/${REPO#*/}.git REMOTE_URL=git@github.com:$REPO.git RUNNER_URL=https://github.com/${REPO%%/*}
  fi
}

# The repository whose default branch sets this tier up: the one its record ($1) names, or, on the tier's first run,
# the one the operator names (TIER_OWNER). Never the checkout's remote: that is the checkout owner's to change.
tier_repo() {
  local record=$1 repo
  if [[ -f $record ]]; then
    repo=$(<"$record")
    [[ -z ${TIER_OWNER:-} || $TIER_OWNER == "$repo" ]] \
      || die "the production tier $TIER_NAME is set up from $repo: run setup without TIER_OWNER, or remove $record to hand the tier to $TIER_OWNER"
  else
    repo=${TIER_OWNER:-}
    [[ -n $repo ]] \
      || die "no repository owns the production tier $TIER_NAME yet: run again with TIER_OWNER=<owner>/<repository>, naming the repository whose default branch sets it up"
  fi
  [[ $repo =~ ^[A-Za-z0-9-]+/[A-Za-z0-9._-]+$ && ${repo#*/} != . && ${repo#*/} != .. && $repo != *.git ]] \
    || die "'$repo' isn't <owner>/<repository>"
  printf '%s\n' "$repo"
}

# ops.json ($1) as data, never run: the broker block's parts setup uses, each checked here, since they reach root's own
# files and commands. Prints EGRESS=, PYTHON=, the timeouts that size the drift unit (HEALTH_TIMEOUT_S=,
# CAPTURE_TIMEOUT_S=, DRIFT_SCAN_TIMEOUT_S=) and one SECRET= line per secret.
block_read() {
  python3 -I - "$1" "$TIER_FILES" <<'PY'
import ipaddress, json, re, sys
path, tier_files = sys.argv[1], set(sys.argv[2].split())
def fail(why):
    sys.exit(f"{path}: {why}")
try:
    with open(path, encoding="utf-8") as f:
        catalog = json.load(f)
except FileNotFoundError:
    fail("missing: the production tier's catalog, with its broker block (the bundle's enable runbook writes it)")
except (OSError, ValueError) as e:
    fail(f"can't read it: {e}")
block = catalog.get("broker") if isinstance(catalog, dict) else None
if not isinstance(block, dict):
    fail("has no broker block")
HOST = re.compile(r"(?=.{1,253}$)[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)+")
egress = block.get("egress")
if not isinstance(egress, list) or not 1 <= len(egress) <= 16 or not all(isinstance(h, str) for h in egress) \
        or len(set(egress)) != len(egress):
    fail("broker.egress must be 1 to 16 different host names")
for host in egress:
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        fail(f"broker.egress names {host!r}, an IP address, not a host name")
    if not HOST.fullmatch(host):
        fail(f"broker.egress names {host!r}, not a lower-case host name")
secrets = block.get("secrets")
if not isinstance(secrets, dict):
    fail("broker.secrets must be an object (it may be empty)")
lines, files = [], set()
for label, s in secrets.items():
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,15}", label):
        fail(f"broker.secrets: {label!r} isn't a secret label")
    if not isinstance(s, dict) or not {"file", "by", "hex"} <= set(s) or set(s) - {"file", "by", "hex", "pattern"}:
        fail(f"broker.secrets.{label} must have file, by and hex (and may have pattern), nothing else")
    file = s["file"]
    if not isinstance(file, str) or not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,63}", file):
        fail(f"broker.secrets.{label}.file must be a plain file name in the tier's /etc directory")
    if file in tier_files or file in files:
        fail(f"broker.secrets.{label}.file {file!r} is the tier's own file or another secret's")
    files.add(file)
    if s["by"] not in ("cd", "setup") or type(s["hex"]) is not bool:
        fail(f"broker.secrets.{label}: by must be cd or setup, and hex true or false")
    if s["by"] == "setup" and not s["hex"]:
        fail(f"broker.secrets.{label}: a secret setup writes is hex (32 random bytes)")
    lines.append(f"SECRET={label} {file} {s['by']} {'hex' if s['hex'] else 'text'}")
python = block.get("python")
if not isinstance(python, str) or not re.fullmatch(r"3\.[0-9]{1,2}", python):
    fail("broker.python must be \"3.<minor>\"")
def timeout(where, entry):
    t = entry.get("timeout_s") if isinstance(entry, dict) else None
    if type(t) is not int or not 1 <= t <= 3600:
        fail(f"{where} needs timeout_s between 1 and 3600")
    return t
ops, internal = catalog.get("operations"), block.get("internal_ops")
health = timeout("operations.health", ops.get("health") if isinstance(ops, dict) else None)
capture = timeout("operations.capture-state", ops.get("capture-state") if isinstance(ops, dict) else None)
drift = timeout("broker.internal_ops.drift-scan", internal.get("drift-scan") if isinstance(internal, dict) else None)
print("EGRESS=" + " ".join(egress))
print("PYTHON=" + python)
print(f"HEALTH_TIMEOUT_S={health}")
print(f"CAPTURE_TIMEOUT_S={capture}")
print(f"DRIFT_SCAN_TIMEOUT_S={drift}")
print("\n".join(lines)) if lines else None
PY
}

# The broker block from ops.json ($1), as block_read checked it, and the drift unit's timeout it sets.
load_block() {
  local out line label file by kind
  out=$(block_read "$1") || exit 1
  EGRESS=() SECRET_LABELS=() SECRET_FILES=() SECRET_BY=() SECRET_KIND=()
  while IFS= read -r line; do
    case $line in
      EGRESS=*) read -r -a EGRESS <<< "${line#EGRESS=}" ;;
      PYTHON=*) PYTHON_MIN=${line#PYTHON=} ;;
      HEALTH_TIMEOUT_S=*) HEALTH_TIMEOUT_S=${line#*=} ;;
      CAPTURE_TIMEOUT_S=*) CAPTURE_TIMEOUT_S=${line#*=} ;;
      DRIFT_SCAN_TIMEOUT_S=*) DRIFT_SCAN_TIMEOUT_S=${line#*=} ;;
      SECRET=*)
        read -r label file by kind <<< "${line#SECRET=}"
        SECRET_LABELS+=("$label") SECRET_FILES+=("$file") SECRET_BY+=("$by") SECRET_KIND+=("$kind") ;;
      *) die "block_read printed '$line'" ;;
    esac
  done <<< "$out"
  # The drift check's worst case (the broker's drift_unit_min_s, which a test ties): the lock wait, longer than a
  # passwordless `health` can hold the lock; a first full fetch; capture-state and drift-scan to their timeouts; both
  # steps' kill margins; and the local git calls. Five minutes over it.
  DRIFT_LOCK_S=$((HEALTH_TIMEOUT_S + STEP_KILL_MARGIN_S + 60))
  ((DRIFT_LOCK_S > DRIFT_LOCK_WAIT_S)) || DRIFT_LOCK_S=$DRIFT_LOCK_WAIT_S
  DRIFT_MIN_S=$((DRIFT_LOCK_S + FETCH_TIMEOUT_S + CAPTURE_TIMEOUT_S + DRIFT_SCAN_TIMEOUT_S + 2 * STEP_KILL_MARGIN_S + GIT_CALLS_BUDGET_S))
  DRIFT_TIMEOUT_MIN=$(((DRIFT_MIN_S + 59) / 60 + 5))
}

# factory.json ($1), as bootstrap.py reads it: the production runner's label (runners.production), its group
# (runners.groups.production, if set), the production environment (environments.production) and the release branch
# (release.branch: empty, or no release block, is the fallback, which this broker isn't for).
factory_read() {
  python3 -I - "$1" <<'PY'
import json, re, sys
path = sys.argv[1]
try:
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
    runners, envs = cfg["runners"], cfg["environments"]
    labels, env = runners["production"], envs["production"]
    group = (runners.get("groups") or {}).get("production") or ""
    release = (cfg.get("release") or {}).get("branch") or ""
except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
    sys.exit(f"can't read {path}'s runners.production and environments.production: {e}")
defaults = {"self-hosted", "linux", "windows", "macos", "x64", "x86", "arm", "arm64"}
if not isinstance(labels, str) or not re.fullmatch(r"[A-Za-z0-9._-]+(,[A-Za-z0-9._-]+)*", labels) \
        or not [l for l in labels.lower().split(",") if l not in defaults]:
    sys.exit(f"{path}: runners.production must name a runner label of the production tier's own")
if not isinstance(group, str) or (group and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}", group)):
    sys.exit(f"{path}: runners.groups.production must be letters, digits, '.', '_' and '-'")
if not isinstance(env, str) or not re.fullmatch(r"[A-Za-z0-9._-]{1,100}", env):
    sys.exit(f"{path}: environments.production must be an environment name")
if not isinstance(release, str) or (release and (not re.fullmatch(r"[A-Za-z0-9._/-]{1,100}", release) or ".." in release)):
    sys.exit(f"{path}: release.branch must be a branch name")
print(f"LABELS={labels}\nGROUP={group}\nENVIRONMENT={env}\nRELEASE={release}")
PY
}

# The runner the factory bundle pins (its host/setup.sh, $1, read as text, never run): one RUNNER_VERSION line and one
# RUNNER_SHA256 line. Prints the version and the archive's sha256.
runner_pin() {
  python3 -I - "$1" <<'PY'
import re, sys
try:
    with open(sys.argv[1], encoding="utf-8") as f:
        text = f.read()
except OSError as e:
    sys.exit(f"can't read the factory bundle's host/setup.sh: {e}")
version = re.findall(r"(?m)^RUNNER_VERSION=([0-9]+\.[0-9]+\.[0-9]+)$", text)
sha = re.findall(r"(?m)^RUNNER_SHA256=([0-9a-f]{64})$", text)
if len(version) != 1 or len(sha) != 1 or len(re.findall(r"(?m)^\s*(?:export\s+)?RUNNER_(?:VERSION|SHA256)=", text)) != 2:
    sys.exit(f"{sys.argv[1]} doesn't pin the runner with one RUNNER_VERSION=<x.y.z> line and one RUNNER_SHA256=<sha256> line")
print(version[0], sha[0])
PY
}

# Everything that follows from the settings, the repository ($REPO), factory.json ($1) and the factory's setup.sh ($2).
resolve_settings() {
  local out line home
  names
  out=$(factory_read "$1") || exit 1
  while IFS= read -r line; do
    case $line in
      LABELS=*) RUNNER_LABELS=${line#*=} ;;
      GROUP=*) FACTORY_GROUP=${line#*=} ;;
      ENVIRONMENT=*) PROD_ENVIRONMENT=${line#*=} ;;
      RELEASE=*) FACTORY_RELEASE_BRANCH=${line#*=} ;;
    esac
  done <<< "$out"
  # The group bootstrap.py checks: production.conf's, else factory.json's, else its convention.
  RUNNER_GROUP=${CONF_RUNNER_GROUP:-${FACTORY_GROUP:-factory-pool-${REPO#*/}-prod}}
  [[ $RUNNER_GROUP =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$ ]] || die "the runner group '$RUNNER_GROUP' isn't a plain name: set RUNNER_GROUP in host/production.conf"
  out=$(runner_pin "$2") || exit 1
  read -r RUNNER_VERSION RUNNER_SHA256 <<< "$out"
  home=
  if command -v getent > /dev/null; then home=$(getent passwd "$RUNNER_USER" | cut -d: -f6 || true); fi
  RUNNER_HOME=${home:-$PROD_HOME_BASE/$RUNNER_USER}
  [[ $RUNNER_HOME =~ ^(/[A-Za-z0-9_][A-Za-z0-9._-]*)+$ ]] || die "$RUNNER_USER's home '$RUNNER_HOME' isn't a plain absolute path"
  RUNNER_DIR=$RUNNER_HOME/actions-runner
  RUNNER_WORK=$RUNNER_HOME/_work
}

# ---- the other tiers on this host: found, never named ----------------------------------------------------------

# Whether $1 is a production tier's name: factory-prod, or factory-prod-<instance> for an instance that isn't reserved.
is_tier_name() {
  local instance
  [[ $1 =~ ^factory-prod(-([a-z0-9]{1,12}))?$ ]] || return 1
  instance=${BASH_REMATCH[2]:-}
  [[ -z $instance || " $RESERVED_INSTANCES " != *" $instance "* ]]
}

# The other production tiers on this host, found as the broker finds them (factory_op.py's other_tiers, which a test
# ties): a tier's /etc/<tier>/config.json, or its /run/<tier>. OTHER_TIERS gets each one's name, sorted.
discover_tiers() {
  local p n found=()
  OTHER_TIERS=()
  for p in "$HOST_ROOT"/etc/factory-prod*/config.json; do
    if [[ -e $p || -L $p ]]; then p=${p%/config.json}; found+=("${p##*/}"); fi
  done
  for p in "$HOST_ROOT"/run/factory-prod*; do
    if [[ -e $p || -L $p ]]; then found+=("${p##*/}"); fi
  done
  while IFS= read -r n; do
    if [[ -n $n ]] && is_tier_name "$n" && [[ $n != "$TIER_NAME" ]]; then OTHER_TIERS+=("$n"); fi
  done < <(printf '%s\n' ${found[@]+"${found[@]}"} | LC_ALL=C sort -u)
}

# A config.json's deploy_dir ($1): nothing, or an absolute path of plain characters. It is written into unit files, so
# a newline or a space in it would be a directive or a second path there: refused, as the broker refuses it.
deploy_dir_of() {
  python3 -I - "$1" <<'PY'
import json, re, sys
path = sys.argv[1]
try:
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
except FileNotFoundError:
    sys.exit(0)
except (OSError, ValueError) as e:
    sys.exit(f"can't read {path}: {e}")
d = cfg.get("deploy_dir") if isinstance(cfg, dict) else None
if d in (None, ""):
    sys.exit(0)
# The broker's own rule for a path in config.json (factory_op.py's plain_path).
if not isinstance(d, str) or not re.fullmatch(r"/[A-Za-z0-9._/@+-]{0,250}", d) or ".." in d.split("/"):
    sys.exit(f"{path}: deploy_dir {d!r} isn't an absolute path of letters, digits and ._/@+- (no ..)")
print(d)
PY
}

# What this tier's steps, egress proxy and runner can't see of the other tiers (HIDE_TIERS: each one's runtime
# directory, where its broker.lock sits, and its state, log, /etc, clone and library directories, the library holding its
# config and host module) and every deploy directory,
# this tier's own included (HIDE_EXTRA: a deploy directory sits at a deployed commit, which can be behind the default
# branch). The broker's hidden_paths builds the same list, in the same order (a test compares them). This tier's
# config: $1, if any.
collect_hidden() {
  local n d cfg cfgs=()
  discover_tiers
  HIDE_TIERS=() HIDE_EXTRA=()
  [[ -z ${1:-} ]] || cfgs+=("$1")
  for n in ${OTHER_TIERS[@]+"${OTHER_TIERS[@]}"}; do
    HIDE_TIERS+=("/run/$n" "/var/lib/$n" "/var/log/$n" "/etc/$n" "/var/lib/$n-clone" "/usr/local/lib/$n")
    cfgs+=("$HOST_ROOT/etc/$n/config.json")
  done
  for cfg in ${cfgs[@]+"${cfgs[@]}"}; do
    d=$(deploy_dir_of "$cfg") || exit 1
    if [[ -n $d && " ${HIDE_EXTRA[*]:-} " != *" $d "* ]]; then HIDE_EXTRA+=("$d"); fi
  done
}

# Paths as an InaccessiblePaths value: space-separated, each optional ("-"), so a path this host lacks is no error, and
# each once.
hidden_list() {
  local p out=
  for p in "$@"; do
    if [[ " $out " != *" -$p "* ]]; then out+="${out:+ }-$p"; fi
  done
  printf '%s' "$out"
}

# The paths hidden from the egress unit.
egress_hidden() {
  hidden_list /run/tailscale /var/run/tailscale /run/dbus/system_bus_socket "$STATE" "$LOGS" \
    ${HIDE_TIERS[@]+"${HIDE_TIERS[@]}"} ${HIDE_EXTRA[@]+"${HIDE_EXTRA[@]}"}
}

# The paths hidden from the runner: Tailscale's local API, and what the steps can't see of the other tiers (their broker
# sockets included: a request client with a fixed path fails closed here, instead of reaching another tier's broker).
runner_hidden() {
  hidden_list /run/tailscale /var/run/tailscale /run/dbus/system_bus_socket \
    ${HIDE_TIERS[@]+"${HIDE_TIERS[@]}"} ${HIDE_EXTRA[@]+"${HIDE_EXTRA[@]}"}
}

# The properties of an operator step. The broker's own steps carry the same (its STEP_PROPS; a test compares them), and
# setup's acceptance probes run under these, so a drift between the two shows up there. AF_UNIX is allowed (the egress
# proxy's socket), so what a step reaches locally is an allowlist: /run is an empty read-only tmpfs holding only the egress
# socket (and, bound by op_step and the broker, the step's own directory); its own IPC; the host's /dev/shm and /dev/mqueue
# hidden. PrivateIPC= needs systemd 248 (check_systemd).
step_props() {
  STEP_PROPS=(
    -p NoNewPrivileges=yes
    -p PrivateTmp=yes
    -p ProtectSystem=strict
    -p ProtectHome=yes
    -p RestrictAddressFamilies=AF_UNIX
    -p PrivateNetwork=yes
    -p PrivateIPC=yes
    -p TemporaryFileSystem=/run:ro
    -p "BindReadOnlyPaths=$RUN/egress.sock"
    -p "ReadOnlyPaths=$CLONE_BASE"
    -p "InaccessiblePaths=$(hidden_list /run/tailscale /var/run/tailscale /run/dbus/system_bus_socket /run/systemd/resolve \
         /dev/shm /dev/mqueue "$STATE" "$LOGS" ${HIDE_TIERS[@]+"${HIDE_TIERS[@]}"} ${HIDE_EXTRA[@]+"${HIDE_EXTRA[@]}"})"
    -p KillMode=control-group
    -p TimeoutStopSec=30
    -p ProtectProc=invisible
    -p PrivateDevices=yes
    -p RestrictNamespaces=yes
    -p CapabilityBoundingSet=
    -p SystemCallFilter=@system-service
    -p SystemCallArchitectures=native
    -p LockPersonality=yes
    -p MemoryMax=512M
    -p TasksMax=64
    -p LimitFSIZE=1M
    -p SystemCallErrorNumber=EPERM
    -p RestrictSUIDSGID=yes
    -p UMask=0077
  )
}

print_settings() {
  local v
  for v in INSTANCE REPO TIER_NAME RUNNER_USER OP_USER EGRESS_USER RUNNER_NAME RUNNER_LABELS RUNNER_GROUP RUNNER_URL \
           RUNNER_VERSION RUNNER_HOME NFT_TABLE NFT_FILE FW_UNIT RUNNER_UNIT BROKER_UNIT EGRESS_UNIT DRIFT_UNIT STEP_UNIT \
           LIB ETC STATE CLONE_BASE CLONE LOGS RUN BROKER_CMD CLIENT SUDOERS_NAME TIER_RECORD AGENT_USER LAN_DNS \
           PROBE_PORTS PROD_HOME_BASE PROD_ENVIRONMENT; do
    printf '%s=%s\n' "$v" "${!v}"
  done
  printf 'OTHER_TIERS=%s\n' "${OTHER_TIERS[*]:-}"
}

# ---- generated files ----------------------------------------------------------------------------------------
# Each takes a root prefix (empty on the host, a directory under --render) and uses $RUID/$OPID/$EID.

write_file() { mkdir -p "$(dirname "$1")"; cat > "$1"; }

render_firewall() {
  local root=$1
  write_file "$root$NFT_FILE" <<EOF
# Loaded by $FW_UNIT.service. Own table, never a flush of the whole ruleset (other tables must stay); nftables.service is
# never restarted or reloaded by this tier. The brokers' Unix sockets aren't IP, so this doesn't touch them.
table inet $NFT_TABLE
delete table inet $NFT_TABLE
table inet $NFT_TABLE {
  set blocked4 {
    type ipv4_addr; flags interval
    elements = { 0.0.0.0/8, 10.0.0.0/8, 100.64.0.0/10, 127.0.0.0/8, 169.254.0.0/16,
                 172.16.0.0/12, 192.0.0.0/24, 192.168.0.0/16, 198.18.0.0/15, 224.0.0.0/4,
                 240.0.0.0/4 }
  }
  chain output {
    type filter hook output priority -150; policy accept;
    meta skuid $RUID jump runner_out
    meta skuid $OPID jump operator_out
    meta skuid $EID jump egress_out
  }
  # $RUNNER_USER: the factory runners' chain. The internet (GitHub), nothing on this host or the LAN.
  chain runner_out {
    ip daddr { 127.0.0.53${LAN_DNS:+, $LAN_DNS} } meta l4proto { tcp, udp } th dport 53 accept
    meta nfproto ipv6 counter reject comment "no IPv6"
    oifname "lo" counter reject comment "host-local services"
    ip daddr @blocked4 counter reject
  }
  # $OP_USER: no IP at all. Its steps reach the world only through the egress proxy's Unix socket.
  chain operator_out {
    counter reject comment "operator: reject all"
  }
  # $EGRESS_USER: DNS to the local stub, TCP 443 to public IPv4, nothing else. The hostname rule is the proxy's. Nothing on
  # this host either: a public address of the host's own goes out on lo, and would reach a local service on 443.
  chain egress_out {
    ip daddr 127.0.0.53 meta l4proto { tcp, udp } th dport 53 accept
    meta nfproto ipv6 counter reject comment "no IPv6"
    oifname "lo" counter reject comment "host-local services"
    ip daddr != @blocked4 tcp dport 443 accept
    counter reject comment "egress: 443 to public IPv4 only"
  }
}
EOF
  write_file "$root/etc/systemd/system/$FW_UNIT.service" <<EOF
[Unit]
Description=Firewall for the $RUNNER_USER, $OP_USER and $EGRESS_USER users
DefaultDependencies=no
Before=network-pre.target
Wants=network-pre.target
# nftables.service's stock ruleset starts with a flush of the whole ruleset: its reload reloads this table, and its start or
# restart runs $FW_UNIT-reapply.service. This tier never restarts or reloads nftables.service itself.
After=nftables.service
ReloadPropagatedFrom=nftables.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/sbin/nft -f $NFT_FILE
ExecReload=/usr/sbin/nft -f $NFT_FILE
ExecStop=/usr/sbin/nft delete table inet $NFT_TABLE

[Install]
WantedBy=multi-user.target
EOF
  write_file "$root/etc/systemd/system/$FW_UNIT-reapply.service" <<EOF
[Unit]
Description=Load the $TIER_NAME production firewall table again after nftables.service flushes the ruleset
DefaultDependencies=no
After=nftables.service $FW_UNIT.service

[Service]
Type=oneshot
ExecStart=/usr/sbin/nft -f $NFT_FILE

[Install]
WantedBy=nftables.service
EOF
  # And its stop: the stock ExecStop flushes the ruleset, so the table is loaded again straight after.
  write_file "$root/etc/systemd/system/nftables.service.d/$FW_UNIT.conf" <<EOF
[Service]
ExecStopPost=-/usr/sbin/nft -f $NFT_FILE
EOF
}

render_isolation() {
  local root=$1
  # Tailscale's local API, a Unix socket no firewall sees, dials tailnet peers as root for any local user. Denied by
  # user, reapplied whenever tailscaled recreates its directory.
  write_file "$root/etc/systemd/system/tailscaled.service.d/$TIER_NAME.conf" <<EOF
[Service]
ExecStartPre=-/usr/bin/setfacl -m u:$RUNNER_USER:--- -m u:$OP_USER:--- -m u:$EGRESS_USER:--- /run/tailscale
ExecStartPost=-/usr/bin/setfacl -m u:$RUNNER_USER:--- -m u:$OP_USER:--- -m u:$EGRESS_USER:--- /run/tailscale
EOF
  write_file "$root/etc/polkit-1/rules.d/60-$TIER_NAME.rules" <<EOF
// $RUNNER_USER, $OP_USER and $EGRESS_USER get nothing from logind (no linger: a user manager of their own would
// run outside the units' sandboxes).
polkit.addRule(function(action, subject) {
  if (["$RUNNER_USER", "$OP_USER", "$EGRESS_USER"].indexOf(subject.user) >= 0 && action.id.indexOf("org.freedesktop.login1.") == 0) { return polkit.Result.NO; }
});
EOF
}

render_broker_units() {
  local root=$1 unit_dir=$1/etc/systemd/system
  write_file "$root/etc/tmpfiles.d/$TIER_NAME.conf" <<EOF
d $RUN 0755 root root -
d $RUN/steps 0711 root root -
EOF
  write_file "$unit_dir/$BROKER_UNIT.socket" <<EOF
[Unit]
Description=Production broker socket for $TIER_NAME (process/factory.md, D4)

[Socket]
ListenStream=$RUN/op.sock
SocketUser=root
SocketGroup=$RUNNER_USER
SocketMode=0660
DirectoryMode=0755
Accept=yes
MaxConnections=4

[Install]
WantedBy=sockets.target
EOF
  write_file "$unit_dir/$BROKER_UNIT@.service" <<EOF
[Unit]
Description=Production broker for $TIER_NAME, one gate request (process/factory.md, D4)

[Service]
ExecStart=/usr/bin/python3 -I $LIB/factory_op.py serve
Environment=PATH=$BROKER_PATH
Environment=LANG=C.UTF-8
StandardInput=socket
StandardOutput=socket
StandardError=journal
SyslogIdentifier=$BROKER_UNIT
User=root
# A gate may wait for locks; each operation has its own timeout.
RuntimeMaxSec=infinity
# The broker finishes and records a gate even if the runner side goes away.
KillMode=process
EOF
  write_file "$unit_dir/$EGRESS_UNIT.socket" <<EOF
[Unit]
Description=Production broker's egress proxy socket for $TIER_NAME

[Socket]
ListenStream=$RUN/egress.sock
SocketUser=root
SocketGroup=$OP_USER
SocketMode=0660
DirectoryMode=0755
Accept=yes
MaxConnections=16

[Install]
WantedBy=sockets.target
EOF
  write_file "$unit_dir/$EGRESS_UNIT@.service" <<EOF
[Unit]
Description=Production broker's egress proxy for $TIER_NAME, one connection (ops.json's broker.egress hosts, port 443, A records only)

[Service]
ExecStart=/usr/bin/python3 -I $LIB/factory_op.py egress
Environment=PATH=$BROKER_PATH
Environment=LANG=C.UTF-8
StandardInput=socket
StandardOutput=socket
StandardError=journal
SyslogIdentifier=$EGRESS_UNIT
User=$EGRESS_USER
NoNewPrivileges=yes
PrivateTmp=yes
PrivateDevices=yes
ProtectSystem=strict
ProtectHome=yes
RestrictAddressFamilies=AF_INET AF_UNIX
CapabilityBoundingSet=
# Tailscale's local API would dial tailnet peers for any local user, as root, past the firewall.
InaccessiblePaths=$(egress_hidden)
MemoryMax=256M
TasksMax=64
RuntimeMaxSec=600
EOF
  write_file "$unit_dir/$DRIFT_UNIT.service" <<EOF
[Unit]
Description=Production drift check for $TIER_NAME (settings, release branch, deployments)

[Service]
Type=oneshot
ExecStart=/usr/bin/python3 -I $LIB/factory_op.py drift-check
Environment=PATH=$BROKER_PATH
Environment=LANG=C.UTF-8
User=root
SyslogIdentifier=$BROKER_UNIT
Nice=10
# The broker lock's wait ($DRIFT_LOCK_S s), a first full fetch ($FETCH_TIMEOUT_S s), capture-state ($CAPTURE_TIMEOUT_S s) and
# drift-scan ($DRIFT_SCAN_TIMEOUT_S s) to their timeouts, a kill margin after each ($STEP_KILL_MARGIN_S s), the local git calls
# ($GIT_CALLS_BUDGET_S s): $DRIFT_MIN_S s at most, and five minutes over it.
TimeoutStartSec=${DRIFT_TIMEOUT_MIN}min
EOF
  write_file "$unit_dir/$DRIFT_UNIT.timer" <<EOF
[Unit]
Description=Production drift check for $TIER_NAME, daily

[Timer]
OnCalendar=*-*-* 12:00:00 UTC
Persistent=true

[Install]
WantedBy=timers.target
EOF
}

render_runner_unit() {
  local root=$1
  write_file "$root/etc/systemd/system/$RUNNER_UNIT.service" <<EOF
[Unit]
Description=GitHub Actions runner for the production gates of $TIER_NAME (process/factory.md, D4)
Requires=$FW_UNIT.service $BROKER_UNIT.socket
After=network-online.target $FW_UNIT.service $BROKER_UNIT.socket
Wants=network-online.target

[Service]
User=$RUNNER_USER
WorkingDirectory=$RUNNER_DIR
ExecStart=$RUNNER_DIR/runsvc.sh
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=full
# The runner's home is under $PROD_HOME_BASE, so this costs nothing and keeps a compromised job out of /home.
ProtectHome=yes
# Tailscale's local API would dial tailnet peers for any local user, as root, past this user's firewall. The other
# production tiers' directories and every deploy directory are hidden too: a request client with a fixed path fails
# closed here.
InaccessiblePaths=$(runner_hidden)
MemoryMax=1G
TasksMax=256
KillMode=process
KillSignal=SIGTERM
TimeoutStopSec=5min

[Install]
WantedBy=multi-user.target
EOF
}

# Not installed by the host flow itself: it writes this to a temporary name and installs it only after visudo
# accepts it.
render_sudoers() {
  local file=$1
  write_file "$file" <<EOF
# The production broker of $TIER_NAME (process/factory.md, D4). $AGENT_USER may read state without a password; every
# other command, baseline, resolve and diagnose above all, asks for the password each time.
Defaults!$BROKER_CMD timestamp_timeout=0
$AGENT_USER ALL=(root) NOPASSWD: $BROKER_CMD check
$AGENT_USER ALL=(root) NOPASSWD: $BROKER_CMD health
$AGENT_USER ALL=(root) NOPASSWD: /usr/bin/cat $STATE/ledger.jsonl
EOF
}

# The command CD (and sudo) run. sudo may keep the caller's PATH, so the broker gets a fixed one; SUDO_USER stays, because
# the ledger records who ran `resolve`.
render_wrapper() {
  local root=$1
  write_file "$root$BROKER_CMD" <<EOF
#!/bin/sh
exec /usr/bin/env -i PATH=$BROKER_PATH LANG=C.UTF-8 \${SUDO_USER:+"SUDO_USER=\$SUDO_USER"} /usr/bin/python3 -I $LIB/factory_op.py "\$@"
EOF
}

render_all() {
  local root=$1
  render_wrapper "$root"
  render_firewall "$root"
  render_isolation "$root"
  render_broker_units "$root"
  render_runner_unit "$root"
  render_sudoers "$root/etc/sudoers.d/$SUDOERS_NAME"
}

# ---- the trusted fetch, the staging and the hand-over (see the header) -----------------------------------------

# git as root uses it: no system or global config, no replace refs, literal paths, no prompts, the pinned SSH command,
# nothing inherited.
clean_git() {
  env -i "PATH=$SAFE_PATH" HOME=/nonexistent LANG=C.UTF-8 GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null \
    GIT_NO_REPLACE_OBJECTS=1 GIT_LITERAL_PATHSPECS=1 GIT_TERMINAL_PROMPT=0 "GIT_SSH_COMMAND=$FETCH_SSH" git "$@"
}

# The default branch GitHub names for the repository at $1 (never the checkout's).
default_branch() {
  local line branch=
  while IFS= read -r line; do
    if [[ $line =~ ^ref:\ refs/heads/([^[:space:]]+)[[:space:]]+HEAD$ ]]; then branch=${BASH_REMATCH[1]}; fi
  done < <(clean_git ls-remote --symref "$1" HEAD)
  [[ $branch =~ ^[A-Za-z0-9._/-]+$ && $branch != *..* ]] || return 1
  printf '%s\n' "$branch"
}

# One file of the tip, written to DEST from the root clone. Its bytes must hash to the blob id the tree names. A third
# argument "optional": the tip may lack the file, and then nothing is written.
stage_blob() { # path in the repository, destination file[, optional]
  local path=$1 dest=$2 mode type blob rest
  read -r mode type blob rest < <(clean_git -C "$CLONE" ls-tree "$TIP" -- "$path") || true
  if [[ -z ${type:-} && ${3:-} == optional ]]; then return 0; fi
  [[ ${type:-} == blob && ${blob:-} =~ ^[0-9a-f]{40}$ ]] || die "the tip ${TIP:0:7} has no file $path"
  [[ $mode == 100644 || $mode == 100755 ]] || die "$path is mode $mode in the tip ${TIP:0:7}, not a regular file"
  mkdir -p "$(dirname "$dest")"
  clean_git -C "$CLONE" cat-file blob "$blob" > "$dest" || die "couldn't read $path ($blob) from the clone"
  [[ $(clean_git -C "$CLONE" hash-object --no-filters "$dest") == "$blob" ]] \
    || die "$path: the bytes staged do not hash to the blob id ${blob:0:12} the tree names"
}

# Everything setup installs, reads or runs, in the repository's own layout under ROOT: the broker and its catalog, the
# digest's other files, this script and its settings, the factory bundle's request client and runner pin, factory.json.
stage_tip() { # destination root
  local root=$1 f name
  for f in production/factory_op.py production/ops.json production/config.json gates.py ed25519.py \
           host/setup-production.sh host/production.conf host/factory-op-request host/setup.sh factory.json; do
    stage_blob ".github/factory/$f" "$root/.github/factory/$f"
  done
  # Optional: the receipt key's public half (setup prints it until it's committed).
  stage_blob ".github/factory/production/receipt.pub" "$root/.github/factory/production/receipt.pub" optional
  # Required here: the broker's own modules. This broker runs every step through its host module and refuses every command
  # without it, so a tip that lacks one stops now, not at the acceptance checks.
  for f in $BROKER_MODULES; do
    stage_blob ".github/factory/production/$f" "$root/.github/factory/production/$f" optional
    [[ -f $root/.github/factory/production/$f ]] \
      || die "the tip ${TIP:0:7} has no file .github/factory/production/$f: this broker runs every step through its host module, so nothing is set up without one (write it: process/factory-broker.md, the host module)"
  done
  # The operation scripts, if any (a Python operation needs none).
  while IFS= read -r -d '' name; do
    name=${name##*/}
    [[ $name == *.sh ]] || continue
    [[ $name =~ ^[A-Za-z0-9_][A-Za-z0-9._-]*\.sh$ ]] || die "production/ops/$name: not a script name setup installs"
    stage_blob ".github/factory/production/ops/$name" "$root/.github/factory/production/ops/$name"
  done < <(clean_git -C "$CLONE" ls-tree -z --name-only "$TIP" -- .github/factory/production/ops/)
}

fetch_tip() {
  clean_git -C "$CLONE" fetch --no-tags --quiet "$REMOTE_URL" "+refs/heads/$BRANCH:$SETUP_REF" || return 1
  TIP=$(clean_git -C "$CLONE" rev-parse --verify "$SETUP_REF^{commit}") && [[ $TIP =~ ^[0-9a-f]{40}$ ]]
}

ensure_deploy_key() {
  if [[ ! -s $ETC/github-deploy-key ]]; then
    ssh-keygen -q -t ed25519 -N '' -C "$TIER_NAME on $(hostname -s) for $REPO" -f "$ETC/github-deploy-key"
  fi
  chmod 600 "$ETC/github-deploy-key"; chown root:root "$ETC/github-deploy-key" "$ETC/github-deploy-key.pub"
  chmod 644 "$ETC/github-deploy-key.pub"
}

# GitHub's host keys from its API over TLS, not from a first connection.
ensure_known_hosts() {
  if env -i "PATH=$SAFE_PATH" LANG=C.UTF-8 python3 -I -c 'import json, urllib.request
for k in json.load(urllib.request.urlopen("https://api.github.com/meta", timeout=20))["ssh_keys"]:
    print("github.com " + k)' > "$WORK/known_hosts" && [[ -s $WORK/known_hosts ]]; then
    install -m 644 -o root -g root "$WORK/known_hosts" "$ETC/known_hosts"
  elif [[ ! -s $ETC/known_hosts ]]; then
    die "couldn't read GitHub's SSH host keys, so the deploy key's fetch can't be checked or used"
  fi
}

# The runner registration token file ($1): a regular file root or the sudo user owns, readable by nobody else, holding
# only a token. Opened once, without following a link; every check is made on the open file, and what was checked is
# copied to $2 (root-only), so a swap of the path after the check changes nothing. Nothing reads $1 again.
copy_token_file() {
  python3 -I - "$1" "$2" "${SUDO_UID:-0}" <<'PY'
import os, re, stat, sys
src, dest, sudo_uid = sys.argv[1], sys.argv[2], int(sys.argv[3])
try:
    fd = os.open(src, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
except OSError as e:
    sys.exit(f"{src}: {e.strerror} (it must be a regular file, not a link)")
st = os.fstat(fd)
if not stat.S_ISREG(st.st_mode):
    sys.exit(f"{src} must be a regular file")
if st.st_uid not in (0, sudo_uid):
    sys.exit(f"{src} is owned by uid {st.st_uid}, not root or the user running sudo")
if st.st_mode & 0o177:
    sys.exit(f"{src} has mode {st.st_mode & 0o777:o}: make it 0600 or tighter")
token = os.read(fd, 4096).decode("ascii", "replace").strip()
os.close(fd)
if not re.fullmatch(r"[A-Za-z0-9]{20,}", token):
    sys.exit(f"{src} doesn't hold only a registration token")
out = os.open(dest, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
os.write(out, token.encode())
os.close(out)
PY
}

# The commands setup needs, the signing library, and the settings production.conf must give.
check_settings() {
  local c
  for c in nft runuser systemd-run systemctl systemd-tmpfiles loginctl python3 git visudo ssh ssh-keygen install useradd usermod \
           passwd sudo ip curl pgrep timeout apt-get apt-cache dpkg-query flock env mktemp cmp diff sha256sum getent tar; do
    command -v "$c" >/dev/null || die "$c is not installed"
  done
  # Receipts are signed through OpenSSL 3 (ed25519.py: constant-time, key on a pipe), and the first call is `pubkey` after
  # the files are installed. LibreSSL can't sign, so it doesn't count. These candidates are ed25519.py's _openssls(), with
  # PATH as the wrapper sets it (env -i).
  local exe ver ssl3=
  for exe in "$(PATH=$BROKER_PATH command -v openssl || true)" /usr/bin/openssl /usr/local/bin/openssl /opt/homebrew/bin/openssl; do
    [[ -n $exe && -f $exe && -x $exe ]] || continue
    ver=$("$exe" version 2>/dev/null) || continue
    if [[ $ver =~ ^OpenSSL\ ([0-9]+)\. && ${BASH_REMATCH[1]} -ge 3 ]]; then ssl3=$exe; break; fi
  done
  [[ -n $ssl3 ]] || die "OpenSSL 3 or newer (not LibreSSL) is required to sign receipts: install the openssl package"
  [[ -n $RUNNER_NAME ]] || die "PROD_RUNNER_NAME is required: set it in host/production.conf (the runner's name)"
  [[ -n $AGENT_USER ]] || die "AGENT_USER is required: set it in host/production.conf (the agent sessions' login)"
}

# The interpreter every unit and the wrapper run, /usr/bin/python3, is at least the broker block's python ($1),
# compared as numbers.
check_python() {
  /usr/bin/python3 -I -c 'import sys; sys.exit(0 if sys.version_info[:2] >= tuple(int(x) for x in sys.argv[1].split(".")) else 1)' "$1" 2>/dev/null \
    || die "/usr/bin/python3 must be Python $1 or newer (ops.json's broker.python): every unit and the broker's command run it"
}

# systemd is at least SYSTEMD_FLOOR: a step's sandbox needs PrivateIPC= (systemd 248), and an older systemd would refuse the
# property, so every step would fail to start.
check_systemd() {
  local line
  line=$(systemctl --version 2>/dev/null | head -n 1) || true
  [[ $line =~ ^systemd\ ([0-9]+) ]] || die "can't read systemd's version (systemctl --version printed '${line:-nothing}')"
  ((BASH_REMATCH[1] >= SYSTEMD_FLOOR)) \
    || die "systemd $SYSTEMD_FLOOR or newer is required (this host has ${BASH_REMATCH[1]}): a production step's sandbox uses PrivateIPC=, which came in systemd 248"
}

# The default branch's production/config.json ($1) against factory.json's settings (resolve_settings read them): the
# environment the broker checks approvals in is factory.json's environments.production (config.json's environment, or
# the factory's default name), and its release branch is factory.json's release.branch.
config_matches_factory() {
  python3 -I - "$1" "$PROD_ENVIRONMENT" "$FACTORY_RELEASE_BRANCH" <<'PY'
import json, sys
path, env, release = sys.argv[1:4]
try:
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
except (OSError, ValueError) as e:
    sys.exit(f"can't read {path}: {e}")
if not isinstance(cfg, dict):
    sys.exit(f"{path} isn't an object")
mine = cfg.get("environment", "factory-production")
bad = []
if mine != env:
    bad.append(f"its environment is {mine!r} ({'set' if 'environment' in cfg else 'the default'}), but factory.json's "
               f"environments.production is {env!r}: the gate run waits on factory.json's, so the broker would find no "
               f"approval. Set config.json's environment to {env!r}")
if not release:
    bad.append("factory.json's release.branch is empty (the fallback, execution-PR gates): this broker is for the release "
               "branch model, D4 rule 13")
elif cfg.get("release_branch") != release:
    bad.append(f"its release_branch is {cfg.get('release_branch')!r}, but factory.json's release.branch is {release!r}")
if bad:
    sys.exit(f"{path}: " + "; ".join(bad))
PY
}

# This tier's step units that systemd doesn't report gone (factory_op.py's live_step_units): a broker stopped mid-step
# leaves its step running. Setup never swaps the package from under one. Dies naming them, or when systemd can't say.
refuse_live_steps() {
  local out line f live=()
  out=$(systemctl list-units --all --plain --no-legend --no-pager --full --type=service "$STEP_UNIT-*") \
    || die "can't ask systemd whether a step of $TIER_NAME is still running"
  while read -r line; do
    [[ -n $line ]] || continue
    read -r -a f <<< "$line"
    [[ ${f[0]} == "$STEP_UNIT-"* && -n ${f[2]:-} ]] || die "systemctl's list of $TIER_NAME's step units has a line setup can't read: $line"
    [[ ${f[2]} == inactive || ${f[2]} == failed ]] || live+=("${f[0]} (${f[2]})")
  done <<< "$out"
  ((${#live[@]} == 0)) || die "a step of $TIER_NAME is still running (${live[*]}): its broker was stopped before it was. Wait for it to end, or stop that unit by hand, then run setup again"
}

# The names of this tier already in use on the host: users, units, the nft table, its files and directories.
names_in_use() {
  local u f
  for u in "$RUNNER_USER" "$OP_USER" "$EGRESS_USER"; do
    if id "$u" > /dev/null 2>&1; then echo "user $u"; fi
  done
  for f in "/etc/systemd/system/$FW_UNIT.service" "/etc/systemd/system/$RUNNER_UNIT.service" \
           "/etc/systemd/system/$BROKER_UNIT.socket" "/etc/systemd/system/$EGRESS_UNIT.socket" \
           "/etc/systemd/system/$DRIFT_UNIT.timer" "$NFT_FILE" "$LIB" "$STATE" "$LOGS" "$ETC/config.json" "$BROKER_CMD" \
           "/etc/sudoers.d/$SUDOERS_NAME"; do
    if [[ -e $HOST_ROOT$f || -L $HOST_ROOT$f ]]; then echo "$f"; fi
  done
  if command -v nft > /dev/null && nft list table inet "$NFT_TABLE" > /dev/null 2>&1; then echo "nft table inet $NFT_TABLE"; fi
}

# On the tier's first run (no record yet) its names must be free. The one exception is this repository's own tier from
# before setup kept a record: its installed config.json (root's) names this repository. Anything else holding the
# names is another tier, or a setup that isn't this one's, and is refused before anything changes.
check_names_free() {
  local taken cfg_repo
  [[ ! -f $HOST_ROOT$TIER_RECORD ]] || return 0
  taken=$(names_in_use)
  [[ -n $taken ]] || return 0
  cfg_repo=$(python3 -I -c 'import json, sys; v = json.load(open(sys.argv[1], encoding="utf-8")).get("repo"); print(v if isinstance(v, str) else "")' \
    "$HOST_ROOT$ETC/config.json" 2>/dev/null || true)
  if [[ -n $cfg_repo && $cfg_repo == "$REPO" ]]; then
    echo "Production tier $TIER_NAME was set up for $REPO before setup kept a record: taking it over as $REPO's."
    return 0
  fi
  die "the names of production tier $TIER_NAME are in use, and not by $REPO's tier:
$taken
Give this tier its own PROD_INSTANCE in host/production.conf."
}

# The record of the repository that sets this tier up ($TIER_RECORD), made on the tier's first run from the repository
# root fetched (FACTORY_SETUP_REPO), and only when the operator named it (TIER_OWNER). A run for another repository is
# refused, so its production.conf can't reconfigure a tier it doesn't own.
claim_tier() {
  local repo=${FACTORY_SETUP_REPO:-}
  [[ -n $repo ]] || die "setup didn't say which repository root fetched: run it as sudo bash setup-production.sh"
  if [[ -f $TIER_RECORD ]]; then
    [[ $(<"$TIER_RECORD") == "$repo" ]] \
      || die "the production tier $TIER_NAME is set up from $(<"$TIER_RECORD"): remove $TIER_RECORD to hand it to $repo"
  else
    [[ ${TIER_OWNER:-} == "$repo" ]] \
      || die "no repository owns the production tier $TIER_NAME yet: if $repo should, run again with TIER_OWNER=$repo"
    install -d -m 755 -o root -g root "$ETC"
    printf '%s\n' "$repo" > "$TIER_RECORD"
    chmod 644 "$TIER_RECORD"
  fi
}

# The request client (the factory bundle's host/factory-op-request) serves every production tier on the host, finding
# its socket from the calling user. It is installed when absent and kept when byte-identical; one that differs is
# replaced only once the operator has seen the difference (printed here) and runs setup again with REPLACE_CLIENT=1,
# since another tier's setup may have installed it. Sets CLIENT_PLAN to install, same or replace.
client_plan() { # installed client, this tier's
  local installed=$1 new=$2
  [[ ! -L $installed ]] || die "$installed is a link: look at what it points to, then run setup again"
  if [[ ! -e $installed ]]; then CLIENT_PLAN=install; return 0; fi
  [[ -f $installed ]] || die "$installed isn't a regular file: look at it, then run setup again"
  if cmp -s "$installed" "$new"; then CLIENT_PLAN=same; return 0; fi
  echo "$installed differs from the factory bundle's host/factory-op-request:"
  diff -u "$installed" "$new" || true
  [[ ${REPLACE_CLIENT:-} == 1 ]] \
    || die "$installed differs from the factory bundle's client (above), and every production tier on this host runs it. If the new one should serve them all, run setup again with REPLACE_CLIENT=1"
  CLIENT_PLAN=replace
}

# The broker, its catalog, its config.json (the copy the broker reads, which the digest covers beside a host module), the
# digest's other files and the operation scripts, from the staged production directory ($1) and factory directory ($2)
# into the lib directory ($3): exactly what the tip holds, so the installed digest is the repository's
# (gates.installed_ops_files). A broker module or a script the tip no longer has is removed.
install_broker_files() {
  local prod=$1 factory=$2 lib=$3 m f
  install -m 644 -o root -g root "$prod/factory_op.py" "$prod/ops.json" "$prod/config.json" "$factory/gates.py" \
    "$factory/ed25519.py" "$lib/"
  for m in $BROKER_MODULES; do
    if [[ -f $prod/$m ]]; then install -m 644 -o root -g root "$prod/$m" "$lib/$m"; else rm -f "$lib/$m"; fi
  done
  for f in "$lib"/ops/*.sh; do
    [[ -e $f || -L $f ]] || continue
    [[ -f $prod/ops/${f##*/} ]] || rm -f "$f"
  done
  for f in "$prod"/ops/*.sh; do
    [[ -f $f ]] || continue
    install -m 644 -o root -g root "$f" "$lib/ops/"
  done
}

# A secret setup makes (and the receipt key): 32 random bytes as hex, written once to $1, root's alone after that.
ensure_hex_secret() {
  python3 -I - "$1" <<'PY'
import os, secrets, stat, sys
path = sys.argv[1]
try:
    st = os.lstat(path)
except FileNotFoundError:
    st = None
if st is not None and not stat.S_ISREG(st.st_mode):
    sys.exit(f"{path} isn't a regular file: look at it, then run setup again")
if st is None or st.st_size == 0:
    # A dot-prefixed name no declared secret can have (a secret's file starts with a letter or digit).
    tmp = os.path.join(os.path.dirname(path), "." + os.path.basename(path) + ".new")
    try:
        os.unlink(tmp)
    except FileNotFoundError:
        pass
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(secrets.token_hex(32) + "\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
os.chown(path, 0, 0, follow_symlinks=False)
os.chmod(path, 0o600)
PY
}

# The bootstrap stage. It runs from the checkout, so it reads nothing there but production.conf (as text) and the
# registration token, and ends in exec or die.
bootstrap_and_exec() {
  local c checkout d real token_copy v stage pass=()
  for c in git ssh ssh-keygen python3 flock install mktemp cmp env; do
    command -v "$c" > /dev/null || die "$c is not installed"
  done
  [[ -f $SCRIPT_DIR/production.conf ]] || die "$SCRIPT_DIR/production.conf is missing: the bundle seeds it; commit this tier's settings there"
  load_conf "$SCRIPT_DIR/production.conf"
  # The preflight first: a host that can't run the tier is refused before the bootstrap makes anything.
  check_settings
  check_systemd
  REPO=
  names
  REPO=$(tier_repo "$TIER_RECORD") || exit 1
  names
  # Before anything is made: another tier's names are never this one's.
  check_names_free
  # One setup at a time on a host, from before the fetch to the end of the staged copy, which inherits fd 7. The lock is
  # in a directory only root can write, so no one can plant a link where root opens it.
  install -d -m 711 -o root -g root "$SETUP_LOCK_DIR"
  exec 7> "$SETUP_LOCK"
  flock -n 7 || die "another setup is running on this host (it holds $SETUP_LOCK): let it finish first"
  checkout=$(cd "$FACTORY/../.." && pwd -P)
  # Never from a tier's own directory or a deploy directory: one sits at a deployed commit, which can be behind.
  collect_hidden "$ETC/config.json"
  for d in "$LIB" "$ETC" "$STATE" "$CLONE_BASE" "$RUN" ${HIDE_EXTRA[@]+"${HIDE_EXTRA[@]}"}; do
    real=$(cd "$d" 2>/dev/null && pwd -P) || continue
    [[ $checkout != "$real" && $checkout != "$real"/* ]] || die "this is $d: run setup from a separate clone of the default branch"
  done
  WORK=$(mktemp -d)
  trap 'rm -rf "$WORK"' EXIT
  token_copy=
  TOKEN_FILE=${TOKEN_FILE:-$SCRIPT_DIR/reg-token}
  if [[ -e $TOKEN_FILE || -L $TOKEN_FILE ]]; then
    token_copy=$WORK/reg-token
    copy_token_file "$TOKEN_FILE" "$token_copy" || die "the registration token file (above)"
  fi
  install -d -m 755 -o root -g root "$ETC" "$CLONE_BASE"
  ensure_deploy_key
  ensure_known_hosts
  [[ -d $CLONE ]] || clean_git init -q --bare "$CLONE"
  BRANCH=$(default_branch "$REMOTE_URL") || die "root couldn't read $REPO from GitHub with its deploy key. If the key isn't on the repository yet, add this as a read-only deploy key (the repository's Settings, Deploy keys, Allow write access off), then run setup again:
$(cat "$ETC/github-deploy-key.pub")"
  fetch_tip || die "root couldn't fetch $BRANCH from $REMOTE_URL. If the deploy key isn't on the repository yet, add this as a read-only deploy key, then run setup again:
$(cat "$ETC/github-deploy-key.pub")"
  stage=$WORK/stage
  stage_tip "$stage"
  # Not a check of the checkout (it can't be one): a reminder that what runs is the default branch's.
  cmp -s "$stage/.github/factory/host/setup-production.sh" "${BASH_SOURCE[0]}" \
    || die "this script differs from $BRANCH's tip (${TIP:0:7}): the checkout is behind or changed. Update it, or run setup from a fresh clone"
  cmp -s "$stage/.github/factory/host/production.conf" "$SCRIPT_DIR/production.conf" \
    || die "this checkout's host/production.conf isn't $BRANCH's (${TIP:0:7}): setup uses the default branch's, so commit its settings there first"
  [[ -z ${REPLACE_CLIENT:-} || $REPLACE_CLIENT == 1 ]] || die "REPLACE_CLIENT is 1 or unset"
  for v in TIER_OWNER REPLACE_CLIENT SUDO_USER SUDO_UID; do
    if [[ -n ${!v:-} ]]; then pass+=("$v=${!v}"); fi
  done
  trap - EXIT
  exec env -i "PATH=$SAFE_PATH" LANG=C.UTF-8 "FACTORY_SETUP_STAGED=$WORK" "FACTORY_SETUP_TIP=$TIP" \
    "FACTORY_SETUP_REPO=$REPO" "FACTORY_SETUP_BRANCH=$BRANCH" "FACTORY_SETUP_INSTANCE=$INSTANCE" \
    "FACTORY_SETUP_CHECKOUT=$checkout" "FACTORY_SETUP_TOKEN_FILE=$TOKEN_FILE" "FACTORY_SETUP_TOKEN_COPY=$token_copy" \
    ${pass[@]+"${pass[@]}"} /bin/bash "$stage/.github/factory/host/setup-production.sh" "$@"
}

# The staged copy's own checks: it runs only as the bootstrap left it.
staged_checks() {
  python3 -I -c 'import os, stat, sys
st = os.lstat(sys.argv[1])
sys.exit(0 if stat.S_ISDIR(st.st_mode) and st.st_uid == 0 and stat.S_IMODE(st.st_mode) == 0o700 else 1)' "$WORK" \
    || die "FACTORY_SETUP_STAGED isn't a root-only directory the bootstrap made"
  [[ ${BASH_SOURCE[0]} == "$WORK/stage/.github/factory/host/setup-production.sh" ]] || die "the staged copy runs only from $WORK/stage"
  [[ ${FACTORY_SETUP_REPO:-} =~ ^[A-Za-z0-9-]+/[A-Za-z0-9._-]+$ && ${FACTORY_SETUP_TIP:-} =~ ^[0-9a-f]{40}$ \
     && ${FACTORY_SETUP_BRANCH:-} =~ ^[A-Za-z0-9._/-]+$ ]] || die "the bootstrap named no repository, branch or tip"
  if ! [[ /dev/fd/7 -ef $SETUP_LOCK ]] || ! flock -n 7 2> /dev/null; then
    die "setup's lock isn't held: run setup as sudo bash setup-production.sh"
  fi
}

# ---- checks that decide something, as functions (the staged copy's) ------------------------------------------

# A user must be in no group but its own, have no sudo rules, and a locked password.
check_groups() {
  local u=$1 g primary extra
  primary=$(id -gn "$u")
  [[ $primary == "$u" ]] || die "$u's primary group is $primary, not $u"
  for g in sudo docker adm lpadmin; do
    if id -nG "$u" | tr ' ' '\n' | grep -qx "$g"; then die "$u must not be in group $g"; fi
  done
  extra=$(id -nG "$u" | tr ' ' '\n' | grep -vx "$u" || true)
  [[ -z $extra ]] || die "$u is in groups the script didn't create: $(echo "$extra" | tr '\n' ' ')"
  if sudo -l -U "$u" 2>/dev/null | grep -qE '^\s+\('; then die "$u must have no sudo rules"; fi
  [[ $(passwd -S "$u" | awk '{print $2}') == L ]] || die "$u's password isn't locked"
}

# This tier's socket groups (the runner's grants the broker socket, the operator's the egress socket) have no member but
# their own user, and no other tier's user is in one of them. (This tier's users are in no other group: check_groups.)
check_socket_groups() {
  local g u n members
  for g in "$RUNNER_USER" "$OP_USER" "$EGRESS_USER"; do
    members=$(getent group "$g" | cut -d: -f4)
    [[ -z $members ]] || die "group $g has members ($members): only its own user may be in it"
  done
  for n in ${OTHER_TIERS[@]+"${OTHER_TIERS[@]}"}; do
    for u in "$n" "$n-op" "$n-egress"; do
      id "$u" > /dev/null 2>&1 || continue
      for g in "$RUNNER_USER" "$OP_USER" "$EGRESS_USER"; do
        if id -nG "$u" | tr ' ' '\n' | grep -qx "$g"; then die "$u (tier $n) must not be in $g"; fi
      done
    done
  done
}

# A runner's settings file, read as that runner's own user (root never parses a file the runner can write): its field
# $3 equals $4. $1 is the user, $2 the file.
runner_field_is() {
  runuser -u "$1" -- timeout 10 python3 -I -c 'import json, os, sys
fd = os.open(sys.argv[1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
with os.fdopen(fd, encoding="utf-8-sig") as f:
    v = json.load(f).get(sys.argv[2])
sys.exit(0 if isinstance(v, str) and v.rstrip("/") == sys.argv[3] else 1)' "$2" "$3" "$4" 2>/dev/null
}

# Another tier's runner name is never this one's: registering with it would fail, or, with --replace, take that runner.
check_runner_name_free() {
  local n home
  for n in ${OTHER_TIERS[@]+"${OTHER_TIERS[@]}"}; do
    home=$(getent passwd "$n" | cut -d: -f6) || continue
    [[ -n $home && -f $home/actions-runner/.runner ]] || continue
    if runner_field_is "$n" "$home/actions-runner/.runner" agentName "$RUNNER_NAME"; then
      die "PROD_RUNNER_NAME $RUNNER_NAME is the runner name of production tier $n: give this tier's runner its own"
    fi
  done
  if [[ -f $RUNNER_DIR/.runner ]] && ! runner_field_is "$RUNNER_USER" "$RUNNER_DIR/.runner" gitHubUrl "$RUNNER_URL"; then
    die "$RUNNER_USER's runner isn't registered to $RUNNER_URL: never taken over here (look at $RUNNER_DIR/.runner)"
  fi
}

# Can USER connect to HOST:PORT over TCP? Quiet; the caller decides what the answer means.
connects() {
  runuser -u "$1" -- python3 -I -c 'import socket, sys; socket.create_connection((sys.argv[1], int(sys.argv[2])), timeout=5)' "$2" "$3" 2>/dev/null
}
root_connects() { python3 -I -c 'import socket, sys; socket.create_connection((sys.argv[1], int(sys.argv[2])), timeout=3)' "$1" "$2" 2>/dev/null; }

# The isolation probes for a user: every PROBE_PORTS port on every address of this machine (the other tiers' services:
# root reaches them, the user doesn't), and Tailscale's local API. Prints ok lines; returns 1 on a failure.
probe_isolation() {
  local u=$1 ip port rc=0
  [[ -n $PROBE_PORTS ]] || echo "note      PROBE_PORTS is empty: no service port is probed for $u"
  for ip in 127.0.0.1 $(ip -4 -o addr show scope global | awk '{print $4}' | cut -d/ -f1); do
    for port in $PROBE_PORTS; do
      if ! root_connects "$ip" "$port"; then
        echo "WARNING: nothing answers on $ip:$port for root either, so the probe there proves nothing"
      elif connects "$u" "$ip" "$port"; then
        echo "FAILED    $u reached $ip:$port"; rc=1
      else
        echo "ok        $ip:$port open to root, closed to $u"
      fi
    done
  done
  if [[ -S /run/tailscale/tailscaled.sock ]]; then
    if ! python3 -I -c 'import socket; socket.socket(socket.AF_UNIX).connect("/run/tailscale/tailscaled.sock")'; then
      echo "WARNING: root can't reach Tailscale's local API either, so the probe for $u proves nothing"
    elif runuser -u "$u" -- python3 -I -c 'import errno, socket, sys
sys.exit(0 if socket.socket(socket.AF_UNIX).connect_ex("/run/tailscale/tailscaled.sock") == errno.EACCES else 1)'; then
      echo "ok        Tailscale's local API refuses $u"
    else
      echo "FAILED    $u can reach Tailscale's local API (or wasn't refused for permission)"; rc=1
    fi
  fi
  return $rc
}

# Normalised view of the host's firewall outside this tier's table: handles and counters stripped, nft as JSON.
RULESET_PY=$(cat <<'PY'
import json, re, sys
kind, path = sys.argv[1], sys.argv[2]
raw = open(path, encoding="utf-8").read()
if kind == "nft":
    skip = sys.argv[3]
    def scrub(o):
        if isinstance(o, dict):
            return {k: (0 if k in ("packets", "bytes") else scrub(v)) for k, v in o.items() if k != "handle"}
        if isinstance(o, list):
            return [scrub(x) for x in o]
        return o
    for item in json.loads(raw)["nftables"]:
        if "metainfo" in item:
            continue
        (kind_name, obj), = item.items()
        table = obj.get("name") if kind_name == "table" else obj.get("table")
        if table == skip and obj.get("family") == "inet":
            continue
        print(json.dumps(scrub(item), sort_keys=True))
else:
    for line in raw.splitlines():
        if not line.startswith("#"):
            print(re.sub(r"\[\d+:\d+\]", "[0:0]", line))
PY
)
snapshot_firewall() { # directory to write nft.norm and iptables.norm into
  local d=$1
  nft -j list ruleset > "$d/nft.json" || die "nft -j list ruleset failed"
  python3 -I -c "$RULESET_PY" nft "$d/nft.json" "$NFT_TABLE" > "$d/nft.norm"
  if command -v iptables-save >/dev/null; then
    iptables-save > "$d/iptables.raw" 2>/dev/null || true
    python3 -I -c "$RULESET_PY" iptables "$d/iptables.raw" > "$d/iptables.norm"
  else
    : > "$d/iptables.norm"
  fi
}

# Another tier's own offline check ($1 its name): ok, failing or absent. Its command is root's (a root-owned regular
# file nobody else can write), or it isn't run.
tier_state() {
  local cmd=/usr/local/sbin/factory-op${1#factory-prod}
  [[ -f $cmd && ! -L $cmd && -x $cmd ]] || { echo absent; return; }
  python3 -I -c 'import os, sys; st = os.lstat(sys.argv[1]); sys.exit(0 if st.st_uid == 0 and not st.st_mode & 0o022 else 1)' "$cmd" \
    || { echo failing; return; }
  if timeout 300 "$cmd" check 2>/dev/null | python3 -I -c 'import json, sys; sys.exit(0 if json.load(sys.stdin).get("ok") is True else 1)' 2>/dev/null; then
    echo ok
  else
    echo failing
  fi
}

# Another tier's isolation probes for its runner user ($1 its name): ok, failing or absent.
tier_probe() {
  id "$1" > /dev/null 2>&1 || { echo absent; return; }
  if probe_isolation "$1" > /dev/null; then echo ok; else echo failing; fi
}

# One sandboxed operator step, as the broker runs them. Arguments: a name, Python source, its args.
op_step() {
  local name=$1 src=$2; shift 2
  systemd-run --unit="$STEP_UNIT-setup-$$-$name" --uid="$OP_USER" --gid="$OP_USER" --pipe --wait --collect --quiet \
    --working-directory="$PROBE_DIR" "${STEP_PROPS[@]}" -p "BindPaths=$PROBE_DIR" -p RuntimeMaxSec=90 \
    /usr/bin/python3 -I -c "$src" "$@"
}

SANDBOX_PY=$(cat <<'PY'
import errno, json, os, socket, sys
spec = json.loads(sys.argv[1])
bad = []
def refused(label, fn):
    try:
        fn()
    except OSError as e:
        print("ok        %s: %s" % (label, errno.errorcode.get(e.errno, e.errno)))
    else:
        print("FAILED    %s: it worked" % label)
        bad.append(label)
if os.geteuid() != spec["uid"]:
    print("FAILED    the step ran as uid %d, not %d" % (os.geteuid(), spec["uid"]))
    bad.append("uid")
for name in ("AF_INET", "AF_INET6", "AF_NETLINK", "AF_PACKET"):
    refused("socket(%s)" % name, lambda n=name: socket.socket(getattr(socket, n)))
def unix(p):
    err = None
    for kind in (socket.SOCK_STREAM, socket.SOCK_DGRAM):  # journald's and /dev/log are datagram sockets
        try:
            socket.socket(socket.AF_UNIX, kind).connect(p)
            return
        except OSError as e:
            err = e
    raise err
for p in spec["sockets"]:
    refused("connect " + p, lambda p=p: unix(p))
for p in spec["files"]:
    refused("read " + p, lambda p=p: open(p, "rb").read(1))
for p in spec["dirs"]:
    refused("list " + p, lambda p=p: os.listdir(p))
# The allowlist itself: /run holds this tier's directory, which holds the egress socket and the step's own directory.
for top, allowed in spec["only"]:
    try:
        seen = sorted(os.listdir(top))
    except OSError as e:
        print("FAILED    list %s: %s" % (top, errno.errorcode.get(e.errno, e.errno)))
        bad.append(top)
        continue
    extra = [n for n in seen if n not in allowed]
    if extra:
        print("FAILED    %s holds %s, beyond %s" % (top, " ".join(extra), " ".join(allowed)))
        bad.append(top)
    else:
        print("ok        %s holds only %s" % (top, " ".join(seen) or "nothing"))
sys.exit(1 if bad else 0)
PY
)

# Through the proxy: every egress host connects; TLS to the first works; hosts off the list, port 80 and a TLS hello
# naming another host than the CONNECT are refused. Arguments: the socket, the off-list host names, then the egress hosts.
PROXY_PY=$(cat <<'PY'
import socket, ssl, sys
sock_path, off_list, hosts = sys.argv[1], sys.argv[2].split(), sys.argv[3:]
first = hosts[0]
bad = []
def check(ok, label):
    print(("ok        " if ok else "FAILED    ") + label)
    if not ok:
        bad.append(label)
def connect(host, port):
    s = socket.socket(socket.AF_UNIX)
    s.settimeout(20)
    s.connect(sock_path)
    s.sendall(("CONNECT %s:%d HTTP/1.1\r\nHost: %s:%d\r\n\r\n" % (host, port, host, port)).encode())
    buf = b""
    while b"\r\n\r\n" not in buf and len(buf) < 8192:
        chunk = s.recv(4096)
        if not chunk:
            break
        buf += chunk
    parts = buf.split(b"\r\n", 1)[0].decode("latin-1").split()
    code = int(parts[1]) if len(parts) > 1 and parts[0].startswith("HTTP/") and parts[1].isdigit() else None
    return s, code
for host in hosts:
    s, code = connect(host, 443)
    check(code == 200, "CONNECT %s:443 answered %s" % (host, code))
    s.close()
s, code = connect(first, 443)
try:
    tls = ssl.create_default_context().wrap_socket(s, server_hostname=first)
    check(True, "TLS to %s through the proxy (%s)" % (first, tls.version()))
    tls.close()
except (OSError, ssl.SSLError) as e:
    check(False, "TLS to %s through the proxy: %s" % (first, e))
for host, port in [(h, 443) for h in off_list] + [(first, 80)]:
    try:
        s, code = connect(host, port)
        s.close()
    except OSError:
        code = None
    check(code is None or not 200 <= code < 300, "CONNECT %s:%d refused (answer %s)" % (host, port, code))
s, code = connect(first, 443)
try:
    ssl.create_default_context().wrap_socket(s, server_hostname=off_list[0])
    check(False, "a TLS hello for %s went through a tunnel to %s" % (off_list[0], first))
except (OSError, ssl.SSLError):
    check(True, "a TLS hello whose name differs from the CONNECT host is refused")
sys.exit(1 if bad else 0)
PY
)

HOSTS_PY=$(cat <<'PY'
import ipaddress, socket, sys
bad = 0
for host in sys.argv[1:]:
    addrs = {a[4][0] for a in socket.getaddrinfo(host, 443, socket.AF_INET, socket.SOCK_STREAM)}
    nonpublic = sorted(a for a in addrs if not ipaddress.ip_address(a).is_global)
    print("%s %s %s" % ("FAILED   " if nonpublic or not addrs else "ok       ", host, " ".join(sorted(addrs)) or "no A record"))
    bad += bool(nonpublic or not addrs)
sys.exit(1 if bad else 0)
PY
)

CONFIG_PY=$(cat <<'PY'
import json, sys
cfg = json.load(open(sys.argv[1], encoding="utf-8"))
want = dict(a.split("=", 1) for a in sys.argv[2:])
bad = [f"{k} is {cfg.get(k)!r}, setup installs {v!r}" for k, v in want.items() if cfg.get(k) != v]
print("\n".join(bad))
sys.exit(1 if bad else 0)
PY
)

jget() { python3 -I -c 'import json, sys; v = json.load(open(sys.argv[1], encoding="utf-8")).get(sys.argv[2]); print(v if isinstance(v, str) else "")' "$1" "$2"; }

# ---- what runs ------------------------------------------------------------------------------------------------

# A setting is production.conf's, never the environment's: one given after sudo would otherwise be silently ignored.
for v in $CONF_KEYS; do
  if declare -p "$v" > /dev/null 2>&1; then die "$v is a production.conf setting: commit it in host/production.conf, not on the command line"; fi
done
INSTANCE='' AGENT_USER='' RUNNER_NAME='' CONF_RUNNER_GROUP='' LAN_DNS='' PROBE_PORTS='' PROD_HOME_BASE='' REPO=''
OTHER_TIERS=() HIDE_TIERS=() HIDE_EXTRA=()

case ${1:-} in
  --print-settings|--print-step-props|--print-egress-hidden|--render)
    [[ $EUID -ne 0 ]] || die "run $1 without sudo: as root, setup reads only the default branch's files"
    HOST_ROOT=${FACTORY_HOST_ROOT:-}
    load_conf "${PRODUCTION_CONF:-$SCRIPT_DIR/production.conf}"
    REPO=
    names
    REPO=$(tier_repo "$HOST_ROOT$TIER_RECORD") || exit 1
    resolve_settings "${FACTORY_JSON:-$FACTORY/factory.json}" "$SCRIPT_DIR/setup.sh"
    [[ -n $AGENT_USER ]] || die "AGENT_USER is required: set it in host/production.conf (the agent sessions' login)"
    # The other tiers this host shows; this tier's own deploy directory joins them in the staged copy, from the default
    # branch's config.json.
    collect_hidden ""
    step_props
    case $1 in
      --print-settings) print_settings ;;
      --print-step-props) printf '%s\n' "${STEP_PROPS[@]}" | paste -d' ' - - ;;
      --print-egress-hidden) egress_hidden; echo ;;
      --render)
        [[ -n ${2:-} ]] || die "--render needs a directory"
        load_block "${OPS_JSON:-$PROD/ops.json}"
        RUID=${RENDER_RUID:-901} OPID=${RENDER_OPID:-902} EID=${RENDER_EID:-903}
        render_all "$2" ;;
    esac
    exit 0 ;;
esac

[[ $EUID -eq 0 ]] || die "run as root: sudo bash $0 (the tier's first run: sudo TIER_OWNER=<owner>/<repository> bash $0)"
for v in PRODUCTION_CONF OPS_JSON FACTORY_JSON FACTORY_HOST_ROOT; do
  [[ -z ${!v:-} ]] || die "$v is for --print-settings and --render: as root, setup reads the default branch's files"
done
if [[ -z ${FACTORY_SETUP_STAGED:-} ]]; then
  bootstrap_and_exec "$@"   # ends in exec of the staged copy, or in die
  exit 1                    # unreachable
fi

# ---- from here on this is the staged copy: root's own, from the root clone's fetch ------------------------------------
WORK=$FACTORY_SETUP_STAGED
PROBE_DIR=
# Checked before anything removes it: only the bootstrap's root-only directory is ever cleaned up.
staged_checks
cleanup() { rm -rf "$WORK" ${PROBE_DIR:+"$PROBE_DIR"}; }
trap cleanup EXIT
TIP=$FACTORY_SETUP_TIP BRANCH=$FACTORY_SETUP_BRANCH REPO=$FACTORY_SETUP_REPO
load_conf "$SCRIPT_DIR/production.conf"
[[ $INSTANCE == "${FACTORY_SETUP_INSTANCE-}" ]] \
  || die "the default branch's production.conf sets PROD_INSTANCE=$INSTANCE, but the bootstrap read ${FACTORY_SETUP_INSTANCE:-none}"
resolve_settings "$FACTORY/factory.json" "$SCRIPT_DIR/setup.sh"
[[ $(clean_git -C "$CLONE" rev-parse --verify "$SETUP_REF^{commit}") == "$TIP" ]] || die "the staged tip isn't the root clone's $SETUP_REF"
head=$TIP
PROBE_DIR=$RUN/steps/setup-probe-$$
check_settings
check_systemd
id "$AGENT_USER" > /dev/null 2>&1 || die "AGENT_USER $AGENT_USER isn't a login on this host"
load_block "$PROD/ops.json"
check_python "$PYTHON_MIN"
python3 -I -c "$CONFIG_PY" "$PROD/config.json" "instance=$INSTANCE" "repo=$REPO" "operator_user=$OP_USER" "lib_dir=$LIB" \
  "ledger=$STATE/ledger.jsonl" "log_dir=$LOGS" "clone_dir=$CLONE" "default_branch=$BRANCH" >&2 \
  || die "the default branch's production/config.json disagrees with this tier's names (above)"
RELEASE_BRANCH=$(jget "$PROD/config.json" release_branch)
[[ -n $RELEASE_BRANCH ]] || die "production/config.json's release_branch isn't set"
config_matches_factory "$PROD/config.json" || die "the default branch's production/config.json disagrees with its factory.json (above)"
# The other tiers, and every deploy directory: hidden from this tier, and never the checkout setup runs from.
collect_hidden "$PROD/config.json"
checkout=${FACTORY_SETUP_CHECKOUT:-}
for d in ${HIDE_EXTRA[@]+"${HIDE_EXTRA[@]}"}; do
  real=$(cd "$d" 2>/dev/null && pwd -P) || continue
  [[ -z $checkout || ( $checkout != "$real" && $checkout != "$real"/* ) ]] \
    || die "this checkout is in $d, a deploy directory: run setup from a separate clone of the default branch"
done
check_names_free
check_runner_name_free
client_plan "$CLIENT" "$SCRIPT_DIR/factory-op-request"
# The broker's own lock, from here until the broker's fetch at the end: a gate holds it for all its steps, so the package is
# never swapped under one (later steps would run code CD didn't approve), and the acceptance probes' step directory is
# safe from the broker's sweep of stale ones. Created 0600, as the broker makes it: anyone who could open it could hold it.
# Taken before anything changes, so a refusal here changes nothing. (fd 7 is setup's own lock.)
install -d -m 755 -o root -g root "$RUN"
umask 077
exec 9>>"$RUN/broker.lock"
umask 022
flock -w 120 9 || die "couldn't take $RUN/broker.lock within 120 s: a gate (or another broker command) is running. Nothing has changed; run setup again once it's done"
refuse_live_steps
# Decided: from here on the host changes.
claim_tier
step_props
echo "Other production tiers on this host: ${OTHER_TIERS[*]:-none}."

# Before anything changes: the host's firewall outside this tier's table, and each other tier's check and probes.
mkdir "$WORK/before" "$WORK/after"
snapshot_firewall "$WORK/before"
other_before=() other_probe_before=()
for n in ${OTHER_TIERS[@]+"${OTHER_TIERS[@]}"}; do
  other_before+=("$(tier_state "$n")") other_probe_before+=("$(tier_probe "$n")")
  echo "Tier $n before: check ${other_before[${#other_before[@]}-1]}, isolation probes ${other_probe_before[${#other_probe_before[@]}-1]}."
done

# ---- 1 users -------------------------------------------------------------------------------------------------------

log "1/8 users $RUNNER_USER, $OP_USER, $EGRESS_USER: no sudo, no docker, no foreign group"
install -d -m 755 "$PROD_HOME_BASE"
if ! id "$RUNNER_USER" >/dev/null 2>&1; then
  useradd --create-home --home-dir "$RUNNER_HOME" --shell /bin/bash --user-group "$RUNNER_USER"
fi
passwd -l "$RUNNER_USER" >/dev/null
chmod 750 "$RUNNER_HOME"
for u in "$OP_USER" "$EGRESS_USER"; do
  if ! id "$u" >/dev/null 2>&1; then
    useradd --system --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin --user-group "$u"
  fi
  usermod --shell /usr/sbin/nologin "$u"
  passwd -l "$u" >/dev/null
done
RUID=$(id -u "$RUNNER_USER"); OPID=$(id -u "$OP_USER"); EID=$(id -u "$EGRESS_USER")
for u in "$RUNNER_USER" "$OP_USER" "$EGRESS_USER"; do check_groups "$u"; done
check_socket_groups

# ---- 2 firewall ------------------------------------------------------------------------------------------------------

log "2/8 firewall: table $NFT_TABLE (loaded with nft -f only; nftables.service is never restarted or reloaded)"
render_firewall ""
systemctl daemon-reload
systemctl enable "$FW_UNIT.service" "$FW_UNIT-reapply.service" >/dev/null
if systemctl is-active --quiet "$FW_UNIT.service"; then nft -f "$NFT_FILE"; else systemctl start "$FW_UNIT.service"; fi
nft list table inet "$NFT_TABLE" >/dev/null || die "firewall table did not load"

# ---- 3 isolation drop-ins -----------------------------------------------------------------------------------------------

log "3/8 Tailscale and logind denials for the three users"
render_isolation ""
systemctl daemon-reload
if [[ -d /run/tailscale ]]; then
  command -v setfacl >/dev/null || die "setfacl is not installed (package acl): install it, then run setup again"
  setfacl -m "u:$RUNNER_USER:---" -m "u:$OP_USER:---" -m "u:$EGRESS_USER:---" /run/tailscale
fi
for u in "$RUNNER_USER" "$OP_USER" "$EGRESS_USER"; do loginctl disable-linger "$u" 2>/dev/null || true; done

# ---- 4 broker ----------------------------------------------------------------------------------------------------------

log "4/8 the broker, from $BRANCH's tip (${head:0:7}), staged from the root clone (setup holds the broker's lock)"
install -d -m 755 -o root -g root "$LIB" "$LIB/ops" "$ETC" "$CLONE_BASE"
install -d -m 700 -o root -g root "$STATE" "$LOGS"
install_broker_files "$PROD" "$FACTORY" "$LIB"
# The same staged blob, where other tiers' brokers and setups look for this tier (its deploy directory, the takeover check).
install -m 644 -o root -g root "$PROD/config.json" "$ETC/config.json"
render_wrapper ""
chown root:root "$BROKER_CMD"; chmod 755 "$BROKER_CMD"

# The request client (decided before step 1): written beside the old one and moved over it, so there is no moment
# without a client.
echo "Request client $CLIENT: $CLIENT_PLAN."
install -m 755 -o root -g root "$SCRIPT_DIR/factory-op-request" "$CLIENT.new"
mv -f "$CLIENT.new" "$CLIENT"

# Keys. The receipt key signs results; the deploy key (made by the bootstrap) is for the daily drift fetch. The broker
# block's secrets: setup writes each one it makes, once; CD writes the others by hand, and setup never reads them.
ensure_hex_secret "$ETC/receipt.key" || die "the receipt key (above)"
cd_actions=()
for i in ${SECRET_LABELS[@]+"${!SECRET_LABELS[@]}"}; do
  f=$ETC/${SECRET_FILES[$i]}
  if [[ ${SECRET_BY[$i]} == setup ]]; then
    ensure_hex_secret "$f" || die "the ${SECRET_LABELS[$i]} secret (above)"
  elif [[ -L $f ]]; then
    die "$f, the ${SECRET_LABELS[$i]} secret, is a link: write the secret itself there"
  elif [[ -f $f ]]; then
    read -r mode owner_group < <(stat -c '%a %U:%G' "$f")
    if [[ $mode != 600 || $owner_group != root:root ]]; then
      chmod 600 "$f"; chown root:root "$f"
      echo "WARNING: $f was $mode $owner_group and is now 600 root:root. If any other account could read it in the meantime, rotate it."
    fi
  else
    cd_actions+=("write the ${SECRET_LABELS[$i]} secret to $f by hand (root, 0600), over SSH, from the terminal")
  fi
done
pub=$("$BROKER_CMD" pubkey)
printf '%s\n' "$pub" > "$LIB/receipt.pub"; chmod 644 "$LIB/receipt.pub"
if [[ ! -f $PROD/receipt.pub || $(tr -d '[:space:]' < "$PROD/receipt.pub") != "$pub" ]]; then
  echo "ACTION NEEDED: commit this public key as .github/factory/production/receipt.pub (until then no gate result verifies):"
  echo "  $pub"
fi
# The clone was made and fetched by the bootstrap. The broker's `fetch` command (acceptance, and the drift timer) names
# the SSH command itself; nothing is configured in the clone. The operator reads the clone through its group; nobody else does.
chown -R "root:$OP_USER" "$CLONE"; chmod 755 "$CLONE_BASE"; chmod 750 "$CLONE"

# ---- 5 systemd ---------------------------------------------------------------------------------------------------------

log "5/8 systemd: broker socket, egress proxy socket, daily drift timer"
render_broker_units ""
systemd-tmpfiles --create "/etc/tmpfiles.d/$TIER_NAME.conf"
systemctl daemon-reload
systemctl enable --now "$BROKER_UNIT.socket" "$EGRESS_UNIT.socket" "$DRIFT_UNIT.timer" >/dev/null
systemctl restart "$BROKER_UNIT.socket" "$EGRESS_UNIT.socket"
[[ -S $RUN/op.sock ]] || die "the broker socket didn't come up"
[[ -S $RUN/egress.sock ]] || die "the egress proxy's socket didn't come up"

# ---- 6 runner ------------------------------------------------------------------------------------------------------------

log "6/8 GitHub Actions runner v$RUNNER_VERSION as $RUNNER_USER (name $RUNNER_NAME, label $RUNNER_LABELS, group $RUNNER_GROUP)"
# The runner's libraries (actions/runner v$RUNNER_VERSION, layoutbin/installdependencies.sh's Debian list), from apt as
# root, before anything is stopped or unpacked: the factory bundle's host/setup.sh's list (a test ties them), and acl for
# the Tailscale denial. A group is satisfied by any installed member, else by the first apt knows.
runner_deps() {
  local group pkg pick picks=()
  for group in "acl" "libkrb5-3" "zlib1g" "liblttng-ust1t64 liblttng-ust1 liblttng-ust0" "libssl3t64 libssl3 libssl1.1" \
               "libicu80 libicu79 libicu78 libicu77 libicu76 libicu75 libicu74 libicu73 libicu72 libicu71 libicu70 libicu69 libicu68 libicu67 libicu66"; do
    pick=
    for pkg in $group; do
      if dpkg-query -W -f '${Status}' "$pkg" 2>/dev/null | grep -q 'install ok installed'; then continue 2; fi
    done
    ((${#picks[@]})) || apt-get update -qq
    for pkg in $group; do apt-cache show "$pkg" > /dev/null 2>&1 && { pick=$pkg; break; }; done
    [[ -n $pick ]] || die "apt has no package for the runner's dependency ($group)"
    picks+=("$pick")
  done
  ((${#picks[@]})) || return 0
  # The picks aren't installed, but apt could still upgrade an installed library they need, and a library upgrade can
  # restart this host's other services (production's). Simulated first, so any upgrade or removal is the operator's.
  local plan upgrades removals
  plan=$(apt-get install -s -y --no-install-recommends "${picks[@]}") \
    || die "apt couldn't plan installing the runner's libraries (${picks[*]})"
  upgrades=$(awk '/^Inst / && $3 ~ /^\[/ {print $2}' <<< "$plan" | tr '\n' ' ')
  removals=$(awk '/^Remv / {print $2}' <<< "$plan" | tr '\n' ' ')
  [[ -z $removals ]] \
    || die "installing the runner's libraries (${picks[*]}) would remove ${removals% }: never done for you; resolve it by hand, then run setup again"
  [[ -z $upgrades ]] \
    || die "installing the runner's libraries (${picks[*]}) would upgrade ${upgrades% }: upgrade those when it suits this host, then run setup again"
  apt-get install -y --no-install-recommends "${picks[@]}"
}
runner_deps
# A command as the runner user, in directory $1, the rest its arguments: values reach it as arguments, never inside a
# shell string.
# shellcheck disable=SC2016  # the inner script's $1 and $@ are its own arguments
as_runner_in() { local dir=$1; shift; runuser -u "$RUNNER_USER" -- /bin/bash -c 'cd -- "$1" && shift && exec "$@"' as-runner "$dir" "$@"; }
runner_busy() { pgrep -u "$RUNNER_USER" -f "$RUNNER_DIR/bin/Runner.Worker" >/dev/null; }
# The installed version is the one this script recorded (root-owned), never asked of the runner's own files, which the
# runner user can write. The archive is downloaded and checked first, so a failed download leaves the runner as it was;
# a runner running a job is never stopped for an upgrade (looked at again after the download, which takes a while).
VERSION_FILE=$STATE/runner.version
installed=$(cat "$VERSION_FILE" 2>/dev/null || true)
fetch=
if [[ ! -x $RUNNER_DIR/config.sh ]]; then
  fetch=new
elif [[ $installed != "$RUNNER_VERSION" ]]; then
  if runner_busy; then
    echo "The runner is at ${installed:-an unknown version} and running a job: not upgraded to $RUNNER_VERSION. Re-run setup when idle."
  else
    fetch=upgrade
  fi
fi
if [[ -n $fetch ]]; then
  runuser -u "$RUNNER_USER" -- mkdir -p "$RUNNER_DIR" "$RUNNER_WORK"
  # shellcheck disable=SC2016  # the inner script's own arguments
  as_runner_in "$RUNNER_DIR" /bin/bash -c 'rm -f runner.tgz && curl -fsSL -o runner.tgz "$1" && printf "%s  runner.tgz\n" "$2" | sha256sum -c -' \
    download "https://github.com/actions/runner/releases/download/v$RUNNER_VERSION/actions-runner-linux-x64-$RUNNER_VERSION.tar.gz" \
    "$RUNNER_SHA256" \
    || { as_runner_in "$RUNNER_DIR" rm -f runner.tgz || true; die "couldn't download actions/runner v$RUNNER_VERSION (above): the runner is as it was"; }
  if [[ $fetch == upgrade ]] && runner_busy; then
    as_runner_in "$RUNNER_DIR" rm -f runner.tgz
    echo "The runner took a job during the download: not upgraded to $RUNNER_VERSION. Re-run setup when idle."
    fetch=
  fi
fi
if [[ -n $fetch ]]; then
  if [[ $fetch == upgrade ]]; then
    echo "Runner: ${installed:-an unknown version} -> $RUNNER_VERSION"
    systemctl stop "$RUNNER_UNIT.service" 2>/dev/null || true
  fi
  as_runner_in "$RUNNER_DIR" /bin/bash -c 'tar xzf runner.tgz && rm runner.tgz'
  printf '%s\n' "$RUNNER_VERSION" > "$VERSION_FILE"
fi
if [[ ! -f $RUNNER_DIR/.runner ]]; then
  if [[ -n ${FACTORY_SETUP_TOKEN_COPY:-} ]]; then
    # The bootstrap validated the file once and copied its content here (root-only); the original path is never read again.
    [[ $FACTORY_SETUP_TOKEN_COPY == "$WORK/reg-token" ]] || die "the token copy isn't the bootstrap's"
    token=$(<"$FACTORY_SETUP_TOKEN_COPY")
    [[ $token =~ ^[A-Za-z0-9]{20,}$ ]] || die "the staged registration token is malformed"
    # The runner reads any option from ACTIONS_RUNNER_INPUT_<NAME>; argv is world-readable in /proc, the environment of
    # a process isn't. Set as a prefix assignment, so it is in no argv here either (runuser keeps the environment). Never
    # --replace: a name another runner holds fails registration instead of displacing it.
    # shellcheck disable=SC2016  # the inner script's own arguments
    ACTIONS_RUNNER_INPUT_TOKEN=$token runuser -u "$RUNNER_USER" -- /bin/bash -c 'cd -- "$1" && shift && exec ./config.sh "$@"' config \
      "$RUNNER_DIR" --unattended --disableupdate --url "$RUNNER_URL" --runnergroup "$RUNNER_GROUP" --name "$RUNNER_NAME" \
      --labels "$RUNNER_LABELS" --work "$RUNNER_WORK"
    unset token
    rm -f "$FACTORY_SETUP_TOKEN_COPY" ${FACTORY_SETUP_TOKEN_FILE:+"$FACTORY_SETUP_TOKEN_FILE"}
  else
    echo "No registration token at ${FACTORY_SETUP_TOKEN_FILE:-<this dir>/reg-token}: the runner is installed but NOT registered. Re-run with the token file."
  fi
fi
if [[ -f $RUNNER_DIR/.runner ]]; then
  as_runner_in "$RUNNER_DIR" python3 -I -c 'import json; d = json.load(open(".runner", encoding="utf-8-sig")); d["disableUpdate"] = True; json.dump(d, open(".runner", "w"), indent=2)'
fi
# No job container (its one job talks to the socket), so never ACTIONS_RUNNER_REQUIRE_JOB_CONTAINER here.
as_runner_in "$RUNNER_DIR" /bin/bash -c 'touch .env && sed -i "/^ACTIONS_RUNNER_REQUIRE_JOB_CONTAINER=/d" .env && cp -f bin/runsvc.sh ./runsvc.sh && chmod 755 runsvc.sh'
render_runner_unit ""
systemctl daemon-reload
if [[ -f $RUNNER_DIR/.runner ]]; then
  systemctl enable "$RUNNER_UNIT.service" >/dev/null
  if runner_busy; then
    echo "The runner is running a job: $RUNNER_UNIT NOT restarted. Re-run setup when idle."
  else
    systemctl restart "$RUNNER_UNIT.service"
  fi
fi

# ---- 7 sudoers -----------------------------------------------------------------------------------------------------------

log "7/8 sudoers: $AGENT_USER may run check and health without a password"
install -d -m 755 /etc/sudoers.d
render_sudoers "$WORK/$SUDOERS_NAME"
visudo -cf "$WORK/$SUDOERS_NAME" >/dev/null || die "the generated sudoers file doesn't parse"
install -m 440 -o root -g root "$WORK/$SUDOERS_NAME" "/etc/sudoers.d/$SUDOERS_NAME"
visudo -c >/dev/null || die "sudoers doesn't parse after installing $SUDOERS_NAME"

# ---- 8 acceptance ------------------------------------------------------------------------------------------------------

log "8/8 acceptance checks"
failed=0
fail() { echo "FAILED    $*"; failed=1; }

# Other tables untouched: the ruleset outside this tier's table, nft and iptables, is what it was.
snapshot_firewall "$WORK/after"
if ! diff -u "$WORK/before/nft.norm" "$WORK/after/nft.norm" >/dev/null || ! diff -u "$WORK/before/iptables.norm" "$WORK/after/iptables.norm" >/dev/null; then
  sleep 3   # a rule another service adds while this runs (Docker, fail2ban) isn't ours: look again
  snapshot_firewall "$WORK/after"
fi
if diff -u "$WORK/before/nft.norm" "$WORK/after/nft.norm" && diff -u "$WORK/before/iptables.norm" "$WORK/after/iptables.norm"; then
  echo "ok        nft and iptables rules outside $NFT_TABLE are unchanged"
else
  fail "the firewall changed outside $NFT_TABLE (diff above; if another service changed a rule meanwhile, run setup again)"
fi

# The other tiers still work: each one's check, and its isolation probes for its runner, no worse than before.
for i in ${OTHER_TIERS[@]+"${!OTHER_TIERS[@]}"}; do
  n=${OTHER_TIERS[$i]}
  after=$(tier_state "$n")
  if [[ ${other_before[$i]} == ok && $after != ok ]]; then fail "tier $n's check was ok and is now $after"
  else echo "ok        tier $n's check: ${other_before[$i]} before, $after after"; fi
  if [[ ${other_probe_before[$i]} != absent ]]; then
    if probe_isolation "$n"; then
      echo "ok        tier $n's isolation probes for $n pass"
    elif [[ ${other_probe_before[$i]} == ok ]]; then
      fail "tier $n's isolation probes for $n passed before this run and fail now"
    else
      echo "WARNING: tier $n's isolation probes for $n failed before this run too"
    fi
  fi
done

# Groups, again, now that everything is installed.
for u in "$RUNNER_USER" "$OP_USER" "$EGRESS_USER"; do check_groups "$u"; done
check_socket_groups
echo "ok        $RUNNER_USER, $OP_USER and $EGRESS_USER are in no group but their own; no other tier's user is in theirs"

# The runner user: the probes, GitHub, its own broker socket and nobody else's.
probe_isolation "$RUNNER_USER" || fail "isolation probes for $RUNNER_USER (above)"
if connects "$RUNNER_USER" api.github.com 443; then echo "ok        $RUNNER_USER reaches api.github.com:443"; else fail "$RUNNER_USER can't reach api.github.com"; fi
if runuser -u "$RUNNER_USER" -- test -w "$RUN/op.sock"; then echo "ok        $RUNNER_USER may write $RUN/op.sock"; else fail "$RUNNER_USER can't write $RUN/op.sock"; fi
for n in ${OTHER_TIERS[@]+"${OTHER_TIERS[@]}"}; do
  for s in "/run/$n/op.sock" "/run/$n/egress.sock"; do
    [[ -S $s ]] || continue
    for u in "$RUNNER_USER" "$OP_USER" "$EGRESS_USER"; do
      if runuser -u "$u" -- test -w "$s"; then fail "$u may write tier $n's socket $s"
      else echo "ok        $u can't use tier $n's $s: a request client with a fixed path fails closed"; fi
    done
  done
done
for u in "$OP_USER" "$EGRESS_USER"; do
  if runuser -u "$u" -- test -w "$RUN/op.sock"; then fail "$u may write the broker socket"; else echo "ok        $u can't write the broker socket"; fi
done
if runuser -u "$RUNNER_USER" -- test -w "$RUN/egress.sock"; then fail "$RUNNER_USER may write the egress socket"; else echo "ok        $RUNNER_USER can't write the egress socket"; fi
if runuser -u "$EGRESS_USER" -- test -w "$RUN/egress.sock"; then fail "$EGRESS_USER may write its own socket"; else echo "ok        $EGRESS_USER can't write the egress socket"; fi
runuser -u "$OP_USER" -- test -w "$RUN/egress.sock" || fail "$OP_USER can't write the egress socket"

# The operator and the egress user, outside the sandbox: the nft chains.
gh_ip=$(python3 -I -c 'import socket; print(socket.gethostbyname("api.github.com"))')
for u in "$OP_USER" "$EGRESS_USER"; do
  runuser -u "$u" -- python3 -I -c 'pass' || fail "can't run Python as $u"
done
if connects "$OP_USER" "$gh_ip" 443; then fail "$OP_USER reached $gh_ip:443: its chain is not reject-all"; else echo "ok        $OP_USER's firewall chain refuses an outside address"; fi
if connects "$OP_USER" 127.0.0.53 53; then fail "$OP_USER reached the local resolver"; else echo "ok        $OP_USER's firewall chain refuses the local resolver"; fi
if connects "$EGRESS_USER" "$gh_ip" 443; then echo "ok        $EGRESS_USER reaches a public address on 443"; else fail "$EGRESS_USER can't reach $gh_ip:443"; fi
if connects "$EGRESS_USER" "$gh_ip" 80; then fail "$EGRESS_USER reached $gh_ip:80"; else echo "ok        $EGRESS_USER can't reach port 80"; fi
if connects "$EGRESS_USER" 127.0.0.1 22; then fail "$EGRESS_USER reached a host-local service"; else echo "ok        $EGRESS_USER can't reach host-local services"; fi
# Its own public addresses: a connection to one goes out on lo, past the public-address rule, so the chain rejects lo first.
egress_chain=$(nft list chain inet "$NFT_TABLE" egress_out 2>/dev/null || true)  # captured: grep -q in a pipe trips pipefail
if grep -q 'oifname "lo" .*reject' <<< "$egress_chain"; then
  echo "ok        the egress chain rejects anything on lo"
else
  fail "the egress chain has no lo rule"
fi
for ip in $(ip -4 -o addr show scope global | awk '{print $4}' | cut -d/ -f1); do
  if ! root_connects "$ip" 443; then
    echo "note      nothing answers on this host's $ip:443 for root, so the lo rule isn't probed there"
  elif connects "$EGRESS_USER" "$ip" 443; then
    fail "$EGRESS_USER reached this host's own $ip:443"
  else
    echo "ok        $EGRESS_USER can't reach this host's own $ip:443"
  fi
done
for u in "$OP_USER" "$EGRESS_USER"; do
  probe_isolation "$u" || fail "isolation probes for $u (above)"
done

# The operator, as a sandboxed step: no IP socket; no local socket but the egress proxy's (/run is empty); its own IPC, and
# none of the host's shared memory; no key or secret readable; this tier's state and every other tier's directories
# hidden; through the proxy only the egress hosts. Setup still holds the broker's lock (taken before step 1), so the
# broker's sweep of stale step directories can't remove the probes' directory.
install -d -m 700 -o "$OP_USER" -g "$OP_USER" "$PROBE_DIR"
# The host's local sockets a step must not reach, among them journald's (and /dev/log, its link), nscd's (DNS by another
# road), userdb's, CUPS's and snapd's: each one root can reach is probed, stream or datagram.
sockets=()
for s in /run/tailscale/tailscaled.sock /var/run/tailscale/tailscaled.sock /run/dbus/system_bus_socket \
         /run/systemd/resolve/io.systemd.Resolve /run/systemd/journal/socket /run/systemd/journal/stdout /dev/log \
         /run/nscd/socket /run/systemd/userdb/io.systemd.Multiplexer /run/cups/cups.sock /run/snapd.socket; do
  [[ -S $s ]] || continue
  if python3 -I -c 'import socket, sys
for kind in (socket.SOCK_STREAM, socket.SOCK_DGRAM):
    try:
        socket.socket(socket.AF_UNIX, kind).connect(sys.argv[1])
        sys.exit(0)
    except OSError:
        pass
sys.exit(1)' "$s" 2>/dev/null; then
    sockets+=("$s")
  else
    echo "WARNING: root can't connect to $s either, so the sandbox probe for it proves nothing"
  fi
done
files=()
for f in receipt.key github-deploy-key ${SECRET_FILES[@]+"${SECRET_FILES[@]}"}; do [[ -f $ETC/$f ]] && files+=("$ETC/$f"); done
[[ -f $STATE/ledger.jsonl ]] && files+=("$STATE/ledger.jsonl")
# The host's shared memory: a file root puts there must not be readable from the step.
shm_marker=
if [[ -d /dev/shm ]]; then
  shm_marker=/dev/shm/$TIER_NAME-probe-$$
  printf 'probe\n' > "$shm_marker"; chmod 644 "$shm_marker"
  files+=("$shm_marker")
fi
# A hidden path that doesn't exist on this host proves nothing, so only existing ones are probed.
hidden_dirs=("$STATE" "$LOGS")
for d in /dev/shm /dev/mqueue ${HIDE_TIERS[@]+"${HIDE_TIERS[@]}"} ${HIDE_EXTRA[@]+"${HIDE_EXTRA[@]}"}; do [[ -e $d ]] && hidden_dirs+=("$d"); done
spec=$(python3 -I -c 'import json, sys
run, tier, probe = sys.argv[5:8]
print(json.dumps({"uid": int(sys.argv[1]), "sockets": sys.argv[2].split(), "files": sys.argv[3].split(), "dirs": sys.argv[4].split(),
                  "only": [["/run", [tier]], [run, ["egress.sock", "steps"]], [run + "/steps", [probe]]]}))' \
  "$OPID" "${sockets[*]:-}" "${files[*]:-}" "${hidden_dirs[*]}" "$RUN" "$TIER_NAME" "${PROBE_DIR##*/}")
if op_step sandbox "$SANDBOX_PY" "$spec"; then echo "ok        the sandboxed operator step is boxed in (the other tiers' directories too)"; else fail "the sandboxed operator step isn't boxed in (above)"; fi
[[ -z $shm_marker ]] || rm -f "$shm_marker"
# The egress proxy's unit, as systemd loaded it: the other tiers' directories are in its InaccessiblePaths. (The running
# service is a template instance; `systemctl show` on an instance name loads the same settings.)
egress_inacc=$(systemctl show -p InaccessiblePaths --value "$EGRESS_UNIT@setup-probe.service" 2>/dev/null || true)
for d in ${HIDE_TIERS[@]+"${HIDE_TIERS[@]}"} ${HIDE_EXTRA[@]+"${HIDE_EXTRA[@]}"}; do
  case " $egress_inacc " in
    *" $d "*|*" -$d "*) echo "ok        the egress unit hides $d" ;;
    *) fail "the egress unit doesn't hide $d (InaccessiblePaths: ${egress_inacc:-none})" ;;
  esac
done
off_list=
for h in example.com example.org api.github.com; do [[ " ${EGRESS[*]} " == *" $h "* ]] || off_list+="${off_list:+ }$h"; done
if op_step proxy "$PROXY_PY" "$RUN/egress.sock" "$off_list" "${EGRESS[@]}"; then
  echo "ok        through the proxy: the egress hosts connect, an off-list host is refused"
else
  fail "the egress proxy probe (above)"
fi
rm -rf "$PROBE_DIR"
flock -u 9; exec 9>&-   # the broker's own fetch below takes the same lock

# The broker's own fetch (what the drift timer and the first baseline use): the release branch and the default branch
# into the bare clone, over SSH with the deploy key and $ETC/known_hosts. This is the real path, not a copy of it.
# Everything else is installed by now, so a failure here (usually the deploy key not yet added to the repository) fails
# the setup with the key to add; running setup again is safe.
if /usr/bin/python3 -I "$LIB/factory_op.py" fetch; then
  echo "ok        the broker's fetch reads $RELEASE_BRANCH and $BRANCH into the clone"
else
  fail "the broker's fetch failed. If the deploy key isn't on $REPO yet, add this as a read-only deploy key, then run setup again:
$(cat "$ETC/github-deploy-key.pub")"
fi

# The names the broker talks to resolve to public addresses.
python3 -I -c "$HOSTS_PY" "${EGRESS[@]}" || fail "a broker egress host doesn't resolve to a public IPv4 address"

systemctl is-active --quiet "$FW_UNIT.service" || fail "$FW_UNIT.service isn't active"
for u in "$BROKER_UNIT.socket" "$EGRESS_UNIT.socket" "$DRIFT_UNIT.timer"; do systemctl is-active --quiet "$u" || fail "$u isn't active"; done
((failed == 0)) || die "acceptance checks failed (above)"

log "check"
"$BROKER_CMD" check || echo "$BROKER_UNIT check found problems (above); fix them before approving a gate"
echo "Installed from ${head:0:7}. The next gate request's ops_digest must equal the one above, or the broker refuses it."
echo
echo "Then, if not done yet (process/factory-broker.md):"
for a in ${cd_actions[@]+"${cd_actions[@]}"}; do echo "  - ACTION NEEDED: $a;"; done
echo "  - python3 .github/factory/bootstrap.py: the environment $PROD_ENVIRONMENT (required reviewer you, deployable from"
echo "    $BRANCH only) and the runner group $RUNNER_GROUP (this repository only, the workflow"
echo "    $REPO/.github/workflows/factory-gate.yml@refs/heads/$BRANCH);"
echo "  - then: sudo $BROKER_CMD diagnose host-check (the host module's preflight, with the secrets in place)."
