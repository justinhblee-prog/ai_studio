# AI CREATOR STUDIO — Current Handoff

## Baseline
- Build: BUILD-00137 (based on BUILD-00136)
- Focus: Asset restore preview invalidation and Project Product Assignment selection-state integrity

## Completed
- Asset version restore now invalidates the old selection request and aborts its controller after the restore succeeds, then clears the old signed preview URL and version history before reloading the asset and its current preview/version list.
- Project Product Assignment clears the prior project's product IDs, event history and error state immediately when a new project is selected.
- Project selection changes invalidate the prior assignment-load sequence; the effect aborts on cleanup and invalidates its sequence again, preventing delayed responses from repopulating the prior project.
- Assignment-load errors are applied only while the same project remains selected.
- Active-project catalog reconciliation invalidates and clears assignment state when the previous project is no longer available.
- Added four structural assertions for Asset restore and Project Product assignment state transitions.
- No backend routes, schemas, migrations, dependencies, public props, Provider calls, credit behavior, publication or rights behavior changed.

## Verification
- Structural validation: 126/126 PASS.
- KeyedRequestGate behavior: 7 assertions PASS.
- RequestScopeGate behavior: 7 assertions PASS.
- TypeScript syntax/transpilation: 10 `.ts`/`.tsx` source files + 2 `.d.mts` declaration parses, 0 errors. This is syntax validation only, not semantic type checking.
- Viewer API contract: 63/63.
- Request body contract: 15 checked, 0 findings.
- Response contract: 51 JSON endpoints across 52 total endpoints; 28 models; no missing routes/schemas.
- Viewer request-contract tests: 2 passed.
- API-contract-validator tests: 2 passed.
- Package integrity: 0 findings.
- Backend Python compileall: PASS.
- Backend full pytest suite: 359 passed in 17.61s.
- Clean ZIP extraction verification: see `BUILD-00137_CLEAN_EXTRACT_VERIFICATION.md`.

## Remaining blockers
- Semantic TypeScript `tsc --noEmit` and actual React/Three.js browser component E2E remain unverified because trusted React/Three.js packages and typings are unavailable in this environment.
- PostgreSQL runtime/multi-host integration, Android, production object storage/secrets/RBAC, live Provider, credit charging, publication, rights grants and deployment remain unverified.

## Next autonomous work
1. Continue auditing Product/Variant form dependencies when source Asset references are deleted or become unavailable, including create/edit form selections.
2. Review Project status transitions against Product Assignment selection and Lookbook references, ensuring no stale active-project UI survives a lifecycle change.
3. Audit Photo Draft and Output Review source/output AssetVersion preview expiration/error recovery without weakening immutable-version provenance.
4. Re-attempt semantic TypeScript and browser component E2E only when trusted dependencies are available.

## Approval boundaries
No live Provider calls, paid APIs, credit charges, publication, rights grants, production data changes, deployment, destructive migrations, or unresolved policy decisions without explicit approval.
