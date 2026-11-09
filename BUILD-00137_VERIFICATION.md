# BUILD-00137 Verification Report

## Result summary

| Check | Result |
|---|---:|
| Structural source checks | 126/126 PASS |
| KeyedRequestGate behavior | 7 assertions PASS |
| RequestScopeGate behavior | 7 assertions PASS |
| TypeScript syntax/transpilation | 10 `.ts`/`.tsx` files + 2 `.d.mts` declarations; 0 errors |
| Viewer API contract | 63/63 matched |
| Viewer request contract | 15 JSON request bodies; 0 findings |
| Viewer response contract | 51 JSON endpoints across 52 endpoints; 28 models; 0 missing routes/schemas |
| Viewer request-contract tests | 2 passed |
| API-contract-validator tests | 2 passed |
| Package integrity | 0 findings |
| Python compileall | PASS |
| Backend pytest | 359 passed in 17.61s |
| Clean ZIP extraction | PASS (see `BUILD-00137_CLEAN_EXTRACT_VERIFICATION.md`) |

## Changed behavior
- Successful AssetVersion restore invalidates any prior selection request and removes the previous signed preview URL/version list before loading the restored current version.
- Changing the selected project clears prior assignment product IDs and event history immediately; pending prior-project reads are aborted/invalidated, and stale failures are ignored.
- Project catalog reconciliation clears assignment state when the selected project disappears from the refreshed active-project catalog.

## Evidence files
- `BUILD-00137_STRUCTURAL.log`
- `BUILD-00137_KEYED_REQUEST_GATE_TEST.log`
- `BUILD-00137_SCOPE_GATE_TEST.log`
- `BUILD-00137_TYPESCRIPT_SYNTAX.log`
- `BUILD-00137_API_CONTRACT.log`
- `BUILD-00137_REQUEST_CONTRACT.log`
- `BUILD-00137_RESPONSE_CONTRACT.log`
- `BUILD-00137_VIEWER_REQUEST_TESTS.log`
- `BUILD-00137_API_VALIDATOR_TESTS.log`
- `BUILD-00137_PACKAGE_INTEGRITY.log`
- `BUILD-00137_PYTHON_COMPILE.log`
- `BUILD-00137_BACKEND_PYTEST.log`

## Explicitly unverified
- Semantic TypeScript type checking (`tsc --noEmit`) and actual React/Three.js browser component E2E.
- PostgreSQL runtime/multi-host integration, Android, production storage/secrets/RBAC, live Provider calls, credit charging, publication, rights grants and deployment.

No live Provider calls, paid services, destructive data changes, publication, rights grants or deployment were performed.
