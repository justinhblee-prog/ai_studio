# AI CREATOR STUDIO Handoff v4.8 — v0.37

## Current source
- Version: v0.37 Job / Execution Repository Extraction
- Backend: `ai_creator_studio_backend_starter/`
- Viewer: `ai_creator_studio_3d_viewer/`

## Completed in v0.37
- Lifecycle transition/update SQL moved to `SQLiteJobRepository`.
- Execution latest-attempt status SQL moved to `SQLiteExecutionRepository`.
- Job, Execution and Event writes share one SQLite connection and transaction.
- `JobEventUnitOfWork` now routes lifecycle writes through the dedicated Job repository.
- Legacy function names remain as compatibility facades.
- Non-lifecycle legacy operations remain temporarily delegated; do not treat full legacy removal as complete.

## Evidence
- Backend pytest: 151 passed.
- `python -m compileall -q app scripts tests`: passed.
- Viewer validation: 19/19.

## Next autonomous steps
1. Extract Job create/get/idempotency SQL into SQLiteJobRepository.
2. Extract Execution read/create-attempt/retry SQL into SQLiteExecutionRepository.
3. Remove remaining `job_repository.py` operational proxies in controlled slices.
4. Add repository contract tests and transaction rollback tests for each slice.
5. Reassess PostgreSQL runtime feasibility; do not claim live integration without an actual PostgreSQL service and driver.

## Open risks / gates
- PostgreSQL runtime adapter/live integration tests absent.
- SQLite remains single-host PoC.
- No zero-downtime deployment/dual-write/CDC/cutover/rollback implementation.
- Credit Quote / append-only Credit Ledger absent.
- FASHN contract, rights, retention, commercial-use review open.
- TypeScript/browser/WebGL/Android E2E and production deployment unverified.
- QA T-01..T-14 remain traceable; do not close gates without evidence.
