# AI CREATOR STUDIO Handoff — v0.31 / v4.4

## Current artifact
- Version: v0.31 Job/Event Repository Ports + API Dependency Injection
- Project root: `AI_CREATOR_STUDIO_v0_31/`
- Backend: `ai_creator_studio_backend_starter/`
- ZIP: `AI_CREATOR_STUDIO_v0_31_job_event_repository_di.zip`

## Completed
- Added JobRepository and EventRepository application protocols.
- Added SQLite compatibility adapters.
- Added cached dependency providers in `app/dependencies.py`.
- Injected repositories into Job create/read/events API endpoints via FastAPI `Depends`.
- Kept existing event diagnostics response shape intact.
- PostgreSQL backend remains fail-closed; no silent SQLite fallback.

## Validation evidence
- pytest: 139 passed.
- Python compileall: passed.
- Viewer structural checks: 19/19 passed.

## Architecture state / limitations
- This is a boundary/DI extraction only. SQLite adapters still delegate to legacy SQLite SQL implementation.
- No live PostgreSQL runtime adapter or PostgreSQL integration test has been completed.
- SQLite remains single-host PoC; do not run multi-host workers against shared SQLite/NFS.
- No zero-downtime dual-write/CDC/cutover/rollback implementation.
- Credit Quote/Ledger remains unimplemented.
- FASHN live rights/contract/retention/commercial-use verification remains open.
- Browser/WebGL/Android E2E and production deployment remain unverified.
- QA T-01..T-14 remain traceable; no unsupported gate closure.

## Next actions
1. Move remaining Job-related API endpoints to repository dependencies.
2. Separate Event append/write operations without breaking atomic Job lifecycle transactions.
3. Add service-level transaction boundary/Unit of Work composition for Job+Event operations.
4. Provision PostgreSQL and run real driver/server tests for migrations, idempotency, row locking, lease claims, rollback, and multi-instance behavior.
5. Only then design and test zero-downtime migration stages.

## Decision rules
- Do not claim PostgreSQL readiness without live PostgreSQL evidence.
- MANUAL provider selection never auto-falls back.
- Job succeeds only after output and database references are persisted.
- Preserve append-only Credit Ledger and idempotency requirements when implemented.
- Any production cutover, external contract, cost, security, or irreversible operation requires explicit approval.
