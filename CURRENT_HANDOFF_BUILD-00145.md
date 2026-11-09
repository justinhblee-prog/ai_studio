# AI CREATOR STUDIO — Current Handoff

## Baseline
- Build: BUILD-00145
- Base: BUILD-00144
- Focus: Authenticated GLTF/GLB AssetVersion loading in the 3D Viewer

## Completed
- `AssetWorkspace` no longer obtains a signed preview URL for the current 3D model. It loads the version list, selects the exact `is_current` AssetVersion, and constructs the authenticated `/v1/assets/{asset_id}/versions/{version_id}/preview-content` endpoint.
- `Studio3DViewer` accepts the short-lived in-memory `accessToken`, fetches model bytes with `Authorization: Bearer ...`, `cache: no-store`, and an AbortController, then calls `GLTFLoader.parse` on the returned ArrayBuffer.
- Changing the model URL or access token aborts the prior fetch. Component cleanup also aborts. A GLTF parse callback arriving after cancellation disposes its scene resources instead of attaching stale content.
- Server-side glTF validation still rejects external buffer/image URIs; GLB and self-contained JSON glTF with embedded base64 data URIs are supported by this single-resource authenticated fetch strategy. No new API route or schema was added.
- Response-contract inventory updated to 52 viewer endpoints / 50 JSON contracts / 28 distinct response models because AssetWorkspace no longer calls the signed preview-url response; endpoint itself remains available to other clients.
- Added `scripts/test_authenticated_gltf_loading.py` and npm script `test:authenticated-gltf-loading`.

## Verification
- Backend full pytest: 367 passed.
- Authenticated GLTF loading structural checks: 9/9.
- Authenticated preview Object URL registry: 5 assertions.
- RequestScopeGate: 7; KeyedRequestGate: 7; project lifecycle events: 4; Lookbook signed-link helper: 12; Lookbook preview recovery: 19/19.
- TypeScript syntax/transpilation: 10 source files + 5 declaration files; 0 syntax errors. This is not semantic type checking.
- Viewer API contract: 63/63; request body contract: 15 checked / 0 findings; response contract: 50 JSON endpoints / 52 total / 28 models / 0 missing routes or schemas.
- Package integrity: 0 findings; Python compileall passed.

## Remaining blockers / limitations
- Actual React/Three.js browser component E2E and actual GLB/GLTF render were not run. Trusted React/Three.js packages and typings are not installed in the environment; network package provisioning is unavailable. Do not claim the model visibly rendered in a browser.
- Semantic `tsc --noEmit` remains unverified for the same dependency/typing limitation.
- The authenticated model fetch buffers the full file in browser memory before `GLTFLoader.parse`; large-file memory pressure should be tested with production-size fixtures before release.
- External GLTF buffer/image URIs remain rejected by server validation. Multi-file glTF package import is not implemented.
- PostgreSQL runtime/multi-host integration, Android, production object storage/secrets/RBAC, live Provider calls, credit charging, publication, rights grants and deployment remain unverified.

## Next autonomous priorities
1. Add bounded client-side download size handling and clearer 401/403/404/409 model preview recovery states without logging tokens or URLs.
2. Add a browser integration harness with trusted pinned React/Three.js dependencies when dependency provisioning is available; test GLB and data-URI GLTF fixtures, cancellation, parse failure and WebGL cleanup.
3. Evaluate a streaming or worker-based parse path only with measured large-asset fixtures; avoid adding untrusted dependencies.
4. Recheck full semantic TypeScript and real browser E2E when the trusted dependency environment becomes available.

## Approval boundaries
No live Provider calls, paid APIs, credit charges, publication, rights grants, production data changes, deployment, destructive migrations, or unresolved security/policy decisions without explicit approval.
