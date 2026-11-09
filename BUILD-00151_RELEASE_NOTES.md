# BUILD-00151 Release Notes — Relative GLTF Model URL Base Resolution

## Change
- Added a dependency-free `resolveModelBasePath` helper for the base path supplied to `GLTFLoader.parse`.
- Relative and root-relative AssetVersion endpoints now resolve against the current page URL instead of relying on `new URL('.', modelUrl)` requiring an absolute URL.
- Absolute HTTP(S) URLs remain supported; non-HTTP(S) schemes and invalid URLs fail closed with a clear `TypeError`.
- Added 10 executable tests covering relative/root-relative/absolute endpoints, query/fragment handling, malformed input and rejected schemes.
- Updated authenticated GLTF structural checks and added a dedicated npm test script.

## Scope
- No dependency or lockfile changes.
- No API/schema, database, Provider, credit, publication, rights, production-data, or deployment changes.

## Verification
- Backend pytest: 367 passed.
- Model base path helper: 10/10; authenticated GLTF structural: 10/10.
- Bounded download runtime: 17/17; structural: 19/19.
- Authenticated preview Object URL: 5; RequestScopeGate: 7; KeyedRequestGate: 7; project lifecycle: 4.
- Lookbook signed-link: 12; Lookbook preview recovery: 19/19.
- Viewer API contract: 63/63; request-body contract: 15 checked / 0 findings; response contract: 50 JSON endpoints / 52 total endpoints / 28 models / 0 missing routes or schemas.
- TypeScript syntax/transpilation: 10 source + 7 declaration files / 0 syntax errors (not semantic type checking).
- Package integrity: 4 tests passed; Python compileall passed.
- Chromium WebGL2 capability smoke: passed (SwiftShader; triangle render/readback, ResizeObserver and requestAnimationFrame). This does not load React/Three.js or a GLTF model.
- Independent clean ZIP extraction and core test rerun: see `BUILD-00151_CLEAN_EXTRACT_VERIFICATION.md`.

## Remaining unverified areas
- Actual React/Three.js browser component E2E and visible GLB/GLTF rendering.
- Semantic `tsc --noEmit`.
- Production-size/target-device memory profiling; 256 MiB is not a device compatibility guarantee.
- External glTF buffer/image URI import, PostgreSQL runtime/multi-host integration, Android, production object storage/secrets/RBAC, live Provider calls, credit charging, publication, rights grants, and deployment.
