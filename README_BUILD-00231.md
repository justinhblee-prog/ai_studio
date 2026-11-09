# AI CREATOR STUDIO — BUILD-00231

This build extends PostgreSQL persistence foundations to Projects, Products, Product Variants and Project↔Product assignments.

- Current handoff: `CURRENT_HANDOFF_BUILD-00231.md`
- Verification: `BUILD-00231_VERIFICATION.md`
- Release notes: `BUILD-00231_RELEASE_NOTES.md`
- Migrations: `ai_creator_studio_backend_starter/app/sql/postgres/migrations/0006_projects.sql` through `0010_cross_catalog_sku_guard.sql`
- Repositories: `app/repositories/postgres_projects.py`, `postgres_products.py`, `postgres_project_products.py`

**Not a public-service release.** FastAPI routes remain SQLite-backed; PostgreSQL repositories are not runtime-selected. Full backend suite, live API CRUD, Storage lifecycle, Vite build, browser E2E, AI Provider execution and Vercel Preview remain unverified. Do not deploy this build to Production.
