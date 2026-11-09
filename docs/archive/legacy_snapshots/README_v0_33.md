# AI CREATOR STUDIO v0.33 — Worker Repository Dependency Injection

## Scope
- Removed module-level repository singleton creation from Outbox, Provider Poll, and Operations Monitor worker modules.
- Worker operations now accept explicit repository ports; standalone process loops build one repository at startup and pass it through the full loop.
- Added `WorkerRepositories` and `build_worker_repositories()` as a shared worker composition root that validates the selected backend once and wires all worker ports to the same legacy SQLite implementation.
- Preserved compatibility for existing callers: one-shot worker functions still construct a repository when none is supplied.
- Preserved provider submission reconciliation behavior, bounded poll retries, atomic output finalization, and HTTPS-only alert webhook behavior.

## Validation
- Backend pytest: 143 passed.
- Python compileall: passed.
- 3D Viewer structural validation: 19/19 passed.

## Known limits
- Worker SQLite adapters still delegate operations not yet extracted into dedicated aggregate repositories to the legacy SQLite module.
- PostgreSQL runtime adapters and live PostgreSQL integration tests are not available; PostgreSQL selection remains fail-closed.
- Credit Quote / append-only Credit Ledger remain unimplemented.
- FASHN live contract, rights, retention, and commercial-use verification remain open.
- Browser/WebGL/Android end-to-end tests and production deployment remain unverified.
