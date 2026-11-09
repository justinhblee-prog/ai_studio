# AI CREATOR STUDIO — BUILD-00181 Release Notes

## Release type
Backend test-runner reliability improvement and verification refresh. No application runtime behavior was changed.

## Baseline integrity
- Started from `AI_CREATOR_STUDIO_FULL_HANDOFF_BUILD-00180.zip`.
- SHA-256 sidecar verification passed.
- ZIP CRC/integrity test passed before extraction.

## Changes
- Added `ai_creator_studio_backend_starter/scripts/run_backend_test_shards.py`.
- The runner discovers backend `tests/test_*.py` files and runs each file in a fresh pytest subprocess, retaining one log per file and an aggregate summary.
- Supports selecting individual test files, per-file timeouts, and fail-fast behavior.
- This avoids relying on one long-running pytest process in constrained execution environments and makes any slow or failing test file independently identifiable. It does not change test semantics or application code.

## Fresh verification
- Backend tests: 367/367 passed across three fresh invocations: `test_api.py` 70, `test_assets_api.py` 69, and all remaining test files 228.
- New shard-runner smoke test: 3 selected test files, 17 tests passed, 0 failures/timeouts.
- Backend test collection: 367 tests collected successfully.
- Viewer dependency-free JavaScript: 17 scripts passed; 295 emitted assertion-summary counts.
- Viewer Python: 7 scripts passed.
- TypeScript syntax/transpile: 10 source files and 14 declaration files parsed; 0 syntax errors. This is not semantic typechecking.
- Viewer API contract: 63/63 calls matched; 0 findings.
- Request contract: 15 JSON body calls checked; 0 findings.
- Response contract: 50 JSON endpoints documented across 52 routes; 0 missing routes/schemas.
- Package integrity: 0 findings.
- Viewer and backend Python compileall passed.
- Final ZIP CRC and SHA-256 verification passed.

## Execution note
A monolithic backend pytest invocation exceeded the execution window despite progressing through the suite. The complete set was therefore rerun in independent test-file groups; all 367 collected tests passed. The new runner smoke test confirms the isolation/logging behavior, but a full 52-file run of the new runner was not performed as a single command in this session.

## Blocked or incomplete validation
- `three`, `react`, `typescript`, `@types/react`, and `@types/three` are absent from the local Viewer `node_modules`; npm cache has no usable package set. Semantic TypeScript checking and the actual Three.js resource integration test remain blocked.
- Browser React E2E, real WebGLRenderer context restoration, WebGL2/GPU stress, and target-device performance acceptance remain unverified.
- No package versions or lockfiles were changed.

## Next acceptance priorities
1. Obtain exact declared React/Three.js dependencies in an approved network-enabled or cached environment.
2. Run semantic typecheck and actual Three.js resource integration.
3. Run authenticated React Viewer E2E in a WebGL2-capable browser.
4. Validate real renderer context loss/restoration, repeated model replacement/unmount, GPU stress, and target-device performance.
