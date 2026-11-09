# AI CREATOR STUDIO v0.25 — SQLite Schema Boundary Extraction

## Delivered
- Moved SQLite DDL out of the monolithic Generation Job repository into `app/schema_sqlite.py`.
- Grouped schema installation by persistence aggregate: Core Job, Outbox, Poll Task, and Operations/Alerts.
- Kept schema application order and historical migration markers v1-v5 unchanged.
- Kept initialization idempotent and preserved SQLite runtime behavior.

## Validation
- Backend: `PYTHONPATH=. pytest -q` — 122 passed.
- Python compile: `python -m compileall -q app scripts tests` — passed.
- 3D Viewer structural validation — 19/19 passed.

## Not claimed
- This is a SQLite schema boundary extraction, not a PostgreSQL migration runner.
- Existing SQL queries and transactions remain in the legacy repository; no PostgreSQL runtime or live server test exists.
- No zero-downtime dual-write, CDC, production cutover, or rollback has been performed.
- Credit Quote/Ledger, FASHN live rights/contract/retention verification, and frontend/browser/Android E2E remain open.

## Next
1. Extract Outbox, Poll Task, and Operations query implementations into aggregate-specific SQLite repositories.
2. Introduce explicit transaction/session boundaries and dialect-aware query construction.
3. Add PostgreSQL migrations and runtime adapter after real PostgreSQL integration environment is available.
