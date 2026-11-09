# BUILD-00195 Verification Report

## Baseline integrity

- Input archive: `AI_CREATOR_STUDIO_FULL_HANDOFF_BUILD-00194.zip`.
- Baseline SHA-256 sidecar verified before extraction.
- `unzip -tq` reported no compressed-data errors.

## Test evidence

| Area | Result |
|---|---:|
| Backend pytest | 52 test files; 394 passed; 0 failed |
| SQLite→PostgreSQL migration suite | 31 passed |
| Viewer dependency-free JavaScript | 17 scripts; 322 assertions passed |
| Optional Three.js resource integration | Blocked: `three` dependency absent; not counted as a pass or failure |
| Viewer Python scripts | 12 passed |
| Viewer structural validation | 143 passed |
| TypeScript syntax/transpile | 10 source files + 14 declaration parses; 0 errors |
| Viewer API contract | 63/63 calls matched; 0 missing or unresolved |
| Request body contract | 15 checked; 0 findings |
| Response contract | 50 JSON contracts; 52 endpoints; 28 models; 0 missing routes/schemas |
| Viewer package integrity | 0 findings |
| Backend / Viewer Python compileall | Passed |
| Chromium WebGL2 capability smoke (Xvfb) | Passed context, shader/triangle pixel, resize, animation frame, context loss and restoration |
| ZIP CRC / SHA-256 | Passed |

Detailed logs are under `build195_logs/`.

## New adversarial coverage

1. Trigger-like text inside PL/pgSQL function bodies and SQL literals does not count as a trigger declaration.
2. Trigger-like comment text does not count as a trigger declaration.
3. Duplicate actual trigger declarations are detectable and rejected against inventory.
4. Unmanifested data files are rejected.
5. Unexpected empty directories are rejected.
6. Symlinked data directories are rejected.
7. Duplicate keys in JSONL records are rejected.
8. Non-standard JSON numeric constants are rejected.
9. Duplicate manifest keys are rejected.
10. Malformed binary/base64 wrappers are rejected.

## Environment gates

- No PostgreSQL executable/service, `psql`, Docker/Podman, or psycopg 3 was found. No live PostgreSQL operation was attempted.
- `three` and React packages are absent from local package trees and npm cache. No package manifest or lockfile was changed to disguise the missing dependencies.
- Chromium was available. The direct headless probe could not create WebGL2; the supported Xvfb probe passed. The latter validates browser WebGL capability only, not the React/Three.js application.
- No live AI generation/provider call was made.

## Security interpretation

The bundle manifest's SHA-256 fields provide content-integrity checks against the values in that manifest. Because the manifest itself is not signed or authenticated, these hashes do not prove who created the bundle or protect against an attacker who can replace both payload and manifest. Treat bundles as trusted deployment artifacts and transfer them through an authenticated channel.

## Conclusion

BUILD-00195 source-level migration preflight hardening and offline regression verification passed. This does not establish live PostgreSQL migration, PostgreSQL runtime repository support, React/Three.js integration, production WebGL rendering, or live AI generation as complete.
