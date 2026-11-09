# Operations SQL Boundary v0.1 (v0.27)

## Scope
Extract SQLite-specific SQL for operational snapshots, durable alert state, and webhook delivery into `app/sql/sqlite_operations.py`.

## Extracted query groups
- Worker heartbeat inventory and Outbox/Poll/Alert/Delivery aggregates.
- Active alert fingerprint lookup, alert update/insert, delivery enqueue/upsert, and alert resolution.
- Alert listing with severity ordering.
- Stale delivery requeue, pending delivery selection, compare-and-set claim, attempt lookup, sent/failed state, and retry scheduling.

## Invariants retained
- Alert identity remains fingerprint-based.
- Existing active alerts are updated; resolved alerts are only reactivated when a current breach exists.
- Delivery uniqueness remains `(alert_id, destination)` through the existing SQLite conflict clause.
- Delivery claims remain guarded by `status='pending'` and increment attempts atomically.
- Retry and terminal delivery states remain explicit.
- Transaction boundaries remain in the repository orchestration; this extraction does not alter transaction semantics.

## Limitations
- Statements are SQLite-only and retain SQLite `ON CONFLICT` syntax.
- No PostgreSQL SQL implementation or live PostgreSQL integration test exists.
- Job/Event/Output SQL remains in `job_repository.py`.
- This is not a production cutover or zero-downtime migration.

## Validation
- Backend pytest: 130 passed.
- Python compileall: passed.
- 3D Viewer structural validation: 19/19 passed.
