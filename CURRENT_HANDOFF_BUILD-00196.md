# AI CREATOR STUDIO — Current Handoff BUILD-00196

Active continuation point: **BUILD-00196**. Baseline BUILD-00195 ZIP SHA-256 and CRC were verified before clean extraction.

## BUILD-00196 work

Improved SQLite→PostgreSQL migration bundle reliability:
- JSONL parser now treats literal LF only as a record separator, preserving valid Unicode U+2028/U+2029/NEL/vertical-tab characters inside string values.
- Export refuses non-empty destination directories, preventing stale payloads from leaking into a new bundle.
- Bundle version is strictly an integer (not bool or float).
- Export rejects non-finite numeric values rather than producing non-standard JSON.
- Four new adversarial regression tests; migration-focused suite is 35/35 passing.
- Migration guide now states SHA-256 is integrity metadata, not signed provenance/authenticity.

## Verification

- Migration-focused tests: **35 passed / 0 failed**.
- Backend compileall: passed.
- Viewer structural validation: **143 passed**.
- Viewer package integrity: **0 findings**.
- BUILD-00195 baseline full backend suite: 394 passed / 0 failed.
- BUILD-00196 full backend suite was attempted but did not finish in the available execution window; no fresh full-suite pass is claimed.
- Package ZIP CRC and SHA-256 are verified after creation.

## Known blockers

1. PostgreSQL server, psql, Docker/Podman and psycopg 3 are unavailable. Live migration, trigger behavior, constraints, sequence restoration, rollback and repeated-import refusal remain unverified.
2. PostgreSQL runtime Repository/transaction adapters are not implemented; SQLite remains the supported runtime DB.
3. React/ReactDOM/Three.js and typings are unavailable locally and absent from npm cache; actual Three.js integration, semantic typecheck and React Viewer E2E remain blocked.
4. Renderer-level WebGL recovery, GPU stress and target-device performance remain unverified.
5. Live AI provider generation was not invoked; no credentials, authorized test inputs or explicit cost approval were available.
6. Product-design OpenAPI draft differs from runtime snapshot; runtime snapshot remains authoritative for implemented behavior.
7. Bundle SHA-256 is not signed provenance/authentication; do not import untrusted bundles without independent review.

## Next priorities

1. Provision an approved disposable PostgreSQL instance plus psycopg 3; test real DDL/import, constraints, append-only triggers, sequences, rollback, checksums and repeated-import refusal.
2. Implement PostgreSQL Repository/transaction adapters only against a working disposable DB and preserve SQLite compatibility.
3. Acquire exact React/Three.js dependencies from a trusted environment and run semantic typecheck, actual Three.js integration and React Viewer E2E.
4. Reconcile design OpenAPI draft against runtime API and record explicit contract decisions.
5. Perform live AI generation only after credentials, authorized input URLs and explicit cost authorization exist.

See `BUILD-00196_RELEASE_NOTES.md`, `BUILD-00196_VERIFICATION.md`, and `build196_logs/`.

## Delivery

BUILD-00196 full handoff archive and SHA-256 sidecar are generated and locally verified. Library upload status is not asserted.
