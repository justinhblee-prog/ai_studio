# AI CREATOR STUDIO Handoff v5.1 — v0.41

## Baseline
- v0.41 source contains dedicated Outbox and Poll repository ports/adapters.
- `app/repositories/outbox.py`: provider submission dispatch boundary.
- `app/repositories/poll.py`: provider polling/output persistence worker boundary.
- Compatibility facade names remain under `app/worker_repositories.py`.

## Verification
- Backend pytest 160 passed.
- Python compileall passed.
- Viewer structural checks 19/19 passed.

## Next
- Extract operator-facing Poll Task list/retry operations into a separate admin repository port.
- Separate Outbox operator reconciliation from dispatch worker repository.
- Move SQL ownership out of `job_repository.py` in small transactional units.
- PostgreSQL runtime and migration proof remain outstanding.

## Open risks
SQLite is the only implemented runtime backend. Credit Quote/Ledger and FASHN live commercial/rights/retention verification remain open. Browser/WebGL/Android E2E and production deployment remain unverified.
