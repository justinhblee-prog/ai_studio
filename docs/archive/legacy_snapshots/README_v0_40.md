# AI CREATOR STUDIO v0.40

## Outbox Repository Port Extraction

- Added `app.repositories.outbox.OutboxRepository` and `SQLiteOutboxRepository`.
- Routed the Outbox worker repository builder through the dedicated adapter.
- Kept legacy worker-facing names and call signatures for compatibility.
- Preserved fail-closed behavior for PostgreSQL; no SQLite fallback.
- The SQLite adapter still delegates audited transactional SQL to `job_repository`; this release extracts the boundary, not the underlying SQL implementation.

## Verification
- Backend: 158 tests passed.
- Python compileall: passed.
- 3D Viewer structural validation: 19/19 passed.
