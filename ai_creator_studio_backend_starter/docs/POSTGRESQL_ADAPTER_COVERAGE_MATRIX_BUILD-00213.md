# PostgreSQL Adapter Coverage Matrix — BUILD-00213

## Current result

**PostgreSQL runtime support is not implemented.** All runtime aggregate paths remain SQLite-only. The current code intentionally fails closed instead of silently routing PostgreSQL configuration to SQLite.

## Runtime persistence domains

| Domain / aggregate | Current implementation | PostgreSQL adapter | Required transaction invariant |
|---|---|---|---|
| Generation Job | SQLiteJobRepository | Missing | Job + Execution + Event + idempotency + Outbox atomic create |
| Job Event / lifecycle | SQLiteEventRepository / SQLiteJobEventUnitOfWork | Missing | Append-only Event in same transaction as Job transition |
| Execution | SQLiteExecutionRepository | Missing | Attempt number and Job state transition atomic |
| Outbox submission | SQLiteOutboxRepository / admin | Missing | `FOR UPDATE SKIP LOCKED`, fenced lease, unknown submission reconciliation |
| Provider polling | SQLitePollRepository / admin | Missing | Lease fencing, bounded retry, output persistence before success |
| Output | SQLiteOutputRepository | Missing | Output metadata, checksum, state transition atomic; file durability separate |
| Output → Asset link | SQLiteOutputAssetLinkRepository | Missing | Idempotent link, provenance, workspace consistency |
| Output review/export | SQLiteOutputReviewRepository and export events | Missing | Append-only review/export audit facts |
| Worker heartbeat/health | SQLite operations repositories | Missing | Monotonic heartbeat and lease-aware worker health |
| Operations alerts/delivery | SQLite alert/monitoring repositories | Missing | Claim lease, bounded retries, idempotent delivery state |
| Workspace / Asset metadata | `app.assets.store` SQLite SQL | Missing | Tenant membership and asset/version/provenance atomicity |
| Credit Ledger | Protocol/domain only; no adapter | Missing | Immutable append, scoped idempotency, reference validation, all-or-nothing batch |
| Private file storage | Local filesystem | Supabase Storage adapter missing | Tenant-safe key, checksum, signed URL, quarantine/delete lifecycle |

## Explicitly guarded PostgreSQL factories

The test `tests/test_postgresql_fail_closed.py` invokes each known PostgreSQL selection path and asserts a `RuntimeError` rather than SQLite fallback:

- `build_job_diagnostics_repository`
- `build_job_repository`
- `build_job_event_uow`
- `build_alert_delivery_repository`
- `build_operations_alert_read_repository`
- `build_operations_monitoring_repository`
- `build_worker_heartbeat_repository`
- `build_worker_health_repository`
- `build_outbox_repository`
- `build_outbox_admin_repository`
- `build_output_asset_link_repository`
- `build_output_repository`
- `build_output_review_repository`
- `build_poll_repository`
- `build_poll_task_admin_repository`
- `get_storage("postgresql")`

This is a negative/fail-closed test only. It does not test a PostgreSQL adapter.

## SQL dialect and transaction work still required

A complete adapter cannot be created by swapping only the connection driver. Runtime code currently includes SQLite connection/row assumptions and SQL dialect features (for example `?` placeholders, `INSERT OR IGNORE`, `rowid`, SQLite DDL/PRAGMA and `sqlite3.Row`). The inventory scan found 106 SQLite-specific references in Python application modules at this build. They require explicit query/adapter conversion and parity tests; do not apply blind string replacement.

## Implementation order

1. Define shared transaction/connection/row contracts and migration versioning.
2. Convert Workspace/Asset metadata and Job/Event/Execution aggregates with transaction parity.
3. Convert Outbox/Poll/Output aggregates and prove multi-worker lock/lease fencing.
4. Convert operations alert/health repositories.
5. Implement Credit Ledger persistence as its own immutable aggregate.
6. Implement Supabase Storage adapter and file lifecycle recovery.
7. Run isolated Supabase test-project migration, RLS, concurrency and authenticated API tests.

Do not enable PostgreSQL runtime until every API and Worker path used by the deployment has an implemented adapter and a passing integration suite.
