# AI CREATOR STUDIO — Backend Implementation Blueprint v0.1

- 기준일: 2026-11-02
- 상태: 구현 설계 기준안 / 실제 저장소 대조 전
- Owner: Tech Lead
- Contributors: Backend Developer, QA, ChatGPT(PM/BA/QA)
- Approver: PO
- 기준 문서: OpenAPI Draft v0.1, Common Data Model Dictionary v0.1, API Error / Idempotency / Recovery Spec v0.1, Requirements Traceability Matrix v1.0
- 구현 상태: 미착수 판정이 아니라 **저장소 및 실행 증거 미확인**. 이 문서는 코드가 이미 존재한다고 주장하지 않는다.

> 목적은 기존 OpenAPI 초안을 실제 FastAPI/Pydantic 구현으로 옮길 때 필요한 경계, 검증 규칙, 트랜잭션, 상태 전이, 테스트 계약을 하나의 기준으로 고정하는 것이다. 실제 패키지 경로, ORM, DB, Queue, 인증 방식은 저장소 확인 후 매핑한다.

---

## 1. 설계 결정과 미확정 항목

| 항목 | 이 문서의 기준 | 확정 조건 |
|---|---|---|
| API prefix | `{API_BASE}` | 기존 저장소 라우터 및 배포 설정 확인 |
| DTO | Pydantic v2 기준 예시 | 설치 버전 및 기존 모델 확인 |
| DB | 관계형 트랜잭션 전제 | 실제 DB/ORM 확인 |
| ID | opaque string | 기존 ID 생성기 및 컬럼 확인 |
| Auth | 인증 주체에서 Organization/Membership/Workspace scope 도출 | 기존 인증·권한 구현 확인 |
| Queue | at-least-once 전달 가정 | 실제 Queue/Worker 확인 |
| Provider retry | Capability/정책 기반 | Provider 계약 및 실제 API 기능 확인 |
| LOOKBOOK input | 별도 schema 미정 | 요구사항 및 OpenAPI discriminator 결정 |

절대 불변 조건:
1. Organization 및 Membership 경계를 제거하지 않는다.
2. 사용자가 전달한 `workspace_id`만 믿지 않고 인증된 Membership으로 접근을 검증한다.
3. Credit RESERVE 성공 전에 Provider 실행을 시작하지 않는다.
4. 같은 멱등성 범위와 Key에서 요청 본문이 달라지면 `409 IDEMPOTENCY_CONFLICT`다.
5. Provider 성공만으로 Job을 `SUCCEEDED` 처리하지 않는다. Output 파일 및 DB 참조가 영속화되어야 한다.
6. Provider 결과가 불명확하면 무조건 재호출하지 않는다.
7. 모든 Credit 변경은 append-only Ledger event로 남긴다.

## 2. 권장 모듈 경계

저장소 구조를 확인하기 전의 논리 패키지 제안이다. 기존 구조가 있으면 동일 책임을 가진 기존 모듈에 매핑하고 불필요한 재배치를 하지 않는다.

```text
backend/
  app/
    api/
      dependencies/          # authenticated principal, tenant scope
      routers/               # assets, quotes, generation_jobs, credits
      exception_handlers.py
    schemas/
      common.py              # Identifier, Timestamp, Meta, Error
      assets.py
      quotes.py
      jobs.py                # generic Job + feature input models
      credits.py
    domain/
      assets/                # entities, policies, domain services
      jobs/                  # state machine, transition policy
      credits/               # ledger invariants and balance policy
      routing/               # provider/model/capability policy
    application/
      commands/              # create asset/job, cancel job
      queries/               # get/list job, get credit account
      ports/                 # repositories, queue, storage, providers
    infrastructure/
      persistence/           # ORM/repositories/transaction boundary
      queue/
      storage/
      providers/             # provider adapters
    workers/
      outbox_publisher.py
      generation_worker.py
      reconciliation_worker.py
    tests/
      contract/
      domain/
      integration/
```

의존성 방향은 `api → application → domain`이며 infrastructure는 application port를 구현한다. Domain은 FastAPI, ORM, Queue SDK, 특정 Provider SDK에 직접 의존하지 않는다.

## 3. Pydantic DTO 계약

### 3.1 공통 타입

- `Identifier`: non-empty string. UUID 등 물리 형식은 저장소 확인 전 강제하지 않는다.
- `Timestamp`: timezone-aware datetime만 허용하고 API 출력은 ISO 8601로 직렬화한다.
- 외부 API 입력 모델은 `extra='forbid'`를 기본으로 한다. 단, 현재 OpenAPI에서 `feature_input`만 `additionalProperties: true`로 열려 있으므로 feature별 DTO로 좁혀 검증한다.
- 출력 DTO는 DB ORM 객체를 직접 노출하지 않고 명시적으로 매핑한다.
- PATCH 미정의 상태에서 `null`과 필드 누락을 같은 의미로 처리하지 않는다.

### 3.2 요청 DTO의 필수 검증

| DTO | 검증 |
|---|---|
| AssetCreateRequest | workspace_id, asset_type, display_name, upload_reference 필수. display_name 1~200. upload_reference는 만료·1회성 여부를 서버에서 검증하고 storage key로 직접 취급하지 않음 |
| QuoteCreateRequest | feature_code ∈ TRY_ON/PHOTO/LOOKBOOK. feature_input은 feature_code에 대응하는 스키마로 검증. routing.mode는 AUTO/MANUAL |
| TryOnInput | source_asset_id, person_asset_id 필수. output_count 1~10. 두 Asset의 workspace 접근·READY 상태 확인 |
| PhotoInput | source_asset_id, operation 필수. operation ∈ ENHANCE/BACKGROUND/LIGHTING/RETOUCH/COMPOSE. output_format ∈ PNG/JPEG/WEBP |
| JobCreateRequest | workspace_id, feature_code, quote_id, feature_input 필수. Quote의 workspace/feature/만료/미소비 여부를 서버에서 재검증 |
| Idempotency-Key | 필수 적용 endpoint에서 공백 제거 후 8~255자. 동일 Key + 다른 canonical request hash는 충돌 |

### 3.3 Feature input dispatch

`feature_code`와 입력 DTO의 조합은 반드시 일치해야 한다.

| feature_code | 입력 DTO | 현재 상태 |
|---|---|---|
| TRY_ON | TryOnInput | OpenAPI 초안 정의됨 |
| PHOTO | PhotoInput | OpenAPI 초안 정의됨 |
| LOOKBOOK | TBD | 현재 OpenAPI에 schema 없음. 임의로 TryOnInput/PhotoInput을 재사용하지 않음 |

Pydantic v2의 `model_validator(mode='after')` 또는 별도 factory에서 조합을 검사한다. LOOKBOOK은 별도 명세가 승인될 때까지 `422 FEATURE_INPUT_SCHEMA_UNAVAILABLE`로 거부하는 방안을 권장한다. 이는 API 호환성 검토 후 확정한다.

### 3.4 예시 코드 — DTO 형태

아래 코드는 Pydantic v2 기준의 구현 예시이며 기존 프로젝트 코드가 아니다.

```python
from datetime import datetime
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Identifier = Annotated[str, StringConstraints(min_length=1, strip_whitespace=True)]
DisplayName = Annotated[str, StringConstraints(min_length=1, max_length=200, strip_whitespace=True)]

class StrictInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

class RoutingRequest(StrictInput):
    mode: Literal["AUTO", "MANUAL"] = "AUTO"
    provider_id: Identifier | None = None
    model_id: Identifier | None = None

    @model_validator(mode="after")
    def manual_requires_target(self):
        if self.mode == "MANUAL" and (not self.provider_id or not self.model_id):
            raise ValueError("MANUAL routing requires provider_id and model_id")
        if self.mode == "AUTO" and (self.provider_id or self.model_id):
            raise ValueError("AUTO routing must not pin provider_id/model_id")
        return self

class TryOnInput(StrictInput):
    source_asset_id: Identifier
    person_asset_id: Identifier
    garment_category: str | None = None
    preserve_person_identity: bool = True
    preserve_garment_details: bool = True
    output_count: int = Field(default=1, ge=1, le=10)

class PhotoInput(StrictInput):
    source_asset_id: Identifier
    operation: Literal["ENHANCE", "BACKGROUND", "LIGHTING", "RETOUCH", "COMPOSE"]
    preserve_identity: bool | None = None
    preserve_product_geometry: bool | None = None
    preserve_text_and_logo: bool | None = None
    target_style: str | None = None
    output_format: Literal["PNG", "JPEG", "WEBP"] | None = None

class JobCreateRequest(StrictInput):
    workspace_id: Identifier
    project_id: Identifier | None = None
    feature_code: Literal["TRY_ON", "PHOTO", "LOOKBOOK"]
    quote_id: Identifier
    identity_profile_id: Identifier | None = None
    brand_profile_id: Identifier | None = None
    routing: RoutingRequest | None = None
    feature_input: dict

    @model_validator(mode="after")
    def validate_feature_input(self):
        if self.feature_code == "TRY_ON":
            TryOnInput.model_validate(self.feature_input)
        elif self.feature_code == "PHOTO":
            PhotoInput.model_validate(self.feature_input)
        else:
            raise ValueError("LOOKBOOK input contract is not defined")
        return self
```

주의: `MANUAL` routing에서 provider_id/model_id 필수 여부는 정책 후보이며, OpenAPI 초안의 현재 schema에는 상호 의존 검증이 없다. 실제 Provider Registry 계약과 PO/Tech Lead 결정을 거쳐 확정한다.

## 4. Job 상태 머신 계약

### 4.1 상태 정의

| 상태 | 의미 | 사용자에게 terminal인가? |
|---|---|---|
| QUEUED | Job 및 Outbox가 커밋되어 실행 대기 | 아니오 |
| RESERVED | Credit 예약 및 실행 claim 완료 | 아니오 |
| RUNNING | Provider 실행 중 | 아니오 |
| CANCEL_REQUESTED | 취소 요청이 접수되어 Provider/Worker 조정 중 | 아니오 |
| SUCCEEDED | Output 영속화, Credit CAPTURE 완료 | 예 |
| FAILED | 재시도 불가 실패 및 Credit 보상 처리 완료 | 예 |
| CANCELED | 취소 확정 및 Credit RELEASE 처리 완료 | 예 |
| REQUIRES_RECONCILIATION | Provider/결제/저장 결과 불명으로 수동 또는 자동 조정 필요 | 아니오(운영 보류) |

### 4.2 허용 전이

| From | To | 조건/행위 |
|---|---|---|
| QUEUED | RESERVED | Worker가 원자적으로 Execution claim 및 예약 상태 확인 |
| QUEUED | CANCELED | 실행 claim 이전 취소. Credit 예약이 없으면 원장 변경 없음 |
| RESERVED | RUNNING | Provider 호출 직전 정책·Asset·예약 재검증 |
| RESERVED | CANCELED | Provider 호출 전 취소, Credit RELEASE |
| RUNNING | SUCCEEDED | Output 저장 및 DB 참조 검증 + Credit CAPTURE 성공 |
| RUNNING | FAILED | 확정 실패, 재시도 소진, 보상 원장 처리 완료 |
| RUNNING | CANCEL_REQUESTED | 취소 요청 접수 |
| RUNNING | REQUIRES_RECONCILIATION | Provider 결과/과금 여부 불명 |
| CANCEL_REQUESTED | CANCELED | Provider 취소 또는 미실행 확인 + Credit RELEASE/정산 |
| CANCEL_REQUESTED | SUCCEEDED | 취소 race에서 결과가 먼저 완료되고 Output/CAPTURE가 확정된 경우 |
| CANCEL_REQUESTED | REQUIRES_RECONCILIATION | 취소 및 Provider 결과 불명 |
| REQUIRES_RECONCILIATION | SUCCEEDED | 결과 회수·Output 영속화·CAPTURE 완료 |
| REQUIRES_RECONCILIATION | FAILED | 실행 실패 확인 및 Credit RELEASE/환불 정합성 완료 |
| REQUIRES_RECONCILIATION | CANCELED | 실행되지 않았거나 취소 확인 + Credit RELEASE 완료 |

그 외 전이는 거부하고 `409 RESOURCE_CONFLICT` 또는 도메인 오류를 반환한다. `SUCCEEDED`, `FAILED`, `CANCELED`에서 일반 재실행 전이는 허용하지 않는다. 재시도는 Job을 덮어쓰지 않고 새 Execution/Attempt로 기록한다.

### 4.3 원자적 전이 구현 규칙

- 상태 변경은 `UPDATE ... WHERE id = ? AND status = ? AND version = ?` 형태의 compare-and-set 또는 동등한 row lock으로 수행한다.
- 각 전이에는 `from_status`, `to_status`, `reason_code`, `actor_type`, `execution_id`, `correlation_id`, `created_at` 이력을 남긴다.
- Job 상태와 해당 전이에 필수인 Ledger/Outbox 변경은 같은 DB 트랜잭션에 묶는다.
- 외부 Provider 호출은 DB 트랜잭션 안에서 수행하지 않는다.
- `SUCCEEDED`는 Output row, AssetVersion 참조, 파일 존재/검증, Credit CAPTURE가 모두 확인된 뒤에만 커밋한다.

## 5. Credit Ledger 트랜잭션 설계

### 5.1 원장 이벤트

| Event | Balance effect | 조건 |
|---|---:|---|
| RESERVE | available 감소, reserved 증가 | 충분한 available balance |
| CAPTURE | reserved 감소 | 해당 Job/Reservation이 유효하고 성공 정산 가능 |
| RELEASE | reserved 감소, available 증가 | 실행 취소/실패 등 미사용분 확정 |
| REFUND | 정책에 따라 available 증가 또는 별도 환불 계정 반영 | 기존 CAPTURE에 대한 참조 필수 |
| ADJUST | 승인된 조정 | 사유, actor, 참조, 감사 로그 필수 |

Ledger는 append-only이며 기존 이벤트를 수정/삭제하지 않는다. 정정은 역분개 또는 신규 ADJUST/REFUND 이벤트로 표현한다.

### 5.2 최소 중복 방지 키

`(organization_id, credit_account_id, idempotency_scope, idempotency_key, event_type)` 조합 또는 이에 준하는 유일성 보장을 둔다. 실제 unique index는 기존 스키마를 확인한 뒤 확정한다. 같은 원장 작업 재전송은 기존 결과를 반환하고 잔액을 다시 변경하지 않는다.

### 5.3 예약 트랜잭션 의사 코드

```text
BEGIN
  lock credit_account row
  verify tenant/workspace membership and account ownership
  verify quote belongs to workspace, is unexpired and unconsumed
  verify idempotency record:
    same key + same request hash -> return existing job/result
    same key + different hash -> IDEMPOTENCY_CONFLICT
  verify available_balance >= quote.estimated_credits
  append RESERVE ledger event
  update cached account balances (if used)
  insert generation_job(status=QUEUED)
  insert execution(status=PENDING, attempt_no=1)
  mark quote consumed by this job
  insert outbox event JOB_QUEUED
  persist idempotency result reference
COMMIT
```

동시 예약은 account row lock 또는 serializable/atomic conditional update로 보호한다. 잔액 캐시를 보유하더라도 원장과 같은 트랜잭션으로 변경하고 정기 reconciliation으로 대조한다.

### 5.4 CAPTURE/RELEASE 규칙

- 동일 reservation에 대해 CAPTURE와 RELEASE가 동시에 성공할 수 없다.
- CAPTURE/RELEASE는 원본 RESERVE event ID를 참조한다.
- CAPTURE 또는 RELEASE 재시도는 unique constraint 및 트랜잭션으로 한 번만 반영한다.
- Provider 비용이 예상 크레딧을 초과하는 경우 자동 추가 차감하지 않는다. 승인된 가격 정책 또는 별도 조정 흐름이 필요하다.
- Provider 성공 후 Output 저장 실패는 즉시 CAPTURE 또는 RELEASE를 임의 선택하지 않고, 결과 회수/저장 재시도 및 `REQUIRES_RECONCILIATION` 정책에 따른다.

## 6. Provider Adapter 인터페이스

Provider SDK를 Domain/Application에 노출하지 않는다. Adapter는 정규화된 입력·출력·오류만 제공한다.

```python
from dataclasses import dataclass
from typing import Protocol, Mapping, Any

@dataclass(frozen=True)
class ProviderRequest:
    execution_id: str
    feature_code: str
    model_id: str
    payload: Mapping[str, Any]
    idempotency_reference: str | None

@dataclass(frozen=True)
class ProviderAccepted:
    provider_request_id: str | None
    provider_job_id: str | None
    status: str  # ACCEPTED | RUNNING | SUCCEEDED | FAILED | UNKNOWN
    raw_status_code: str | None = None

@dataclass(frozen=True)
class ProviderResult:
    provider_request_id: str | None
    outputs: list[Mapping[str, Any]]
    usage: Mapping[str, Any] | None = None

@dataclass(frozen=True)
class ProviderFailure:
    code: str
    retryable: bool
    outcome_unknown: bool
    retry_after_seconds: int | None = None
    safe_message: str = "Provider execution failed"

class ProviderAdapter(Protocol):
    async def submit(self, request: ProviderRequest) -> ProviderAccepted: ...
    async def get_status(self, provider_job_id: str) -> ProviderAccepted: ...
    async def fetch_result(self, provider_job_id: str) -> ProviderResult: ...
    async def cancel(self, provider_job_id: str) -> ProviderAccepted: ...
```

Capability Registry는 최소한 다음을 기록한다: `supports_idempotency`, `supports_status_lookup`, `supports_callback`, `supports_cancel`, `max_output_count`, `supported_features`, `regions`, `data_retention_policy`, `training_use_policy`, `rights_constraints`, `retry_policy`.

`MANUAL`은 지정 Provider/Model만 사용하고 자동 fallback하지 않는다. `AUTO`는 사전에 정의된 hard filter(기능/지역/권리/보안/입력 크기) 통과 후 scoring하며, fallback 허용 정책이 명시된 경우에만 다음 Provider로 이동한다.

## 7. Worker / Outbox 처리 순서

1. Outbox Publisher가 미발행 이벤트를 lease/lock으로 claim한다.
2. Queue publish 성공 후 `published_at`을 기록한다. publish와 DB update 사이 crash는 중복 publish를 만들 수 있으므로 consumer 멱등성이 필수다.
3. Consumer가 `event_id`를 중복 확인하고 Execution claim을 원자적으로 시도한다.
4. Job/Execution/Asset/Quote/Reservation의 유효성을 재검증한다.
5. Provider Adapter를 호출하고 provider request/job ID를 저장한다.
6. 비동기 Provider는 callback/polling으로 상태를 갱신한다.
7. 결과 다운로드, MIME/signature/size 검사, malware scanning 정책 적용, Object Storage 저장을 수행한다.
8. AssetVersion/Output DB 참조를 저장하고 결과 접근 가능성을 검증한다.
9. Credit CAPTURE 후 Job SUCCEEDED를 동일한 정합성 경계에서 확정한다.
10. 알림/후속 이벤트는 Outbox로 발행한다.

Worker가 중간 종료되면 lease 만료 후 재획득한다. Provider 호출이 시작된 Execution은 단순히 처음부터 재호출하지 않고 Provider 상태 조회 및 실행 결과 조정 절차를 먼저 수행한다.

## 8. 오류 매핑 기준

| 내부 원인 | API code | HTTP | 자동 재시도 |
|---|---|---:|---|
| Pydantic/schema validation | VALIDATION_ERROR | 400 | 아니오 |
| Membership/tenant scope mismatch | FORBIDDEN 또는 RESOURCE_NOT_FOUND | 403/404 | 아니오 |
| Idempotency key + hash mismatch | IDEMPOTENCY_CONFLICT | 409 | 아니오 |
| Quote expired/consumed | QUOTE_EXPIRED / QUOTE_ALREADY_CONSUMED | 409 | 새 Quote 또는 기존 Job 조회 |
| Insufficient balance | INSUFFICIENT_CREDITS | 409 | 아니오 |
| Provider definite transient failure | PROVIDER_CAPACITY_EXCEEDED 등 | 502/503 | Capability 정책에 따름 |
| Provider timeout, execution unknown | PROVIDER_RESULT_UNKNOWN | 504 | 상태 조회/조정 전 재호출 금지 |
| Output persistence failure | OUTPUT_PERSISTENCE_FAILED | 500/503 내부 처리 | 저장 단계만 제한 재시도 |
| Credit ledger invariant failure | CREDIT_RECONCILIATION_REQUIRED | 500 내부 처리 | 자동 성공/중복 차감 금지 |

공개 오류 응답에는 내부 Provider 메시지, credential, raw payload, storage key, stack trace를 포함하지 않는다. `request_id`와 `correlation_id`로 운영 로그를 연결한다.

## 9. 테스트 계약 및 원본 QA ID 연결

기존 T-01~T-14 식별자와 의미를 유지한다.

| 기존 ID | 구현 검증 포인트 | 필수 관측 증거 |
|---|---|---|
| T-01 | 인증 및 Organization/Membership/Workspace 접근 | 허용/거부 테스트 로그 |
| T-02 | 유효 이미지 업로드 및 완료 | Asset READY 및 파일 검증 결과 |
| T-03 | MIME/signature/size 거부 | 각각의 오류 코드 및 파일 미등록 증거 |
| T-04 | 타 Organization Asset/Job ID 접근 | 정보 노출 없는 거부 응답 |
| T-05 | Quote 후 Job 생성 | Quote 검증, RESERVE, Job, Outbox 원자성 |
| T-06 | 잔액 부족 | Provider 호출 0회, Ledger 변경 없음 |
| T-07 | Provider 성공 및 결과 영속화 | Storage object, AssetVersion, Output, CAPTURE, SUCCEEDED 순서 |
| T-08 | 같은 Idempotency Key 재전송 | Job/RESERVE 중복 생성 0건 |
| T-09 | Provider timeout/unknown | 자동 중복 호출 차단 및 reconciliation 기록 |
| T-10 | 실행 중 취소 | cancel race 및 최종 상태/원장 정합성 |
| T-11 | 원본과 생성 결과 비교 | source/output 참조 및 UI 접근 증거 |
| T-12 | 실패/재시도/fallback 이력 | Execution attempt와 routing decision 로그 |
| T-13 | DB commit 후 queue publish 전 crash | Outbox 재발행 및 단일 실행 효과 |
| T-14 | Provider 성공 후 결과 저장 실패 | SUCCEEDED 금지, 복구 또는 reconciliation 증거 |

추가 구현 테스트는 신규 ID를 부여하되 T-01~T-14를 대체하지 않는다.

## 10. 구현 순서 및 완료 조건

| 순서 | 작업 | Owner | 산출물 | 완료 조건 |
|---:|---|---|---|---|
| 1 | 기존 저장소 구조/버전/실행 명령 확인 | Tech Lead / Backend Developer | Repo Evidence Map | commit, tree, dependency, run/test 결과 |
| 2 | OpenAPI와 기존 라우터/DTO 대조 | Backend Developer | API Mapping | endpoint/schema별 기존/신규/충돌 표 |
| 3 | DTO 및 공통 오류 처리 | Backend Developer | Pydantic models + handlers | OpenAPI schema contract tests 통과 |
| 4 | Job state machine 및 domain service | Backend Developer | transition policy + tests | 허용/금지 전이 테스트 통과 |
| 5 | Credit Ledger transaction | Backend Developer | ledger service + DB constraints | 동시 예약/중복 CAPTURE/RELEASE 테스트 통과 |
| 6 | Provider Adapter port + mock adapter | Backend Developer | adapter contract + fake | timeout/unknown/cancel/lookup 계약 테스트 통과 |
| 7 | Outbox/Worker recovery | Backend Developer | publisher/consumer/reconciler | T-13/T-14 재현 및 복구 증거 |
| 8 | 실제 Provider 연결 | Backend Developer + PO | Provider evidence pack | 실제 요청/응답/비용/권리/지역 정책 기록 |

### Definition of Done
- 코드 변경은 실제 저장소 branch/commit에 연결되어야 한다.
- Unit/contract/integration test 결과와 실행 명령을 보존한다.
- 테스트 실패를 숨기거나 Mock 통과를 실제 Provider 통과로 표현하지 않는다.
- DB migration 및 rollback 전략을 제시한다.
- API 문서, 구현, QA matrix의 버전이 일치해야 한다.
- 미확정 항목은 임의 확정하지 않고 Decision Register에 기록한다.

## 11. 남은 결정 사항

1. API prefix 및 기존 라우터 호환성.
2. Pydantic/FastAPI 실제 버전과 validation error envelope 호환성.
3. LOOKBOOK input schema 및 discriminator.
4. MANUAL routing에서 provider/model 필수 규칙.
5. Quote 소비 시점과 만료/재사용 정책.
6. Job 상태와 Execution 상태의 물리 테이블 분리 여부.
7. Credit account lock/conditional update 전략 및 DB isolation level.
8. Provider별 idempotency/status lookup/cancel 지원 범위.
9. Output storage consistency 및 orphan cleanup 정책.
10. Credit capture 단위, 부분 성공/부분 결과 비용 정책.

이 결정들은 저장소와 실제 Provider 계약을 확인하기 전에는 확정하지 않는다.

---

## 12. 변경 이력

- v0.1: OpenAPI Draft v0.1과 오류·멱등성·복구 규격을 기준으로 DTO, 상태 머신, Credit Ledger, Provider Adapter, Worker, QA 구현 계약을 통합 정리.
