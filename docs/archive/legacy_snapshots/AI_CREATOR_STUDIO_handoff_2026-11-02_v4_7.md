# AI CREATOR STUDIO Handoff — v0.34 / v4.7

## Current artifact
- Version: v0.34 Job/Event Atomic Unit of Work
- Project root: `AI_CREATOR_STUDIO_v0_34/`
- Backend: `ai_creator_studio_backend_starter/`
- Viewer: `ai_creator_studio_3d_viewer/`
- ZIP: `AI_CREATOR_STUDIO_v0_34_job_event_uow.zip`

## Completed
- Added `JobEventUnitOfWork` protocol and `SQLiteJobEventUnitOfWork` adapter.
- Added `JobLifecycleService` for transition/update/event access.
- Poll repository composes the service and routes lifecycle writes through it.
- SQLite lifecycle transition/update and Event append remain within the same transaction in the existing implementation.
- Added an integration test that injects an Event INSERT failure and verifies Job status rollback and absence of a partial Event.
- PostgreSQL selection remains fail-closed.

## Validation
- pytest: 147 passed.
- compileall: passed.
- Viewer structural validation: 19/19 passed.

## Limits
- SQLite UoW delegates SQL and transaction ownership to the legacy implementation; full aggregate SQL extraction remains in progress.
- No PostgreSQL runtime UoW or live PostgreSQL integration proof.
- Credit Quote / append-only Credit Ledger remain open.
- FASHN contract/rights/retention/commercial-use verification remains open.
- Browser/WebGL/Android E2E and production deployment remain unverified.

## Next
1. Further isolate Job/Event repository adapters from legacy SQL internals.
2. Route API reconciliation and operator lifecycle commands through the same atomic application service while preserving authorization and response contracts.
3. Verify PostgreSQL transaction, rollback, idempotency, lease, and multi-instance behavior when a real test server and supported driver are available.

## Engineering guardrails
- Never claim implementation without source and test evidence.
- Never silently fall back from PostgreSQL to SQLite.
- MANUAL provider selection must not auto-fallback.
- A Job may become SUCCEEDED only after Output and database references are persisted.
- Unknown provider submissions must not be automatically replayed.
- External contracts, costs, security-sensitive changes, and irreversible production actions require explicit approval.
