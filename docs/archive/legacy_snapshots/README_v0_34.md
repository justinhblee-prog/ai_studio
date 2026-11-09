# AI CREATOR STUDIO v0.34 — Job/Event Atomic Unit of Work

## Scope
- Added the `JobEventUnitOfWork` application port and SQLite adapter.
- Added `JobLifecycleService` to route lifecycle transitions and metadata updates through the Job/Event atomic command boundary.
- Composed the lifecycle service into the Provider Poll repository; worker transition/update commands now use the service rather than calling the legacy module directly.
- Kept the transaction owner in the existing SQLite implementation: each transition/update changes Job (and relevant Execution state) and appends its Event in the same database transaction.
- Explicitly documented that this is an atomic command UoW, not a caller-managed transaction spanning several independent commits.
- PostgreSQL selection fails closed.

## Validation
- Backend pytest: 147 passed.
- Python compileall: passed.
- 3D Viewer structural validation: 19/19 passed.
- Added injected Event INSERT failure test proving the Job transition rolls back with the Event write.

## Known limits
- SQLite UoW delegates SQL and transaction ownership to the audited legacy implementation; aggregate SQL extraction is not complete.
- PostgreSQL runtime UoW and live server integration tests are not available.
- Credit Quote / append-only Credit Ledger remain unimplemented.
- FASHN live contract, rights, retention, and commercial-use verification remain open.
- Browser/WebGL/Android end-to-end tests and production deployment remain unverified.
