# AI CREATOR STUDIO — Current Handoff BUILD-00220

## Latest verified state
- Local backend tests: 536 passed, 0 failed.
- Python compileall: passed.
- Dedicated Supabase test project now contains 20 application tables across migrations 0001/0002; all 20 have RLS enabled.
- Supabase anon/authenticated table and sequence grants have been revoked. Service-role DML remains available.
- Transactional Workspace/Asset relational probe rolled back cleanly; residual rows 0.
- Security Advisor: only 20 informational RLS-enabled-without-policy notices remain; no function search_path warning. Health Advisor: 0.
- Storage buckets are private. No Storage object policies, test objects, or app-level HTTP Storage integration verified.
- Vercel remains bootstrap-only; no source-backed Preview deployment. Project has no linked Git repo. No Production changes.

## Implemented source
- PostgreSQL Output adapter and transactional finalization.
- PostgreSQL Workspace/Asset metadata migration and adapter (version, provenance, relation, soft-delete support).
- Local/Supabase private BlobStore adapter; Supabase path is explicit opt-in and not yet wired into Asset API routes.
- Migration 0003 hardens append-only function search_path.
- Migration 0004 removes anon/authenticated table/sequence privileges and default grants.

## Important boundaries
- PostgreSQL adapters are not all wired into runtime. Poll/Outbox/Operations composition remains SQLite-only/fail-closed.
- No app service-role psycopg connection tested; only Supabase SQL execution path tested.
- No tenant RLS policies yet. Keep default-deny; do not add broad policies to silence Advisor.
- BlobStore's Supabase adapter has mocked HTTP contract tests only; no real upload/download has been performed.
- Real AI generation, React/Three browser E2E, and Vercel Preview remain unverified.

## Next autonomous work
1. Integrate BlobStore into Asset upload, preview, version, restore, and delete flows behind explicit backend selection, preserving local default.
2. Add tenant-aware RLS policies based on Supabase Auth identity mapping and verify with two users.
3. Add live psycopg adapter parity tests against the dedicated test project.
4. Complete PostgreSQL Poll/Outbox/Operations worker composition before runtime activation.
5. Establish source-backed Vercel Preview deployment; current Vercel project has no Git repository link, so use a supported source deployment path or record the external blocker.
