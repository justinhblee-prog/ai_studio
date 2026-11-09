# AI CREATOR STUDIO v0.37 — Job / Execution Repository Extraction

## Scope
- Move Generation Job lifecycle transition and metadata update SQL out of `app/job_repository.py` into `app/repositories/job.py` (`SQLiteJobRepository`).
- Extract latest Execution-attempt state updates into `app/repositories/execution.py` (`SQLiteExecutionRepository`).
- Keep Job, Execution and append-only Event mutations on the exact same caller-owned SQLite connection/transaction.
- Preserve legacy module-level function names as compatibility facades and preserve non-extracted operational methods through a transitional proxy.
- Route the Job/Event Unit of Work lifecycle methods through the dedicated Job repository.

## Verification
- Backend: `python -m pytest -q` — 151 passed.
- Backend compile: `python -m compileall -q app scripts tests` — passed.
- 3D Viewer structural validation — 19/19 passed.
- Added tests for Execution adapter contract, lifecycle status propagation, and rollback of Job + Execution when Event append fails.

## Boundaries / known limitations
- SQLite remains the only implemented runtime persistence adapter.
- PostgreSQL runtime adapter and live PostgreSQL integration tests are not implemented.
- The Job repository still delegates create/read/idempotency and non-lifecycle operational methods to the legacy module; this milestone extracts lifecycle writes and Execution SQL, not the entire legacy repository.
- No zero-downtime deployment or database cutover is claimed or implemented.
