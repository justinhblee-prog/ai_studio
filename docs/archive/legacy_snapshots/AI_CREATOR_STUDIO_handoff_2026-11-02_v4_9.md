# AI CREATOR STUDIO Handoff v4.9 — v0.38

## Current source
- Version: v0.38 Job Create / Read Repository Extraction
- Backend: `ai_creator_studio_backend_starter/`
- Viewer: `ai_creator_studio_3d_viewer/`

## Completed in v0.38
- `SQLiteJobRepository` owns create/get/idempotency/transition/update SQL.
- `SQLiteExecutionRepository` owns initial attempt creation and latest attempt lifecycle status SQL.
- `SQLiteEventRepository` owns event reads and append operations.
- Job creation transaction persists Job + initial Execution + JOB_CREATED Event + optional idempotency row + Outbox row atomically.
- Legacy module functions remain as compatibility facades; operational diagnostics and worker/admin SQL still need extraction.

## Evidence
- Backend pytest: 153 passed.
- `python -m compileall -q app scripts tests`: passed.
- Viewer structural validation: 19/19.

## Next autonomous steps
1. Extract Execution reads and diagnostics into Execution/Operations repositories.
2. Extract Outbox/Poll/admin reconciliation SQL into explicit repository adapters.
3. Remove transitional legacy delegation only after each API/Worker path has a replacement and regression evidence.
4. Reassess PostgreSQL runtime implementation and run live integration tests only when a real service and driver are available.

## Open risks / gates
- PostgreSQL runtime adapter/live integration absent; SQLite remains single-host PoC.
- No zero-downtime deployment/dual-write/CDC/cutover/rollback implementation.
- Credit Quote / append-only Credit Ledger absent.
- FASHN contract, rights, retention, commercial-use review open.
- TypeScript/browser/WebGL/Android E2E and production deployment unverified.
- QA T-01..T-14 remain traceable; do not close gates without evidence.
