# AI CREATOR STUDIO — Current Handoff BUILD-00231

- Date: 2026-11-07
- Engineering build: BUILD-00231
- Base: BUILD-00230
- Scope: PostgreSQL Project, Product, Product Variant and Project↔Product persistence foundations; TEST Supabase migrations 0006–0010.

## 1. Implemented

### Project (0006)
- Workspace-scoped Project table, constraints, indexes and RLS.
- `PostgreSQLProjectRepository`: create/list/get/update with membership and role checks.

### Product Catalog (0007, 0009, 0010)
- Products, product image associations, variants, variant image associations and append-only product events.
- `PostgreSQLProductRepository`: Product create/list/get and Variant create/list/update/archive.
- Workspace membership/role checks, image Asset validation, ordered image associations and immutable event records.
- Variant image trigger requires active image Assets in the same Workspace.
- Cross-table SKU guard uses a transaction advisory lock and prevents case-insensitive duplicate SKUs between Products and Variants.
- All Product/Variant tables have RLS enabled and no client policies/grants.

### Project ↔ Product (0008)
- Assignment table retains removal history and ordering.
- Composite FKs enforce Project and Product belong to the same Workspace.
- Append-only assignment events.
- `PostgreSQLProjectProductRepository`: list and replace assignment sets with member role and active state checks.

## 2. TEST Supabase evidence

Target: `AI-CREATOR-STUDIO-TEST` (`niktytizbtvxypwswbcc`). Production Supabase was not modified.

- `20261107062600 add_projects_aggregate_0006` applied.
- `20261107062809 add_product_catalog_aggregate_0007` applied.
- `20261107062943 add_project_product_assignments_0008` applied.
- `20261107063118 harden_product_variant_asset_guard_0009` applied.
- `20261107063139 cross_catalog_sku_guard_0010` applied.
- Catalog checks confirmed RLS, indexes and expected Product/Variant/assignment triggers.
- Grants checks for the new tables returned only `postgres` and `service_role`; no `anon` or `authenticated` grants.

## 3. Verification

| Check | Result |
|---|---:|
| Focused Project/Product/assignment/migration/readiness tests | 59 passed |
| Python compileall | PASS |
| TEST Supabase migrations 0006–0010 | PASS |
| Catalog trigger verification | PASS |
| Full backend pytest | Not completed; previous attempts timed out at ~63% and ~80% |
| FastAPI PostgreSQL CRUD/assignment integration | NOT RUN |
| Two-user tenant isolation | NOT RUN |
| Production resources | NOT modified |

## 4. Runtime boundary

FastAPI Workspace, Project, Product, Variant and Project-Product endpoints still use SQLite. PostgreSQL repositories are not runtime-selected. `DATABASE_BACKEND=postgresql` must remain disabled because other aggregates, workers and file lifecycle paths are not fully migrated.

## 5. Next gates

1. Implement and test PostgreSQL Character, Photo and Lookbook aggregates.
2. Migrate Workspace and Asset APIs and connect private Supabase Storage for upload/version/restore/preview/integrity/delete.
3. Complete PostgreSQL Job/Worker/Output runtime selection and lease/concurrency validation.
4. Introduce central dependency injection only after every API route and worker supports the same backend.
5. Run authenticated FastAPI integration tests against TEST Supabase with two real users and cross-Workspace denial cases.
6. Run Vite production build, browser/mobile E2E and non-production Vercel Preview.

## 6. Production protection

No Production Supabase schema/data and no Production Vercel deployment were changed.
