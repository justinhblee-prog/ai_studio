# AI CREATOR STUDIO — BUILD-00230

This build extends PostgreSQL persistence foundations to Projects, Product Catalog and Project↔Product assignments.

- Current handoff: `CURRENT_HANDOFF_BUILD-00230.md`
- Verification: `BUILD-00230_VERIFICATION.md`
- Release notes: `BUILD-00230_RELEASE_NOTES.md`
- Migrations: `ai_creator_studio_backend_starter/app/sql/postgres/migrations/0006_projects.sql` through `0008_project_product_assignments.sql`
- Repositories: `app/repositories/postgres_projects.py`, `postgres_products.py`, `postgres_project_products.py`

**Not a public-service release.** FastAPI routes remain SQLite-backed; new PostgreSQL repositories are not runtime-selected. Full backend suite, live API CRUD, Product Variant CRUD, Storage lifecycle, Vite build, browser E2E, AI Provider execution and Vercel Preview remain unverified. Do not deploy this build to Production.
