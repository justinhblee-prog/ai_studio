# AI CREATOR STUDIO Handoff v3.8 — v0.25

## Current baseline
- Latest milestone: v0.25 SQLite Schema Boundary Extraction.
- Source root: `AI_CREATOR_STUDIO_v0_25/`.
- Backend: `ai_creator_studio_backend_starter/`.
- Runtime remains SQLite; PostgreSQL is not implemented and must fail closed.

## v0.25 changes
- Extracted SQLite DDL from `job_repository.py` into `app/schema_sqlite.py`.
- Grouped schema DDL into Core Job, Outbox, Poll Task, and Operations/Alerts.
- Preserved migration markers 1-5 and idempotent initialization behavior.

## Evidence
- Backend pytest: 122 passed.
- Python compileall: passed.
- 3D Viewer structural validation: 19/19 passed.

## Limitations
- SQL query bodies and transaction logic remain in the monolithic SQLite repository.
- Schema module is SQLite-specific; it is not a PostgreSQL migration runner.
- No PostgreSQL runtime adapter, live PostgreSQL tests, multi-instance production rollout, or zero-downtime cutover.
- SQLite remains a single-host PoC; do not run multi-host workers against shared SQLite/NFS.
- Credit Quote / append-only Credit Ledger remain unimplemented.
- FASHN live contract, rights, retention, and commercial-use verification remain open.
- TypeScript/browser/WebGL/Android E2E and production deployment remain unverified.
- QA IDs T-01 through T-14 remain traceable; do not silently close gates.

## Next execution sequence
1. Physically extract Outbox, Poll Task, and Operations query implementations into aggregate-specific SQLite repositories.
2. Add transaction/session and SQL dialect boundaries while preserving atomic claim/transition semantics.
3. Implement PostgreSQL schema migration and adapter only with real server validation.
4. Test idempotency, transaction rollback, lease claim contention, and multi-instance behavior on PostgreSQL.
5. Only then design a staged zero-downtime cutover with verification and rollback checkpoints.
