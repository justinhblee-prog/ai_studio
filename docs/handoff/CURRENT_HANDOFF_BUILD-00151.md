# AI CREATOR STUDIO — Current Handoff

## Baseline
- Build: BUILD-00151
- Base: BUILD-00150
- Focus: safe base-path resolution for authenticated GLTF/GLB parsing when the model endpoint is relative to the current page.

## Completed
- Added dependency-free `resolveModelBasePath(modelUrl, pageUrl)` and a TypeScript declaration.
- The helper resolves relative, root-relative and absolute HTTP(S) model endpoints to the containing directory used by `GLTFLoader.parse`.
- Invalid URLs and non-HTTP(S) schemes fail closed; query strings and fragments do not leak into the base path.
- Viewer now resolves its parse base against `window.location.href`, fixing relative endpoint handling without changing the authenticated fetch path.
- Added 10 executable helper tests and authenticated GLTF structural coverage (10/10).
- BUILD-00150's typed final-trim allocation recovery and all existing bounded-download protections remain unchanged.
- No dependency, API/schema, database, Provider, credit, publication, rights, production-data or deployment changes.

## Verification
- Backend full pytest: 367 passed.
- Model base path helper: 10/10; authenticated GLTF structural: 10/10.
- Bounded download structural: 19/19; executable runtime: 17/17.
- Authenticated preview Object URL: 5; RequestScopeGate: 7; KeyedRequestGate: 7; project lifecycle: 4; Lookbook signed-link: 12; Lookbook recovery: 19/19.
- Viewer API contract: 63/63; request-body contract: 15 checked / 0 findings; response contract: 50 JSON / 52 total / 28 models / 0 missing.
- TypeScript syntax/transpilation: 10 source + 7 declaration files, 0 syntax errors. This is not semantic type checking.
- Package integrity: 4 tests passed; Python compileall passed.
- Chromium WebGL2 capability smoke: passed under Xvfb/SwiftShader (triangle shader compile/link/draw/readback, ResizeObserver and requestAnimationFrame). It is not React/Three.js component E2E and did not load a GLTF model.
- Independent clean ZIP extraction and core test rerun: see `BUILD-00151_CLEAN_EXTRACT_VERIFICATION.md`.

## Remaining blockers / limitations
- Actual React/Three.js browser component E2E and visible GLB/GLTF rendering remain unverified.
- Semantic `tsc --noEmit` remains unverified; syntax/transpilation only.
- Production-size or target-device memory profiling is unavailable; geometric buffer growth can temporarily retain old and new backing stores, and 256 MiB is not a device compatibility guarantee.
- External glTF buffer/image URIs remain rejected; multi-file glTF package import is not implemented.
- PostgreSQL runtime/multi-host integration, Android, production object storage/secrets/RBAC, live Provider calls, credit charging, publication, rights grants and deployment remain unverified.

## Next autonomous priorities
1. Retry trusted pinned React/Three.js package provisioning only when registry access is available; run semantic TypeScript and actual browser E2E with minimal GLB/data-URI GLTF fixtures.
2. Add real GLTF parse/cancellation/scene-disposal tests and WebGL cleanup assertions.
3. Measure memory on representative target devices and production-size fixtures; consider parser/worker changes only against measured evidence.
4. Continue readiness gaps without crossing approval boundaries.

## Approval boundaries
No live Provider calls, paid APIs, credit charges, publication, rights grants, production data changes, deployment, destructive migrations, or unresolved security/policy decisions without explicit approval.
