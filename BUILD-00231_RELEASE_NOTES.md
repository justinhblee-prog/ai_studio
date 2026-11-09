# BUILD-00231 — PostgreSQL Product Variant and SKU integrity

Date: 2026-11-07
Base: BUILD-00230

## Implemented
- Extended `PostgreSQLProductRepository` with Product Variant create/list/update/archive operations.
- Added Variant option/image validation, Workspace role checks, active parent Product checks, asset membership/image checks, ordered image links and immutable Product events.
- Hardened the Variant asset trigger in migration `0009_harden_product_variant_asset_guard.sql` to require active image assets in the same Workspace.
- Added migration `0010_cross_catalog_sku_guard.sql` with transaction advisory locks and triggers preventing case-insensitive SKU collisions between Products and Variants under concurrent writes.
- Applied migrations 0009 and 0010 to TEST Supabase (`AI-CREATOR-STUDIO-TEST`, `niktytizbtvxypwswbcc`).
- Verified migration history and catalog presence of Product/Variant asset guard and cross-catalog SKU triggers.

## Verification
- Focused PostgreSQL Project/Product/assignment/migration/readiness tests: 59 passed.
- Python compileall: passed.
- TEST Supabase migrations 0009–0010: applied successfully.
- Catalog trigger verification: passed.
- Full backend suite remains unverified; previous attempts timed out around 63% and 80%.

## Not implemented / not verified
- PostgreSQL repositories are not selected by FastAPI runtime; API routes remain SQLite-backed.
- No live FastAPI Product/Variant CRUD or Project assignment request was run.
- No two-user tenant isolation test was run.
- No Supabase Storage byte lifecycle, Vite build, browser E2E, AI Provider execution or Vercel Preview was completed.

## Release decision
Not production-ready. Do not switch `DATABASE_BACKEND=postgresql` or deploy to Production until all aggregates, API routes, workers and storage operations are migrated and live-tested.
