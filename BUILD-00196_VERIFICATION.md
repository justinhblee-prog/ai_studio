# BUILD-00196 Verification Report

## Baseline integrity

- BUILD-00195 archive SHA-256 verified before extraction.
- BUILD-00195 ZIP CRC test passed before extraction.

## Changes tested

- `tests/test_sqlite_to_postgres_migration.py`: **35 passed**.
  - Unicode JSON string separators (U+2028/U+2029/NEL/vertical tab) survive export and preflight.
  - Non-empty export destination is rejected without overwriting stale content.
  - Float bundle version is rejected.
  - Non-finite SQLite REAL values are rejected during strict JSON export.
- Backend `compileall`: passed.
- Viewer structural source validator: **143 passed**.
- Viewer package integrity validator: **0 findings**.

## Regression-suite qualification

A complete backend suite run was attempted, but the test process did not finish within the available execution window in this environment. This build therefore does not claim a fresh full-suite pass. The prior BUILD-00195 full-suite result remains **394 passed / 0 failed**; the BUILD-00196 migration-focused suite independently passes all 35 tests.

## Environment and integration blockers

- No PostgreSQL server, `psql`, Docker/Podman, psycopg 3, or pg8000 is installed.
- No React, ReactDOM, Three.js, or matching typings are installed or cached locally; npm registry name resolution is unavailable in this environment.
- Actual provider generation was not invoked. Credentials, authorized test inputs and explicit cost approval are not available.
- SHA-256 checksums detect accidental/tampered content relative to the manifest but do not authenticate who created a bundle. Untrusted bundles must not be imported without independent review.

## Artifact

Full source and evidence are included in the BUILD-00196 handoff archive. Archive CRC and SHA-256 are checked after packaging.
