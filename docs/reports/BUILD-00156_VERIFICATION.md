# BUILD-00156 Verification Report

## Scope
Viewer lifecycle integration hardening: realistic nested scene/resource graph coverage, model replacement and renderer teardown sequencing, and propagation of collected resource-disposal diagnostics into the failure-isolated cleanup runner. The source validator and authenticated GLTF structural test were also reconciled with the current authenticated `GLTFLoader.parse` implementation and disposal wrapper.

## Results
- Backend full pytest: **367 passed in 30.57s**. A later duplicate run timed out at approximately 42% without reporting a failing test; the completed run is the successful full-suite evidence. No backend source changed.
- Viewer lifecycle integration: **32 assertions passed** (nested scene graph, shared texture/material/geometry/skeleton ownership, stage resources, model replacement, teardown ordering, injected disposal failure and follow-up cleanup).
- Viewer cleanup helper: **10 runtime assertions passed**; lifecycle structure **13/13**; disposal diagnostic integration **4/4**.
- GLTF disposal regression suite: **33 assertions passed** (deduplication, cycles, skeletons, best-effort errors, traversal/getter failures).
- Authenticated GLTF lifecycle: **15/15**.
- Bounded download: **17 runtime / 19 structural**.
- Model base path: **10/10**; authenticated preview Object URL: **5**; RequestScopeGate **7**; KeyedRequestGate **7**; project lifecycle **4**; Lookbook links **12**; Lookbook recovery **19/19**.
- Viewer API contract: **63/63**; request body contract: **15 checked / 0 findings**; response contract: **50 JSON / 52 total endpoints / 28 models / 0 missing**.
- Offline source validation: **143 structural checks passed**.
- TypeScript syntax/transpilation: **10 source + 10 declaration files / 0 syntax errors**.
- Package integrity: **0 findings**; Python compileall passed.
- Chromium WebGL2 capability smoke: **passed under Xvfb** (WebGL2, shader draw/readback, ResizeObserver, animation frame). This does not load the React/Three Viewer or a GLTF model.
- Semantic `npm run typecheck`: **BLOCKED** because React, Three.js, addons and type declarations are absent. No dependency installation or lockfile modification was made.

## Changes
- Added `src/disposeViewerResources.mjs` and `.d.mts`. The wrapper executes the exhaustive best-effort GLTF disposer and throws a summarized diagnostic only after all resource attempts have completed. The surrounding `runViewerCleanupSteps` records the error and proceeds to later teardown steps.
- Wired the wrapper into GLTF model replacement, complete loaded-GLTF teardown, and stage-resource teardown.
- Added `scripts/test_viewer_lifecycle_integration.mjs` and `npm run test:viewer-lifecycle-integration`; integrated it into `test:viewer-cleanup`.
- Registered the existing authenticated preview Object URL test as an npm script.
- Updated stale structural checks to match authenticated `GLTFLoader.parse`, immutable AssetVersion `/preview-content`, and the current disposal wrapper rather than removed loader/signed-URL patterns.
- No backend/API/schema/DB/dependency-version/Provider/credit/publication/rights/production-data/deployment changes.

## Not verified
- Actual React/Three component browser E2E and visible GLB/GLTF rendering.
- Semantic TypeScript type checking.
- Production-size/target-device memory profiling.
- PostgreSQL runtime/multi-host integration, Android, production object storage/secrets/RBAC, live Provider calls, credit charging, publication, rights grants, deployment.
