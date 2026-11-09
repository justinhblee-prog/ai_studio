# BUILD-00179 Release Notes

## Scope
WebGL context lifecycle reentrancy regression coverage and dependency/runtime verification.

## Changes
- Extended `ai_creator_studio_3d_viewer/scripts/test_webgl_context_lifecycle.mjs` with six assertions for two additional reentrant host-callback boundaries.
- Verified a fresh context-loss event dispatched from `onRestored` remains authoritative and stops the restarted render loop.
- Verified a context-loss event dispatched from `clock.start()` aborts stale restoration before resize or animation restart.
- No production source behavior needed changing; the existing generation ownership guards correctly handle both cases.
- Attempted dependency installation using the declared package manifest without changing versions or lockfiles. `npm install --ignore-scripts --no-audit --no-fund --package-lock=false` timed out in this environment; actual Three.js integration remains blocked.

## Test results
- All dependency-free Viewer JavaScript test scripts passed (295 assertions counted from emitted assertion summaries; includes the two new 3-assertion regression groups).
- All Viewer Python test scripts passed (7 scripts).
- TypeScript syntax/transpile check: 10 TS/TSX source files + 14 declaration files, 0 errors. This is not semantic typechecking.
- API contract: 63/63; request contract: 15 JSON-body calls, 0 findings; response contract: 50 JSON endpoints documented across 52 routes, 0 missing; package integrity: 0 findings.
- Viewer and backend Python compileall passed.
- Backend full-suite rerun did not complete within the available execution window. The previous packaged BUILD-00178 verification log records 367 passed in 20.48s against the unchanged backend source. Do not treat the current rerun as a fresh pass.
- Actual Three.js resource integration did not run because `three` is unavailable and dependency installation timed out.

## Remaining acceptance work
1. Install exact declared React/Three.js dependencies in an approved network-enabled or cached environment.
2. Run `npm run typecheck` and `npm run test:three-resource-integration`.
3. Run React Viewer E2E in a WebGL2-capable browser with authenticated GLTF fixtures.
4. Verify actual renderer context loss/restoration, repeated model replacement/unmount, GPU stress, and target-device performance.
