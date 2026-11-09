# AI CREATOR STUDIO v0.48

## Worker Heartbeat Repository Extraction

- Added a dedicated `WorkerHeartbeatRepository` port and SQLite adapter.
- Worker heartbeat upsert SQL moved out of `job_repository.py`.
- Operations Worker Composition Root now uses the dedicated heartbeat adapter; alert evaluation and webhook-delivery SQL remain compatibility-bridged.
- Added tests proving heartbeat writes do not call the legacy module.

## Verification
- Backend pytest: 170 passed.
- Python compileall: passed.
- 3D Viewer structural validation: 19/19 passed.
- ZIP integrity: passed.

## Remaining boundaries
- SQLite remains the only implemented runtime backend; PostgreSQL runtime adapter/server-backed tests are incomplete.
- No production zero-downtime migration/cutover proof.
- Credit Quote and append-only Credit Ledger are not implemented.
- FASHN contract, rights, retention, and commercial-use verification remain open.
- TypeScript/browser/WebGL/Android E2E and production deployment remain unverified.
