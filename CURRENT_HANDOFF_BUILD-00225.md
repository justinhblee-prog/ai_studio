# AI CREATOR STUDIO — Current Handoff BUILD-00225

- Date: 2026-11-06
- Build: BUILD-00225
- Baseline: BUILD-00223 full source + BUILD-00224 React/Vite app shell
- Scope: repair frontend package regression, reconcile the test Supabase schema with the existing Asset storage locator contract, and re-run local verification.

## Completed in BUILD-00225

### Frontend package repair
- Moved the Vite entrypoint from `src/main.tsx` to `src/app/main.tsx` so the existing eight Viewer workspace components remain the audited module surface.
- Corrected relative imports after the move.
- Restored the package contract: React/ReactDOM peer dependencies, Three.js runtime dependency, TypeScript development dependency; React and ReactDOM also remain dev dependencies for the runnable application.
- Added `vite.config.ts`, explicit `dist` output, and Node >=20 engine requirement.
- Corrected invalid CSS font shorthand declarations.
- Package integrity audit: 0 findings.
- TypeScript transpile/syntax audit: 11 source files + 14 declaration files, 0 errors.
- Existing dependency-free frontend tests: 17 Node scripts passed; 12 Python validation/test scripts passed; 143 structural source checks passed.

### Backend regression repair
- The new app entrypoint initially increased the source-file count in the backend's Viewer/OpenAPI audit. Moving the app shell under `src/app/` restored the intended eight-module audit boundary without weakening the test.
- Backend test suite: **548 passed / 0 failed**.
- Python compileall: PASS.
- Runtime OpenAPI snapshot check: PASS.

### Supabase test project
- Project: `AI-CREATOR-STUDIO-TEST` (`niktytizbtvxypwswbcc`), PostgreSQL 17.11, Seoul, ACTIVE_HEALTHY.
- Applied migration `asset_storage_locators_0005` (Supabase migration version `20261106124229`) to add `storage_backend` and `storage_bucket` to `assets` and `asset_versions`, including validated allowlist constraints.
- Verified both tables contain the new non-null columns with backwards-compatible defaults (`local`, `private_assets`).
- Verified both check constraints are validated.
- Asset and AssetVersion rows remain 0; no user data was inserted.
- The three storage buckets remain private: `acs-assets`, `acs-gallery`, `acs-outputs`.
- RLS remains enabled and fail-closed. No tenant policies were added. `anon` and `authenticated` cannot SELECT `public.assets`; `service_role` can.
- Security Advisor reports 20 informational RLS-enabled-without-policy findings. This is intentional default-deny pending Auth identity mapping and two-user authorization tests; do not “fix” by opening broad access.

## Not verified / blocked

### Frontend build and browser
- `npm install` cannot complete in the current local runner: DNS requests to `registry.npmjs.org` return `EAI_AGAIN`.
- Therefore `npm run build`, full TypeScript typecheck, the Three.js dependency integration test, and browser E2E are **not verified**.
- The Three.js resource integration test is blocked specifically because the declared `three` package is not installed in this runner.

### Supabase live application integration
- The test database has the required storage locator schema, but the backend runtime is still SQLite-only. `DATABASE_BACKEND=postgresql` deliberately fails closed; there is no complete PostgreSQL repository/worker adapter.
- Vercel Preview environment variables are empty. No `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, API signing secret, or test bearer-token mapping is configured there.
- No live Supabase Storage upload/download/delete was performed. The Storage BlobStore adapter is present and mock-tested, but is not wired through the complete Asset lifecycle.

### Vercel Preview
- Project: `ai-creator-studio` (`prj_YLMaRJ9qTE1ZJh4FNr7pgj6mZAfW`), linked metadata points to `justinhblee-prog/A_CREATOR_STUDIO`.
- Project framework is currently `fastapi`; only one bootstrap Production deployment exists.
- Attempts to resolve `main`, `master`, and the repository's default branch failed with `incorrect_git_source_info`. The default branch and commit SHA remain unverified; do not guess.
- `create_git_project` reused the existing project but failed to create Preview for the same missing/unresolved default Git ref.
- No Preview URL exists. Existing Production URL/aliases remain untouched and are not the full application.

## Next work
1. Obtain a resolvable GitHub ref/commit for the linked repository, then build the React/Vite app from the correct root in a Preview-only deployment.
2. Complete PostgreSQL adapters and worker composition before setting `DATABASE_BACKEND=postgresql`.
3. Wire Supabase Storage into Asset upload/version/restore/preview/integrity/delete with compensation and orphan cleanup.
4. Configure Preview-only secrets through Vercel's environment-variable interface; never put service-role keys in client bundles or source files.
5. Run live DB, private Storage byte-transfer, API, worker, and browser E2E tests.
6. Keep Production deployments/aliases and the production Supabase project unchanged. No paid AI provider calls.
