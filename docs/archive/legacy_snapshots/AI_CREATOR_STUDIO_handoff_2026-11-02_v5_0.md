# AI CREATOR STUDIO Handoff v5.0 — v0.40

## Current baseline
- Source: AI_CREATOR_STUDIO_v0_40
- Outbox Repository port and SQLite adapter are in `app/repositories/outbox.py`.
- Worker builder resolves the dedicated adapter; compatibility facade remains in `worker_repositories.py`.
- Outbox transactional SQL is still delegated to `app/job_repository.py`.

## Verification
- Backend pytest: 158 passed
- compileall: passed
- 3D Viewer structural checks: 19/19 passed

## Next
1. Extract Poll Task repository port and adapter into `app/repositories/poll.py`.
2. Keep Output finalization and Job/Event lifecycle transactional boundaries intact.
3. Separate operator-facing Poll Task administration from worker lease operations.
4. Continue PostgreSQL runtime feasibility checks; do not claim PG runtime or zero-downtime migration.

## Open risks
- SQLite is still the only implemented runtime backend.
- Credit Quote/Ledger remains unimplemented.
- FASHN live contract, rights, retention, and commercial-use verification remains open.
- TypeScript/browser/WebGL/Android E2E and production deployment remain unverified.
