# AI CREATOR STUDIO — Current Handoff

## Baseline
- Build: BUILD-00146
- Base: BUILD-00145
- Focus: Bounded authenticated GLTF/GLB model downloads and actionable access/version recovery.

## Completed
- `Studio3DViewer` no longer uses unbounded `response.arrayBuffer()` for authenticated model downloads.
- Added a 256 MiB maximum download size. A declared `Content-Length` above the cap is rejected before reading; otherwise streamed chunks are counted and the reader is cancelled immediately when actual bytes exceed the cap.
- Abort signals are checked during stream consumption and before assembling the final ArrayBuffer. Existing AbortController cancellation on model URL/access token changes and unmount remains active.
- Added concise UI recovery guidance for HTTP 401 (re-authenticate), 403 (check workspace/asset access), 404 (refresh missing version), 409 (refresh changed version), oversized files, unavailable response streams, and generic network/server errors.
- Error UI and `onError` callback receive safe actionable messages, not raw response bodies, tokens, URLs or server diagnostics.
- Download progress uses `Content-Length` when available; 98% represents parse/scene-attach stage, and 100% only follows successful parse.
- Added `scripts/test_bounded_gltf_download.py` and npm script `test:bounded-gltf-download`.
- No backend API/schema, database migration, dependencies, Provider, credit, publication, rights, production data or deployment changes.

## Verification
- Backend full pytest: 367 passed.
- Bounded download/recovery structural checks: 15/15.
- Authenticated GLTF loading: 9/9.
- Authenticated preview Object URL: 5; RequestScopeGate: 7; KeyedRequestGate: 7; project lifecycle: 4; Lookbook signed-link: 12; Lookbook recovery: 19/19.
- Viewer API contract: 63/63; request-body contract: 15 checked / 0 findings; response contract: 50 JSON / 52 total / 28 models / 0 missing.
- API validator tests: 2; package integrity tests: 4; package integrity validator: 0 findings.
- TypeScript syntax/transpilation: 10 source + 5 declaration files, 0 syntax errors. This is not semantic type checking.
- Clean extraction verification reruns the backend and Viewer checks against the extracted ZIP.

## Remaining blockers / limitations
- `GLTFLoader.parse` still requires the complete ArrayBuffer. The stream is bounded, but chunk storage plus final contiguous buffer can temporarily require substantially more memory than the source file. No production-size fixture was available; 256 MiB is a cap, not a device compatibility guarantee.
- Actual React/Three.js browser component E2E and actual visible GLB/GLTF rendering remain unverified. Trusted React/Three.js packages and typings are unavailable in this environment.
- Semantic `tsc --noEmit` remains unverified; syntax/transpilation check only.
- External glTF buffer/image URIs remain rejected. Multi-file glTF package import is not implemented.
- PostgreSQL runtime/multi-host integration, Android, production object storage/secrets/RBAC, live Provider calls, credit charging, publication, rights grants and deployment remain unverified.

## Next autonomous priorities
1. Add an isolated executable test harness for the bounded stream reader when a trusted TS/browser runtime is provisioned; exercise known/unknown Content-Length, threshold crossing, abort during read, truncated transfer and 401/403/404/409 mapping.
2. Obtain trusted pinned React/Three.js packages and typings; run semantic TypeScript and browser E2E with minimal GLB and embedded-data GLTF fixtures, cancellation, parse failure and WebGL cleanup.
3. Measure realistic device memory with production-size fixtures before raising the 256 MiB cap or attempting worker/streaming parse.
4. Continue production readiness gaps only within approval boundaries.

## Approval boundaries
No live Provider calls, paid APIs, credit charges, publication, rights grants, production data changes, deployment, destructive migrations, or unresolved security/policy decisions without explicit approval.
