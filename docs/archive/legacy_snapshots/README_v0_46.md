# AI CREATOR STUDIO v0.46

## Poll Admin SQLite SQL Extraction

- `SQLitePollTaskAdminRepository` now owns workspace-scoped Poll Task listing and operator retry SQL.
- Operator retry continues to validate job phase and Provider identifiers, and appends an actor-attributed Event in the same transaction.
- `job_repository.py` admin list/retry functions are compatibility facades.
- Added focused extraction tests proving worker and admin adapters no longer call legacy SQL entry points.

## Verification
- Backend pytest: 168 passed.
- Python compileall: passed.
- 3D Viewer structural validation: 19/19 passed.
- ZIP integrity: checked after packaging.

## Boundaries
- SQLite remains the only implemented runtime backend. PostgreSQL runtime adapter and server-backed tests are not complete.
- No production zero-downtime migration/cutover has been implemented or verified.
- Credit Quote / append-only Credit Ledger remain open.
- FASHN contract, rights, retention, and commercial-use verification remain open.
- TypeScript build, browser/WebGL/Android E2E, and production deployment remain unverified.
