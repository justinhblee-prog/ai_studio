# PostgreSQL Runtime Readiness Gate v0.1

## Purpose

Provide a reproducible, non-invasive check before claiming PostgreSQL integration tests are executable.

## Required capabilities

- At least one Python driver: `psycopg`, `psycopg2`, or `asyncpg`.
- A local provisioner: native `postgres` + `initdb` + `pg_ctl`, or Docker, or Podman.
- `psql` is useful for diagnosis but is not mandatory when a driver and provisioner are present.

Run:

```bash
python scripts/check_postgres_runtime.py
```

Exit code 0 means the local runtime prerequisites are present. Exit code 2 means the environment is not ready. This probe does not connect to a database, start a service, inspect credentials, or prove migrations/transactions work.

## Current environment snapshot (2026-11-02)

- Native `postgres`, `initdb`, `pg_ctl`, `psql`: unavailable.
- Docker/Podman: unavailable.
- Python `psycopg`, `psycopg2`, `asyncpg`: unavailable.
- SQLAlchemy is present, but without a PostgreSQL driver this is insufficient.

Therefore PostgreSQL live integration testing remains BLOCKED by environment prerequisites. No runtime adapter or multi-instance guarantee is claimed by this milestone.
