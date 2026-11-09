# BUILD-00150 Verification Report

## Change under test
Unknown-length authenticated GLTF/GLB response finalization now maps exact-size trim allocation failure to typed `ModelDownloadError` code `memory`.

## Results
- Backend full pytest: **367 passed**.
- Bounded download structural: **19/19**.
- Bounded download executable Fetch/ReadableStream runtime: **17/17**.
- Authenticated GLTF loading structural: **9/9**.
- Authenticated preview Object URL lifecycle: **5 assertions**.
- RequestScopeGate: **7 assertions**.
- KeyedRequestGate: **7 assertions**.
- Project lifecycle events: **4 assertions**.
- Lookbook signed-link behavior: **12 assertions**.
- Lookbook preview recovery: **19/19**.
- Viewer API contract: **63/63**, no missing calls or query mismatches.
- Request body contract: **15 checked, 0 findings**.
- Response contract: **50 JSON endpoints / 52 total endpoints / 28 models / 0 missing routes or schemas**.
- TypeScript syntax/transpilation: **10 source files + 6 declaration files, 0 syntax errors**. This is not semantic type checking.
- Package integrity tests: **4 passed, 0 findings**.
- Python compileall: passed.
- ZIP CRC and companion SHA-256: passed.
- Independent clean extraction: backend full suite 367 passed; bounded runtime 17/17; structural 19/19; authenticated GLTF 9/9; API/request/response contracts; syntax and package integrity checks passed. See `BUILD-00150_CLEAN_EXTRACT_VERIFICATION.md` and `BUILD-00150_CLEAN_*.log`.

## New runtime coverage
1. Unknown-length stream grows across capacity boundaries and preserves exact byte order/content.
2. Empty unknown-length stream returns a zero-byte ArrayBuffer.
3. Simulated unknown-length growth allocation failure cancels the reader and returns typed `memory`.
4. Simulated known-length destination allocation failure cancels the unlocked response body and returns typed `memory`.
5. Simulated final exact-size trim allocation failure returns typed `memory` rather than leaking a raw RangeError.
6. Existing known-length, Content-Length validation, 256 MiB cap, overflow cancellation, truncation, abort and HTTP status mappings remain passing.

## Environment notes
- Backend tests require `PYTHONPATH=.` in this execution environment; with it, all 367 tests pass.
- No npm package provisioning or lockfile changes were attempted for this build.

## Not verified
- Actual React/Three.js component E2E or visible GLB/GLTF rendering.
- Semantic `tsc --noEmit`.
- Production-size or target-device memory profiling. Geometric growth may temporarily retain both old and new buffers during resize; 256 MiB is not a device compatibility guarantee.
- External glTF buffer/image URI loading; PostgreSQL runtime/multi-host integration; Android; production object storage/secrets/RBAC; live Provider calls; credit charging; publication; rights grants; deployment.
