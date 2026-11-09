# AI CREATOR STUDIO v0.52

## Operations Monitoring Repository Extraction

- Added `OperationsMonitoringRepository` and a dedicated SQLite adapter for bounded operational snapshots and alert evaluation.
- Worker heartbeat, Outbox/Poll aggregate counts, oldest queue age, alert aggregates, and delivery aggregates now live behind the monitoring repository.
- Alert fingerprint create/update/resolve logic now executes in the dedicated repository transaction.
- Legacy `operational_snapshot` and `evaluate_operational_alerts` are compatibility facades.
- Added tests proving the legacy monitoring facade is bypassed and repeated evaluation does not duplicate active fingerprints.

## Verification
- Backend pytest: 178 passed.
- Python compileall: passed.
- 3D Viewer structural validation: 19/19 passed.
- ZIP integrity: passed.

## Remaining boundaries
- Prometheus text rendering remains an API/application presentation concern and uses the repository snapshot contract.
- SQLite remains the only implemented runtime backend; PostgreSQL runtime adapter and server-backed tests remain incomplete.
- No production zero-downtime migration/cutover proof.
- Credit Quote/Ledger, FASHN rights/contract verification, frontend E2E, and production deployment remain open.
