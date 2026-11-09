# BUILD-00200 Verification Report

## Baseline integrity

- BUILD-00199 ZIP SHA-256: `7a451c76f88e446479affb86ea973dc32a12043484dc6df229440d69471b26df`.
- BUILD-00199 ZIP CRC test: passed before extraction.

## Backend

- Full backend suite: **428 passed / 0 failed** (28.20 seconds).
- Focused Outbox/Poll repository tests: **29 passed**.
- Python compileall for backend app/scripts/tests: passed.

## Viewer offline checks

- Dependency-free JavaScript scripts: **17 passed**. The actual Three.js package integration script was excluded because the `three` package is not installed.
- Python viewer scripts: **7 passed**.
- Source structural validation: **143 passed**.
- API contract: **63/63 calls matched**, no missing/query mismatch/unresolved dynamic segments.
- Request contract: **15 JSON body calls checked, 0 findings**.
- Response contract: **50 JSON endpoint contracts across 52 endpoints and 28 models; 0 missing routes/schemas**.
- Package integrity: **0 findings**.
- TypeScript syntax/transpile: **10 source files + 14 declaration files parsed, 0 syntax errors**. This is not semantic `tsc` typechecking.

## Browser capability probe

- Chromium was found, but this run could not create a WebGL2 context (`WebGL2 context unavailable`). The probe timed out waiting for WebGL context restoration and is recorded as **blocked**, not passed. This is a browser capability probe only and does not load the React/Three.js Viewer.

## Not run / not claimed

- No PostgreSQL server, `psql`, Docker/Podman or psycopg driver was available. Live PostgreSQL import, rollback, trigger, constraint, sequence and multi-instance tests remain deferred.
- PostgreSQL runtime Repository/transaction adapters remain unimplemented; SQLite remains the supported runtime database.
- React/ReactDOM/Three.js packages and typings remain unavailable. Semantic TypeScript checking and React Viewer E2E remain deferred.
- Live AI generation was not invoked; credentials, authorized test inputs and explicit cost authorization are not configured.
- No external integration test was attempted, consistent with the project's current decision to defer external testing.

## Logs

See `build200_logs/` for backend compileall, focused and full suite logs, Viewer JS/Python tests, API/request/response contract audits, structural checks, TypeScript syntax and browser capability probe.
