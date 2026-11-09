# BUILD-00227 Verification Report

| Validation | Result |
|---|---:|
| Backend pytest | 555 passed / 0 failed |
| Supabase Auth backend tests | 7 passed / 0 failed |
| Frontend Auth/API tests | 8 passed / 0 failed |
| Public landing contract | PASS |
| Frontend structural checks | 143 passed |
| TypeScript syntax/transpile | 12 source + 16 declaration parses, 0 errors |
| Package integrity | 0 findings |
| Viewer Node scripts | 17 passed; one Three.js integration script blocked because dependency unavailable |
| Viewer Python test scripts | 7 passed |
| API contract | 63/63 matched, 0 findings |
| Request contract | 15 checked, 0 findings |
| Response contract | 50 JSON endpoints / 52 routes / 28 models / 0 missing |
| Python compileall | PASS |
| Runtime OpenAPI snapshot | PASS, 83 paths |

## Blocked / not run

- npm install: DNS `EAI_AGAIN` for `registry.npmjs.org`.
- Vite build, semantic TypeScript typecheck, React browser E2E, and Android browser E2E: not verified.
- Live Supabase login/email confirmation: not run.
- Complete PostgreSQL repository/worker runtime and live Supabase Storage: not implemented/verified.
- Vercel Preview for BUILD-00227: not deployed because the modified source is not pushed to the linked GitHub repository.

Passing test counts are scoped to the code/tests executed and do not establish production readiness.
