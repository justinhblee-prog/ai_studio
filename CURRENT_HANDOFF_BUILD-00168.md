# AI CREATOR STUDIO — Current Handoff BUILD-00168

## Baseline
BUILD-00167 full handoff archive was present in the active runtime, its SHA-256 matched the recorded digest, and `unzip -t` passed before extraction.

## Build result
BUILD-00168 implements transactional rollback for synchronous partial initialization failures in the 3D Viewer setup effect.

### Implementation
- New `ai_creator_studio_3d_viewer/src/resourceRollback.mjs` provides a reverse-order, failure-isolated rollback stack with commit semantics.
- `Studio3DViewer.tsx` registers cleanup for scene resources, renderer, canvas, key-light shadow, controls, resize observer, WebGL context lifecycle, animation loop, and viewer refs.
- On successful setup, the rollback stack is committed and the existing normal unmount cleanup path remains active.
- On setup failure, rollback is attempted, diagnostics are best-effort, and the Viewer enters its actionable error state.
- New dependency-free tests cover ordering, isolation, idempotency, commit, ownership-transfer release, and seven injected setup failure points (17 assertions).

## Fresh verification
- 14 dependency-free Viewer JavaScript test scripts passed.
- 7 Viewer Python test scripts passed.
- Backend: 367 passed.
- TypeScript syntax/transpile: 10 source files + 13 declarations, 0 errors.
- API contract: 63/63 matched; request contract: 0 findings; response contract: 0 missing routes/schemas; package integrity: 0 findings.

## Blockers / remaining acceptance work
- Three.js resource integration is blocked by missing declared `three` package (`ERR_MODULE_NOT_FOUND`). The test was attempted and not counted as passing.
- React/Three semantic typecheck, browser E2E, real WebGLRenderer context-loss/recovery, GPU stress, and target-device performance remain unverified.
- The dependency-free failure-injection suite does not replace actual browser/Three.js integration testing.

## Next work
1. Obtain the exact declared React/Three.js dependencies in an approved network-enabled or cached environment without changing versions or lockfiles.
2. Run semantic TypeScript and actual Three.js resource integration tests.
3. Mount the React Viewer in Chromium and test authenticated GLTF load, replacement, unmount, and injected setup failures.
4. Exercise real WebGL context loss/restoration and GPU resource stress.
5. Measure target-device performance and update acceptance evidence.

## Safety boundaries
No API, DB, provider, credits, publication, rights, deployment, dependency version, or lockfile changes.
