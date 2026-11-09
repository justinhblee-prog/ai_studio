# BUILD-00148 Verification Report

## Change under test
Bounded authenticated GLB/GLTF response reader memory and header validation hardening.

## Results
- Backend full pytest: **367 passed** (`BUILD-00148_BACKEND_PYTEST.log`).
- Bounded download structural: **15/15**.
- Bounded download executable runtime: **12/12** (`BUILD-00148_BOUNDED_GLTF_RUNTIME.log`).
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

## Runtime cases added or strengthened
1. Known Content-Length uses one exact-size destination buffer.
2. Zero-byte known-length response succeeds with an empty ArrayBuffer.
3. Oversized declared length is rejected and response body cancellation is requested before streaming.
4. Actual streamed bytes remain bounded by the global ceiling.
5. Stream bytes exceeding the declared Content-Length are cancelled and rejected.
6. Truncated transfer, abort, and 401/403/404/409 mappings remain covered.
7. Invalid, negative, fractional, and empty Content-Length values fail closed.

## Environment notes
- `pytest -q` requires `PYTHONPATH=.` in this execution environment. With that explicit project path, all 367 tests pass.
- npm registry provisioning was retried but remains blocked by DNS `EAI_AGAIN registry.npmjs.org`; no React/Three.js packages or lockfiles were changed.

## Not verified
- Actual React/Three.js component E2E or visible GLB/GLTF rendering.
- Semantic `tsc --noEmit`.
- Production-size or target-device memory profiling.
- PostgreSQL runtime/multi-host integration, Android, production object storage/secrets/RBAC, live Provider calls, credit charging, publication, rights grants, or deployment.
