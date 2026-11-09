# BUILD-00151 Verification Report

## Change under test
HTTP(S) model URL base-path resolver for `GLTFLoader.parse`, supporting relative and root-relative AssetVersion endpoints.

## Results
- Backend full pytest: **367 passed**.
- Model base path runtime: **10/10**.
- Authenticated GLTF loading structural: **10/10**.
- Bounded download structural: **19/19**; executable Fetch/ReadableStream runtime: **17/17**.
- Authenticated preview Object URL: **5 assertions**.
- RequestScopeGate: **7 assertions**; KeyedRequestGate: **7 assertions**; project lifecycle: **4 assertions**.
- Lookbook signed-link: **12 assertions**; Lookbook preview recovery: **19/19**.
- Viewer API contract: **63/63**, no missing calls or query mismatches.
- Request body contract: **15 checked, 0 findings**.
- Response contract: **50 JSON endpoints / 52 total endpoints / 28 models / 0 missing routes or schemas**.
- TypeScript syntax/transpilation: **10 source files + 7 declaration files, 0 syntax errors**. This is not semantic type checking.
- Package integrity tests: **4 passed, 0 findings**.
- Python compileall: passed.
- Chromium WebGL2 capability smoke: passed under Xvfb/SwiftShader, including triangle shader compile/link/draw/readback, ResizeObserver and requestAnimationFrame. This is not React/Three.js component E2E and did not load a GLTF model.
- ZIP CRC and companion SHA-256: passed.
- Independent clean extraction: backend 367 passed; model base path 10/10; bounded runtime 17/17; authenticated GLTF 10/10; bounded structural 19/19; API/request/response contracts, syntax and package integrity passed. See `BUILD-00151_CLEAN_EXTRACT_VERIFICATION.md` and `BUILD-00151_CLEAN_*.log`.

## New runtime coverage
1. Relative endpoint path resolution.
2. Root-relative endpoint path resolution.
3. Absolute HTTP and HTTPS endpoint path resolution.
4. Query and fragment exclusion from the GLTF base path.
5. Invalid URL and invalid page-base rejection.
6. `javascript:`, `data:` and FTP scheme rejection.

## Not verified
- Actual React/Three.js component E2E or visible GLB/GLTF rendering.
- Semantic `tsc --noEmit`.
- Production-size or target-device memory profiling.
- External glTF buffer/image URI loading; PostgreSQL runtime/multi-host integration; Android; production object storage/secrets/RBAC; live Provider calls; credit charging; publication; rights grants; deployment.
