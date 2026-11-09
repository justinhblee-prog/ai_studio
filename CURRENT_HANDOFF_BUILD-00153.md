# AI CREATOR STUDIO — Current Handoff

## Baseline
- Build: BUILD-00153
- Base: BUILD-00152
- Focus: viewer GPU resource lifecycle completion.

## Completed
- GLTF resource disposal now covers all parser-returned scenes, shared geometries/materials/textures, nested material uniforms, cyclic object graphs, and shared skinned-mesh skeletons.
- The viewer retains the complete GLTF result for disposal on model replacement, late parse completion after cancellation, and renderer teardown.
- Floor and grid are grouped in a dedicated stage-resource group and disposed independently of loaded GLTF content.
- Directional key-light shadow resources are explicitly disposed on renderer teardown.
- Animation actions are stopped and mixer roots uncached before model replacement and renderer teardown.
- Added 14 executable disposal assertions and 4 new structural lifecycle checks (authenticated GLTF 15/15).
- No dependency/API/schema/DB/Provider/credit/publication/rights/production-data/deployment changes.

## Verification
- Backend full pytest: 367 passed.
- GLTF disposal: 14 assertions; authenticated GLTF structural: 15/15.
- Model base path 10/10; bounded download structural 19/19 and runtime 17/17.
- Preview Object URL 5; RequestScopeGate 7; KeyedRequestGate 7; project lifecycle 4; Lookbook signed-link 12; Lookbook recovery 19/19.
- Viewer API 63/63; request body 15 checked / 0 findings; response contract 50 JSON / 52 total / 28 models / 0 missing.
- TypeScript syntax 10 source + 8 declarations / 0 syntax errors; package integrity 0 findings; Python compileall passed.
- Chromium WebGL2 capability smoke passed under Xvfb/SwiftShader. This is not React/Three E2E and did not load a GLTF model.
- Semantic `npm run typecheck` attempted but blocked by missing React/Three packages and type declarations; no dependency installation or lockfile change.
- Independent clean extraction and rerun documented in `BUILD-00153_CLEAN_EXTRACT_VERIFICATION.md`.

## Remaining blockers / limitations
- Actual React/Three browser component E2E and visible GLB/GLTF rendering remain unverified.
- Semantic TypeScript type checking remains blocked until trusted pinned dependencies can be provisioned.
- Production-size or target-device memory profiling remains unavailable.
- External glTF buffer/image URIs remain rejected; multi-file glTF import is not implemented.
- PostgreSQL runtime/multi-host integration, Android, production object storage/secrets/RBAC, live Provider calls, credit charging, publication, rights grants and deployment remain unverified.

## Next autonomous priorities
1. Continue viewer integration hardening without overstating WebGL capability probes as application E2E.
2. Provision trusted pinned React/Three.js dependencies only when registry access is available; then run semantic typecheck and actual browser E2E with minimal GLB/data-URI GLTF fixtures.
3. Profile target-device memory and representative large assets before changing parser/buffer architecture.
4. Continue readiness work without crossing approval boundaries.

## Approval boundaries
No live Provider calls, paid APIs, credit charges, publication, rights grants, production data changes, deployment, destructive migrations, or unresolved security/policy decisions without explicit approval.
