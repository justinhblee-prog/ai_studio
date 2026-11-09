# PostgreSQL Migration Foundation — BUILD-00215

## Scope

This build adds a PostgreSQL schema/migration foundation for the generation runtime. It does **not** enable PostgreSQL as the application repository backend.

## Implementation

- `app/postgres.py`
  - Requires an explicit `DATABASE_URL`; fails closed when absent.
  - Uses psycopg 3 with a bounded connection timeout and application name.
  - Applies ordered `NNNN_*.sql` migrations under a PostgreSQL transaction-scoped advisory lock.
  - Maintains an `acs_schema_migrations` ledger with SHA-256 checksums and refuses modified already-applied migrations.
  - Exposes a read-only migration ledger inspection function.
- `app/sql/postgres/migrations/0001_generation_core.sql`
  - Creates 13 core generation, execution, event, output, idempotency, outbox, worker, poll, operations and review/export tables.
  - Adds indexes, foreign keys, uniqueness and bounded lease columns.
  - Protects output review/export events against UPDATE and DELETE.
  - Enables RLS on every application table without client policies yet (default deny for anon/authenticated). Server-side service-role access is required until reviewed tenant policies exist.
- `requirements.txt`: adds `psycopg[binary]`.

## Verification

- Backend pytest: 500 passed / 0 failed.
- Python compileall: PASS.
- Runtime OpenAPI snapshot: PASS (no API contract change).
- SQL was reviewed structurally and covered by migration tests. It has **not yet been applied to the Supabase test project**, and no live PostgreSQL connection test has been run.

## Safety / incomplete

- `DATABASE_BACKEND=postgresql` remains disabled and the repository factory still fails closed.
- No credentials are stored in source or documentation.
- The migration establishes schema only. Aggregate repository implementations, `FOR UPDATE SKIP LOCKED` claim paths, tenant-aware RLS policies, Storage adapter and app integration remain incomplete.
- Before a live apply, validate the migration against the dedicated test project and inspect Supabase Security Advisor. Production project must remain untouched.
