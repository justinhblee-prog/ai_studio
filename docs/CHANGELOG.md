## BUILD-00157 — Viewer Animation Loop Failure Isolation

- Extracted the Studio3DViewer requestAnimationFrame loop into a dependency-free controller with one-frame ownership, idempotent stop/restart, and render-failure isolation.
- Added 19 focused controller assertions and re-ran backend/viewer/contract/browser-capability checks.
- Semantic TypeScript and actual React/Three/GLTF browser E2E remain blocked/unverified; see BUILD-00157_VERIFICATION.md.


## BUILD-00154 — Failure-Resilient GLTF Resource Disposal

- Made GLTF GPU-resource cleanup best-effort: a throwing `dispose()` no longer aborts cleanup of later resources.
- Added structured diagnostics and counts for attempted/successful disposal across textures, materials, geometries, and skeletons.
- Isolated traversal and nested material-property inspection failures; shared resources remain deduplicated.
- Added 19 runtime assertions; backend 367 passed; authenticated GLTF 15/15; Viewer contracts, TypeScript syntax, package integrity and WebGL2 capability smoke passed.
- Semantic TypeScript and actual React/Three browser E2E remain unverified because React/Three dependencies are absent.

## BUILD-00144 — Authenticated AssetVersion Preview Delivery

- Added a Bearer-authenticated binary AssetVersion preview endpoint that rechecks current Workspace membership at each fetch and streams the exact immutable version through descriptor-pinned size/SHA-256 validation.
- Photo Draft, Output Review, and Lookbook image previews now use authenticated fetch-to-Blob rather than reusable signed preview URLs.
- Added keyed Object URL ownership/revocation on replacement, preview error, workspace/assembly reset, and unmount; stale request/scope responses cannot publish a Blob URL.
- Preserved short-lived signed URLs for GLTF/GLB model preview because external relative buffers/textures require resource-aware loading; a single Blob URL is not a safe drop-in replacement.
- Backend pytest 367 passed; Viewer structural 143; Lookbook recovery 19/19; object URL registry 5 assertions; API 64/64; request body 15 checked/0 findings; response contract 51 JSON/53 total/29 models; syntax 10 source + 5 declarations/0 errors; OpenAPI snapshot current; package integrity 0 findings.
- Actual React/Three.js browser E2E and semantic TypeScript remain unverified due unavailable trusted dependencies/runtime. No database migration, Provider/credit/publication/rights/deployment changes.

## BUILD-00141 — Lookbook Export History & Page-Order Integrity

- Lookbook assembly now shows append-only internal ZIP export history, including package and approved snapshot hashes, timestamps, retention expiry, and observed file state (`available`, `expired`, `missing`).
- The backend history endpoint uses safe `lstat` checks for regular package files and does not mutate audit rows or remove files. New package exports refresh the history display.
- Added regression coverage proving page order is included in the immutable assembly snapshot hash and that missing/restored ZIP files are reflected without losing audit history.
- Backend 359 passed; compileall passed; Lookbook structural 19/19; helper 12; API 64/64; request bodies 15 checked/0 findings; response contract 52 JSON/53 endpoints/29 models; request-contract tests 2 passed; syntax 10 source + 4 declarations/0 errors; package integrity 0 findings.
- Semantic TypeScript and actual React/Three.js browser E2E remain unverified because trusted dependencies/typings are unavailable. No new routes, database schema, migrations, dependencies, Provider, credit, publication, or rights behavior changed.

## BUILD-00140 — Lookbook Preview & Signed Download Recovery

- Lookbook output assembly now requests preview URLs for exact immutable AssetVersion pairs, tracks per-output loading/error/expiry, supports manual retry, and ignores stale image errors using keyed request sequencing.
- Package download now distinguishes the 15-minute signed-link expiry from the 24-hour package retention expiry, preflights expiry, uses a no-store Blob download, surfaces errors, and allows explicit fresh ZIP/link issuance.
- Added 12 helper assertions and 15 structural assertions; strengthened backend integration coverage for immutable AssetVersion identity across preview refresh and ZIP export; backend 359 passed; Viewer API 63/63; request body 15 checked/0 findings; response schema 51 JSON / 52 endpoints; syntax 10 sources + 4 declarations / 0 errors; package integrity 0 findings.
- No backend/API/schema/database/dependency/provider/credit/publication/rights behavior changed. Real browser component E2E and actual Blob download remain unverified.

## BUILD-00134 — Dependency-Free Request Scope Lifecycle Gate

- Extracted async request-scope token lifecycle into a dependency-free gate used by `useRequestScope`, invalidating stale work on API/auth/workspace/job scope changes and unmount.
- Added a `.d.mts` declaration and a Node built-in behavior test (7 assertions) covering scope changes, disposal and reactivation; added `test:scope-gate` npm script.
- Structural checks 113/113; TypeScript syntax 10 source files + declaration parse / 0 errors; API 63/63; request bodies 15 checked; response schema 51 JSON / 52 total; Viewer script tests 8 passed; package integrity 0 findings; backend pytest 359 passed; compileall passed.
- No backend/API/database contract or dependency version changes.

# Changelog

## BUILD-00156 — Viewer Lifecycle Integration & Disposal Diagnostics

- Added a dependency-free integration harness for nested scene graphs, shared textures/materials/geometries/skeletons, stage resources, model replacement, teardown ordering, and injected GPU-disposal failure (32 assertions).
- Added `disposeViewerResources` so collected disposal errors reach the failure-isolated lifecycle runner after exhaustive release attempts; later teardown steps still execute.
- Reconciled stale Viewer structural checks with authenticated byte-fetch + `GLTFLoader.parse` and the immutable AssetVersion `/preview-content` endpoint; structural checks now pass 143/143.
- Backend 367 passed; cleanup runtime 10, structural 13/13, diagnostic integration 4/4; GLTF disposal 33; authenticated GLTF 15/15; API 63/63; TypeScript syntax 10 source + 10 declarations / 0 errors; package integrity 0 findings.
- Chromium WebGL2 capability smoke passed under Xvfb. Semantic typecheck remains blocked by missing React/Three dependencies; actual React/Three browser E2E and target-device memory profiling remain unverified.

## BUILD-00136 — Photo Review & Output Decision State Integrity

- Added dependency-free keyed request sequencing for Photo Draft AssetVersion preview URL hydration; superseded responses and scope-reset responses are ignored.
- Serialized Photo Draft review/archive/manifest mutations and Output Review decision/manifest mutations to prevent rapid duplicate/conflicting state transitions. Photo archive immediately clears stale manifest and review-comment state.
- TypeScript syntax validation now parses all `.d.mts` declarations; added seven keyed-gate behavior assertions. Structural checks 122/122; KeyedRequestGate 7 assertions; RequestScopeGate 7 assertions; backend pytest 359 passed; compileall passed.
- No backend/API/schema/database/dependency/provider behavior changed. Semantic TypeScript and actual React/Three.js browser E2E remain unverified.

## BUILD-00133 — Nested Read Hydration and Selected-Project Race Protection

- Photo Draft, Project Product Assignment, and Output Review now reject older concurrent nested-read hydration using request sequences; assignment responses additionally verify the currently selected project identity.
- Product Catalog's existing sequence guard was reviewed and retained. Structural validation expanded to 111 checks. Backend 359 passed; Viewer script tests 8 passed; TypeScript syntax/transpilation 10 files / 0 errors.
- No backend/API/schema/database/dependency/provider behavior changed. Runtime React component E2E and semantic TypeScript typecheck remain unverified.

## BUILD-00131 — Workspace Mutation Scope Safety

- Added a shared request-scope guard to prevent late mutation/read callbacks from updating a different workspace/job view after API origin, access token, scope or component lifecycle changes.
- Applied scope guards across Asset, Photo Draft, Lookbook, Product Catalog/Variant, Project Product Assignment, Project and Output Review workspaces; cleared prior-scope UI state on scope changes.
- Expanded structural validation to 103 checks. No backend/API/schema/database/dependency/provider behavior changed.
- Verification details and the full-suite timeout qualification are in `docs/reports/BUILD-00131_VERIFICATION.md`.

## BUILD-00113 — OpenAPI Runtime Contract Reconciliation

- Added a committed runtime OpenAPI snapshot (80 path items) and deterministic `--check` exporter.
- Added regression tests to detect unreviewed runtime contract changes.
- Documented compatibility decisions and the three deferred credit/quote operations.
- Preserved runtime behavior; the design draft remains unchanged.

# 변경 이력

## BUILD-00111 — 승인 Lookbook 내부 ZIP 패키지

- 별도 조립 승인이 완료된 Lookbook 결과를 exact AssetVersion 파일과 manifest.json으로 묶는 private ZIP export를 추가했습니다. 100페이지/250MiB 제한, SHA-256 검증, append-only export audit를 적용했습니다.
- 다운로드 URL은 15분 서명 링크이며 패키지는 24시간 후 만료됩니다. 만료 파일 cleanup은 dry-run 기본, `--apply` 명시 실행 방식입니다. audit 기록은 보존합니다.
- LookbookDraftWorkspace에 승인 후 ZIP 생성/다운로드를 추가했습니다. Backend 340 passed, compileall passed, cleanup dry-run passed, Viewer structural checks 65/65 passed. TypeScript/browser/WebGL은 미검증입니다.

## BUILD-00110 — Lookbook 페이지 순서 미리보기

- Lookbook output assembly 패널에서 각 연결 결과의 정확한 immutable AssetVersion을 서명된 preview URL로 불러와 페이지 순서대로 표시합니다.
- 최신 Asset pointer가 바뀌어도 검수 대상 버전이 바뀌지 않습니다. Preview 실패는 검수 성공으로 처리하지 않으며 backend 무결성 검사가 별도로 적용됩니다.
- Backend 340 passed, compileall passed, Viewer structural checks 63/63 passed. TypeScript/browser/WebGL은 미검증입니다.

## BUILD-00109 — Lookbook 결과 조립 별도 검토·승인

- 승인된 Photo 결과를 Lookbook에 연결한 뒤, 조립 순서/캡션/SKU snapshot 전체를 SHA-256으로 고정해 별도 검토 요청할 수 있도록 했습니다.
- owner/admin만 조립 승인·반려할 수 있고, 반려는 terminal이며 새 초안에서 재구성해야 합니다. 검토 제출 후 결과 추가 연결을 동결합니다.
- 승인된 조립 snapshot과 Photo AssetVersion 파일 무결성을 재검증한 경우에만 내부 manifest를 내보냅니다. Backend 340 passed, compileall passed, Viewer structural checks 62/62 passed. TypeScript/browser/WebGL은 미검증입니다.

## BUILD-00108 — Lookbook 승인 Photo 결과 조립

- 승인된 Lookbook 기획안에 개별 승인된 Photo AssetVersion만 연결할 수 있도록 했습니다. Product/Variant가 기획안에 포함됐는지 검증하고 SKU·옵션 snapshot을 고정합니다.
- 결과 아이템과 manifest export audit는 append-only입니다. 내부 manifest는 SHA-256 메타데이터만 포함하며 페이지 조립 자체는 별도 승인되지 않았고 게시/상업 권리를 부여하지 않습니다.
- LookbookDraftWorkspace에 승인 Photo 결과 탐색, Variant 연결, 페이지 순서/캡션, 내부 manifest 내보내기를 추가했습니다. Backend 340 passed, compileall passed, Viewer structural checks 59/59 passed. TypeScript/browser/WebGL은 미검증입니다.

## BUILD-00107 — immutable AssetVersion 미리보기 및 Photo 원본 버전 고정

- 특정 AssetVersion에 서명된 미리보기 URL을 발급하고, 파일 크기·SHA-256·경로를 검증하도록 했습니다. v2 업로드 이후에도 v1 URL은 v1을 보여줍니다.
- Photo Draft가 원본 AssetVersion/체크섬을 고정하고, 실행·멱등성·출처 Provenance가 해당 버전을 사용하도록 개선했습니다.
- PhotoDraftWorkspace와 OutputReviewWorkspace에서 검수 대상의 정확한 immutable version을 미리 볼 수 있습니다. Backend 339 passed, compileall passed, Viewer structural checks 56/56 passed. TypeScript/browser/WebGL은 미검증입니다.

## BUILD-00106 — Photo 결과 검수·승인 및 내부 manifest

- 로컬 Photo 처리 결과를 AssetVersion/Provenance/SHA-256에 고정해 검수·승인·수정 요청·반려하는 API를 추가했습니다. 검수 이력은 append-only이며 owner/admin만 결정할 수 있습니다.
- 승인된 결과는 owner/admin/editor가 metadata-only 내부 manifest로 내보낼 수 있습니다. 새 AssetVersion이 추가되어도 검수된 v1 파일의 무결성을 확인해 승인 스냅샷을 유지합니다.
- PhotoDraftWorkspace에 검수 상태, 결정 버튼, 승인 manifest 내보내기를 추가했습니다. Backend 337 passed, compileall passed, Viewer structural checks 54/54 passed. TypeScript/browser/WebGL은 미검증입니다.

## BUILD-00105 — 로컬 Photo Engine 이미지 조정

- ENHANCE·LIGHTING에 한해 Pillow 기반 결정론적 로컬 이미지 조정을 실행할 수 있도록 했습니다. 이는 생성형 AI가 아니며 Provider 호출·크레딧 차감이 없습니다.
- Idempotency-Key, 실행 이력, 실패 후 재시도, immutable AssetVersion, SHA-256, `derived_from` 및 Provenance를 연결했습니다. 로컬 지원 범위를 벗어나는 BACKGROUND·RETOUCH·COMPOSE와 프롬프트/마스크/복수 출력은 AI 엔진 연결 전까지 차단합니다.
- PhotoDraftWorkspace에 로컬 실행 및 결과 Asset/Version 표시를 추가했습니다. Backend 336 passed, compileall passed, Viewer structural checks 51/51 passed. TypeScript/browser/WebGL은 미검증입니다.

## BUILD-00104 — Generated Output 검수·승인 및 내부 Export Manifest

- 생성 Output이 검증된 immutable AssetVersion/Provenance에 연결된 뒤에만 개별 검수하도록 API와 UI를 추가했습니다.
- owner/admin 승인 권한으로 승인·수정 요청·반려를 기록하며, 각 결정은 Asset ID, Version ID, Provenance ID, SHA-256을 스냅샷으로 보존합니다. 수정 요청 후 재검토는 허용하지만 승인/반려는 terminal입니다.
- 모든 Output이 개별 승인된 succeeded Job만 내부 metadata manifest를 내보낼 수 있습니다. manifest는 SHA-256과 append-only export audit를 남기며 바이너리/공개 URL을 포함하지 않습니다. 상업적 권리나 게시 허가를 부여하지 않는다는 상태를 명시합니다.
- `OutputReviewWorkspace` UI를 추가했습니다. Backend 332 passed, compileall passed, Viewer structural checks 49/49 passed. TypeScript/browser/WebGL은 의존성/런타임 부재로 미검증입니다.

## BUILD-00089 — Private Asset Integrity Audit

- `GET /v1/assets/integrity`를 추가해 workspace 내 private asset 파일을 upload-time size/SHA-256 metadata와 비교합니다. `ok`, `missing`, `size_mismatch`, `checksum_mismatch` 상태를 반환합니다.
- Workspace RBAC, 페이지네이션, root 내부 경로 확인, 1 MiB chunk hashing을 적용했습니다. 응답에는 asset ID/status만 포함하고 storage path/key/checksum은 노출하지 않습니다.
- 읽기 전용 감사 기능으로 파일을 수정/삭제/복구하지 않습니다.
- Asset API tests 17 passed, Backend 전체 281 passed, compileall passed, Viewer structural 19/19 passed. OpenAPI route/schema drift report와 runtime snapshot을 재생성했습니다.

## BUILD-00088 — OpenAPI schema contract audit

- Design OpenAPI v0.2와 FastAPI runtime의 request body, success response schema/status, parameters, operationId를 비교하는 `scripts/audit_openapi_contract.py`를 추가했습니다. Local schema/response references를 해석하며 generated runtime OpenAPI JSON snapshot도 저장합니다.
- 15개 matched design operations 중 10개에서 contract drift를 확인했고, 5개 design operation은 runtime에 없습니다. Route inventory audit와 별개로 schema-level gap을 가시화합니다.
- 이 도구는 구조적 비교이며 semantic equivalence나 runtime payload conformance를 증명하지 않습니다. Design baseline은 덮어쓰지 않았습니다.
- Audit tests 2개 추가; Backend 278 passed, Python compileall passed, Viewer structural 19/19 passed. 세부 내용은 BUILD-00088 verification report를 참조하십시오.

## BUILD-00087 — Queued Job cancellation 및 상태 추적

- `POST /v1/generation-jobs/{job_id}/cancel`을 추가했습니다. Workspace owner/admin/editor만 호출할 수 있고, Job이 `queued`이며 SUBMIT_GENERATION outbox 이벤트가 아직 `pending`인 경우에만 취소합니다.
- Job/Execution을 terminal `failed`로 종료하고 `error_code=JOB_CANCELLED` 및 `JOB_CANCELLED_BEFORE_DISPATCH` 이벤트를 기록하며, pending outbox를 `processed`로 마감합니다. 이 동작은 단일 SQLite 트랜잭션으로 처리됩니다.
- Provider dispatch가 이미 claim됐거나 reconciliation 상태인 경우 취소를 거부해 실제 Provider 요청이 진행 중인데 취소된 것처럼 보이는 상황을 방지합니다. 실행 중 Provider 취소 API는 별도 Provider capability/권리 검증 전까지 지원하지 않습니다.
- OpenAPI draft에 이미 정의된 cancellation route가 runtime과 일치하도록 구현했습니다. Audit 결과 design-only path는 6개에서 5개로 줄었지만 전체 계약 일치는 아닙니다.
- 회귀 테스트 4개 추가. Backend 276 passed, compileall passed, Viewer structural 19/19 passed.

이 문서는 사용자/개발자 관점에서 의미 있는 변경을 누적합니다. 세부 구현은 `development/DEVELOPMENT_LOG.md`, 현재 상태는 `handoff/CURRENT_HANDOFF.md`를 참조하십시오.

## BUILD-00086 — Project CRUD, Job Listing 및 제품 범위 감사

- Library에 보관된 통합 요구사항 추적표, 공통 데이터 모델, Backend Blueprint, OpenAPI v0.2, Schema Mapping Audit, Job 상태 전이 fixture를 통합 소스에 포함했습니다. 설계 문서와 실제 구현을 구분합니다.
- Workspace RBAC 기반 Project 생성/조회/수정 API와 workspace-scoped Generation Job 목록/페이지네이션 API를 추가했습니다.
- OpenAPI 설계 경로와 실제 FastAPI route/method 차이를 재현하는 audit script 및 JSON 결과를 추가했습니다. 정확 일치가 아니며 계약 drift가 문서화되어 있습니다.
- 제품 요구사항 전체를 runtime 기준으로 분류한 BUILD-00086 scope audit를 추가했습니다.
- Backend 272 tests 통과, compileall 통과, Viewer structural 19/19 통과.

## BUILD-00085 — Cost-gated Live FASHN Sandbox Harness

- `scripts/live_fashn_smoke.py`를 추가해 실제 FASHN start/status 호출과 반환 이미지 다운로드/포맷 검증을 한 번에 수행할 수 있도록 했습니다.
- 실행 전 API key, 소유/사용 권한이 있는 HTTPS 입력 이미지 URL, 명시적 비용 확인 문자열을 모두 요구합니다. 기본 실행은 외부 호출 없이 차단됩니다.
- 출력은 임시 디렉터리에 저장 후 삭제하며 API key와 signed URL을 로그에 남기지 않습니다. Job DB 생성이나 production eligibility 변경은 하지 않습니다.
- 사전 조건 테스트 4개 추가. Backend 261 tests 통과. 실제 Provider 호출은 실행하지 않았으므로 완료/성공으로 표시하지 않습니다.

## BUILD-00084 — Output Crash Residue Recovery

- Output 파일을 임시 파일에 기록하고 fsync한 직후 프로세스가 강제 종료되면 남는 숨김 임시 파일을 고아 파일 정리 대상에 포함했습니다.
- 애플리케이션이 생성하는 `.<job-id>.<32-hex-uuid>.tmp` 형식만 대상으로 제한해 운영자가 만든 임의 `.tmp` 파일은 삭제 후보에서 제외합니다.
- subprocess에서 `os.replace` 직전에 강제 종료하는 crash-injection 테스트를 추가하고 dry-run/보존기간/명시적 삭제를 검증했습니다.
- Backend 257 tests 통과. Viewer structural checks 19/19 통과. TypeScript typecheck는 npm 의존성 설치 timeout으로 미검증입니다.

## BUILD-00081 — 문서 버전 관리 체계 정리

- 제품 버전, 엔지니어링 빌드 ID, 문서 정책 버전, ADR 번호를 분리했습니다.
- 매 빌드마다 증가하던 별도 README/개발기록/인수인계 파일 생성을 중단하고 단일 최신 문서 + 누적 이력 방식으로 전환했습니다.
- 기존 버전별 문서 146개를 `docs/archive/legacy_snapshots/`에 원본 파일명으로 보존했습니다.
- 문서 인덱스, 버전 정책, 변경 이력, 개발 로그, 현재 인수인계, 빌드 정보 파일을 추가했습니다.
- 제품 기능 및 Backend/Viewer 동작은 변경하지 않았습니다.

## BUILD-00080 — Provider Output 계약 검증 (레거시 스냅샷)

- Provider 성공 응답의 Output URL 형식과 Output 최종 확정 메타데이터 검증을 강화했습니다.
- Backend 248 tests, compileall, Viewer 19/19, ZIP 무결성 검증 결과는 당시 기록 기준입니다.
- 상세 내용은 `archive/legacy_snapshots/README_v0_80.md` 및 `AI_CREATOR_STUDIO_개발진행기록_v0_80.md`를 참조하십시오.


## BUILD-00082 — Output 파일 생명주기 및 Lease 경합 안전성 강화

- Worker별 Output 저장 파일명을 Job 단위 고정 파일명에서 Poll Task/시도 단위 불변 파일명으로 변경했습니다. 만료된 이전 Worker가 새 Worker의 파일을 덮어쓰지 못합니다.
- Output 다운로드/저장 결과의 파일 키를 DB Output 레코드에 저장하고, 비공개 Output API는 DB가 참조하는 정확한 파일만 제공합니다.
- Lease를 잃은 Worker는 자신의 미확정 파일만 정리하고, 다른 Worker의 파일은 건드리지 않습니다.
- 프로세스 중단 후 남은 고아 파일은 DB 참조 키를 대조하는 명시적 정리 도구로 처리합니다. 기본은 dry-run이며 `--apply`를 명시해야 삭제합니다.
- Backend 250 tests, compileall, Viewer 19/19 검증 통과. SQLite 단일 호스트 범위이며 PostgreSQL/다중 서버 보증은 아닙니다.

## BUILD-00083 — Poll Output Lease 갱신 및 유지보수 잠금

- 대용량 Output 다운로드 중 Poll Task Lease를 주기적으로 갱신합니다. 갱신은 task/worker/status/phase/기존 만료시각을 모두 확인하며, 만료된 Lease는 되살리지 않습니다.
- Lease 갱신이 거부되면 진행 중인 다운로드를 취소하고, 기존 DB 최종 확정 fencing을 유지합니다.
- Poll Worker는 Output 다운로드부터 DB 참조 확정까지 같은 호스트의 공유 잠금을 보유합니다. 고아 파일 정리 명령은 참조 스냅샷과 삭제 전체에 배타 잠금을 사용해 같은 호스트 Worker와의 경합을 막습니다.
- Output artifact 운영 Runbook v0.1을 추가했습니다.
- Backend 254 tests, Python compileall, Viewer structural checks 19/19 통과. SQLite 단일 호스트/POSIX advisory lock 범위이며 다중 호스트·PostgreSQL 보증은 아닙니다.


## BUILD-00090 — AssetVersion / AssetRelation / Provenance

- `POST /v1/assets/{asset_id}/versions`로 새 GLB/GLTF 버전을 추가하고 현재 버전으로 승격합니다. 이전 버전 파일은 자산 삭제 전까지 불변 보존하며, `GET .../versions`에서 저장 경로 없이 메타데이터를 조회합니다.
- 업로드 시 v1 baseline을 자동 생성하고, 구형 자산은 초기화 시 v1 history로 backfill합니다. 버전 번호는 asset별 순차 증가하며 업로드/승격은 SQLite 트랜잭션으로 처리합니다.
- `POST/GET /v1/assets/{asset_id}/relations`로 `derived_from`, `variant_of`, `uses_texture`, `paired_with` 관계를 관리합니다. 자기 자신, 타 workspace 참조, 중복 관계를 거부합니다.
- `GET /v1/assets/{asset_id}/provenance`에서 upload, version, relation, delete 이벤트를 append-only 형태로 조회합니다. 모든 조회/변경은 workspace RBAC를 적용합니다.
- 자산 삭제 시 현재 및 이전 버전 파일을 함께 정리합니다. 브라우저/3D Viewer 통합 및 PostgreSQL 다중 호스트 보증은 아직 미검증입니다.
- Asset API tests 23 passed, Backend 전체 287 passed. OpenAPI/runtime 감사는 새 runtime-only routes를 반영해 갱신합니다.

## BUILD-00091 — Asset Version Restore

- `POST /v1/assets/{asset_id}/versions/{version_id}/restore` restores a selected historical GLB/GLTF as a new immutable version, never overwriting the source version. Restore requires private file existence, recorded size and SHA-256 match, and successful glTF validation.
- The restore operation serializes version numbering with SQLite `BEGIN IMMEDIATE`, promotes the new storage key, and appends `asset.version_restored` provenance including source version and prior current version. Missing/corrupt history fails closed without changing metadata.
- `GET .../versions` now includes `is_current`. The AssetWorkspace UI displays version history and provides restore controls for non-current versions, then refreshes the preview and history.
- Backend 290 passed (Asset API 26); Python compileall passed; Viewer structural checks 21/21 passed. TypeScript typecheck remains unverified because React/Three.js dependencies are absent; browser/WebGL/Android E2E remains unverified.

## BUILD-00092 — Image Asset Foundation and Photo Draft Preparation

- Added authenticated private PNG/JPEG/WebP image upload with Pillow format/extension checks, full decode, single-frame policy and bounded size/dimensions. Asset list supports `kind=all|model|image`; the 3D Viewer filters to models.
- Image assets now use the same integrity audit, private preview, immutable version and verified restore lifecycle. Version updates preserve asset kind.
- Added non-billable workspace-scoped Photo Draft create/list/read/update/archive/event APIs. Draft inputs validate source, mask and reference image assets; operation, output format/count and preservation options are constrained.
- Active Photo Draft references block image deletion until archive. Draft events are append-only.
- No Generation Job, quote, credit reservation, Provider request or output image is created. Actual Photo Engine processing remains unimplemented.
- Backend 302 passed (Asset API + Photo Draft 38); compileall passed; Viewer structural 22/22 passed. TypeScript/browser/WebGL remain unverified because React/Three.js dependencies are absent.

## BUILD-00093 — Lookbook Draft Preparation

- Added non-billable Lookbook Draft create/list/read/update/archive/event APIs, grouping product image assets with optional person image, active Project and Character references, scene preset and planned output count.
- Validates active same-workspace image assets, ACTIVE Project and active same-workspace Character. Active drafts protect referenced images, Projects and Characters from delete/archive transitions; archive releases active-reference protections while retaining history.
- Added `LookbookDraftWorkspace` UI and package export. The UI creates/archives draft compositions and explicitly states that generation, review/approval, export and credits are not executed.
- SKU/catalog, multi-product UI, generated outputs, review/approval/export remain unimplemented. Backend 307 passed (43 asset/photo/lookbook API tests); compileall passed; UI structural checks 30/30 passed. TypeScript/browser/WebGL remain unverified.

## BUILD-00094 — Draft API Pagination

- Added bounded `limit`/`offset` pagination and `total` metadata to Photo Draft and Lookbook Draft lists (1..100), preserving archived filtering.
- Added bounded pagination and total counts to both append-only draft event histories (1..500). Companion UIs request up to 100 active drafts.
- Backend 308 passed (44 asset/photo/lookbook API tests); compileall passed; Viewer/Photo/Lookbook structural checks 30/30 passed. TypeScript/browser/WebGL remain unverified because frontend dependencies are absent.

## BUILD-00095 — AssetRelation Graph Integrity

- `derived_from` relationship creation now rejects directed cycles using a recursive CTE. Relation writes serialize through SQLite `BEGIN IMMEDIATE` to prevent concurrent insertions from bypassing cycle checks.
- Relation creation appends `asset.relation_created` provenance to the source and `asset.relation_received` to the target. Existing relations and deletion/retention policies are unchanged.
- Backend 309 passed (45 asset/photo/lookbook API tests); compileall passed; Viewer/Photo/Lookbook structural checks 30/30 passed. PostgreSQL/multi-host and frontend runtime remain unverified.

## BUILD-00096 — Product / SKU Catalog

- Added workspace-scoped Product catalog CRUD/archive/events with 1..12 active same-workspace image assets and case-insensitive unique SKU per Workspace.
- Active Products protect image assets from deletion. Lookbook Drafts can reference catalog `product_ids` plus direct image assets; active Lookbook Drafts prevent Product archive until the draft is archived.
- Added `ProductCatalogWorkspace` and extended `LookbookDraftWorkspace` with multi-product catalog selection. Added a transactional migration to extend legacy Lookbook entity references while preserving existing Project/Character rows.
- Backend 314 passed (50 asset/photo/lookbook/product API tests); compileall passed; UI structural checks 35/35 passed. TypeScript/browser/WebGL remain unverified.
- Product variants, price/inventory, marketplace sync and actual generation remain unimplemented.

## BUILD-00097 — Product Variant / Option Catalog

- Added Product Variant persistence and create/list/update/archive APIs with independent variant SKU and normalized option values (e.g. color, size, fit).
- Product master SKU and Variant SKU share a case-insensitive Workspace namespace; transactional validation prevents cross-table collisions on create/update.
- Optional variant-specific image assets require active same-workspace image assets and are protected from deletion while referenced by an active Variant.
- Archiving a Product archives active child Variants in the same transaction. Historical records remain retained.
- Extended ProductCatalogWorkspace with basic color/size Variant creation and archive controls.
- Backend 317 passed; Python compileall passed; Viewer structural checks 37/37 passed. TypeScript/browser/WebGL remain unverified.
- Variant-aware Lookbook selection, price/inventory/barcode/marketplace sync and actual generation remain unimplemented.


## BUILD-00098 — Project ↔ Product Assignment

- Added workspace-safe Project/Product assignment read and replace APIs, preserving caller order and rejecting inactive or cross-workspace Products.
- Added retained assignment rows with soft removal and append-only events for additions, removals and reorder operations. Identical replace requests are idempotent.
- Active Project assignments block Product archive; archived Products are omitted from active Project product lists.
- Added ProjectProductAssignmentWorkspace UI for project selection, product assignment/order and history.
- Backend 320 passed; Python compileall passed; Viewer structural checks 40/40 passed. TypeScript/browser/WebGL remain unverified.


## BUILD-00099 — Variant-aware Lookbook Drafts

- Lookbook Drafts can now reference active Product Variants in addition to parent Products and direct images. Variant-specific images are resolved first; otherwise the parent Product gallery is used.
- Resolved image references are snapshotted and protected while the Draft is active. Both parent Product and Variant references are retained; active drafts block Product archive and Variant update/archive.
- Migrated Lookbook entity relation constraint to include `product_variant` while preserving prior entity rows.
- Extended LookbookDraftWorkspace with multi-select Variant selection.
- Backend 322 passed; Python compileall passed; Viewer structural checks 41/41 passed. TypeScript/browser/WebGL remain unverified. Lookbook generation, approval and export remain unimplemented.


## BUILD-00100 — Lookbook Planning Review / Approval

- Added DRAFT → IN_REVIEW → APPROVED / CHANGES_REQUESTED review state machine for Lookbook planning drafts. Workspace owner/admin approve or request changes; editor can submit; viewer is read-only.
- Change requests require a comment. Review events are append-only. Draft edits are locked during review and after approval; changes-requested drafts can be revised and resubmitted.
- Added an approved plan-only manifest that explicitly contains no generated outputs or image files.
- Added UI actions for submit, approve, request changes and manifest inspection.
- Backend 324 passed; Python compileall passed; Viewer structural checks 43/43 passed. TypeScript/browser/WebGL remain unverified. Actual image generation, output review and publication remain unimplemented.


## BUILD-00101 — Job Execution / Output History APIs

- Added authenticated, workspace-scoped execution attempt history with bounded limit and opaque cursor pagination.
- Added read-only Output metadata history; private storage keys/paths are never returned, and Outputs are listed only after Job success.
- Added repository read ports and SQLite adapter methods; unsupported repository implementations return HTTP 501 rather than fallback.
- Backend 325 passed; Python compileall passed; Viewer structural checks 43/43 passed.
- OpenAPI now has 3 unmatched design operations; 12 structural drifts remain. Output→Asset/AssetVersion/checksum/provenance linkage is not implemented.


## BUILD-00102 — Generation Output → Asset/Version/Provenance Linker

- Successful Output finalization now inserts a durable Generation DB link-outbox row in the same transaction. Added SHA-256 persistence and migration for legacy Output tables.
- Added independent Output Asset Link Worker. It validates and copies persisted images into private Asset storage, then creates immutable Asset, AssetVersion and Provenance records.
- Deterministic per-Output IDs and lease-fenced acknowledgement make crash recovery idempotent when Asset DB commit succeeds but Generation DB acknowledgement is lost. Separate SQLite DB tests cover this failure window.
- Output history exposes link status, checksum and linked Asset/Version/Provenance IDs, never storage paths. Diagnostics/event payloads redact storage keys. Generated-output Assets cannot be deleted through the ordinary Asset delete route.
- Added worker heartbeat and required worker configuration. Deployment now requires API, outbox worker, poll worker, output asset linker and monitoring worker.
- Backend 329 passed; Python compileall passed; Viewer structural checks 43/43 passed. TypeScript/browser/WebGL remain unverified. No live Provider call was made.


## BUILD-00103 — Failed Output Asset Link Retry / Audit

- Added owner/admin-only manual retry for terminally failed Output Asset links. A required reason and prior error/attempt count are recorded in an append-only event.
- Added read-only retry audit history endpoint. Only failed tasks can be retried; duplicate retry attempts are rejected.
- Reuses deterministic Output→Asset import and cross-DB recovery behavior.
- Backend 330 passed; schema migration and worker retry tests passed; Python compileall passed; Viewer structural checks 43/43 passed. TypeScript/browser/WebGL remain unverified.


## BUILD-00112 — Failure-Resilient Lookbook Export Retention Cleanup

- Hardened expired package cleanup against traversal, absolute/path separator tricks, symlinks and non-regular filesystem entries. Operations are anchored to the resolved private export directory using a directory file descriptor and non-following stat.
- Each expired package is handled independently. Missing files are reported; an unlink failure does not prevent later files from being processed. Partial failures return exit code 2 for operations monitoring.
- Dry-run remains the default. Apply removes only regular expired package files; immutable export audit rows are never changed.
- Added failure-injection tests for unlink permission errors, traversal, symlink targets, missing files, directories, dry-run/apply and audit retention.
- Backend pytest: 345 passed; compileall passed; Viewer structural checks: 65/65 passed. Browser/TypeScript runtime remains unverified.


## BUILD-00114

- Viewer ↔ Backend API source contract validation: 58/58 fetch call sites matched across 48 unique method/path combinations.
- Query parameter names are checked against OpenAPI operation declarations. Removed two unsupported/ignored `limit` query arguments from asset-list calls.
- TypeScript/browser/WebGL runtime checks remain unverified because npm dependency installation timed out and no browser harness is present.

## BUILD-00115 — Viewer Request Body Contract Audit

- Added static comparison of all 10 Viewer JSON request body call sites against runtime OpenAPI.
- Validated top-level body fields and required fields, including shorthand properties and dynamic review actions; 0 unknown fields, 0 missing required fields, 0 unresolved calls.
- Compared PhotoOperation and OutputFormat union values with runtime OpenAPI enums; exact matches.
- Added 2 validator regression tests and npm scripts for repeatable checks.
- Backend pytest 347 passed; Viewer URL/API checks 58/58; structural checks 65/65. TypeScript/browser runtime remains unverified.

## BUILD-00116

- Added explicit OpenAPI/Pydantic response contracts for generated output list/review and private Asset/AssetVersion preview URLs.
- Updated Viewer Output Review response declarations for nullable and additional backend fields.
- Added response contract regression tests and refreshed runtime OpenAPI snapshot.

## BUILD-00117 — Viewer Response Contract Coverage

- Viewer가 소비하는 48개 고유 API endpoint 중 JSON 성공 응답이 있는 47개 모두에 runtime OpenAPI response schema를 추가했습니다. HTTP 204 DELETE는 body가 없는 정상 동작으로 유지합니다.
- Asset/Version, Project, Character, Product/Variant, Project Product, Photo Draft/Run/Review, Lookbook Draft/Output/Review/Export/Manifest 응답 모델을 추가하고 실제 응답 envelope 차이를 별도 모델로 분리했습니다.
- Viewer response contract audit 및 회귀 테스트를 추가했습니다. 27개 response model, 미선언 schema/route/동적 경로 0건입니다.
- 기존 API 경로·요청·권한·업무 흐름은 변경하지 않았습니다. 전체 pytest는 355 passed summary를 보고했지만 프로세스 종료 지연으로 clean exit는 미확정입니다. TypeScript/browser/WebGL은 의존성 부재로 미검증입니다.


## BUILD-00119 — Viewer Runtime JSON Success Endpoint Coverage

- Added successful runtime integration tests for Photo output rejection and Lookbook output-assembly rejection.
- Added a reusable pytest response-capture plugin and a suite-level verifier that proves successful HTTP JSON execution across all 47 Viewer JSON success endpoints. The explicit DELETE 204 endpoint remains bodyless.
- Full backend suite: 359 passed; runtime coverage: 47/47; Viewer API contract 58/58; request contract 10/10; structural checks 65/65.
- Runtime application behavior unchanged. TypeScript/browser/WebGL/Android/PostgreSQL and production deployment remain unverified.


## BUILD-00120 — Offline TypeScript/TSX Syntax Validation

- Added a TypeScript `transpileModule` checker and `npm run validate:syntax` for all eight Viewer `.ts`/`.tsx` source files.
- Result: 8 files, 0 syntax/transpilation diagnostics under TypeScript 5.8.3.
- This is not full semantic type checking; React/Three.js dependencies and typings remain unavailable. No application behavior or dependency versions changed.


## BUILD-00121 — Viewer Package Integrity Guard

- Added an offline package-integrity validator for npm script targets, local imports/stylesheets, declared third-party dependencies, public entrypoint exports and TypeScript source inclusion.
- Added regression tests for missing local imports, undeclared external dependencies and broken npm script targets; 4 tests pass.
- Made the TypeScript syntax/transpilation check recursive so nested source files cannot be silently skipped.
- Full backend suite: 359 passed; Viewer runtime JSON coverage: 47/47; API contract: 58/58; request contract: 10/10; structural checks: 65/65.
- Chromium is installed, but this headless execution environment exposes neither WebGL nor WebGL2. Actual Viewer browser/WebGL execution remains unverified. PostgreSQL driver/server tooling and React/Three.js dependencies remain unavailable.


## BUILD-00122 — Feature Scope and Documentation Alignment

- Added a single current feature-scope matrix distinguishing implemented workflows from explicitly unimplemented or unverified capabilities.
- Corrected stale Viewer/Backend README descriptions: Photo local processing and review, Product Variants, Lookbook planning approval, approved Photo output assembly, separate assembly review, and internal-only package/manifest export are now accurately described.
- Preserved historical BUILD-00093/00096 scope notes as historical rather than rewriting past build evidence.
- Updated project entrypoint and docs index to point at the current scope matrix and BUILD-00122 verification.
- No application code, API behavior, dependency versions, or database schema changed.


## BUILD-00123 — Browser WebGL2 Capability Probe

- Added an optional Playwright/Chromium probe that compiles and renders a WebGL2 triangle, then checks ResizeObserver and requestAnimationFrame.
- Added optional pinned browser-audit dependency metadata and `npm run probe:browser-runtime`; no runtime app dependencies changed.
- Verified Chromium 144 under Xvfb/SwiftShader: WebGL2 context available, triangle pixel readback passed, ResizeObserver passed, requestAnimationFrame passed.
- This verifies browser-engine capability only. React/Three.js packages remain unavailable, so actual Viewer E2E and GLTF model rendering are still not claimed.


## BUILD-00124 — Product Variant Image Management

- Product Catalog UI now allows up to 12 variant-specific image Asset references when creating a Variant, editing an existing Variant, or clearing its image override to fall back to the parent Product gallery.
- Added Variant edit flow using the existing `PUT /v1/products/{product_id}/variants/{variant_id}` endpoint; additional option-value keys are preserved when the UI edits color/size fields.
- Updated Viewer API/request/response contract evidence: 59/59 fetch calls matched; 11 JSON request bodies checked; 48 JSON response endpoints across 49 method/path endpoints; 0 missing routes/schemas.
- Backend full suite: 359 passed; runtime Viewer HTTP JSON coverage: 48/48; Viewer structural checks: 68/68; syntax/transpilation: 8 files, 0 diagnostics.
- No new backend route or schema change; existing backend Variant validation and Lookbook image-resolution tests cover the behavior.


## BUILD-00125 — Product Catalog Edit Workflow

- Product Catalog UI now edits existing Product SKU, name, description, category and ordered image references through the existing `PUT /v1/products/{product_id}` endpoint.
- Added edit/cancel flow and retained create/archive operations. Backend conflict responses continue to protect Products referenced by active Lookbook drafts.
- Updated Viewer API/request/response coverage: 60/60 fetch calls, 12 JSON request bodies, 49 JSON response endpoints across 50 method/path endpoints, 0 missing contract entries.
- Backend full suite 359 passed; runtime Viewer JSON coverage 49/49; Viewer structural checks 70/70; TypeScript syntax/transpilation 8/0; Viewer scripts 8 passed.
- No new backend route or schema was introduced; existing Product update integration tests exercise the route.


## BUILD-00126 — Project Workspace Management

- Added a new exported `ProjectWorkspace` React component for workspace-scoped project creation, listing, editing, completion, archival and reactivation.
- Project state changes use the existing PUT API; active Lookbook project references remain protected by backend 409 guards. External reference is visible but read-only after project creation because the backend update schema does not support changing it.
- Added responsive styles and integration documentation.
- Updated Viewer contract coverage: API 63/63, request bodies 15 checked, response schemas 51 JSON endpoints / 52 total method/path endpoints, runtime JSON coverage 51/51.
- Backend full suite 359 passed; Viewer scripts 8 passed; structural checks 75/75; TypeScript syntax/transpilation 9 files / 0 diagnostics.
- No backend route/schema or dependency version changed.


## BUILD-00127 — Custom Product Variant Options

- Product Catalog now lets users add, edit and remove custom Variant option key/value pairs in addition to the standard color and size fields.
- Custom keys are normalized to lowercase and checked against backend rules (1–40 characters, alphanumeric/underscore only); values are limited to 80 characters; reserved color/size keys and duplicates are rejected.
- Enforces the backend maximum of 12 option values before save and retains custom values when editing existing Variants.
- No backend route/schema, API contract, dependency version or database schema changed.
- Backend full suite 359 passed; runtime Viewer JSON coverage 51/51; API contract 63/63; request body contract 15 checked; response schema audit 51 JSON / 52 total endpoints; structural checks 76/76; Viewer script tests 8 passed; package integrity 0 findings; TypeScript syntax/transpilation 9 files / 0 diagnostics.


## BUILD-00128 — UI Edit-State Consistency

- Project status actions now synchronize the currently open Project edit form, preventing a later save from silently reverting a completion/archive/reactivation action.
- Product archive clears an edit form for that Product and any Variant form scoped to it; Variant archive clears its own edit form.
- Variant custom option values are trimmed and validated as non-empty, at most 80 characters before sending the existing API request.
- No backend route/schema, API contract, dependency version or database schema changed.
- Backend full suite 359 passed; runtime Viewer JSON coverage 51/51; API contract 63/63; request bodies 15 checked; response schema 51 JSON / 52 total; structural checks 79/79; Viewer scripts 8 passed; package integrity 0 findings; TypeScript syntax 9 files / 0 diagnostics; browser capability probe passed.


## BUILD-00129 — Workspace Request Race Protection

- ProjectWorkspace and ProductCatalogWorkspace now abort their initial effect-owned fetches on unmount or workspace/token changes.
- Both workspaces use monotonically increasing load sequence IDs and current workspace/access-token scope checks before applying responses, preventing stale requests from a previous workspace or earlier refresh from overwriting current data.
- No API routes/schemas, backend behavior, dependency versions or database schema changed.
- Backend full suite 359 passed; runtime Viewer JSON coverage 51/51; API contract 63/63; request bodies 15 checked; response schema 51 JSON / 52 total; structural checks 81/81; Viewer scripts 8 passed; package integrity 0 findings; TypeScript syntax 9 files / 0 diagnostics; browser capability probe passed.

## BUILD-00132 — Selection-Level Async Race Protection
- Asset preview and version-history selection reads now abort on supersession and reject stale responses after scope changes, deletion, or unmount.
- Lookbook draft manifest and output-assembly reads now use request sequencing to prevent stale draft selections from replacing current UI state.
- Structural validation increased to 107 checks; backend full suite 359 passed.

## BUILD-00135 — Lookbook Archive State Integrity

- Centralized Lookbook output-assembly dependent-state cleanup and request invalidation.
- Archiving the currently open assembly draft now invalidates in-flight assembly hydration and planning manifest reads, then clears the selected draft, approved Photo runs, attached outputs, preview URLs, selections, page/caption fields, output manifest, internal package export and assembly-review state.
- Closing the assembly panel and changing workspace/API/token scope reuse the same complete teardown path.
- Archive remains non-destructive; historical immutable records are retained.
- No backend routes/schemas, migrations, dependency versions, public props, Provider calls, credit behavior, publication or rights grants changed.
- Backend full suite 359 passed; structural checks 116/116; RequestScopeGate behavioral assertions 7 passed; TypeScript syntax 10 source files + declaration / 0 errors; API contract 63/63; request contract 15 checked; response contract 51 JSON / 52 endpoints; Viewer script tests 2 passed; package integrity 0 findings.


## BUILD-00136 — Photo Draft & Output Review State Integrity

- Added latest-request-wins preview hydration per immutable AssetVersion in Photo Draft and invalidated pending preview requests on workspace/API/token scope changes.
- Serialized Photo Draft review/archive/manifest mutations and Output Review decisions/manifest exports to prevent rapid duplicate or conflicting UI transitions.
- Structural checks 122/122; KeyedRequestGate 7 assertions; RequestScopeGate 7 assertions; backend full suite 359 passed.

## BUILD-00137 — Asset Restore & Project Assignment State Integrity

- Successful AssetVersion restore now invalidates the previous selection request and clears the old signed preview URL and version history before rehydrating the restored current version.
- Project Product Assignment now clears the previous project's selected products and event history immediately on project change, aborts/invalidates stale reads, and rejects stale errors. Catalog reconciliation also clears assignments when the selected project is no longer active/available.
- No backend routes/schemas, migrations, dependency versions, or public component props changed.
- Structural checks 126/126; KeyedRequestGate 7 assertions; RequestScopeGate 7 assertions; TypeScript syntax 10 source files + 2 declarations / 0 errors; API contract 63/63; request bodies 15 checked; response contract 51 JSON / 52 endpoints; two Viewer test suites passed; package integrity 0 findings; backend full pytest 359 passed.


## BUILD-00138 — Project Lifecycle UI Synchronization

- Added a dependency-free same-tab project lifecycle event helper shared by Project Workspace, Project Product Assignment and Lookbook Draft workspaces.
- Project edits and lifecycle status changes publish workspace-scoped notifications after successful API mutations.
- Project Product Assignment refreshes active projects on matching lifecycle events; when the selected project is no longer ACTIVE, dependent assignment selections/history are invalidated and an active project is selected.
- Lookbook Draft refreshes active project references and clears a selected project that is no longer active. Its multi-resource hydration now uses latest-request-wins protection before response error parsing and state application.
- Added 4 executable lifecycle-event assertions and 7 structural assertions.
- No backend routes/schemas, migrations, external dependencies, Provider calls, credit behavior, publication or rights behavior changed.
- Backend full suite 359 passed; structural checks 133/133; TypeScript syntax 10 sources + 3 declarations / 0 errors; API contract 63/63; request bodies 15 checked; response schema 51 JSON / 52 total; Viewer pytest suites 8 passed; package integrity 0 findings.


## BUILD-00139 — Immutable AssetVersion Preview Recovery

- Photo Draft now tracks per-version preview loading/errors/expiry, stores signed URL `expires_at`, and exposes explicit refresh/retry for source and processed output versions.
- Failed image loading invalidates only the still-current URL for the exact `asset_id:version_id`, clears it and offers a fresh signed URL request.
- Output Review now shows per-output preview failures, missing immutable version links and signed URL expiry; users can explicitly reissue a preview for the exact asset/version in the review record.
- Keyed preview request sequencing prevents a late automatic Output Review preview hydration from overwriting a newer manual retry.
- No backend routes/schemas, migrations, dependencies, Provider calls, credit behavior, publication or rights behavior changed.
- Backend full suite 359 passed; structural checks 140/140; TypeScript syntax 10 sources + 3 declarations / 0 errors; API contract 63/63; request bodies 15 checked; response schema 51 JSON / 52 total; Viewer pytest suites 8 passed; package integrity 0 findings.

## BUILD-00142 — Private ZIP Download Authorization & Cleanup Observability
- Signed Lookbook ZIP downloads now require current workspace membership and a permitted role in addition to HMAC URL validation; Viewer sends Bearer auth.
- Reject symlink/non-regular ZIP entries before integrity checks.
- Add machine-readable cleanup duration, limit, candidate, outcome, partial-failure and audit-retention fields; dry-run remains default.
- Verification: backend 361 passed; structural 140; API 64/64; syntax 10+4; browser capability smoke PASS; semantic TS and actual component E2E remain blocked/unverified.


## BUILD-00143 — Descriptor-Pinned Private File Delivery
- Added a shared descriptor-pinned streaming helper for private local files, with `O_NOFOLLOW` where available, regular-file `fstat`, optional descriptor-based size/SHA-256 verification and streaming from the same open descriptor.
- Migrated private AssetVersion previews, asset previews, generation output downloads and Lookbook ZIP downloads away from path-based `FileResponse`.
- Added pathname-replacement race, symlink, checksum mismatch and non-regular-file tests.
- Backend full suite 365 passed; Viewer runtime coverage 52/52; API 64/64; request bodies 15 checked; response schema 52 JSON / 53 total; TypeScript syntax 10+4; package integrity 0 findings.


## BUILD-00146 — Bounded Authenticated GLTF Downloads & Recovery

- Enforced a 256 MiB maximum for authenticated model downloads using Content-Length preflight and streamed-byte accounting; cancel over-limit streams and retain abort handling.
- Added actionable safe recovery guidance for 401/403/404/409 and file-size/network/stream failures without exposing raw server details, model URLs or tokens.
- Added 15 bounded-download structural assertions and a dedicated npm test script.
- Backend full suite 367 passed; bounded GLTF 15/15; authenticated GLTF 9/9; Viewer API 63/63; request bodies 15 checked; response contract 50 JSON / 52 total; syntax 10+5; package integrity 0 findings. Browser E2E and semantic TypeScript remain unverified.

## BUILD-00147 — Executable Bounded GLTF Stream Reader
- Extracted bounded authenticated model response reading into a dependency-free `.mjs` module and typed declaration; added executable Fetch/ReadableStream tests for limits, cancellation, abort, truncation and status mapping.
- Backend 367 passed; bounded runtime 9/9; API 63/63; request body 15/0 findings; response 50 JSON / 52 total / 28 models; TypeScript syntax 10+6; package integrity 0 findings.

## BUILD-00148 — Bounded GLTF Download Memory & Header Validation
- Known Content-Length responses now stream directly into one exact-size destination buffer; malformed, negative, fractional and empty Content-Length values fail closed.
- Backend 367 passed; bounded runtime 12/12; structural 16/16; authenticated GLTF 9/9. Browser E2E, semantic TypeScript and target-device memory remain unverified.

## BUILD-00149 — Unknown-Length GLTF Buffer Growth Hardening
- Replaced unknown-length stream chunk retention plus final assembly copy with a capped 64 KiB-start geometric-growth accumulator (maximum 256 MiB); exact-capacity results reuse the backing store.
- Known-length allocation failure cancels the unlocked response body; unknown-length growth failure cancels the active reader. Both return a typed `memory` error with actionable UI guidance.
- Backend 367 passed; bounded runtime 16/16; structural 19/19; authenticated GLTF 9/9; API 63/63; request body 15/0 findings; response 50 JSON / 52 total / 28 models; syntax 10+6; package integrity 0 findings.
- Browser E2E, semantic TypeScript and target-device memory profiling remain unverified.

## BUILD-00152 — Complete GLTF Resource Lifecycle Disposal
- Added cycle-safe disposal across all GLTF scenes, nested material textures, shared materials and geometries.
- Viewer retains the complete GLTF result and cleans it up on replacement, cancellation completion, and renderer teardown.
- GLTF disposal 11 assertions; authenticated GLTF structural 11/11; backend 367 passed; existing viewer, API and contract regressions passed.
- Semantic typecheck blocked by missing React/Three packages; actual component rendering and device memory profiling remain unverified.


## BUILD-00153 — Viewer GPU Resource Lifecycle Completion
- Extended GLTF cleanup to dispose shared skinned-mesh skeleton resources exactly once.
- Moved viewer floor/grid into a dedicated stage-resource group and explicitly disposes its GPU resources even when a model is loaded.
- Explicitly disposes the directional light shadow target and uncaches animation mixer roots during replacement/teardown.
- Added 3 skeleton runtime assertions and 4 authenticated GLTF structural checks; disposal runtime 14 assertions, authenticated GLTF 15/15.
- Backend 367 passed; bounded download 17 runtime/19 structural; API 63/63; request/response contracts clean; TypeScript syntax 10+8/0; package integrity 0 findings. Chromium WebGL2 capability smoke passed under Xvfb/SwiftShader.
- Semantic typecheck remains blocked by absent React/Three dependencies; actual React/Three rendering and target-device memory remain unverified.


## BUILD-00155 — Viewer Renderer Teardown Resilience
- Added a dependency-free, failure-isolated cleanup-step runner with structured attempted/completed/error diagnostics.
- Applied ordered best-effort cleanup to renderer teardown and model replacement so one throwing cleanup operation cannot suppress later resource release.
- Added 10 runtime failure-injection assertions and 13 lifecycle-order structural checks; backend 367 passed; viewer/API contracts and syntax/package checks passed.
- Browser WebGL2 capability smoke passed under Xvfb/SwiftShader; React/Three E2E and semantic typecheck remain unverified/blocked by missing dependencies.
