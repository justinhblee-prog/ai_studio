# AI CREATOR STUDIO v0.31 — Job/Event Repository Ports + API DI

## Scope
- Added application-facing `JobRepository` and append-only `EventRepository` protocols.
- Added SQLite compatibility adapters that delegate to the audited legacy implementation.
- Added cached composition-root providers in `app/dependencies.py`.
- Injected Job and Event repositories into the create/read/event API endpoints through FastAPI `Depends`.
- Preserved the existing `/events` response contract, including execution/output/outbox/poll diagnostics.
- PostgreSQL remains fail-closed; no SQLite fallback is permitted when PostgreSQL is selected.

## Validation
- Backend pytest: 139 passed.
- `python -m compileall -q app scripts tests`: passed.
- 3D Viewer source validation: 19/19 passed.

## Important limits
- SQLite adapters still delegate to the legacy SQLite SQL implementation; this is a boundary extraction, not a PostgreSQL adapter.
- PostgreSQL server/driver integration, multi-instance claim tests, production deployment, browser/WebGL runtime, and Android E2E remain unverified.
- Credit Quote/Ledger and FASHN live rights/contract/retention/commercial-use verification remain open.
- No zero-downtime migration or production cutover is claimed.
