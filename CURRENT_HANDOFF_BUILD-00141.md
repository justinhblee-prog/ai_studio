# AI CREATOR STUDIO — Current Handoff

## Baseline
- Build: BUILD-00141 (based on BUILD-00140)
- Focus: Lookbook package export history visibility and assembly page-order snapshot integrity

## Completed
- Lookbook assembly hydration now loads package export history alongside Photo runs, attached outputs, and assembly review state. History is isolated to the selected draft and cleared on workspace/draft scope changes.
- The workspace displays every recorded private ZIP export with export ID, creation time, page count, package size, package SHA-256, approved assembly snapshot SHA-256, retention expiry, and observed file status.
- Backend history status distinguishes `available`, `expired`, and `missing`. File presence is inspected using `lstat` and only a regular file is considered available. Invalid storage keys, symlinks, missing files, and non-regular entries are never followed or exposed. Reading history does not delete, repair, or mutate the immutable export audit record.
- After successful ZIP creation, the workspace refreshes export history so the new append-only record appears immediately.
- Added regression coverage that simulates out-of-band page-order corruption after assembly submission and proves the approved review snapshot changes to `integrity_error`; restoring the original order restores `in_review`. This verifies page order is part of the canonical snapshot hash, together with exact AssetVersion identity.
- Added package-history file-state integration coverage: moving the ZIP file out of the private export directory surfaces `missing`, restoring it surfaces `available`, and the audit row remains present.
- Existing immutability policy is unchanged: output rows cannot be edited or reordered in place; after review submission the sequence remains frozen. A changed sequence requires a new Lookbook draft.
- No new API route, DB schema, migration, dependency, Provider, credit, publication, or rights behavior was introduced. The existing export-history GET endpoint is now consumed by the Viewer, so its documented Viewer contract coverage increases by one endpoint.

## Verification
- Backend full pytest: 359 passed.
- Python compileall: PASS.
- Lookbook preview/download/history structural checks: 19/19 PASS.
- Lookbook signed-link and stale-preview helper tests: 12 assertions PASS.
- KeyedRequestGate: 7 assertions PASS.
- RequestScopeGate: 7 assertions PASS.
- Project lifecycle event helper: 4 assertions PASS.
- TypeScript syntax/transpilation: 10 `.ts`/`.tsx` sources + 4 `.d.mts` declarations; 0 errors. This is syntax/transpilation only.
- Viewer API contract: 64/64 calls matched; 0 missing, 0 query mismatches, 0 unresolved dynamic segments.
- Request body contract: 15 checked; 0 findings.
- Response contract: 52 JSON endpoints across 53 method/path endpoints; 29 models; 0 missing routes/schemas; 0 unresolved dynamic segments.
- Viewer request-contract tests: 2 passed.
- Package integrity: 0 findings.
- Semantic `tsc --noEmit`: BLOCKED by unavailable `react`, `react/jsx-runtime`, and React type declarations; cascading JSX/implicit-any diagnostics are not treated as source semantic findings.
- Actual React/Three.js component browser E2E remains unverified.

## Remaining blockers
- Trusted React/ReactDOM/Three.js packages and typings are not installed; network package registry access was unavailable in prior checks. Semantic TypeScript and actual component browser E2E remain unverified.
- Browser-driven signed preview expiry/retry and real ZIP Blob download are not exercised in React component E2E.
- PostgreSQL runtime/multi-host integration, Android build/device testing, production object storage/secrets/RBAC, live Provider calls, credit charging, publication, rights grants, and deployment remain unverified.

## Next autonomous work
1. Audit internal export download authorization and file-serving path behavior against workspace membership changes, without weakening the current private signed-link checks.
2. Review cleanup job observability (dry-run/apply counts, partial failures, expired audit history) and add operational tests without changing append-only audit semantics.
3. Re-attempt semantic TypeScript and real browser component E2E only when trusted dependencies are available.

## Approval boundaries
No live Provider calls, paid APIs, credit charges, publication, rights grants, production data changes, deployment, destructive migrations, or unresolved policy decisions without explicit approval.
