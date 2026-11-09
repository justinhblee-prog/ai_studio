# AI CREATOR STUDIO — 현재 인수인계

- 기준 빌드: `BUILD-00115`
- 기반 빌드: `BUILD-00114`
- 제품 버전: 미지정

## BUILD-00115 현재 상태 — Viewer Request Body Contract Validation

### 구현

- Viewer `src/*.tsx` 7개 파일의 literal JSON request body 10개를 runtime OpenAPI와 대조하는 `scripts/validate_viewer_request_contract.py`를 추가했습니다.
- Top-level field, required field, dynamic review action schema를 검사합니다. Shorthand properties와 nested object/array를 인식합니다.
- `PhotoOperation` 및 `OutputFormat` TypeScript union과 Backend OpenAPI enum의 값 집합을 비교합니다.
- 회귀 테스트 2개, npm scripts `validate:request-contract`, `test:request-contract`, machine-readable audit JSON을 추가했습니다.
- 실제 payload와 Backend runtime은 변경하지 않았습니다. 필드/required/enum 불일치가 발견되지 않았습니다.

### 검증

- JSON body: 10/10 검사, unresolved 0, unknown fields 0, missing required 0.
- Enum parity: 2/2 exact match.
- 신규 regression tests: 2 passed.
- Backend pytest: 347 passed (clean exit).
- Viewer API path/method/query: 58/58 passed.
- Viewer structural checks: 65/65 passed.
- Python compileall: passed.
- TypeScript compiler, browser/React/WebGL/Android E2E: 미검증.

### 한계 / 다음 작업

1. Viewer가 소비하는 response JSON field/type과 Backend response model/실제 반환값의 정적 계약 대조.
2. npm 의존성 설치 가능한 환경에서 TypeScript typecheck 수행.
3. Browser 기반 React UI/API 통합 및 WebGL 검증 환경 확보.
4. PostgreSQL, multi-host, credit policy, Provider 비용/권리 승인 gate는 기존 결정대로 보류.

## BUILD-00115 산출물

- `BUILD-00115_RELEASE_NOTES.md`
- `BUILD-00115_VERIFICATION.md`
- `ai_creator_studio_3d_viewer/docs/VIEWER_REQUEST_BODY_CONTRACT_AUDIT_BUILD-00115.md`
- `ai_creator_studio_3d_viewer/docs/viewer_request_contract_audit.v1.json`
- `ai_creator_studio_3d_viewer/scripts/validate_viewer_request_contract.py`
- `ai_creator_studio_3d_viewer/scripts/test_viewer_request_contract.py`

---

# AI CREATOR STUDIO — 현재 인수인계

- 기준 빌드: `BUILD-00114`
- 기반 빌드: `BUILD-00113`
- 제품 버전: 미지정

## BUILD-00114 현재 상태 — Viewer ↔ Backend API Integration Contract Audit

### 구현

- Viewer `src/*.tsx` 7개 파일의 `fetch()` 호출을 추출해 BUILD-00113 runtime OpenAPI snapshot과 비교하는 `scripts/validate_api_contract.py`를 추가했습니다.
- URL path, HTTP method, query parameter 이름을 검사하며 동적 review/action 경로를 callback별 허용값으로 확장합니다.
- `npm run validate:api-contract`와 validator 회귀 테스트 2개를 추가했습니다.
- Product Catalog 및 Lookbook 화면에서 `/v1/assets` 호출 시 전달하던 `limit=100`을 제거했습니다. 실제 route는 `workspace_id`, `kind`만 선언하며 limit은 무시되고 있었습니다. 현재 endpoint pagination은 미구현입니다.
- Viewer API 계약 결과 JSON 및 통합 감사 문서를 추가했습니다.

### 검증

- Viewer source 7개 파일, fetch call site 58개 검사: 58/58 path + method + query name 일치.
- 고유 method + path 조합 48개. 누락 route/method 0, 미선언 query 0, 해석 불가 dynamic path 0.
- Validator 회귀 테스트 2 passed.
- Viewer scripts Python compileall passed.
- `npm install`이 실행 제한 시간 내 완료되지 않아 TypeScript typecheck는 미검증. Browser/React/WebGL/Android E2E도 미검증.
- Backend 코드는 변경하지 않았으므로 Backend pytest는 재실행하지 않았습니다.

### 미완료 / 다음 작업

1. Viewer request body와 Backend Pydantic request model의 필드/required/type/enum 계약 대조.
2. Viewer가 소비하는 response JSON field/type과 Backend response model/실제 반환값의 정적 계약 대조.
3. npm 의존성 설치 가능한 환경 확보 후 TypeScript typecheck 실행.
4. Browser 기반 React UI/API 통합 및 WebGL 검증 환경 확보.
5. PostgreSQL, credit policy, Provider 비용/권리 승인 gate는 기존 결정대로 보류.

## BUILD-00114 산출물

- `BUILD-00114_RELEASE_NOTES.md`
- `BUILD-00114_VERIFICATION.md`
- `ai_creator_studio_3d_viewer/docs/VIEWER_API_INTEGRATION_AUDIT_BUILD-00114.md`
- `ai_creator_studio_3d_viewer/docs/viewer_api_contract.v1.json`
- `ai_creator_studio_3d_viewer/scripts/validate_api_contract.py`

---


- 기준 빌드: `BUILD-00113`
- 기반 빌드: `BUILD-00112`
- 제품 버전: 미지정

## BUILD-00113 현재 상태 — OpenAPI Runtime Contract Reconciliation

### 구현

- FastAPI runtime에서 실제 생성한 OpenAPI 문서 80 path item을 `docs/api/openapi.runtime.v1.json`으로 고정했습니다.
- `scripts/export_runtime_openapi.py`를 추가했습니다. `--check`는 코드와 저장된 snapshot이 다르면 실패합니다.
- Runtime contract snapshot 회귀 테스트 2개와 reconciliation 결정 문서를 추가했습니다.
- 설계 초안 v0.2는 변경하지 않았습니다. 현재 구현과 다른 응답 envelope, pagination, status, operationId를 억지로 맞추면 기존 API/SDK 호환성을 깨뜨릴 수 있기 때문입니다.
- 크레딧 계정/원장/견적 3개 operation은 credit reservation, ledger persistence, quote expiry/consumption 정책 승인 전까지 미구현 상태로 유지합니다.

### 검증

- Full backend pytest: `347 passed` 출력 확인. 단, 테스트 요약 후 프로세스가 정상 종료하지 않아 clean process exit는 확인하지 못했습니다.
- Focused OpenAPI tests: 4 passed, clean exit.
- Python compileall: 통과.
- Runtime OpenAPI snapshot `--check`: 통과.
- Design/runtime structural audit: 15 operations 비교, 12 drift, 3 unmatched.

### 미완료 / 다음 작업

1. Operation별 consumer/API compatibility review 및 실제 client usage 확인.
2. 12개 drift 중 우선순위를 정해 API contract migration plan 수립. 실제 변경은 호환성/승인 기준을 먼저 확보합니다.
3. Runtime-only internal operations와 public API의 OpenAPI 분리 필요성 검토.
4. TypeScript/browser/WebGL 검증 환경 확보.
5. Credit/Quote 구현은 정책 승인 전 보류. PostgreSQL, multi-host, Provider 비용·권리 정책도 기존 승인 gate 유지.

---

- 기준 빌드: `BUILD-00110`
- 기반 빌드: `BUILD-00109`
- 제품 버전: 미지정

## BUILD-00110 현재 상태 — Lookbook Output Page Preview

- LookbookDraftWorkspace output assembly 패널에서 연결된 각 결과의 정확한 immutable AssetVersion signed preview URL을 발급받아 페이지 순서대로 미리봅니다.
- `POST /v1/assets/{asset_id}/versions/{version_id}/preview-url`을 사용하므로 current Asset pointer가 이후 변경되어도 미리보기는 검수된 version을 유지합니다. Private storage path는 브라우저에 노출하지 않습니다.
- Preview가 실패해도 검수 완료로 간주하지 않습니다. Backend assembly review는 별도로 exact Photo version file size/SHA-256과 review snapshot을 검증하고 `integrity_error`를 반환할 수 있습니다.

### 검증

- Backend pytest: 340 passed (backend behavior unchanged from BUILD-00109).
- Python compileall (`app scripts tests`): passed.
- Viewer structural validation: 63/63 passed. TypeScript/browser runtime 검증은 아닙니다.
- OpenAPI inventory: design 13 paths vs runtime 77 paths; exact match false.
- OpenAPI contract audit: 15 design operations; 12 structural drifts; 3 unmatched credit operations.
- TypeScript: NOT VERIFIED — React/Three.js dependencies/type declarations absent (`TS2307`). Browser/WebGL/Android E2E 미검증.

### 다음 안전 작업

1. Lookbook assembly review UI를 실제 browser runtime에서 검증하고, page preview/approval UX의 접근성·반응형 상태를 확인합니다.
2. OpenAPI design/runtime drift를 operation 단위로 검토하고 승인된 contract reconciliation 수행.
3. TypeScript/browser/WebGL 통합 테스트 환경 확보 후 실제 UI 검증.
4. 외부 AI Provider/과금/법무·권리 정책은 명시적 승인 전까지 보류.

---


- 기준 빌드: `BUILD-00109`
- 기반 빌드: `BUILD-00108`
- 제품 버전: 미지정

## BUILD-00109 현재 상태 — Lookbook Output Assembly Review / Approval

### 구현

- `lookbook_output_assembly_review_events`를 추가했습니다. UPDATE/DELETE는 SQLite trigger로 차단합니다.
- `GET /v1/lookbook-drafts/{draft_id}/outputs/review`, `POST .../outputs/submit`, `POST .../outputs/approve`, `POST .../outputs/reject`를 추가했습니다.
- Owner/admin/editor가 승인된 Lookbook 기획안과 개별 승인 Photo output들을 조립한 뒤 검토 요청할 수 있습니다. 제출 시 page order, caption, Product/Variant/SKU/AssetVersion/Provenance/checksum을 포함한 canonical SHA-256 snapshot과 output count를 고정합니다.
- Owner/admin만 승인/반려할 수 있습니다. 반려는 comment 필수이며 terminal입니다. immutable output item이므로 변경하려면 새 Lookbook draft를 만들어야 합니다. Viewer는 이력만 조회할 수 있습니다.
- 검토 제출 후에는 새 Photo output을 연결할 수 없습니다. 승인/manifest는 매번 Photo review snapshot과 exact AssetVersion 파일 경로·크기·SHA-256을 재검증합니다.
- 파일 손상이나 snapshot drift가 있으면 review read는 `integrity_error`를 표시하고 approve/export를 차단합니다.
- `POST .../outputs/manifest`는 latest assembly review approved 및 snapshot hash/output count 일치가 필수입니다. Manifest는 `output_assembly_approved=true`, reviewer/time/hash를 포함하되 publication/commercial flags는 false로 유지합니다.
- LookbookDraftWorkspace에 조립 검토 요청, owner/admin 승인·반려, 상태 표시 및 승인 후 manifest export를 추가했습니다.

### 검증

- Backend pytest: 340 passed.
- Lookbook assembly test: pending→in_review→approved, viewer read-only, owner/admin role boundary, rejection comment, submission 후 attach freeze, output file corruption/integrity_error/recovery, approval-gated manifest, terminal state, append-only review event 검증.
- Python compileall (`app scripts tests`): passed.
- Viewer structural validation: 62/62 passed. TypeScript/browser runtime 검증은 아닙니다.
- OpenAPI inventory: design 13 paths vs runtime 77 paths; exact match false.
- OpenAPI contract audit: 15 design operations; 12 structural drifts; 3 unmatched credit operations. Baseline YAML unchanged.
- TypeScript: NOT VERIFIED — React/Three.js dependencies/type declarations absent (`TS2307`). Browser/WebGL/Android E2E 미검증.

### 경계/미완료

- 조립 승인은 내부 업무/시각 검수이며 저작권·초상권·동의·브랜드·법무·게시·상업 이용 허가가 아닙니다.
- Manifest는 metadata-only이며 binary ZIP/public URL이 아닙니다.
- PostgreSQL/object storage/multi-host/production 미검증. Credit Ledger policy/persistence 미결정. G0-G5 미통과.

### 다음 안전 작업

1. Lookbook output page preview/side-by-side review UI 및 브라우저 검증 환경 확보.
2. OpenAPI design/runtime drift를 operation 단위로 검토하고 승인된 contract reconciliation 수행.
3. TypeScript/browser/WebGL 통합 테스트 환경 확보 후 실제 UI 검증.
4. 외부 AI Provider/과금/법무·권리 정책은 명시적 승인 전까지 보류.

---


- 기준 빌드: `BUILD-00108`
- 기반 빌드: `BUILD-00107`
- 제품 버전: 미지정

## BUILD-00108 현재 상태 — Lookbook Assembly from Approved Photo Outputs

### 구현

- `lookbook_output_assets`와 `lookbook_output_export_events`를 Asset/Lookbook SQLite DB에 추가했습니다. Output item과 export event는 DB trigger로 UPDATE/DELETE를 차단합니다.
- `GET /v1/lookbook-drafts/{draft_id}/outputs`, `POST .../outputs`, `POST .../outputs/manifest`를 추가했습니다.
- 승인된 Lookbook 기획안에 한해, succeeded Photo run이며 immutable AssetVersion이 개별 approved인 결과만 연결할 수 있습니다.
- 연결 시 Photo review snapshot의 Asset ID/Version ID/Provenance ID/SHA-256을 확인하고, Lookbook transaction 내부에서 정확한 version file의 경로·크기·checksum을 재검증합니다.
- Product/Variant는 승인된 Lookbook 기획안에 포함되어야 합니다. Product SKU, Variant SKU, option values를 Lookbook output item에 immutable snapshot합니다.
- 동일 Photo run은 한 Lookbook에 한 번만 연결되며 page_order도 draft 내 unique입니다. 연결된 output item은 immutable이므로 조립 변경은 새 Lookbook draft에서 수행합니다.
- Output manifest는 모든 연결 결과의 latest Photo approval snapshot과 정확한 AssetVersion file integrity를 재검증한 후 canonical SHA-256 및 append-only export audit를 기록합니다.
- Manifest는 Photo 결과 개별 승인을 표시하지만 `output_assembly_approved=false`입니다. 페이지 순서/조립 자체는 별도 승인되지 않았습니다. Binary/public URL을 포함하지 않고 publication/commercial flags를 false로 둡니다.
- LookbookDraftWorkspace에 승인된 Photo run 조회, Product Variant 연결, 페이지 순서/캡션, 내부 manifest export를 추가했습니다.

### 검증

- Backend pytest: 340 passed.
- 신규 Lookbook assembly 테스트: 기획 승인 gate, Photo output approval gate, Variant plan membership, SKU/옵션 snapshot, 중복 연결 차단, metadata manifest/hash, immutable item 및 append-only export audit 검증.
- Python compileall (`app scripts tests`): passed.
- Viewer structural validation: 59/59 passed. TypeScript/browser runtime 검증은 아닙니다.
- OpenAPI inventory: design 13 paths vs runtime 73 paths; exact match false.
- OpenAPI contract audit: 15 design operations; 12 structural drifts; 3 unmatched credit operations. Baseline YAML unchanged.
- TypeScript: NOT VERIFIED — React/Three.js dependencies/type declarations absent (`TS2307`). Browser/WebGL/Android E2E 미검증.

### 경계/미완료

- 새로운 AI 사진 생성은 하지 않습니다. 기존 개별 승인 Photo output만 Lookbook에 연결합니다.
- 기획안 승인과 각 Photo 결과 승인은 별개이며, 조립된 페이지 순서는 별도 승인되지 않았습니다. 이 manifest는 게시용이 아닙니다.
- Manifest는 내부 metadata only이며 binary ZIP, public distribution, commercial rights clearance가 아닙니다.
- PostgreSQL/object storage/multi-host/production 미검증. Credit Ledger policy/persistence 미결정. G0-G5 미통과.

### 다음 안전 작업

1. Lookbook output assembly 자체의 별도 review/approval workflow와 페이지 미리보기 구현.
2. OpenAPI design/runtime drift를 operation 단위로 검토하고 승인된 contract reconciliation 수행.
3. TypeScript/browser/WebGL 통합 테스트 환경 확보 후 실제 UI 검증.
4. 외부 AI Provider/과금/법무·권리 정책은 명시적 승인 전까지 보류.

---


- 기준 빌드: `BUILD-00107`
- 기반 빌드: `BUILD-00106`
- 제품 버전: 미지정

## BUILD-00107 현재 상태 — Immutable AssetVersion Preview / Photo Source Pinning

### 구현

- `POST /v1/assets/{asset_id}/versions/{version_id}/preview-url`와 signed `GET /v1/assets/{asset_id}/versions/{version_id}/preview`를 추가했습니다.
- HMAC 서명은 asset_id + version_id + expires를 포함합니다. URL 발급/실제 파일 제공 시 path containment, 파일 존재, 크기, immutable AssetVersion SHA-256을 검증합니다. 응답은 private no-store 및 nosniff입니다.
- v2 업로드 후에도 v1 preview URL은 v1을 제공하며, 기존 `/preview-url`은 current Asset version을 제공합니다.
- Photo Draft 생성/수정 시 source AssetVersion ID와 SHA-256을 `payload_json`에 snapshot합니다. 구형 draft에 snapshot이 없으면 최초 로컬 실행 시 현재 버전을 고정합니다.
- Local Photo run fingerprint, 실행 입력, 결과 provenance/manifest가 고정 source version/checksum을 사용합니다. 실제 처리도 current Asset pointer가 아닌 해당 immutable version 파일을 읽고 checksum/size를 검증합니다. 이후 v2가 업로드되어도 같은 Idempotency-Key는 v1 기준으로 동일 결과를 replay합니다.
- Derived Asset 저장 시 source AssetVersion이 같은 workspace에 존재하고 checksum이 일치하는지 확인합니다.
- PhotoDraftWorkspace와 OutputReviewWorkspace는 current asset가 아닌 정확한 immutable source/output/review AssetVersion을 미리봅니다.

### 검증

- Backend pytest: 339 passed.
- 신규 테스트: v1/v2 signed preview 분리, tampered/expired signature 거부, Photo Draft source v1 pinning 후 v2 업로드, output provenance source version/checksum, idempotent replay 검증.
- Python compileall (`app scripts tests`): passed.
- Viewer structural validation: 56/56 passed. TypeScript/browser runtime 검증은 아닙니다.
- OpenAPI inventory: design 13 paths vs runtime 71 paths; exact match false.
- OpenAPI contract audit: 15 design operations; 12 structural drifts; 3 unmatched credit operations. Baseline YAML unchanged.
- TypeScript: NOT VERIFIED — React/Three.js dependencies/type declarations absent (`TS2307`). Browser/WebGL/Android E2E 미검증.

### 경계/미완료

- Preview는 짧은 만료시간을 가진 서명된 private read URL입니다. 공개 게시 권한을 부여하지 않습니다.
- Photo ENHANCE/LIGHTING은 결정론적 Pillow 조정이며 생성형 AI가 아닙니다. BACKGROUND/RETOUCH/COMPOSE는 실제 AI Photo Engine 연결 전까지 미지원입니다.
- PostgreSQL/object storage/multi-host/production 미검증. Credit Ledger policy/persistence 미결정. G0-G5 미통과.

### 다음 안전 작업

1. Lookbook output assembly에 immutable AssetVersion 및 Photo output approval snapshot 연결.
2. OpenAPI design/runtime drift를 operation 단위로 검토하고 승인된 contract reconciliation 수행.
3. TypeScript/browser/WebGL 통합 테스트 환경 확보 후 실제 UI 검증.
4. 외부 AI Provider/과금/법무·권리 정책은 명시적 승인 전까지 보류.

---


- 기준 빌드: `BUILD-00106`
- 기반 빌드: `BUILD-00105`
- 제품 버전: 미지정

## BUILD-00106 현재 상태 — Photo Output Review / Approval / Internal Manifest

### 구현

- Asset/Photo SQLite DB에 `photo_output_review_events`, `photo_output_export_events`를 추가했습니다. 두 테이블은 DB trigger로 UPDATE/DELETE를 차단합니다.
- `GET /v1/photo-drafts/{draft_id}/runs/{run_id}/review`: workspace member가 Photo run의 검수 상태와 이력을 조회합니다.
- `POST .../review/approve`, `/review/request-changes`, `/review/reject`: owner/admin만 결정할 수 있습니다. 수정 요청/반려는 comment 필수. `changes_requested`는 재검토 가능하며 `approved`/`rejected`는 terminal입니다.
- 검수 이벤트는 Asset ID, immutable AssetVersion ID, `asset.photo_processed` Provenance ID, SHA-256을 snapshot합니다.
- 검수/내보내기는 현재 Asset pointer가 아니라 해당 immutable AssetVersion 파일을 직접 확인합니다. storage key path containment, 파일 크기, SHA-256을 검증합니다. 이후 v2를 업로드해도 v1 승인 스냅샷은 v1 파일이 유효한 한 유지됩니다.
- `POST .../export-manifest`: owner/admin/editor만 가능하며 latest review가 approved이고 immutable snapshot이 일치할 때만 내부 metadata manifest를 생성합니다. canonical SHA-256 및 append-only export audit를 기록합니다.
- Manifest는 binary/public URL을 포함하지 않으며 `is_ai_generated=false`, `publication_authorized=false`, `commercial_rights_verified=false`, `binary_files_included=false`를 명시합니다.
- `PhotoDraftWorkspace`에 결과 검수 상태, 승인/수정 요청/반려, 승인 manifest 내보내기를 추가했습니다.

### 검증

- Backend pytest: 337 passed.
- Photo review/export 신규 테스트: viewer read-only/decision/export 권한, comment 필수, changes_requested→approved, snapshot, v2 추가 후 v1 승인 유지, metadata-only manifest, terminal decision, append-only event 검증.
- Python compileall (`app scripts tests`): passed.
- Viewer structural validation: 54/54 passed. TypeScript/browser runtime 검증은 아닙니다.
- OpenAPI inventory: design 13 paths vs runtime 69 paths; exact match false.
- OpenAPI contract audit: 15 design operations; 12 structural drifts; 3 unmatched credit operations. Baseline YAML unchanged.
- TypeScript: NOT VERIFIED — React/Three.js packages/type declarations absent (`TS2307`). Browser/WebGL/Android E2E 미검증.

### 경계/미완료

- 승인과 manifest는 내부 업무용입니다. 저작권·초상권·동의·브랜드·법무·게시/상업 이용 허가가 아닙니다.
- Manifest는 바이너리 ZIP/export가 아닙니다.
- ENHANCE/LIGHTING은 결정론적 Pillow 로컬 조정이며 생성형 AI가 아닙니다. BACKGROUND/RETOUCH/COMPOSE는 실제 AI Photo Engine 연결 전까지 미지원입니다.
- PostgreSQL/object storage/multi-host/production 미검증. Credit Ledger policy/persistence 미결정. G0-G5 미통과.

### 다음 안전 작업

1. Lookbook generated-output 결과와 Product Variant/SKU snapshot을 연결하는 workflow/contract 설계 및 테스트.
2. Photo/Lookbook output review/approval UI의 브라우저 통합 테스트와 API 계약 정합성 개선.
3. OpenAPI design/runtime drift를 operation 단위로 검토하고 승인된 contract reconciliation 수행.
4. 외부 AI Provider/과금/법무·권리 정책은 명시적 승인 전까지 보류.

---


- 기준 빌드: `BUILD-00105`
- 기반 빌드: `BUILD-00104`
- 제품 버전: 미지정

## BUILD-00105 현재 상태 — Deterministic Local Photo Processing

### 구현

- Pillow 기반 로컬 이미지 조정 processor `pillow-local-1.0`을 추가했습니다. **생성형 AI가 아니라 결정론적 이미지 필터**입니다.
- `ENHANCE`: 채널 동적 범위가 의미 있을 때만 guarded autocontrast를 적용하고, 약한 color/sharpness 조정을 적용합니다.
- `LIGHTING`: 제한된 brightness/contrast 조정을 적용합니다.
- `BACKGROUND`, `RETOUCH`, `COMPOSE`는 실제 AI Photo Engine이 필요하므로 409로 차단합니다. 로컬 실행은 output_count=1, mask/reference 없음, target_style/prompt 없음 조건을 요구합니다.
- `POST /v1/photo-drafts/{draft_id}/process-local?workspace_id=...`는 8..128자의 `Idempotency-Key`가 필요합니다. `GET .../runs` 및 `GET .../runs/{run_id}/events`는 페이지네이션을 지원합니다.
- `photo_processing_runs`와 append-only `photo_processing_events`를 추가했습니다. 동일 key/동일 payload는 기존 성공 결과를 재사용하고, key/payload 충돌은 409, 동시 활성 run은 409, 실패 run은 원본 복구 후 같은 key로 재시도 가능합니다. 30분 lease 만료 후에는 stale run을 reclaim할 수 있습니다.
- 성공 시 새로운 private image Asset과 immutable AssetVersion v1, SHA-256, `derived_from` relation, `asset.photo_processed` provenance를 생성합니다. Asset ID는 run 기준 결정적이므로 DB commit 후 run ack 전 프로세스가 종료되어도 재시도 시 동일 자산을 검증/재사용합니다.
- 로컬 처리 결과 Asset은 retention workflow가 마련될 때까지 일반 삭제를 차단합니다.
- PhotoDraftWorkspace에 로컬 실행 버튼, run 상태, Output Asset/Version 표시를 추가했습니다.

### 품질/진실 경계

- run metadata는 `is_ai_generated=false`, `provider_dispatched=false`, `credit_charged=false`를 기록합니다.
- 출력 폭/높이는 입력과 동일합니다(`spatial_geometry_preserved=true`). 이는 픽셀 내 의미 보존 보증이 아닙니다.
- 인물 정체성 및 텍스트/로고의 의미적 보존은 검증하지 않았습니다. 결과는 사람이 검수해야 합니다.
- 실제 생성형 AI, background segmentation, semantic retouch, composition은 미구현/미검증입니다.

### 검증

- Backend pytest: 336 passed.
- 신규 Photo processing tests 4개: ENHANCE/LIGHTING, private output Asset/immutable version, derived relation/provenance, deletion guard, idempotent replay, key collision, unsupported operation fail-closed, output_count restriction, source checksum failure/retry, append-only run events, viewer role 검증.
- Python compileall (`app scripts tests`): passed.
- Viewer source structural validation: 51/51 passed. TypeScript/browser runtime 검증은 아닙니다.
- OpenAPI inventory: design 13 paths vs runtime 64 paths; exact match false.
- OpenAPI contract audit: 15 design operations; 12 structural drifts; 3 unmatched design operations (credit account, credit ledger, quote). Baseline YAML은 수정하지 않았습니다.
- TypeScript: NOT VERIFIED — React/Three.js dependency/type declarations absent (`TS2307`). Browser/WebGL/Android E2E 미검증.

### 다음 안전 작업

1. 실제 AI Photo Engine Provider 연결은 사용자의 비용·권리·보존 정책 승인 전까지 보류합니다. 그 전에는 로컬 품질 rubric/fixture 및 결과 review UX를 강화합니다.
2. Photo 결과의 검수/승인 및 Lookbook SKU/Variant 결과 연결을 통합하되, 내부 승인과 법적 게시/상업 권리를 구분합니다.
3. OpenAPI design/runtime drift를 operation 단위로 검토하고 승인된 contract reconciliation을 수행합니다.
4. TypeScript/browser/WebGL, PostgreSQL/object storage/multi-host 테스트 환경 확보 후 별도 검증합니다.

---


- 기준 빌드: `BUILD-00104`
- 기반 빌드: `BUILD-00103`
- 제품 버전: 미지정

## BUILD-00104 현재 상태 — Generated Output Review / Approval / Internal Export Manifest

### 구현

- SQLite migration v9: `generation_output_review_events`, `generation_output_export_events` 추가.
- Review/Export 이벤트는 DB trigger로 UPDATE/DELETE를 차단하는 append-only 구조입니다.
- `GET /v1/generation-jobs/{job_id}/outputs/{output_id}/review`: workspace member가 검수 상태/이력을 조회합니다. Output Asset link가 준비되지 않았으면 `asset_link_pending` 또는 `asset_link_failed`; 링크가 검증 완료되면 `pending_review`입니다.
- `POST .../review/approve`, `/review/request-changes`, `/review/reject`: owner/admin 전용. 변경 요청과 반려는 comment 필수. `changes_requested`는 재검토 가능하며 `approved`/`rejected`는 terminal입니다.
- 검수 결정은 Job이 succeeded이고 Output→Asset link가 `linked`이며 AssetVersion/Provenance/SHA-256이 모두 존재해야 가능합니다. 각 이벤트에 불변 Asset ID, Version ID, Provenance ID, checksum을 스냅샷으로 기록합니다.
- `POST /v1/generation-jobs/{job_id}/outputs/export-manifest`: succeeded Job의 모든 Output이 linked + individually approved인 경우에만 내부 metadata manifest를 생성합니다. SHA-256 및 append-only export audit를 기록합니다.
- Manifest에는 binary 파일이나 public URL이 없습니다. `publication_authorized=false`, `commercial_rights_verified=false`, `binary_files_included=false`를 명시합니다. 법적 권리/상업적 이용/게시 승인으로 해석하면 안 됩니다.
- Viewer에 `OutputReviewWorkspace.tsx/.css`를 추가하고 package index에서 export했습니다.

### 검증

- Backend pytest: 332 passed.
- 신규 Output review/export tests 2개: pending link gate, viewer role denial, required comments, changes_requested→approved, rejection/approval terminality, per-output approval gate, immutable AssetVersion/Provenance/checksum snapshot, manifest flags/hash/export audit 검증.
- Schema migration v9, idempotent initialization, review/export tables, append-only triggers 테스트 통과.
- Python compileall: passed.
- Viewer source structural validation: 49/49 passed. 이는 offline 정적 소스 검사이며 TypeScript compile 또는 browser runtime 검증이 아닙니다.
- OpenAPI runtime inventory: design 13 paths vs runtime 61 paths; exact match false.
- OpenAPI contract audit: 15 design operations; 12 structural drifts; 3 unmatched design operations (credit account, credit ledger, quote). Design YAML은 승인 없이 수정하지 않았습니다.
- TypeScript: NOT VERIFIED — React/Three.js dependency/type declarations absent (`TS2307`).
- Browser/WebGL/Android E2E: 미검증.

### 미완료/경계

- 실제 Provider generation, Photo Engine 2D generation, binary ZIP/export delivery, publication/commerce rights clearance는 미완료/미검증입니다.
- Output review approval은 내부 시각 품질/업무 승인이지 저작권·초상권·동의·브랜드·법무 clearance가 아닙니다.
- SQLite/local filesystem only. PostgreSQL runtime, object storage, multi-host, production deployment 미검증.
- Credit Quote/Ledger persistence 및 정책 결정 대기. 외부 FASHN 호출과 비용은 승인 전까지 보류.
- QA T-01..T-14 및 G0-G5는 PASS 증거가 없어 미통과.

### 다음 안전 작업

1. Photo Engine 실제 2D 처리와 Job/Output 경로의 contract/quality fixture 설계 및 테스트. Provider dispatch와 크레딧 차감은 정책/승인 전 실행 금지.
2. OpenAPI design/runtime drift를 operation 단위로 검토하고 승인된 contract reconciliation 수행.
3. TypeScript/browser/WebGL 테스트 환경 확보 후 실제 프런트엔드 통합 검증.
4. PostgreSQL/runtime repository ports, object storage, multi-host fencing의 별도 검증 계획 수립.

---


- 기준 빌드: `BUILD-00103`
- 기반 빌드: `BUILD-00102`
- 제품 버전: 미지정

## BUILD-00103 변경 — Failed Output Asset Link Retry / Audit

- Workspace owner/admin 전용 `POST /v1/generation-jobs/{job_id}/outputs/{output_id}/asset-link-retry`를 추가했습니다.
- Retry 사유는 필수이며 최대 2,000자입니다. `failed` 상태만 재시도 가능하며, pending/processing/linked 상태는 HTTP 409, link 없음은 404입니다. editor/viewer는 403입니다.
- 재시도는 task를 pending으로 되돌리고 attempts/lease/error 상태를 초기화하며, 같은 Generation DB transaction에서 append-only `output_asset_link.retry_requested` event를 기록합니다.
- Event에는 재시도 사유, 이전 실패 내용, 이전 시도 횟수가 보존됩니다. owner/admin 전용 `GET .../asset-link-events`로 감사 이력을 조회합니다.
- 재시도는 기존 deterministic Asset/Version/Provenance ID 및 linker를 재사용하므로 이전 작업이 Asset DB commit 후 Generation DB ack 전에 중단된 경우에도 중복 생성 없이 복구합니다.
- schema migration version 8 및 `generation_output_asset_link_events`를 추가했습니다.

## BUILD-00103 검증

- Backend pytest: 330 passed.
- Output Asset Link Worker tests: 4 passed; terminal failure retry, owner/admin role restrictions, required reason, duplicate retry rejection, audit event and successful recovery verified.
- Schema tests: 4 passed; migration history includes version 8 and retry event table exists.
- Python compileall: passed.
- Viewer source structural validation: 43/43 passed (no UI changes).
- OpenAPI runtime inventory: 13 design paths vs 56 runtime paths; exact match false.
- OpenAPI contract audit: 15 design operations; 12 structural drifts; 3 unmatched design operations (credit account, credit ledger, quote).
- TypeScript typecheck: NOT VERIFIED — React and type declarations are unavailable (TS2307).
- Browser/WebGL/Android E2E: 미검증.

## BUILD-00102 변경 — Generation Output → Asset/Version/Provenance Linker

- Output finalization transaction은 `generation_outputs` row와 함께 `generation_output_asset_links` outbox row를 Generation DB에 기록합니다. SHA-256 checksum을 함께 보존합니다. Migration은 safe attempt-scoped filename을 가진 succeeded legacy Output만 backfill하고, 다른 legacy 이름은 `not_queued`로 남겨 임의 파일 연결을 하지 않습니다.
- 별도 프로세스 `python -m app.output_asset_link_worker`가 outbox를 lease 기반으로 claim합니다.
- Worker는 private Output 파일의 크기/MIME/실제 이미지 디코딩/checksum을 검증한 뒤 Asset private storage로 복사하고 Asset DB에 Asset, immutable AssetVersion v1, `asset.generated_output_imported` Provenance를 생성합니다.
- Output별 deterministic Asset/Version/Provenance IDs와 storage key를 사용합니다. Asset DB commit 후 Generation DB ack 전에 프로세스가 죽어도 retry는 기존 Asset의 checksum/metadata를 확인하고 중복 생성 없이 link를 완료합니다.
- Generation DB와 Asset DB가 별도 SQLite 파일인 경우를 테스트했습니다. 두 DB 사이의 단일 atomic transaction을 주장하지 않으며, durable outbox + deterministic idempotency로 복구합니다.
- Output history는 checksum, `asset_link_status`, Asset/Version/Provenance IDs를 표시합니다. Storage key/path는 노출하지 않습니다. Job diagnostics의 Output metadata와 event payload에서도 storage key를 제거했습니다.
- `asset.generated_output_imported` provenance가 있는 Asset은 명시적 Output retention/detachment workflow가 구현될 때까지 일반 Asset 삭제를 차단합니다.
- `output_asset_link` worker heartbeat를 추가하고 default required worker set에 포함했습니다.
- 영구 validation/metadata conflict는 즉시 failed, transient failure는 설정된 횟수만큼 retry합니다. Failed link task의 수동 재시도 UI/API는 아직 없습니다.

## BUILD-00102 검증

- Backend pytest: 329 passed.
- Output Asset Link Worker tests: 3 passed; separate SQLite DBs, immutable Asset/Version/Provenance, checksum mismatch failure, deletion guard and crash-after-Asset-commit recovery verified.
- Schema tests: legacy `generation_outputs` table migration to `checksum_sha256` and link outbox verified.
- Python compileall: passed.
- Viewer source structural validation: 43/43 passed (no UI changes).
- OpenAPI runtime inventory: 13 design paths vs 54 runtime paths; exact match false.
- OpenAPI contract audit: 15 design operations; 12 structural drifts; 3 unmatched design operations (credit account, credit ledger, quote).
- TypeScript typecheck: NOT VERIFIED — React/Three.js dependencies unavailable.
- Browser/WebGL/Android E2E: 미검증.

## BUILD-00101 변경 — Job Execution / Output History APIs

- `GET /v1/generation-jobs/{job_id}/executions`: 인증된 Workspace 멤버만 조회할 수 있으며 최신 attempt부터 `limit`(1~100) + opaque cursor pagination을 지원합니다. attempt number, provider/model, status, request ID, timestamps, error code를 반환합니다.
- Cursor는 마지막 attempt number를 인코딩하며 잘못된 cursor는 HTTP 422입니다. `meta.next_cursor`, `meta.has_more`를 제공합니다.
- `GET /v1/generation-jobs/{job_id}/outputs`: 성공한 Job의 저장 Output metadata만 반환합니다. Output ID, Job ID, MIME type, size, created_at을 제공하며 private storage key/path는 절대 노출하지 않습니다.
- Job이 succeeded가 아니면 Output data는 빈 배열입니다. Binary download는 기존 인증된 `/output` route에 별도로 유지됩니다.
- Job repository port 및 SQLite adapter에 read methods를 추가했습니다. 미지원 repository는 SQLite fallback하지 않고 HTTP 501을 반환합니다.

## BUILD-00101 검증

- Backend pytest: 325 passed.
- Job execution/output history API test: 1 passed; workspace authorization, opaque cursor pagination, invalid cursor rejection, output metadata filtering, storage-key secrecy and no-output-before-success verified.
- Python compileall: passed.
- Viewer source structural validation: 43/43 passed (no UI changes in this build).
- OpenAPI runtime inventory: 13 design paths vs 54 runtime paths; exact match false.
- OpenAPI contract audit: 15 design operations; 12 structural drifts; 3 unmatched design operations (credit account, credit ledger, quote).
- TypeScript typecheck: NOT VERIFIED — React/Three.js dependencies unavailable.
- Browser/WebGL/Android E2E: 미검증.

## BUILD-00100 변경 — Lookbook Planning Review / Approval

- Lookbook 기획 초안 workflow: `DRAFT → IN_REVIEW → APPROVED` 또는 `IN_REVIEW → CHANGES_REQUESTED → IN_REVIEW`.
- `POST /v1/lookbook-drafts/{draft_id}/submit`, `/approve`, `/request-changes`; 승인된 기획안은 `GET .../manifest`로 plan-only manifest를 조회할 수 있습니다.
- Workspace owner/admin은 승인 및 수정 요청 가능, owner/admin/editor는 검토 제출 가능, viewer는 읽기 전용입니다.
- 수정 요청에는 비어 있지 않은 comment가 필요합니다. 모든 review transition과 의견은 append-only event로 기록됩니다.
- DRAFT/CHANGES_REQUESTED에서만 편집할 수 있고 IN_REVIEW/APPROVED는 잠깁니다. 수정 요청 상태에서 수정 후 재제출할 수 있습니다.
- 기존 Draft는 migration 후 `workflow_status=DRAFT`로 초기화됩니다. review metadata columns 및 index를 추가했습니다.
- Manifest는 `LOOKBOOK_PLAN_ONLY`, `generated_outputs_included=false`를 명시하고 기획 입력/참조 Asset ID만 포함합니다. 이미지 파일, AI 생성 결과, 상업 게시 승인을 포함하지 않습니다.
- `LookbookDraftWorkspace`에 제출, 승인, 수정 요청 및 manifest 조회 UI를 추가했습니다.

## BUILD-00100 검증

- Backend pytest: 324 passed.
- Lookbook review workflow tests: 2 passed; submit/approve/request-changes, role restrictions, required comments, edit lock, revision/resubmit, event history and plan-only manifest verified.
- Python compileall: passed.
- Viewer source structural validation: 43/43 passed.
- OpenAPI route inventory: 13 design paths vs 52 runtime paths; exact match false.
- OpenAPI contract audit: 15 design operations; 10 structural drifts; 5 unmatched design operations.
- TypeScript typecheck: NOT VERIFIED — React/Three.js dependencies unavailable.
- Browser/WebGL/Android E2E: 미검증.

## BUILD-00099 변경 — Variant-aware Lookbook Drafts

- `LookbookDraftInput.product_variant_ids`로 동일 Workspace의 활성 Product Variant를 최대 40개 선택할 수 있습니다.
- Variant 전용 이미지가 있으면 해당 이미지들을 우선 사용하고, 없으면 부모 Product의 활성 이미지 갤러리를 사용합니다.
- 선택한 이미지들은 `lookbook_draft_assets`에 스냅샷 저장되어 Draft가 활성인 동안 삭제가 차단됩니다.
- Lookbook entity history에는 부모 `product`와 `product_variant` 참조를 함께 기록합니다. 활성 Draft가 참조하는 부모 Product archive와 Variant update/archive는 HTTP 409로 차단됩니다.
- 기존 Project/Character/Product entity row를 보존하면서 `product_variant` 타입을 허용하도록 SQLite migration을 확장했습니다.
- `LookbookDraftWorkspace`에 Variant 다중 선택 UI와 이미지 fallback 안내를 추가했습니다.

## BUILD-00099 검증

- Backend pytest: 322 passed.
- Variant-aware Lookbook API tests: 2 passed; variant image resolution, parent gallery fallback, invalid variant rejection, active reference protections and migration behavior verified.
- Python compileall: passed.
- Viewer source structural validation: 41/41 passed.
- OpenAPI route inventory: 13 design paths vs 48 runtime paths; exact match false.
- OpenAPI contract audit: 15 design operations; 10 structural drifts; 5 unmatched design operations.
- TypeScript typecheck: NOT VERIFIED — React/Three.js dependencies unavailable.
- Browser/WebGL/Android E2E: 미검증.

## BUILD-00098 변경 — Project ↔ Product Assignment

- `GET/PUT /v1/projects/{project_id}/products`로 프로젝트에 활성 동일 Workspace Product를 최대 100개 연결/교체합니다.
- 연결된 상품의 선택 순서를 보존하고 변경할 수 있습니다. 동일 요청 반복은 추가 이벤트를 생성하지 않습니다.
- `project_product_assignments`는 `removed_at`으로 연결 종료를 보존하며 과거 행을 삭제하지 않습니다.
- `GET /v1/projects/{project_id}/product-events`에서 추가/제거/순서 변경의 append-only 이력을 확인할 수 있습니다.
- 활성 Project에 연결된 Product는 archive할 수 없습니다. 연결을 해제하거나 Project를 archive한 뒤 Product를 archive해야 합니다. archived Product는 Project의 활성 상품 목록에서 제외됩니다.
- `ProjectProductAssignmentWorkspace` UI를 추가해 프로젝트 선택, 다중 상품 연결, 순서 편집, 이력 표시를 제공합니다.

## BUILD-00097 변경 — Product Variant / Option Catalog

- `product_variants` 및 `product_variant_assets` 저장 구조를 추가했습니다.
- Product 하위 Variant는 독립 SKU, 선택 속성(`option_values`), 선택적 variant image assets, ACTIVE/ARCHIVED 상태를 가집니다.
- `POST/GET /v1/products/{product_id}/variants`, `PUT /v1/products/{product_id}/variants/{variant_id}`, `POST .../archive` API를 추가했습니다.
- Variant SKU와 Product master SKU는 Workspace 내 대소문자 무시 단일 네임스페이스를 공유합니다. create/update는 SQLite `BEGIN IMMEDIATE`로 직렬화하고 cross-table 중복을 HTTP 409로 거부합니다.
- 옵션 키는 lowercase identifier로 정규화하며 값은 1~80자 문자열입니다. variant image는 선택 사항이며 지정 시 동일 Workspace의 활성 image Asset이어야 합니다.
- 활성 Variant가 참조하는 이미지 삭제는 차단됩니다. Variant를 보관하거나 이미지 참조를 변경하면 보호가 해제됩니다.
- Product archive는 활성 하위 Variant도 같은 트랜잭션에서 archive합니다. 기존 Product/Variant/Event 기록은 삭제하지 않습니다.
- `ProductCatalogWorkspace`에 기본 색상/사이즈 Variant 생성 및 보관 UI를 추가했습니다.

## BUILD-00096 이전 기능 유지

- Workspace Product/SKU Catalog CRUD, 이미지 연결, Lookbook Draft catalog Product references.
- Photo Draft 입력 준비, Lookbook Draft 캠페인 구성, Image Asset 및 immutable AssetVersion, AssetRelation/Provenance.
- 3D Viewer와 asset workspace.

## BUILD-00098 검증

- Backend pytest: 320 passed.
- Project/Product assignment API tests: 3 passed; replace-set, ordered assignments, append-only history, active Project archive guard, archived Project release, workspace and role checks verified.
- Python compileall: passed.
- Viewer source structural validation: 40/40 passed.
- OpenAPI route inventory: 13 design paths vs 48 runtime paths; exact match false.
- OpenAPI contract audit: 15 design operations; 10 structural drifts; 5 unmatched design operations.
- TypeScript `npm run typecheck`: NOT VERIFIED — React/Three.js dependencies unavailable.
- Browser/WebGL/Android E2E: 미검증.

## BUILD-00097 검증

- Backend pytest: 317 passed.
- Product Variant 관련 테스트: 신규 3개 포함, SKU cross-table 충돌, 옵션 검증, 이미지 삭제 보호, update/archive, 부모 Product archive cascade 검증.
- Python compileall: passed.
- Viewer source structural validation: 37/37 passed.
- OpenAPI route inventory: 13 design paths vs 46 runtime paths; exact match false.
- OpenAPI contract audit: 15 design operations; 10 structural drifts; 5 unmatched design operations.
- TypeScript `npm run typecheck`: NOT VERIFIED — React/Three.js 패키지와 타입 선언이 설치되지 않아 실행 환경 검증 불가.
- Browser/WebGL/Android E2E: 미검증.

## 미완료 및 제한

- Lookbook Variant-aware Draft 준비는 구현됐지만 실제 이미지 생성, Job dispatch, SKU별 generated Output, 생성된 이미지의 품질 검수/승인/상업용 내보내기는 미구현입니다. 기획안 승인과 생성 결과 승인은 별도입니다.
- Photo Engine actual 2D processing 및 생성 결과물의 review/approval/export workflow는 미구현/미검증입니다. Lookbook 기획안 승인과 생성 결과물 승인은 별도입니다.
- 가격, 재고, 바코드, 창고, 세금, 공급사, Marketplace/ERP 동기화는 미구현입니다.
- SQLite + local filesystem만 구현/검증. PostgreSQL runtime adapter/live PG, object storage, multi-host fencing 미구현/미검증.
- Live FASHN actual generation은 API key, authorized input URL, 비용 승인 및 권리/보존 정책이 없어 미실행.
- Credit Quote/Ledger persistence는 계정 범위, unit precision, expiry/lot, partial capture, refund/payment, ADJUST approval, locking policy 결정 전 보류.
- Asset relation deletion/retention semantics 미결정.
- OpenAPI baseline/runtime 불일치: 12 structural drift, 3 design operations missing (credits/quote). BUILD-00102 보고서 기록 유지.
- QA T-01..T-14 및 G0-G5는 PASS 증거가 없어 미통과.

## 다음 안전 작업

1. Generated Output review/approval/export lifecycle tied to immutable AssetVersion and job provenance; no Provider dispatch or credit charging until the required approvals/policies are available.
2. OpenAPI design/runtime contract reconciliation as an explicit reviewed change, not silent spec rewrite.
3. TypeScript/browser/WebGL tests when dependency installation and browser runtime are available.


외부 Provider 호출, 과금, 법무/권리, 운영 데이터 변경은 사용자 승인 전까지 보류합니다.
