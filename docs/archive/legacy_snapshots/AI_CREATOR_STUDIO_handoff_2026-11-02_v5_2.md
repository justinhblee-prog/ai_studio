# AI CREATOR STUDIO Handoff v5.2 — v0.42

## Baseline
- v0.40: dedicated Outbox repository port/adapter.
- v0.41: dedicated Poll worker repository port/adapter.
- v0.42: dedicated Poll Task admin repository port/adapter and API dependency injection.
- API poll-task list/retry endpoints no longer depend on the broad JobRepository contract.

## Verification
- Backend pytest: 162 passed.
- Python compileall: passed.
- 3D Viewer structural validation: 19/19 passed.

## Next
1. Separate Outbox reconciliation administration from worker dispatch port.
2. Move remaining Poll Task and Outbox SQL ownership from `job_repository.py` into dedicated adapters, preserving transaction boundaries.
3. Add transaction-level fault injection for all cross-aggregate operations.
4. Reassess PostgreSQL runtime adapter prerequisites; only report live tests after actual server-backed execution.

## Open risks
- SQLite remains the only implemented runtime backend.
- No zero-downtime migration/cutover proof.
- Credit Quote/append-only Credit Ledger not implemented.
- FASHN live contract, rights, retention, and commercial-use verification open.
- TypeScript build/browser/WebGL/Android E2E and production deployment unverified.
