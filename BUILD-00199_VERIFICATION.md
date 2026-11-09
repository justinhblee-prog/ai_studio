# BUILD-00199 Verification Report

## Baseline integrity

- BUILD-00198 archive SHA-256 verified before extraction.
- BUILD-00198 ZIP CRC test passed.

## Backend

- Full suite: **405 passed / 0 failed** (19.29 seconds).
- Focused OpenAPI audit tests: **4 passed / 0 failed**.
- `compileall` for app/scripts/tests: passed.
- Runtime OpenAPI snapshot `--check`: passed.

## API reconciliation

- Design draft operations: **15**.
- Runtime operations: **101**.
- Structural drift among matched operations: **12**.
- Design operations missing at runtime: **3**.
- Runtime-only operations: **89**.
- Normalized path collisions: **0**.
- The audit is structural only; it does not prove semantic equivalence, authorization correctness, or live payload behavior. Runtime-only operations are not automatically public API.

## Viewer offline checks

- 17 dependency-free JavaScript test scripts passed; the Three.js package integration script was excluded because the `three` dependency is unavailable.
- Seven Python viewer test scripts passed.
- Viewer source structural validation: **143 passed**.
- TypeScript syntax/transpile: 10 TS source files + 14 declaration files parsed, 0 syntax errors; this is not semantic `tsc` typechecking.
- API calls: 63/63 matched. Request contract: 15 JSON calls, 0 findings. Response contract: 50 JSON endpoint contracts across 52 endpoints and 28 models, 0 missing routes/schemas. Package integrity: 0 findings.

## Blockers / not claimed

- PostgreSQL server, `psql`, Docker/Podman and psycopg 3 remain unavailable. Live migration, rollback, trigger, constraint, sequence and repeated-import behavior remain unverified.
- PostgreSQL runtime Repository/transaction adapters remain unimplemented; SQLite remains the supported runtime database.
- React/ReactDOM/Three.js and typings remain unavailable. Actual Three.js integration, semantic TypeScript checking and React Viewer E2E remain unverified.
- Live AI generation was not invoked; credentials, authorized test inputs and explicit cost authorization are absent.
- SHA-256 is integrity metadata, not signed provenance or authentication.

## Logs

See `build199_logs/` for test output, API audit JSON and command logs.
