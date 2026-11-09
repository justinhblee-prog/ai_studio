# AI CREATOR STUDIO — Current Handoff

## Baseline
- Build: BUILD-00142 (based on BUILD-00141)
- Focus: Private Lookbook ZIP download authorization and cleanup observability

## Completed
- Signed Lookbook ZIP download URLs remain short-lived and HMAC-validated, and now additionally require a currently valid Bearer token and current membership in the export's workspace.
- Download authorization rechecks current workspace role at use time (`owner`, `admin`, `editor`, `viewer`). A removed member cannot reuse a previously issued signed URL; a current viewer can still download.
- Viewer ZIP download fetch now sends the same Authorization header used by the workspace API.
- Download rejects non-regular filesystem entries using `lstat`; symlink entries are rejected even when their target bytes match the recorded package.
- Existing package SHA-256 and size verification, expiry checks, private/no-store response headers, and append-only export audit remain intact.
- Expired package cleanup JSON output now includes mode, configured limit, candidate count, detailed outcome counters, partial-failure flag, audit-retention assertion, elapsed milliseconds, and completion epoch.
- Cleanup remains dry-run by default; `--apply` is still required for file deletion. Per-file failures do not stop subsequent candidates; nonzero exit indicates partial operational failure.
- Runtime OpenAPI snapshot refreshed for the newly authenticated download route.
- Added regression tests for unauthenticated access, active viewer access, revoked membership, symlink rejection, dry-run operational output, partial-failure output, and nonzero exit behavior.

## Verification
- Backend full pytest: 361 passed.
- Python compileall: PASS.
- Viewer structural source checks: 140 passed.
- Lookbook signed-link and stale-preview helper assertions: 12 passed.
- KeyedRequestGate: 7 passed.
- RequestScopeGate: 7 passed.
- Project lifecycle event helper: 4 passed.
- TypeScript syntax/transpilation: 10 `.ts`/`.tsx` sources + 4 `.d.mts` declarations; 0 errors.
- Viewer API contract: 64/64 matched; 0 missing, 0 query mismatches, 0 unresolved dynamic segments.
- Request body contract: 15 checked; 0 findings.
- Response contract: 52 JSON endpoints across 53 method/path endpoints; 29 models; 0 missing routes/schemas.
- Viewer request-contract tests: 2 passed.
- Package integrity: 0 findings.
- Browser capability smoke under Xvfb: PASS (Chromium WebGL2, shader/triangle readback, ResizeObserver, animation frame); this is not React/Three.js component E2E.
- Semantic `tsc --noEmit`: BLOCKED by unavailable `react`, `react/jsx-runtime`, and React type declarations; cascading JSX/implicit-any diagnostics are not treated as source semantic findings.

## Remaining blockers
- Actual React/Three.js component browser E2E and browser-driven ZIP Blob download are not verified.
- PostgreSQL runtime/multi-host integration, Android build/device testing, production object storage/secrets/RBAC, live Provider calls, credit charging, publication, rights grants, and deployment remain unverified.
- `FileResponse` is still path-based after a preflight `lstat` and checksum; a highly privileged local filesystem actor racing the check/open window is outside this build's tested threat model. Production object storage or descriptor-based serving should be considered before deployment.

## Next autonomous work
1. Review whether all private asset/output download routes have equivalent current-membership checks and whether signed-link lifetime/revocation behavior is consistent.
2. Add a race-safe file-descriptor serving path or storage abstraction for private ZIP downloads, with cross-platform tests where supported.
3. Continue retrying semantic TypeScript and actual React/Three.js component E2E only when trusted dependencies and browser runtime are available.

## Approval boundaries
No live Provider calls, paid APIs, credit charges, publication, rights grants, production data changes, deployment, destructive migrations, or unresolved policy decisions without explicit approval.
