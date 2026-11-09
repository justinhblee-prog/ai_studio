# AI CREATOR STUDIO — Current Handoff BUILD-00228

- Date: 2026-11-07
- Engineering build: BUILD-00228
- Base: BUILD-00227
- Scope: PostgreSQL Project aggregate schema and repository foundation, TEST Supabase migration.

## 1. Changes

### PostgreSQL schema
- Added `app/sql/postgres/migrations/0006_projects.sql`.
- `projects.workspace_id` references `workspaces` with cascade delete.
- Added constraints for name/type/status/description/external reference.
- Added indexes for workspace/status/update and workspace/creation sorting.
- Enabled RLS; no client policy was added, so client access remains default-deny.

### Repository
- Added `app/repositories/postgres_projects.py`.
- Supports create, list by workspace, get by ID, update, and workspace role checks.
- Create/update validate inputs before database writes and enforce membership roles.
- Repository is deliberately not runtime-selected yet.

## 2. TEST Supabase evidence

Target: `AI-CREATOR-STUDIO-TEST` (`niktytizbtvxypwswbcc`). Production Supabase was not modified.

- Migration `add_projects_aggregate_0006` applied successfully.
- Migration history includes `20261107062600 add_projects_aggregate_0006`.
- Catalog check: `projects.relrowsecurity = true`; 3 indexes reported.
- Grants query returned privileges only for `postgres` and `service_role`; no `anon` or `authenticated` grants.

## 3. Verification

| Check | Result |
|---|---:|
| PostgreSQL project/migration/readiness focused tests | 31 passed |
| Python compileall | PASS |
| Full backend pytest | Attempted twice; timed out at ~63% and ~80%; not a pass |
| Live schema migration | PASS on TEST Supabase |
| Live table/RLS/index catalog check | PASS |
| Client-role grants check | PASS: no anon/authenticated grants |
| FastAPI Project CRUD against PostgreSQL | NOT RUN |

## 4. Important boundary

The FastAPI Workspace and Project endpoints still use the SQLite implementation. The new PostgreSQL repository is not connected to the running API. Do not describe Project persistence as end-to-end complete. `DATABASE_BACKEND=postgresql` remains fail-closed because other application aggregates still use SQLite/local files.

## 5. Next implementation gates

1. Implement and test PostgreSQL repository adapters for Product/Variant, Character, Photo, Lookbook and Project-product relationships.
2. Migrate Workspace and Asset API paths to PostgreSQL + private Supabase Storage with lifecycle parity.
3. Migrate Job/Worker/Output repository selection and transactions; validate lease concurrency on PostgreSQL.
4. Add a single runtime dependency-injection layer only after all routes and workers support the selected backend.
5. Run API integration tests against TEST Supabase using two real test users and cross-workspace denial cases.
6. Resolve frontend npm dependency installation, run Vite build, browser E2E, and Android layout checks.
7. Deploy a non-production Vercel Preview from a reviewed branch and execute the full user journey.

## 6. Production protection

No Production Supabase migration or Production Vercel deployment was performed. Keep Production untouched until the above gates pass.
