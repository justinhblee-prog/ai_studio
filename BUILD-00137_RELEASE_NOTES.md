# BUILD-00137 — Asset Restore & Project Assignment State Integrity

## Implemented
- Asset version restore now invalidates the previously selected preview request and clears the old signed preview URL and version history after the restore succeeds, before refreshing the asset list and hydrating the new current version.
- Project Product Assignment now clears the previous project's selected product IDs and event history immediately when project selection changes, before the new project's assignment/history reads complete.
- Project selection changes invalidate prior assignment hydration sequence IDs; effect cleanup aborts the read and invalidates its sequence, and stale errors are ignored unless the same project remains selected.
- Catalog reconciliation invalidates and clears assignment state when the previously selected project is no longer present in the active project list.
- Structural validation expanded from 122 to 126 checks.

## Compatibility and safety
- No backend routes, schemas, migrations, database behavior, public component props, dependency versions, Provider behavior, credit charging, publication, or rights behavior changed.
- Asset version restore and project assignment remain existing API operations. This change only improves client-side state consistency and stale-response rejection.
- No destructive data changes or external service calls were performed.

## Verification
- Structural source checks: 126/126 passed.
- KeyedRequestGate behavior: 7 assertions passed.
- RequestScopeGate behavior: 7 assertions passed.
- TypeScript syntax/transpilation: 10 `.ts`/`.tsx` source files + 2 `.d.mts` declarations, 0 errors.
- Viewer API contract: 63/63 matched.
- Viewer request contract: 15 JSON request bodies, 0 findings.
- Viewer response contract: 51 JSON endpoints across 52 endpoints; 28 models; 0 missing routes/schemas.
- Viewer request-contract tests: 2 passed; API-contract-validator tests: 2 passed.
- Package integrity: 0 findings.
- Python compileall: passed.
- Backend full pytest: 359 passed in 17.61s.
- Clean ZIP extraction verification: see `BUILD-00137_CLEAN_EXTRACT_VERIFICATION.md`.

## Known limitations
- Semantic TypeScript `tsc --noEmit` and actual React/Three.js browser component E2E remain unverified because trusted React/Three.js packages and typings are unavailable in this environment.
- PostgreSQL runtime/multi-host integration, Android, production object storage/secrets/RBAC, live Provider calls, credit charging, publication, rights grants, and deployment remain unverified.
