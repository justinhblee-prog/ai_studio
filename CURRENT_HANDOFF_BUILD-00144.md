# AI CREATOR STUDIO — Current Handoff

## Baseline
- Build: BUILD-00144 (based on BUILD-00143)
- Focus: Membership-revocable authenticated AssetVersion image previews and object URL lifecycle

## Completed
- Added `GET /v1/assets/{asset_id}/versions/{version_id}/preview-content`.
- The new endpoint requires a current Bearer token and current Workspace membership (`owner`, `admin`, `editor`, `viewer`) at every fetch. Missing/removed membership returns 404; invalid/missing authentication returns 401.
- The endpoint resolves the exact immutable AssetVersion, verifies recorded size and SHA-256, and streams from the descriptor-pinned private-file response. It emits private/no-store bytes and is documented in runtime OpenAPI as a binary response.
- Photo Draft, Output Review, and Lookbook output assembly now use authenticated fetch-to-Blob for image previews instead of reusable signed preview URLs.
- Added `AuthenticatedPreviewObjectUrls` to replace/revoke keyed Blob URLs and release all owned URLs on workspace/assembly reset or component unmount. Failed image loads revoke only the current URL; stale responses cannot create a new URL after request/scope guards fail.
- Kept signed preview URL behavior for the 3D Asset Workspace model loader. GLTF/GLB model URLs can resolve dependent resources, so converting them to one Blob URL without a resource-aware loader would break valid external buffer/texture references. This remains short-lived signed capability access and is not membership-revocable on every byte request.
- No database migration, external dependency, Provider call, credit behavior, publication, rights behavior, or deployment was added.

## Verification
- Backend full pytest: 367 passed.
- Asset API focused suite: 69 passed (includes authenticated endpoint auth, membership, immutable bytes, and viewer role).
- Viewer structural checks: 143 passed.
- Lookbook preview recovery structural checks: 19/19.
- Authenticated object URL registry tests: 5 assertions.
- RequestScopeGate: 7; KeyedRequestGate: 7; project lifecycle events: 4; Lookbook signed-link helper: 12 assertions passed.
- TypeScript syntax/transpilation: 10 source files + 5 `.d.mts` declarations; 0 syntax errors. This is syntax-only, not semantic type checking.
- Viewer API contract: 64/64; request body contract: 15 checked / 0 findings.
- Viewer response contract: 51 JSON endpoints across 53 total endpoints, 29 models, 0 missing routes/schemas; authenticated binary preview endpoint is explicitly represented as a non-JSON success response.
- Runtime OpenAPI snapshot check: PASS; Python compileall: PASS; package integrity: 0 findings.
- Full backend suite after final source update: 367 passed.

## Remaining blockers / limits
- Actual React/Three.js component browser E2E and browser-driven fetch-to-Blob image preview flow remain unverified; no React packages/typings are installed in the environment.
- Semantic `tsc --noEmit` remains blocked by missing React/Three.js packages and typings.
- 3D GLTF/GLB model preview continues to use short-lived signed URLs; every-byte membership revocation is not claimed for that path.
- PostgreSQL runtime/multi-host integration, Android build/device testing, production object storage/secrets/RBAC, live Provider calls, credit charging, publication, rights grants, and deployment remain unverified.
- Local filesystem storage remains PoC-only. `O_NOFOLLOW` remains platform-dependent.

## Next autonomous work
1. Evaluate authenticated model delivery for GLB and GLTF without breaking relative external buffers/textures; likely requires a resource-aware loader/URL modifier or server-side packaging, not a single Blob URL.
2. Add real browser tests for authenticated fetch-to-Blob previews, workspace change, logout/token change, component unmount, and revoked membership.
3. Re-attempt semantic TypeScript and React/Three.js E2E only when trusted dependencies and runtime are available.

## Approval boundaries
No live Provider calls, paid APIs, credit charges, publication, rights grants, production data changes, deployment, destructive migrations, or unresolved policy decisions without explicit approval.
