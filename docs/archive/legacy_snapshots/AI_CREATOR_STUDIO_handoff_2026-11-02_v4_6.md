# AI CREATOR STUDIO Handoff — v0.33 / v4.6

## Current artifact
- Version: v0.33 Worker Repository Dependency Injection
- Project root: `AI_CREATOR_STUDIO_v0_33/`
- Backend: `ai_creator_studio_backend_starter/`
- Viewer: `ai_creator_studio_3d_viewer/`
- ZIP: `AI_CREATOR_STUDIO_v0_33_worker_repository_di.zip`

## Completed
- Outbox, Provider Poll, and Operations Monitor workers no longer create module-level repository singletons.
- Worker one-shot functions accept explicit repository ports.
- Long-running loops build their repository once and pass it to all operations in that process.
- Added `WorkerRepositories` composition bundle and `build_worker_repositories()`; all three worker ports share the same legacy SQLite implementation.
- Backward-compatible no-argument one-shot calls remain supported.
- Provider MANUAL/no-fallback, bounded polling, unknown submission reconciliation, atomic Output finalization, and HTTPS-only webhook constraints retained.

## Validation
- pytest: 143 passed.
- compileall: passed.
- Viewer structural validation: 19/19 passed.

## Limits
- Some worker adapter operations still delegate to legacy `job_repository` SQL implementation.
- PostgreSQL runtime adapter and live PostgreSQL integration evidence are absent; backend selection fails closed.
- Credit Quote / append-only Credit Ledger remain open.
- FASHN contract/rights/retention/commercial-use verification remains open.
- Browser/WebGL/Android E2E and production deployment remain unverified.

## Next
1. Define a service-level Job/Event Unit of Work so state transition and append-only Event persistence share one transaction boundary.
2. Add rollback and concurrency tests without changing API response contracts.
3. Implement and verify PostgreSQL runtime adapters only when a real server and supported driver are available.

## Engineering guardrails
- Never claim implementation without source and test evidence.
- Never silently fall back from PostgreSQL to SQLite.
- MANUAL provider selection must not auto-fallback.
- A Job may become SUCCEEDED only after Output and database references are persisted.
- Unknown provider submissions must not be automatically replayed.
- External contracts, costs, security-sensitive changes, and irreversible production actions require explicit approval.
