# AI CREATOR STUDIO v0.50

## Worker Health and Queue Count Repository Extraction

- Added WorkerHealthRepository with dedicated SQLite reads for worker heartbeat health, Outbox counts, and Poll Task counts.
- `job_repository.worker_health`, `outbox_counts`, and Poll Task count helper now act as compatibility facades.
- Operational snapshot/alert evaluation still owns additional aggregate SQL and is explicitly left for a later extraction.
- Added tests proving health reads and counts bypass the legacy facade.

## Verification
- Backend pytest: 174 passed.
- Python compileall: passed.
- 3D Viewer structural validation: 19/19 passed.
- ZIP integrity: passed.

## Remaining boundaries
- SQLite remains the only implemented runtime backend; PostgreSQL runtime adapter and server-backed tests are incomplete.
- No production zero-downtime migration/cutover proof.
- Credit Quote and append-only Credit Ledger are not implemented.
- FASHN contract, rights, retention, and commercial-use verification remain open.
- TypeScript/browser/WebGL/Android E2E and production deployment remain unverified.
