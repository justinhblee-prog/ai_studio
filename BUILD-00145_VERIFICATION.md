# BUILD-00145 Verification Report

| Check | Result |
|---|---:|
| Backend full pytest | 367 passed |
| Authenticated GLTF loading structural assertions | 9/9 passed |
| Authenticated preview Object URL registry | 5 assertions passed |
| RequestScopeGate | 7 passed |
| KeyedRequestGate | 7 passed |
| Project lifecycle events | 4 passed |
| Lookbook signed-link helper | 12 passed |
| Lookbook preview recovery | 19/19 passed |
| TypeScript syntax/transpilation | 10 source + 5 declarations; 0 errors |
| Viewer API contract | 63/63 |
| Request body contract | 15 checked; 0 findings |
| Response contract | 50 JSON / 52 endpoints / 28 models / 0 missing |
| Package integrity | 0 findings |
| Python compileall | PASS |

## Scope notes
- Authenticated model loading now fetches the exact current immutable AssetVersion with Bearer authorization and `cache: no-store`, then parses bytes with GLTFLoader.parse.
- AbortController cancels stale network fetches on URL/token changes and unmount; late parse results are disposed if cancelled.
- Backend validation rejects external glTF URIs. Only self-contained GLB and data-URI glTF are covered by the one-request strategy.

## Not verified
- Actual React/Three.js browser E2E, visible GLB/GLTF rendering, browser memory behavior for large models, semantic TypeScript `tsc --noEmit`, PostgreSQL integration, Android, production storage/secrets/RBAC, live Provider, credit, publication, rights and deployment.
- TypeScript result above is syntax/transpilation only, not semantic type checking.
