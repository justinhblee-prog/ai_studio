# BUILD-00186 Release Notes

## Scope
Fresh integrity, backend, viewer-contract, syntax, and browser-capability verification. No application runtime source, API behavior, dependency manifest, dependency versions, or lockfiles were changed.

## Verification results
- Input BUILD-00185 archive: SHA-256 sidecar verified; `unzip -t` passed before extraction.
- Backend: all 52 test files verified, **367 passed / 0 failed / 0 skipped**. The first eight files passed in isolated shards (204 tests); the next five groups passed together (78 tests); the four BUILD-00185 group-8 files passed individually (8 tests); the final five groups passed together (77 tests). A full sequential shard-runner invocation exceeded the outer command execution window after its first eight files; this is an orchestration limit, not a test failure. The interrupted shard was independently rerun and passed 4/4.
- Viewer JavaScript: 17 dependency-free scripts passed; one Three.js integration script was not run because the declared `three` package is unavailable. 0 JS failures.
- Viewer Python: 7 scripts passed; 0 failures.
- TypeScript syntax/transpile: 10 source files + 14 declaration parses, 0 syntax errors. Global TypeScript CLI is 5.8.3. Semantic typecheck was not run because React/Three.js type packages are absent.
- API contract: 63/63 matched.
- Request contract: 15 JSON-body calls checked, 0 findings.
- Response contract: 50 JSON endpoints documented across 52 routes, 28 models, 0 missing routes/schemas.
- Package integrity: 0 findings.
- Viewer and backend Python `compileall`: passed.

## Runtime/dependency gate
- npm cache listing is empty; `three`, React/ReactDOM and corresponding type packages were not found in searched local/global package paths.
- Chromium capability probe: WebGL2 context unavailable; no renderer, context-loss/restoration, or triangle-pixel acceptance was demonstrated. The probe is capability-only and does not load the React/Three.js viewer.
- Prior exact npm registry probe failed with DNS `EAI_AGAIN`; this build did not repeat network retries or change dependency declarations.

## Remaining acceptance work
1. Obtain the exact declared dependencies from a network-enabled or pre-populated approved environment.
2. Run semantic `tsc --noEmit` and actual Three.js resource integration tests.
3. Run authenticated React Viewer browser E2E in a WebGL2-capable browser.
4. Verify real renderer context-loss/restoration, repeated model replacement/unmount, GPU stress, and target-device performance.

## Artifacts
See `BUILD-00186_VERIFICATION.md`, `CURRENT_HANDOFF_BUILD-00186.md`, and `build186_logs/`.
