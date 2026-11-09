# AI CREATOR STUDIO v0.35 — API Lifecycle Service Integration

## Scope
- Extended `JobEventUnitOfWork` with operator reconciliation of unknown provider submissions.
- Extended `JobLifecycleService` to expose the same atomic reconciliation command.
- Added a cached Job/Event UoW dependency and lifecycle-service dependency.
- Routed the authenticated Generation Job reconciliation API through `JobLifecycleService` rather than calling the legacy repository directly.
- Preserved owner/admin authorization, request validation, conflict handling, and response schema.
- SQLite reconciliation continues to persist Job changes and audit Event in its existing transaction; PostgreSQL remains fail-closed.

## Validation
- Backend pytest: 148 passed.
- Python compileall: passed.
- 3D Viewer structural validation: 19/19 passed.

## Known limits
- SQL and transaction ownership still live in the audited SQLite implementation behind the UoW adapter.
- PostgreSQL runtime adapter and live server integration remain unavailable.
- Credit Quote / append-only Credit Ledger remain unimplemented.
- FASHN live contract, rights, retention, and commercial-use verification remain open.
- Browser/WebGL/Android end-to-end tests and production deployment remain unverified.
