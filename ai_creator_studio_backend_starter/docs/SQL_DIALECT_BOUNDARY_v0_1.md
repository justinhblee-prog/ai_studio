# SQL Dialect Boundary v0.1 (v0.26)

## Purpose
Move the highest-risk worker claim/recovery SQL out of the orchestration module before introducing another database engine. This is a boundary extraction, not a PostgreSQL implementation.

## Extracted statements
`app/sql/sqlite_worker.py` now owns the SQLite statements for:
- Outbox expired-lease detection and UNKNOWN/reconciliation transition.
- Outbox ready-row selection and compare-and-set claim.
- Poll task expired-lease requeue, ready-row selection, and compare-and-set claim.

`app/job_repository.py` retains transaction orchestration, domain transitions, event writes, and row mapping. It imports the SQLite statement module and executes those statements within the existing SQLite transaction behavior.

## Preserved invariants
- Outbox expired dispatch lease is marked `needs_reconciliation`; it is never automatically replayed because provider acceptance may be unknown.
- Poll lease expiration is requeued because status GET/output persistence tasks are safe to retry under current semantics.
- Claim UPDATE statements retain `status='pending'` compare-and-set guards and increment attempts atomically.
- Ready selection order remains deterministic.
- Existing `BEGIN IMMEDIATE` write serialization remains unchanged.

## Deliberate non-claims
- No PostgreSQL SQL dialect or PostgreSQL repository is present.
- No `FOR UPDATE SKIP LOCKED` implementation is claimed.
- No PostgreSQL live transaction/concurrency test was run.
- The monolithic repository still contains other SQL for Job, event, output, alert, and operational workflows.

## Validation
- Backend pytest: 126 passed.
- `python -m compileall -q app scripts tests`: passed.
- 3D Viewer structural validation: 19/19 passed.
