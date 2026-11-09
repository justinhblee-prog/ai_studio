# BUILD-00147 Verification Report

## Scope
Extracted the bounded authenticated GLTF/GLB response reader into a standalone dependency-free module used by `Studio3DViewer`, added runtime tests, and rejected incomplete transfers when a valid `Content-Length` does not match the received byte count. No API/schema/DB/dependency/provider/credit/publication/rights/deployment behavior was changed.

## Results
- Backend full pytest: **367 passed**.
- Bounded download structural checks: **15/15**.
- Executable Node Fetch/ReadableStream runtime tests: **9/9**.
- Authenticated GLTF loading structural checks: **9/9**.
- RequestScopeGate: **7 assertions**; KeyedRequestGate: **7 assertions**; project lifecycle: **4 assertions**; authenticated preview Object URL registry: **5 assertions**; Lookbook signed-link: **12 assertions**; Lookbook recovery: **19/19**.
- Viewer API contract: **63/63**, no missing routes or query mismatches.
- Request body contract: **15 checked, 0 findings**.
- Response contract: **50 JSON endpoints / 52 total / 28 models**, no missing routes or schemas.
- TypeScript syntax/transpilation: **10 source files + 6 declaration files, 0 syntax errors**. This is not semantic type checking.
- Package integrity: **0 findings**; Python compileall passed.

## Runtime harness coverage
1. Known Content-Length: byte assembly and progress callback.
2. Unknown Content-Length: successful streaming.
3. Declared size above 256 MiB: rejected before body consumption.
4. Actual stream crossing 256 MiB: stream cancelled and rejected.
5. Abort before read: AbortError.
6. Abort during pending read: reader cancelled and AbortError.
7. Truncated transfer: declared/actual length mismatch becomes network error.
8. HTTP 401/403/404/409: typed safe error mapping.
9. Malformed Content-Length: handled as unknown length.

## Limitations / not verified
- React/Three.js browser component E2E and visible GLB/GLTF rendering remain unverified; dependencies are not provisioned.
- Semantic `tsc --noEmit` remains unverified; only syntax/transpilation and declaration parsing passed.
- No production-size fixture/device memory profiling. `GLTFLoader.parse` still needs a contiguous ArrayBuffer; temporary peak memory can exceed the 256 MiB source cap.
- External glTF buffer/image URIs remain rejected; multi-file glTF package loading is not implemented.
- PostgreSQL multi-host runtime, Android, production object storage/secrets/RBAC, live Providers, credit charging, publication, rights grants and deployment remain unverified.

## Integrity
ZIP CRC and SHA-256 are recorded alongside the release artifact. A separate clean extraction was tested; see `BUILD-00147_CLEAN_EXTRACT_VERIFICATION.md`.
