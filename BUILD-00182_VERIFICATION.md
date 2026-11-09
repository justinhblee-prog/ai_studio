# BUILD-00182 Verification Report

## Provenance and package input
- Input: `AI_CREATOR_STUDIO_FULL_HANDOFF_BUILD-00181.zip`.
- SHA-256 sidecar validation: PASS.
- ZIP CRC validation: PASS.

## Fresh test evidence

### Backend
- All 52 backend `test_*.py` files were executed in 13 fresh pytest processes, four files per invocation.
- **367 passed, 0 failed, 0 skipped; 13/13 groups passed.**
- Per-group counts: 150, 54, 14, 21, 15, 10, 18, 8, 16, 14, 16, 17, 14.
- See `build182_logs/backend_grouped_test_results.log` for the exact test-file grouping.
- An all-in-one pytest run and the generic subprocess batch orchestrator intermittently stalled in this runtime; these are not counted as passing evidence. Direct grouped invocations completed.

### Viewer
- Dependency-free JS test scripts: 17 passed; actual Three.js integration script blocked by missing `three` dependency.
- Viewer Python test scripts: 7 passed.
- TypeScript syntax/transpile: 10 source + 14 declarations, 0 syntax errors. This is not a semantic typecheck.
- API contract: 63/63.
- Request contract: 15 JSON body calls checked, 0 findings.
- Response contract: 50 JSON endpoints documented across 52 routes, 0 missing routes/schemas.
- Package integrity: 0 findings.
- Viewer and backend `compileall`: PASS.

### Runtime/dependencies
- Chromium capability probe: WebGL2 context unavailable. The probe does not load the React/Three.js Viewer and is not an E2E test.
- npm registry lookup for exact `three@0.180.0`: blocked by DNS `EAI_AGAIN`; no package installation or lockfile change.

## Verdict
Backend automated tests passed in 13 isolated groups (367/367). Dependency-free Viewer and contract checks passed. Actual Three.js integration, semantic TypeScript checking, React browser E2E, WebGL2/GPU and target-device acceptance remain unverified in this build.
