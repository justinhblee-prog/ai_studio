# AI CREATOR STUDIO Handoff v5.12 — v0.50

## Baseline
- v0.44: Outbox dispatch SQL extracted.
- v0.45: Poll Task worker SQL extracted.
- v0.46: Poll Task administration SQL extracted.
- v0.47: Outbox reconciliation administration SQL extracted.
- v0.48: Worker heartbeat upsert SQL extracted.
- v0.49: Alert delivery queue mutation SQL extracted.
- Current milestone: Worker Health and Queue Count Repository Extraction.

## Completed
- Added WorkerHealthRepository with dedicated SQLite reads for worker heartbeat health, Outbox counts, and Poll Task counts.
- `job_repository.worker_health`, `outbox_counts`, and Poll Task count helper now act as compatibility facades.
- Operational snapshot/alert evaluation still owns additional aggregate SQL and is explicitly left for a later extraction.
- Added tests proving health reads and counts bypass the legacy facade.

## Verification
- Backend pytest: 174 passed.
- Python compileall: passed.
- 3D Viewer structural validation: 19/19 passed.

## Next
1. Move operational snapshot and alert evaluation SQL to dedicated repository boundaries.
2. Separate alert listing and metrics read models.
3. Add failure-injection/concurrency coverage.
4. Implement PostgreSQL runtime only with actual server-backed integration evidence.

## Open risks
- SQLite remains the only implemented runtime backend.
- No production zero-downtime migration/cutover evidence.
- Credit Quote and append-only Credit Ledger remain unimplemented.
- FASHN live contract/rights/retention/commercial-use verification remains open.
- TypeScript build, browser/WebGL/Android E2E, and production deployment are unverified.
