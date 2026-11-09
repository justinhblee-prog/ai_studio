# AI CREATOR STUDIO v0.28 — Unit of Work Contract

Introduced a backend-owned transaction context for Generation Job persistence. It owns connection creation/closure and commit/rollback behavior; existing SQLite `BEGIN IMMEDIATE` serialization remains explicit.

## Validation
- Backend pytest: **132 passed**
- Python compileall: passed
- 3D Viewer structural checks: **19/19 passed**

SQLite remains the only implemented runtime. PostgreSQL, multi-instance production operation, and zero-downtime cutover are not complete.
