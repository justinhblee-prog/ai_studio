# BUILD-00214 — Supabase / Vercel Live Smoke Test

Date: 2026-11-06 (KST)
Scope: read-only Supabase project metadata, migration/table/bucket/policy inspection, advisors, and Vercel deployment GET checks. No schema or deployment mutations.

## Supabase test project

- Project: `AI-CREATOR-STUDIO-TEST` (`niktytizbtvxypwswbcc`)
- State: `ACTIVE_HEALTHY`; PostgreSQL 17.11; Seoul `ap-northeast-2`.
- Migration ledger: one migration, `acs_private_storage_buckets`.
- Private buckets: `acs-assets` (100 MiB), `acs-gallery` (20 MiB), `acs-outputs` (25 MiB).
- No application tables in `public`; no app Storage object policies; no objects.
- Security Advisor: 0 lints. Health Advisor: 0 lints.

Interpretation: Supabase infrastructure and private bucket configuration are healthy. Application schema, tenant-aware RLS policies, Storage object policies, test users and test objects are absent. Application upload/download authorization and DB integration are not ready.

## Vercel project

- Project: `ai-creator-studio` (`prj_YLMaRJ9qTE1ZJh4FNr7pgj6mZAfW`).
- Existing deployment: `dpl_FJHKKrgj3WG69sEhLyiyYrqWNF8X`, target `production`, state `READY`.
- `https://ai-creator-studio-topaz.vercel.app/` → HTTP 200.
- `/health` → HTTP 200.
- Both responses identify `bootstrap-preview`; the body explicitly states full application modules are not deployed.
- Preview deployment history: 0 deployments.

Interpretation: infrastructure/bootstrap endpoints respond. No source-backed Preview deployment or full application deployment exists.

## Change impact

Supabase: read-only checks only. No DDL, data writes, policies, users or objects created.
Vercel: metadata and GET checks only. No deployment, alias or environment changes.
Real AI generation: not tested. No paid AI call made.

## Next integration gate

1. Finish and review PostgreSQL schema foundation and repository adapters locally.
2. Apply schema only to this dedicated test project.
3. Add and test tenant-safe RLS and Storage object policies.
4. Deploy actual source to Vercel Preview only.
5. Verify API → PostgreSQL → Storage → Worker and collect evidence.
