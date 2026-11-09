# BUILD-00193 Verification Report

## Baseline integrity

- Baseline: `AI_CREATOR_STUDIO_FULL_HANDOFF_BUILD-00192.zip`.
- Baseline SHA-256 sidecar verified before extraction.
- `unzip -t` completed with no compressed-data errors.

## Implemented and tested

| Area | Result |
|---|---:|
| Backend test files | 52 / 52 passed |
| Backend tests | 380 passed, 0 failed |
| Migration preflight focused tests | 17 passed |
| Viewer JavaScript scripts | 17 passed |
| Viewer Python scripts | 7 passed |
| Viewer structural checks | 143 passed |
| API contract | 63 / 63 |
| Request contract | 15 checked, 0 findings |
| Response contract | 50 JSON endpoints / 52 routes / 28 models; 0 missing |
| TypeScript syntax/transpile | 10 source + 14 declarations; 0 syntax errors |
| Python compileall | Passed |
| Package integrity | 0 findings |
| Chromium/Xvfb WebGL2 capability smoke | Passed |

Backend shard orchestration exceeded the outer execution window twice. This did not produce a failing test result: all 52 test files have independent passing logs. `build193_logs/backend_aggregate_summary.txt` records each file and count. The final migration test count is 17 and is reflected in the aggregate total.

## Migration bundle v2 safeguards

- `schema_sha256` validates generated PostgreSQL schema DDL.
- Manifest shape, table/column identifiers, duplicate entries, row counts and serial-column membership are validated.
- Data paths must be exactly `data/<table>.jsonl`; traversal, absolute paths, backslashes and symlinks are rejected.
- Schema/data digests, UTF-8, JSONL syntax, exact column sets, binary payload encoding, per-table row counts and aggregate row count are checked before psycopg import or DB connection.
- Validated schema/data bytes are retained in memory and reused during import.
- Existing PostgreSQL relations/sequences block import.
- Bundle v1 is intentionally rejected; export a fresh v2 bundle.

## Environment blockers

- PostgreSQL live integration: blocked; no PostgreSQL server, `psql`, Docker or psycopg 3 present.
- Three.js resource integration: blocked by missing `three` package.
- TypeScript semantic check: blocked by missing React/ReactDOM/Three.js packages and type declarations. The syntax/transpile pass does not establish semantic correctness.
- Actual React/Three.js browser E2E, renderer-level context recovery, GPU stress and target-device performance remain unverified. Browser smoke only verifies Chromium's WebGL2 capability.
- Live AI provider generation remains unverified and was not attempted.

## Evidence

All per-test logs and validator outputs are under `build193_logs/`. No dependency manifest or lockfile was changed.
