# BUILD-00193 Release Notes

## SQLite → PostgreSQL migration bundle hardening

- Upgraded the migration bundle format to version 2. Existing version-1 bundles are explicitly rejected and must be re-exported.
- Added a SHA-256 digest for `schema.postgresql.sql` in the manifest.
- Added a complete import preflight before importing psycopg or opening a database connection: manifest shape/counts, strict table and column identifiers, duplicate names/files, serial-column membership, exact `data/<table>.jsonl` paths, path traversal/absolute path/backslash rejection, symlink rejection, schema/data checksums, UTF-8/JSONL parsing, exact JSON column sets, binary base64 payload validation, per-table row counts, and total row count.
- Schema SQL and validated JSONL payloads are pinned in memory and reused during import, closing the validation/use file replacement window.
- The target-schema emptiness guard now rejects existing tables, partitioned tables, views, materialized views, foreign tables, and sequences rather than checking base tables only.
- Unsupported SQLite trigger/view/virtual-table semantics remain fail-closed. No PostgreSQL runtime adapter or live migration claim is made.

## Tests

- Added six adversarial/preflight regression cases over the prior 11 migration tests; final focused migration suite: **17 passed**.
- Full backend suite: **52 test files / 380 passed / 0 failed**. Two orchestration calls exceeded the outer command window; all affected and remaining test files were rerun in bounded independent groups. Per-file evidence is retained in `build193_logs/backend*` and aggregate summary.
- Viewer: 17 dependency-free JavaScript test scripts passed; 7 Python test scripts passed.
- Viewer structural validation: 143 checks passed.
- API contract: 63/63; request contract: 15 JSON-body calls checked, 0 findings; response contract: 50 JSON endpoints across 52 routes, 28 models, 0 missing routes/schemas.
- TypeScript syntax/transpile: 10 TS/TSX source files + 14 declaration files, 0 syntax errors.
- Python compileall and package integrity validation passed; package integrity findings: 0.
- Chromium/Xvfb browser capability smoke passed WebGL2 context, triangle pixel readback, ResizeObserver, animation frame, context loss and restoration. This is not React/Three.js Viewer E2E.

## Unverified / blocked

- No PostgreSQL server, `psql`, Docker, or psycopg 3 is available in this environment. Live import, trigger firing, sequence restoration, rollback and multi-worker contention remain unverified.
- `three` is unavailable; real Three.js integration test is blocked. React/ReactDOM and typings are also missing, so semantic TypeScript checking and actual React Viewer E2E remain blocked. TypeScript syntax validation is not a semantic typecheck.
- Live AI generation was not requested or authorized; no provider call or charge was made.

No dependency versions, lockfiles, or application runtime dependencies were changed. Only the migration utility, its tests, and migration documentation were updated.
