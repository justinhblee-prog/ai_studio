# AI CREATOR STUDIO — Current Handoff

## Baseline
- Build: BUILD-00139 (based on BUILD-00138)
- Focus: Immutable AssetVersion preview expiry/error recovery in Photo Draft and Output Review

## Completed
- Photo Draft now maintains per-version preview error, loading and expiry state keyed by exact `asset_id:version_id`.
- Photo Draft preview URL reissue clears the prior URL first, records API `expires_at`, shows a retryable error when URL issuance fails, and exposes explicit refresh/retry controls for source and output versions.
- Photo Draft image `onError` only invalidates the URL if it is still the current URL for that exact immutable version. It clears the URL and prompts the user to request a fresh signed URL.
- Output Review now tracks preview error/loading/expiry state per output, displays missing immutable AssetVersion reference errors, and offers explicit preview refresh/retry.
- Output Review preview requests use the exact `asset_id` and `asset_version_id` in the persisted review response. `KeyedRequestGate` ensures a late automatic preview hydration cannot replace a newer manual retry.
- Refreshing Output Review output data clears prior preview state before loading the current review map, avoiding stale previews being displayed beside refreshed metadata.
- Added 7 structural assertions.
- No backend routes/schemas/migrations, external dependencies, public props, Provider calls, credit behavior, publication or rights behavior changed.

## Verification
- Structural validation: 140/140 PASS.
- KeyedRequestGate: 7 assertions PASS.
- RequestScopeGate: 7 assertions PASS.
- TypeScript syntax/transpilation: 10 source files + 3 declaration parses, 0 errors. This is syntax validation only, not semantic type checking.
- Viewer API contract: 63/63.
- Request body contract: 15 checked, 0 findings.
- Response contract: 51 JSON endpoints across 52 endpoints; 28 models; no missing routes/schemas.
- Viewer pytest suites: 8 passed.
- Package integrity: 0 findings.
- Backend Python compileall: PASS.
- Backend full pytest: 359 passed in 15.19s.
- Clean ZIP extraction verification: see `BUILD-00139_CLEAN_EXTRACT_VERIFICATION.md`.

## Remaining blockers
- Semantic TypeScript `tsc --noEmit` and actual React/Three.js browser component E2E remain unverified because trusted React/Three.js packages and typings are unavailable.
- Browser-driven expired signed URL fetch/retry behavior is not yet exercised in real React component E2E.
- PostgreSQL runtime/multi-host integration, Android, production object storage/secrets/RBAC, live Provider, credit charging, publication, rights grants and deployment remain unverified.

## Next autonomous work
1. Review Lookbook output preview URL expiry and internal package export download expiry/retry state.
2. Check exact immutable AssetVersion identity across output attach, assembly review and package export after a preview refresh.
3. Add dependency-free tests for URL expiry parsing and stale image-error behavior where practical.
4. Re-attempt semantic TypeScript and actual browser component E2E only when trusted dependencies are available.

## Approval boundaries
No live Provider calls, paid APIs, credit charges, publication, rights grants, production data changes, deployment, destructive migrations, or unresolved policy decisions without explicit approval.
