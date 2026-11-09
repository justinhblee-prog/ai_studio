# AI CREATOR STUDIO Handoff v5.28 — v0.66

## Completed
- Outbox submission and unknown-outcome transaction rollback are covered by failure injection.
- Poll provider-success phase handoff rolls back Job, Execution, and Poll Task when Event append fails.
- Runtime application code has no imports of the legacy Job facade; the facade remains for old tests/tools only.

## Next
1. Add Poll retry-exhaustion and Output finalization audit-failure coverage where not already covered.
2. Review transaction ownership for manual reconciliation and Alert Delivery completion.
3. Decide whether to implement Credit Ledger only after resolving Organization vs Workspace account scope, unit precision, expiry, and partial capture policy.
4. Provision a real PostgreSQL server/driver before claiming PostgreSQL runtime readiness.

## Open risks
- SQLite remains the only implemented runtime backend; PostgreSQL adapter/live integration tests unavailable.
- Credit Quote and append-only Credit Ledger remain unimplemented.
- FASHN rights/contract/retention/commercial-use verification, frontend E2E, and production deployment remain open.
- No production zero-downtime migration/cutover/rollback proof.
