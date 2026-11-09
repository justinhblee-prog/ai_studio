# AI CREATOR STUDIO Handoff v4.1 — v0.28

## Current baseline
- Latest milestone: v0.28 Unit of Work Contract.
- Source root: `AI_CREATOR_STUDIO_v0_28/`.
- Runtime remains SQLite-only; PostgreSQL must fail closed.

## v0.28 changes
- Added `StorageBackend.transaction(database_path)` to the storage protocol.
- SQLite transaction context now owns connection open/close, commit on success, and rollback on exceptions.
- Migrated 31 Generation Job repository connection scopes to the storage transaction boundary.
- Preserved explicit SQLite `BEGIN IMMEDIATE` on serialized multi-statement write paths.
- Added commit, rollback, connection-close, and partial-create rollback tests.

## Evidence
- Backend pytest: 132 passed.
- Python compileall: passed.
- 3D Viewer structural validation: 19/19 passed.

## Transaction semantics warning
The context manager owns connection lifetime and finalization; it does not automatically begin a transaction. Critical multi-statement write paths must continue to call `begin_write`. This avoids double-BEGIN errors and preserves current SQLite serialization.

## Limitations
- SQLite is the only implemented StorageBackend.
- No PostgreSQL pool, isolation configuration, savepoints, or SKIP LOCKED claims.
- No PostgreSQL live transaction/concurrency/multi-instance tests.
- No zero-downtime production cutover has occurred.
- SQLite remains a single-host PoC; do not run multi-host workers against shared SQLite/NFS.
- Credit Quote / append-only Credit Ledger remain unimplemented.
- FASHN live contract, rights, retention, and commercial-use verification remain open.
- TypeScript/browser/WebGL/Android E2E and production deployment remain unverified.
- QA IDs T-01 through T-14 remain traceable; do not silently close gates.

## Next execution sequence
1. Extract Job/Event/Output SQL into aggregate-specific SQLite modules.
2. Define explicit read/write/serialized-write transaction modes.
3. Extend StorageBackend contract only when a PostgreSQL implementation can satisfy it.
4. Validate idempotency, rollback, lease claims, output/event atomicity, and multi-instance contention on a real PostgreSQL server.
5. Plan staged zero-downtime cutover with reconciliation and rollback checkpoints only after integration gates pass.
