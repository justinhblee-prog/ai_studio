# AI CREATOR STUDIO Handoff v3.9 — v0.26

## Current baseline
- Latest milestone: v0.26 SQL Dialect Boundary Extraction.
- Source root: `AI_CREATOR_STUDIO_v0_26/`.
- Backend: `ai_creator_studio_backend_starter/`.
- Runtime remains SQLite-only. PostgreSQL must fail closed; no fallback.

## v0.26 changes
- Extracted Outbox SQL statements to `app/sql/sqlite_worker.py`.
- Extracted Poll Task claim/recovery SQL statements to the same SQLite-specific module.
- Kept transaction orchestration and domain state transitions in `job_repository.py`.
- Added tests for compare-and-set claim guards, attempt increments, deterministic selection, Outbox UNKNOWN handling, and safe Poll lease requeue.

## Evidence
- Backend pytest: 126 passed.
- Python compileall: passed.
- 3D Viewer structural validation: 19/19 passed.

## Preserved safety properties
- Outbox expired dispatch lease transitions to reconciliation; it is not automatically replayed.
- Poll GET/output task expired lease can be safely requeued under current task semantics.
- Claim updates retain pending-state guards and atomic attempt increments.
- Existing SQLite transaction semantics are unchanged.

## Limitations
- SQL statement extraction is SQLite-only; no PostgreSQL dialect exists.
- No PostgreSQL live server, transaction, concurrency, or multi-instance tests were run.
- Job/Event/Output and Operations/Alert SQL still require extraction.
- No zero-downtime cutover or production multi-instance rollout has occurred.
- SQLite remains a single-host PoC; do not run multi-host workers against shared SQLite/NFS.
- Credit Quote / append-only Credit Ledger remain unimplemented.
- FASHN live contract, rights, retention, and commercial-use verification remain open.
- TypeScript/browser/WebGL/Android E2E and production deployment remain unverified.
- QA IDs T-01 through T-14 remain traceable; do not silently close gates.

## Next execution sequence
1. Extract Operations/Alert SQL into its own SQLite query module.
2. Extract Job/Event/Output SQL and define a complete transaction/session contract.
3. Implement PostgreSQL only after a real server-backed integration environment is available.
4. Validate idempotency, rollback, lease claims, event/output atomicity, and multi-instance contention on PostgreSQL.
5. Only then design staged zero-downtime cutover with dual-read/write or replication strategy, reconciliation, observability, and rollback checkpoints.
