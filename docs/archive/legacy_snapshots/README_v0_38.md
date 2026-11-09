# AI CREATOR STUDIO v0.38 — Job Create / Read Repository Extraction

## Scope
- Move Generation Job creation, lookup, workspace-scoped idempotency lookup and event list compatibility SQL into dedicated repositories.
- `SQLiteJobRepository` now owns create/get/get_idempotent/transition/update operations.
- `SQLiteExecutionRepository` owns initial Execution attempt creation and latest-attempt status mutation.
- Job creation writes Job, initial Execution, JOB_CREATED Event, optional idempotency record and Outbox row in one SQLite transaction.
- Legacy module-level APIs remain compatibility facades; Event list remains a facade to `SQLiteEventRepository`.

## Verification
- Backend: `python -m pytest -q` — 153 passed.
- Backend compile: `python -m compileall -q app scripts tests` — passed.
- 3D Viewer structural validation — 19/19 passed.
- Added direct adapter tests proving create/read/idempotency no longer call legacy module functions and verifying duplicate idempotency behavior.

## Boundaries
- Some operational diagnostics, Outbox, Poll and admin reconciliation SQL remain in legacy/worker repositories.
- SQLite is still the only runtime adapter; PostgreSQL runtime and live integration tests are not implemented.
- No zero-downtime deployment or database cutover is claimed.
