# AI CREATOR STUDIO Handoff v3.7 — v0.24

## Current baseline
- Latest milestone: v0.24 Worker Repository Port Extraction.
- Source root: `AI_CREATOR_STUDIO_v0_24/`.
- Backend: `ai_creator_studio_backend_starter/`.
- API/workers still run on SQLite. PostgreSQL is intentionally rejected.

## v0.24 changes
- Added role-specific Outbox, Poll, and Operations repository Protocols.
- Added SQLite compatibility adapters and builders.
- Routed the three worker modules through those builders.
- Kept legacy SQL and transaction behavior unchanged to minimize migration risk.

## Evidence
- Backend pytest: 119 passed.
- Python compileall: passed.
- 3D Viewer structural validation: 19/19 passed.

## Important limitations
- These are application-level ports; adapters still delegate to the monolithic SQLite `job_repository`.
- No PostgreSQL runtime adapter or live PostgreSQL integration test exists.
- No multi-instance production deployment or zero-downtime cutover has been completed.
- SQLite remains a single-host PoC; do not run multi-host workers against shared SQLite/NFS.
- Credit Quote / append-only Credit Ledger remain unimplemented.
- FASHN live contract, rights, retention, and commercial-use verification remain open.
- TypeScript/browser/WebGL/Android E2E and production deployment remain unverified.
- QA IDs T-01 through T-14 remain traceable; do not silently close gates.

## Next execution sequence
1. Physically split Outbox / Poll Task / Operations SQL repositories while preserving transactional invariants.
2. Introduce driver-neutral session, transaction, row, and placeholder/dialect boundaries.
3. Add PostgreSQL migration runner and adapter.
4. Provision a real PostgreSQL test service and verify idempotency, atomic state transitions, lease claims, and multi-instance contention.
5. Design staged cutover (read-only shadow verification, controlled writer handoff, rollback checkpoints) only after evidence exists.

## Non-negotiable invariants
- MANUAL provider selection never auto-falls back.
- Job and Execution attempt statuses remain distinct.
- Job is SUCCEEDED only after Output and DB references persist.
- Credit Ledger remains append-only and idempotent when implemented.
- Outbox/idempotency recovery semantics must be preserved.
- Tenant isolation, rights/region/retention, and upload validation remain mandatory.
