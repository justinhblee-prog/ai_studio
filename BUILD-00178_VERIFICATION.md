# BUILD-00178 Verification

## Fresh verification

- Viewer JavaScript: 17 dependency-free test scripts passed. `test_three_resource_integration.mjs` remains blocked because the declared `three` package is not installed in this environment.
- WebGL context lifecycle suite: existing cases plus 8 new reentrancy assertions passed.
- Animation frame controller: 46 assertions passed.
- Viewer Python: 7 test scripts passed.
- Backend: `PYTHONPATH=. pytest -q` — 367 passed in 20.48s.
- Backend Python compileall: passed.
- TypeScript syntax/transpile: 10 source files + 14 declaration parses, 0 errors. This is not a semantic React/Three.js typecheck.
- API contract: 63/63 calls matched; 0 missing, 0 query mismatches, 0 unresolved dynamic segments.
- Request contract: 15 JSON-body calls checked; 0 findings.
- Response contract: 50 JSON endpoints documented across 52 routes; 0 missing routes/schemas.
- Package integrity: 0 findings.
- ZIP integrity and SHA-256: verified after packaging.

## Remaining unverified / blocked

- Actual Three.js integration test and semantic TypeScript typecheck: `three`, `react`, and corresponding type dependencies are not installed locally; npm cache contains no matching Three.js package. No dependency versions were changed and no network install was claimed.
- React browser E2E, real WebGLRenderer context loss/restoration, WebGL2/GPU stress, and target-device performance remain unverified.

Logs are in `build178_logs/`.
