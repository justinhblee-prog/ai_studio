# AI CREATOR STUDIO — BUILD-00195 Release Notes

Date: 2026-11-05  
Baseline: BUILD-00194 full handoff ZIP (SHA-256 and ZIP CRC verified before extraction)

## Summary

Hardened SQLite→PostgreSQL migration bundle v2 preflight validation against ambiguous JSON, misleading trigger inventory, and unmanifested bundle content. No application runtime API, dependency manifest, lockfile, or provider configuration was changed.

## Source changes

- `ai_creator_studio_backend_starter/scripts/sqlite_to_postgres.py`
  - Added strict JSON decoding with duplicate-object-key rejection and rejection of non-standard numeric constants (`NaN`, `Infinity`).
  - Hardened binary payload decoding: base64 field must be a string and malformed base64 is rejected explicitly.
  - Trigger inventory is now derived from SQL statement boundaries, not a broad regex over the complete schema text; trigger-like text inside PL/pgSQL bodies, SQL literals, and comments is not counted as a trigger declaration.
  - Duplicate trigger declarations are rejected when compared with manifest inventory.
  - Enforced a closed bundle layout: only `manifest.json`, `schema.postgresql.sql`, and the manifest-listed `data/*.jsonl` files are allowed; unexpected files, empty directories, nested directories, and symlinked directories/files are rejected.
- `ai_creator_studio_backend_starter/tests/test_sqlite_to_postgres_migration.py`
  - Added 10 regression tests covering function-body/literal/comment trigger spoofing, duplicate trigger declarations, unmanifested files/directories, duplicate JSON keys, non-standard JSON numbers, malformed binary payloads, and symlinked data-directory rejection.

## Compatibility and scope

- Bundle format remains v2; bundle v1 remains unsupported.
- Validation remains offline and runs before PostgreSQL driver import or database connection.
- Existing exporter-generated bundles continue to use the same layout and manifest format.
- SHA-256 digests detect accidental or post-export content changes relative to the manifest; they do **not** authenticate the bundle's origin or provide a digital signature.

## Verification

- Backend: 52 test files, **394 passed, 0 failed**.
- Migration-focused suite: **31 passed**.
- Viewer dependency-free JavaScript: **17 scripts / 322 assertions passed**; one optional Three.js integration script is **blocked**, not failed, because the declared `three@^0.180.0` package is not installed or cached.
- Viewer Python scripts: **12 passed**.
- Viewer structural source validation: **143 passed**.
- Viewer TypeScript syntax/transpile: **10 source files + 14 declaration parses, 0 errors**.
- Viewer API contract: **63/63 matched**.
- Viewer request contract: **15 JSON body calls checked, 0 findings**.
- Viewer response contract: **50 JSON success contracts across 52 endpoints and 28 models; 0 missing routes/schemas**.
- Viewer package integrity: **0 findings**.
- Backend and Viewer Python compileall: passed.
- Xvfb + Chromium WebGL2 capability probe: passed context creation, triangle pixel readback, resize observation, animation frame, context loss and restoration. This is a browser capability smoke test, not the application React/Three.js Viewer E2E.
- ZIP CRC and SHA-256: verified.

## Remaining blockers / not claimed as complete

- No PostgreSQL server, `psql`, Docker/Podman, or psycopg 3 is available in this environment. Live import, trigger execution, sequence restoration, rollback, constraints, and repeated-import safety remain unverified.
- PostgreSQL application Repository/transaction adapters remain unimplemented; SQLite remains the supported runtime DB.
- React/ReactDOM/Three.js and type packages are unavailable locally and absent from npm cache. Semantic TypeScript typecheck and the actual Three.js resource integration test remain blocked.
- React Viewer browser E2E, authenticated real GLTF rendering, renderer-level WebGL recovery, GPU stress and target-device performance remain unverified. The WebGL2 probe does not substitute for these.
- Live AI provider generation was not invoked; no provider credentials/test input or cost authorization was supplied, and no charge was made.
- Product-design OpenAPI draft still differs from the runtime API snapshot; runtime snapshot remains authoritative for implemented behavior pending explicit contract decisions.

## Artifacts

- `BUILD-00195_VERIFICATION.md`
- `CURRENT_HANDOFF_BUILD-00195.md`
- `CURRENT_HANDOFF.md`
- `build195_logs/`
