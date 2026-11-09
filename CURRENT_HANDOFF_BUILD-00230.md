# AI CREATOR STUDIO — Current Handoff BUILD-00230

- Date: 2026-11-07
- Engineering build: BUILD-00230
- Base: BUILD-00229
- Scope: PostgreSQL Project, Product Catalog and Project↔Product assignment persistence foundations; TEST Supabase migrations 0006–0008.

## 1. Implemented

### Project (0006)
- Durable Workspace-scoped Project table, constraints, indexes and RLS.
- `PostgreSQLProjectRepository`: create/list/get/update with workspace membership and role checks.

### Product Catalog (0007)
- `products`, `product_assets`, `product_variants`, `product_variant_assets`, `product_events`.
- Workspace-safe foreign keys, case-insensitive SKU indexes, active-image/same-workspace trigger, append-only events, RLS.
- `PostgreSQLProductRepository`: Product create/list/get with input validation, role checks, image asset validation and immutable creation event.
- Variant tables exist; PostgreSQL Variant CRUD adapter is still pending.

### Project ↔ Product (0008)
- `project_product_assignments` and `project_product_events`.
- Composite foreign keys ensure both Project and Product belong to the same Workspace.
- Active assignment uniqueness, assignment removal history, ordering and append-only events.
- `PostgreSQLProjectProductRepository`: list and replace assignment sets, enforce member role and active Project/Product state, record changes.

## 2. TEST Supabase evidence

Target: `AI-CREATOR-STUDIO-TEST` (`niktytizbtvxypwswbcc`). Production Supabase was not modified.

- `20261107062600 add_projects_aggregate_0006` applied.
- `20261107062809 add_product_catalog_aggregate_0007` applied.
- `20261107062943 add_project_product_assignments_0008` applied.
- Catalog checks: Project, Product and assignment tables present; RLS enabled; supporting indexes/triggers present.
- Grants checks: new tables return only `postgres` and `service_role`; no `anon` or `authenticated` grants.

## 3. Verification

| Check | Result |
|---|---:|
| Focused Project/Product/assignment/migration/readiness tests | 49 passed |
| Python compileall | PASS |
| TEST Supabase migrations 0006–0008 | PASS |
| RLS/index/trigger/grant catalog checks | PASS |
| Full backend pytest | Not completed; previous attempts timed out at ~63% and ~80% |
| FastAPI CRUD against PostgreSQL | NOT RUN |
| Two-user tenant isolation | NOT RUN |
| Production resources | NOT modified |

## 4. Runtime boundary

FastAPI Workspace, Project, Product and Project-Product endpoints still use SQLite. New PostgreSQL repositories are not runtime-selected. Product Variant CRUD is schema-only. `DATABASE_BACKEND=postgresql` must remain disabled because other aggregates and file lifecycle are not fully migrated.

## 5. Next gates

1. Complete Product Variant PostgreSQL CRUD and Project/Product assignment API wiring.
2. Migrate Workspace and Asset APIs and connect private Supabase Storage for upload/version/restore/preview/integrity/delete.
3. Implement PostgreSQL Character, Photo and Lookbook aggregates.
4. Complete Job/Worker/Output repository selection and PostgreSQL lease/concurrency validation.
5. Introduce central dependency injection only after all route and worker modules support the same backend.
6. Run authenticated FastAPI integration tests against TEST Supabase with two real test users and cross-Workspace denial cases.
7. Run Vite production build, browser/mobile E2E and non-production Vercel Preview.

## 6. Production protection

No Production Supabase schema/data and no Production Vercel deployment were changed.
