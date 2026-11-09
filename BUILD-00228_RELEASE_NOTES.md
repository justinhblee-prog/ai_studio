# BUILD-00228 — PostgreSQL Project persistence foundation

Date: 2026-11-07
Base: BUILD-00227

## Implemented
- Added PostgreSQL migration `0006_projects.sql` for durable Workspace-scoped Projects.
- Added project constraints, workspace foreign key with cascade, status validation, description/reference bounds, and workspace query indexes.
- Enabled RLS on `projects`; no end-user RLS policy was added, preserving default-deny client access.
- Added `PostgreSQLProjectRepository` with create/list/get/update operations and workspace-role enforcement.
- Added validation and authorization tests for project creation/update and migration properties.
- Applied migration `add_projects_aggregate_0006` to the TEST Supabase project `AI-CREATOR-STUDIO-TEST` (`niktytizbtvxypwswbcc`).
- Verified TEST database catalog: `projects` exists, RLS is enabled, and 3 indexes exist (primary key + 2 query indexes).
- Verified grants: `service_role` and `postgres` only; no `anon` or `authenticated` table grants were returned.

## Verification
- Focused PostgreSQL project + migration + readiness tests: 31 passed.
- Python compileall: passed.
- Full backend pytest suite was attempted twice but exceeded the execution time limit at approximately 63% and 80%; this build does not claim a full-suite pass.

## Not implemented / not verified
- Project repository is not yet selected by FastAPI runtime; API routes still use SQLite.
- No PostgreSQL DSN was used by the local runner; repository operations were validated with unit-level fake connection tests, not live application-driver calls.
- No live user/project CRUD transaction was executed through FastAPI.
- Workspace, Product, Character, Photo, Lookbook, Job, Asset and Output aggregates are not all migrated to PostgreSQL runtime.
- No Vite build, browser E2E, or Vercel Preview was completed.

## Release decision
Not production-ready. This is a database schema + repository foundation step only. Do not set `DATABASE_BACKEND=postgresql` or deploy to Production until every aggregate adapter and API path is migrated and live-tested.
