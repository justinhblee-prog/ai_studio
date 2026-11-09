# BUILD-00194 Verification Report

## Build integrity

- Baseline: BUILD-00193 full handoff archive.
- Baseline SHA-256: `b86513f8812b040aaf8634e4e07aac47f83056790d1aa7d6e7202624532f1363`.
- Baseline ZIP CRC: `unzip -t` reported no errors.
- No application runtime API, dependency manifest, lockfile, or provider configuration changed.

## Test evidence

| Area | Result |
|---|---:|
| Backend pytest | 52 files; 384 passed; 0 failed |
| SQLite→PostgreSQL migration tests | 21 passed |
| Viewer dependency-free JavaScript | 17 scripts; 322 assertions passed |
| Viewer Python scripts | 7 scripts; 87 checks/tests passed |
| Viewer structural validation | 143 passed |
| Viewer API contract | 63/63 matched; 52 unique endpoints |
| Request body contract | 15 checked; 0 findings |
| Response contract | 50 JSON success contracts; 52 endpoints; 28 models; 0 missing routes/schemas |
| Python compileall | Passed |
| Package integrity | 0 findings |

All 52 backend test files have individual logs under `build194_logs/backend/`. The backend aggregate summary is `build194_logs/backend_aggregate_summary.txt`.

## New regression coverage

1. Reject boolean `row_count` even though Python treats `bool` as an `int` subclass.
2. Reject trigger inventory that does not match actual trigger definitions in the verified PostgreSQL schema.
3. Reject duplicate trigger names in the manifest.
4. Reject duplicate serial-column declarations.

## Not verified / blockers

- PostgreSQL live integration is unavailable: no server, `psql`, Docker, or psycopg 3. The migration utility's SQL execution, triggers firing on real PostgreSQL, sequence restoration, rollback and concurrency have not been demonstrated.
- Three.js resource integration test was not run because the `three` package is absent.
- React/Three.js semantic TypeScript and actual browser Viewer E2E remain blocked by unavailable dependencies. Prior WebGL2 capability smoke only proves browser WebGL primitives, not the application Viewer.
- Live provider generation was not called; no paid request was made.

## Conclusion

BUILD-00194's source-level migration preflight hardening and offline regression suite passed. This is not a declaration that PostgreSQL runtime migration, 3D Viewer integration, or live AI generation is complete.
