# BUILD-00152 Verification Report

## Change under test
Complete GLTF resource disposal across all parser-returned scenes and nested material texture references.

## Results
- Backend full pytest: **367 passed**.
- GLTF disposal runtime: **11 assertions passed** (shared geometry/material/texture deduplication, inactive scene, nested uniforms, cyclic object graph, legacy scene root, empty/null input).
- Authenticated GLTF loading structural: **11/11**.
- Model base path: **10/10**.
- Bounded download structural: **19/19**; executable Fetch/ReadableStream runtime: **17/17**.
- Authenticated preview Object URL: **5 assertions**.
- RequestScopeGate: **7 assertions**; KeyedRequestGate: **7 assertions**; project lifecycle: **4 assertions**.
- Lookbook signed-link: **12 assertions**; Lookbook preview recovery: **19/19**.
- Viewer API contract: **63/63**; request body contract: **15 checked / 0 findings**.
- Response contract: **50 JSON endpoints / 52 total endpoints / 28 models / 0 missing routes or schemas**.
- TypeScript syntax/transpilation: **10 source files + 8 declaration files / 0 syntax errors**. Not semantic type checking.
- Package integrity: **4 tests passed / 0 findings**.
- Python compileall: passed.
- Chromium WebGL2 capability smoke: passed under Xvfb/SwiftShader (shader compile/link/draw/readback, ResizeObserver, requestAnimationFrame). This is not React/Three.js component E2E and did not load a GLTF model.
- `npm run typecheck`: attempted; blocked by missing installed `react`, `three`, and corresponding type declarations. No dependency install or lockfile change was made.

## Not verified
- Actual React/Three.js component E2E or visible GLB/GLTF rendering.
- Semantic TypeScript type checking due unavailable package dependencies.
- Production-size or target-device memory profiling.
- External glTF buffer/image URI loading; PostgreSQL runtime/multi-host integration; Android; production object storage/secrets/RBAC; live Provider calls; credit charging; publication; rights grants; deployment.
