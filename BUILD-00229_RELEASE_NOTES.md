# BUILD-00229 — PostgreSQL Project + Product Catalog foundations

Date: 2026-11-07
Base: BUILD-00228

## Implemented
- Retained migration 0006 and `PostgreSQLProjectRepository` from BUILD-00228.
- Added migration `0007_products.sql` for Products, Product Assets, Product Variants, Variant Assets and append-only Product Events.
- Added workspace-scoped composite foreign keys, case-insensitive SKU uniqueness within each aggregate, asset/workspace guards, active-image validation trigger for Product images, append-only event trigger, RLS on all five tables, and supporting indexes.
- Added `PostgreSQLProductRepository` for validated Product create/list/get, workspace membership/role checks, asset ownership checks, image associations and immutable create events.
- Applied migration `add_product_catalog_aggregate_0007` to TEST Supabase (`AI-CREATOR-STUDIO-TEST`, `niktytizbtvxypwswbcc`).
- Verified all five Product tables exist with RLS enabled; catalog returned expected indexes and asset/event triggers.
- Verified grants on all five tables: `postgres` and `service_role` only; no `anon` or `authenticated` grants.

## Verification
- Focused PostgreSQL project/product/migration/readiness tests: 41 passed.
- Python compileall: passed.
- TEST Supabase migrations 0006 and 0007: applied successfully.
- TEST catalog checks: passed for RLS, indexes, triggers and grants.
- Full backend pytest suite remains unverified: previous attempts timed out around 63% and 80%; it was not represented as a pass.

## Not implemented / not verified
- Neither PostgreSQL repository is selected by FastAPI runtime; existing Workspace, Project and Product API routes still use SQLite.
- Product Variant CRUD adapter is not implemented yet; schema only is present for variants.
- No live FastAPI CRUD transaction against PostgreSQL was run.
- No real user login/tenant negative-case integration test was run.
- No Storage byte lifecycle, Vite production build, browser E2E, or Vercel Preview was completed.

## Release decision
Not production-ready. Do not switch `DATABASE_BACKEND=postgresql` and do not deploy to Production until all aggregates, routes, workers and storage operations are migrated and live-tested.
