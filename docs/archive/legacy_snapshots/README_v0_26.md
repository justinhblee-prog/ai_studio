# AI CREATOR STUDIO v0.26 — SQL Dialect Boundary Extraction

This milestone extracts Outbox and Poll Task claim/recovery SQL into a SQLite-specific statement module while preserving existing transaction orchestration and behavior.

## Validation
- Backend pytest: **126 passed**
- Python compileall: passed
- 3D Viewer structural checks: **19/19 passed**

## Important status
Runtime remains SQLite-only. PostgreSQL is not implemented. The configured PostgreSQL backend must fail closed rather than silently use SQLite. This milestone is not a zero-downtime migration or multi-instance production deployment.

See `ai_creator_studio_backend_starter/docs/SQL_DIALECT_BOUNDARY_v0_1.md` and the v3.9 handoff for details and next steps.
