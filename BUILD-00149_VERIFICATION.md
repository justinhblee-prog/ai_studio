# BUILD-00149 Verification Report

## Change under test
Capped geometric-growth accumulator for unknown-Content-Length authenticated GLB/GLTF downloads, plus typed allocation-failure recovery.

## Results
- Backend full pytest: **367 passed**.
- Bounded download structural: **19/19**.
- Bounded download executable Fetch/ReadableStream runtime: **16/16**.
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
- Package integrity: **0 findings**.
- Python compileall: passed.

## New runtime coverage
1. Unknown-length stream grows its buffer across multiple capacity boundaries and preserves exact byte order/content.
2. Empty unknown-length stream returns a zero-byte ArrayBuffer.
3. Simulated unknown-length growth allocation failure cancels the reader and returns `ModelDownloadError` code `memory`.
4. Simulated known-length destination allocation failure cancels the unlocked response body and returns the same typed error.
5. Existing known-length, Content-Length validation, 256 MiB cap, overflow cancellation, truncation, abort and HTTP status mappings remain passing.

## Environment notes
- Backend tests require `PYTHONPATH=.` in this execution environment; with it, all 367 tests pass.
- No npm package provisioning or lockfile changes were attempted for this build. Trusted React/Three.js dependency availability remains a separate blocker.

## Not verified
- Actual React/Three.js component E2E or visible GLB/GLTF rendering.
- Semantic `tsc --noEmit`.
- Production-size or target-device memory profiling. Geometric growth may temporarily retain both old and new buffers during resize; 256 MiB is not a device compatibility guarantee.
- External glTF buffer/image URI loading; PostgreSQL runtime/multi-host integration; Android; production object storage/secrets/RBAC; live Provider calls; credit charging; publication; rights grants; deployment.
