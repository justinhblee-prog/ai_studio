# BUILD-00144 Verification Report

## Scope
Authenticated, Workspace-membership-rechecked AssetVersion image preview delivery and Blob Object URL lifecycle management.

## Results
- Backend full pytest: **367 passed**.
- Asset API focused suite: **69 passed**.
- Viewer structural validation: **143/143 passed**.
- Lookbook preview recovery structural validation: **19/19 passed**.
- Authenticated preview Object URL registry: **5 assertions passed** (replacement revokes previous URL; explicit revoke; clear releases all remaining URLs).
- RequestScopeGate: **7 assertions passed**.
- KeyedRequestGate: **7 assertions passed**.
- Project lifecycle event helper: **4 assertions passed**.
- Lookbook signed-link helper: **12 assertions passed**.
- TypeScript syntax/transpilation: **10 `.ts`/`.tsx` source files + 5 `.d.mts` declarations; 0 syntax errors**. Syntax validation only, not semantic type checking.
- Viewer API contract: **64/64 matched**, no missing routes, query mismatches, or unresolved dynamic segments.
- Request body contract: **15 checked, 0 findings**.
- Response contract: **51 JSON endpoints across 53 total endpoints; 29 response models; 0 missing routes/schemas; 0 unresolved dynamic segments**. The new authenticated binary preview endpoint is explicitly documented as a non-JSON streaming response.
- Runtime OpenAPI snapshot `--check`: PASS.
- Python `compileall`: PASS.
- Package integrity: **0 findings**.

## Authenticated preview behavior covered
- Missing Bearer authentication is rejected.
- Valid workspace member can fetch exact immutable AssetVersion bytes.
- Current Viewer role is permitted to fetch preview bytes.
- Workspace membership lookup failure/revocation is denied.
- Exact immutable version content, private/no-store response and recorded checksum/size validation are retained.

## Not verified / limitations
- Actual React/Three.js component browser E2E and real browser fetch-to-Blob image preview flow remain unverified. The environment lacks trusted React/Three.js installed packages and typings.
- Semantic `tsc --noEmit` remains blocked by missing React/Three.js dependencies and type declarations.
- GLTF/GLB model preview continues to use short-lived signed URLs because external relative buffers/textures require a resource-aware loader; the single-Blob migration is intentionally limited to image previews.
- PostgreSQL runtime/multi-host integration, Android build/device testing, production object storage/secrets/RBAC, live Provider calls, credit charging, publication, rights grants and deployment remain unverified.
- Local filesystem storage remains PoC-only; `O_NOFOLLOW` is platform-dependent.

## Change boundaries
No database migrations, external dependency changes, Provider calls, credit charges, publication, rights grants, production data changes, or deployment were performed.
