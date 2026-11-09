# BUILD-00136 Verification Report

## Result summary

| Check | Result |
|---|---:|
| Structural source checks | 122/122 PASS |
| KeyedRequestGate behavior | 7 assertions PASS |
| RequestScopeGate behavior | 7 assertions PASS |
| TypeScript syntax/transpilation | 10 source files + 2 `.d.mts` declarations; 0 errors |
| Viewer API contract | 63/63 matched |
| Viewer request contract | 15 JSON request bodies; 0 findings |
| Viewer response contract | 51 JSON endpoints across 52 endpoints; 28 models; 0 missing routes/schemas |
| Viewer script tests | 2 passed |
| Package integrity | 0 findings |
| Python compileall | PASS |
| Backend pytest | 359 passed in 15.25s |
| Clean ZIP extraction | PASS (see `BUILD-00136_CLEAN_EXTRACT_VERIFICATION.md`) |

## Changed behavior
- Per-AssetVersion Photo preview requests use latest-request-wins semantics. A second request for the same `asset_id:version_id` supersedes the first without invalidating requests for other keys.
- Workspace/API/token scope reset invalidates pending preview responses.
- Photo Draft review, archive and manifest export share a synchronous in-flight mutation gate. Archive clears review comment and prior manifest immediately; stale responses cannot update a different scope.
- Output Review decisions and manifest export share an in-flight gate, preventing duplicate/conflicting actions from rapid repeated interaction. Scope changes reset the gate and clear old job state.

## Evidence files
- `BUILD-00136_STRUCTURAL.log`
- `BUILD-00136_KEYED_REQUEST_GATE_TEST.log`
- `BUILD-00136_SCOPE_GATE_TEST.log`
- `BUILD-00136_TYPESCRIPT_SYNTAX.log`
- `BUILD-00136_API_CONTRACT.log`
- `BUILD-00136_REQUEST_CONTRACT.log`
- `BUILD-00136_RESPONSE_CONTRACT.log`
- `BUILD-00136_VIEWER_SCRIPT_TESTS.log`
- `BUILD-00136_PACKAGE_INTEGRITY.log`
- `BUILD-00136_PYTHON_COMPILE.log`
- `BUILD-00136_BACKEND_PYTEST.log`

## Explicitly unverified
- Semantic TypeScript type checking (`tsc --noEmit`) and actual React/Three.js browser component E2E.
- PostgreSQL runtime/multi-host integration, Android, production storage/secrets/RBAC, live Provider calls, credit charging, publication, rights grants and deployment.

No live Provider calls, paid services, destructive data changes, publication, rights grants or deployment were performed.
