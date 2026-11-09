# AI CREATOR STUDIO v0.39 — Job Diagnostics Repository

## Scope
- Extract read-only Job diagnostics composition from `app/job_repository.py` into `app/repositories/diagnostics.py`.
- `SQLiteJobDiagnosticsRepository` composes Event, Execution, Output, Outbox and Poll Task records.
- Keep `job_repository.diagnostics()` as a compatibility facade.
- Fail closed for PostgreSQL selection; no SQLite fallback.

## Verification
- Backend: `python -m pytest -q` — 156 passed.
- Backend compile: `python -m compileall -q app scripts tests` — passed.
- 3D Viewer structural validation — 19/19 passed.

## Boundaries
- Outbox, Poll, operator reconciliation and operational monitoring SQL still have legacy/worker adapter portions to extract.
- PostgreSQL runtime and live integration tests remain unimplemented.
