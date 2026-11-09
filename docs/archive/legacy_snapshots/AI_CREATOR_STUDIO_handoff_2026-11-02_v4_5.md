# AI CREATOR STUDIO Handoff — v0.32 / v4.5

## Current artifact
- Version: v0.32 API Repository Dependency Injection
- Project root: `AI_CREATOR_STUDIO_v0_32/`
- Backend: `ai_creator_studio_backend_starter/`
- ZIP: `AI_CREATOR_STUDIO_v0_32_api_repository_di.zip`

## Completed
- All primary Generation Job API operations now obtain the Job repository via FastAPI dependency injection.
- Startup schema initialization uses the repository composition root.
- Event API preserves its diagnostics response shape and role checks.
- SQLite adapter forwards remaining legacy operations while extraction proceeds.
- PostgreSQL remains fail-closed.

## Validation
- pytest: 139 passed.
- compileall: passed.
- Viewer structural validation: 19/19 passed.

## Limits
- SQLite adapter still delegates unextracted SQL operations to legacy module.
- No live PostgreSQL runtime adapter or PostgreSQL integration proof.
- No zero-downtime Dual Write/CDC/cutover/rollback.
- Credit Quote/Ledger remains open.
- FASHN rights/contract/retention/commercial-use verification remains open.
- Browser/WebGL/Android E2E and production deployment remain unverified.

## Next
1. Move Worker entrypoints to shared repository composition root and remove module-level singleton coupling.
2. Introduce service-level Job/Event Unit of Work without weakening append-only event and atomic transition semantics.
3. Obtain PostgreSQL server/driver and test schema migration, idempotency, row locking, leases, rollback and multi-instance behavior.
4. Plan zero-downtime stages only after parity evidence.

## Safety rules
- Never claim PostgreSQL readiness without live evidence.
- MANUAL provider selection must not auto-fallback.
- Job succeeds only after output and database references are persisted.
- Production cutover, external contracts, costs, security and irreversible actions require approval.
