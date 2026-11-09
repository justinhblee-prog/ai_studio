# AI CREATOR STUDIO — Current Handoff

## Baseline
- Build: BUILD-00156
- Base: BUILD-00155
- Focus: viewer lifecycle integration and surfaced resource-disposal diagnostics.

## Completed
- Added `src/disposeViewerResources.mjs` and `.d.mts` as the lifecycle boundary around exhaustive GLTF resource disposal.
- Model replacement, loaded GLTF teardown and stage-resource teardown now report collected disposal errors through `runViewerCleanupSteps`; cleanup continues after the diagnostic is recorded.
- Added `scripts/test_viewer_lifecycle_integration.mjs`: nested scene graph, shared resource deduplication, stage resource release, model replacement, teardown order, injected GPU disposal failure and later cleanup assertions (32 total).
- Integrated the lifecycle harness into `npm run test:viewer-cleanup` and exposed a dedicated npm script.
- Registered the authenticated preview Object URL test as an npm script.
- Reconciled stale structural checks with the current authenticated byte-fetch + `GLTFLoader.parse` implementation and `/preview-content` endpoint.
- No backend/API/schema/DB/dependency-version/Provider/credit/publication/rights/production-data/deployment changes.

## Verification
- Backend full pytest: 367 passed in a completed run (30.57s). A later duplicate run timed out around 42% without a reported test failure; see verification report.
- Viewer lifecycle integration 32 assertions; cleanup helper 10 runtime; lifecycle structural 13/13; diagnostic integration 4/4.
- GLTF disposal 33 assertions; authenticated GLTF 15/15; bounded download 17 runtime/19 structural; model base path 10/10.
- Preview Object URL 5; RequestScopeGate 7; KeyedRequestGate 7; project lifecycle 4; Lookbook links 12; Lookbook recovery 19/19.
- Viewer API 63/63; request bodies 15 checked/0 findings; response contract 50 JSON/52 total/28 models/0 missing.
- Offline source structural validation 143; TypeScript syntax 10 source + 10 declarations/0 errors; package integrity 0 findings; Python compileall passed.
- Chromium WebGL2 capability smoke passed under Xvfb. This does not load React/Three Viewer or GLTF.
- Semantic `npm run typecheck` remains blocked by missing React/Three packages and typings; no dependencies were installed.

## Remaining blockers / limitations
- Actual React/Three browser component E2E and visible GLB/GLTF rendering remain unverified.
- Semantic TypeScript checking remains blocked until trusted pinned dependencies are provisioned.
- Production-size/target-device memory profiling unavailable.
- External glTF buffer/image URIs rejected; multi-file glTF import not implemented.
- PostgreSQL runtime/multi-host integration, Android, production object storage/secrets/RBAC, live Provider calls, credit charging, publication, rights grants and deployment remain unverified.

## Next autonomous priorities
1. Continue strengthening the Viewer lifecycle harness and introduce a real Three.js renderer/scene test when trusted pinned dependencies are available.
2. Provision pinned React/Three dependencies only in an approved network-enabled environment; then run semantic typecheck and browser E2E with minimal GLB/data-URI GLTF fixtures.
3. Profile target-device memory and representative large assets.
4. Continue readiness work without crossing approval boundaries.

## Approval boundaries
No live Provider calls, paid APIs, credit charges, publication, rights grants, production data changes, deployment, destructive migrations, or unresolved security/policy decisions without explicit approval.

## 상세 인수인계 문서

전체 프로젝트 개요, 승인 경계, 디렉터리 구조, 검증 현황, 실행 명령, 미완료 항목 및 BUILD-00157 작업 기준은 `AI_CREATOR_STUDIO_HANDOFF_BUILD-00156.md`를 먼저 확인합니다.
