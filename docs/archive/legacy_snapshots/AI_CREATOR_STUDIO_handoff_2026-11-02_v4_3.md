# AI CREATOR STUDIO Handoff v4.3 — 2026-11-02

## Current baseline
- Version: v0.30 Output Repository Extraction
- Source: `AI_CREATOR_STUDIO_v0_30/`
- Runtime database: SQLite only

## Completed through v0.30
- v0.29 introduced atomic Output finalization: Output row, Job succeeded/API reference, latest Execution success, lifecycle Event, and owned Poll Task completion are committed together.
- v0.30 extracted Output aggregate into `OutputRepository` Protocol and `SQLiteOutputRepository` implementation.
- `job_repository.py` retains compatibility facades; `SQLitePollRepository` composes the dedicated Output adapter.
- Validation: 136 pytest passed; compileall passed; Viewer structural validation 19/19.

## Critical invariants
- Job may only become `succeeded` after Output metadata and API reference are persisted in the same DB transaction.
- Execution attempt status and Job status are distinct.
- MANUAL provider selection never auto-falls back; unknown provider submission is never auto-replayed.
- Tenant isolation, rights/region/retention, upload validation, append-only idempotent Credit Ledger design, QA T-01..T-14 traceability remain mandatory.

## Open / unverified
- PostgreSQL adapter and live PostgreSQL integration tests.
- PostgreSQL multi-instance claim/lease semantics and `FOR UPDATE SKIP LOCKED` tests.
- Output binary storage + DB crash recovery, temporary object key promotion, checksum and orphan reconciliation.
- Dual-write/CDC, cutover rehearsal, rollback and true zero-downtime migration.
- Credit Quote / append-only Credit Ledger.
- FASHN live contract, rights, retention and commercial-use verification.
- TypeScript/browser/WebGL/Android E2E and production deployment.

## Next steps
1. Extract Generation Job and Event repositories; retain compatibility facades until callsites are migrated.
2. Inject aggregate repositories explicitly into API and worker service boundaries.
3. Implement PostgreSQL adapter only against the same protocols and run live rollback/idempotency/lease/multi-instance tests.
4. Design object-store promotion and orphan reconciliation before claiming end-to-end file+DB atomicity.
5. Keep all unresolved QA gates explicit.
