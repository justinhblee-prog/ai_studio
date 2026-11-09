# BUILD-00226 Release Notes

## Scope
Supabase Auth browser entry, API token validation, and Workspace bootstrap/selection.

## Added
- Supabase email/password sign-in and sign-up UI.
- Auth session storage, refresh, email-link hash handling, and logout.
- HTTPS-only non-local API URL validation.
- Authenticated identity endpoint `GET /v1/auth/me`.
- Backend Supabase Auth token validation using `/auth/v1/user`.
- Automatic Workspace discovery/creation and Workspace switching.
- Auth/API client unit tests and declaration files.

## Changed
- Removed the manual bearer-token and Workspace-ID entry as the normal app entry flow.
- Updated runtime OpenAPI snapshot to 83 paths.
- Extended TypeScript syntax validation to include nested `.d.mts` declarations.

## Verification
- Backend: 555 passed.
- New backend auth tests: 7 passed.
- Frontend Auth/API tests: 8 passed.
- Structural checks: 143 passed.
- TypeScript syntax: 11 source + 16 declaration files, 0 syntax errors.
- Package integrity: 0 findings.
- API/request/response contract validators: 63/63, 15 checked, 50 JSON endpoints / 52 routes / 28 models.

## Not included / not claimed
- No successful npm install, Vite build, semantic typecheck, React browser E2E, or real Supabase login.
- No complete PostgreSQL runtime adapter or live database integration.
- No full Supabase Storage Asset lifecycle integration or live byte transfer.
- No source-backed Vercel Preview deployment.
- No live AI generation, virtual try-on, 3D garment generation, or paid provider call.
- No Production deployment, alias change, production Supabase mutation, or paid resource creation.
