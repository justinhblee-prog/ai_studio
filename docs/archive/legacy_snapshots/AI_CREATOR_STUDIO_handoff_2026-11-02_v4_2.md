# AI CREATOR STUDIO Handoff v4.2 — 2026-11-02

## Current baseline
- Version: v0.29 Atomic Output Finalization
- Source: `AI_CREATOR_STUDIO_v0_29/`
- Backend: `ai_creator_studio_backend_starter/`
- Runtime database: SQLite only

## v0.29 completed
- Added one atomic repository operation to finalize provider output.
- The transaction validates poll-task lease ownership and persists Output metadata, Job success/API reference, Execution success, lifecycle Event, and Poll Task completion together.
- Poll Worker now uses the atomic operation.
- Failure injection confirms all DB writes roll back together: Job remains `post_processing`, Output row is absent, and task remains processing/owned for retry.
- Validation: 134 pytest passed; compileall passed; Viewer structural validation 19/19.

## Invariants to preserve
- Job may only become `succeeded` after Output metadata and API reference are persisted in the same DB transaction.
- Execution attempt status remains distinct from Job status.
- Outbox unknown submission must not auto-replay; MANUAL provider selection must not auto-fallback.
- Credit Ledger must be append-only/idempotent when implemented.
- Tenant isolation, rights/region/retention, upload validation, and QA T-01..T-14 traceability remain mandatory.

## Open / not verified
- PostgreSQL runtime adapter and live PostgreSQL integration tests.
- Multi-instance claim/lease tests on PostgreSQL (`FOR UPDATE SKIP LOCKED` semantics).
- File/object-store + DB crash recovery and orphan cleanup policy beyond current retry overwrite behavior.
- Dual-write/CDC, cutover rehearsal, rollback and true zero-downtime migration.
- Credit Quote / append-only Credit Ledger.
- FASHN live contract, rights, retention and commercial-use verification.
- TypeScript/browser/WebGL/Android E2E and production deployment.

## Next steps
1. Extract Job/Event/Output SQL and repository contracts fully from the legacy `job_repository.py` module.
2. Define PostgreSQL transaction implementation against the same Unit of Work contract; do not enable selection until live tests pass.
3. Test output-finalization rollback, idempotent retries, lease loss, and multi-instance races on a real PostgreSQL service.
4. Design object storage promotion/temporary key + checksum + orphan reconciliation before claiming end-to-end atomicity.
5. Keep all unresolved QA gates explicit.
