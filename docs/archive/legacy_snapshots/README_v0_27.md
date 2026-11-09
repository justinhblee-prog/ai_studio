# AI CREATOR STUDIO v0.27 — Operations SQL Boundary

Operations snapshot, alert lifecycle, and alert-delivery SQL has been extracted into a dedicated SQLite-only module. Transaction orchestration and alert policy remain in the repository service layer.

## Validation
- Backend pytest: **130 passed**
- Python compileall: passed
- 3D Viewer structural checks: **19/19 passed**

## Status
SQLite remains the only implemented runtime. PostgreSQL adapter and live integration tests are not available yet. Do not interpret this milestone as zero-downtime migration or production multi-instance readiness.
