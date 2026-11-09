# BUILD-00153 Release Notes — Viewer GPU Resource Lifecycle Completion

## Changes
- Extended GLTF disposal to release shared `SkinnedMesh` skeleton resources exactly once; Three.js `Skeleton.dispose()` releases allocated bone textures.
- Isolated the viewer floor and grid in a dedicated stage-resource group so their geometries and materials are disposed even when a GLTF is currently loaded.
- Explicitly dispose the directional key light shadow resources/render target during renderer teardown.
- Stop animation actions and call `AnimationMixer.uncacheRoot()` before dropping the model root on replacement and renderer teardown.
- Added executable skeleton deduplication tests and structural lifecycle regression checks.

## Verification
- Backend full pytest: 367 passed.
- GLTF disposal runtime: 14 assertions passed.
- Authenticated GLTF structural: 15/15.
- Model base path: 10/10; bounded download runtime: 17/17; bounded structural: 19/19.
- Preview Object URL: 5; RequestScopeGate: 7; KeyedRequestGate: 7; project lifecycle: 4; Lookbook signed-link: 12; Lookbook recovery: 19/19.
- Viewer API contract: 63/63; request body contract: 15 checked / 0 findings; response contract: 50 JSON / 52 total / 28 models / 0 missing.
- TypeScript syntax: 10 source + 8 declarations / 0 syntax errors; package integrity: 0 findings; Python compileall passed.
- Chromium WebGL2 capability smoke passed under Xvfb/SwiftShader; this is not a React/Three component E2E and did not load GLTF.
- Independent clean extraction and rerun documented in `BUILD-00153_CLEAN_EXTRACT_VERIFICATION.md`.

## Limitations
- Semantic `tsc --noEmit` remains blocked by absent React/Three packages and type declarations; no dependencies or lockfiles were modified.
- Actual React/Three browser rendering, target-device memory profiling, external glTF buffer/image URI import, PostgreSQL runtime/multi-host integration, Android, production storage/secrets/RBAC, live Provider/credit operations, publication, rights grants and deployment remain unverified.
- No API/schema, database, Provider, credit, publication, rights, production data or deployment changes.
