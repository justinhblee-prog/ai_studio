# AI CREATOR STUDIO — 공통 데이터 모델 사전

- 문서 버전: v0.1
- 기준일: 2026-11-02
- 상태: Draft / 개발자 검토 및 PO 승인 전
- 문서 유형: 논리 데이터 모델·엔터티 사전
- 상위 기준: 통합 실행 기준 v0.2, 기술 아키텍처 구현 v0.2, 요구사항 추적 매트릭스 v1.0, API 계약·설계 결정 등록부 v0.1
- 관련 Gate: G0~G5
- 승인 상태: 미승인

> 이 문서는 논리 모델 제안이다. 실제 DB 테이블, ORM 클래스, 컬럼 타입, 인덱스, 외래 키, 마이그레이션 또는 API 경로가 현재 저장소에 존재한다고 주장하지 않는다. 모든 물리 구현 매핑은 Termux 저장소 G0 감사 이후 개발자가 작성하고 PO가 제품 의미를 승인한다.

---

## 1. 목적과 적용 원칙

이 문서는 AI CREATOR STUDIO의 공통 데이터 언어를 정의한다. 제품 기능별로 데이터 구조가 중복되는 것을 막고, Workspace 권한 경계, Asset 버전, 비동기 Job, Provider 실행, Output, Credit Ledger, Review, Rights/Provenance를 일관되게 연결하는 것이 목적이다.

### 1.1 모델링 원칙

1. **Organization / Membership / Workspace 유지**: Workspace 중심 UX로 단순화하더라도 조직과 멤버십·역할 검증을 제거하지 않는다.
2. **Workspace 소유권 우선**: Project와 Asset의 실제 소유권·공유 방식은 ADR 승인 전 제안으로 둔다. 교차 Workspace 접근은 명시적 권한 관계 없이는 금지한다.
3. **Asset과 AssetVersion 분리**: 논리 자산과 변경 불가능한 파일 버전을 구분한다. 새 결과는 원본 덮어쓰기가 아니라 새 버전/파생 자산으로 추적한다.
4. **Job / Execution / Event / Output 분리**: 사용자 요청, Provider 실행 시도, 상태 이력, 결과물을 한 레코드에 혼합하지 않는다.
5. **Credit Ledger append-only**: 잔액을 직접 덮어쓰는 방식 대신 예약·확정·해제·환불·조정 거래를 추가한다. 캐시 잔액은 원장 재계산이 가능한 파생값이어야 한다.
6. **Provider-neutral**: Provider별 필드와 비밀정보를 공통 도메인 모델에 노출하지 않고 Adapter/Capability/Policy 경계로 격리한다.
7. **권리·출처 추적**: 업로드·참조·생성·파생·내보내기 결과의 권리 선언과 출처를 연결한다.
8. **상태는 명시적 전이**: 상태 변경은 검증 가능한 전이 규칙과 이벤트/감사 기록을 남긴다.
9. **비동기 작업의 복구 가능성**: 중복 이벤트, timeout, 결과 불명, Worker 중단, 저장 실패를 복구할 수 있어야 한다.
10. **미결정 사항은 미결정으로 표시**: 저장소 확인 전 실제 경로·테이블·타입·정책을 단정하지 않는다.

### 1.2 상태 표기

- **제안**: 논리 설계 권고이며 아직 승인되지 않음.
- **저장소 감사 필요**: 기존 코드·DB·클라이언트·배포 설정을 확인해야 결정 가능.
- **Provider 확인 필요**: 실제 공급자 API/약관/기능에 따라 달라짐.
- **PO 승인 필요**: 제품 정책·권리·비용·운영 결정이 필요.
- **확정된 제품 경계**: 현재 프로젝트 기준선에서 기능 경계가 정해진 사항. 물리 구현 확정을 뜻하지 않음.

---

## 2. 논리 도메인 구성

| 영역 | 핵심 엔터티 | 책임 |
|---|---|---|
| Tenant & Access | Organization, Membership, Workspace, Role/Permission | 조직·사용자 소속·Workspace 접근 통제 |
| Work Management | Project, SKU, ProjectAssetRelation | 작업 단위·상품 식별·프로젝트와 자산의 연결 |
| Asset & Identity | Asset, AssetVersion, AssetRelation, CharacterIdentityProfile, BrandProfile | 파일·버전·파생 관계·캐릭터/브랜드 정체성 |
| AI Orchestration | Provider, Model, Capability, Policy, Quote, GenerationJob, JobExecution, JobEvent | 공급자 선택·비용 견적·작업 실행·이벤트 |
| Output & Review | GenerationOutput, Review, Approval, ExportRecord | 결과 연결·품질 검수·승인·내보내기 |
| Credits & Usage | CreditAccount, CreditLedgerEntry, UsageRecord | 크레딧 예약/확정/반환·실제 사용량 |
| Rights & Governance | RightsDeclaration, ProvenanceRecord, License, Entitlement, AuditEvent, DataRetentionRequest | 권리·출처·사용허가·감사·보존/삭제 |
| Marketplace (후속) | MarketplaceListing, Purchase, Refund, Payout, Dispute | 등록·구매·라이선스·환불·정산·분쟁 |

### 2.1 관계 개요

```text
Organization
 ├─ Membership ─ User [외부 인증/사용자 식별 경계]
 └─ Workspace
     ├─ Project ─ SKU
     │   └─ ProjectAssetRelation ─ Asset ─ AssetVersion
     │                                  ├─ AssetRelation (derived/reference)
     │                                  ├─ RightsDeclaration
     │                                  └─ ProvenanceRecord
     ├─ CharacterIdentityProfile ─ AssetVersion (reference images)
     ├─ BrandProfile ─ AssetVersion (brand assets)
     ├─ CreditAccount ─ CreditLedgerEntry ─ Quote
     ├─ GenerationJob ─ JobExecution ─ Provider/Model
     │       ├─ JobEvent
     │       └─ GenerationOutput ─ Asset/AssetVersion
     ├─ Review ─ Approval ─ ExportRecord
     └─ AuditEvent / DataRetentionRequest

MarketplaceListing ─ AssetVersion / License
Purchase ─ Entitlement ─ Refund / Payout / Dispute
```

> 위 그림은 논리 관계를 나타낸다. 실제 User/인증 테이블, 조직 간 공유, 다중 Workspace 자산 재사용, Marketplace 연결은 기존 구현·정책 검토 후 확정한다.

---

## 3. 공통 필드 규약

다음은 필드 설계의 공통 권고이며 실제 DB 타입은 저장소 감사 후 정한다.

| 필드 | 의미 | 규칙 |
|---|---|---|
| `id` | 내부 식별자 | 불투명한 고유 ID 권고. 외부 노출 시 순차 ID 노출 지양 |
| `organization_id` | 조직 테넌트 경계 | 조직 소유 리소스에 필수 여부를 일관되게 적용 |
| `workspace_id` | Workspace 경계 | Workspace 소유 리소스에 적용. 서버에서 멤버십 검증 |
| `created_at`, `updated_at` | 생성/수정 시각 | UTC 저장 권고. append-only 레코드의 과거 값 변경 금지 |
| `created_by`, `updated_by` | 행위 주체 | 사용자 또는 명시적 시스템 주체. nullable 허용은 시스템 생성 정책에 한함 |
| `status` | 현재 상태 | 허용 enum 및 전이표를 명시. 임의 문자열 금지 권고 |
| `metadata` | 확장 속성 | 검증된 스키마·크기 제한·민감정보 금지. 핵심 필드를 metadata에 숨기지 않음 |
| `version` / `revision` | 낙관적 동시성/설정 버전 | 필요한 엔터티에 적용. 파일 버전과 설정 revision 의미 구분 |
| `idempotency_key` | 중복 요청 방지 | 적용 범위·보존 기간·payload 충돌 규칙 정의 필요 |

**보안 규칙**: 클라이언트가 전달한 `organization_id`, `workspace_id`, `owner_id`는 권한 증거가 아니다. 서버가 인증 주체의 Membership과 리소스 관계를 통해 접근을 결정한다. Worker와 다운로드 URL 발급에도 같은 테넌트 정책을 적용한다.

---

## 4. 엔터티 사전

필수 필드는 논리적 최소 후보이며, 실제 필수 여부와 nullability는 구현 전 계약 리뷰에서 확정한다.

### 4.1 Organization

- **목적**: 고객 조직/테넌트의 최상위 경계.
- **주요 필드**: `id`, `name`, `slug`(고유성 정책 필요), `status`, `created_at`, `updated_at`.
- **관계**: Organization 1:N Membership, 1:N Workspace.
- **불변조건**: 조직 소유 데이터 접근은 해당 조직의 활성 Membership 및 역할을 확인한다.
- **상태 후보**: `ACTIVE`, `SUSPENDED`, `CLOSED` — 제안, 정책 승인 필요.
- **미결정**: 개인 계정의 기본 Organization 자동 생성 여부, 조직 병합/이전 정책.

### 4.2 Membership

- **목적**: 사용자와 Organization의 소속·역할·상태 연결.
- **주요 필드**: `id`, `organization_id`, `user_subject`(인증 공급자 사용자 식별자 참조), `role_id` 또는 역할 표현, `status`, `joined_at`, `created_at`, `updated_at`.
- **관계**: Membership N:1 Organization, 사용자 주체 N:M Organization.
- **불변조건**: 요청 주체의 활성 Membership을 확인하지 않고 조직 리소스에 접근시키지 않는다.
- **상태 후보**: `INVITED`, `ACTIVE`, `SUSPENDED`, `REMOVED`.
- **미결정**: 인증 공급자 및 User 테이블 소유 주체, 초대 만료·재초대·탈퇴 처리.

### 4.3 Role / Permission

- **목적**: 역할 기반 접근 제어(RBAC)의 권한 의미 정의.
- **주요 필드**: `id`, `organization_id`(조직별 사용자 정의 역할을 지원할 경우), `key`, `display_name`, `permission_set`, `is_system_role`.
- **관계**: Role 1:N Membership 또는 WorkspaceMembership/Grant(후보).
- **불변조건**: UI에서 숨기는 것만으로 권한을 통제하지 않는다. 모든 API와 Worker 작업에서 서버 측 검사.
- **미결정**: 조직 역할과 Workspace 역할의 계층/상속, 세분화 권한 목록, 소유자 보호 규칙.

### 4.4 Workspace

- **목적**: 실제 제작 업무와 자산·프로젝트·Job·크레딧 사용이 묶이는 작업 공간.
- **주요 필드**: `id`, `organization_id`, `name`, `status`, `created_at`, `updated_at`.
- **관계**: Workspace N:1 Organization; 1:N Project, Asset, GenerationJob, CreditAccount(계정 구조는 정책에 따라).
- **불변조건**: 모든 리소스 접근 시 Workspace와 상위 Organization의 관계를 검증.
- **상태 후보**: `ACTIVE`, `ARCHIVED`, `SUSPENDED`.
- **미결정**: Workspace별 멤버 권한 분리 여부, 개인 Workspace, 조직 내 기본 Workspace.

### 4.5 Project

- **목적**: 상품 콘텐츠·룩북·캠페인 등 사용자의 작업 단위.
- **주요 필드**: `id`, `workspace_id`, `name`, `project_type`, `status`, `description`(선택), `created_by`, timestamps.
- **관계**: Project N:1 Workspace; Project N:M Asset via ProjectAssetRelation; Project 1:N SKU(필요 시).
- **상태 후보**: `ACTIVE`, `ARCHIVED`, `COMPLETED`.
- **불변조건**: 프로젝트와 연결된 Asset이 다른 Workspace 소유라면 명시적 공유/권한 관계 없이는 연결 금지.
- **미결정**: 프로젝트 유형 목록, Project 삭제 시 Asset 처리, 프로젝트 간 자산 재사용.

### 4.6 SKU

- **목적**: 상품 단위 식별 및 패션/이커머스 콘텐츠와 결과 연결.
- **주요 필드**: `id`, `workspace_id`, `project_id`(선택 여부 결정 필요), `sku_code`, `title`, `brand_reference`, `attributes`, `status`.
- **관계**: SKU N:1 Workspace; Project 연결은 선택 또는 별도 관계로 표현 가능; SKU 1:N ProjectAssetRelation/AssetRelation 후보.
- **불변조건**: SKU 코드의 유일성 범위(Workspace/Brand/외부 PIM)는 정책으로 명시.
- **미결정**: PIM/ERP 연동, 변형상품/사이즈·컬러 모델, 초기 Gate에서 필요한 최소 필드.

### 4.7 ProjectAssetRelation

- **목적**: 프로젝트와 Asset의 역할·정렬·대표 여부를 연결.
- **주요 필드**: `id`, `project_id`, `asset_id`, `relation_type`, `sort_order`, `is_primary`, `created_at`.
- **관계**: Project N:M Asset.
- **규칙**: 같은 Project/Asset/관계 유형 중복 허용 여부를 정의. 참조만으로 소유권이 바뀌지 않는다.
- **미결정**: 별도 테이블 대신 기존 연결 구조가 있는지 G0에서 확인.

### 4.8 Asset

- **목적**: 이미지·영상·3D 모델·문서 등 논리적 파일 자산을 나타냄.
- **주요 필드**: `id`, `workspace_id`, `asset_type`, `name`, `current_version_id`(순환 참조/갱신 순서 검토), `status`, `created_by`, timestamps.
- **관계**: Asset 1:N AssetVersion; Asset N:M Asset via AssetRelation; Asset은 Project/SKU/Character Profile/Output 등과 연결될 수 있음.
- **소유권 제안**: Asset은 Workspace에 귀속되고 Project는 관계로 참조한다. Project 소유 모델을 채택할 경우 다중 프로젝트 재사용·권한 상속을 명시해야 한다.
- **상태 후보**: `PENDING_UPLOAD`, `ACTIVE`, `QUARANTINED`, `ARCHIVED`, `DELETION_PENDING`, `DELETED`.
- **불변조건**: 파일 본문은 객체 스토리지에, 메타데이터/권한/버전 참조는 DB에 저장하는 구조를 권고. 파일 교체는 기존 버전 덮어쓰기가 아닌 새 AssetVersion.
- **미결정**: 단일/다중 파일 자산, 폴더/컬렉션, 공개 URL 허용 여부, 보존·삭제 및 휴지통 정책.

### 4.9 AssetVersion

- **목적**: 특정 시점의 불변 파일/콘텐츠 버전.
- **주요 필드**: `id`, `asset_id`, `version_number` 또는 `revision`, `storage_key`, `mime_type`, `file_size_bytes`, `checksum`, `width`, `height`, `duration_ms`(미디어 해당 시), `metadata`, `created_by`, `created_at`.
- **관계**: AssetVersion N:1 Asset; 다른 버전과 AssetRelation/Provenance를 통해 파생·참조 연결.
- **불변조건**: 업로드/생성 파일의 저장·검증이 완료된 후 활성 버전으로 노출. 파일 내용 수정은 금지하고 새 버전을 만든다.
- **보안**: `storage_key`와 내부 버킷 경로는 일반 사용자 응답에 직접 노출하지 않는 것을 권고. 다운로드는 권한 확인 후 짧은 만료 URL 등으로 제공.
- **미결정**: 버전 번호 동시 발급, checksum 알고리즘, 바이러스/악성 파일 검사, 파생 미리보기 저장.

### 4.10 AssetRelation

- **목적**: Asset/AssetVersion 간 원본·파생·참조·대체·변환 관계 추적.
- **주요 필드**: `id`, `source_asset_version_id`, `target_asset_version_id`, `relation_type`, `created_at`, `created_by`.
- **관계 유형 후보**: `DERIVED_FROM`, `REFERENCES`, `VARIANT_OF`, `REPLACES`, `CONTAINS`.
- **불변조건**: 파생 관계는 원본 출처를 추적 가능해야 한다. 순환 관계 허용 여부를 제한하고 검증한다.
- **미결정**: Asset 단위 관계와 Version 단위 관계를 어떻게 병행할지 G0 및 API 계약 리뷰 필요.

### 4.11 CharacterIdentityProfile

- **목적**: 반복 생성에 사용하는 캐릭터 정체성의 구조화된 프로필.
- **주요 필드**: `id`, `workspace_id`, `name`, `profile_version`, `identity_attributes`, `reference_asset_version_ids`(정규화 관계 권고), `status`, timestamps.
- **속성 영역**: 얼굴형, 눈·눈썹·코·입, 피부톤, 헤어스타일·색·질감, 체형, 의상, 액세서리, 표정·포즈 등.
- **관계**: Workspace N:1; ProfileVersion/참조 AssetVersion과 연결. Job은 실행 시점의 프로필 버전 스냅샷을 참조.
- **불변조건**: Job 실행 이후 프로필이 변경되어도 과거 Job의 입력 정체성은 재현 가능해야 한다.
- **미결정**: 현재 문서의 단일 행 + revision 방식 또는 별도 ProfileVersion 엔터티 중 선택, 민감한 생체정보 취급과 보존 정책.

### 4.12 BrandProfile

- **목적**: 브랜드 톤, 시각 규칙, 로고·컬러·폰트 등 반복 적용할 브랜드 설정.
- **주요 필드**: `id`, `workspace_id`, `name`, `brand_rules`, `reference_asset_version_ids`(관계 테이블 권고), `version`, `status`, timestamps.
- **관계**: Workspace 1:N BrandProfile; Job/Project가 특정 버전을 참조.
- **불변조건**: 실행 시점에 적용한 브랜드 설정 버전을 보존.
- **미결정**: 브랜드 프로필의 조직 전체 공유와 Workspace별 권한, 브랜드별 다국어 표기.

### 4.13 Provider

- **목적**: 외부 AI 서비스 공급자 또는 내부 실행 공급자 식별.
- **주요 필드**: `id`, `key`, `display_name`, `provider_type`, `status`, `documentation_reference`(내부 참조), timestamps.
- **관계**: Provider 1:N Model; Provider 1:N Capability/Policy; JobExecution N:1 Provider.
- **보안**: API Key/Secret은 별도 Secret Manager/KMS에 보관. DB·일반 로그·클라이언트 응답에 평문 저장 금지.
- **미결정**: 실제 공급자 목록과 계정별 자격증명 구조.

### 4.14 Model

- **목적**: Provider가 제공하는 모델/엔드포인트/버전 식별.
- **주요 필드**: `id`, `provider_id`, `model_key`, `display_name`, `provider_version`, `status`, `capability_snapshot` 또는 Capability 연결.
- **관계**: Model N:1 Provider; JobExecution은 사용 모델과 버전 기록.
- **불변조건**: 실행 당시 모델 버전·요청 옵션·정책 버전을 추적할 수 있어야 한다.
- **미결정**: Provider 모델 버전이 고정/가변인 경우의 스냅샷 규칙.

### 4.15 Capability

- **목적**: 모델이 지원하는 작업 유형과 입력·출력 제약 정의.
- **주요 필드**: `id`, `provider_id`, `model_id`(적용 범위), `capability_key`, `input_schema_version`, `output_schema_version`, `constraints`, `status`.
- **예시**: image-based try-on, image editing, background replacement, upscaling, text-to-image 등 실제 지원 확인 후 등록.
- **불변조건**: UI/API는 Capability 검증 결과에 맞는 옵션만 노출.
- **미결정**: Capability 카탈로그와 schema registry의 실제 구현 방식.

### 4.16 Policy

- **목적**: Provider/Model 선택, 품질·비용·권리·지역·데이터 처리 제약을 관리.
- **주요 필드**: `id`, `policy_key`, `version`, `scope`, `rules`, `status`, `approved_by`, `approved_at`.
- **관계**: Provider/Model/Capability/Workspace/Job 유형 등에 적용 가능.
- **불변조건**: Hard filter(권리·지역·데이터·지원 기능 등)를 먼저 적용한 뒤 scoring. AUTO fallback은 승인된 정책에서만 허용하며 MANUAL 선택은 지정 Provider만 사용.
- **미결정**: 정책 우선순위·상속·긴급 비활성화 절차, 승인 권한.

### 4.17 Quote

- **목적**: Job 실행 전 예상 비용/크레딧을 산정한 불변 스냅샷.
- **주요 필드**: `id`, `workspace_id`, `requested_by`, `job_type`, `input_fingerprint`, `provider/model_candidate`, `estimated_cost`, `estimated_credits`, `currency`, `policy_version`, `expires_at`, `status`, `created_at`.
- **관계**: Quote 1:0..1 GenerationJob; Quote는 Credit 예약과 연결될 수 있음.
- **상태 후보**: `ACTIVE`, `EXPIRED`, `CONSUMED`, `CANCELLED`.
- **불변조건**: 생성 당시 산정 근거와 정책 버전을 보존. 만료/입력 변경 Quote 재사용 금지.
- **미결정**: 실제 원가/마진/환율/크레딧 환산 공식은 PO 승인 필요.

### 4.18 GenerationJob

- **목적**: 사용자가 제출한 하나의 논리적 AI 작업 요청.
- **주요 필드**: `id`, `workspace_id`, `project_id`(선택), `job_type`, `status`, `requested_by`, `quote_id`, `idempotency_scope`, `idempotency_key`, `input_snapshot`, `identity_profile_version_id`(해당 시), `brand_profile_version_id`(해당 시), `policy_version`, `created_at`, `updated_at`, `submitted_at`, `completed_at`.
- **관계**: Job 1:N JobExecution, 1:N JobEvent, 1:N GenerationOutput(복수 결과 가능); 0..1 Quote; CreditLedgerEntry와 연결.
- **기능 경계**: Try-on, Photo, 향후 기타 생성 기능은 기능별 입력 스키마를 가지되 공통 Job 수명주기를 공유. 3D Viewer의 로컬 조작은 반드시 GenerationJob일 필요 없음. 3D 렌더/생성 요청을 추가할 경우 별도 job_type으로 공통 오케스트레이터에 연결.
- **상태 후보**: `DRAFT`, `QUEUED`, `RUNNING`, `CANCEL_REQUESTED`, `SUCCEEDED`, `FAILED`, `CANCELLED`, `UNKNOWN`.
- **불변조건**: 생성 요청의 유효 입력·권한·Quote/크레딧을 검증하고 idempotency를 적용. `SUCCEEDED`는 결과 객체 및 DB 참조가 영속화된 후에만 허용.
- **미결정**: 입력 스냅샷의 저장 형식, 개인정보 최소화, Job 결과 개수/부분 성공 규칙.

### 4.19 JobExecution

- **목적**: Job에 대한 Provider 실행 시도 하나를 기록.
- **주요 필드**: `id`, `job_id`, `attempt_number`, `provider_id`, `model_id`, `provider_request_id`(가능한 경우), `status`, `started_at`, `finished_at`, `timeout_at`, `error_code`, `retryable`, `cost_actual`, `currency`, `request_fingerprint`, `response_metadata_redacted`.
- **관계**: JobExecution N:1 GenerationJob; N:1 Provider/Model; 결과 Output과 연결 가능.
- **상태 후보**: `CREATED`, `SUBMITTED`, `RUNNING`, `SUCCEEDED`, `FAILED`, `TIMED_OUT`, `CANCEL_REQUESTED`, `CANCELLED`, `UNKNOWN`.
- **불변조건**: 재시도마다 새 Execution을 만든다. 기존 시도 이력을 덮어쓰지 않는다. 공급자 원문 응답/비밀정보를 무제한 저장하지 않는다.
- **미결정**: Provider가 비동기 task ID를 제공하지 않는 경우 추적 키 및 timeout 복구 전략.

### 4.20 JobEvent

- **목적**: Job/Execution 상태 변화와 주요 실행 사실을 시간순 기록.
- **주요 필드**: `id`, `job_id`, `execution_id`(선택), `event_type`, `from_status`, `to_status`, `payload_redacted`, `occurred_at`, `recorded_at`, `source`, `deduplication_key`.
- **관계**: Job 1:N JobEvent; Execution 0..1:N JobEvent.
- **불변조건**: 이벤트는 추적/복구 목적에 맞게 append-only 권고. 중복 수신에 대비한 deduplication 필요. 이벤트 발생 시각과 수신/기록 시각을 구분.
- **미결정**: 이벤트 저장소/Outbox 패턴/보존기간 및 개인정보 필터.

### 4.21 GenerationOutput

- **목적**: Job이 생성한 결과물 및 그 결과의 자산 연결.
- **주요 필드**: `id`, `job_id`, `execution_id`, `asset_id`, `asset_version_id`, `output_type`, `sequence_no`, `status`, `metadata`, `created_at`.
- **관계**: Output N:1 Job, 선택적으로 Execution N:1; AssetVersion에 연결.
- **불변조건**: Output의 AssetVersion과 실제 저장 객체가 확인된 후 결과 완료로 처리. 결과가 여러 개면 sequence/역할로 구분.
- **미결정**: Output을 독립 엔터티로 유지할지 기존 결과 테이블을 확장할지 G0 감사 필요.

### 4.22 CreditAccount

- **목적**: Workspace 또는 정책상 청구 주체의 크레딧 잔액 원장 범위.
- **주요 필드**: `id`, `organization_id`, `workspace_id`(청구 단위 정책에 따라), `currency_or_credit_unit`, `status`, `created_at`.
- **관계**: CreditAccount 1:N CreditLedgerEntry.
- **불변조건**: 잔액은 원장 합계로 검증 가능해야 한다. 계정 소유/청구 범위는 명확히 하나로 정의.
- **미결정**: Organization 단위와 Workspace 단위 중 과금 주체, 공유 크레딧 풀, 음수 잔액/한도 정책.

### 4.23 CreditLedgerEntry

- **목적**: 크레딧 변동의 감사 가능한 원장 거래.
- **주요 필드**: `id`, `credit_account_id`, `job_id`(선택), `quote_id`(선택), `entry_type`, `amount`, `unit`, `idempotency_key`, `reverses_entry_id`(정정/상쇄 시), `reason_code`, `created_at`, `created_by`.
- **거래 유형**: `RESERVE`, `CAPTURE`, `RELEASE`, `REFUND`, `ADJUST`.
- **관계**: Account 1:N LedgerEntry; Job/Quote와 추적 연결.
- **불변조건**: append-only. 기존 행 수정·삭제 금지. 예약/확정/해제/환불의 상호 관계와 원자성 보장. 중복 webhook/worker 이벤트는 멱등 처리.
- **미결정**: 부호 규칙, 부분 capture, reserve 만료, 동시성 잠금/원자적 조건부 갱신 방식.

### 4.24 UsageRecord

- **목적**: Provider/기능 사용량과 실측 원가·시간을 기록.
- **주요 필드**: `id`, `job_id`, `execution_id`, `provider_id`, `model_id`, `metric_key`, `quantity`, `unit`, `actual_cost`, `currency`, `measured_at`, `source`.
- **관계**: Job/Execution N:1; Credit Ledger와 별도 보존.
- **불변조건**: 예상 비용 Quote와 실제 Usage를 구분. 실제 값이 없으면 추정치로 표시하고 실측처럼 취급하지 않는다.
- **미결정**: 공급자 청구서 대사, 환율 시점, 토큰/이미지/초당 비용 표준화.

### 4.25 Review

- **목적**: Output/Asset에 대한 품질 검수 요청 및 결과.
- **주요 필드**: `id`, `workspace_id`, `target_type`, `target_id`, `review_status`, `reviewer_id`, `checklist_snapshot`, `feedback`, `created_at`, `completed_at`.
- **관계**: Output/AssetVersion/Project와 연결 가능.
- **상태 후보**: `PENDING`, `IN_REVIEW`, `CHANGES_REQUESTED`, `PASSED`, `REJECTED`.
- **불변조건**: 검수 대상 버전이 바뀌면 기존 Review가 새 버전을 자동 승인하지 않는다.
- **미결정**: 검수 템플릿, 자동 품질 점수와 사람 승인 분리, 다단계 리뷰.

### 4.26 Approval

- **목적**: 게시/내보내기/고객 전달 등 공식 승인 결정 기록.
- **주요 필드**: `id`, `workspace_id`, `target_type`, `target_id`, `target_version_id`, `decision`, `approver_id`, `policy_snapshot`, `comment`, `decided_at`.
- **관계**: Review와 연결 가능하나 Review와 Approval은 동일 개념으로 합치지 않는다.
- **불변조건**: 승인된 버전과 실제 내보낸 버전이 일치해야 한다. 새 버전 생성 시 승인 유효성 재검토.
- **상태/결정 후보**: `APPROVED`, `REJECTED`, `REVOKED`.
- **미결정**: 고객 승인과 내부 승인 구분, 승인 만료/철회 정책.

### 4.27 ExportRecord

- **목적**: 승인된 결과의 내보내기/다운로드 패키지 이력.
- **주요 필드**: `id`, `workspace_id`, `project_id`, `target_version_ids`, `export_format`, `status`, `storage_reference`, `requested_by`, `created_at`, `completed_at`.
- **관계**: Project/Approval/AssetVersion과 연결.
- **불변조건**: 내보내기 시점의 파일 버전과 권리/승인 상태를 기록. 외부 링크는 권한·만료·재발급 정책 적용.
- **미결정**: zip/package 규칙, 대량 export 비동기 처리, 다운로드 로그 보존.

### 4.28 RightsDeclaration

- **목적**: 업로드/참조 자산 및 생성 입력에 대한 권리·동의·사용 제한 선언.
- **주요 필드**: `id`, `workspace_id`, `subject_type`, `subject_id`, `rights_type`, `declared_by`, `declaration_text_or_code`, `scope`, `territories`, `valid_from`, `valid_until`, `evidence_asset_version_id`(선택), `status`, timestamps.
- **관계**: Asset/AssetVersion/Character Profile/Marketplace Listing 등과 연결.
- **불변조건**: 권리 선언은 실제 법적 권리 보유를 자동 보증하지 않는다. 선언자·범위·근거·시점을 추적한다.
- **미결정**: 인물 초상권/모델 릴리스, 상표·저작권, 생성물 상업 이용 가능 범위 및 국가별 검토.

### 4.29 ProvenanceRecord

- **목적**: 생성/변환 결과가 어떤 입력·모델·설정에서 나왔는지 출처 연결.
- **주요 필드**: `id`, `output_id` 또는 `asset_version_id`, `source_asset_version_ids`, `job_id`, `execution_id`, `provider_id`, `model_id`, `model_version`, `prompt_or_config_reference`, `policy_version`, `created_at`.
- **관계**: Output/AssetVersion 1:N provenance records 가능.
- **불변조건**: 민감한 프롬프트·개인정보·공급자 비밀정보를 그대로 노출하지 않으며, 재현에 필요한 최소한의 허용된 메타데이터를 보존.
- **미결정**: 프롬프트 보존·암호화·삭제 예외, 공급자 약관상 기록 가능 범위.

### 4.30 License

- **목적**: Asset/Listing/구매 결과에 부여되는 사용허가 조건.
- **주요 필드**: `id`, `license_key`, `version`, `terms`, `territories`, `duration`, `usage_scope`, `commercial_use`, `derivative_allowed`, `attribution_required`, `status`.
- **관계**: Listing 1:N License 버전 또는 Purchase가 특정 License 버전을 참조.
- **불변조건**: 구매 시점의 라이선스 버전을 보존하고 사후 변경으로 기존 구매 조건을 소급 변경하지 않는다.
- **미결정**: 표준 라이선스 유형과 법무 검토, 국가별 약관.

### 4.31 Entitlement

- **목적**: 사용자/조직이 구매 또는 부여로 획득한 권한을 기록.
- **주요 필드**: `id`, `grantee_type`, `grantee_id`, `resource_type`, `resource_id`, `license_id`, `source_purchase_id`, `valid_from`, `valid_until`, `status`.
- **관계**: Purchase/License/Marketplace Asset과 연결.
- **불변조건**: 권한 확인은 다운로드·사용·파생 허용 등 실제 행위 시 서버에서 수행.
- **미결정**: 취소/환불 후 권한 회수, 팀원 공유, 라이선스 양도.

### 4.32 AuditEvent

- **목적**: 보안·권한·비용·관리 작업에 대한 감사 추적.
- **주요 필드**: `id`, `organization_id`, `workspace_id`(해당 시), `actor_type`, `actor_id`, `action`, `resource_type`, `resource_id`, `result`, `request_id`, `ip_or_client_context`(정책 허용 시), `occurred_at`, `payload_redacted`.
- **관계**: 모든 주요 엔터티에 논리적으로 연결.
- **불변조건**: 감사 로그는 append-only 권고. 비밀번호·토큰·비밀 키·민감한 원본 입력은 기록하지 않는다.
- **미결정**: 보존 기간, 관리자 열람 권한, 삭제/법적 보존 예외.

### 4.33 DataRetentionRequest

- **목적**: 보존·삭제·내보내기 요청과 처리 이력 관리.
- **주요 필드**: `id`, `organization_id`, `workspace_id`(선택), `request_type`, `subject_scope`, `requested_by`, `status`, `legal_hold`, `scheduled_at`, `completed_at`, `result_summary`.
- **관계**: Asset/AssetVersion/Job/Provenance/Rights/Audit 등 대상에 대한 처리 기록.
- **상태 후보**: `REQUESTED`, `UNDER_REVIEW`, `SCHEDULED`, `PROCESSING`, `COMPLETED`, `REJECTED`, `BLOCKED_BY_RETENTION`.
- **불변조건**: DB 레코드 삭제만으로 객체 스토리지·캐시·백업·Provider 보유 데이터가 삭제되었다고 간주하지 않는다. 실제 삭제 범위와 예외를 증거로 남긴다.
- **미결정**: 백업 만료, Provider 삭제 API, 법적 보존, 감사 로그 비식별화 정책.

### 4.34 MarketplaceListing (후속)

- **목적**: 판매/라이선스 가능한 AssetVersion을 마켓플레이스에 등록.
- **주요 필드**: `id`, `seller_organization_id`, `asset_version_id`, `title`, `description`, `category`, `price`, `currency`, `license_id`, `moderation_status`, `listing_status`, timestamps.
- **관계**: AssetVersion/RightsDeclaration/License와 연결; Purchase의 대상.
- **불변조건**: 유효 권리 선언·검수·라이선스가 없으면 공개 등록 불가.
- **미결정**: 마켓플레이스 수수료, 판매자 검증, 국가별 세금/결제/콘텐츠 정책.

### 4.35 Purchase / Refund / Payout / Dispute (후속)

- **Purchase 주요 필드**: `id`, `buyer_id`, `listing_id`, `license_version_id`, `amount`, `currency`, `payment_status`, `purchased_at`.
- **Refund 주요 필드**: `id`, `purchase_id`, `amount`, `reason`, `status`, `created_at`.
- **Payout 주요 필드**: `id`, `seller_id`, `period`, `gross_amount`, `fee_amount`, `net_amount`, `currency`, `status`.
- **Dispute 주요 필드**: `id`, `purchase_id` 또는 `listing_id`, `opened_by`, `reason`, `evidence_refs`, `status`, timestamps.
- **관계**: Purchase → Entitlement; Purchase → Refund; Seller → Payout; Purchase/Listing → Dispute.
- **경계**: Marketplace는 후속 제품 범위이며 초기 파일럿의 완료 조건으로 간주하지 않는다.
- **미결정**: PG/환불/정산 파트너, 세금·KYC·분쟁 정책과 법무 검토.

---

## 5. 핵심 관계 카디널리티 요약

| 부모 | 자식/연결 | 카디널리티(논리) | 핵심 제약 |
|---|---|---:|---|
| Organization | Membership | 1:N | 활성 멤버십 확인 |
| Organization | Workspace | 1:N | Workspace는 조직에 귀속 |
| Workspace | Project | 1:N | Project 접근은 Workspace 권한 필요 |
| Workspace | Asset | 1:N 제안 | 소유권 모델 ADR 필요 |
| Project | Asset | N:M | ProjectAssetRelation로 연결 제안 |
| Asset | AssetVersion | 1:N | 버전 파일 불변 |
| AssetVersion | AssetVersion | N:M | AssetRelation으로 출처/파생 추적 |
| Workspace | CharacterIdentityProfile / BrandProfile | 1:N | 실행 시점 버전 고정 |
| Provider | Model | 1:N | 실행 당시 모델 버전 기록 |
| Model | Capability | 1:N 또는 N:M | 실제 카탈로그 구조 결정 필요 |
| GenerationJob | JobExecution | 1:N | 각 재시도는 새 Execution |
| GenerationJob | JobEvent | 1:N | 이벤트 이력 추적 |
| GenerationJob | GenerationOutput | 1:N | 결과 저장 후 성공 처리 |
| CreditAccount | CreditLedgerEntry | 1:N | 원장 append-only |
| GenerationJob | Quote | 0..1:1 제안 | Quote 만료·입력 fingerprint 검증 |
| GenerationJob | UsageRecord | 1:N | 예상치와 실측치 분리 |
| AssetVersion / Output | Rights / Provenance | 1:N 가능 | 범위·출처·시점 기록 |
| Output / AssetVersion | Review / Approval | 1:N 가능 | 버전별 검수·승인 |
| Listing | Purchase | 1:N 후속 | 구매 시 라이선스 버전 고정 |
| Purchase | Entitlement | 1:N 또는 1:1 정책 | 환불 후 권한 회수 정책 필요 |

---

## 6. 상태 전이와 불변조건

### 6.1 GenerationJob 상태 전이 제안

```text
DRAFT → QUEUED → RUNNING → SUCCEEDED
                    ├──→ FAILED
                    ├──→ UNKNOWN
                    └──→ CANCEL_REQUESTED → CANCELLED
                                      └────→ RUNNING (취소 미지원/거절 시 정책에 따라)
```

- `UNKNOWN`은 Provider timeout/응답 유실 등으로 결과를 확정할 수 없는 상태다. 즉시 실패 처리하거나 무조건 재실행하지 않는다.
- 재시도는 기존 Job 아래 새 JobExecution으로 기록하고, 정책에 따라 Job 상태를 다시 `QUEUED` 또는 `RUNNING`으로 전환한다.
- `SUCCEEDED` 조건: 결과 객체 저장, checksum/메타데이터 검증, AssetVersion 생성, GenerationOutput 연결, DB 트랜잭션 완료.
- `CANCELLED`는 사용자 요청만으로 확정하지 않는다. Provider 취소 확인 또는 실행 종료를 확인한다. Provider 취소 미지원 시 결과 처리/과금 정책을 별도 적용한다.

### 6.2 JobExecution 상태 전이 제안

```text
CREATED → SUBMITTED → RUNNING → SUCCEEDED
                         ├──→ FAILED
                         ├──→ TIMED_OUT → UNKNOWN (결과 확인 중)
                         └──→ CANCEL_REQUESTED → CANCELLED
```

Provider의 실제 비동기/동기 동작에 맞춰 세부 전이를 조정한다. 공급자 상태와 내부 상태의 매핑표를 Provider Adapter별로 유지한다.

### 6.3 Credit Ledger 순서 제안

```text
Quote 생성 → RESERVE → [Provider 실행]
                         ├─ 성공/실제 사용량 확정 → CAPTURE
                         ├─ 실행 전 취소/미사용 → RELEASE
                         ├─ 사후 환불 승인 → REFUND
                         └─ 불일치/정정 → ADJUST
```

- 예약·확정·해제·환불은 별도 원장 행으로 기록한다.
- 동시 요청 시 잔액 확인과 RESERVE 생성은 원자적으로 처리한다.
- 중복 webhook/worker 메시지는 동일 멱등성 키로 중복 거래가 발생하지 않게 한다.
- Provider 결과 불명 상태에서는 비용 확정/예약 해제 기준을 정책화하고 사후 대사 가능하게 한다.
- 부호 규칙 및 부분 확정/부분 반환은 구현 전 결정한다.

### 6.4 Asset/Version 상태 원칙

- 업로드 시작 → 임시 저장 → 서버 검증 → `ACTIVE` 버전 공개.
- 파일 시그니처/디코딩/크기/권리 검사 실패 시 `QUARANTINED` 또는 명시적 거절.
- 새 편집/생성 결과는 새 AssetVersion 또는 파생 Asset으로 저장.
- 삭제 요청은 즉시 물리 삭제로 취급하지 않고 보존/법적 보류/스토리지·백업·Provider 삭제 범위를 추적.

---

## 7. 기능별 입력 스키마와 공통 Job 경계

| 기능 | 기능별 입력(예시 범주) | 공통 코어 사용 |
|---|---|---|
| Image-based Try-on | 의류 이미지 AssetVersion, 인물/모델 참조, 포즈/프레이밍, Provider 지원 옵션 | Quote, GenerationJob, JobExecution, Event, Output, Credit, Rights |
| Photo Engine | 원본 이미지, 편집 작업 유형, 마스크/참조 이미지, 출력 규격, 품질 옵션 | 동일 공통 Job 코어. 독립 2D 처리 파이프라인 |
| Character generation/update | Identity Profile 버전, 참조 이미지, 캐릭터 특성·스타일 | 동일 Job 코어 사용 여부는 생성 방식에 따라 결정. Profile 버전 보존 |
| 3D Viewer | GLB/glTF AssetVersion, 씬/카메라/조명/재질 설정 | Viewer 상태 저장은 일반 Scene/Asset 데이터. 서버 AI 생성 작업은 필요 시 공통 Job 사용 |
| 3D Garment Simulation | 패턴/의상 메시/바디/물리 파라미터 | 별도 R&D/검증 경계. 기존 Viewer 기능으로 간주하지 않음 |
| Video Pipeline | 영상 입력/프레임·시간 설정/일관성 제약 | 후속 별도 시간축 파이프라인. 공통 Project/Asset/Rights는 재사용 검토 |

기능별 payload는 버전이 있는 schema로 검증한다. 공통 GenerationJob에는 공통 필드와 입력 스키마 참조/스냅샷을 두고, 기능별 필드를 단일 범용 JSON에 무제한 혼합하지 않는다.

---

## 8. API 계약·요구사항·QA 연결

### 8.1 API 계약 등록부와의 연결

| 결정 ID | 이 문서의 관련 엔터티 | 현재 상태/주의 |
|---|---|---|
| ADR-API-001 | 모든 API 리소스 | `/v1` vs `/api/v1`; G0 전 확정 금지 |
| ADR-TEN-001 | Organization, Membership, Workspace, Role | 기존 모델·마이그레이션·권한 확인 필요 |
| ADR-AST-001 | Project, Asset, AssetVersion, AssetRelation | Workspace 소유권/공유/파생 관계 제안 |
| ADR-JOB-001~003 | GenerationJob, JobExecution, JobEvent, GenerationOutput | 상태·재시도·취소·결과 불명 검토 |
| ADR-CR-001 | CreditAccount, CreditLedgerEntry, Quote, UsageRecord | 원자성·멱등성·append-only 검증 |
| ADR-PRV-001~002 | Provider, Model, Capability, Policy | Adapter 및 MANUAL/AUTO 정책 승인 |
| ADR-OUT-001 | GenerationOutput, AssetVersion, ProvenanceRecord | 결과 저장과 버전 연결 |
| ADR-SEC-001 / ADR-UPL-001 | Tenant 엔터티, Asset, AssetVersion | 테넌트 검사 및 업로드 검증 |
| ADR-PH-001 | GenerationJob, JobExecution, GenerationOutput | Photo Engine은 독립 2D 파이프라인 |
| ADR-3D-001 | Asset, AssetVersion 및 Scene 설정 | Viewer와 Garment Simulation 구분 |

### 8.2 원본 통합 QA T-01~T-14 보존

| QA ID | 관련 엔터티 | 검증 핵심 |
|---|---|---|
| T-01 | Organization, Membership, Workspace, Role | 로그인 후 조직/Workspace 접근 |
| T-02 | Asset, AssetVersion | 유효 이미지 업로드 및 완료 |
| T-03 | Asset, AssetVersion | MIME/시그니처/크기 위장 파일 거부 |
| T-04 | Tenant 엔터티 전반 | 타 조직 리소스 접근 차단 |
| T-05 | Quote, CreditAccount, CreditLedgerEntry, GenerationJob | 견적 후 Job 생성 및 예약 |
| T-06 | CreditAccount, CreditLedgerEntry | 크레딧 부족 시 Job 생성 차단 |
| T-07 | Provider, Model, JobExecution, GenerationOutput, AssetVersion | 실제 Provider 성공과 결과 영속화 |
| T-08 | GenerationJob, CreditLedgerEntry | 동일 멱등성 키 반복 요청 |
| T-09 | JobExecution, JobEvent, UsageRecord | Provider timeout/결과 불명 및 중복 실행 방지 |
| T-10 | GenerationJob, JobExecution, JobEvent | 실행 중 취소 요청과 실제 취소 구분 |
| T-11 | AssetVersion, GenerationOutput, ProvenanceRecord | 원본과 생성 결과 비교/추적 |
| T-12 | GenerationJob, JobExecution, JobEvent, Policy | 실패·재시도·fallback 이력 |
| T-13 | GenerationJob, JobEvent, Outbox(구현 선택) | Queue 발행 전 DB 커밋 후 장애 복구 |
| T-14 | JobExecution, GenerationOutput, AssetVersion | Provider 성공 후 결과 저장 장애 복구 |

기존 ID와 의미를 유지한다. 새 QA ID가 추가되어도 T-01~T-14를 대체하지 않는다.

---

## 9. 인덱스·제약·트랜잭션 설계 체크리스트

실제 DB 엔진과 스키마 확인 후 개발자가 결정한다. 아래는 검토해야 할 항목이지 확정 DDL이 아니다.

- Tenant: 주요 조회 테이블에 `organization_id`/`workspace_id` 인덱스 및 서버 측 필터 적용.
- Membership: 사용자 주체 + Organization 조합의 중복 소속 방지 제약 검토.
- ProjectAssetRelation: Project/Asset/관계 유형 중복 제약 검토.
- AssetVersion: Asset별 version_number 유일성 및 동시 발급 보호.
- AssetRelation: 자기 자신 연결 및 순환 관계 제한 검토.
- GenerationJob: idempotency scope/key 유일성, 상태/생성 시각 조회 인덱스.
- JobExecution: Job별 attempt_number 유일성.
- JobEvent: deduplication_key 중복 방지 및 Job 시간순 조회 인덱스.
- GenerationOutput: Job/sequence_no 중복 정책과 AssetVersion 참조 무결성.
- CreditLedgerEntry: 멱등성 키 범위 유일성, 원장 거래와 예약/확정 참조 무결성.
- Quote: 만료 조회 및 입력 fingerprint 검증.
- Rights/License: 유효기간·상태·대상 리소스 조회 인덱스.
- AuditEvent: 조직/Workspace/행위자/시각 조회와 보존 정책.

### 9.1 트랜잭션 경계 후보

1. **Job 접수**: 권한 검증 → Quote 유효성 → Credit RESERVE → Job 생성 → Outbox/Queue 이벤트 기록. 원자성 범위를 개발자가 정의.
2. **Worker 실행 시작**: Job/Execution 상태 변경과 실행 이벤트 기록을 원자적으로 유지.
3. **Provider 결과 처리**: 응답 수신 → 결과 객체 저장 → checksum 검증 → AssetVersion/Output 생성 → Job 성공 상태 확정. 외부 스토리지 작업과 DB 트랜잭션의 보상/재처리 전략 필요.
4. **Credit 정산**: 실제 Usage/결과 상태를 근거로 CAPTURE 또는 RELEASE. Provider 결과 불명은 별도 조정 절차.
5. **취소**: 요청 기록 → Provider 취소 시도 → 실제 종료 확인 → 비용/크레딧 정산. 취소 요청과 취소 완료를 같은 이벤트로 처리하지 않음.

---

## 10. 개인정보·권리·보존 및 운영 통제

- 최소 수집: 작업 실행·재현·감사에 필요한 데이터만 보존하고 불필요한 원본 입력/프롬프트는 저장하지 않는다.
- 접근 통제: 조직/Workspace 권한은 API·Worker·관리자 도구·다운로드 경로 모두 동일하게 적용.
- 비밀정보: Provider credential은 Secret Manager/KMS 경계에 둔다. 로그는 redaction 적용.
- 이미지/인물 권리: 인물 참조 이미지, 모델 사진, 상표·로고, 의류 디자인의 사용 권리와 동의 범위를 기록한다. RightsDeclaration은 법률 자문이나 실제 권리 보증을 대체하지 않는다.
- Provider 정책: 데이터 지역, 보존 기간, 모델 학습 사용, 재위탁, 삭제 요청, 상업 이용 조건을 Provider별로 검토한다.
- 삭제: 원본 객체, 파생 버전, 미리보기, CDN 캐시, 백업, Provider 측 사본을 각각 추적한다. 완료 전 삭제 완료로 표시하지 않는다.
- Audit: 권한 변경, 크레딧 거래, Provider 실행, 승인, 내보내기, 삭제 요청을 기록하되 민감정보는 제외.

---

## 11. 미결정 사항 및 결정 책임

| ID | 미결정 사항 | 결정 책임 | 필요한 증거/선행 조건 | 현재 상태 |
|---|---|---|---|---|
| DM-001 | 실제 DB 엔진·테이블·ORM·마이그레이션 경로 | 개발자 | Termux G0 저장소 감사 | NEEDS_REPO_AUDIT |
| DM-002 | API prefix `/v1` vs `/api/v1` | 개발자 + PO | 기존 라우터/클라이언트/프록시 비교, ADR-API-001 | NEEDS_REPO_AUDIT |
| DM-003 | User/인증 주체 및 Membership 연결 | 개발자 | 인증 코드/DB 확인 | NEEDS_REPO_AUDIT |
| DM-004 | Workspace 멤버 권한 및 Role 상속 | 개발자 + PO | 현재 RBAC와 제품 정책 | NEEDS_REPO_AUDIT / NEEDS_PO_APPROVAL |
| DM-005 | Asset 소유권(Workspace vs Project), 공유·파생 모델 | 개발자 + PO | 기존 Asset 구현, 사용 시나리오 | NEEDS_REPO_AUDIT |
| DM-006 | AssetVersion 번호/스토리지/checksum/삭제 | 개발자 | 저장소·스토리지 코드와 운영 정책 | NEEDS_REPO_AUDIT |
| DM-007 | Character/Brand Profile version snapshot 방식 | 개발자 + PO | 기존 프로필 스키마와 재현성 요구 | PROPOSED |
| DM-008 | Job 상태 enum, Outbox/Queue 및 복구 방식 | 개발자 | 기존 Worker/Queue 및 장애 테스트 | NEEDS_REPO_AUDIT |
| DM-009 | Provider timeout/취소/결과 불명 처리 | 개발자 | 실제 Provider별 문서·호출 테스트 | NEEDS_PROVIDER_CHECK |
| DM-010 | CreditAccount 과금 단위와 잔액 정책 | PO + 개발자 | 상품/가격/원가 정책 및 동시성 설계 | NEEDS_PO_APPROVAL |
| DM-011 | Credit 부호/부분 capture/refund/reserve 만료 | 개발자 + PO | 원장 시나리오·QA | PROPOSED |
| DM-012 | Rights/Provenance 보존·삭제·법적 근거 | PO + 법무 검토 + 개발자 | 대상 국가/Provider 약관/운영 정책 | NEEDS_PO_APPROVAL |
| DM-013 | Marketplace Listing/Purchase/Entitlement 구조 | PO + 개발자 | Marketplace Gate 및 법무/결제 검토 | FUTURE / NOT IN INITIAL GATES |
| DM-014 | 실제 API 경로와 OpenAPI schema | 개발자 | G0 및 ADR 승인 | NEEDS_REPO_AUDIT |

---

## 12. Gate별 데이터 모델 수용 기준

| Gate | 데이터 모델 검증 범위 | 통과 증거 |
|---|---|---|
| G0 | 기존 테이블/ORM/API/스토리지/Job/크레딧/3D 자산 구조와 본 논리 모델 비교 | 저장소 경로·브랜치·커밋, 모델/마이그레이션 목록, 실행·테스트 로그, 재사용/변경/폐기 판정표 |
| G1 | Asset/AssetVersion 및 Scene 설정이 GLB/glTF와 참조 버전을 안정적으로 저장·복원 | GLB 3종 이상 로드, 카메라/회전/줌, 씬 저장·복원 테스트와 로그. 의상 물리 시뮬레이션은 제외 |
| G2 | Quote/Job/Execution/Provider/Output/Usage/Rights 연결 | 실제 Provider 호출 요청·응답(비밀정보 제거), 결과 파일, 실행시간·원가, 권리/약관 검토 증거 |
| G3 | Organization/Membership/Workspace부터 Asset·Credit·Job·Output·Review까지 통합 | T-01~T-14 및 추가 QA 결과, 테넌트/멱등성/장애복구/원장 일관성 증거 |
| G4 | Photo Job 입력·Execution·Output·AssetVersion·Provenance | 독립 2D 파이프라인 실행, 전후 품질 평가, 비용·시간·오류 및 저장 증거 |
| G5 | 고객 Workspace·권한·권리·승인·Export·사용량·지원 데이터 | 유료 파일럿 계약/동의/권리 확인, 고객 승인 흐름, 실제 원가·품질·운영 데이터 및 국가별 준비 증거 |

Gate 통과는 문서 작성만으로 선언하지 않는다. 해당 Gate의 실제 실행 증거와 승인 기록이 필요하다.

---

## 13. Owner / Approver / 산출물

| 작업 | Owner | Contributors | Approver | 산출물/합격 기준 |
|---|---|---|---|---|
| 기존 스키마 및 마이그레이션 감사 | 실제 개발자/Tech Lead | ChatGPT(분석·추적) | PO | G0 모델 비교표와 재사용 판정 |
| 논리 모델의 물리 DB 매핑 | 개발자 | ChatGPT(리뷰) | PO + 개발자 기술 승인 | ERD, DDL/ORM, migration, 인덱스/제약 명세 |
| API 계약/OpenAPI 반영 | 개발자 | ChatGPT(BA/QA) | PO | 승인된 API 계약, 기존 T-01~T-14 매핑 |
| 권리·보존 정책 | PO | 개발자, 필요 시 법무 | PO | Rights/Retention 정책과 국가·Provider별 근거 |
| 비용·크레딧 정책 | PO | 개발자 | PO | 가격/원가 가정, 원장 시나리오, 정산 승인 |
| Gate 검증 | 개발자 | ChatGPT(QA) | PO | 재현 가능한 테스트 로그/결과물/승인 기록 |

---

## 14. 변경 관리

1. 이 문서의 제안 필드·관계·상태를 구현 기준으로 바꾸려면 Change Request를 생성한다.
2. 개발자는 저장소 영향, 데이터 마이그레이션, API 호환성, 성능·보안·일정을 분석한다.
3. ChatGPT는 제품 요구사항·UX·QA·상위 문서 정합성을 검토한다.
4. PO가 제품 의미·권리·비용·우선순위를 승인한다. 기술 구현 방식은 개발자가 책임지고 설명한다.
5. 승인 후 본 문서, API 계약 등록부, 요구사항 추적 매트릭스, OpenAPI/DB migration, QA를 같은 변경 버전으로 갱신한다.
6. 이전 버전은 삭제하지 않고 `SUPERSEDED`로 남긴다.

### 14.1 변경 이력

| 버전 | 날짜 | 변경 |
|---|---|---|
| v0.1 | 2026-11-02 | 공통 도메인 엔터티, 관계, 핵심 필드, 상태 전이, 보안·권리·크레딧 불변조건, Gate 검증 연결 초안 작성 |

---

## 15. 다음 실행 순서

1. 사용자가 별도로 진행하기로 한 Termux G0 저장소 감사를 수행한다. 이 문서 작성 단계에서는 로컬 저장소 변경이나 명령 실행을 요청하지 않는다.
2. 실제 ORM/DB/API/Worker/Storage 구조를 이 논리 모델에 매핑하고 기존 구현을 재사용·수정·폐기 후보로 분류한다.
3. ADR-API-001 및 DM-001~DM-006을 실제 코드 증거로 우선 결정한다.
4. Job/Execution/Event/Output 및 Credit Ledger의 트랜잭션·복구 경계를 개발자와 확정한다.
5. 승인된 계약을 OpenAPI/ERD/migration/QA에 동기화하고 G0 이후 Gate 순서에 따라 검증한다.

**현재 결론**: 본 문서는 공통 데이터 모델의 논리 초안이다. 실제 DB 설계 확정, 코드 반영, 마이그레이션, QA 실행 또는 Gate 통과를 의미하지 않는다.
