# The CI tier's half of host setup (z-sdlc process/factory.md, Enablement step 10, The CI tier). Sourced by
# setup.sh for TIER=ci after its step 6: the runner user, its firewall, caps, delegated controllers, rootless
# Docker and the isolation test are in place, and setup.sh has checked the CI settings and the App's key. This adds
# the job image, the launcher's settings, the isolation checks (a gate at boot, the whole check every 6 hours, the
# firewall table every minute) and one systemd slot per concurrent job. Every slot runs ci_launcher.py: one
# disposable container per job, from a just-in-time runner registration. Root writes only root-owned files here,
# and builds and runs nothing of the project's: the runner user builds the image, from a root-owned copy of the
# build context.

LIB=/usr/local/lib/factory-runner
CONF_DIR=/etc/factory-runner/$RUNNER_UNIT
# On disk, not tmpfs: slot-N.runner names a registration a killed cycle left, and a reboot must not forget it.
STATE=/var/lib/factory-runner/$RUNNER_UNIT
CONF=$CONF_DIR/launcher.json
NEW_CONF=$CONF.new
TRIPPED=$CONF_DIR/tripped

log "7/8 CI tier: the runner-registration App, the runner group and the job image"
install -d -m 755 -o root -g root "$LIB" "$CONF_DIR"
install -d -m 711 -o root -g root /var/lib/factory-runner "$STATE"
# The state was on tmpfs before (a pre-release CI tier): its tmpfiles entry goes; its records move just before the
# slots restart, below.
rm -f "/etc/tmpfiles.d/$RUNNER_UNIT.conf"
install -m 644 -o root -g root "$SCRIPT_DIR/ci_launcher.py" "$LIB/ci_launcher.py"

# The jobs' caps need the cpu, memory and pids controllers delegated to the runner user (step 3 wrote the drop-in).
controllers=/sys/fs/cgroup/user.slice/user-$RUID.slice/user@$RUID.service/cgroup.controllers
delegated() { for c in cpu memory pids; do grep -qw "$c" "$controllers" 2> /dev/null || return 1; done; }
if ! delegated; then
  echo "Restarting user@$RUID.service for the delegated controllers (its rootless Docker restarts with it)."
  systemctl restart "user@$RUID.service"
  for _ in $(seq 30); do as_runner "docker info > /dev/null 2>&1" && break; sleep 1; done
fi
delegated || die "the cpu, memory and pids controllers aren't delegated to $RUNNER_USER: the jobs' caps wouldn't hold"

# The launcher's settings: everything a cycle and the checks need, root-owned, nothing secret but the key's path.
# Written whole to a new file, checked against GitHub and completed with the image, and only then put in place, so a
# run that fails partway leaves the slots the settings they had.
write_conf() {
  python3 -I - "$NEW_CONF" "$@" <<'PY'
import json, os, sys
path, pairs = sys.argv[1], sys.argv[2:]
try:
    with open(path) as f:
        conf = json.load(f)
except FileNotFoundError:
    conf = {}
for pair in pairs:
    key, value = pair.split("=", 1)
    conf[key] = json.loads(value)
with open(path + ".tmp", "w") as f:
    json.dump(conf, f, indent=2)
os.chmod(path + ".tmp", 0o644)
os.replace(path + ".tmp", path)
PY
}
json_str() { python3 -I -c 'import json,sys; print(json.dumps(sys.argv[1]))' "$1"; }
labels=$(python3 -I -c 'import json,sys; print(json.dumps([l.strip() for l in sys.argv[1].split(",") if l.strip()]))' "$RUNNER_LABELS")
rm -f "$NEW_CONF"
# The tier's table as loaded, for the checks: flushing a chain or a set leaves the table there, changed.
fw_print=$(python3 -I "$SCRIPT_DIR/ci_launcher.py" fingerprint "$NFT_TABLE") \
  || die "can't fingerprint firewall table $NFT_TABLE"
write_conf "api=\"https://api.github.com\"" "org=$(json_str "$FACTORY_ORG")" "client_id=$(json_str "$CI_APP_CLIENT_ID")" \
  "key=$(json_str "$CONF_DIR/app.pem")" "group=$(json_str "$RUNNER_GROUP")" "labels=$labels" \
  "name_prefix=$(json_str "$RUNNER_NAME_PREFIX-ci")" "container=$(json_str "$RUNNER_UNIT")" \
  "user=$(json_str "$RUNNER_USER")" "uid=$RUID" "gid=$(id -g "$RUNNER_USER")" "home=$(json_str "$RUNNER_HOME")" \
  "setpriv=$(json_str "$(command -v setpriv)")" "env=\"/usr/bin/env\"" "docker=$(json_str "$(command -v docker)")" \
  "python=\"/usr/bin/python3\"" "openssl=$(json_str "$(command -v openssl)")" "nft=$(json_str "$(command -v nft)")" \
  "systemctl=$(json_str "$(command -v systemctl)")" "loginctl=$(json_str "$(command -v loginctl)")" \
  "job={\"cpus\": $CI_JOB_CPUS, \"memory\": \"$CI_JOB_MEMORY\", \"pids\": $CI_JOB_PIDS, \"shm\": \"$CI_JOB_SHM\", \"hours\": $CI_JOB_HOURS}" \
  "idle_hours=$CI_IDLE_HOURS" "min_free_gb=$CI_MIN_FREE_GB" \
  "state_dir=$(json_str "$STATE")" "tripped=$(json_str "$TRIPPED")" "unit=$(json_str "$RUNNER_UNIT")" \
  "firewall_table=$(json_str "$NFT_TABLE")" "cgroup=$(json_str "/sys/fs/cgroup/user.slice/user-$RUID.slice")" \
  "probe={\"targets\": $(json_str "$targets"), \"ports\": $(json_str "$ports")}" "firewall_fingerprint=$(json_str "$fw_print")"
ids=$(python3 -I "$LIB/ci_launcher.py" resolve "$NEW_CONF") || die "the runner-registration App or the runner group isn't ready (above)"
write_conf "installation_id=$(python3 -I -c 'import json,sys; print(json.loads(sys.argv[1])["installation_id"])' "$ids")" \
  "group_id=$(python3 -I -c 'import json,sys; print(json.loads(sys.argv[1])["group_id"])' "$ids")"

# The job image: the project's toolchain (factory.json's ci block), then the runner (ci-runner.Dockerfile). Root
# stages the build context from its own clone of the default branch, at the commit setup runs from, never from the
# checkout, into a root-owned directory the runner user reads; the runner user builds.
# Each path a plain one inside the repository: the tree, not the checkout, says what it is.
{ IFS= read -r dockerfile && IFS= read -r context; } < <(python3 -I - "$FACTORY_JSON" <<'PY'
import json, posixpath, sys
ci = json.load(open(sys.argv[1])).get("ci") or {}
for key in ("dockerfile", "context"):
    path = ci.get(key) or ""
    norm = posixpath.normpath(path) if path else ""
    if not path or path.startswith("/") or any(c.isspace() or not c.isprintable() for c in path) \
            or norm == ".." or norm.startswith("../") or (key == "dockerfile" and norm == "."):
        sys.exit(f"factory.json's ci.{key}: a path inside the repository, got {path!r}")
    print(norm)
PY
) || die "factory.json's ci block names no toolchain Dockerfile and context inside the repository (above)"
build_args=$(python3 -I - "$FACTORY_JSON" <<'PY'
import json, re, shlex, sys
args = (json.load(open(sys.argv[1])).get("ci") or {}).get("build_args") or {}
for k, v in args.items():
    if not re.fullmatch(r"[A-Z_][A-Z0-9_]*", k) or not isinstance(v, str) or "\n" in v:
        sys.exit(f"factory.json's ci.build_args: {k!r}")
    print(shlex.quote(f"--build-arg={k}={v}"), end=" ")
PY
) || die "factory.json's ci.build_args (above)"
# Under /var/lib/factory-runner, root's all the way up: under RUNNER_HOME_BASE, whoever owns a directory above it could
# swap the context between root's copy and the build.
build=$(mktemp -d /var/lib/factory-runner/ci-build.XXXXXX)
chmod 755 "$build"
# Links are staged as links, never followed, so nothing outside the context comes along. chmod -R skips links.
stage_tree dir "$FACTORY_SETUP_CLONE" "$FACTORY_SETUP_TIP" "$build/toolchain" "$context" \
  || { rm -rf "$build"; die "factory.json's ci.context ($context) isn't a directory of the tip ${FACTORY_SETUP_TIP:0:7} (above)"; }
stage_tree files "$FACTORY_SETUP_CLONE" "$FACTORY_SETUP_TIP" "$build/dockerfile" "$dockerfile" \
  && mv "$build/dockerfile/$dockerfile" "$build/toolchain.Dockerfile" && rm -rf "$build/dockerfile" \
  || { rm -rf "$build"; die "factory.json's ci.dockerfile ($dockerfile) isn't a file of the tip ${FACTORY_SETUP_TIP:0:7} (above)"; }
install -d -m 755 "$build/runner" && cp "$SCRIPT_DIR/ci-runner.Dockerfile" "$build/runner/Dockerfile"
chown -R -h root:root "$build" && chmod -R a+rX "$build"
# The job image is kept while its inputs are unchanged (the context and Dockerfiles as copied, the build arguments, the
# runner's version) and it's still there: rebuilding the same inputs still makes a new image, whose package steps
# resolve again, and churns the prune. CI_REBUILD=1 on setup's command line rebuilds anyway, for the base image's and
# packages' updates: sudo CI_REBUILD=1 TIER=ci bash .github/factory/host/setup.sh
inputs=$(python3 -I "$SCRIPT_DIR/ci_launcher.py" inputs "$build" "$build_args" "$RUNNER_VERSION" "$RUNNER_SHA256") \
  || { rm -rf "$build"; die "can't fingerprint the job image's inputs"; }
read -r old_inputs old_image < <(python3 -I -c 'import json,sys
try:
    conf = json.load(open(sys.argv[1]))
except (OSError, ValueError):
    conf = {}
print(conf.get("image_inputs") or "-", conf.get("image") or "-")' "$CONF")
if [[ ${CI_REBUILD:-} != 1 && $inputs == "$old_inputs" && $old_image =~ ^sha256:[0-9a-f]{64}$ ]] \
    && as_runner "docker image inspect '$old_image' > /dev/null 2>&1"; then
  rm -rf "$build"
  image=$old_image
  echo "job image kept (its inputs are unchanged; CI_REBUILD=1 rebuilds it)"
else
  as_runner "docker build -q -f '$build/toolchain.Dockerfile' $build_args -t $RUNNER_UNIT-toolchain:latest '$build/toolchain' > /dev/null" \
    || { rm -rf "$build"; die "the toolchain image didn't build"; }
  # Labelled factory.keep: the weekly prune never takes the job image, which nothing uses between jobs.
  as_runner "docker build -q --label factory.keep=1 --build-arg BASE=$RUNNER_UNIT-toolchain:latest \
    --build-arg RUNNER_VERSION=$RUNNER_VERSION --build-arg RUNNER_SHA256=$RUNNER_SHA256 -t $RUNNER_UNIT-runner:latest \
    '$build/runner' > /dev/null" \
    || { rm -rf "$build"; die "the runner image didn't build"; }
  rm -rf "$build"
  image=$(as_runner "docker image inspect -f '{{.Id}}' $RUNNER_UNIT-runner:latest") || die "no runner image"
  [[ $image =~ ^sha256:[0-9a-f]{64}$ ]] || die "no runner image"
  # Earlier job images, unless a running job still uses one (the runner user lists and removes them; root reads none).
  as_runner "docker image ls -q --no-trunc --filter label=factory.keep | grep -vx '$image' | xargs -r docker image rm > /dev/null 2>&1" || true
fi
write_conf "image=$(json_str "$image")" "image_inputs=$(json_str "$inputs")"
mv -f "$NEW_CONF" "$CONF"
echo "job image: $image"

log "8/8 CI tier: the isolation checks, then $RUNNER_COUNT slot(s)"
launcher="/usr/bin/python3 -I $LIB/ci_launcher.py"
# The gate runs the check before any slot starts (at boot too), a timer runs it every 6 hours, and another checks the
# firewall table every minute. A failure, or a check that doesn't finish, writes $TRIPPED, which no slot starts past,
# and stops the slots, the timers and the runner user's whole session, a job mid-run included. It disables the slots,
# the gate, the timers and the runner user's linger too, so a reboot starts none of it: this run of setup enables
# them again (below, and step 4's linger).
cat > "/etc/systemd/system/$RUNNER_UNIT-trip.service" <<EOF
[Unit]
Description=Stop the $RUNNER_USER slots: an isolation check failed or didn't finish

[Service]
Type=oneshot
ExecStart=$launcher trip $CONF
EOF
cat > "/etc/systemd/system/$RUNNER_UNIT-gate.service" <<EOF
[Unit]
Description=Isolation check before the $RUNNER_USER slots start
Requires=$FW_UNIT.service user@$RUID.service
Wants=network-online.target
After=$FW_UNIT.service user@$RUID.service network-online.target
ConditionPathExists=!$TRIPPED
OnFailure=$RUNNER_UNIT-trip.service

[Service]
Type=oneshot
RemainAfterExit=yes
TimeoutStartSec=30min
ExecStart=$launcher check $CONF

[Install]
WantedBy=multi-user.target
EOF
# No Requires= on user@: the timer's check is skipped while the tier is tripped, and must not start the runner user's
# manager either way (a unit's condition doesn't stop its Requires= from starting).
cat > "/etc/systemd/system/$RUNNER_UNIT-check.service" <<EOF
[Unit]
Description=Isolation check for the $RUNNER_USER slots (stops them on failure)
After=user@$RUID.service
ConditionPathExists=!$TRIPPED
OnFailure=$RUNNER_UNIT-trip.service

[Service]
Type=oneshot
TimeoutStartSec=30min
ExecStart=$launcher check $CONF
EOF
cat > "/etc/systemd/system/$RUNNER_UNIT-check.timer" <<EOF
[Unit]
Description=Isolation check for the $RUNNER_USER slots, every 6 hours

[Timer]
OnBootSec=6h
OnUnitActiveSec=6h

[Install]
WantedBy=timers.target
EOF
cat > "/etc/systemd/system/$RUNNER_UNIT-fw.service" <<EOF
[Unit]
Description=Firewall table check for the $RUNNER_USER slots (stops them if it's gone)
ConditionPathExists=!$TRIPPED
OnFailure=$RUNNER_UNIT-trip.service

[Service]
Type=oneshot
TimeoutStartSec=2min
ExecStart=$launcher fwcheck $CONF
EOF
cat > "/etc/systemd/system/$RUNNER_UNIT-fw.timer" <<EOF
[Unit]
Description=Firewall table check for the $RUNNER_USER slots, every minute

[Timer]
OnBootSec=1min
OnUnitActiveSec=1min
AccuracySec=5s

[Install]
WantedBy=timers.target
EOF
# SIGTERM goes to the launcher alone (KillMode=mixed), which removes its container and registration before it exits.
cat > "/etc/systemd/system/$RUNNER_UNIT-slot@.service" <<EOF
[Unit]
Description=CI tier slot %i: one disposable runner per job ($RUNNER_USER)
Requires=$FW_UNIT.service user@$RUID.service $RUNNER_UNIT-gate.service
After=$FW_UNIT.service user@$RUID.service $RUNNER_UNIT-gate.service network-online.target
ConditionPathExists=!$TRIPPED

[Service]
Type=simple
ExecStart=$launcher run $CONF %i
ExecStopPost=$launcher stop $CONF %i
Restart=always
RestartSec=5
KillMode=mixed
# Above the launcher's worst-case cleanup: docker rm (120 s), then the token (openssl 30 s, the API 30 s) and the
# registration's removal (30 s), all of it twice over for a refused token minted again: 300 s, with room.
TimeoutStopSec=360

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
# A run of setup is the operator's say that the cause of a trip is fixed; the check must still pass. It runs here,
# not by restarting the gate: the slots require the gate, and restarting it would restart them, killing their jobs.
rm -f "$TRIPPED"
$launcher check "$CONF" || die "the CI tier's isolation check failed (above): no slot starts"
systemctl enable --now "$RUNNER_UNIT-gate.service" "$RUNNER_UNIT-check.timer" "$RUNNER_UNIT-fw.timer" > /dev/null
# Records a cycle left on the old tmpfs state (a host upgrading from a pre-release CI tier) move into the state as
# leftovers, which the slots' cycles, their stop and retire all read. Moved only now, once the slots' settings name the
# new state, so no cycle started from here on writes there; one a cycle started earlier writes later is read where it
# is (the launcher looks there too). As leftovers, never over a slot's current record.
for f in /run/factory-runner/"$RUNNER_UNIT"/slot-*.runner; do
  [[ -f $f && ! -L $f ]] || continue
  id=$(<"$f") n=${f##*/slot-}
  n=${n%.runner}
  if [[ $id =~ ^[0-9]+$ && $n =~ ^[0-9]+$ ]]; then mv -f "$f" "$STATE/slot-$n.leftover-$id"; else rm -f "$f"; fi
done
# A slot running a job keeps it, and takes this run's launcher and settings at its next cycle. A slot whose runner
# isn't running one is restarted, so it takes them now: an idle runner's next cycle can be CI_IDLE_HOURS away (and a
# runner registered with an old label set would wait for it). retire asks GitHub about each registration the slot
# holds and deregisters an idle one, which GitHub also refuses once it has a job, and answers 10 only when they're all
# gone: any other answer, an error's included, leaves the slot alone and says why.
for i in $(seq "$RUNNER_COUNT"); do
  if systemctl is-active --quiet "$RUNNER_UNIT-slot@$i.service"; then
    idle=0
    $launcher retire "$CONF" "$i" || idle=$?
    if ((idle == 10)); then
      systemctl restart "$RUNNER_UNIT-slot@$i.service"
    else
      echo "Slot $i is running a job, or its runner couldn't be retired: not restarted. It takes this run's launcher and settings at its next cycle."
    fi
  fi
  systemctl enable --now "$RUNNER_UNIT-slot@$i.service" > /dev/null
done
# Slots beyond RUNNER_COUNT, enabled or running, are stopped (each removes its container and registration).
for unit in $({ ls /etc/systemd/system/multi-user.target.wants/ 2> /dev/null
                systemctl list-units --all --plain --no-legend "$RUNNER_UNIT-slot@*.service" | awk '{print $1}'; } \
              | grep -E "^$RUNNER_UNIT-slot@[0-9]+\.service$" | sort -u); do
  n=${unit#"$RUNNER_UNIT-slot@"}
  n=${n%.service}
  if ((n > RUNNER_COUNT)); then systemctl disable --now "$unit" > /dev/null 2>&1 || true; fi
done
systemctl --no-pager --lines=0 status "$RUNNER_UNIT-slot@*" | grep -E '●|Active:' || true
