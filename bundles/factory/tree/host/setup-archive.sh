#!/usr/bin/env bash
# The factory's evidence archive (process/factory.md D6 rule 7): installs evidence_archive.py, which pulls each
# factory run's browser evidence before GitHub's 90 days run out, as a user of its own on a systemd timer.
# Run as root on the host that keeps the archive, from a checkout no agent session can write:
#   sudo bash setup-archive.sh <root> <owner/repository> [<owner/repository> ...]
# <root> must already exist, on storage that survives a disk (a ZFS dataset with a quota and daily snapshots, say):
# creating it is the host's own business. The read-only token (Actions read on those repositories, nothing else)
# goes in /etc/factory-evidence/token, which this asks for on its first run and never echoes. Idempotent.
set -euo pipefail
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
[[ $(id -u) == 0 ]] || die "run as root"
(( $# >= 2 )) || die "usage: setup-archive.sh <root> <owner/repository> [...]"
root=$1; shift
# A plain path, two levels down at least, that isn't a system directory: setup hands it to the archive's user.
[[ $root =~ ^/[A-Za-z0-9._-]+(/[A-Za-z0-9._-]+)+$ && -d $root && ! -L $root ]] \
  || die "$root must be an existing absolute directory of plain characters, at least two levels down, not a link"
case $root in
  /bin/*|/boot/*|/dev/*|/etc/*|/lib*|/proc/*|/root/*|/run/*|/sbin/*|/sys/*|/usr/*|/var/lib/*|/var/log/*|/home/*)
    die "$root is under a system directory" ;;
esac
for r in "$@"; do [[ $r =~ ^[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}$ ]] || die "not owner/repository: $r"; done
here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
user=factory-evidence

id "$user" > /dev/null 2>&1 || useradd --system --home-dir /nonexistent --shell /usr/sbin/nologin "$user"
for g in sudo docker adm; do
  if id -nG "$user" | tr ' ' '\n' | grep -qx "$g"; then die "$user must not be in group $g"; fi
done
chown "$user:$user" "$root"
chmod 750 "$root"

install -d -m 755 /usr/local/lib/factory-evidence
install -m 644 -o root -g root "$here/evidence_archive.py" /usr/local/lib/factory-evidence/evidence_archive.py
install -d -m 750 -o root -g "$user" /etc/factory-evidence
if [[ ! -s /etc/factory-evidence/token ]]; then
  read -rsp "Read-only Actions token for $*: " token; echo
  [[ -n $token ]] || die "no token"
  umask 027; printf '%s\n' "$token" > /etc/factory-evidence/token; unset token
fi
chown root:"$user" /etc/factory-evidence/token; chmod 640 /etc/factory-evidence/token
python3 -I -c 'import json, sys; print(json.dumps({"root": sys.argv[1], "token_file": "/etc/factory-evidence/token",
  "repos": sys.argv[2:], "days": 90}, indent=2))' "$root" "$@" > /etc/factory-evidence/archive.json
chown root:"$user" /etc/factory-evidence/archive.json; chmod 640 /etc/factory-evidence/archive.json

cat > /etc/systemd/system/factory-evidence.service <<EOF
[Unit]
Description=Pull the factory's browser evidence into $root
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=$user
Group=$user
ExecStart=/usr/bin/python3 -I /usr/local/lib/factory-evidence/evidence_archive.py /etc/factory-evidence/archive.json
NoNewPrivileges=yes
ProtectSystem=strict
ReadWritePaths=$root
ProtectHome=yes
PrivateTmp=yes
EOF
cat > /etc/systemd/system/factory-evidence.timer <<'EOF'
[Unit]
Description=Pull the factory's browser evidence every six hours

[Timer]
OnBootSec=15min
OnUnitActiveSec=6h
Persistent=true

[Install]
WantedBy=timers.target
EOF
systemctl daemon-reload
systemctl enable --now factory-evidence.timer
echo "Installed. First pull: sudo systemctl start factory-evidence.service; journalctl -u factory-evidence"
echo "Set factory.json's evidence.archive to $root in each project, so its PRs name the path."
