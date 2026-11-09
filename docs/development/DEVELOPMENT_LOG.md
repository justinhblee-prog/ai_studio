# 개발 진행 기록

## BUILD-00081 — 문서 버전 관리 체계 정리

### 문제

기존에는 코드 스냅샷을 `v0.80`처럼 증가시키는 동시에 인수인계 문서는 `v5.40`처럼 별도 증가시켰습니다. README와 개발기록도 버전별 복제되어 프로젝트 루트에 146개의 문서 파일이 누적됐습니다. 서로 다른 번호가 무엇을 의미하는지 정의되어 있지 않고, 어느 문서가 현재 기준인지 한눈에 알기 어려웠습니다.

### 변경

- 제품 버전(SemVer), 엔지니어링 빌드 ID, 문서 정책 버전, ADR 번호를 독립시켰습니다.
- 프로젝트 공통 문서를 `docs/`로 이동하고 역할별 디렉터리를 만들었습니다.
- 이전 버전별 문서 146개를 `docs/archive/legacy_snapshots/`로 이동했으며 파일명과 본문은 변경하지 않았습니다.
- `README.md`, `docs/CHANGELOG.md`, `docs/development/DEVELOPMENT_LOG.md`, `docs/handoff/CURRENT_HANDOFF.md`를 단일 기준 문서로 설정했습니다.
- 빌드별 고정 문서는 필요한 경우에만 `docs/releases/BUILD-xxxxx.md`로 생성하도록 했습니다.
- `BUILD_INFO.md`를 추가해 ZIP 단위 추적 정보를 제공합니다.

### 기능 영향

문서와 파일 배치만 변경했습니다. Backend/Viewer 소스 및 런타임 동작은 변경하지 않았습니다.

### 검증 계획

- Backend 전체 테스트
- Python compileall
- Viewer 구조 검사
- Markdown 링크/문서 인덱스 대상 존재 검사
- ZIP 무결성 및 SHA-256


### 검증 결과

- Backend pytest: 248 passed
- Python compileall: passed
- Viewer structural validation: 19/19 passed
- 프로젝트 공통 Markdown 링크 검사: passed (7개 기준 문서)
- ZIP 무결성: passed


## BUILD-00082 — Output 파일 생명주기 및 Lease 경합 안전성 강화

### 감사에서 확인한 문제

- 기존 Output 저장소는 `{job_id}.{extension}` 고정 파일명을 사용하고 `os.replace`로 교체했습니다. DB 최종 확정은 Lease를 확인했지만, 파일 쓰기 자체는 DB Lease와 결합되지 않아 만료된 Worker가 늦게 저장하면 새 Worker의 파일을 덮어쓸 수 있었습니다.
- 프로세스가 파일 저장 직후 DB 확정 전에 종료되면 파일시스템에 참조되지 않는 파일이 남을 수 있었습니다.
- Output API가 Job ID로 파일을 추론했기 때문에 DB가 실제 확정한 storage_key와 디스크 파일의 직접 대응이 약했습니다.

### 변경

- `save_provider_output_artifact`를 추가하고 `Job ID + Poll Task ID + attempt count + random artifact token` 기반의 고유 파일 키를 생성합니다. 파일은 시도별로 불변이며 다른 Worker 시도와 경로가 겹치지 않습니다.
- Poll Worker는 저장된 storage_key를 받아 Output Repository에 전달합니다. Lease 검증 및 Job/Execution/Event/Output/Poll Task의 DB 원자 확정은 기존 트랜잭션 경계를 유지합니다.
- 최종 확정에 실패한 Worker는 자신이 생성한 고유 파일만 삭제합니다. 다른 시도의 파일을 덮어쓰거나 삭제할 수 없습니다.
- Output API는 DB의 `generation_outputs.storage_key`가 존재해야만 해당 파일을 읽습니다. DB 참조가 없으면 legacy deterministic 파일로 fallback하지 않습니다.
- `list_output_storage_keys` 및 `cleanup_orphaned_attempt_outputs`를 추가했습니다. `scripts/cleanup_orphaned_outputs.py`는 기본 dry-run이며 `--apply`가 있어야 실제 삭제합니다. 참조된 키와 최근 파일은 보존합니다. 자동 실행하지 않습니다.
- 구형 테스트 seam을 새 attempt-artifact API에 맞춰 조정하고, 서로 다른 시도 파일의 비덮어쓰기, DB 참조 파일 보존, orphan dry-run/삭제, 파일 키 경로 검증을 추가했습니다.

### 검증

- `python -m pytest -q`: 250 passed
- `python -m compileall -q app scripts tests`: passed
- `python scripts/validate_source.py`: 19/19 passed
- ZIP integrity: passed (final packaging)

### 제한 및 주의

- SQLite 단일 호스트 환경에서 검증했습니다. 다중 호스트 파일시스템 및 PostgreSQL 환경에서의 Lease/스토리지 경합은 미검증입니다.
- SQLite와 파일시스템은 하나의 원자 트랜잭션이 아닙니다. DB 확정 전 프로세스가 종료되면 고아 파일이 남을 수 있으므로 정리 도구는 운영자가 검토 후 실행해야 합니다.
- cleanup은 참조 키 스냅샷을 읽고 파일을 지우는 사이의 race-free distributed GC가 아닙니다. 실행 시 Worker를 정지하거나 충분한 보존기간을 두는 운영 절차가 필요합니다. 자동 background cleanup으로 취급하지 않습니다.

## BUILD-00083 — Poll Output Lease 갱신 및 유지보수 잠금

### 변경 배경

BUILD-00082에서 Output을 Poll Task/시도별 불변 artifact로 분리했지만, 긴 Output 다운로드 동안 Lease를 갱신하지 않아 90초 기본 Lease보다 다운로드가 오래 걸리면 유효한 Worker가 lease를 잃을 수 있었습니다. 또한 cleanup과 Worker 사이의 같은 호스트 파일 경합을 조정할 운영 잠금이 없었습니다.

### 구현

- `PollRepository.renew_poll_task_lease` 계약 및 SQLite 구현을 추가했습니다. `processing`, `persist_output`, worker ID 일치, 현재 Lease 미만료 조건을 한 UPDATE에서 검사합니다. 만료된 Lease는 부활시키지 않습니다.
- Poll Worker는 Output 다운로드 중 주기적으로 Lease를 갱신합니다. 갱신 실패 시 다운로드 task를 취소하고, 기존 finalization transaction의 fencing을 유지합니다.
- `output_storage_lock`을 추가했습니다. Worker는 다운로드 시작부터 Output DB 참조 확정까지 shared lock을 보유합니다. cleanup은 reference snapshot과 삭제 동안 exclusive lock을 보유합니다.
- Output 유지보수 Runbook v0.1을 추가했습니다.
- 회귀 테스트: lease owner mismatch, expired lease non-resurrection, lease loss download cancellation, 별도 프로세스 간 shared/exclusive lock serialization.

### 검증

- Backend `python -m pytest -q`: **254 passed**
- `python -m compileall -q app scripts tests`: passed
- Viewer `scripts/validate_source.py`: **19/19 passed**

### 제한

- SQLite 단일 호스트 및 POSIX advisory lock 기반 검증입니다. NFS, 다중 호스트, PostgreSQL, object storage, 분산 GC는 미검증입니다.
- Advisory lock은 협력적이므로 모든 writer/cleanup process가 동일 프로토콜을 사용해야 합니다.
- 파일시스템과 SQLite의 원자성은 보장하지 않습니다.



## BUILD-00084 — Output crash residue recovery

- 발견: `save_provider_output_artifact`는 숨김 임시 파일을 생성한 뒤 fsync 및 atomic replace를 수행합니다. 프로세스가 fsync 후 replace 전에 강제 종료되면 기존 orphan cleanup 패턴(`*.attempt-*.*`)에 매칭되지 않는 숨김 `.tmp` 파일이 잔류합니다.
- 수정: cleanup이 애플리케이션 생성 규칙과 일치하는 `.<job-id>.<32-hex-uuid>.tmp` 파일만 age-gated candidate로 검색하도록 했습니다. 임의 숨김 `.tmp`는 제외합니다.
- 테스트: subprocess에서 `os.replace` 직전에 `os._exit(73)`을 호출해 실제 프로세스 종료 후 temp residue가 남는 상황을 만들고 dry-run 및 `apply=True` 삭제를 검증했습니다. 별도 테스트로 fresh temp와 unrelated hidden temp 보호를 검증했습니다.
- 검증: `python -m pytest -q` 257 passed; `python -m compileall -q app scripts tests` 통과; Viewer source structural validation 19/19 통과.
- 제한: npm install이 실행 환경에서 timeout되어 React/Three.js TypeScript typecheck 및 Browser/WebGL 실환경 검증은 미완료. FASHN API key가 런타임 환경에 설정되지 않아 실제 Provider 생성 호출도 실행하지 않았으며 Mock 결과를 실사용 성공으로 취급하지 않았습니다.


## BUILD-00085 — Cost-gated live FASHN sandbox harness

- 실제 Provider 검증을 진행할 수 있는 안전한 opt-in CLI `ai_creator_studio_backend_starter/scripts/live_fashn_smoke.py`를 추가했습니다.
- 명시적 비용 확인(`FASHN_LIVE_TEST_CONFIRM_COST`), FASHN API key, 권한 있는 HTTPS model/garment 입력 URL이 없으면 외부 호출을 시작하지 않습니다.
- 실행 시 Provider start/status를 직접 호출하고, 성공 output을 임시 디렉터리로 다운로드해 실제 이미지 시그니처/바이트를 검증한 뒤 삭제합니다. API key 및 signed URL은 로그에 남기지 않습니다.
- 이 sandbox harness는 Job/Outbox/DB finalization 전체 E2E가 아니며 production Provider registry gate를 열지 않습니다. Rights, retention, commercial-use review도 별도입니다.
- 4개 preflight-only tests 추가; 이 테스트들은 외부 Provider를 호출하지 않습니다. `python -m pytest -q`: 261 passed.
- 현재 환경에는 FASHN API key 및 승인된 입력 자산이 없어 live request를 실행하지 않았습니다. 따라서 actual generation remains NOT VERIFIED.


## BUILD-00086 — Product scope recovery and core workflow coverage

- Library reference recovery: Requirements Traceability Matrix v1.0, Common Data Model Dictionary v0.1, Backend Implementation Blueprint v0.1, OpenAPI Integrated Draft v0.2, OpenAPI/DTO Schema Mapping Audit v0.1, Job State Transition Fixture v0.1을 `docs/product-baseline/`에 보존했습니다. 문서가 구현 증거로 오인되지 않도록 baseline README와 coverage audit를 추가했습니다.
- Project: Workspace RBAC 기반 Project create/list/read/update를 구현했습니다. Project deletion, SKU, ProjectAssetRelation은 삭제/소유권/중복 정책 미결정으로 추가하지 않았습니다.
- Job listing: SQLite Job Repository에 workspace-scoped paginated list를 추가하고 viewer read 권한 및 pagination 경계를 테스트했습니다.
- Contract audit: OpenAPI draft와 runtime route inventory를 `/v1` prefix 정규화 후 비교하는 script를 추가했습니다. 6개 design-only path, 17개 runtime-only path, 3개 method gap이 확인됐습니다. Body/response shape 검사는 별도 필요합니다.
- Product scope audit는 STR/PRD/TECH/OPS 및 G0~G5를 PARTIAL/NOT IMPLEMENTED/NOT VERIFIED로 구분했습니다. G0~G5를 PASS로 승격하지 않았습니다.
- Verification: Backend pytest 272 passed; Python compileall passed; Viewer source structural validation 19/19 passed.


## BUILD-00087 — Queued Job cancellation 및 상태 추적

### 변경 배경

- 제품 범위 감사에서 Generation Job cancellation이 미구현으로 남아 있었습니다.
- Outbox dispatch는 별도 Worker가 claim하므로 API에서 단순히 Job 상태만 바꾸면 이미 claim된 Provider 제출과 경합할 수 있습니다.

### 구현

- `POST /v1/generation-jobs/{job_id}/cancel`을 추가했습니다. Workspace `owner`/`admin`/`editor`만 호출할 수 있습니다.
- Repository가 단일 SQLite write transaction에서 Job이 `queued`인지, 최신 `SUBMIT_GENERATION` 이벤트가 `pending`인지 확인합니다. 둘 다 맞을 때 Job/Execution을 종료하고 Outbox를 `processed`로 마감하며 append-only Event를 기록합니다.
- Outbox가 `processing`/`needs_reconciliation`이거나 Job이 이미 실행/종료 상태라면 409로 거부합니다. Provider 제출이 이미 시작된 경우를 취소 성공으로 오인하지 않도록 제한했습니다.
- 기존 SQLite status CHECK를 무계획하게 바꾸지 않기 위해 현재 저장 상태는 `failed` + `error_code=JOB_CANCELLED`로 표현합니다. 별도 `cancelled` 상태 도입은 전용 schema migration과 API contract 버전업 시 처리해야 합니다.
- Cancellation reason은 최대 500자이며 Event payload에 기록됩니다.

### 검증

- 신규 cancellation 테스트 4개 통과: pre-dispatch cancel 및 Job/Execution/Outbox/Event 일관성, workspace RBAC, outbox claim 경합 방어, payload validation.
- Backend 전체: 276 passed. Python compileall passed. Viewer structural validation 19/19 passed.
- OpenAPI route inventory: cancellation path가 design/runtime 양쪽에 존재함을 확인. Design-only path 5, runtime-only path 17, method gaps 3; exact match false.

### 제한

- 이 API는 Provider dispatch 전 취소만 지원합니다. Running Provider 요청 취소, 비용 보상, 부분 과금은 구현하지 않았습니다.
- `failed` + `JOB_CANCELLED`는 현재 DB 상태 제약을 보존하기 위한 호환 표현입니다. UI는 `error_code`를 확인해 취소로 표시해야 합니다.
- SQLite 단일 호스트 테스트이며 PostgreSQL 및 multi-host race는 미검증입니다.


## BUILD-00088 — OpenAPI schema contract audit

### 변경 배경

- BUILD-00087 route inventory audit는 path/method 일치만 확인했습니다. 실제 API request/response field shape, status code, pagination, operationId의 차이는 확인하지 못했습니다.

### 구현

- `scripts/audit_openapi_contract.py`를 추가했습니다. Design YAML과 FastAPI `app.openapi()`를 비교하고 local schema/response component references를 해석합니다.
- 비교 대상은 request body schema, 2xx response schema/status, business parameters, operationId입니다. Authorization header는 business parameter가 아닌 authentication transport로 취급해 비교에서 제외합니다.
- `BUILD-00088_openapi-contract-drift.json` 및 generated runtime OpenAPI snapshot `BUILD-00088_runtime-openapi.json`을 생성합니다.
- Audit는 구조적 차이를 보고할 뿐 semantic equivalence, authorization semantics 또는 runtime payload conformance를 증명하지 않습니다. Design baseline YAML은 변경하지 않았습니다.

### 초기 결과

- 15 matched design operations 중 10개에 구조적 drift가 있고 5개 design operations는 runtime에 없습니다. 주요 차이는 generic feature/quote Job request와 Try-on-specific runtime request, enveloped response와 flat/list response, cursor와 offset pagination, cancellation 202/Idempotency-Key design과 runtime 200/optional reason body입니다.
- 2개 audit tests 추가. 상세 field-level evidence는 JSON report에서 확인합니다.

## BUILD-00090 — AssetVersion / AssetRelation / Provenance

### 변경

- Asset upload 시 `asset_versions` v1 baseline과 `asset_provenance` upload event를 생성합니다. 기존 자산은 schema initialization에서 현재 metadata를 v1로 backfill합니다.
- `POST /v1/assets/{asset_id}/versions`는 GLB/GLTF를 동일한 보안 검증 경로로 검증하고 새 immutable storage key에 저장한 뒤 version metadata와 현재 Asset pointer를 트랜잭션으로 승격합니다. 이전 버전 바이트는 보존합니다.
- `GET /versions`는 저장소 내부 키를 제외한 버전 메타데이터를 반환합니다.
- `POST/GET /relations`는 workspace 내부 typed relation을 제공합니다. 허용 타입은 `derived_from`, `variant_of`, `uses_texture`, `paired_with`; self-link, cross-workspace, duplicate를 차단합니다.
- `GET /provenance`는 upload/version/relation/delete 이력을 pagination으로 반환합니다. provenance row는 append-only로 사용하며 수정/삭제 API는 제공하지 않습니다.
- Asset soft-delete 시 모든 버전의 실제 파일을 함께 삭제해 저장소 잔여 파일을 방지합니다.

### 검증

- `PYTHONPATH=. pytest -q`: 287 passed
- Asset API: 23 passed
- `python -m compileall -q app scripts tests`: passed
- Viewer structural checks: 19/19 passed
- OpenAPI route inventory/schema audit regenerated; 13 design paths vs 29 runtime paths, 10 schema drifts and 5 unmatched design operations remain

### 제한

- Version 승격은 SQLite + local filesystem PoC 범위입니다. DB commit과 filesystem write는 단일 원자 트랜잭션이 아니므로 프로세스 강제 종료 시 고아 파일 가능성이 남습니다.
- PostgreSQL, object storage, distributed locking, browser/WebGL E2E는 검증하지 않았습니다.

## BUILD-00091 — Asset Version Restore

### Implementation

- Added `restore_asset_version` and authenticated `POST /v1/assets/{asset_id}/versions/{version_id}/restore`.
- Restore reads the historical file from the private root, verifies path containment, recorded size, SHA-256 using constant-time digest comparison, and re-runs strict GLB/GLTF validation before creating a new version.
- Under `BEGIN IMMEDIATE`, it rechecks the active Asset and source version, allocates the next version number, writes a fresh attempt-unique storage key, updates the Asset current pointer, inserts the version row, and appends `asset.version_restored` provenance. Any caught failure rolls back metadata and removes the newly created file.
- Historical files are read-only and preserved. A missing/corrupt file returns 409 with `ASSET_VERSION_INTEGRITY_FAILED`; unknown asset/version returns 404; viewer role is denied with 403.
- `GET /versions` includes a boolean `is_current` derived from the current Asset storage pointer. No storage key is exposed.
- AssetWorkspace now loads version history and exposes restore buttons only for non-current versions. On success it refreshes the asset listing, signed preview URL, and version history.

### Verification evidence

- Baseline BUILD-00090 suite: 287 passed.
- Final `python -m pytest -q`: 290 passed; Asset API tests: 26 passed.
- `python -m compileall -q app scripts tests`: passed.
- `python ai_creator_studio_3d_viewer/scripts/validate_source.py`: 21 structural checks passed.
- OpenAPI contract audit and runtime route inventory were regenerated. The design baseline remains unchanged; restore is documented as runtime-only.
- `npm run typecheck` attempted and failed because `react`, `three`, and their type declarations are not installed. This environment cannot provide a valid TypeScript pass; the result is explicitly NOT VERIFIED.

### Limitations

- SQLite/local filesystem only. A process crash between file creation and DB commit can leave an orphan; no cross-resource atomicity is claimed.
- TypeScript, browser/WebGL, Android E2E, PostgreSQL, object storage, multi-host, and production deployment remain unverified.
- Live FASHN, commercial/rights review, and credit charging remain blocked by prior explicit cost/credential/policy deferrals. G0-G5 remain unpassed.

## BUILD-00092 — Image Asset Foundation and Photo Draft Preparation

### Image asset implementation

- Added `validate_image_upload` for PNG/JPEG/WebP using Pillow: server-detected format and extension agreement, full pixel decode, single-frame restriction, byte cap, dimension cap (16,384 per axis) and pixel cap (100 million).
- Added `POST /v1/assets/images`; image and model assets share private storage, SHA-256 metadata, integrity audit, signed preview, version history and restore. Storage suffix and preview MIME are selected from validated media type.
- `GET /v1/assets` accepts `kind=all|model|image`. The 3D AssetWorkspace requests `kind=model` to avoid feeding photographs to GLTFLoader.
- Version uploads enforce same-kind replacement; historical image restore verifies file checksum and decodes the image again before creating a new immutable version.

### Photo Draft implementation

- Added `app/photo_engine.py` with workspace-scoped Photo Draft create/list/read/update/archive/event APIs.
- `PhotoDraftInput` validates operation enum, output format/count, prompt/style lengths, unique source/mask/reference IDs and active same-workspace image Asset membership.
- `photo_drafts`, `photo_draft_assets`, and `photo_draft_events` are persisted in the existing SQLite asset database. Create/update/archive write append-only events.
- Active Photo Draft references prevent referenced image Asset deletion. The check and soft-delete are serialized with `BEGIN IMMEDIATE`; archive keeps draft/event history and releases the active reference protection.
- Draft-only operations intentionally do not create GenerationJob, Quote, Credit, Provider calls, or outputs. No image generation is simulated.

### Verification evidence

- Backend pytest: 302 passed; Asset API + Photo Draft tests: 38 passed.
- `python -m compileall -q app scripts tests`: passed.
- Viewer source structural validation: 22/22 passed.
- OpenAPI inventory: 13 design paths vs 35 runtime paths; exact match false. 5 design-only paths and 27 runtime-only paths remain.
- OpenAPI schema audit: 15 matched design operations; 10 structural drifts. Design baseline unchanged.
- TypeScript typecheck remains NOT VERIFIED because React/Three.js packages/type declarations are absent. Browser/WebGL/Android E2E not run.

### Limitations

- Photo Draft is preparation only; independent Photo Engine 2D processing, GenerationJob integration, Output persistence, QA-PH dataset/rubric, real Provider generation, cost/time/rights validation remain open.
- Uploaded original image bytes/metadata remain private and unmodified; no Provider receives them in this build.
- SQLite/local filesystem only; PostgreSQL, multi-host, object storage and production readiness not verified. Credit persistence and G0-G5 remain blocked/unpassed.

## BUILD-00093 — Lookbook Draft Preparation

### Implementation

- Added `app/lookbook.py` with workspace-scoped Lookbook Draft create/list/read/update/archive/event-history APIs.
- `LookbookDraftInput` requires 1..20 unique active same-workspace image product assets; optional person image must be unique and same-workspace. Optional Project must be ACTIVE in the Workspace; optional Character must be active in the same Workspace.
- Persisted `lookbook_drafts`, normalized `lookbook_draft_assets`, `lookbook_draft_entities` (Project/Character refs), and append-only `lookbook_draft_events`.
- Active Lookbook Draft references protect image deletion, Project archive/completion, and Character deletion. Draft create/update/archive and destructive reference checks use `BEGIN IMMEDIATE` to serialize competing state changes. Archiving the draft releases the active reference protection without deleting its history.
- Added `LookbookDraftWorkspace` UI with image, project, character selection, scene preset, planned output count, create and archive actions. UI and API are preparation-only.

### Verification

- Backend pytest: 307 passed; Asset API + Photo Draft + Lookbook Draft tests: 43 passed.
- Python compileall: passed.
- Viewer/Photo/Lookbook UI source structural validation: 30/30 passed.
- OpenAPI inventory: 13 design paths vs 39 runtime paths; 5 design-only paths, 31 runtime-only paths; exact match false.
- OpenAPI structural audit: 15 matched design operations, 10 drifted operations. Baseline YAML unchanged.
- TypeScript typecheck remains NOT VERIFIED because React/Three.js dependencies/type declarations are absent. Browser/WebGL/Android E2E not run.

### Limitations

- Lookbook SKU/catalog, product-variant uniqueness, generated output persistence, review/approval and export are not implemented. Current UI chooses one product image; API accepts up to 20.
- No Provider dispatch, Quote/Credit reservation or image output is created. Actual Lookbook generation remains unverified.
- SQLite/local filesystem only; PostgreSQL, multi-host and production deployment not verified. G0-G5 remain unpassed.

## BUILD-00094 — Draft API Pagination

- Added bounded `limit`/`offset` pagination and total counts for Photo Draft and Lookbook Draft list APIs. Active/archived filtering is applied consistently before pagination.
- Added bounded pagination and total counts for Photo/Lookbook append-only event history.
- Updated preparation UIs to request up to 100 active drafts by default.
- Regression coverage verifies total counts, page windows, event history pagination, and invalid query bounds.
- Verification: Backend 308 passed; Asset/Photo/Lookbook API tests 44 passed; Python compileall passed; Viewer/Photo/Lookbook structural checks 30/30 passed. TypeScript remains unverified because React/Three.js packages and type declarations are absent.

## BUILD-00095 — AssetRelation Graph Integrity

- `create_asset_relation` now acquires SQLite `BEGIN IMMEDIATE` before reading graph state and inserting a relation.
- For `derived_from`, a recursive CTE traverses existing outgoing derived-from edges from the proposed target. If the proposed source is reachable, the new edge is rejected as a cycle (HTTP 422).
- Provenance now records both ends of a relation: `asset.relation_created` on source and `asset.relation_received` on target. Payloads identify the counterpart and relation type.
- Added regression coverage for A→B→C then C→A rejection and target-side provenance. Other relation types and relation deletion semantics are unchanged.
- Verification: Backend 309 passed; Asset/Photo/Lookbook API tests 45 passed; compileall passed; UI structural checks 30/30 passed. SQLite-only; PostgreSQL/multi-host remains unverified.

## BUILD-00096 — Product / SKU Catalog

### Implementation

- Added `app/products.py` with workspace-scoped Product create/list/read/update/archive/event-history endpoints.
- Product input requires SKU, name, category and 1..12 active same-workspace image assets. SKU is uppercased and unique case-insensitively per Workspace; duplicate create/update returns 409.
- Added `products`, `product_assets` and append-only `product_events` tables. Product image roles preserve primary/gallery order.
- Active Product records protect linked image Assets from deletion. Product archive is non-destructive and releases the active image reference protection.
- Extended Lookbook Draft with catalog `product_ids` in addition to direct `product_asset_ids`. Active catalog Products and their image assets are validated and linked; Lookbook Draft records a normalized product entity reference and snapshot image references. Active Lookbook Draft prevents Product archive.
- Added `ProductCatalogWorkspace`; extended `LookbookDraftWorkspace` to select multiple catalog Products.
- Added transactional migration for existing `lookbook_draft_entities` tables whose prior CHECK constraint allowed only project/character. Existing references are copied and preserved while product is added to the allowed entity types.

### Verification

- Backend pytest: 314 passed; Asset/Photo/Lookbook/Product API tests: 50 passed.
- Python compileall: passed.
- Viewer/Photo/Product Catalog/Lookbook UI structural validation: 35/35 passed.
- OpenAPI inventory: 13 design paths vs 43 runtime paths; 5 design-only and 35 runtime-only paths; exact match false.
- OpenAPI structural audit: 15 matched design operations, 10 drifted operations. Baseline YAML unchanged.
- TypeScript remains NOT VERIFIED due missing React/Three.js dependencies/type declarations. Browser/WebGL/Android E2E not run.

### Limitations

- Product variants, size/color/fit SKU hierarchy, pricing, inventory, barcode, marketplace sync and project-level product assignment are not implemented.
- Lookbook remains a non-billable draft workflow; no Provider request, generated output, review/approval or export.
- SQLite/local filesystem only; PostgreSQL, multi-host and production deployment not verified. G0-G5 remain unpassed.


## BUILD-00104 — Generated Output Review / Approval / Internal Export Manifest

### 구현

- `app/schema_sqlite.py`에 migration v9를 추가하고 Output review decision 및 export audit 테이블을 구성했습니다. 두 이벤트 테이블은 SQLite trigger로 UPDATE/DELETE를 차단합니다.
- `app/repositories/output_review.py`를 추가했습니다. Job/Output/Asset link 상태를 교차 확인하고, 승인 이벤트마다 immutable AssetVersion/Provenance/checksum을 snapshot합니다. `BEGIN IMMEDIATE`로 현재 review 상태 확인과 decision insert를 직렬화합니다.
- FastAPI에 review read, approve, request-changes, reject, metadata export manifest routes를 추가했습니다. Review는 owner/admin만 결정하며 export는 owner/admin/editor에 허용합니다.
- Export manifest는 모든 Output이 linked + approved인지 검증한 뒤 canonical JSON SHA-256과 append-only export event를 남깁니다. Binary나 public URL은 제공하지 않으며 publication/commercial rights flags는 false로 고정했습니다.
- Viewer에 `OutputReviewWorkspace` 및 CSS를 추가해 결과 검수, 이력, AssetVersion/Provenance/checksum 확인, 승인 및 manifest export UI를 제공합니다.

### 검증

- `PYTHONPATH=. pytest -q`: 332 passed.
- `PYTHONPATH=. python -m compileall -q app`: passed.
- Viewer `python scripts/validate_source.py`: 49/49 passed (offline static checks only).
- OpenAPI inventory: 13 design paths vs 61 runtime paths; exact match false.
- OpenAPI contract audit: 15 design operations, 12 structural drifts, 3 unmatched design operations. Baseline YAML unchanged.
- `npm run typecheck`: NOT VERIFIED; React/Three.js modules and type declarations unavailable (TS2307). Browser/WebGL/Android E2E not run.

### 제한

- Internal approval is not rights clearance or commercial/publication approval. Manifest-only export is not a binary bundle or public distribution.
- No Provider request or credit charge was performed. PostgreSQL/multi-host/production remains unverified; G0-G5 remain unpassed.


## BUILD-00105 — Deterministic Local Photo Processing

### 구현

- `photo_engine.py`에 Pillow 기반 비AI 로컬 ENHANCE/LIGHTING processor를 추가했습니다. ENHANCE는 동적 범위가 충분할 때만 autocontrast를 적용하고 color/sharpness를 소폭 조정합니다. LIGHTING은 brightness/contrast를 제한 조정합니다.
- BACKGROUND/RETOUCH/COMPOSE, 다중 출력, mask/reference, style/prompt 입력은 실제 AI 엔진이 없으므로 local processor에서 거부합니다.
- Photo run idempotency, 30분 lease/reclaim, status/events, append-only event triggers, failure retry를 구현했습니다.
- `save_derived_image_asset`는 run 기반 deterministic Asset ID로 private output을 저장하고 immutable AssetVersion v1, checksum, `derived_from`, provenance를 연결합니다. 파일시스템/SQLite atomicity는 주장하지 않으며 retry 시 기존 asset metadata/file checksum/version/relation/provenance를 재검증합니다.
- `PhotoDraftWorkspace`에 실행 및 결과 Asset/Version/quality boundary 표시를 추가했습니다.

### 검증

- `PYTHONPATH=. pytest -q`: 336 passed.
- `PYTHONPATH=. python -m compileall -q app scripts tests`: passed.
- Viewer source structural validation: 51/51 passed.
- OpenAPI inventory: 13 design paths vs 64 runtime paths; exact match false.
- OpenAPI contract audit: 15 design operations, 12 structural drifts, 3 unmatched credit operations. Baseline YAML unchanged.
- TypeScript typecheck: NOT VERIFIED; React/Three.js dependencies unavailable (TS2307). Browser/WebGL/Android E2E not run.

### 제한

- Local image adjustments are not generative AI. Semantic identity/logo/text preservation is not verified; human review is required.
- No Provider dispatch, credits, publication rights or public URL. PostgreSQL/multi-host/production remains unverified; G0-G5 remain unpassed.


## BUILD-00106 — Photo Output Review / Approval / Internal Manifest

### 구현

- Added Photo output review/export event tables to Asset DB with append-only UPDATE/DELETE triggers.
- Added workspace member review read API, owner/admin approve/request-changes/reject, and owner/admin/editor metadata manifest export.
- Each decision snapshots Asset ID, immutable AssetVersion ID, Photo provenance ID and SHA-256. Verification reads the exact version file and checks path containment, size and checksum; it does not rely on the mutable current Asset pointer.
- Manifest export requires latest approval and snapshot equality, writes canonical SHA-256 plus append-only export audit, and explicitly excludes binaries/publication/commercial rights.
- Extended PhotoDraftWorkspace with review status/actions and gated manifest export.

### 검증

- `PYTHONPATH=. pytest -q`: 337 passed.
- `PYTHONPATH=. python -m compileall -q app scripts tests`: passed.
- Viewer source structural validation: 54/54 passed.
- OpenAPI inventory: 13 design paths vs 69 runtime paths; exact match false.
- OpenAPI contract audit: 15 design operations, 12 structural drifts, 3 unmatched credit operations. Baseline YAML unchanged.
- TypeScript: NOT VERIFIED; React/Three.js dependencies unavailable (TS2307). Browser/WebGL/Android E2E not run.

### 제한

- Approval is internal visual/workflow approval only. Manifest is metadata-only, not binary/public export and not rights clearance.
- Local Photo processing remains non-AI. PostgreSQL/multi-host/production remains unverified; G0-G5 remain unpassed.


## BUILD-00107 — Immutable AssetVersion Preview / Photo Source Pinning

### 구현

- Added exact-version signed preview URL/GET routes. HMAC binds asset/version/expiry; path, size and SHA-256 are verified on URL issue and file response.
- Photo Draft create/update snapshots source version ID/checksum. Legacy drafts are pinned at first run. Local processor reads exact version file; idempotency fingerprint and output provenance/manifest include that snapshot.
- Added `get_asset_version_record` internal repository accessor and passed source version lineage into derived asset provenance.
- Photo and Generation Output review UIs request signed previews for exact immutable versions, not mutable current Asset versions.

### 검증

- `PYTHONPATH=. pytest -q`: 339 passed.
- `PYTHONPATH=. python -m compileall -q app scripts tests`: passed.
- Viewer source structural validation: 56/56 passed.
- OpenAPI inventory: 13 design paths vs 71 runtime paths; exact match false.
- OpenAPI contract audit: 15 design operations, 12 structural drifts, 3 unmatched credit operations. Baseline YAML unchanged.
- TypeScript: NOT VERIFIED; React/Three.js dependencies unavailable (TS2307). Browser/WebGL/Android E2E not run.

### 제한

- Signed previews remain private and short-lived. Local Photo remains non-AI; PostgreSQL/multi-host/production remains unverified; G0-G5 remain unpassed.


## BUILD-00108 — Lookbook Assembly from Individually Approved Photo Outputs

### 구현

- Added immutable `lookbook_output_assets` and append-only `lookbook_output_export_events` with DB UPDATE/DELETE triggers.
- Added workspace-scoped output list/attach/manifest APIs. Attachment requires an approved Lookbook plan and an individually approved Photo output whose immutable AssetVersion/Provenance/checksum and file integrity are verified.
- Product/Variant assignment must be referenced by the approved plan; SKU and option values are snapshotted. Duplicate run/page-order attachment is rejected.
- Output manifest rechecks each Photo review snapshot and exact version file, stores canonical SHA-256 and append-only export audit. Manifest explicitly states the assembled sequence is not separately approved and no publication/commercial rights are granted.
- LookbookDraftWorkspace now discovers approved Photo runs, attaches them to planned variants and exports internal metadata manifest.

### 검증

- `PYTHONPATH=. pytest -q`: 340 passed.
- `PYTHONPATH=. python -m compileall -q app scripts tests`: passed.
- Viewer source structural validation: 59/59 passed.
- OpenAPI inventory: 13 design paths vs 73 runtime paths; exact match false.
- OpenAPI contract audit: 15 design operations, 12 structural drifts, 3 unmatched credit operations. Baseline YAML unchanged.
- TypeScript: NOT VERIFIED; React/Three.js dependencies unavailable (TS2307). Browser/WebGL/Android E2E not run.

### 제한

- Assembly output manifest is metadata-only; page sequence is not separately approved, no binary/public export or rights clearance.
- Only existing approved Photo outputs are assembled; no Provider call/credit charge. PostgreSQL/multi-host/production remains unverified; G0-G5 remain unpassed.


## BUILD-00109 — Lookbook Output Assembly Review / Approval

### 구현

- Added append-only Lookbook output assembly review events with `submitted`/`approved`/`rejected` states.
- Submit snapshots canonical ordered output sequence hash/count and verifies all Photo output AssetVersions. Assembly becomes immutable after submit; further attachment is blocked.
- Owner/admin approve/reject; rejection requires a comment and is terminal. Viewer can read review events.
- Manifest export requires separate assembly approval and revalidates exact Photo version file integrity and snapshot equality. Manifest records approval metadata but does not grant publication/commercial rights.
- LookbookDraftWorkspace supports assembly submit, decision, review status and gated manifest export.

### 검증

- `PYTHONPATH=. pytest -q`: 340 passed.
- `PYTHONPATH=. python -m compileall -q app scripts tests`: passed.
- Viewer source structural validation: 62/62 passed.
- OpenAPI inventory: 13 design paths vs 77 runtime paths; exact match false.
- OpenAPI contract audit: 15 design operations, 12 structural drifts, 3 unmatched credit operations. Baseline YAML unchanged.
- TypeScript: NOT VERIFIED; React/Three.js dependencies unavailable (TS2307). Browser/WebGL/Android E2E not run.

### 제한

- Assembly approval is internal only; manifest is metadata-only and does not authorize publication or commercial use.
- PostgreSQL/multi-host/production remains unverified; G0-G5 remain unpassed.


## BUILD-00110 — Lookbook Output Page Preview

- Added signed exact-AssetVersion image previews to the ordered Lookbook output assembly panel.
- The UI uses the version-specific preview URL; it never receives a private storage path or silently substitutes the current Asset version.
- Backend suite remains 340 passed; compileall passed; Viewer structural validation 63/63 passed. TypeScript/browser runtime remains unverified due missing React/Three.js packages and browser environment.


## BUILD-00111 — Private Lookbook ZIP Package Export

### 구현

- Added private ZIP export from an approved Lookbook output assembly. ZIP contains exact immutable image AssetVersions under `pages/` plus manifest.json with output/SKU/version/checksum and explicit internal-only rights flags.
- Enforced 100 page / 250 MiB input caps; private storage path containment; HMAC signed 15-minute download URL; 24-hour package expiry; package SHA-256/size verification at download.
- Added append-only package export audit table and dry-run-first `cleanup_expired_lookbook_exports.py`; `--apply` removes expired files but preserves audit rows.
- Added LookbookDraftWorkspace ZIP generation and signed download link after assembly approval.

### 검증

- `PYTHONPATH=. pytest -q`: 340 passed.
- `PYTHONPATH=. python -m compileall -q app scripts tests`: passed.
- Cleanup dry-run: 0 inspected, 0 removed; audit retention true.
- Viewer source structural validation: 65/65 passed.
- OpenAPI inventory: 13 design paths vs 80 runtime paths; exact match false.
- OpenAPI contract audit: 15 design operations, 12 structural drifts, 3 unmatched credit operations.
- TypeScript: NOT VERIFIED; React/Three.js dependencies unavailable (TS2307). Browser/WebGL/Android E2E not run.

### 제한

- Package is internal-use only; no publication/public distribution/commercial rights grant. Package files expire after 24h and require cleanup script operation.
- PostgreSQL/multi-host/production remains unverified; G0-G5 remain unpassed.


## BUILD-00113 — OpenAPI Runtime Contract Reconciliation

- BUILD-00112 실제 FastAPI runtime에서 80 path item을 export해 `docs/api/openapi.runtime.v1.json`으로 고정.
- `scripts/export_runtime_openapi.py --check`와 snapshot regression test 2개 추가.
- Design draft v0.2와 비교: 15 operations, 12 structural drifts, 3 unmatched credit/quote operations.
- API wire behavior는 변경하지 않았으며, operationId/pagination/envelope/status compatibility decision은 consumer review 후 진행하도록 문서화.
- Full suite 347 passed 출력; runner clean exit 미확인. Focused OpenAPI 4 passed, compileall 및 snapshot check 통과.


## BUILD-00115 — Viewer Request Body Contract Validation

### 변경

- Viewer 7개 TSX 파일에서 JSON request body를 추출하고 BUILD-00113 runtime OpenAPI의 request schema와 비교하는 검증기를 추가했습니다.
- 필드명, required field, 동적 review action 경로를 검사하며 shorthand object property(`operation`, `option_values`)와 nested object/array 구문을 처리합니다.
- `PhotoOperation`, `OutputFormat` TypeScript union 값과 OpenAPI enum을 정확히 비교합니다.
- 회귀 테스트 2개와 npm 실행 스크립트, machine-readable audit JSON을 추가했습니다.
- 실제 request payload와 Backend 동작은 변경하지 않았습니다. 검사 결과 필드 누락/불일치는 발견되지 않았습니다.

### 검증

- JSON body 10/10 검사, unresolved 0, unknown field 0, missing required 0, enum mismatch 0.
- 신규 테스트 2 passed; Backend pytest 347 passed; Viewer API path/method/query 58/58; 구조 검사 65/65; compileall passed.
- TypeScript/browser/WebGL/Android runtime은 미검증입니다.

## BUILD-00117 — Viewer Response Contract Coverage

### 분석 및 구현

- BUILD-00116 handoff에서 미완료로 남은 Viewer 응답 계약을 실제 FastAPI route와 Pydantic/SQLite 반환 구조에 대조했습니다. 기존 runtime OpenAPI 80 path item을 유지했습니다.
- `app/viewer_responses.py`를 추가해 Asset/AssetVersion, Project, Product/Variant, Project Product, Character, Photo Draft/Run/Review/local processing, Lookbook Draft/Output/Review/Export/Manifest, Event 응답 모델을 정의했습니다.
- API 테스트에서 AssetVersion mutation이 일반 version record와 다르고, Photo local process가 `{run, output_asset}` envelope를 반환한다는 사실을 확인해 별도 응답 모델로 나눴습니다.
- `validate_viewer_response_contract.py`가 Viewer fetch URL/dynamic action과 runtime OpenAPI success JSON schema를 대조합니다. Viewer 48 endpoints 중 47 JSON endpoints schema complete, 1 DELETE 204 no body, 27 distinct models, 0 missing schema/route/unresolved dynamic.
- Viewer TypeScript local declarations를 actual response fields에 맞춰 확장했습니다.

### 검증

- Focused API/contract suite: 160 passed, clean exit.
- Full pytest: 355 passed summary; pytest process did not terminate after summary, clean exit unconfirmed.
- OpenAPI snapshot 80 path items, `--check` passed.
- compileall passed; Viewer structural 65/65; API contract 58/58; request body 10/10; response contract 47/47.
- Global TypeScript 5.8.3 `tsc --noEmit` attempted; React/Three.js packages and typings are absent, so typecheck is blocked and not claimed. Browser/WebGL/Android E2E not run.

### 제한

- Static OpenAPI coverage is not exhaustive runtime payload proof. Next step is serialized payload fixture coverage for all 47 JSON endpoints.
- No Provider call, paid service, credit policy, publication/commercial-rights decision, PostgreSQL selection, or production mutation was made.


## BUILD-00121 — Viewer Package Integrity Guard

### 구현

- Viewer `scripts/validate_package_integrity.py` 추가: npm script target 존재 여부, TS/TSX 상대 import 및 CSS 파일 해석, 외부 import의 package.json dependency 선언, `src/index.ts` 공개 export 대상, tsconfig source inclusion 및 React/Three/TypeScript dependency 역할을 검사합니다.
- 회귀 테스트 4개 추가: 정상 package, 누락 상대 import, 미선언 외부 패키지, 누락 npm script target.
- `validate_typescript_syntax.cjs`를 재귀 파일 탐색으로 변경하여 중첩된 TS/TSX 파일도 검사합니다.
- `npm run validate:package-integrity` 스크립트 및 Viewer README 설명을 추가했습니다.

### 검증

- Viewer script tests: 8 passed.
- Package integrity validator: 0 findings; its four regression tests passed.
- TypeScript syntax/transpilation: 8 files, 0 diagnostics (TypeScript 5.8.3).
- Viewer API contract 58/58; request body contract 10/10; response schema audit 47/47; structural checks 65/65.
- Backend full pytest: 359 passed; runtime JSON endpoint coverage: 47/47; Python compileall and runtime OpenAPI snapshot check passed.
- Chromium headless probe: ResizeObserver/requestAnimationFrame available, WebGL and WebGL2 contexts unavailable. This does not count as Viewer browser E2E.

### 제한

- React/ReactDOM/Three.js/type declarations are not provisioned locally; full semantic TypeScript typecheck remains blocked. No network package installation or dependency/lockfile change was made.
- PostgreSQL driver and local server/container provisioners are absent. Android, multi-host and production deployment remain unverified.


## BUILD-00122 — Feature Scope and Documentation Alignment

### 구현

- 현재 기능 범위와 검증 한계를 한 곳에서 확인할 수 있도록 `docs/FEATURE_SCOPE_STATUS.md`를 추가했습니다.
- Viewer/Backend README의 오래된 BUILD-00093/00096 설명을 현재 코드에 맞게 수정했습니다. Photo 로컬 처리/검수, Product Variant, Lookbook 기획 승인, 승인 Photo 결과 연결, 별도 조립 검토, 내부 전용 ZIP/manifest export를 현재 지원 범위로 반영했습니다.
- AI 이미지 생성, Provider 호출, Quote/Credit, 게시/상업 권리, PostgreSQL 런타임, Android, 실제 WebGL E2E 등은 미구현 또는 미검증으로 명확히 분리했습니다.
- 과거 빌드 시점의 범위 설명은 역사적 기록으로 보존하고 현재 문서에서 현재 상태로 오인하지 않도록 정정 링크를 추가했습니다.

### 검증

- 구현 상태를 `app/lookbook.py`, `app/products.py`, `app/photo_engine.py`와 관련 API 테스트의 실제 route/test 존재 여부에 대조했습니다.
- Backend 359 passed, Viewer script tests 8 passed, runtime JSON coverage 47/47, API 58/58, request 10/10, response schema 47/47, structural 65/65, package integrity 0 findings, TypeScript syntax 8/0.
- 문서 전용 변경이며 애플리케이션 동작과 DB schema는 변경하지 않았습니다.


## BUILD-00123 — Browser WebGL2 Capability Probe

### 구현

- Optional Playwright browser probe `ai_creator_studio_3d_viewer/scripts/probe_browser_runtime.py` 추가. WebGL2 context 생성, shader compile/link, triangle draw/readback, ResizeObserver, requestAnimationFrame을 확인합니다.
- Optional browser audit dependency는 `requirements-browser-audit.txt`에 별도 분리하고 `npm run probe:browser-runtime`을 추가했습니다. 앱 runtime dependency는 변경하지 않았습니다.

### 검증

- `xvfb-run -a python3 scripts/probe_browser_runtime.py`: PASS. Chromium 144 / Xvfb / SwiftShader에서 WebGL2=true, trianglePixel=true, resizeObserved=true, animationFrame=true.
- 이 검증은 브라우저 엔진 capability만 확인하며 실제 React/Three.js Viewer 또는 GLTF 모델 실행은 아닙니다. React/Three.js dependencies 미설치로 실제 Viewer E2E는 계속 blocked입니다.


## BUILD-00124 — Product Variant Image Management

### 구현

- Product Catalog UI에 Variant 전용 이미지 다중 선택(최대 12개)을 추가했습니다. Variant 이미지가 있으면 Lookbook에서 우선 사용되고, 선택하지 않으면 상위 Product 이미지로 fallback합니다.
- 기존 Variant 편집 UI를 추가하고 이미 구현된 `PUT /v1/products/{product_id}/variants/{variant_id}`를 연결했습니다. SKU, size/color, 이미지 연결을 변경할 수 있으며 size/color 이외의 기존 option_values도 보존합니다.
- Variant 편집/생성/보관 상태와 이미지 override 여부를 UI에 표시합니다.

### 검증

- Viewer API contract: 59/59; request-body contract: 11 checked, no findings; response schema audit: 48 JSON endpoints / 49 total endpoints, no missing route/schema.
- Viewer structural checks: 68/68; TypeScript syntax/transpilation: 8 files, 0 diagnostics; Viewer script tests: 8 passed; package integrity: 0 findings.
- Backend full pytest: 359 passed; runtime Viewer HTTP JSON coverage: 48/48; compileall and runtime OpenAPI snapshot check passed.
- Existing backend tests cover Variant image validation, image retention, PUT update and Lookbook Variant image resolution. UI runtime browser test remains blocked by unavailable React/Three dependencies.


## BUILD-00125 — Product Catalog Edit Workflow

### 구현

- Product Catalog UI에 기존 Product 편집을 추가했습니다. SKU, 상품명, 설명, 카테고리, 상품 이미지 참조를 수정하고 기존 `PUT /v1/products/{product_id}` API를 호출합니다.
- 상품 편집 취소를 추가하고 생성/편집 버튼을 상태에 맞게 전환합니다. 활성 Lookbook 초안에서 사용 중인 Product의 수정 거부(409)는 기존 API 정책대로 UI 오류로 표시합니다.

### 검증

- Viewer API contract: 60/60; request-body contract: 12 checked, no findings; response schema audit: 49 JSON endpoints / 50 total endpoints.
- Viewer structural checks: 70/70; TypeScript syntax/transpilation: 8 files, 0 diagnostics; Viewer script tests: 8 passed; package integrity: 0 findings.
- Backend full pytest: 359 passed; runtime Viewer HTTP JSON coverage: 49/49; compileall and runtime OpenAPI snapshot check passed.
- Chromium/Xvfb/SwiftShader WebGL2 capability probe remains PASS; actual React UI browser interaction remains unverified because React/Three dependencies are unavailable.


## BUILD-00126 — Project Workspace Management

### 구현

- `ProjectWorkspace` React 컴포넌트를 추가해 프로젝트 생성/목록/편집과 ACTIVE/COMPLETED/ARCHIVED 상태 전환 및 재활성화를 지원합니다.
- 기존 `POST /v1/projects`, `GET /v1/projects`, `PUT /v1/projects/{project_id}` API만 사용합니다. 활성 Lookbook 초안 참조 중 상태 변경은 backend 409 guard가 처리합니다.
- 외부 참조는 생성 시 저장하고 backend update schema가 변경을 지원하지 않으므로 편집 화면에서 읽기 전용으로 표시합니다.
- `src/index.ts` export, 반응형 CSS, README integration 예제를 추가했습니다.

### 검증

- Viewer API contract: 63/63; request-body contract: 15 checked, no findings; response schema audit: 51 JSON endpoints / 52 total endpoints.
- Viewer structural checks: 75/75; TypeScript syntax/transpilation: 9 files, 0 diagnostics; Viewer script tests: 8 passed; package integrity: 0 findings.
- Backend full pytest: 359 passed; runtime Viewer HTTP JSON coverage: 51/51; compileall and runtime OpenAPI snapshot check passed.
- Actual React browser interaction remains unverified until React dependencies are provisioned.

## BUILD-00131 — Workspace Mutation Scope Safety

### 구현

- 공통 `useRequestScope` hook을 추가해 API origin, access token, workspace/job 식별자로 비동기 작업의 시작 scope를 고정하고 scope 변경 또는 unmount 이후의 늦은 결과가 현재 화면 상태를 변경하지 못하도록 했습니다.
- Asset, Photo Draft, Lookbook, Product Catalog/Variant, Project Product Assignment, Project, Output Review의 mutation callback과 주요 loader/후속 reload에 scope 검증을 적용했습니다.
- workspace/job 변경 시 이전 scope의 목록, 폼, 선택, 미리보기, manifest, 오류 및 busy 상태를 초기화합니다.
- Backend/API/schema/DB/dependency/provider/credit 동작은 변경하지 않았습니다.

### 검증

- Viewer structural 103/103, TypeScript syntax/transpilation 10 files/0 diagnostics.
- Viewer API contract 63/63, request bodies 15/0 findings, response contract 51 JSON endpoints / 52 total endpoints / 28 models.
- Viewer script tests 8 passed, package integrity 0 findings, Python compileall PASS.
- Isolated backend tests: assets API 67 passed, concurrent claims 28 passed, focused Lookbook assembly 1 passed.
- Full 359-test suite was attempted but timed out/stalled during suite-order execution in the extracted runtime; see `BUILD-00131_VERIFICATION.md`. This is not reported as a fresh full-suite pass. Backend code was unchanged.
- Full semantic TypeScript typecheck and actual React/Three.js browser E2E remain unverified due missing trusted dependencies.


## BUILD-00141 — Lookbook Export History & Page-Order Integrity

- Export history now loads with Lookbook assembly and shows export ID, creation time, page count, size, package SHA-256, assembly snapshot SHA-256, retention expiry and file status. Backend status uses `lstat` to distinguish available, expired and missing files without following symlinks or mutating audit rows.
- Added a page-order tampering regression proving review snapshot integrity detection, plus missing/restored ZIP history status assertions while preserving the immutable audit row.
- Verification: backend 359 passed; compileall passed; Viewer API 64/64; request bodies 15/0 findings; response 52 JSON/53 endpoints/29 models; Lookbook structural 19/19; helper 12; syntax 10+4 / 0 errors; package integrity 0 findings.
- Semantic TypeScript remains blocked by missing React and typings; real React/Three.js browser E2E remains unverified.


## BUILD-00142 — Private ZIP Download Authorization & Cleanup Observability

- Added current workspace membership/role revalidation to signed Lookbook ZIP download; active viewers remain read-authorized, removed members cannot reuse an unexpired link, and the Viewer sends its Bearer token on ZIP fetch.
- Reject symlink/non-regular package entries with `lstat` before package integrity validation.
- Cleanup script now reports machine-readable run mode, limit, candidate count, outcome counters, partial-failure flag, audit-retention assertion, duration and completion timestamp. Dry-run remains default; `--apply` is explicit.
- Added regression coverage for unauthenticated download, viewer access, membership revocation, symlink substitution, cleanup dry-run telemetry and partial failure exit code.
- Verification: backend 361 passed; Python compileall passed; structural 140; helper tests 12/7/7/4; TypeScript syntax 10+4; API 64/64; request contract 15 / 0 findings; response contract 52 JSON / 53 endpoints / 29 models; request contract tests 2; package integrity 0; Xvfb browser capability smoke passed. Semantic TS remains blocked by unavailable React typings; component E2E remains unverified.

## BUILD-00149 — Unknown-Length GLTF Buffer Growth Hardening

- Base: BUILD-00148.
- Unknown-length authenticated GLTF/GLB downloads now grow a single bounded accumulator geometrically instead of retaining each stream chunk and allocating another full-size final buffer.
- The accumulator begins at 64 KiB, doubles up to the 256 MiB cap, and returns the backing store directly when the final size exactly matches capacity. A shorter final payload is copied once into an exact-sized result.
- Allocation failure cancels the stream and is represented as a typed `memory` error with a Korean recovery message in the viewer.
- Runtime tests: 16/16; structural tests: 19/19; backend full suite: 367 passed; API contract 63/63; response contract 50 JSON / 52 total / 28 models; syntax 10 source + 6 declarations; package integrity 0 findings.
- Limitations: geometric resize temporarily retains old and new backing stores; no target-device memory profiling. React/Three component E2E and semantic TypeScript remain unverified. No external integrations, dependencies, API/schema or approval-gated operations changed.



## BUILD-00154 — Failure-Resilient GLTF Resource Disposal

- Made GLTF GPU-resource cleanup best-effort: a throwing `dispose()` no longer aborts cleanup of later resources.
- Added structured diagnostics and counts for attempted/successful disposal across textures, materials, geometries, and skeletons.
- Isolated traversal and nested material-property inspection failures; shared resources remain deduplicated.
- Added 19 runtime assertions; backend 367 passed; authenticated GLTF 15/15; Viewer contracts, TypeScript syntax, package integrity and WebGL2 capability smoke passed.
- Semantic TypeScript and actual React/Three browser E2E remain unverified because React/Three dependencies are absent.



## BUILD-00155 — Viewer Renderer Teardown Resilience

- Added `runViewerCleanupSteps.mjs` / `.d.mts` to execute named teardown operations independently and return `{ attemptedCount, completedCount, errors }`.
- Renderer unmount cleanup now isolates animation-frame cancellation, observer disconnect, controls disposal, mixer stop/root uncaching, GLTF/stage resource disposal, shadow target disposal, renderer disposal, canvas removal and ref clearing.
- Model replacement uses the same runner to isolate scene removal, mixer cleanup, GLTF disposal and reference clearing.
- Added 10 runtime failure-injection assertions and 13 structural ordering assertions; existing authenticated GLTF checks were updated to validate semantic cleanup labels and callbacks.
- Verification: backend 367 passed; GLTF disposal 33; authenticated GLTF 15/15; cleanup 10 + 13/13; API 63/63; request body 15/0 findings; response 50 JSON/52 total/28 models; syntax 10+9; package integrity 0; Python compileall passed; Xvfb WebGL2 capability smoke passed.
- Semantic TypeScript remains blocked by absent React/Three dependencies. Browser probe is capability-only, not application E2E.

## BUILD-00200 — Worker Lease Input Safety

- Added shared worker lease validation and applied it before Outbox/Poll claim storage access and Poll lease-renewal delegation.
- Rejected empty/non-string/overlong worker IDs and non-positive/non-integer lease durations, including Python booleans; Poll renewal rejects blank task IDs.
- Added adversarial parameterized tests. Backend full suite 428 passed; focused Outbox/Poll 29 passed; compileall passed.
- Viewer offline contracts and structural checks passed. Chromium WebGL2 probe was blocked in this environment; no browser success claimed.
- External tests intentionally deferred; PostgreSQL, React/Three.js and live AI provider integrations remain future work.
