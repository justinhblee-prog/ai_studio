# BUILD-00086 Verification Report

| Check | Result | Scope |
|---|---|---|
| Backend pytest | PASS — 272 passed | SQLite/local filesystem; includes Project RBAC, Job listing, crash recovery and FASHN preflight tests |
| Python compileall | PASS | `python -m compileall -q app scripts tests` |
| Viewer source structural checks | PASS — 19/19 | Static source checks only |
| API smoke | PASS | FastAPI TestClient `/health` 200 and `/v1/engines/capabilities` 200 |
| OpenAPI/runtime route inventory | DRIFT FOUND | 13 design path items vs 24 runtime path items; exact match false; 6 spec-only paths, 17 runtime-only paths, 3 method gaps |
| Project CRUD | PASS | Workspace RBAC and CRUD/status filtering tested against temporary SQLite DB |
| Job listing | PASS | Workspace scope, viewer read permission, pagination bounds tested |
| Live FASHN | NOT EXECUTED | No API key, authorized real input URLs, or explicit cost authorization |
| TypeScript typecheck | NOT VERIFIED | npm install timed out; React/Three.js dependencies unavailable |
| Browser/WebGL/Android | NOT VERIFIED | No real browser/device E2E |
| PostgreSQL/multi-host | NOT IMPLEMENTED / NOT VERIFIED | SQLite single-host only |

See `BUILD-00086_verification.log`, `BUILD-00086_openapi-runtime-drift.json`, and `BUILD-00086_PRODUCT_SCOPE_IMPLEMENTATION_AUDIT.md`.

A passing automated suite does not imply any G0–G5 Gate has passed.
