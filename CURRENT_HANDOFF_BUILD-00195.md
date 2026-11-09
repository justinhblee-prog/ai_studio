# AI CREATOR STUDIO — Current Handoff BUILD-00195

Active continuation point: **BUILD-00195**. Baseline: BUILD-00194 full handoff ZIP; SHA-256 and ZIP CRC verified before extraction.

## This build

Hardened SQLite→PostgreSQL bundle v2 preflight validation. JSON decoding rejects duplicate keys and non-standard numeric constants; binary wrappers require valid base64 strings; trigger inventory parsing is anchored to SQL statement boundaries; and the bundle must have an exact, closed file/directory layout. Added adversarial tests for trigger-text spoofing, duplicate JSON keys, malformed binary values, unmanifested content, and symlinked data directories.

No application runtime API, dependency manifest, lockfile, or provider configuration changed.

## Verified

- Backend: **52 test files / 394 passed / 0 failed**.
- Migration-focused suite: **31 passed**.
- Viewer dependency-free JavaScript: **17 scripts / 322 assertions passed**; one Three.js integration script remains blocked by missing dependency.
- Viewer Python scripts: **12 passed**.
- Viewer structural validation: **143 passed**.
- TypeScript syntax/transpile: **10 source files + 14 declaration parses, 0 errors**.
- API contract: **63/63 matched**; request contract **15 checked / 0 findings**; response contract **50 JSON contracts across 52 endpoints and 28 models / 0 missing**.
- Viewer package integrity: **0 findings**; backend and Viewer Python compileall passed.
- Xvfb + Chromium WebGL2 capability smoke passed, including context loss/restoration. It is not application Viewer E2E.
- Full handoff ZIP CRC and SHA-256 verified.

## Current blockers / truthful scope

1. No PostgreSQL server, `psql`, Docker/Podman, or psycopg 3 is available. Live migration, triggers, constraints, rollback, sequences, and repeated-import safety are unverified.
2. PostgreSQL application Repository/transaction adapters remain unimplemented; SQLite remains the supported runtime database.
3. React/ReactDOM/Three.js and typings are unavailable locally and absent from npm cache. Semantic TypeScript typecheck and actual Three.js integration remain blocked.
4. React Viewer E2E, authenticated actual GLTF rendering, renderer-level WebGL recovery, GPU stress, and target-device performance remain unverified.
5. Live AI provider generation was not invoked; no credentials, authorized test inputs, or cost approval were present.
6. Product-design OpenAPI draft still differs from runtime snapshot; runtime snapshot remains authoritative for implemented behavior.
7. Bundle SHA-256 values are integrity checks, not signed provenance/authenticity.

## Next priorities

1. Obtain an approved disposable PostgreSQL environment and psycopg 3; verify import, constraints, append-only triggers, sequence restoration, rollback, checksums, and repeated-import refusal.
2. Implement PostgreSQL Repository/transaction adapters only with a working disposable database and preserve SQLite compatibility.
3. Acquire exact React/Three.js dependencies from a trusted network-enabled or pre-populated environment; run semantic typecheck and Three.js integration.
4. Run React Viewer E2E in Chromium, including authenticated GLTF loading, replacement/unmount cleanup, renderer context restoration, and GPU/device acceptance.
5. Reconcile design OpenAPI draft with runtime API and record explicit contract decisions.
6. Execute live AI generation only after explicit cost authorization and valid credentials/authorized test inputs.

See `BUILD-00195_RELEASE_NOTES.md`, `BUILD-00195_VERIFICATION.md`, and `build195_logs/`.

## Delivery

BUILD-00195 full handoff ZIP and SHA-256 sidecar are generated and locally integrity-verified. Library upload status is not asserted.
