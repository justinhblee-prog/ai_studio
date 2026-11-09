# AI CREATOR STUDIO — Current Handoff

## Baseline
- Build: BUILD-00152
- Base: BUILD-00151
- Focus: complete, deduplicated GLTF GPU-resource disposal across all parsed scenes.

## Completed
- Added dependency-free `disposeGltfResources.mjs` and `.d.mts` declaration.
- Cleanup covers every scene returned by GLTFLoader, or a single scene/root fallback.
- Collects shared geometries, single/array materials, and textures nested in material properties/uniforms; cycles are guarded and each resource is disposed once per cleanup call.
- Viewer retains the complete GLTF result and disposes it during model replacement, late parse completion after cancellation, and renderer teardown.
- Added 11 executable assertions for shared resources, inactive scenes, nested textures, cyclic references, legacy scene-root input and empty/null inputs.
- No dependency, API/schema, DB, Provider, credit, publication, rights, production-data or deployment changes.

## Verification
- Backend full pytest: 367 passed.
- GLTF disposal: 11 assertions; authenticated GLTF structural: 11/11.
- Model base path: 10/10; bounded download structural 19/19 and runtime 17/17.
- Preview Object URL 5; RequestScopeGate 7; KeyedRequestGate 7; project lifecycle 4; Lookbook signed-link 12; Lookbook recovery 19/19.
- Viewer API 63/63; request body 15 checked / 0 findings; response contract 50 JSON / 52 total / 28 models / 0 missing.
- TypeScript syntax: 10 source + 8 declarations / 0 syntax errors. Semantic typecheck attempted but blocked by absent React/Three dependencies; no package provisioning or lockfile change.
- Package integrity 4 tests; Python compileall passed.
- Chromium WebGL2 capability smoke passed under Xvfb/SwiftShader; not a React/Three.js E2E and did not load GLTF.
- Independent clean extraction and test rerun documented in `BUILD-00152_CLEAN_EXTRACT_VERIFICATION.md`.

## Remaining blockers / limitations
- Actual React/Three.js browser component E2E and visible GLB/GLTF rendering remain unverified.
- Semantic `tsc --noEmit` remains blocked until trusted pinned dependencies can be provisioned.
- Production-size or target-device memory profiling remains unavailable.
- External glTF buffer/image URIs remain rejected; multi-file glTF import is not implemented.
- PostgreSQL runtime/multi-host integration, Android, production object storage/secrets/RBAC, live Provider calls, credit charging, publication, rights grants and deployment remain unverified.

## Next autonomous priorities
1. Provision trusted pinned React/Three.js dependencies when registry access is available; run semantic typecheck and actual browser E2E with minimal GLB/data-URI GLTF fixtures.
2. Add renderer/scene lifecycle integration assertions when real Three.js packages are available.
3. Profile target-device memory and representative large assets before altering buffer/parser architecture.
4. Continue readiness work without crossing approval boundaries.

## Approval boundaries
No live Provider calls, paid APIs, credit charges, publication, rights grants, production data changes, deployment, destructive migrations, or unresolved security/policy decisions without explicit approval.
