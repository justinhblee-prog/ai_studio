# AI CREATOR STUDIO — Current Handoff BUILD-00194

Active continuation point: **BUILD-00194**. Baseline: BUILD-00193 full handoff ZIP; SHA-256 and ZIP CRC verified before extraction.

## This build

Hardened SQLite→PostgreSQL bundle v2 preflight metadata validation. It now validates non-boolean integer table/row counts, non-empty source database metadata, trigger inventory structure/count/uniqueness, trigger names against the checksum-verified schema, and unique valid serial-column declarations. All validation happens before importing psycopg or connecting to PostgreSQL.

## Verified

- Backend: **52 test files / 384 passed / 0 failed**.
- Migration-focused suite: **21 passed**, including four new adversarial manifest tests.
- Viewer: 17 dependency-free JavaScript scripts / 322 assertions passed; 7 Python scripts / 87 checks/tests passed.
- Viewer structural validation: 143 checks passed.
- API contract 63/63; request contract 15 checked / 0 findings; response contract 50 JSON endpoints across 52 routes and 28 models / 0 missing.
- Python compileall passed; package integrity 0 findings.

## Current blockers

1. No PostgreSQL server, `psql`, Docker, or psycopg 3. Live import, trigger firing, rollback, sequence restoration, and multi-worker concurrency are unverified.
2. Bundle v1 is no longer accepted; re-export source databases as bundle v2 before importing.
3. PostgreSQL application Repository/transaction adapters remain unimplemented; SQLite remains the only supported runtime backend.
4. React/ReactDOM/Three.js and typings remain unavailable. Semantic TypeScript, actual Three.js integration, React Viewer E2E, renderer-level context recovery, GPU stress and target-device performance remain unverified.
5. Live AI generation requires explicit cost authorization, credentials and authorized input URLs. No provider request was made.
6. Product-design OpenAPI draft still intentionally differs from current runtime behavior; runtime snapshot is authoritative for implemented behavior pending explicit contract decisions.

## Next priorities

1. Provision a disposable PostgreSQL service and psycopg 3; test v2 import, constraints, append-only triggers, sequences, rollback, checksums and repeated-import safety.
2. Add PostgreSQL integration tests and fail the migration gate on schema/data/trigger mismatch.
3. Continue PostgreSQL Repository/transaction adapters and multi-worker claim tests only after the live DB environment exists.
4. Acquire exact declared React/Three dependencies from a legitimate network-enabled or pre-populated environment; run semantic typecheck and actual Three.js integration.
5. Mount the real React Viewer in Chromium and test authenticated GLTF loading, replacement, unmount cleanup, renderer context restoration and GPU/device performance.
6. Reconcile the older design OpenAPI draft with active API and explicitly record accepted/deferred contract differences.
7. Run live AI generation only with explicit cost approval and valid authorized inputs.

See `BUILD-00194_RELEASE_NOTES.md`, `BUILD-00194_VERIFICATION.md`, and `build194_logs/`.

## Delivery

BUILD-00194 full handoff ZIP and SHA-256 sidecar are generated and locally integrity-verified. Library upload status is not asserted.
