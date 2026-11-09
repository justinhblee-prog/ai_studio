# AI CREATOR STUDIO — OpenAPI / DTO Schema Mapping Audit v0.1

- 기준일: 2026-11-02
- 상태: 정적 점검 완료 / 구현 저장소 대조 전
- Owner: Backend Tech Lead
- Contributors: Backend Developer, QA, ChatGPT(PM/BA/QA)
- Approver: PO
- 대상: `AI_CREATOR_STUDIO_openapi_draft_v0_1.yaml`

## 1. 검증 범위와 결과

검증 대상 YAML은 OpenAPI 3.1.0 선언, 8개 path item, 24개 component schema, 107개 `$ref` 사용을 포함한다.

| 검사 | 결과 | 비고 |
|---|---|---|
| YAML parse | PASS | PyYAML 6.0.3 |
| OpenAPI version declaration | PASS | 3.1.0 |
| Local `$ref` resolution | PASS | 107개 참조 모두 로컬 경로 해석 |
| Path parameter declaration | PASS | `$ref` parameter를 역참조하여 확인 |
| Required property declaration | PASS | object schema의 required 항목이 properties에 존재 |
| OpenAPI dedicated validator | NOT RUN | `openapi-spec-validator`, `openapi-schema-validator`가 실행 환경에 설치되어 있지 않음 |
| Runtime FastAPI compatibility | NOT RUN | 실제 저장소 및 FastAPI 버전 미확인 |

주의: 최초 검사 스크립트가 `$ref` parameter를 역참조하지 않아 path parameter 4개를 누락으로 잘못 보고했다. 역참조를 반영해 재검사한 결과 오류 0건이다. 이는 OpenAPI 오류가 아니라 1차 검사기의 한계였다.

## 2. Endpoint ↔ DTO ↔ Use-case mapping

| Operation ID | Method / Path | Request DTO | Response DTO | Application 책임 | 주요 검증 |
|---|---|---|---|---|---|
| createAsset | POST /assets | AssetCreateRequest | AssetResponse | RegisterAsset | upload reference, workspace membership, asset type, display name |
| getAsset | GET /assets/{asset_id} | path AssetId | AssetResponse | GetAsset | tenant/workspace access, deleted/rejected visibility |
| createQuote | POST /quotes | QuoteCreateRequest | QuoteResponse | CreateQuote | feature input dispatch, asset readiness, policy, routing eligibility, quote expiry |
| createGenerationJob | POST /generation-jobs | JobCreateRequest | JobResponse | CreateGenerationJob | quote ownership/expiry/consumption, feature schema, credits, idempotency, outbox |
| listGenerationJobs | GET /generation-jobs | workspace_id, limit, cursor | JobListResponse | ListGenerationJobs | membership, workspace filter, cursor scope |
| getGenerationJob | GET /generation-jobs/{job_id} | path JobId | JobResponse | GetGenerationJob | tenant/workspace access |
| cancelGenerationJob | POST /generation-jobs/{job_id}/cancel | path JobId + Idempotency-Key | JobResponse | RequestJobCancellation | transition eligibility, provider cancellation capability, idempotency |
| listGenerationJobOutputs | GET /generation-jobs/{job_id}/outputs | path JobId | OutputListResponse | ListJobOutputs | job access, persisted output visibility |
| getCreditAccount | GET /credits/accounts/{account_id} | path account_id | CreditAccountResponse | GetCreditAccount | tenant/account membership, no cross-tenant balance disclosure |

총 9개 operation이 8개 path item에 배치되어 있다.

## 3. Schema ↔ Pydantic mapping

| OpenAPI schema | Python DTO / type | Mapping 상태 | 구현 메모 |
|---|---|---|---|
| Identifier | `Annotated[str, StringConstraints(min_length=1)]` | Direct | physical format 미확정 |
| Timestamp | timezone-aware `datetime` | Semantic | naive datetime 거부 권장 |
| ResponseMeta | `ResponseMeta` | Direct | request_id/correlation_id optional |
| ErrorDetail | `ErrorDetail` | Direct | field/reason |
| ErrorBody | `ErrorBody` | Direct | code/message/retryable required |
| ErrorResponse | `ErrorResponse` | Direct | error required, meta optional |
| AssetCreateRequest | `AssetCreateRequest` | Direct + policy | upload_reference를 실제 storage key로 취급 금지 |
| Asset | `AssetRead` | Direct | status enum, nullable project/current version |
| AssetResponse | `AssetResponse` | Direct | data required |
| QuoteCreateRequest | `QuoteCreateRequest` | Semantic | feature_input 현재 object 자유형; feature별 dispatch 필요 |
| Quote | `QuoteRead` | Direct | estimated_credits non-negative, expires_at |
| QuoteResponse | `QuoteResponse` | Direct | data required |
| RoutingRequest | `RoutingRequest` | Semantic | AUTO/MANUAL 상호 의존 검증은 OpenAPI에 없음 |
| TryOnInput | `TryOnInput` | Direct + domain | 두 Asset READY 및 같은 Workspace 권한 검증 |
| PhotoInput | `PhotoInput` | Direct + domain | source Asset READY 및 작업 권한 검증 |
| JobCreateRequest | `JobCreateRequest` | Semantic | feature_code ↔ feature_input oneOf dispatch |
| JobStatus | `JobStatus` enum | Direct | 상태 전이 유효성은 DTO가 아닌 Domain에서 검사 |
| GenerationJob | `GenerationJobRead` | Direct | API status와 내부 Execution status 구분 |
| JobResponse | `JobResponse` | Direct | data required |
| JobListResponse | `JobListResponse` | Semantic | meta allOf pagination 확장 |
| Output | `OutputRead` | Direct | asset_version_id는 현재 optional schema; 완료된 Output에서는 필수 정책 검토 |
| OutputListResponse | `OutputListResponse` | Direct | data required |
| CreditAccount | `CreditAccountRead` | Semantic | available/reserved balance non-negative invariant 필요 |
| CreditAccountResponse | `CreditAccountResponse` | Direct | data required |

## 4. 확인된 계약 공백 및 결정 제안

| ID | 관찰 | 위험 | 제안 / 상태 |
|---|---|---|---|
| MAP-01 | QuoteCreateRequest.feature_input은 자유 object | Quote와 Job 사이 입력 검증 차이 | feature별 DTO dispatch를 Quote/Job 공통 서비스에서 사용. 승인 전 제안 |
| MAP-02 | JobCreateRequest.oneOf에 discriminator 없음 | 코드 생성기/서버 validation별 분기 차이 | `feature_code`를 discriminator로 연결하거나 application dispatcher에서 엄격 검증. 도구 호환성 테스트 필요 |
| MAP-03 | LOOKBOOK이 enum에 있지만 input schema 미정 | 선언된 feature를 생성할 수 없음 | schema 확정 전 422로 차단하거나 LOOKBOOK을 API 지원 enum에서 제외하는 결정 필요 |
| MAP-04 | RoutingRequest에서 MANUAL + provider/model 관계 미정 | MANUAL이 의도와 다르게 AUTO fallback할 위험 | MANUAL은 명시 provider/model 필요로 제안. 기존 provider registry 확인 후 확정 |
| MAP-05 | Output.asset_version_id optional | 성공 Output lineage가 불완전할 수 있음 | SUCCEEDED Job Output에서는 필수 invariant로 두고 API schema required 여부 결정 |
| MAP-06 | CreditAccount.available_balance/reserved_balance 최소값 미지정 | 음수 잔액 표현 가능 | minimum: 0을 schema에 추가하는 변경 제안. 실제 조정/부채 모델 확인 필요 |
| MAP-07 | JobStatus에 REQUIRES_RECONCILIATION 포함 | 사용자 상태와 내부 운영 상태가 혼재 | 현재 공개 API 노출이 적절한지 검토. 숨기거나 별도 public status로 매핑할지 결정 필요 |
| MAP-08 | Quote create endpoint에는 Idempotency-Key 미포함 | 중복 Quote가 생성될 수 있음 | Quote가 비용 예약/소비를 하지 않는 순수 계산이면 optional; audit/cost control 필요 시 추가. 정책 결정 필요 |
| MAP-09 | Asset upload lifecycle endpoint가 OpenAPI 범위 밖 | T-02 upload 흐름을 API만으로 재현 불가 | upload session/create/complete 또는 signed URL 발급 계약을 별도 정의 |
| MAP-10 | GenerationJob 응답에 project_id, quote_id, execution summary, output summary 미포함 | UI/운영 조회에서 추가 API 호출 또는 추적 어려움 | 최소 response 요구사항 확인 후 확장. 과도한 내부 필드 노출 금지 |
| MAP-11 | ErrorBody code는 자유 string | 오탈자/클라이언트 분기 오류 | canonical error code enum/catalog를 별도 관리하고 OpenAPI enum 동기화 권장 |
| MAP-12 | Identifier string에 format/pattern 없음 | 잘못된 ID 형식 허용 | 저장소 ID 전략 확인 후 pattern 추가. 지금은 opaque string 유지 |

## 5. 권장 OpenAPI 후속 변경 묶음

### 변경안 A — 바로 정합성 개선 후보
- CreditAccount balance에 `minimum: 0` 추가(negative balance가 허용되지 않는다는 정책 확정 전제).
- Output의 `asset_version_id` required 여부를 SUCCEEDED Output invariant와 맞춤.
- Error code catalog를 schema component로 재사용 가능하게 정리.

### 변경안 B — feature input 안정화
- `TryOnInput`, `PhotoInput`, `LookbookInput`의 discriminator/dispatch 전략 확정.
- Quote와 Job이 동일한 feature input validation service를 사용하도록 명시.
- LOOKBOOK 미지원 기간의 HTTP/API 동작 결정.

### 변경안 C — upload contract 보완
- Upload session 발급, upload completion, validation status 조회 흐름을 명세.
- Signed URL, storage key, raw object path는 외부 API 응답에서 구분하고 내부 storage key를 노출하지 않음.

이 변경은 현재 v0.1 파일을 조용히 덮어쓰지 않고, Decision Register 및 OpenAPI v0.2 변경안으로 별도 관리한다.

## 6. 검증 방법 재현

사용한 정적 검증:
- Python 3 YAML parser: PyYAML 6.0.3
- local `$ref` traversal: all 107 references resolved
- path template parameter check: path-level + operation-level parameter `$ref` dereference
- object `required` member check

실행하지 않은 검증:
- OpenAPI 전용 validator
- FastAPI route generation / runtime schema export
- generated client compatibility
- repository contract tests

## 7. 변경 이력

- v0.1: OpenAPI Draft v0.1의 정적 YAML/reference/path/schema 검증과 Pydantic mapping, 계약 공백 및 후속 변경 제안을 기록.
