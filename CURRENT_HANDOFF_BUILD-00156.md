# AI CREATOR STUDIO — Current Handoff

## Baseline
- Build: BUILD-00157
- Base: BUILD-00156
- Focus: animation-frame lifecycle ownership and render-failure isolation.

## Completed
- Added `src/disposeViewerResources.mjs` and `.d.mts` as the lifecycle boundary around exhaustive GLTF resource disposal.
- Model replacement, loaded GLTF teardown and stage-resource teardown now report collected disposal errors through `runViewerCleanupSteps`; cleanup continues after the diagnostic is recorded.
- Added `scripts/test_viewer_lifecycle_integration.mjs`: nested scene graph, shared resource deduplication, stage resource release, model replacement, teardown order, injected GPU disposal failure and later cleanup assertions (32 total).
- Integrated the lifecycle harness into `npm run test:viewer-cleanup` and exposed a dedicated npm script.
- Registered the authenticated preview Object URL test as an npm script.
- Reconciled stale structural checks with the current authenticated byte-fetch + `GLTFLoader.parse` implementation and `/preview-content` endpoint.
- No backend/API/schema/DB/dependency-version/Provider/credit/publication/rights/production-data/deployment changes.

## Verification
- Backend full pytest: 367 passed in a completed run (30.57s). A later duplicate run timed out around 42% without a reported test failure; see verification report.
- Viewer lifecycle integration 32 assertions; cleanup helper 10 runtime; lifecycle structural 13/13; diagnostic integration 4/4.
- GLTF disposal 33 assertions; authenticated GLTF 15/15; bounded download 17 runtime/19 structural; model base path 10/10.
- Preview Object URL 5; RequestScopeGate 7; KeyedRequestGate 7; project lifecycle 4; Lookbook links 12; Lookbook recovery 19/19.
- Viewer API 63/63; request bodies 15 checked/0 findings; response contract 50 JSON/52 total/28 models/0 missing.
- Offline source structural validation 143; TypeScript syntax 10 source + 10 declarations/0 errors; package integrity 0 findings; Python compileall passed.
- Chromium WebGL2 capability smoke passed under Xvfb. This does not load React/Three Viewer or GLTF.
- Semantic `npm run typecheck` remains blocked by missing React/Three packages and typings; no dependencies were installed.

## Remaining blockers / limitations
- Actual React/Three browser component E2E and visible GLB/GLTF rendering remain unverified.
- Semantic TypeScript checking remains blocked until trusted pinned dependencies are provisioned.
- Production-size/target-device memory profiling unavailable.
- External glTF buffer/image URIs rejected; multi-file glTF import not implemented.
- PostgreSQL runtime/multi-host integration, Android, production object storage/secrets/RBAC, live Provider calls, credit charging, publication, rights grants and deployment remain unverified.

## Next autonomous priorities
1. Continue strengthening the Viewer lifecycle harness and introduce a real Three.js renderer/scene test when trusted pinned dependencies are available.
2. Provision pinned React/Three dependencies only in an approved network-enabled environment; then run semantic typecheck and browser E2E with minimal GLB/data-URI GLTF fixtures.
3. Profile target-device memory and representative large assets.
4. Continue readiness work without crossing approval boundaries.

## Approval boundaries
No live Provider calls, paid APIs, credit charges, publication, rights grants, production data changes, deployment, destructive migrations, or unresolved security/policy decisions without explicit approval.


## BUILD-00157 delta
- Added `src/animationFrameController.mjs` and `.d.mts`; integrated it into `Studio3DViewer` for one-pending-frame scheduling, idempotent stop/restart, and render-failure isolation.
- Added `scripts/test_animation_frame_controller.mjs` (19 assertions) and npm script.
- Backend pytest 367 passed; structural 143; Viewer lifecycle 32; cleanup 10; API 63/63; request 15/0 findings; response 50 JSON/52 endpoints/28 models/0 missing; package integrity 0 findings; syntax 0 errors.
- Chromium WebGL2 capability smoke passed under Xvfb/SwiftShader. It is not React/Three Viewer E2E.
- Semantic TypeScript remains blocked by absent React/Three dependencies; npm install attempt timed out and no dependency/lockfile changes were made.
- Actual Three.js resource graph, React Viewer+GLTF visual E2E, context-loss recovery and GPU profiling remain unverified.
- Detailed evidence: `BUILD-00157_VERIFICATION.md`; release summary: `BUILD-00157_RELEASE_NOTES.md`.

## Next autonomous priorities
1. Obtain an approved, pinned React/Three dependency environment without silently changing the project's lockfile.
2. Add actual Three.js object graph disposal tests and React Viewer browser E2E with a minimal GLB/data-URI GLTF fixture.
3. Verify WebGL context loss/recovery and profile repeated mount/unmount and model replacement on target devices.
4. Keep API/DB/Provider/credits/publication/rights/production/deployment approval boundaries unchanged.
