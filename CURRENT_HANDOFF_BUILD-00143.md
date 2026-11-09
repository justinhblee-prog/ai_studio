# AI CREATOR STUDIO — Current Handoff

## Baseline
- Build: BUILD-00143 (based on BUILD-00142)
- Focus: Descriptor-pinned private file delivery and path-replacement race protection

## Completed
- Added `app/private_file_response.py` with a descriptor-pinned streaming response. It opens a path once, applies `O_NOFOLLOW` where supported, validates the opened descriptor with `fstat`, optionally checks expected size and SHA-256 through the same descriptor, rewinds, and streams from that descriptor.
- Migrated AssetVersion preview, general private asset preview, generation output download, and Lookbook package download away from path-based `FileResponse`.
- Lookbook ZIP and AssetVersion bytes are revalidated by size and SHA-256 against immutable metadata using the opened descriptor. Generation outputs also use recorded size/checksum when available.
- Added 4 dependency-free helper tests: pathname replacement after response creation still streams the original opened file; symlink rejection with `O_NOFOLLOW`; checksum mismatch rejection; directory/non-regular rejection.
- Updated the Lookbook preview recovery structural test's expected fetch expression to include the already-implemented Authorization header alongside `cache: no-store`.
- No routes, API schemas, database schema/migrations, dependencies, Provider calls, credit behavior, publication or rights behavior changed.

## Verification
- Focused backend suites: 148 passed.
- Backend full pytest: 365 passed.
- Viewer runtime JSON success coverage: 52/52.
- Baseline Viewer structural checks: 140 passed; Lookbook preview recovery checks: 19/19.
- RequestScopeGate: 7; KeyedRequestGate: 7; project lifecycle events: 4; Lookbook signed-link helper: 12 assertions passed.
- Python compileall: PASS.
- TypeScript syntax/transpilation: 10 source files + 4 declaration parses; 0 syntax errors.
- Viewer API contract: 64/64; request body contract: 15 checked, 0 findings; response contract: 52 JSON endpoints / 53 total / 29 models / 0 missing.
- Package integrity: 0 findings.

## Remaining blockers / limits
- React/Three.js semantic `tsc --noEmit` remains blocked by unavailable React/Three.js packages and type declarations. No claim of semantic typecheck success.
- Actual React/Three.js component browser E2E and browser-driven ZIP Blob download remain unverified.
- PostgreSQL runtime/multi-host integration, Android build/device tests, production object storage/secrets/RBAC, live Provider calls, credit charging, publication, rights grants and deployment remain unverified.
- The current asset preview URL endpoints remain short-lived signed capabilities suitable for `<img>`/model URL loading; they do not revalidate workspace membership on every byte request. Their TTL remains the existing bounded control. A membership-revocable preview would require a compatible authenticated streaming/fetch-to-blob client path and is deliberately not represented as completed here.
- `O_NOFOLLOW` is platform-dependent. On platforms without it, descriptor pinning and regular-file validation remain, but the final-component symlink-open guarantee is weaker. Linux verification passed.

## Next autonomous work
1. Decide and implement a compatible revocable signed-preview strategy for Asset and AssetVersion preview URLs without breaking image/model loading.
2. Add authenticated fetch-to-blob preview handling and stale URL revocation only if the UI can safely own/release object URLs across scope changes and unmount.
3. Continue semantic TypeScript and actual React/Three.js E2E only when trusted dependencies and runtime are available.

## Approval boundaries
No live Provider calls, paid APIs, credit charges, publication, rights grants, production data changes, deployment, destructive migrations, or unresolved policy decisions without explicit approval.
