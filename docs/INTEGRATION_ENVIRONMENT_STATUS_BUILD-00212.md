# Supabase / Vercel Integration Environment Status — BUILD-00212

Date: 2026-11-06. This is an environment inventory, not a successful app integration test.

## Supabase test project

- Project: `AI-CREATOR-STUDIO-TEST`
- ID: `niktytizbtvxypwswbcc`
- Region: `ap-northeast-2`
- PostgreSQL: 17.11
- State: `ACTIVE_HEALTHY`
- Applied migration: `acs_private_storage_buckets`
- Private buckets: `acs-assets`, `acs-gallery`, `acs-outputs`
- Application schema/tables: not yet applied.
- Storage object policies: not yet applied.
- Test users and test objects: none.
- Runtime credentials connected to Vercel: no.
- Production project: untouched.

## Vercel project

- Project: `ai-creator-studio`
- Project ID: `prj_YLMaRJ9qTE1ZJh4FNr7pgj6mZAfW`
- Framework: FastAPI
- Current latest deployment: `dpl_FJHKKrgj3WG69sEhLyiyYrqWNF8X`
- Target: `production`, state: `READY`
- URL: `https://ai-creator-studio-edhu46qt9-justinhblee-9540.vercel.app`
- Alias: `https://ai-creator-studio-topaz.vercel.app`
- `/` and `/health` return HTTP 200, but the root body identifies itself as `bootstrap-preview` and states that full application modules are not deployed.
- Git source connection: not verified.
- Source-backed Preview deployment: not performed.

## Local application readiness endpoint

`GET /internal/ops/runtime-readiness` is now implemented. It is read-only and requires a platform operator identity configured through `OPS_ADMIN_USER_IDS`. It reports known integration gaps without attempting network access or modifying external resources. It does not reveal database URLs or API keys.

## Next safe live-test batch

1. Complete and test PostgreSQL repositories/migrations locally.
2. Apply reviewed migrations only to the dedicated test project.
3. Add private Storage object policies and run authenticated tenant-isolation tests.
4. Deploy source to Vercel Preview only; do not redeploy Production.
5. Configure test-only credentials through protected Vercel environment variables.
6. Run API → PostgreSQL → Storage → Worker end-to-end tests and capture logs.

No live application integration is claimed in this report.
