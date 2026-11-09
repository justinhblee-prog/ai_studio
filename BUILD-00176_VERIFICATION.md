# BUILD-00176 Verification

## Fresh results

- Animation-frame controller: 34 assertions passed.
- Viewer JavaScript: 13 dependency-free scripts passed; `test_three_resource_integration.mjs` blocked because `three` is unavailable.
- Viewer Python: 7 test scripts passed.
- Backend: `PYTHONPATH=. pytest -q` — 367 passed.
- TypeScript syntax/transpile: 10 TS/TSX source files + 13 declaration files, 0 errors.
- API contract: 63/63 matched, 0 missing, 0 query mismatches, 0 unresolved dynamic segments.
- Request contract: 15 JSON body calls checked, 0 findings.
- Response contract: 50 JSON endpoints documented across 52 endpoints, 0 missing routes, 0 missing schemas, 0 unresolved dynamic segments.
- Package integrity: 0 findings.
- Python `compileall`: passed for backend app/tests/scripts.
- ZIP CRC and SHA-256 sidecar: verified after packaging.

## Environment blockers

- `three` is not installed, so the actual Three.js resource integration test was not run.
- React and its type declarations are not installed; semantic TypeScript validation and actual React browser E2E remain blocked.
- WebGL2 renderer recovery, GPU stress, and target-device performance were not exercised.
