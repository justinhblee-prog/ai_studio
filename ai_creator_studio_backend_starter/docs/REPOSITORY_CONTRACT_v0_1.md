# Generation Job Repository Contract v0.1

## Purpose
Establish an application-facing persistence contract before introducing a second database engine. This avoids presenting a configuration-only DSN change as a working PostgreSQL migration.

## Contract
`app.repository_contract.GenerationJobRepository` defines the operations required by the current Generation Job lifecycle: initialization, idempotent creation, reads, state transitions, Outbox/Poll/Alert claiming, worker health, diagnostics, and operational snapshots.

`SQLiteRepository` is a compatibility adapter around the existing `app.job_repository` module. It preserves proven SQLite behavior and makes the future dependency boundary explicit. The adapter is not yet injected into every API/worker component; that is the next extraction step.

## Backend selection
- `DATABASE_BACKEND=sqlite`: supported.
- `DATABASE_BACKEND=postgresql`: deliberately rejected with a clear runtime error.
- Any other value: rejected.
- `DATABASE_URL` is reserved and currently unused.
- No automatic fallback is permitted.

## Why PostgreSQL is not enabled
The existing implementation relies on SQLite-specific schema and SQL behavior, including PRAGMA, `executescript`, `BEGIN IMMEDIATE`, `INSERT OR IGNORE`, qmark placeholders, and SQLite row behavior. A PostgreSQL implementation must explicitly reproduce transactional invariants and claim semantics rather than mechanically translating connection strings.

## Acceptance gate before enabling PostgreSQL
1. Repository contract conformance tests against PostgreSQL.
2. Atomic Job + Execution + Event + Idempotency + Outbox creation and rollback.
3. Concurrent idempotency replay and workspace isolation.
4. Outbox, Poll Task, and Alert Delivery claim exclusivity using row locks / `SKIP LOCKED`.
5. Lease expiry, worker crash recovery, retry, and reconciliation tests.
6. Two or more independent worker processes against one PostgreSQL database.
7. Migration row counts/checksums and sequence restoration verified on real PostgreSQL.
8. Backup, cutover, rollback, and private asset/output copy procedures rehearsed.

Until all gates pass, SQLite remains the only supported runtime backend and PostgreSQL must remain fail-closed.

## Low-level storage port (v0.22)
`app.storage.StorageBackend` isolates connection creation and write-transaction start. `SQLiteStorage` owns SQLite PRAGMA/WAL/timeout configuration and `BEGIN IMMEDIATE`; `job_repository._connect()` and write paths delegate to it. This is intentionally a narrow first extraction. SQL statements, DDL, migrations, row types, and placeholders remain SQLite-specific and must be separated before PostgreSQL can be implemented safely.
