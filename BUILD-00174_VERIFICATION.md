# BUILD-00174 Verification Report

## Fresh test results
- Viewer dependency-free JavaScript: 17 passed, 1 blocked, 0 failed. The blocked test is `test_three_resource_integration.mjs`; the declared `three` package is not installed.
- Viewer Python tests: 7 passed, 0 failed.
- Backend: `PYTHONPATH=. pytest -q` — 367 passed.
- TypeScript syntax/transpile: 10 TS/TSX source files and 14 declaration files parsed; 0 errors.
- Viewer source structural validation: 143 checks passed.
- API contract: 63/63 matched; 0 missing, 0 query mismatches, 0 unresolved dynamic segments.
- Request contract: 15 checked, 0 findings.
- Response contract: 50 JSON endpoints documented across 52 endpoints; 0 missing routes, 0 missing schemas, 0 unresolved dynamic segments.
- Package integrity: 0 findings.
- Python compileall: Viewer and backend source/test/script trees passed.
- ZIP CRC and SHA-256 sidecar verification passed.

## Dependency/runtime blockers
- `three` is unavailable, so actual Three.js resource integration remains unexecuted.
- React and `@types/react` are unavailable, so semantic TypeScript typecheck and React browser E2E remain unverified.
- Actual WebGL2 context loss/restoration, GPU stress, and target-device performance remain unverified.

## Changed behavior
`Studio3DViewer` now assigns each model load a monotonic request identity through `KeyedRequestGate`. Every asynchronous completion path checks that identity. Cleanup invalidates the owner before aborting fetch, so stale parse callbacks cannot commit, report errors, or alter the current model's UI state.

## Scope boundaries
No external services were called. No dependencies or lockfiles were changed. No deployment, publication, commercial-rights grant, or external account action was performed.
