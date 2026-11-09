# BUILD-00230 — PostgreSQL Project/Product relationship

Date: 2026-11-07
Base: BUILD-00229

## Implemented
- Added migration `0008_project_product_assignments.sql`.
- Added tenant-safe composite foreign keys from assignments to both Project and Product within the same Workspace.
- Added active-assignment partial uniqueness, retained removal history, ordering, and append-only assignment events.
- Enabled RLS on assignment and assignment-event tables; client access remains default-deny.
- Added `PostgreSQLProjectProductRepository` for ordered assignment listing/replacement, role enforcement, active Project/Product checks, retained history, and event recording.
- Applied migration `add_project_product_assignments_0008` to TEST Supabase (`AI-CREATOR-STUDIO-TEST`, `niktytizbtvxypwswbcc`).
- Verified both tables exist with RLS enabled, indexes present, and grants limited to `postgres` and `service_role`.

## Verification
- Focused PostgreSQL Project/Product/assignment/migration/readiness tests: 49 passed.
- Python compileall: passed.
- TEST Supabase migration 0008: applied successfully.
- Catalog checks for RLS, indexes and grants: passed.
- Full backend pytest was not re-run to completion; prior full-suite attempts timed out at ~63% and ~80%.

## Not implemented / not verified
- PostgreSQL Project, Product and assignment repositories are not selected by FastAPI runtime; API routes remain SQLite-backed.
- Product Variant CRUD is not implemented in the PostgreSQL repository (schema only).
- No live FastAPI CRUD/assignment request or two-user tenant isolation test was run.
- No Supabase Storage byte lifecycle, Vite build, browser E2E, AI Provider execution or Vercel Preview was completed.

## Release decision
Not production-ready. Do not switch `DATABASE_BACKEND=postgresql` or deploy to Production until all API aggregates, workers and Storage paths are migrated and live-tested.
