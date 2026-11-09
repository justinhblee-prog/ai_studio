# BUILD-00144 Release Notes

BUILD-00144 adds a Bearer-authenticated AssetVersion binary preview endpoint that checks current Workspace membership for every request and serves descriptor-pinned immutable bytes. Photo Draft, Output Review and Lookbook image previews now fetch those bytes with authorization and display Blob URLs owned by a shared dependency-free registry. Replaced, failed, reset and unmounted previews revoke their Blob URLs. GLTF/GLB model previews retain the existing short-lived signed URL mechanism because external glTF resources require resource-aware resolution.

Verification: Backend 367 passed; Asset API 69 passed; Viewer structural 143; Lookbook recovery 19/19; Object URL lifecycle 5 assertions; API 64/64; request contract 15 checked/0 findings; response contract 51 JSON / 53 total / 29 models; syntax 10 source + 5 declarations / 0 errors; OpenAPI snapshot current; package integrity 0 findings.
