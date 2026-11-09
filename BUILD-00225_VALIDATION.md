# BUILD-00225 Validation Report

| Validation | Result | Evidence / boundary |
|---|---|---|
| Backend pytest | PASS | 548 passed, 0 failed |
| Backend compileall | PASS | `python -m compileall -q app scripts tests` |
| Runtime OpenAPI snapshot | PASS | `python scripts/export_runtime_openapi.py --check` |
| Frontend package integrity | PASS | 0 findings |
| Frontend TypeScript syntax/transpile | PASS | 11 source files + 14 declaration parses, 0 errors; not a full typecheck |
| Frontend structural checks | PASS | 143 checks |
| Frontend Node unit scripts | PASS | 17 scripts; Three.js integration script excluded because package unavailable |
| Frontend Python validation scripts | PASS | 12 scripts |
| npm dependency installation | BLOCKED | `EAI_AGAIN` resolving registry.npmjs.org |
| Vite production build | NOT RUN | Dependencies unavailable |
| Browser E2E / real WebGL rendering | NOT RUN | No built app/dependency runtime |
| Supabase test schema migration 0005 | PASS | Applied and read back; validated constraints |
| Supabase RLS/grant check | PASS | RLS enabled; anon/authenticated SELECT denied; service_role SELECT allowed |
| Live Supabase Storage transfer | NOT RUN | Service-role runtime credential not configured in Vercel; BlobStore only mock-tested |
| Vercel source-backed Preview | BLOCKED | Linked Git repo could not resolve default ref; no Preview URL |
| Production deployment | UNCHANGED | Existing deployment is bootstrap-only; not represented as full app |

## Important distinction

This report records actual local tests and the live test-database migration. It does **not** claim a completed Vite build, a browser-tested website, live Storage transfer, PostgreSQL runtime parity, or a Vercel Preview deployment.
