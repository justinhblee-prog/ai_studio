# AI CREATOR STUDIO — Current Handoff

## Baseline
- Build: BUILD-00140 (based on BUILD-00139)
- Focus: Lookbook output preview recovery and signed package download expiry/reissue

## Completed
- Lookbook output assembly preview now keeps loading/error/expiry state per `output_item_id` while requesting preview URLs against the exact immutable `asset_id` + `asset_version_id` pair.
- Each preview request uses `KeyedRequestGate` and the current request scope. Manual retry supersedes prior requests; a late image error only invalidates the URL if it is still the currently displayed URL for that output.
- Preview issuance failure and image-load failure are visible and recoverable through an explicit refresh/retry action. `expires_at` from the preview API is displayed.
- Lookbook package download now parses the signed URL's `expires` query parameter (15-minute signature window) separately from the package retention `expires_at` (24-hour package lifetime). This corrects the previous UI conflation of the two expiry times.
- Package download preflights signed-link expiry, fetches with `cache: no-store`, surfaces HTTP/download errors, and saves the ZIP through a browser Blob download. Users can explicitly create a new internal ZIP and signed link if the signature expires or download fails.
- Package download async state is guarded by the active API/auth/workspace scope. Assembly changes clear stale output preview and package download state.
- Strengthened the backend Lookbook assembly regression test: refreshing the exact attached AssetVersion preview leaves the attached asset/version/checksum unchanged; the approved package manifest and ZIP page filename retain that exact asset/version identity. Product Variant/SKU snapshot assertions remain in the same end-to-end test.
- Added dependency-free helper and regression tests for signed-link expiry parsing/usability and stale preview error detection (12 assertions), plus 15 structural assertions for exact-version preview/retry and package expiry/download behavior.
- Added npm scripts `test:lookbook-preview-links` and `test:lookbook-preview-recovery`.
- No backend route/schema/database/migration, dependency version, Provider, credit, publication, or rights behavior changed.

## Verification
- Lookbook preview recovery structural checks: 15/15 PASS.
- Lookbook signed-link and stale-preview helper tests: 12 assertions PASS.
- KeyedRequestGate: 7 assertions PASS.
- RequestScopeGate: 7 assertions PASS.
- Project lifecycle event helper: 4 assertions PASS.
- TypeScript syntax/transpilation: 10 `.ts`/`.tsx` sources + 4 `.d.mts` declarations; 0 errors. Syntax only, not semantic type checking.
- Viewer API contract: 63/63.
- Request body contract: 15 checked; 0 findings.
- Response schema contract: 51 JSON endpoints across 52 method/path endpoints; 28 models; 0 missing routes/schemas.
- Viewer contract/validator tests: 2 passed.
- Package integrity: 0 findings.
- Backend Python compileall: PASS.
- Backend full pytest: 359 passed.
- Clean ZIP extraction verification: see `BUILD-00140_CLEAN_EXTRACT_VERIFICATION.md`.

## Remaining blockers
- Semantic TypeScript `tsc --noEmit` and actual React/Three.js component browser E2E remain unverified because trusted React/Three.js packages and typings are unavailable.
- Browser-driven signed preview expiry/image retry and actual ZIP Blob download are not exercised in real React component E2E; helper and source-structure tests are not a substitute for browser integration.
- PostgreSQL runtime/multi-host integration, Android, production object storage/secrets/RBAC, live Provider, credit charging, publication, rights grants and deployment remain unverified.

## Next autonomous work
1. Audit export history UX and cleanup/retention visibility without changing append-only audit semantics.
2. Add reorder-focused regression coverage proving the assembly review snapshot binds exact AssetVersion identities and page order.
3. Re-attempt semantic TypeScript and real browser component E2E only when trusted dependencies are available.

## Approval boundaries
No live Provider calls, paid APIs, credit charges, publication, rights grants, production data changes, deployment, destructive migrations, or unresolved policy decisions without explicit approval.
