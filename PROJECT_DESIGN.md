# AI CREATOR STUDIO — 통합 제품·시스템 설계 기준(인수인계용)

- 설계 참조: `docs/project-design/imported-reference/AI_CREATOR_STUDIO_integrated_execution_baseline_v0_2.md`
- 글로벌 마스터 계획: `docs/project-design/imported-reference/AI_CREATOR_STUDIO_global_integrated_master_plan_v0_1.md`
- 모듈별 실제 상태: `PROJECT_STATUS_AND_HANDOFF_BUILD-00156.md`
- 주의: 아래는 기존 설계의 통합 안내서이며, 제품 책임자 승인 및 개발자 기술 검토가 완료된 최종 아키텍처라고 간주하지 않습니다.

## 제품 축
- Studio: Photo Edit, Character Studio, 3D Studio, Virtual Try-on, Photo Engine, Lookbook/Campaign, Video(후속).
- Business: Organization, Workspace, Project, SKU, Asset/Version, Brand Kit, Batch Workflow, Review/Approval, Export.
- Marketplace: Listing, Purchase, License Grant, Refund, Dispute, Payout, Tax/Settlement.

## 논리 아키텍처
```text
AI CREATOR STUDIO
├── Public Website / Trust / Marketing
├── Accounts / Organization / Workspace / RBAC
├── Project / SKU / Asset / AssetVersion / Rights
├── Character Studio / Identity Profile
├── 3D Studio / Scene Editor
├── Image-based Try-on / Provider Adapters
├── Photo Engine
├── Lookbook / Campaign / Workflow
├── Review / Approval / Export
├── Engine Registry / Capability / Policy / Cost
├── Credit Ledger / Billing / Audit
├── Video Pipeline (later)
└── Marketplace (rights + commerce readiness required)
```

## 책임 경계
- Character Studio: 재사용 가능한 인물 외형 프로필 및 버전.
- 3D Viewer/Scene Editor: GLB/glTF 씬 로드, 카메라, 조명, 재질, 변환, 씬 상태 저장/복원.
- 3D Garment Simulation: 패턴, 메시, 리깅, 충돌, 천 물리. Viewer와 별도 R&D.
- Image-based Try-on: 인물/의류 이미지 입력으로 결과 이미지 생성.
- Photo Engine: 2D 사진 보정/후처리. Viewer 캡처와 별도.
- Video Pipeline: 프레임·모션·시간 일관성.
- Marketplace: 권리·라이선스·거래·환불·분쟁·정산이 필요한 별도 시스템.

## 권장 초기 기술 방향(실제 저장소 확인 우선)
- Frontend: React / TypeScript.
- API: Python / FastAPI / Pydantic.
- DB: PostgreSQL 목표, 현재 SQLite PoC 범위와 구분.
- Async: Queue + Worker; Outbox 또는 동등한 복구 패턴.
- File: S3-compatible Object Storage + CDN 목표.
- Auth: 검증된 OIDC/managed auth 또는 동등한 보안 경계.
- Secrets: Secret Manager/KMS.
- Observability: structured logs, metrics, traces.
- 3D: Three.js / GLTFLoader / OrbitControls.

## 주요 도메인 모델(설계 범위)
- Tenant & Access: Organization, Membership, Workspace, Role, Permission, Policy.
- Work & Assets: Project, SKU, Asset, AssetVersion, AssetRelation, RightsDeclaration, Provenance, License, BrandProfile.
- Identity & 3D: Character, CharacterIdentityProfile, IdentityProfileVersion, CharacterReferenceAsset, Scene3D, SceneVersion.
- AI execution: Provider, ProviderModel, CapabilityEvidence, ProviderPolicy, CostQuote, GenerationJob, JobExecution, JobEvent, GenerationResult, OutboxEvent.
- Commercial & governance: CreditAccount, append-only CreditLedger, UsageRecord, Review, Approval, AuditEvent, RetentionPolicy, DeletionRequest.
- Marketplace later: Listing, Purchase, LicenseGrant, Refund, Dispute, Payout, Tax/SettlementRecord.

## 핵심 실행 흐름
`Customer Asset → Work Definition → Rights/Policy → Capability Check → Cost Quote → Credit Reserve → Async Job/Execution → Provider → Persist Output → Quality Review → Approval → Version/SKU Link → Export`

이 흐름 전체는 제품 목표이며 현재 소스에서 완전히 수직 통합되었다는 의미가 아닙니다. 현재 구현과 미검증 경계는 `PROJECT_STATUS_AND_HANDOFF_BUILD-00156.md`에서 확인하십시오.
