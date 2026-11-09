# AI CREATOR STUDIO — Handoff BUILD-00166

## Continuation point
The active build is **BUILD-00166**. Continue from this complete source package; do not restart earlier work.

## BUILD-00166 implementation
- Added `ai_creator_studio_3d_viewer/src/notifyViewerError.mjs` and `.d.mts`.
- Updated `Studio3DViewer.tsx` so all five optional `onErrorRef` callback invocations use the safe notification helper. A consumer callback throwing cannot interrupt the viewer's own fallback/error handling.
- Added `scripts/test_notify_viewer_error.mjs` (7 assertions) and updated `scripts/test_viewer_cleanup_lifecycle.py` (20 structural assertions + 4 disposal diagnostic assertions).

## Verification
- 13 dependency-free Viewer JavaScript test scripts passed (the Three.js integration script is intentionally excluded because `three` is unavailable).
- 7 Viewer Python test scripts passed.
- Backend pytest: 367 passed in 18.77s.
- API 63/63; response contract 50 JSON endpoints across 52 endpoints, no missing routes/schemas; request contract 8 files / 15 calls / 0 findings; package integrity 0 findings.
- TypeScript syntax/transpile: 10 TS/TSX source files + 13 declaration files, 0 syntax errors.

## Known blockers / unverified gates
- Semantic TypeScript typecheck and real Three.js resource integration require the declared React/Three.js packages, absent from this environment. See blocker logs.
- Browser E2E, authenticated GLTF browser loading, actual WebGLRenderer context loss/restoration, GPU stress/telemetry, and target-device performance are not verified.
- Do not claim those gates passed. Do not alter dependency versions or lockfiles merely to force a green result.

## Next work
1. In an approved network-enabled or cached environment, obtain the exact already-declared dependency versions and run semantic typecheck and Three.js integration.
2. Add/run Chromium React Viewer E2E with authenticated GLTF fixtures.
3. Exercise real renderer context loss/restoration and repeated model replacement/unmount under resource telemetry.
4. Reassess initialization setup rollback after these real-runtime checks; current change specifically hardens error-callback isolation and does not claim complete transactional rollback for every possible exception during renderer setup.

## Package
`AI_CREATOR_STUDIO_FULL_HANDOFF_BUILD-00166.zip` contains the full project source, documents, logs, and this handoff. SHA-256 is supplied in the paired `.sha256` file.
