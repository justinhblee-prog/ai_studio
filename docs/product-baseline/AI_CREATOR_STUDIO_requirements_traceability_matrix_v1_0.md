# AI CREATOR STUDIO — 통합 요구사항 추적 매트릭스 v1.0

- 기준일: 2026-11-02
- 상태: 문서 기준선 / 실제 구현 검증 전
- 상위 기준: 통합 실행 기준서 v0.2, G0~G5 검증 계획 v0.1, 개발자 착수명세서 v0.1 원본 및 v0.2 제안본, 기술 아키텍처 구현 v0.2, 글로벌 통합 전략 문서
- 목적: 제품 요구사항에서 모듈, API·데이터 계약, QA, Gate, 책임자 및 증거까지 양방향 추적
- 주의: 이 문서는 개발·테스트 수행 증거가 아니다. 저장소/API/DB 실제 경로가 확인되지 않은 항목은 `TBD — repository audit required`로 둔다.

## 1. 상태·책임 표기 규칙

| 표기 | 의미 |
|---|---|
| Confirmed direction | 사용자 지시 또는 현행 기준 문서에서 방향이 확인됨 |
| Proposed | 설계 권고 또는 승인 전 제안 |
| TBD | 저장소 감사·개발자 확인·PO 결정 필요 |
| Evidence pending | 요구사항/테스트는 정의됐으나 실행 증거 미확인 |
| Not started / Not verified | 실제 구현·검증 상태를 확인하지 못함 |

- Owner 기본값은 `개발자/Tech Lead(실행 책임, 지정자 확인 필요)`이며, 제품 정책·우선순위·가격·출시 결정은 `PO` 승인 대상이다.
- ChatGPT 역할은 요구사항·QA·문서 추적 및 산출물 검토이며, 실제 코드 실행·개발자 전달·배포 책임자가 아니다.
- 모든 Evidence 필드는 증거 링크/커밋/실행 로그가 제공되기 전까지 `미제출`이다.
- API 이름은 논리적 계약 이름이며 실제 route가 확인된 것으로 간주하지 않는다.

## 2. 요구사항 추적 매트릭스

| Req ID | 영역 / 우선순위 | 요구사항 및 근거 수준 | 기술 모듈 | API / 데이터 엔터티 (논리 수준) | QA 연결 | Gate | Owner / Approver | Acceptance Criteria | Evidence | Status / Dependency |
|---|---|---|---|---|---|---|---|---|---|---|
| STR-001 | 전략 / P0 | 글로벌 우선 제품·브랜드·데이터·권리·현지화·결제 설계 (Confirmed direction) | Product Strategy / Platform Core | Organization, Workspace, Rights, Billing, Locale | QA-G5-STR-01(신규) | G5 | PO / PO | 국가별 출시 가능 여부를 별도 체크리스트로 판단하며 단일 국가 전용 구조를 강제하지 않음 | 미제출 | 기준 방향 확정; 국가별 실무 검증 TBD |
| STR-002 | 수익화 / P0 | 초기 유료 진입은 B2B 패션·이커머스 룩북/상품 콘텐츠 파일럿 (Confirmed direction) | Business Workflow / Lookbook | Project, SKU, Asset, Quote, UsageRecord | QA-G5-PILOT-01(신규) | G5 | PO / PO | 파일럿 범위·산출물·권리·가격·지원 조건이 계약서에 명시 | 미제출 | 전략 방향; 고객 계약 증거 대기 |
| STR-003 | 마케팅 / P1 | 홈페이지 상위 진입은 asset-first 업무: 사진 편집, 상품 이미지, AI 모델/가상착장, 룩북/캠페인 (Confirmed direction) | Public Website / Product IA | 해당 없음; 웹 구현 별도 승인 | QA-WEB-IA-01(신규, 미실행) | 별도 승인 | PO / PO | 고객이 캐릭터 선행 생성 없이 대표 업무로 진입 가능 | 미제출 | 웹 구현은 별도 지시 전 범위 제외 |
| PRD-001 | 공통 코어 / P0 | Organization/Membership/Workspace 구조와 역할 기반 접근 유지 (Confirmed direction) | Identity & Tenant | Organization, Membership, Workspace, Role; API 경로 TBD | T-01, T-04; QA-TEN-01~03 | G0, G3 | 개발자 / PO | 멤버십·역할에 따라 허용/거절되고 타 조직 데이터가 노출되지 않음 | 저장소·테스트 로그 미제출 | Evidence pending; G0 선행 |
| PRD-002 | 공통 코어 / P0 | Project 단위 작업·SKU·Asset 관리 (Confirmed direction) | Project / Asset Service | Project, SKU, Asset, AssetVersion, AssetRelation | T-02, T-11; QA-AST-01~06 | G0, G3 | 개발자 / PO | 업로드 자산과 파생 결과가 버전·관계·소유권을 보존 | 미제출 | 실제 스키마 TBD |
| PRD-003 | Asset / P0 | Asset 소유권, 공유, 파생 관계, 버전 관리 (Proposed baseline) | Asset Service / Storage | Asset, AssetVersion, AssetRelation, RightsDeclaration | T-02, T-11; QA-AST-04~06 | G0, G3 | 개발자 / PO | 원본 불변, 파생본 별도 버전, 접근 정책 및 메타데이터 조회 가능 | 미제출 | 데이터 계약 확인 필요 |
| PRD-004 | 업로드 / P0 | 파일 MIME·시그니처·크기 검증 및 비공개 저장 (원본 기준) | Upload / Storage | Asset, AssetVersion, Upload session (실제명 TBD) | T-02, T-03; QA-AST-01~03 | G0, G3 | 개발자 / PO | 유효 파일만 READY, 부적합 파일 거절, 공개 노출 없음 | 미제출 | 저장소·스토리지 설정 증거 대기 |
| PRD-005 | Character / P1 | Character Identity Profile을 구조화하고 버전·참조 자산과 연결 (Confirmed product direction) | Character Studio | CharacterIdentityProfile, AssetVersion, Project | QA-CHAR-01~06(신규) | G3 이후 | 개발자 / PO | 얼굴·체형·헤어·피부·의상·포즈 등 프로필과 변경 이력 연결 | 미제출 | 구현 여부 TBD; MVP 범위 승인 필요 |
| PRD-006 | 3D Viewer / P1 | GLB/glTF 모델 로드, 회전·줌·카메라 프리셋, 씬 저장/복원 (G1 계획) | 3D Viewer / Scene Editor | AssetVersion, Scene, CameraPreset (실제 스키마 TBD) | QA-3D-01~10 | G0 → G1 | 개발자 / PO | 라이선스 확인 GLB 3종 이상 로드; 카메라 조작·씬 저장/복원 및 재진입 검증 | GLB·실행 로그 미제출 | G0 통과 후 실행; Evidence pending |
| PRD-007 | 3D Simulation / P2 | 의상 메시·패턴·물리·바디 피팅은 Viewer와 분리된 R&D (Confirmed boundary) | Garment Simulation R&D | GarmentMesh, Pattern, BodyFit 등 제안 엔터티; API TBD | QA-GAR-01~(별도 설계 필요) | 별도 Gate | 개발자 / PO | 별도 물리·품질 기준과 샘플 데이터셋 승인 전 출시 범위에 포함하지 않음 | 미제출 | 보류 / Viewer 완료로 대체 불가 |
| PRD-008 | Try-on / P0 | 이미지 기반 AI 가상착장은 실제 Provider Adapter 호출로 검증 (G2 계획) | Try-on Engine / Provider Adapter | GenerationJob, JobExecution, Provider, Model, Output, RightsDeclaration | T-07, T-09, T-12, T-14; G2 QA 세트 | G0 → G2 | 개발자 / PO | 실제 API 요청·응답 메타데이터, request ID, 결과 저장, 권리·원가·시간 기록 | 실제 호출 증거 미제출 | Mock 불인정; Provider 계정/정책 필요 |
| PRD-009 | Photo / P1 | Photo Engine은 3D 뷰포트 캡처가 아닌 독립 2D 후처리 파이프라인 (Confirmed boundary) | Photo Engine | GenerationJob, JobExecution, AssetVersion, Output | QA-PH-01~16 | G3 선행 권고 → G4 | 개발자 / PO | P01~P12 대표 유형의 원본/결과 품질·비용·시간·권리 평가 | 미제출 | 독립 실행 증거 대기 |
| PRD-010 | Lookbook / P1 | SKU·모델·장면·결과를 그룹화하고 검수·승인·내보내기 (Confirmed direction) | Lookbook & Campaign / Workflow | Project, SKU, Asset, Output, Review, Approval | QA-LB-01~08(신규) | G3 이후, G5 | 개발자 / PO | 캠페인 산출물의 버전·승인·내보내기 이력 추적 가능 | 미제출 | G3 공통 코어 의존 |
| PRD-011 | Video / P2 | Video는 시간적 생성·프레임 일관성 별도 파이프라인으로 후속 (Confirmed boundary) | Video Pipeline | VideoJob, FrameAsset 등 추후 정의 | 별도 QA 계획 필요 | 후속 Gate | 개발자 / PO | 독립 품질·비용·권리 기준 승인 전 출시 기능으로 표현하지 않음 | 미제출 | 후속 |
| PRD-012 | Marketplace / P2 | Marketplace는 권리·등록·구매·라이선스·정산·분쟁 준비가 선행 (Confirmed direction) | Marketplace / Commerce | Listing, Purchase, License, Entitlement, Refund, Payout, Dispute | QA-MKT-01~(별도 설계) | 후속 Gate | 개발자 / PO | 권리·결제·정산·분쟁 정책 및 감사 증거 확보 전 거래 개시 금지 | 미제출 | 후속 |
| TECH-001 | API / P0 | API prefix `/v1` vs `/api/v1` 충돌을 저장소 확인 후 결정 (Known conflict) | API Gateway / Backend | OpenAPI, route registry | QA-API-BASE-01(신규) | G0 | 개발자 / PO | 실제 라우트·클라이언트·프록시·문서와 일치하는 단일 prefix 결정 및 ADR 기록 | 미제출 | TBD — repository audit required |
| TECH-002 | API / P0 | 범용 Generation Job과 기능별 Try-on/Photo 입력 스키마를 계층화하고 Job 시스템 중복 방지 (Proposed baseline) | Job Service / Feature Adapters | GenerationJob, JobExecution, JobEvent, Output; TryOnInput, PhotoInput(논리 스키마) | T-05, T-07~T-14; QA-JOB-01~13 | G2, G3, G4 | 개발자 / PO | 공통 lifecycle 재사용, 기능별 검증 스키마 분리, 결과 타입 명확 | 미제출 | 실제 API 계약 TBD |
| TECH-003 | API / P0 | Photo Job API 누락 보완 (문서 검토 항목) | Photo Adapter / API | PhotoInput, GenerationJob | QA-PH-API-01(신규) | G4 | 개발자 / PO | Photo 입력·견적·생성·상태·결과 조회 계약이 OpenAPI에 반영 | OpenAPI 미제출 | 문서상 보완 필요; 구현 확인 전 |
| TECH-004 | Job / P0 | Job / Execution / Event / Result 분리 및 상태 전이·재시도·취소·복구 일관성 (Proposed baseline) | Job Orchestrator / Worker | GenerationJob, JobExecution, JobEvent, Output | T-05, T-07~T-10, T-12~T-14; QA-JOB-01~13 | G2, G3, G4 | 개발자 / PO | 상태 전이 규칙·이벤트 이력·재시도/취소 결과가 일관되고 추적 가능 | 미제출 | 실제 상태 머신 TBD |
| TECH-005 | Job / P0 | 결과 파일과 DB 참조 영속화 완료 후에만 SUCCEEDED 처리 (Confirmed rule) | Worker / Output Persistence | Output, Asset, AssetVersion, JobEvent | T-07, T-14; QA-JOB-09, QA-JOB-13 | G2, G3, G4 | 개발자 / PO | Provider 성공만으로 Job 성공 처리 금지; 저장 완료 및 참조 검증 후 성공 | 미제출 | 구현 증거 대기 |
| TECH-006 | Queue / P0 | DB commit 후 queue publish 전 장애에 대한 복구 경로 (Proposed baseline) | Outbox / Queue / Worker | OutboxEvent, GenerationJob, JobEvent | T-13; QA-JOB-12(보완 권고) | G3 | 개발자 / PO | 프로세스 장애 후 Job 유실 없이 재발행 또는 명시적 복구 | 미제출 | Outbox 사용 여부 TBD |
| TECH-007 | Provider / P0 | Provider-neutral Adapter와 provider/model/capability/policy registry (Proposed architecture) | Engine Hub / Routing | Provider, Model, Capability, Policy | T-07, T-09, T-12; QA-PRV-01~08(신규) | G2, G4 | 개발자 / PO | 모델별 capability·정책·버전·요금 정보를 등록·조회·감사 가능 | 미제출 | 실제 registry 구현 TBD |
| TECH-008 | Provider / P0 | Hard filters 후 scoring; AUTO fallback은 명시 정책 하에서만, MANUAL은 자동 fallback 금지 (Proposed policy) | Routing / Policy Engine | Policy, Provider, Model, JobExecution | T-09, T-12; QA-PRV-05~08 | G2, G4 | 개발자 / PO | 비호환·권리 위반 후보 제외; fallback 정책과 실행 이력 기록; MANUAL 자동 전환 없음 | 미제출 | PO 정책 승인 필요 |
| TECH-009 | Credit / P0 | 멱등성 append-only Credit Ledger: RESERVE/CAPTURE/RELEASE/REFUND/ADJUST (Confirmed design direction) | Quote / Credit Ledger | Quote, CreditLedger, UsageRecord | T-05, T-06, T-08, T-10, T-14; QA-CR-01~07 | G3 | 개발자 / PO | 중복 예약/과금 방지, 원장 행 덮어쓰기 금지, 보정은 ADJUST 이벤트 | 미제출 | 동시성·트랜잭션 설계 TBD |
| TECH-010 | Security / P0 | Tenant isolation 및 업로드 검증 (Confirmed baseline) | Auth / RBAC / Asset API | Organization, Membership, Workspace, Role, Asset | T-01~T-04; QA-TEN-01~03, QA-AST-01~03 | G0, G3 | 개발자 / PO | 교차 tenant ID 요청에서 데이터 미노출·거절 | 미제출 | 실행 테스트 필요 |
| TECH-011 | Rights / P0 | Provider terms, commercial rights, training policy, region, retention, deletion policy 확인 (Confirmed requirement) | Rights / Provider Governance | RightsDeclaration, Provenance, License, ProviderPolicy, AuditEvent | G2 권리 QA, QA-PH 권리 항목, QA-G5-LEGAL-01(신규) | G2, G4, G5 | 개발자 + PO / PO | 입력 자산·출력물·Provider별 사용 조건과 보존/삭제/학습 정책을 기록하고 사용 전 차단 규칙 적용 | 정책 증빙 미제출 | Provider별 검토 필요 |
| TECH-012 | Observability / P1 | 구조화 로그·메트릭·트레이스 및 Job/Provider/비용 연결 (Proposed architecture) | Observability / Audit | JobEvent, UsageRecord, AuditEvent, trace context | QA-OBS-01~04(신규) | G2, G3, G4 | 개발자 / PO | request/job/provider ID로 실행 추적, 민감정보 마스킹, 오류·비용 조회 | 미제출 | 구현 경로 TBD |
| TECH-013 | Storage / P0 | S3 호환 저장소/CDN, 인증·Secret Manager/KMS 등 후보 아키텍처는 실구현 확인 후 확정 (Proposed) | Storage / Identity / Secrets | Asset, AssetVersion, Secret reference | QA-AST-01~06, QA-SEC-01~(신규) | G0, G3 | 개발자 / PO | 실제 배포 설정·접근제어·비밀관리·삭제/보존 절차 확인 | 미제출 | 후보 기술; 구현 확정 아님 |
| TECH-014 | Architecture / P1 | 초기 모듈형 모놀리스, API·Worker 분리 배포 가능; 초기 Kubernetes 불필요 (Proposed) | Platform Architecture | 서비스/배포 단위 TBD | QA-DEP-01~(신규) | G0 이후 | 개발자 / PO | 현재 규모·운영 조건에 맞는 ADR과 배포 증거 확보 | 미제출 | 개발자 기술 검토 및 PO 승인 필요 |
| OPS-001 | Review / P1 | Review/Approval/Audit 흐름과 변경 이력 추적 | Workflow / Admin | Review, Approval, AuditEvent | QA-REV-01~05(신규) | G3, G5 | 개발자 / PO | 승인자·시각·대상 버전·판정이 기록되고 승인 전 내보내기 정책 적용 | 미제출 | 업무 규칙 상세 TBD |
| OPS-002 | Cost / P0 | 실제 provider/model/version/usage/cost/latency를 Job 결과에 연결 | Usage & Cost | UsageRecord, Quote, CreditLedger, JobExecution | G2 비용 QA, QA-CR-04~07 | G2, G3, G4 | 개발자 / PO | 실제 공급자 사용량과 비용을 기록하고 견적 대비 편차 확인 가능 | 미제출 | 실제 계량 방식 TBD |
| OPS-003 | Reliability / P0 | timeout 및 결과 불명 상태에서 중복 실행·중복 과금 방지 | Job Orchestrator | GenerationJob, JobExecution, JobEvent, CreditLedger | T-08, T-09; QA-JOB-04, QA-JOB-07 | G2, G3 | 개발자 / PO | 공급자 상태 조회/복구 전 중복 실행 금지, 정산 중복 없음 | 미제출 | Provider별 복구 계약 TBD |
| OPS-004 | Reliability / P0 | 실행 중 취소와 Provider 취소 상태를 구분하고 정산 일관성 유지 | Job Orchestrator / Credit | GenerationJob, JobExecution, JobEvent, CreditLedger | T-10; QA-JOB-08, QA-CR-05 | G3 | 개발자 / PO | 내부 취소와 외부 취소 확인을 분리 기록하고 정책에 맞게 RELEASE/REFUND | 미제출 | Provider별 취소 지원 확인 필요 |
| OPS-005 | Export / P1 | 원본과 생성 결과를 별도 Asset/Version으로 보존하고 비교 가능 | Asset / Output | Asset, AssetVersion, AssetRelation, Output | T-11; QA-AST-04~06 | G3, G4 | 개발자 / PO | 원본 덮어쓰기 없음, 생성 결과·파라미터·출처 연결 | 미제출 | 구현 증거 대기 |
| GATE-000 | Gate / P0 | G0: 기존 저장소·UI·Mock·3D 코드 재현 및 재사용 감사 | Repository Audit | Git commit, build/test artifacts, module inventory | G0-E01~E10; T-01~T-14 mapping | G0 | 개발자 / PO | 저장소/branch/commit, 실행·테스트 로그, 재사용/수정/대체 판정표 제출 및 기준 통과 | 증거 미제출 | Evidence pending; 모든 구현 Gate 선행 |
| GATE-001 | Gate / P1 | G1: GLB Viewer 검증 | 3D Viewer | GLB-A/B/C, Scene, Camera | QA-3D-01~10 | G1 | 개발자 / PO | GLB 3종 로드, 조작, 저장/복원, 권한·성능·반응형 검증 | 증거 미제출 | G0 통과 필요 |
| GATE-002 | Gate / P0 | G2: 실제 Try-on Provider 1개 호출 및 결과·원가·권리 검증 | Try-on / Provider | 실제 request/response metadata, request ID, Output | G2 QA plan; T-07, T-09, T-12, T-14 | G2 | 개발자 / PO | Mock 아닌 실제 호출, 결과 영속화, 블라인드 품질, 비용·시간·정책 증거 | 증거 미제출 | G0 및 공급자 계정/권리 필요 |
| GATE-003 | Gate / P0 | G3: Project/Asset/Job/Output/Credit 통합 및 실패 복구 검증 | Core Integration | 공통 코어 논리 엔터티 | T-01~T-14; QA-JOB-12, QA-AST-06, QA-JOB-13, QA-CR-07 | G3 | 개발자 / PO | 정상·권한·멱등성·재시도·취소·장애 복구 시나리오 통과 | 증거 미제출 | G0 선행; 실제 DB/API 필요 |
| GATE-004 | Gate / P1 | G4: 독립 Photo Engine 품질·비용·권리 검증 | Photo Engine | P01~P12 dataset, Output, UsageRecord | QA-PH-01~16 | G4 | 개발자 / PO | 독립 2D 파이프라인, 품질 rubric, 비용·시간·권리 검증 | 증거 미제출 | G3 공통 코어 연계 권고 |
| GATE-005 | Gate / P0 | G5: 유료 파일럿·고객·법무·운영 검증 | Business Operations | Customer, Quote/Contract, Rights, Support, Refund | QA-G5-* (신규 계획 ID) | G5 | PO / PO | 실제 고객 승인·유료 계약·제공 가능 기능·권리·지원·환불·현지화 증거 | 증거 미제출 | 검증된 제품 기능 및 고객 증거 필요 |

## 3. 원본 P0 통합 테스트 T-01~T-14 보존표

다음 ID와 시나리오 의미는 원본 `AI_CREATOR_STUDIO_개발자_착수명세서_v0_1.docx`에서 확인한 내용이다. 새 QA ID는 원본 ID를 대체하지 않는다.

| 원본 ID | 원본 시나리오 | 원본 합격 기준 요약 | 연결 요구사항 | 추적/보완 |
|---|---|---|---|---|
| T-01 | 로그인 후 조직/워크스페이스 접근 | 멤버십에 따라 접근 허용/거절 | PRD-001, TECH-010 | QA-TEN-01, QA-TEN-03 |
| T-02 | 유효한 이미지 업로드 및 완료 처리 | Asset READY, 비공개 저장, 메타데이터 확인 | PRD-002~004 | QA-AST-01 |
| T-03 | 잘못된 MIME/시그니처/초과 크기 파일 업로드 | 거절, READY로 바뀌지 않음 | PRD-004, TECH-010 | QA-AST-02, QA-AST-03 |
| T-04 | 다른 조직의 asset/job ID로 요청 | 데이터 노출 없이 거절 | PRD-001, TECH-010 | QA-TEN-01, QA-TEN-02 |
| T-05 | 유효한 견적 후 Job 생성 | 예약 원장과 Job 생성, 큐 등록 일관성 | TECH-002, TECH-004, TECH-009 | QA-CR-01~03, QA-JOB-06; QA-JOB-12 보완 권고 |
| T-06 | 크레딧 부족 상태에서 Job 생성 | 예약/큐 등록 없음 | TECH-009 | QA-CR-02 |
| T-07 | Provider 성공 및 결과 저장 | 결과 Asset/Version 저장 후 성공 및 정산 | PRD-008, TECH-005, OPS-002 | QA-JOB-09, QA-CR-04 |
| T-08 | 동일 idempotency key 요청 반복 | 중복 Job/예약/과금 없음 | TECH-009, OPS-003 | QA-JOB-04, QA-CR-03 |
| T-09 | Provider timeout 및 결과 불명 | 중복 실행을 피하고 상태 조회/복구 절차 수행 | TECH-004, OPS-003 | QA-JOB-07 |
| T-10 | 실행 중 취소 요청 | 내부/Provider 취소 상태 구분, 정산 일관성 | TECH-004, OPS-004 | QA-JOB-08, QA-CR-05; QA-JOB-13 보완 추적 |
| T-11 | 원본과 생성 결과 비교 | 원본 보존, 결과는 별도 Asset/Version으로 연결 | PRD-003, OPS-005 | QA-AST-04~06 |
| T-12 | 실행 실패/재시도/fallback 이력 조회 | Provider/model/version/비용/오류/재시도 연결 확인 | TECH-004, TECH-007, TECH-008 | QA-JOB-10~12, QA-PRV-05~08 |
| T-13 | 큐 발행 전 DB 커밋 후 프로세스 장애 | Outbox/복구 작업으로 Job 유실 방지 | TECH-006 | QA-JOB-12 (보완 권고) |
| T-14 | Provider 성공 후 결과 저장 장애 | 성공/실패 오판 없이 재처리/정산 조정 가능 | TECH-005, TECH-009 | QA-JOB-13 (보완 권고), QA-CR-07 |

## 4. Gate 선행조건과 증거 연결

| Gate | 선행조건 | 필수 증거 패키지 | 통과 전 금지 사항 |
|---|---|---|---|
| G0 | 개발자 저장소 및 실행 환경 접근 | G0-E01~E10: 저장소/commit, 환경 실행, UI, FastAPI Mock, Three.js/GLB, DB/API, 테스트 로그, 재사용 판정 | 기존 구현을 재사용 가능/완료로 단정 금지 |
| G1 | G0 통과 및 GLB 샘플 권리 확인 | GLB 3종, 브라우저 실행 영상/로그, QA-3D 결과, 씬 저장·복원 증거 | 3D Viewer와 Garment Simulation을 동일 기능으로 표현 금지 |
| G2 | G0 통과, 실제 Provider 계정·상업 이용 조건 확인 | 마스킹 요청/응답, request ID, 실제 결과, 품질 평가, 원가·시간, 권리 정책 | Mock 결과를 실제 Provider 연동으로 표시 금지 |
| G3 | G0 및 핵심 API/DB/Queue 접근 | T-01~T-14 실행 결과, 통합 E2E 로그, 원장/멱등성/복구 증거 | 문서상 테스트 ID 존재만으로 통과 선언 금지 |
| G4 | 독립 Photo Engine 실행 경로 및 데이터셋 | P01~P12, QA-PH-01~16, 원본/결과, 블라인드 평가, 비용·시간·권리 | 3D Viewer 캡처/단순 리사이즈를 Photo Engine 완료로 인정 금지 |
| G5 | 고객에게 제공할 기능의 해당 Gate 통과 | 고객 인터뷰·승인·계약·결제·지원·환불·법무·국가별 체크 증거 | 검증되지 않은 기능, ROI/SLA/시간 절감 수치 약속 금지 |

## 5. QA 추가 항목 및 중복/누락 관리

| QA ID | 연결 원본/영역 | 목적 | 상태 |
|---|---|---|---|
| QA-JOB-12 | T-05/T-12/T-13 | 큐 발행 전 커밋 장애 및 재발행/복구 추적 보완 | 추가 보완 권고; 실제 테스트 미확인 |
| QA-AST-06 | T-11 | Asset 파생 관계·버전·원본 불변성 보완 | 추가 보완 권고; 실제 테스트 미확인 |
| QA-JOB-13 | T-10/T-14 | 취소·결과 저장 장애·상태/정산 조정 보완 | 추가 보완 권고; 실제 테스트 미확인 |
| QA-CR-07 | T-14 | Provider 성공 후 결과 저장 실패 시 원장 정산 조정 보완 | 추가 보완 권고; 실제 테스트 미확인 |
| QA-3D-01~10 | G1 | GLB 로드·오류·카메라·씬 저장복원·권한·성능·반응형·Asset 연결 | 계획 문서 존재; 실행 증거 대기 |
| QA-PH-01~16 | G4 | 독립 Photo Engine 품질·경계·정체성·재질·브랜드·자연스러움·목적 적합성 | 계획 문서 존재; 실행 증거 대기 |

- 중복 방지: Try-on과 Photo는 동일한 공통 Job lifecycle을 공유하되 입력 스키마와 Provider capability/policy를 분리한다.
- 계층 경계: 3D Viewer, 3D Garment Simulation, 이미지 기반 Try-on, 독립 Photo Engine, Video Pipeline은 서로의 완료 증거를 대체하지 않는다.
- 요구사항 충돌: `/v1` 대 `/api/v1`은 G0에서 저장소·프록시·클라이언트·OpenAPI를 대조해 ADR로 확정한다.
- 누락 확인 필요: Photo Job의 견적/생성/상태/결과 API, Asset 소유권·공유·파생 관계, Character Profile 버전 연결, Provider policy registry, Credit 동시성, 데이터 삭제/보존, 관리자 감사 기능.

## 6. 미결정 사항 레지스터

| Decision ID | 미결정 사항 | 필요한 입력/검증 | 결정 책임 | 상태 |
|---|---|---|---|---|
| DEC-001 | API prefix `/v1` vs `/api/v1` | 저장소 route, reverse proxy, frontend client, OpenAPI, 배포 설정 | 개발자 제안 / PO 승인 | TBD — repository audit required |
| DEC-002 | 실제 DB 테이블·마이그레이션 | 현재 schema, migration history, ERD | 개발자 | TBD — repository audit required |
| DEC-003 | 실제 API route·request/response | OpenAPI 및 구현 코드 | 개발자 | TBD — repository audit required |
| DEC-004 | 첫 Try-on Provider 및 모델 | 공식 상업 이용·학습·보존·리전 정책, API 접근, 품질/비용 | 개발자 제안 / PO 승인 | TBD — G2 입력 필요 |
| DEC-005 | Provider routing/fallback 정책 | AUTO/MANUAL별 허용 조건, 비용 상한, 오류 코드 | 개발자 제안 / PO 승인 | Proposed; 승인 대기 |
| DEC-006 | Credit 단위·가격·환불 규칙 | 실제 Provider 원가, 마진, 세금·결제·국가별 조건 | PO | TBD — 실측/시장 검증 필요 |
| DEC-007 | Storage/Auth/Secrets 공급자 | 보안·비용·리전·운영 비교 및 기존 구현 감사 | 개발자 제안 / PO 승인 | 후보안; 확정 아님 |
| DEC-008 | Character Studio MVP 범위 | Identity Profile 필수 필드·버전·재현성 | PO | TBD |
| DEC-009 | Photo Engine 품질 합격선 | P01~P12 기준 이미지, 평가자 rubric, 최소 점수 | PO + 개발자 | G4 계획 단계 |
| DEC-010 | 국가별 파일럿 운영 범위 | 고객 수요, 결제, 세금, 개인정보, 지원 언어/시간대 | PO | G5 검증 필요 |

## 7. 증거 제출 템플릿

각 요구사항/QA 실행마다 아래 필드를 남긴다.

- Req ID / QA ID / 원본 T ID
- 저장소 URL / branch / commit SHA
- 환경 및 실행 명령
- 입력 데이터셋 ID와 권리 상태
- 실행 시작·종료 시각 및 실행자
- 기대 결과 / 실제 결과 / PASS·FAIL·BLOCKED
- 로그·스크린샷·영상·Provider request ID 링크
- 비용·사용량·지연시간(해당 시)
- 결함 ID / 재현 절차 / 수정 commit
- 검토자 및 PO 승인 여부

## 8. 범위 및 신뢰성 주의

1. 본 문서는 기존 Library 문서에서 확인한 요구사항과 계획을 통합한 추적표다. 코드·API·DB·클라우드의 실재 경로를 확인한 문서가 아니다.
2. `QA-*` 신규 ID 중 별도 QA 명세가 아직 작성되지 않은 항목은 추적용 제안 ID다. 실행 가능한 테스트 케이스로 간주하지 않는다.
3. G0~G5 계획 문서가 존재해도 해당 Gate가 통과한 것은 아니다.
4. 개발자에게 본 문서가 전달되었다고 간주하지 않는다. 실제 전달 및 수신 확인은 별도 기록이 필요하다.
5. 문서 변경은 Change Control에 따라 요청 → 개발자 영향 분석 → 제품/UX/QA 영향 분석 → PO 승인 → 문서·코드 동시 버전 반영 순으로 처리한다.

