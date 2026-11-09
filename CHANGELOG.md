## BUILD-00157 — Viewer Animation Loop Failure Isolation

- Extracted the Studio3DViewer requestAnimationFrame loop into a dependency-free controller with one-frame ownership, idempotent stop/restart, and render-failure isolation.
- Added 19 focused controller assertions and re-ran backend/viewer/contract/browser-capability checks.
- Semantic TypeScript and actual React/Three/GLTF browser E2E remain blocked/unverified; see BUILD-00157_VERIFICATION.md.

# Changelog

## BUILD-00156 — Viewer Lifecycle Integration & Disposal Diagnostics

- Added a dependency-free integration harness for nested scene graphs, shared textures/materials/geometries/skeletons, stage resources, model replacement, teardown ordering, and injected GPU-disposal failure (32 assertions).
- Added `disposeViewerResources` so collected disposal errors reach the failure-isolated lifecycle runner after exhaustive release attempts; later teardown steps still execute.
- Reconciled stale Viewer structural checks with authenticated byte-fetch + `GLTFLoader.parse` and the immutable AssetVersion `/preview-content` endpoint; structural checks now pass 143/143.
- Backend 367 passed; cleanup runtime 10, structural 13/13, diagnostic integration 4/4; GLTF disposal 33; authenticated GLTF 15/15; API 63/63; TypeScript syntax 10 source + 10 declarations / 0 errors; package integrity 0 findings.
- Chromium WebGL2 capability smoke passed under Xvfb. Semantic typecheck remains blocked by missing React/Three dependencies; actual React/Three browser E2E and target-device memory profiling remain unverified.

## BUILD-00154 — Failure-Resilient GLTF Resource Disposal

- Made GLTF GPU-resource cleanup best-effort: a throwing `dispose()` no longer aborts cleanup of later resources.
- Added structured diagnostics and counts for attempted/successful disposal across textures, materials, geometries, and skeletons.
- Isolated traversal and nested material-property inspection failures; shared resources remain deduplicated.
- Added 19 runtime assertions; backend 367 passed; authenticated GLTF 15/15; Viewer contracts, TypeScript syntax, package integrity and WebGL2 capability smoke passed.
- Semantic TypeScript and actual React/Three browser E2E remain unverified because React/Three dependencies are absent.


## BUILD-00145 — Authenticated GLTF/GLB AssetVersion Loading
- Replaced the 3D AssetWorkspace signed preview URL with the exact current immutable AssetVersion authenticated content endpoint.
- Added Bearer-authenticated `fetch` with `cache: no-store`, AbortController cancellation on model/scope changes, and `GLTFLoader.parse` from fetched bytes.
- Preserved server-side external glTF URI rejection; self-contained GLB and data-URI glTF avoid unauthenticated secondary resource requests.
- Added dependency-free structural regression checks and updated response-contract inventory for the endpoint usage change.
- Backend: 367 passed. React/Three.js browser E2E and semantic TypeScript remain unverified.


## BUILD-00146 — Bounded Authenticated GLTF Downloads & Recovery

- Enforced a 256 MiB maximum for authenticated model downloads using Content-Length preflight and streamed-byte accounting; cancel over-limit streams and retain abort handling.
- Added actionable safe recovery guidance for 401/403/404/409 and file-size/network/stream failures without exposing raw server details, model URLs or tokens.
- Added 15 bounded-download structural assertions and a dedicated npm test script.
- Backend full suite 367 passed; bounded GLTF 15/15; authenticated GLTF 9/9; Viewer API 63/63; request bodies 15 checked; response contract 50 JSON / 52 total; syntax 10+5; package integrity 0 findings. Browser E2E and semantic TypeScript remain unverified.


## BUILD-00147 — Executable Bounded GLTF Stream Reader & Transfer Integrity

- Extracted bounded authenticated model response reading into a dependency-free `.mjs` module and typed `.d.mts` declaration; the viewer now consumes this single tested implementation.
- Added a real Node Fetch/ReadableStream test harness covering known/unknown Content-Length, early declared-size rejection, streamed-size overflow and cancellation, abort before/during read, truncated transfers, 401/403/404/409 mapping, and malformed length handling (9/9).
- Added declared-length mismatch detection so truncated or incomplete transfers fail safely before GLTF parsing.
- Backend 367 passed; bounded-download structural 15/15; authenticated GLTF 9/9; Viewer API 63/63; request bodies 15 / 0 findings; response 50 JSON / 52 total / 28 models; TypeScript syntax 10 source + 6 declarations; package integrity 0 findings.
- Actual React/Three browser rendering, semantic TypeScript, device memory profiling and external-resource GLTF remain unverified.

## BUILD-00148 — Bounded GLTF Download Memory & Header Validation
- For valid known Content-Length responses, allocate the exact final ArrayBuffer once and stream chunks directly into it, avoiding duplicate full-payload buffering.
- Fail closed on malformed, negative, fractional, or empty Content-Length values; cancel oversized declared responses before reading.
- Reject and cancel streamed payloads exceeding declared length or the global 256 MiB limit.
- Expanded executable Fetch/ReadableStream coverage from 9 to 12 cases; backend suite remains 367 passed.
- No dependencies, API/schema, database, Provider, credit, publication, rights or deployment changes. Browser E2E, semantic TypeScript and target-device memory remain unverified.

## BUILD-00149 — Unknown-Length GLTF Buffer Growth Hardening
- Replaced unknown-length stream chunk retention plus final assembly copy with a 64 KiB-start, geometric-growth `Uint8Array` accumulator capped at 256 MiB.
- Reuse the accumulator backing store when its capacity exactly matches the final payload; otherwise copy only the exact final range.
- Allocation failure cancels the stream and returns a typed `memory` error with user-facing recovery guidance.
- Added runtime coverage for multi-boundary growth, empty unknown-length streams, and allocation-failure cancellation; bounded runtime 16/16 and structural 19/19.
- Backend full suite 367 passed; Viewer API 63/63; request body 15 checked/0 findings; response contract 50 JSON / 52 total / 28 models; TypeScript syntax 10 source + 6 declarations / 0 errors; package integrity 0 findings.
- Browser E2E, semantic TypeScript, and target-device memory profiling remain unverified. No dependency, API/schema, DB, Provider, credit, publication, rights or deployment changes.


## BUILD-00150 — Final GLTF Buffer Trim Failure Handling
- Mapped unknown-length stream final-trim allocation failures to the same typed `memory` error used by growth and known-length allocation failures.
- Added executable regression coverage for simulated final-trim allocation failure; bounded runtime 17/17, structural 19/19.
- Backend 367 passed; Viewer API 63/63; request body 15 / 0 findings; response 50 JSON / 52 total / 28 models; TypeScript syntax 10 source + 6 declarations / 0 errors; package integrity 0 findings.
- Actual React/Three rendering, semantic TypeScript and target-device memory profiling remain unverified.


## BUILD-00151 — Relative GLTF Model URL Base Resolution
- Added dependency-free HTTP(S) base-path resolver for `GLTFLoader.parse`; relative/root-relative model endpoints now resolve against the current page URL.
- Invalid URLs and unsupported schemes fail closed; added 10 runtime cases and updated authenticated GLTF structural coverage to 10/10.
- Backend 367 passed; bounded download 17/17 runtime + 19/19 structural; Viewer API 63/63; request body 15 / 0 findings; response 50 JSON / 52 total / 28 models; TypeScript syntax 10 source + 7 declarations / 0 errors.
- Chromium WebGL2 capability smoke passes under SwiftShader, but does not prove React/Three.js component rendering. Semantic typecheck and device memory profile remain unverified.

## BUILD-00152 — Complete GLTF Resource Lifecycle Disposal
- Added cycle-safe GLTF resource disposal across all parser-returned scenes, nested material uniforms, shared geometries/materials/textures, and inactive scenes.
- Viewer now retains the complete GLTF result and disposes it on model replacement, late parse completion after cancellation, and renderer teardown.
- Added 11 executable disposal assertions; authenticated GLTF structural checks 11/11.
- Backend 367 passed; bounded download 17/17 runtime + 19/19 structural; model base path 10/10; Viewer API 63/63; request-body 15 / 0 findings; response 50 JSON / 52 total / 28 models; syntax 10 source + 8 declarations / 0 errors; package integrity 4 tests.
- Chromium WebGL2 capability smoke passed under Xvfb/SwiftShader. Semantic typecheck remains blocked by missing React/Three dependencies; actual React/Three rendering and target-device memory remain unverified.


## BUILD-00153 — Viewer GPU Resource Lifecycle Completion
- Extended GLTF cleanup to dispose shared skinned-mesh skeleton resources exactly once.
- Moved viewer floor/grid into a dedicated stage-resource group and explicitly disposes its GPU resources even when a model is loaded.
- Explicitly disposes the directional light shadow target and uncaches animation mixer roots during replacement/teardown.
- Added 3 skeleton runtime assertions and 4 authenticated GLTF structural checks; disposal runtime 14 assertions, authenticated GLTF 15/15.
- Backend 367 passed; bounded download 17 runtime/19 structural; API 63/63; request/response contracts clean; TypeScript syntax 10+8/0; package integrity 0 findings. Chromium WebGL2 capability smoke passed under Xvfb/SwiftShader.
- Semantic typecheck remains blocked by absent React/Three dependencies; actual React/Three rendering and target-device memory remain unverified.

## BUILD-00205 — API security surface audit (2026-11-06)
- Reduced public health output to liveness + version; removed worker/queue/provider operational detail from unauthenticated response.
- Added FastAPI route dependency inventory regression checks and an explicit public endpoint allowlist; internal operations routes must remain authenticated.
- Documented workspace role matrix, signed preview capability limits, platform operations boundary, API design/runtime compatibility rules, and production identity risks.
- Full backend: 468 passed; focused security/API/assets/operations: 144 passed; compileall and runtime OpenAPI snapshot check passed.

## BUILD-00206 — Output Asset Provenance & Workspace Integrity (2026-11-06)
- Attribute new generated Output import provenance to the worker service principal; retain initiating user and worker identity as separate audit details.
- Verify deterministic Asset owner/workspace/content, immutable AssetVersion metadata, and Provenance source/job/output linkage on retry.
- Add adversarial cross-workspace version and owner-mismatch regression tests. Full backend 470 passed; focused 100 passed; compileall and runtime OpenAPI check passed.
- Preserve legacy provenance compatibility; automated orphan private-file cleanup remains open.

## BUILD-00207 — Workspace Relation Integrity (2026-11-06)
- Add database-level workspace validation triggers for Product/Variant images, Character Assets, Lookbook Assets and Lookbook entity references; direct SQL cross-workspace writes are rejected.
- Freeze Product and Character mutations while active Lookbook Drafts reference them; archive the draft to resume edits.
- Add adversarial direct-SQL tests. Focused 72 passed; full Backend 473 passed; compileall and runtime OpenAPI check passed.
- PostgreSQL parity and historical relation audit remain open.

## BUILD-00208 — Read-only Historical Workspace Integrity Auditor (2026-11-06)
- Added a read-only SQLite CLI auditor for historical Product/Variant/Character/Lookbook references, including missing, deleted, cross-workspace and invalid-media findings.
- Added deterministic JSON reports and regression tests for adversarial legacy rows and clean data; confirmed the auditor does not mutate rows.
- Documented human-reviewed remediation, safe orphan-file quarantine/retention requirements, and PostgreSQL migration design notes.
- New auditor tests 2 passed; full Backend 475 passed; Python compileall passed. PostgreSQL parity and destructive cleanup remain unimplemented/unverified.
