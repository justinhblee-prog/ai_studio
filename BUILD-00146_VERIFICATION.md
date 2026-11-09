# BUILD-00146 Verification Report

| Check | Result |
|---|---:|
| Backend full pytest | 367 passed |
| Bounded GLTF download/recovery structural assertions | 15/15 passed |
| Authenticated GLTF loading structural assertions | 9/9 passed |
| Authenticated preview Object URL registry | 5 assertions passed |
| RequestScopeGate | 7 assertions passed |
| KeyedRequestGate | 7 assertions passed |
| Project lifecycle events | 4 assertions passed |
| Lookbook signed-link helper | 12 assertions passed |
| Lookbook preview recovery | 19/19 passed |
| Viewer API contract | 63/63 |
| Request body contract | 15 checked / 0 findings |
| Response contract | 50 JSON endpoints / 52 total / 28 models / 0 missing routes or schemas |
| API validator tests | 2 passed |
| Package integrity tests | 4 passed; validator 0 findings |
| TypeScript syntax/transpilation | 10 source + 5 declarations / 0 syntax errors |
| Python compileall | PASS |

## Implementation scope
- 3D model download is streamed and capped at 256 MiB. Both declared Content-Length and actual streamed byte totals are checked.
- The stream is cancelled when it exceeds the limit; AbortSignal is checked while reading and before returning the final ArrayBuffer.
- HTTP 401/403/404/409 and file-size/network/body failures map to concise actionable UI messages. Error messages do not include raw server responses, access tokens or model URLs.
- The component still passes the completed ArrayBuffer to `GLTFLoader.parse`; this is bounded download, not streaming GLTF parsing. Chunk buffering plus final contiguous ArrayBuffer means peak memory can exceed the file size and requires production-size fixture measurement.
- No API routes/schemas, migrations, dependencies, Provider calls, credits, publication, rights grants or deployment actions were added.

## Not verified / limitations
- Actual React/Three.js browser component E2E and visible GLB/GLTF rendering remain unverified because trusted React/Three.js packages and typings are unavailable in this environment.
- Semantic `tsc --noEmit` remains unverified; the successful check above is syntax/transpilation only.
- No production-size GLB fixture was available; 256 MiB is a hard client-side upper bound, not a claim that files near that size are safe on all devices.
- External glTF buffer/image URIs remain rejected; multi-file glTF package import is not implemented.
- PostgreSQL runtime/multi-host integration, Android, production object storage/secrets/RBAC, live Provider, credit charging, publication, rights grants and deployment remain unverified.
