# BUILD-00226 Verification Report

## Fresh results

| Validation | Result |
|---|---:|
| Backend pytest | 555 passed / 0 failed |
| Supabase Auth backend tests | 7 passed / 0 failed |
| Frontend Auth/API tests | 8 passed / 0 failed |
| Frontend structural checks | 143 passed |
| TypeScript syntax/transpile | 11 source + 16 declaration parses, 0 errors |
| Package integrity | 0 findings |
| Viewer Node scripts | 17 passed; one Three.js integration script blocked because `three` is unavailable |
| Viewer Python test scripts | 7 passed |
| API contract | 63/63, 0 findings |
| Request contract | 15 checked, 0 findings |
| Response contract | 50 JSON endpoints / 52 routes / 28 models / 0 missing |
| Python compileall | PASS |
| Runtime OpenAPI snapshot | PASS, 83 paths |

## Environment failures / unverified

- npm install: blocked by DNS `EAI_AGAIN` resolving `registry.npmjs.org`.
- Vite build: not run.
- Semantic TypeScript typecheck: blocked by absent React/ReactDOM and typings.
- React browser E2E / actual Supabase sign-in / Android: not run.
- Supabase live PostgreSQL application data path: not implemented/verified; runtime remains SQLite-first and PostgreSQL fails closed.
- Supabase Storage live transfer: not run; full Asset lifecycle is not wired.
- Vercel Preview: no source-backed Preview deployment exists for BUILD-00226.

## Interpretation

All passing results are scoped to the named source checks and test environment. They do not establish a production-ready website or end-to-end product workflow.
