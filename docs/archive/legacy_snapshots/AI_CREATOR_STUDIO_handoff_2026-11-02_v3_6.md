# AI CREATOR STUDIO Handoff v3.6 — 2026-11-02

## Current milestone
v0.23 Shared Storage Port Extension

## What changed
Asset/workspace metadata now obtains its database connection through `app.storage.get_storage()`, matching Generation Job persistence. Backend selection is explicit across both domains. PostgreSQL selection fails closed; no SQLite fallback is permitted.

## Evidence
- Backend tests: **116 passed** (`python -m pytest -q`)
- Python compile: passed (`python -m compileall -q app scripts tests`)
- 3D Viewer structural validation: **19/19 passed**
- Added tests verify asset schema creation through the shared adapter, SQLite FK/WAL settings, and explicit PostgreSQL rejection.

## Current architecture boundary
- Modular monolith remains.
- SQLite is the only enabled runtime backend.
- Generation Job repository and Asset metadata connection creation use the Storage Port.
- Existing SQLite DDL and SQL query semantics remain in the repositories.
- PostgreSQL runtime adapter is not implemented.
- This milestone is not a zero-downtime migration and does not establish multi-host readiness.

## Known unresolved risks
- SQLite-specific SQL remains (`?` placeholders, `INSERT OR IGNORE`, SQLite exception classes, SQLite row behavior, and claim transaction semantics).
- No live PostgreSQL server/driver integration evidence exists in this environment.
- Do not run multiple hosts/workers against shared SQLite/NFS.
- Credit Quote and append-only Credit Ledger remain unimplemented.
- FASHN live contract, rights, retention, and commercial-use verification remains open.
- TypeScript/browser/WebGL/Android E2E and production deployment remain unverified.
- QA T-01 through T-14 remain traceable; no gate is silently closed.

## Next autonomous work
Extract Asset/Workspace repositories, isolate dialect/placeholder behavior, then extract Outbox/Poll/Alert persistence boundaries. Do not implement a PostgreSQL adapter until all query semantics and real PostgreSQL integration tests are covered. A real cutover requires separately tested dual-write or CDC, reconciliation, traffic switch, and rollback procedures.

## Library destinations
- `/AI_CREATOR_STUDIO/AI_CREATOR_STUDIO_v0_23_shared_storage_port.zip`
- `/AI_CREATOR_STUDIO/README_v0_23.md`
- `/AI_CREATOR_STUDIO/AI_CREATOR_STUDIO_개발진행기록_v0_23.md`
- `/AI_CREATOR_STUDIO/AI_CREATOR_STUDIO_handoff_2026-11-02_v3_6.md`
- `/AI_CREATOR_STUDIO/STORAGE_PORT_EXTRACTION_v0_2.md`
