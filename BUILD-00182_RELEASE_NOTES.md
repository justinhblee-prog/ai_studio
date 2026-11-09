# BUILD-00182 Release Notes

## Changes
- Improved `ai_creator_studio_backend_starter/scripts/run_backend_test_shards.py` so pytest output streams directly to each shard log instead of being buffered in memory. Partial progress is preserved when a shard times out.
- No application runtime source, API behavior, dependency versions, or lockfiles were changed.

## Verification
- BUILD-00181 input archive SHA-256 and ZIP CRC verified before extraction.
- Backend: all 52 `test_*.py` files executed in 13 fresh pytest processes, four files per invocation. **367 passed, 0 failed, 0 skipped; 13/13 groups passed.** See `build182_logs/backend_grouped_test_results.log`.
- An all-in-one pytest run and the generic subprocess batch orchestrator intermittently stalled in this constrained runtime; neither is claimed as passing. Grouped invocations completed successfully.
- Viewer dependency-free JavaScript scripts: 17 passed; actual Three.js integration script blocked because `three` is not installed.
- Viewer Python test scripts: 7 passed.
- TypeScript syntax/transpile: 10 source files + 14 declaration parses, 0 syntax errors (not semantic typecheck).
- API contract: 63/63; request contract: 15 JSON calls, 0 findings; response contract: 50 JSON endpoints across 52 routes, 0 missing routes/schemas; package integrity: 0 findings.
- Viewer and backend Python compileall passed.
- Chromium capability probe: WebGL2 context unavailable. Probe scope is capability smoke only, not Viewer E2E.
- npm registry lookup for exact `three@0.180.0` failed with DNS `EAI_AGAIN`; dependencies could not be obtained. No versions or lockfiles were changed.

## Remaining blockers
- Obtain declared React/Three.js/type dependencies through an approved network-enabled or cached environment.
- Run semantic TypeScript checking and actual Three.js resource integration.
- Run browser React E2E, actual WebGL2 context-loss/restoration, GPU stress, and target-device performance acceptance.
