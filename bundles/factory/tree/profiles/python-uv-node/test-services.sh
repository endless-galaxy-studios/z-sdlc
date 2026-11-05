#!/usr/bin/env bash
# Start throwaway Postgres 17 (with pgvector) and Redis 7 for a stage that runs the test suite, on the job
# container's loopback (127.0.0.1:5432 and :6379), plus Unix sockets under <dir> for this script.
# Sandboxed Bash reaches the loopback ports through with-test-services, which forwards them over the
# sandbox's HTTP proxy (the sandbox blocks Unix sockets and has a loopback of its own).
# Run as root before the agent starts (copied out of the workspace first, like every check);
# each server runs as its own user. Prints the settings, for the project's env file (agent_job.sh services):
# only DATABASE_URL and REDIS_URL, since a project's settings may refuse a key they don't define. The test
# database's and test Redis's URLs (<database>_test, db 15) are exported by with-test-services instead.
# The servers run outside the sandbox with open network access, so the agent must not be able to
# make them run code: the only Postgres login is the project's (<database>, also its role), which can
# create databases but isn't a superuser (a superuser can run shell commands with COPY ... TO PROGRAM); Redis denies the commands
# that run code, change its config or open connections (MIGRATE, REPLICAOF). Both start with an
# empty environment, so they never hold the step's tokens. The script checks all of this before it
# returns. The data is disposable: no fsync, gone with the container.
# Usage: test-services.sh <socket-dir> <database>
set -euo pipefail

dir=$1 db=$2
[[ $db =~ ^[a-z_][a-z0-9_]*$ ]] || { echo "test-services: bad database name $db" >&2; exit 1; }
pgbin=/usr/lib/postgresql/17/bin
data=/var/lib/postgresql/factory
# EVAL stays enabled (projects script Redis with Lua), so Redis must carry the 2025 Lua fixes (CVE-2025-49844,
# -46817, -46818, -46819; Debian DSA-6020-1). Debian backports them without changing 7.0.15, so the
# package version is what counts. The image build checks this too; this catches an older pinned image.
redis_floor='5:7.0.15-1~deb12u6'
redis_pkg=$(dpkg-query -W -f '${Version}' redis-server)
dpkg --compare-versions "$redis_pkg" ge "$redis_floor" \
  || { echo "redis-server $redis_pkg predates the Lua fixes ($redis_floor); rebuild the job image" >&2; exit 1; }
# Each server process gets only these variables.
as() { local user=$1; shift; env -i PATH=/usr/sbin:/usr/bin:/sbin:/bin LANG=C.UTF-8 runuser -u "$user" -- "$@"; }

install -d -m 755 "$dir"
install -d -m 755 -o postgres -g postgres "$dir/pg" "$data"
chmod 700 "$data"
install -d -m 755 -o redis -g redis "$dir/redis"

as postgres "$pgbin/initdb" -D "$data" -U postgres --auth-local=peer --auth-host=reject > /dev/null
as postgres "$pgbin/pg_ctl" -D "$data" -l "$data/server.log" -w start \
  -o "-c listen_addresses=127.0.0.1 -c unix_socket_directories='$dir/pg' -c fsync=off -c full_page_writes=off" > /dev/null
# pgvector isn't a trusted extension, so the role can't create it. The superuser installs it in template1,
# in a schema of its own, so every database made from template1 has it: the project's, its test database,
# any scratch database a test makes. In its own schema, a test teardown's DROP SCHEMA public CASCADE leaves it
# alone (in public, the cascade would drop it and the role couldn't create it again), and the role's
# search_path finds it unqualified. The role can't drop or move it: it doesn't own it.
as postgres psql -q -h "$dir/pg" -U postgres -d template1 \
  -c "CREATE SCHEMA extensions" -c "GRANT USAGE ON SCHEMA extensions TO PUBLIC" \
  -c "CREATE EXTENSION vector SCHEMA extensions"
# The test harness creates its own test database, so the role needs CREATEDB; no migration needs a superuser.
as postgres psql -q -h "$dir/pg" -U postgres -d postgres \
  -c "CREATE ROLE $db LOGIN CREATEDB" -c "ALTER ROLE $db SET search_path = \"\$user\", public, extensions" \
  -c "CREATE DATABASE $db OWNER $db"
# From here on only the project's role can log in (trust: the socket is the boundary); postgres is refused.
printf 'local all %s trust\nhost all %s 127.0.0.1/32 trust\nlocal all all reject\nhost all all all reject\n' "$db" "$db" \
  > "$data/pg_hba.conf"
as postgres "$pgbin/pg_ctl" -D "$data" reload > /dev/null

as redis redis-server --bind 127.0.0.1 --port 6379 --unixsocket "$dir/redis/redis.sock" --unixsocketperm 777 \
  --save '' --appendonly no --dir /tmp --daemonize yes --logfile /tmp/factory-redis.log \
  --enable-module-command no --enable-debug-command no --enable-protected-configs no \
  --set-proc-title no --sanitize-dump-payload yes \
  --user default on nopass '~*' '&*' +@all -migrate -replicaof -slaveof -module -config -debug -acl \
    -monitor -sync -psync -failover -cluster -shutdown -save -bgsave -bgrewriteaof -restore -restore-asking -function
for _ in $(seq 50); do [ -S "$dir/redis/redis.sock" ] && break; sleep 0.1; done
[ -S "$dir/redis/redis.sock" ] || { echo "redis did not start" >&2; exit 1; }

# Fail closed if the lockdown didn't take.
fail() { echo "test-services: $1" >&2; exit 1; }
# The project's role: no superuser, no role creation, no membership (pg_execute_server_program and the file roles).
[ "$(psql -h "$dir/pg" -U "$db" -d "$db" -tAc "select rolsuper or rolcreaterole
     or exists (select 1 from pg_auth_members where member = oid) from pg_roles where rolname = current_user")" = f ] \
  || fail "$db has more than LOGIN and CREATEDB"
# Even as the postgres OS user (peer auth would admit it), the superuser login is refused.
! as postgres psql -h "$dir/pg" -U postgres -d postgres -tAc 'select 1' > /dev/null 2>&1 || fail "postgres login allowed"
! psql -h 127.0.0.1 -U postgres -d postgres -tAc 'select 1' > /dev/null 2>&1 || fail "postgres login allowed over TCP"
[ "$(psql -h 127.0.0.1 -U "$db" -d "$db" -tAc 'select 1')" = 1 ] || fail "$db can't log in over TCP"
# pgvector resolves for the role, unqualified, and isn't the role's to drop.
[ "$(psql -h "$dir/pg" -U "$db" -d "$db" -tAc "select '[1,2]'::vector <=> '[1,3]' is not null")" = t ] \
  || fail "pgvector doesn't resolve for $db"
[ "$(psql -h "$dir/pg" -U "$db" -d "$db" -tAc "select extowner::regrole::text from pg_extension where extname = 'vector'")" != "$db" ] \
  || fail "$db owns the vector extension"
[ "$(redis-cli -h 127.0.0.1 -p 6379 ping)" = PONG ] || fail "redis does not answer over TCP"
[ "$(redis-cli -s "$dir/redis/redis.sock" ping)" = PONG ] || fail "redis does not answer"
# Each with valid arguments (Redis checks arity before permissions); SHUTDOWN last.
while read -r cmd; do
  # shellcheck disable=SC2086
  reply=$(timeout 3 redis-cli -s "$dir/redis/redis.sock" $cmd 2>&1 || true)  # SYNC blocks after its reply
  grep -qE 'NOPERM|not allowed' <<< "$reply" || fail "redis allows $cmd"
done <<'CMDS'
MIGRATE 127.0.0.1 1 k 0 1
REPLICAOF NO ONE
SLAVEOF NO ONE
MODULE LIST
CONFIG GET maxmemory
DEBUG HELP
ACL WHOAMI
MONITOR
SYNC
PSYNC ? -1
FAILOVER ABORT
CLUSTER INFO
SAVE
BGSAVE
BGREWRITEAOF
RESTORE k 0 x
RESTORE-ASKING k 0 x
FUNCTION LIST
SHUTDOWN NOSAVE
CMDS
# The servers started under env -i are the oldest process of each user (the postmaster, redis-server);
# every other server process is their fork. Postgres blanks a child's environ when it sets the
# child's process title, so only these two can be read, and they're the ones that matter.
# Read as the owning user: container root has no CAP_SYS_PTRACE, so it can't read another user's environ.
for user in postgres redis; do
  pid=$(pgrep -o -u "$user") || fail "no $user process"
  env_vars=$(runuser -u "$user" -- cat "/proc/$pid/environ" | tr '\0' '\n') || fail "can't read $user's environment"
  printf '%s\n' "$env_vars" | grep -qx 'LANG=C.UTF-8' || fail "$user process $pid has no readable environment"
  if printf '%s\n' "$env_vars" | grep -vE '^(PATH|LANG|HOME|SHELL|USER|LOGNAME|PWD|PG[A-Z_]*|LC_[A-Z]*)=|^$' > /dev/null; then
    fail "the $user server holds variables it was not given"
  fi
done

cat <<ENV
DATABASE_URL=postgresql+asyncpg://$db@127.0.0.1:5432/$db
REDIS_URL=redis://127.0.0.1:6379/0
ENV
