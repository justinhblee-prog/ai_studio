#!/usr/bin/env bash
# Reproduce the live PostgreSQL repository tests on a throwaway local cluster.
# Requires PostgreSQL server binaries (default /usr/lib/postgresql/16/bin) and root or a
# user that may run initdb. Never touches Supabase TEST or Production.
set -euo pipefail
PGBIN="${PGBIN:-/usr/lib/postgresql/16/bin}"
PORT="${PGTESTPORT:-5440}"
WORK="$(mktemp -d /tmp/acs_pg.XXXXXX)"
SOCK="$WORK/sock"; DATA="$WORK/data"
PY="${PYTHON:-python}"
RUN=""
if [ "$(id -u)" = "0" ]; then
  id postgres >/dev/null 2>&1 || useradd -m postgres
  mkdir -p "$SOCK" "$DATA"; chown -R postgres "$WORK"; chmod 755 "$WORK"
  RUN="su postgres -c"
fi
sh() { if [ -n "$RUN" ]; then $RUN "$1"; else bash -c "$1"; fi; }
cleanup() { sh "$PGBIN/pg_ctl -D $DATA -m immediate stop >/dev/null 2>&1 || true"; rm -rf "$WORK"; }
trap cleanup EXIT
mkdir -p "$SOCK" "$DATA"
sh "$PGBIN/initdb -D $DATA -A trust >/dev/null"
sh "$PGBIN/pg_ctl -D $DATA -o '-k $SOCK -p $PORT' -l $WORK/log -w start >/dev/null"
PSQL=("$PGBIN/psql" -h "$SOCK" -p "$PORT" -U postgres -v ON_ERROR_STOP=1 -q)
"${PSQL[@]}" -c "create role anon nologin; create role authenticated nologin; create role service_role nologin bypassrls; create schema auth; create function auth.uid() returns uuid language sql stable as 'select null::uuid';"
"${PSQL[@]}" -c "create database acs_live"
cd "$(dirname "$0")/.."
ACS_TEST_DATABASE_URL="postgresql://postgres@/acs_live?host=$SOCK&port=$PORT" \
  "$PY" -m pytest -q --no-header -p no:cacheprovider tests/test_postgres_live_repositories.py "$@"
