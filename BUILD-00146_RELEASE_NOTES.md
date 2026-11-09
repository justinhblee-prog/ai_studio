# BUILD-00146 Release Notes

## Bounded Authenticated GLTF Downloads & Recovery
- Replaced the unbounded `response.arrayBuffer()` download with a streaming reader that enforces a 256 MiB maximum using both `Content-Length` preflight and cumulative received-byte checks.
- Oversized streams are cancelled as soon as the cap is crossed; abort signals are checked during and after stream reads. The existing model/token-change and unmount cancellation behavior remains in place.
- Added actionable, non-sensitive recovery messages for HTTP 401, 403, 404 and 409, plus oversized files, unavailable response streams and generic network/server failures. Raw response bodies, server details, model URLs and access tokens are not exposed in these messages.
- Download progress is updated from the response length when available; parse stage is represented as 98% until successful scene attachment.
- Added `scripts/test_bounded_gltf_download.py` and npm script `test:bounded-gltf-download` (15 structural regression assertions).
- No API route/schema, database migration, dependency version, Provider, credit, publication, rights or deployment behavior changed.

## Verification
- Backend full pytest: 367 passed.
- Bounded download/recovery assertions: 15/15; authenticated GLTF assertions: 9/9.
- Authenticated preview object URL: 5; RequestScopeGate: 7; KeyedRequestGate: 7; project lifecycle: 4; Lookbook signed-link: 12; Lookbook recovery: 19/19.
- Viewer API contract: 63/63; request-body contract: 15 checked / 0 findings; response contract: 50 JSON endpoints / 52 total / 28 models / 0 missing.
- TypeScript syntax/transpilation: 10 source files + 5 declarations, 0 syntax errors (not semantic type checking).
- Package integrity: 0 findings; Python compileall passed; clean ZIP extraction re-verification passed.
- Actual React/Three.js browser E2E, visible model rendering, semantic TypeScript typecheck and production-size memory behavior remain unverified.
