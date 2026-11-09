# AI CREATOR STUDIO Handoff v4.0 — v0.27

## Current baseline
- Latest milestone: v0.27 Operations SQL Boundary Extraction.
- Source root: `AI_CREATOR_STUDIO_v0_27/`.
- Backend: `ai_creator_studio_backend_starter/`.
- Runtime remains SQLite-only; PostgreSQL must fail closed.

## v0.27 changes
- Extracted operations snapshot aggregate SQL.
- Extracted alert fingerprint lookup/update/insert/resolve and alert listing SQL.
- Extracted alert delivery enqueue/upsert, stale requeue, ready selection, claim, terminal status, and retry SQL.
- Preserved repository-owned transaction orchestration and alert policy.
- Added four SQL-boundary regression tests.

## Evidence
- Backend pytest: 130 passed.
- Python compileall: passed.
- 3D Viewer structural validation: 19/19 passed.

## Limitations
- Operations statements remain SQLite-specific; PostgreSQL SQL/dialect is not implemented.
- Job/Event/Output SQL remains in the monolithic repository.
- No live PostgreSQL transaction, concurrency, multi-instance, or cutover test.
- No zero-downtime production migration has occurred.
- SQLite remains a single-host PoC; do not run multi-host workers against shared SQLite/NFS.
- Credit Quote / append-only Credit Ledger remain unimplemented.
- FASHN live contract, rights, retention, and commercial-use verification remain open.
- TypeScript/browser/WebGL/Android E2E and production deployment remain unverified.
- QA IDs T-01 through T-14 remain traceable; do not silently close gates.

## Next execution sequence
1. Extract Job/Event/Output SQL and aggregate-specific repository boundaries.
2. Define a complete unit-of-work/transaction contract, including output persistence before SUCCEEDED.
3. Add PostgreSQL adapter only with a real server and integration suite.
4. Validate idempotency, rollback, outbox/poll/alert claims, event/output atomicity, and multi-instance contention.
5. Plan staged zero-downtime cutover only after those tests pass, with reconciliation, monitoring, and rollback checkpoints.
