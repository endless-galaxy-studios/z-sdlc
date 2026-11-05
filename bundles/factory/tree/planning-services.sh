#!/usr/bin/env bash
# Start the planning tier's database proxy (design rule D3): pgbouncer on the job container's
# loopback, holding the read-only factory_reader login's password, so the agent can query the
# production database without ever seeing the password. Run as root before the agent, with the
# password in FACTORY_DB_READER_PASSWORD (that step's env only). The config sits in a directory only
# the postgres user can read, under the runner temp directory the sandbox can't see.
# Usage: planning-services.sh <planning.json> <config-dir>. With no database in planning.json it does nothing.
set -euo pipefail

cfg=$1
dir=$2
# The database is optional (D3): a project whose planning.json names none plans without production data.
if [ -z "$(jq -r '.database.host // ""' "$cfg")" ]; then
  echo "planning-services: planning.json names no database; planning runs without production data"
  exit 0
fi
host=$(jq -r .database.host "$cfg"); port=$(jq -r .database.port "$cfg"); name=$(jq -r .database.name "$cfg")
user=$(jq -r .database.user "$cfg"); local_port=$(jq -r .database.local_port "$cfg")
# TLS to the database (D3 rule 2). On a private, tailnet or loopback address (the runner host, a VPN peer) the
# network is the boundary, and TLS is used when the server offers it. Anywhere else the login's exchange and
# every row cross the internet, so TLS is required and prefer or disable is refused: pgbouncer's own default
# would fall back to plaintext when the server doesn't offer TLS. planning.json's database.sslmode overrides
# the default within those limits.
private=no
if [[ $host =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]] && python3 -I -c '
import ipaddress, sys
a = ipaddress.IPv4Address(sys.argv[1])
# RFC 1918, loopback, and the shared range (RFC 6598) that Tailscale addresses come from, 0x64400000/10.
nets = ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", (0x64400000, 10), "127.0.0.0/8")
sys.exit(0 if any(a in ipaddress.IPv4Network(n) for n in nets) else 1)' "$host" 2> /dev/null; then
  private=yes
fi
sslmode=$(jq -r '.database.sslmode // ""' "$cfg")
case "$sslmode" in
  "") if [ $private = yes ]; then sslmode=prefer; else sslmode=require; fi ;;
  require) ;;
  prefer|disable)
    [ $private = yes ] \
      || { echo "planning-services: $host isn't a private address, so sslmode must be require, not $sslmode" >&2; exit 1; } ;;
  *) echo "planning-services: database.sslmode must be require, prefer or disable, not $sslmode" >&2; exit 1 ;;
esac
echo "planning-services: TLS to $host: $sslmode"
[ -n "${FACTORY_DB_READER_PASSWORD:-}" ] || { echo "planning-services: no database password" >&2; exit 1; }

# A fresh directory each run: the runner's temp directory can outlive a job, and a stale pidfile or
# config from an earlier run would stop pgbouncer from starting (silently, before this fix).
rm -rf "$dir"
install -d -m 700 -o postgres -g postgres "$dir"
umask 077
cat > "$dir/pgbouncer.ini" <<INI
[databases]
$name = host=$host port=$port dbname=$name user=$user password=$FACTORY_DB_READER_PASSWORD

[pgbouncer]
server_tls_sslmode = $sslmode
; Deadlines the login can't lift (it can SET statement_timeout away): a query over a minute is cancelled, a
; transaction left idle or a client left waiting for a connection is dropped after 30 seconds.
query_timeout = 60
idle_transaction_timeout = 30
query_wait_timeout = 30
listen_addr = 127.0.0.1
listen_port = $local_port
unix_socket_dir =
auth_type = trust
auth_file = $dir/userlist.txt
pool_mode = session
max_client_conn = 20
default_pool_size = 4
ignore_startup_parameters = extra_float_digits,options
logfile = $dir/pgbouncer.log
pidfile = $dir/pgbouncer.pid
INI
printf '"%s" ""\n' "$user" > "$dir/userlist.txt"
chown postgres:postgres "$dir/pgbouncer.ini" "$dir/userlist.txt"
if ! env -i PATH=/usr/sbin:/usr/bin:/sbin:/bin LANG=C.UTF-8 runuser -u postgres -- pgbouncer -d "$dir/pgbouncer.ini" > "$dir/start.log" 2>&1; then
  echo "planning-services: pgbouncer didn't start:" >&2
  # Its own messages only (no password: that's in the ini, which isn't printed).
  tail -20 "$dir/start.log" "$dir/pgbouncer.log" 2> /dev/null >&2 || true
  exit 1
fi

for _ in $(seq 50); do (exec 3<> "/dev/tcp/127.0.0.1/$local_port") 2> /dev/null && break; sleep 0.1; done
answer=$(psql -h 127.0.0.1 -p "$local_port" -U "$user" -d "$name" -tAc 'select 1' 2>&1) || true
if [ "$answer" != 1 ]; then
  echo "planning-services: the database proxy can't reach $host:$port ($answer)" >&2
  tail -20 "$dir/pgbouncer.log" 2> /dev/null >&2 || true
  exit 1
fi
# Read-only is the login's privileges, never a session default: any session can open a read-write transaction
# (COMMIT; BEGIN READ WRITE), and the privileges PUBLIC holds stay the login's. Refuse a login that can write
# anything, keep anything, or lift its own limits (D3 rule 3), before the agent starts.
reader_check=$(cat <<'SQL'
select p from (
  select 'it can write large objects through ' || f || ' (revoke EXECUTE from PUBLIC)' as p
    from unnest(array['lo_create(oid)', 'lo_creat(integer)', 'lo_from_bytea(oid,bytea)', 'lo_put(oid,bigint,bytea)',
                      'lowrite(integer,bytea)', 'lo_truncate(integer,integer)', 'lo_truncate64(integer,bigint)',
                      'lo_import(text)', 'lo_import(text,oid)']) f
   where has_function_privilege(f, 'EXECUTE')
  union all
  select 'it can create temporary tables (revoke TEMPORARY on the database from PUBLIC)'
   where has_database_privilege(current_database(), 'TEMPORARY')
  union all
  select 'it can create schemas in the database' where has_database_privilege(current_database(), 'CREATE')
  union all
  select 'temp_file_limit is unlimited (set it on the role; only a superuser can change it)'
   where current_setting('temp_file_limit') = '-1'
  union all
  select 'it is a superuser, or can create roles or databases, or bypasses row security'
    from pg_roles where rolname = current_user and (rolsuper or rolcreaterole or rolcreatedb or rolbypassrls)
  union all
  select 'it is a member of ' || r
    from unnest(array['pg_write_all_data', 'pg_write_server_files', 'pg_execute_server_program',
                      'pg_read_server_files', 'pg_signal_backend']) r
   where pg_has_role(current_user, r, 'MEMBER')
  union all
  select 'it owns the database' from pg_database where datname = current_database() and datdba = (select oid from pg_roles where rolname = current_user)
  union all
  select 'it owns ' || c.oid::regclass from pg_class c where c.relowner = (select oid from pg_roles where rolname = current_user)
  union all
  select 'it can create in schema ' || n.nspname from pg_namespace n
   where n.nspname not like 'pg\_%' and n.nspname <> 'information_schema' and has_schema_privilege(n.oid, 'CREATE')
  union all
  select 'it can write to ' || c.oid::regclass from pg_class c join pg_namespace n on n.oid = c.relnamespace
   where c.relkind in ('r', 'p', 'v', 'm', 'f') and n.nspname not like 'pg\_%' and n.nspname <> 'information_schema'
     and (has_any_column_privilege(c.oid, 'INSERT') or has_any_column_privilege(c.oid, 'UPDATE')
          or has_table_privilege(c.oid, 'DELETE') or has_table_privilege(c.oid, 'TRUNCATE'))
  union all
  select 'it can change sequence ' || c.oid::regclass from pg_class c
   where case when c.relkind = 'S' then has_sequence_privilege(c.oid, 'UPDATE') else false end
) problems
SQL
)
problems=$(psql -h 127.0.0.1 -p "$local_port" -U "$user" -d "$name" -tA -c "$reader_check" 2>&1) \
  || { echo "planning-services: can't check $user's privileges: $problems" >&2; problems=unchecked; }
if [ -n "$problems" ]; then
  echo "planning-services: $user isn't read-only (process/factory.md, D3 rule 3):" >&2
  printf '%s\n' "$problems" | head -20 | sed 's/^/  - /' >&2
  kill "$(cat "$dir/pgbouncer.pid" 2> /dev/null)" 2> /dev/null || true
  exit 1
fi
echo "planning-services: $name at 127.0.0.1:$local_port (read-only, as $user)" >&2
