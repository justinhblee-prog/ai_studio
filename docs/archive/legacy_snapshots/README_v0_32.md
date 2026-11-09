# AI CREATOR STUDIO v0.32 — API Repository Dependency Injection

## Scope
- Routed remaining Generation Job API operations through the cached repository dependency: health, reconciliation, poll-task administration, worker health, metrics, alerts, and private output authorization.
- Startup initialization now uses the Job repository composition root.
- Extended SQLite adapter compatibility forwarding for operations not yet extracted into dedicated ports.
- Kept the existing public API response contracts and role checks.
- PostgreSQL remains fail-closed; no silent SQLite fallback.

## Validation
- Backend pytest: 139 passed.
- Python compileall: passed.
- 3D Viewer structural validation: 19/19 passed.

## Limits
- The adapter still delegates to legacy SQLite implementation for operations not yet extracted.
- No PostgreSQL runtime adapter or live PostgreSQL integration evidence.
- No zero-downtime migration or production cutover.
- Credit Quote/Ledger, FASHN live rights/contract/retention/commercial-use verification, browser/WebGL/Android E2E and production deployment remain open.
