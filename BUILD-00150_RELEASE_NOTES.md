# BUILD-00150 Release Notes — Final GLTF Buffer Trim Failure Handling

## Change
- Hardened the final exact-size trim for unknown-Content-Length model downloads.
- If the stream completes but the final `Uint8Array.slice()` allocation fails, the helper now raises the same typed `ModelDownloadError` with code `memory` used for earlier allocation failures.
- Added an executable regression test that simulates final-trim allocation failure and confirms the typed recovery path.
- The completed response is already fully consumed in this case, so no reader cancellation is possible or necessary; the error is surfaced safely before GLTF parsing.

## Scope
- No dependency or lockfile changes.
- No API/schema, database, Provider, credit, publication, rights, production-data, or deployment changes.

## Verification
- Backend pytest: 367 passed.
- Bounded download runtime: 17/17; structural: 19/19.
- Authenticated GLTF loading: 9/9; preview Object URL: 5 assertions.
- RequestScopeGate: 7; KeyedRequestGate: 7; project lifecycle: 4.
- Lookbook signed-link: 12; Lookbook preview recovery: 19/19.
- Viewer API contract: 63/63; request-body contract: 15 checked / 0 findings; response contract: 50 JSON endpoints / 52 total endpoints / 28 models / 0 missing routes or schemas.
- TypeScript syntax/transpilation: 10 source + 6 declaration files / 0 syntax errors (not semantic type checking).
- Package integrity: 0 findings; Python compileall passed.
- Independent clean ZIP extraction and core test rerun: see `BUILD-00150_CLEAN_EXTRACT_VERIFICATION.md`.

## Remaining unverified areas
- Actual React/Three.js browser component E2E and visible GLB/GLTF rendering.
- Semantic `tsc --noEmit`.
- Production-size/target-device memory profiling; geometric buffer growth can temporarily retain old and new backing stores, and 256 MiB is not a device compatibility guarantee.
- External glTF buffer/image URI import, PostgreSQL runtime/multi-host integration, Android, production object storage/secrets/RBAC, live Provider calls, credit charging, publication, rights grants, and deployment.
