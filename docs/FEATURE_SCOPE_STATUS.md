# AI CREATOR STUDIO — Current Feature Scope

**As of BUILD-00151.** This is the current product-scope reference. Older BUILD-00093/00096 notes describe the narrower feature set that existed at those historical builds and are not current implementation status.

| Area | Implemented now | Explicit boundary / not verified |
|---|---|---|
| 3D model viewer | React/Three.js source for GLB/GLTF loading, OrbitControls, camera framing, grid, animation, resize and cleanup; authenticated bounded downloads with exact-size known-length buffers and capped geometric-growth unknown-length buffers with typed final-trim allocation recovery and HTTP(S) relative-base resolution | WebGL2 capability smoke passes in Chromium under Xvfb/SwiftShader; full TypeScript typecheck and real React/Three.js model rendering are not verified |
| Asset workspace | Workspace-scoped upload/list/delete, authenticated current-membership fetch-to-Blob image previews with Object URL lifecycle; short-lived signed GLTF/GLB model previews; immutable versions, verified restore, image/model kind separation | Local filesystem adapter is PoC-only; production object storage and distributed atomicity are not claimed |
| Photo Draft | Non-billable drafts; deterministic local Pillow ENHANCE/LIGHTING processing; immutable derived outputs; output review; gated metadata manifest | No AI image generation, Provider dispatch, Quote/Credit charge, or identity/semantic quality guarantee. AI-only operations fail closed |
| Project Management | Workspace-scoped project create/list/edit, active/completed/archived lifecycle, active Lookbook reference protection, stale workspace-load cancellation/response guards | External reference is read-only after creation; no project deletion endpoint |
| Product Catalog | Workspace SKU create/edit/archive, product image references, stale workspace-load cancellation/response guards, Product Variants with independent SKUs, standard and custom option values (up to 12), variant-specific image selection/editing, and archive lifecycle | Not a commerce/PIM system; no marketplace sync, price/inventory, barcode, or multi-organization SKU namespace |
| Lookbook planning | Product/Variant and direct image selection, optional person/Project/Character, planning submit/approve/request-changes, manifest | Planning does not generate campaign images or call an AI Provider |
| Lookbook output assembly | Attach individually approved Photo outputs as exact immutable AssetVersions; Product/Variant association; ordered page/caption; separate snapshot-based assembly review; integrity-gated internal ZIP and manifest export; per-output exact-version authenticated fetch-to-Blob preview error/retry with Object URL revocation; signed download expiry preflight and Blob download/reissue; append-only export history with package/snapshot hashes, retention expiry and safe available/expired/missing file-state visibility; page-order snapshot integrity regression coverage | ZIP is internal-use-only; no publication or commercial-rights grant. Browser E2E for preview retry and Blob download is not verified; no new image generation or Provider execution |
| Generation output review | Read persisted outputs/review history, exact AssetVersion authenticated fetch-to-Blob preview, approve/request-changes/reject, gated metadata manifest | Review does not publish content or grant commercial rights |
| PostgreSQL | SQLite export/migration bridge and SQL dialect/readiness analysis | PostgreSQL runtime repository adapter, live DB integration, multi-host guarantees and cutover are not implemented/verified |
| Android | No native Android app in the current source package | Android build, packaging and device tests not implemented/verified |
| Production operations | Local test suite, API contracts, worker/repository tests, cleanup and readiness tooling | Production secrets, managed storage, live provider, deployment and production data changes are not verified |

## Current verification boundary

- Backend suite: 367 passed.
- Viewer API contract 63/63; request body contract 15 checked/0 findings; response schema audit 50 JSON endpoints across 52 method/path endpoints / 28 models.
- BUILD-00141 Lookbook preview/download/history structural checks 19/19; signed-link/stale-preview helper tests 12; KeyedRequestGate 7; RequestScopeGate 7; project lifecycle events 4; TypeScript syntax/transpilation 10 source files + 4 declarations / 0 errors; package integrity 0 findings.
- Python compileall and clean ZIP extraction checks pass.
- Full semantic TypeScript typecheck is blocked by unavailable trusted React/Three.js dependencies and typings. Actual React/Three.js component E2E, browser-driven signed URL expiry/retry, and actual ZIP Blob download remain unverified. Chromium/Xvfb/SwiftShader capability probes are not substitutes for component E2E.

- BUILD-00144: authenticated AssetVersion image preview endpoint; current Workspace membership checked per fetch; Photo Draft, Output Review and Lookbook use fetch-to-Blob; keyed Object URL replacement/revocation tested with 5 assertions. GLTF/GLB model previews remain signed-link based pending resource-aware loader design.

- BUILD-00150: bounded GLTF download runtime 17/17; structural 19/19; authenticated GLTF 9/9; backend 367 passed. Unknown-length growth and final-trim allocation failures surface typed memory recovery; device memory profile remains unverified.

- BUILD-00151: relative/root-relative model endpoint base resolution 10/10; authenticated GLTF structural checks 10/10; Chromium WebGL2 capability smoke passes under SwiftShader (not React/Three.js E2E).
