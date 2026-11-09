# AI CREATOR STUDIO v0.76

SQLite concurrent idempotency regression.

- Added a 12-worker race for simultaneous Generation Job creation with one workspace-scoped idempotency key.
- Verifies one canonical Job, one creator, and one idempotency record.
- This is SQLite single-host concurrency evidence, not PostgreSQL or multi-host proof.
