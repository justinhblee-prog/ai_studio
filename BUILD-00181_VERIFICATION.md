# BUILD-00181 Verification Report

## Provenance
BUILD-00180 ZIP SHA-256 and ZIP CRC checks passed before extraction. This build adds a backend pytest sharding utility and fresh validation evidence; no application runtime code was modified.

## Results
| Check | Fresh result | Status |
|---|---:|---|
| Backend test collection | 367 tests collected | PASS |
| Backend `test_api.py` | 70 passed | PASS |
| Backend `test_assets_api.py` | 69 passed | PASS |
| Backend remaining test files | 228 passed | PASS |
| Backend total | 367/367 across 3 isolated invocations | PASS |
| New shard-runner smoke | 3 files / 17 tests; 0 failures or timeouts | PASS |
| Viewer dependency-free JS scripts | 17 passed | PASS |
| JS emitted assertion summaries | 295 | PASS |
| Viewer Python scripts | 7 passed | PASS |
| TypeScript syntax/transpile | 10 source + 14 declarations; 0 syntax errors | PASS (syntax only) |
| API contract | 63/63; 0 findings | PASS |
| Request contract | 15 JSON calls; 0 findings | PASS |
| Response contract | 50 JSON endpoints / 52 routes; 0 missing | PASS |
| Package integrity | 0 findings | PASS |
| Viewer and backend Python compileall | completed | PASS |
| Three.js resource integration | `three` package absent | BLOCKED |
| Semantic TypeScript check | required dependencies absent | BLOCKED |
| Browser/WebGL2/GPU/device acceptance | not executed in this environment | NOT VERIFIED |
| Final ZIP CRC + SHA-256 | passed | PASS |

## Backend full-suite execution detail
The single-process full-suite invocation exceeded the execution window. Test collection was independently confirmed at 367. To obtain a complete fresh result, the suite was run in three non-overlapping invocations:
- `tests/test_api.py`: 70 passed.
- `tests/test_assets_api.py`: 69 passed.
- All other test files: 228 passed.

The new `scripts/run_backend_test_shards.py` was smoke-tested on three test files (17 tests total). A full 52-file run through that new wrapper was not executed in one command during this build.

## Evidence files
- `build181_logs/backend_api_tests.log`
- `build181_logs/backend_assets_tests.log`
- `build181_logs/backend_remaining_tests.log`
- `build181_logs/backend_collect.log`
- `build181_logs/backend_runner_smoke.log`
- `build181_logs/backend_runner_smoke/`
- `build181_logs/viewer_js_tests.log`
- `build181_logs/viewer_python_tests.log`
- `build181_logs/typescript_syntax.log`
- `build181_logs/api_contract.log`
- `build181_logs/request_contract.log`
- `build181_logs/response_contract.log`
- `build181_logs/package_integrity.log`
- `build181_logs/viewer_compileall.log`
- `build181_logs/backend_compileall.log`

## Interpretation
All 367 backend tests passed when divided into non-overlapping groups. The monolithic execution timeout is an execution-window limitation, not a reported test failure. Actual Three.js integration, semantic TypeScript checks, browser E2E, real renderer recovery, GPU stress, and target-device performance remain unverified.
