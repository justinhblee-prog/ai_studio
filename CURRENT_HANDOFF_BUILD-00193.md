# AI CREATOR STUDIO — Current Handoff BUILD-00193

Active continuation point: **BUILD-00193**. Baseline: BUILD-00192 full handoff ZIP; SHA-256 sidecar and ZIP CRC verified before extraction.

## This build

Hardened SQLite → PostgreSQL migration bundle import preflight and upgraded the portable bundle format to v2. Import now verifies all manifest-controlled paths, schema/data checksums, JSONL shape and row counts before importing psycopg or connecting to PostgreSQL. Validated schema and data payloads are held in memory and reused, avoiding a file-replacement race between validation and import. PostgreSQL target emptiness now includes views and sequences as well as table relations.

## Verified

- Backend: **52 test files / 380 passed / 0 failed**.
- Migration focused suite: **17 passed** including traversal, symlink, schema/data tampering, JSONL column mismatch, invalid bundle version, and preflight-before-driver tests.
- Viewer: 17 dependency-free JavaScript scripts and 7 Python scripts passed.
- Viewer structural validation: 143 checks passed.
- API contract 63/63; request contract 15 checked / 0 findings; response contract 50 JSON endpoints across 52 routes and 28 models / 0 missing.
- TypeScript syntax: 10 TS/TSX sources + 14 declaration parses / 0 syntax errors.
- Package integrity 0 findings; Python compileall passed.
- Chromium/Xvfb WebGL2 capability smoke passed context creation, triangle pixel readback, ResizeObserver, requestAnimationFrame, context loss and restoration. This is not actual React/Three.js Viewer E2E.

## Current blockers

1. No PostgreSQL server, `psql`, Docker, or psycopg 3. Live import, trigger firing, rollback, sequence restoration, and multi-worker concurrency are unverified.
2. Bundle v1 is no longer accepted; re-export all source databases as bundle v2 before importing.
3. PostgreSQL application Repository/transaction adapters remain unimplemented; SQLite remains the only supported runtime backend.
4. React/ReactDOM/Three.js and typings remain unavailable. Semantic TypeScript, actual Three.js integration, React Viewer E2E, renderer-level context recovery, GPU stress and target-device performance remain unverified.
5. Live AI generation requires explicit cost authorization, credentials and authorized input URLs. No provider request was made.
6. Older design OpenAPI draft reconciliation remains open; active Viewer API contract remains 63/63.

## Next priorities

1. Provision a disposable PostgreSQL service and psycopg 3, export fresh v2 bundles, then verify import, constraints, triggers, sequences, rollback, checksums and repeated import safety.
2. Add live PostgreSQL integration tests and fail the gate on any schema/data/trigger mismatch.
3. Continue PostgreSQL Repository/transaction adapters and multi-worker claim tests only after the live database environment exists.
4. Acquire exact declared React/Three dependencies from a legitimate network-enabled or pre-populated environment; run semantic typecheck and actual Three.js integration.
5. Mount the real React Viewer in Chromium and test authenticated GLTF loading, replacement, unmount cleanup, renderer context restoration and GPU/device performance.
6. Reconcile the older design OpenAPI draft with the active API surface.
7. Run live AI generation only with explicit cost approval and valid authorized inputs.

See `BUILD-00193_RELEASE_NOTES.md`, `BUILD-00193_VERIFICATION.md`, and `build193_logs/`.

## Delivery

BUILD-00193 full handoff ZIP and SHA-256 sidecar are locally generated and integrity-verified. Library upload status is not asserted in this handoff.
