# AI CREATOR STUDIO v0.23 — Shared Storage Port

v0.23 extends the v0.22 storage-port extraction to asset/workspace metadata. Both Generation Job persistence and asset metadata now obtain SQLite connections through the explicit storage backend selector.

## Validation
- Backend pytest: 116 passed
- Python compileall: passed
- 3D Viewer structural validation: 19/19 passed
- PostgreSQL runtime: not implemented and intentionally fails closed

## Important boundary
This release does not claim PostgreSQL compatibility or zero-downtime database migration. SQLite-specific DDL, placeholders, conflict syntax, exception types, and worker claim semantics remain. SQLite is still a single-host proof of concept; do not run multi-host workers against shared SQLite/NFS.

See `AI_CREATOR_STUDIO_handoff_2026-11-02_v3_6.md` for evidence, limitations, and next steps.
