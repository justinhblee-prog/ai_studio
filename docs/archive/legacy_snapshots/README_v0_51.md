# AI CREATOR STUDIO v0.51

## Operations Alert Read Repository Extraction

- Added `OperationsAlertReadRepository` and a dedicated SQLite read adapter for workspace-independent, bounded alert listing.
- Alert listing SQL and details JSON decoding moved out of `job_repository.py`.
- Existing status filter and 1–200 row limit are preserved.

## Verification
- Backend pytest: 176 passed.
- Python compileall: passed.
- 3D Viewer structural validation: 19/19 passed.
- ZIP integrity: passed.

## Remaining boundaries
- Operational snapshot and alert evaluation still retain aggregate SQL in the legacy module.
- SQLite is the only implemented runtime backend; PostgreSQL runtime adapter and server-backed tests remain incomplete.
- No production zero-downtime migration/cutover proof.
- Credit Quote/Ledger, FASHN rights/contract verification, and frontend E2E remain open.
