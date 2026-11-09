# AI CREATOR STUDIO — 통합 실행 기준서 v0.2

- 기준일: 2026-11-02
- 문서 상태: 통합 작업 기준 초안 / 제품 책임자 승인 및 개발자 기술 검토 전
- 적용 범위: 사업·제품·UX·기술 아키텍처·개발 협업·QA·글로벌 진출
- 상위 방향: Global-first, B2B fashion/e-commerce initial commercial wedge
- 문서 목적: 기존 기획·개발 자료를 하나의 실행 기준으로 연결하고, 미확정 사항과 실제 증거가 필요한 항목을 분리

> 이 문서는 기존 원본 문서를 대체하거나 개발자 구현 완료를 선언하지 않는다. 상충하는 제안은 저장소·실측·권리 검토가 필요한 결정으로 남긴다. 기존 문서는 보존하고, 이 문서를 통합 검토 기준으로 사용한다.

---

## 0. 통합 결론

AI CREATOR STUDIO는 단일 이미지 생성기가 아니라, 기업과 창작자가 보유한 인물·상품·브랜드 자산을 기반으로 AI 비주얼 콘텐츠를 제작하고, 품질·비용·권리·승인·버전을 관리하는 글로벌 크리에이티브 운영 플랫폼이다.

초기 상업 진입은 패션·의류 이커머스의 상품 콘텐츠와 AI 룩북 업무에 집중한다. 다만 제품·브랜드·데이터·권리·결제·Marketplace 구조는 처음부터 글로벌 확장 가능성을 고려한다. 시장 진입 순서는 실제 고객 검증 결과로 정한다. 한국 우선 진출을 확정한 과거 문서는 현 전략의 기준으로 사용하지 않는다.

제품은 세 축으로 성장한다.

1. **Studio** — Character, 3D, Photo, Try-on, Lookbook, 추후 Video.
2. **Business** — 팀·브랜드·SKU 단위 반복 제작, 검수, 승인, 내보내기.
3. **Marketplace** — 캐릭터·모델·프리셋·템플릿·3D 에셋·콘텐츠·서비스의 권리 기반 거래.

첫 유료 상품은 플랫폼 전체가 아니라 **브랜드별 AI 룩북/상품 콘텐츠 파일럿**이다. 고객의 실제 상품과 승인된 모델 자산으로 결과 품질, 제품 보존, 작업 시간, 원가, 수정 횟수, 재사용 의사를 측정한다. 검증 전 ROI·성능·얼굴 보존·제품 보존을 보장하지 않는다.

### 0.1 제품의 핵심 업무 흐름

`고객 자산 → 작업 정의 → 권리/정책 확인 → capability 검증 → 비용 견적 → 크레딧 예약 → 비동기 생성/편집 → 결과 영속화 → 품질 검수 → 승인 → 버전/SKU 연결 → 다운로드/채널 내보내기`

### 0.2 절대 혼동하지 않을 기술 경계

- Character Studio: 얼굴·체형·헤어·피부·의상·포즈 등의 구조화된 Identity Profile 관리.
- 3D Viewer/Scene Editor: GLB/glTF 로드, 씬 그래프, 카메라, 조명, 재질, 변환, 저장/복원.
- 3D Garment Simulation: 의상 패턴·메시·리깅·충돌·천 물리. Viewer와 별도 R&D.
- Image-based AI Try-on: 인물 참조 이미지와 의류 이미지로 결과 이미지를 만드는 공급자 파이프라인.
- Photo Engine: 사진형 2D 보정·후처리. 3D 뷰포트 캡처와 다른 결과 파이프라인.
- Video Pipeline: 프레임·모션·시간 일관성을 다루는 후속 엔진.
- Marketplace: 등록·권리·라이선스·거래·환불·분쟁·정산이 필요한 별도 비즈니스 시스템.

---

## 1. 전략 기준

### 1.1 브랜드와 포지셔닝

- 마스터 브랜드: **AI CREATOR STUDIO**
- 글로벌 비전: **Create Characters. Build Worlds. Make Content.**
- B2B 핵심 메시지: **Turn your product and brand assets into repeatable visual content workflows.**
- 패션/3D 상세 메시지 “캐릭터는 3D로 설계하고, 결과물은 실제 사진처럼.”은 해당 기능과 품질이 실제 검증된 범위에서만 사용한다.

제품을 단순히 “AI 이미지 생성”으로 포지셔닝하지 않는다. 고객이 구매하는 가치는 상품·브랜드 자산 재활용, 제품 디자인 보존, 모델/브랜드 일관성, 반복 제작, 검수·승인, 비용 통제, 권리·버전 이력이다. Multi-engine neutrality는 차별화 가설이며 고객 인터뷰와 유료 파일럿으로 검증한다.

### 1.2 고객군

초기 ICP 후보:

1. 온라인 패션 쇼핑몰·셀러.
2. D2C 및 패션 브랜드.
3. 브랜드 내부 콘텐츠/이커머스 팀.
4. 패션 콘텐츠 제작 대행사·스튜디오.
5. 의류 제조사·도매·유통사.

우선순위는 회사 규모만으로 정하지 않는다. 월별 SKU/콘텐츠 생산량, 기존 촬영 비용과 리드타임, 제품 이미지 보유 상태, 브랜드 승인 절차, 재촬영 빈도, AI 결과 사용 허용 범위, 구매 의사와 예산을 기준으로 점수화한다.

### 1.3 첫 유료 제안

**Brand-specific AI Lookbook & Product Content Pilot**

- 고객의 실제 상품 SKU와 권리 확인된 인물/모델 참조 자료 사용.
- 사전에 합의한 소수 SKU와 출력 유형으로 범위를 제한.
- 고객 브랜드 가이드와 제품 보존 기준을 수집.
- 원본·생성 결과·수정 버전·승인 상태를 기록.
- 품질, 성공률, 소요 시간, 실제 공급자 비용, 수동 수정 시간, 고객 승인률, 재사용/재구매 의사를 측정.
- 파일럿 결과에 따라 반복 계약·월간 패키지·SKU 단위 과금 가설을 조정.

가격은 실제 Provider 원가, 실패/재시도율, 사람의 검수·수정 비용, 저장·전송 비용, 고객지원 비용, 목표 공헌이익을 측정한 뒤 확정한다. 크레딧 숫자와 API 예시 금액을 실제 가격처럼 노출하지 않는다.

### 1.4 글로벌 전략

Global-first는 모든 국가를 동시에 영업한다는 뜻이 아니다. 제품·데이터·권리·브랜드·과금 구조를 글로벌-ready로 설계하고, 시장별 진입은 검증 결과에 따라 순차 실행한다.

- 영어를 기본 제품/문서 언어 후보로 두고 다국어 구조를 지원.
- 통화·세금·결제 수단·정산 국가를 코드에 하드코딩하지 않음.
- 데이터 지역, 국외 이전, 보존·삭제 정책을 공급자별로 기록.
- 국가별 고객지원·약관·소비자/사업자 거래 요건을 별도 확인.
- 미국/캐나다, 일본, 영국/유럽, 싱가포르/동남아 등은 조사 후보이지 확정 순위가 아님. 중국은 별도 정책·플랫폼·결제·데이터 전략으로 검토.
- 실제 고객 인터뷰·유료 파일럿·결제 가능성·지원 비용·법률 준비도에 따라 국가 우선순위를 결정.

---

## 2. 제품 구조 및 IA 기준

### 2.1 플랫폼 계층

```text
AI CREATOR STUDIO
├─ Public Website / Trust / Marketing
├─ Accounts / Organization / Workspace / RBAC
├─ Project / SKU / Asset / Asset Version / Rights
├─ Character Studio / Identity Profile
├─ 3D Studio / Scene Editor
├─ Try-on Engine / Provider Adapters
├─ Photo Engine
├─ Lookbook & Campaign / Workflow
├─ Review / Approval / Export
├─ Engine Registry / Capability / Policy / Cost
├─ Credit Ledger / Billing / Audit
├─ Video Pipeline (later)
└─ Marketplace (rights + commerce readiness required)
```

### 2.2 공개 웹사이트 IA

- Home
- Product
  - Character Studio
  - 3D Studio
  - Virtual Try-on
  - Photo Studio
  - Video Studio (출시 전 기능 표기 금지)
  - Business Workflow
- Solutions
  - Fashion & Apparel
  - E-commerce
  - Agencies
  - Creators
- Marketplace (실제 거래 개시 전에는 Preview/Coming Soon 상태 명확히 표시)
- Pricing
- Resources: Tutorials, Use Cases, Documentation, Quality Method, Trust & Legal
- Company / Contact / Support
- Sign in / Demo Request

홈페이지는 B2B 자산 중심 진입을 기본으로 한다. 주요 진입 업무는 기존 사진 편집, 상품 이미지 제작, AI 모델·가상착장, 룩북·캠페인이다. 캐릭터 중심 진입은 보조 경로로 유지한다. 고객이 반드시 캐릭터를 먼저 생성해야만 작업을 시작할 수 있게 만들지 않는다.

웹사이트 구현은 별도 승인/지시가 있기 전까지 개발 범위로 자동 편입하지 않는다. 미구현 기능은 실제 기능처럼 표현하지 않고, 합성 시안은 예시임을 표시한다.

### 2.3 로그인 후 앱 IA

- Workspace Home
- Create: Product Content / Photo Edit / Try-on & Lookbook / 3D Studio / Character
- Projects & SKU
- Asset Library & Brand Kit
- Jobs & Results
- Review & Approval
- Usage & Billing
- Team & Settings

운영자 콘솔은 고객용 메뉴와 분리한다. 운영자 메뉴는 사용자·워크스페이스·권한, Provider/Model/Capability/Policy, Job·원가·크레딧, 권리·삭제 요청, 보안·감사 로그를 포함한다.

### 2.4 UX 원칙

- 사용 목적을 먼저 묻고 전문가 옵션은 단계적으로 공개.
- 초보자에게 가이드형 흐름, 전문가에게 모델·파라미터·프롬프트 제어 제공.
- 실행 전에 선택 엔진, 예상 비용/시간, 입력 제약, 권리·데이터 처리 요약을 보여줌.
- 결과 화면은 원본/결과 비교, 버전, 실패 사유, 품질 검수, 승인 상태를 중심으로 구성.
- Mock/미리보기와 실제 생성 결과를 시각적으로 구분.
- 3D 씬과 Try-on 입력 이미지는 서로 다른 Asset로 취급하며 자동 변환을 가정하지 않음.

---

## 3. 기술 아키텍처 기준

### 3.1 권장 초기 구조

- Frontend: Next.js / React / TypeScript.
- API: Python / FastAPI / Pydantic.
- Database: PostgreSQL.
- Async: Queue + Worker; 초기에는 운영 복잡도가 낮은 관리형/단순 큐 우선.
- File: S3-compatible object storage + CDN.
- Auth: managed Auth/OIDC 또는 검증된 인증 솔루션.
- Secrets: Secret Manager/KMS.
- Observability: structured logs, metrics, traces, OpenTelemetry.
- 3D: Three.js, GLTFLoader, OrbitControls; 압축 모델 필요 시 DRACO/KTX2 지원 검토.

초기에는 모듈형 모놀리스로 시작하되 API와 Worker를 별도 실행·배포할 수 있도록 경계를 둔다. 초기 Kubernetes 및 다수 마이크로서비스는 필수로 두지 않는다. 위 기술은 권장 기준이며 실제 저장소와 개발자의 기술 검토가 우선한다.

### 3.2 논리 데이터 모델

**Tenant & Access**
- Organization
- Membership
- Workspace
- WorkspaceMembership 또는 명확한 Organization↔Workspace membership 관계
- Role / Permission / Policy

**Work & Assets**
- Project
- SKU
- Asset
- AssetVersion
- AssetRelation (source/derived/variant/preview 등)
- RightsDeclaration
- Provenance
- License / Entitlement
- BrandProfile

**Identity & 3D**
- Character
- CharacterIdentityProfile
- IdentityProfileVersion
- CharacterReferenceAsset
- Scene3D
- SceneVersion

**AI execution**
- Provider
- ProviderModel
- CapabilityEvidence
- ProviderPolicy
- CostQuote
- GenerationJob
- JobExecution
- JobEvent
- GenerationResult
- OutboxEvent

**Commercial & governance**
- CreditAccount
- CreditLedger (append-only)
- UsageRecord
- Review
- Approval
- AuditEvent
- RetentionPolicy
- DeletionRequest

**Marketplace later**
- Listing
- Purchase
- LicenseGrant
- Refund
- Dispute
- Payout
- Tax/SettlementRecord

실제 DDL을 확정하기 전에 기존 DB/ORM/마이그레이션을 감사한다. Organization/Membership 계층을 제거하지 않는다. Workspace 중심으로 단순화하더라도 조직 소유권·멤버십·역할 관계가 보존되어야 한다.

### 3.3 Asset 원칙

- 원본 파일은 불변으로 보존하고 파생 결과는 새 AssetVersion으로 기록.
- 모든 Asset은 소유자/테넌트/워크스페이스/프로젝트 범위가 명확해야 함.
- 공개/비공개, 공유, 파생, 외부 공급자 전송 동의를 별도 관리.
- 파일 시그니처·실제 디코딩·용량·해상도·악성 파일 검사.
- 다운로드는 권한 확인 후 짧은 만료 URL 발급.
- 삭제 요청은 원본, 파생본, 백업, 공급자 보존 정책까지 추적.
- 고객 비공개 자산은 기본적으로 Marketplace 공개 대상이 아님.

### 3.4 Character Identity Profile

캐릭터는 한 장의 이미지가 아니라 재사용 가능한 구조화 프로필이다.

- 외형: 얼굴형, 눈·눈썹·코·입, 피부톤, 헤어 스타일·색·질감.
- 체형·비율: 필요한 범위에서 명시적으로 선택/입력한 속성만 저장.
- 스타일: 의상·액세서리·메이크업.
- 연출: 표정·포즈·카메라·배경·조명.
- 관계: 개인·커플·브랜드 모델.
- 버전: 기준 이미지, 설정값, 변경 이력, 참조 Asset, 생성 Job.

민감한 생체·건강·인종 속성을 추론하거나 불필요하게 저장하지 않는다. 얼굴/인물 일관성은 공급자별 capability와 내부 평가 항목으로 취급하며 보장 문구로 사용하지 않는다.

### 3.5 3D Viewer / Scene Editor

초기 Gate 범위:
- GLB/glTF 로드와 오류 표시.
- 카메라 orbit/zoom/pan.
- 정면/측면/후면 프리셋.
- 모델 위치·회전·스케일.
- 조명·배경·재질 override의 기본 조정.
- 씬 저장·복원 및 버전 충돌 방지.
- GLB 파일 3종 이상으로 브라우저 검증.

Viewer는 우선 클라이언트에서 렌더링한다. 카메라 조작을 매번 API 호출하지 않고 복원에 필요한 Scene State만 저장한다. 3D 의상 물리 시뮬레이션, 패턴 제작, 자동 리깅, 완전한 360도 재구성은 이 Gate에 포함하지 않는다.

### 3.6 Provider Adapter / Engine Hub

표준 Adapter 계약:
- `capabilities`
- `validate_request`
- `estimate_cost`
- `submit`
- `get_status`
- `fetch_result`
- `cancel`
- `normalize_error`

라우팅 순서:
1. 작업 유형·입력 형식·해상도·인물/의류 제약 필터.
2. 테넌트 허용 공급자, 데이터 지역, 상업 이용, 보존·학습 정책, 예산 필터.
3. 검증된 capability와 현재 운영 상태 확인.
4. 통과한 후보만 품질·비용·지연·성공률로 비교.

MANUAL 선택은 사용자에게 알리지 않은 공급자 변경/fallback을 금지한다. AUTO는 사전에 공개된 정책과 동의 범위 내에서만 fallback한다. 공급자 문서에 적힌 기능과 내부 테스트가 확인한 기능을 구분한다.

### 3.7 Job 상태 및 복구 원칙

Job과 개별 Execution을 분리하고, 모든 상태 변경을 JobEvent로 기록한다. 최소 상태는 원본 명세서의 DRAFT, VALIDATING, COST_ESTIMATED, CREDIT_RESERVED, QUEUED, RUNNING, POST_PROCESSING, REVIEW_REQUIRED, SUCCEEDED, FAILED, CANCELED, EXPIRED, RETRYING, PARTIALLY_SUCCEEDED를 기준으로 실제 구현과 맞춰 정규화한다.

필수 불변조건:
1. 요청 검증 전 크레딧 예약 금지.
2. 크레딧 예약 성공 전 공급자 큐 등록 금지.
3. 공급자 호출 전 Job/Execution을 DB에 기록.
4. Timeout은 공급자 실행 실패로 단정하지 않고 공급자 request ID/상태를 확인.
5. 공급자 취소 성공과 내부 Job 취소 상태를 구분.
6. 결과 파일과 메타데이터 영속화 전 SUCCEEDED 금지.
7. 종료 상태를 과거 상태로 되돌리지 않고 재실행은 새 Job 또는 명시적 Retry Execution으로 기록.
8. 부분 성공은 Job과 BatchItem/Result 상태를 분리.
9. DB와 큐 사이 유실 방지를 위해 Outbox 또는 동등한 복구 패턴 사용.

### 3.8 Credit Ledger

append-only 원장 이벤트:
- RESERVE
- CAPTURE
- RELEASE
- REFUND
- ADJUST

멱등성 키와 DB 트랜잭션으로 중복 예약·확정을 방지한다. 예상 비용과 실제 비용을 구분하고, 실제 사용량 확정 후 잔액 차이를 처리한다. Provider timeout/결과 불명 상태에서 중복 과금되지 않도록 공급자 요청 ID와 내부 실행 ID를 연결한다. 테스트 크레딧과 실제 결제는 분리한다.

### 3.9 API 경로 충돌 해결 원칙

기존 착수명세서 v0.1은 `/v1`, 이후 기술 아키텍처/개발자 초안은 `/api/v1`을 제안한다. 어느 쪽도 저장소 확인 전 확정하지 않는다.

결정 절차:
1. 실제 router, OpenAPI, frontend API client, deployment proxy를 확인.
2. 이미 외부에 노출된 경로가 있으면 하위 호환성 우선.
3. 신규 경로를 채택할 경우 migration/alias/deprecation 계획을 작성.
4. API contract test로 실제 배포 경로를 검증.

### 3.10 API 리소스 계층

범용 Generation 계약을 유지하고 기능별 입력 계약을 분리한다. Try-on만 독립 Job 시스템으로 만들지 않는다.

- `/projects`
- `/assets`, `/assets/{id}/versions`, `/assets/upload-intents`
- `/characters`, `/identity-profiles`
- `/scenes-3d`
- `/engines/providers`, `/engines/models`, `/engines/capabilities`
- `/generation-quotes`, `/generation-jobs`, `/jobs/{id}`
- 작업 유형별 payload: `image_edit`, `product_content`, `virtual_tryon`, `photo_refinement` 등
- `/reviews`, `/approvals`, `/exports`
- `/credits`, `/usage`

정확한 경로와 필드명은 저장소 감사 후 OpenAPI 기준으로 확정한다. `/tryon-jobs`와 `/photo-jobs`를 별도 구현하더라도 공통 Job lifecycle/ledger/result 체계를 중복 생성하지 않는다.

---

## 4. 개발 및 검증 실행 순서

### WP-00 — 기존 구현 감사 (G0)

**Owner:** 개발자 / **Review:** ChatGPT / **Approver:** 제품 책임자

제출 증거:
- 저장소 URL, branch, commit hash, README, 실행 명령.
- UI prototype 실행 및 캡처.
- FastAPI Mock 소스와 테스트 로그.
- Three.js/GLTFLoader/OrbitControls 소스와 GLB 실행 증거.
- 기존 DB/API/OpenAPI 구조.
- FASHN 등 Provider 연결 상태의 마스킹된 요청/응답 메타데이터.
- 파일/모듈별 재사용·수정·대체 판정 및 이유.
- 미완료/차단 이슈와 의존성.

**완료 기준:** 다른 개발 환경에서 재현 가능한 실행 절차, 현재 상태와 문서 차이, 재사용 근거가 기록됨.

### WP-01 — 3D Viewer (G1)

- 기존 Three.js 구현 감사 후 재사용.
- GLB 3종 이상 로드.
- orbit/zoom/pan, front/side/back presets.
- loading/error/unsupported file handling.
- Scene State save/restore.
- 모델별 성능과 메모리/콘솔 오류 기록.

**제외:** cloth simulation, garment pattern editor, production-grade 3D fitting.

### WP-02 — 실제 Try-on Provider PoC (G2)

- 권리 확인된 인물 기준 이미지 1장과 개별 의류 이미지 3~5장.
- 콜라주 시안을 실제 API 입력으로 사용하지 않음.
- 동일 입력으로 최소 1개 Provider를 실제 호출하고, 가능하면 두 번째 후보를 비교.
- 공급자명을 가린 블라인드 평가.
- 제품 디자인 보존, 모델 일관성, 착장 자연스러움, 결함, 성공률, 지연, 실제 원가, 재시도, 권리/정책 기록.
- 비밀키·개인정보 제거한 request/response metadata와 원본/결과 파일 보존.

**완료 기준:** 실제 호출과 결과가 재현 가능하고, 비용·품질·권리 판단에 필요한 근거가 기록됨. Mock은 통과 증거가 아님.

### WP-03 — 공통 수직 통합 (G3)

`Login → Workspace → Project → Asset Upload → Quote → Credit Reserve → Job → Provider → Output Persist → Review → Capture/Release → Export`

테스트: 권한, 중복 요청, quote 만료, 잔액 부족, 큐 발행 실패, provider timeout, 재시도, 취소, 결과 저장 실패, 부분 성공, 삭제 요청.

### WP-04 — Photo Engine (G4)

- Try-on 결과 또는 승인된 입력에서 독립적인 Photo Job 실행.
- 원본과 후처리 버전 별도 보존.
- 피부/헤어/섬유 디테일, 색상, 로고·상품 디테일 보존, 해상도, 결함을 평가.
- 실제 사진형 품질을 주장하기 전 고객/내부 블라인드 평가 통과.

### WP-05 — Video 및 3D Garment Simulation 조사

초기 핵심 흐름과 분리한 기술 스파이크. 입력 조건, 공급자/오픈소스 옵션, 라이선스, GPU/클라우드 비용, 품질, 지연, 권리, 운영 난이도 비교 후 별도 승인.

### WP-06 — Marketplace 준비

실거래 공개 전 다음을 설계·검증:
- 판매자 검증 및 권리 선언.
- provenance와 라이선스 범위(개인/상업, 수정, 재배포, 재판매, 독점, 기간, 지역, 좌석/수량).
- AI 생성물 고지와 출처/귀속.
- 신고·삭제·IP 분쟁·환불·차지백.
- 수수료·수익 배분·세금·원천징수·국가별 payout.
- 구매한 라이선스의 Asset/Version 연결.
- 구매 후 판매 중단/권리 철회 처리.

---

## 5. QA 테스트 카탈로그

모든 테스트는 `Requirement ID`, `Test ID`, `Build/Commit`, `Environment`, `Input Asset IDs`, `Expected`, `Actual`, `Evidence URI`, `Pass/Fail`, `Defect ID`를 기록한다.

### 5.1 Tenant / Access
- QA-TEN-01: 다른 Organization의 Project ID 접근 거부.
- QA-TEN-02: 다른 Workspace Asset 다운로드 거부.
- QA-TEN-03: Viewer 역할의 업로드/Job 실행 거부.
- QA-TEN-04: Support Operator의 고객 콘텐츠 기본 열람 차단.

### 5.2 Asset
- QA-AST-01: 정상 이미지 업로드·디코딩·READY.
- QA-AST-02: 확장자/MIME 위장 파일 거절.
- QA-AST-03: 크기·픽셀 상한 초과 거절.
- QA-AST-04: 원본 덮어쓰기 금지 및 새 Version 생성.
- QA-AST-05: 삭제 요청과 파생 Asset 관계 추적.

### 5.3 3D
- QA-3D-01: GLB sample A/B/C 정상 로드.
- QA-3D-02: 손상/미지원 GLB의 오류 처리.
- QA-3D-03: 카메라 preset과 orbit/zoom/pan.
- QA-3D-04: 씬 저장 후 새 세션에서 동일 상태 복원.
- QA-3D-05: 동시 편집 시 버전 충돌 처리.

### 5.4 Provider / Job
- QA-JOB-01: capability 불일치 입력 거절.
- QA-JOB-02: MANUAL provider 선택 유지, silent fallback 금지.
- QA-JOB-03: AUTO fallback은 정책·사용자 동의 범위 내에서만 실행.
- QA-JOB-04: 동일 Idempotency-Key + 동일 body는 중복 Job 생성 금지.
- QA-JOB-05: 동일 key + 다른 body는 conflict.
- QA-JOB-06: queue publish 실패 시 Outbox 복구.
- QA-JOB-07: timeout 후 provider 상태 확인, 중복 과금 방지.
- QA-JOB-08: 취소 요청과 provider 취소 결과를 구분 기록.
- QA-JOB-09: 결과 저장 실패 시 SUCCEEDED 금지.
- QA-JOB-10: retry는 새 execution/history로 남김.
- QA-JOB-11: partial success에서 Job/Result 상태 구분.

### 5.5 Credit
- QA-CR-01: 검증 실패 시 RESERVE 발생하지 않음.
- QA-CR-02: 잔액 부족 시 Job 큐 등록 금지.
- QA-CR-03: 동일 Job 중복 예약 금지.
- QA-CR-04: 성공 시 실제 사용량 CAPTURE 및 잔액 RELEASE.
- QA-CR-05: 확정 실패/공급자 실패 시 정책에 맞는 RELEASE/REFUND.
- QA-CR-06: 원장 수정은 기존 행 변경이 아닌 ADJUST 이벤트.

### 5.6 Output / Review / Export
- QA-OUT-01: 결과 파일, metadata, AssetVersion, GenerationResult 연결.
- QA-OUT-02: 원본/결과 비교 가능.
- QA-OUT-03: 승인자·시각·버전 이력 보존.
- QA-OUT-04: 권한 없는 다운로드 차단.
- QA-OUT-05: 만료된 signed URL 거절.

### 5.7 Provider 품질 평가
각 샘플을 1~5점으로 평가하되 실제 결과가 생성되기 전 점수를 채우지 않는다.
- Product Fidelity: 색상, 실루엣, 패턴, 로고, 디테일.
- Identity Consistency: 얼굴/헤어/체형 일관성.
- Naturalness: 핏, 주름, 관절, 접힘, 광원.
- Defect Severity: 손·팔·옷 경계, 왜곡, 중복 부위, 텍스트 오류.
- Operational: 성공률, 지연, timeout, 재시도.
- Economics: 공급자 원가 + 후처리 + 검수 인건비 + 저장/전송.
- Rights/Policy: 입력 권리, 공급자 상업 이용, 보존·학습·지역 정책.

---

## 6. 사업·마케팅 실행 체계

### 6.1 고객 검증

파일럿 판매 전 인터뷰에서 다음을 수집한다.
- 월간 SKU 수와 신규 상품 등록 빈도.
- SKU당 필요한 이미지 유형/각도/모델 컷 수.
- 현재 촬영/편집 비용, 리드타임, 외주 비중.
- 브랜드 가이드와 제품 디테일 승인 기준.
- 반려/재작업의 주요 원인.
- 모델/인물 이미지 사용 권리와 AI 사용 허용 조건.
- 담당자·승인자·예산 보유자.
- 파일럿 범위와 지불 의사.

초기 활동량은 가설로 둔다: 100개 타깃 계정 리스트, 주 20~25건 개인화 접촉, 주 3~5회 상담, 주 2~3회 데모, 주 1~2건 파일럿 제안. 90일 목표 3~5개 유료 고객은 목표 가설이지 실적이나 보장치가 아니다.

### 6.2 채널 역할

- LinkedIn: B2B 의사결정자·파트너.
- Instagram: 시각 결과와 전후 비교.
- YouTube: 제작 과정·사용법·신뢰.
- TikTok: 짧은 변환 데모.
- Pinterest: 룩북·스타일 탐색 유입.
- Reddit/Discord: 사용자 문제·커뮤니티 검증(스팸 금지).
- SEO/가이드: 품질 평가, 상품 콘텐츠, 가상착장 실무.
- 직접 영업/파트너: 첫 유료 파일럿의 핵심.

콘텐츠 믹스 가설: 실제 결과 40%, 데모 25%, 실무 정보 20%, 회사/비전 15%. 실제 기능이 아닌 콘셉트 화면은 반드시 예시로 표시한다.

### 6.3 퍼널 및 KPI

`콘텐츠/검색/파트너 → 랜딩 → 데모/상담 → 유료 파일럿 → 반복 계약`

핵심 KPI:
- 방문→문의 전환율, 문의→상담, 상담→파일럿, 파일럿→반복 계약.
- 첫 프로젝트 생성률, 첫 결과 성공률, 승인률, 재시도율, SKU당 제작 시간.
- 고객당 실제 원가, 공헌이익, 지원 시간, 환불률.
- 30일 재사용, 구독 유지, 고객 추천.
- 국가별로 분리 집계하며 합산 지표로 특정 국가의 저성과를 감추지 않는다.

### 6.4 예산 가이드(비율 제안, 총액 미승인)

- 35% 제품/API/품질 검증.
- 25% 파일럿 제작·온보딩.
- 15% 직접 영업·파트너.
- 10% 콘텐츠·사례 제작.
- 10% 유료 광고(실제 성과 증거 확보 후).
- 5% 법률·권리 예비비.

총예산, 현금흐름, 공급자 API 지출 한도는 제품 책임자가 별도로 승인해야 한다.

---

## 7. 법률·권리·보안 기준

이 절은 법률 자문이 아니라 출시 전 검토 항목이다. GDPR, EU AI Act, 개인정보 국외 이전, 저작권·초상/퍼블리시티권, 상표, 소비자·전자상거래, 결제·세금은 실제 판매 국가와 서비스 역할에 맞춰 전문가 검토가 필요하다.

### 7.1 입력/인물/브랜드 권리
- 고객은 업로드한 이미지·인물·상품·로고를 사용할 권한을 보유/허락받았음을 확인.
- 타인의 얼굴·인물 이미지는 명시적 허가와 목적·기간·지역·매체 범위를 기록.
- 공급자에게 전송되는 입력과 보존·학습 사용 조건을 작업 전 안내.
- 고객 자산은 기본 비공개이며 별도 동의 없이 학습·공개·Marketplace 등록하지 않음.
- 생성 결과의 독점 저작권·재판매 권리를 보장하지 않음.

### 7.2 공급자 레지스트리 필수 필드
- API/모델 버전, 작업 capability, 입력·출력 제약.
- 가격 단위, 과금 이벤트, timeout/재시도 정책.
- 상업 이용 허용 범위.
- 입력/출력 보존 기간, 모델 학습 사용 여부, 삭제 절차.
- 처리 지역·하위 처리자·국외 이전 근거.
- 콘텐츠 안전/금지 입력 정책.
- 계약/약관 확인 일자와 담당자.

### 7.3 Marketplace 권리 통제
판매자 검증, provenance, 라이선스 범위, AI 생성 고지, 귀속, 신고·삭제, 분쟁·환불, 정산·세금·지급보류, 라이선스 철회와 구매자 권리 처리를 구현하기 전에는 공개 거래를 시작하지 않는다.

### 7.4 보안
- Tenant isolation은 모든 서버 API에서 검증.
- Secret Manager/KMS로 공급자 키 관리.
- 고객 콘텐츠의 기본 최소 권한, 운영자 접근 감사.
- 파일 업로드 검증, signed URL 만료, rate limit, abuse control.
- 암호화, 로그 비식별화, 보존/삭제 정책, 백업 복구 절차.
- 공급자 호출과 외부 전송 기록, 요청 ID/Job ID 추적.

---

## 8. 3자 협업 및 변경 통제

### 8.1 역할

**제품 책임자(사용자)**
- 비전·시장·우선순위·예산·정책·최종 제품 승인.
- 주요 범위·가격·국가·법률/데이터 정책 승인.

**개발자(Technical Lead / Implementation Owner)**
- 저장소 감사, 기술 타당성, 아키텍처 공동 설계, 코드/API/DB/인프라/테스트/배포.
- PR/commit, 실행 로그, 테스트 결과, 배포/운영 증거 제출.

**ChatGPT(통합 PM/BA/QA 지원)**
- 문서 기준선, 요구사항 추적, 충돌 분석, 명세 초안, 테스트 설계, 코드/증거 검토, 사업·마케팅 정합성.
- 실제 개발자 저장소에 접근하거나 개발자에게 전달하지 못한 작업을 완료했다고 주장하지 않음.

### 8.2 변경 요청 절차

1. 요구사항/UI/API/DB/데이터 처리/가격/법률 정책 변경은 Change Request로 기록.
2. 개발자가 기술·일정·비용·운영 영향 분석.
3. ChatGPT가 사용자 흐름·요구사항 추적·문서 영향 분석.
4. 제품 책임자가 범위·예산·제품 영향 승인.
5. 문서·코드·테스트 버전을 함께 갱신.
6. 기존 문서는 삭제하지 않고 Superseded 표시.

### 8.3 작업 카드 필수 필드

`Work ID / Owner / Contributors / Approver / Inputs / Outputs / Acceptance Criteria / Dependencies / Status / Evidence / Risks`

기술 설계는 개발자가 기술 책임자로서 공동 작성한다. ChatGPT가 코드·저장소 검증 없이 기술 결정을 단독 확정하지 않는다.

---

## 9. 통합 의사결정 레지스터

| ID | 결정 항목 | 현재 통합 기준 | 확정에 필요한 근거/담당 |
|---|---|---|---|
| D-01 | 글로벌 전략 | Global-first 제품, 단계적 국가 GTM | 제품 책임자 승인 |
| D-02 | 초기 상업 분야 | 패션·의류 이커머스 | 유료 고객 인터뷰/파일럿 |
| D-03 | 첫 유료 제안 | 브랜드별 AI 룩북/상품 콘텐츠 파일럿 | 원가·품질 실측 후 가격 승인 |
| D-04 | 3D 우선순위 | Viewer/Scene Editor 초기 핵심 검증 | 개발자 G0/G1 증거 |
| D-05 | 3D 의상 시뮬레이션 | Viewer와 별도 R&D | 별도 PoC/예산 승인 |
| D-06 | Try-on 방식 | 이미지 기반 Provider pipeline | 실제 Provider PoC |
| D-07 | Photo Engine | 별도 2D 후처리 파이프라인 | 품질 PoC |
| D-08 | API Prefix | 미확정(`/v1` vs `/api/v1`) | 기존 저장소/API client 확인, 개발자 제안 |
| D-09 | Tenant DB | Organization/Membership/Workspace 보존 | 실제 DB/ORM/migration 확인 |
| D-10 | 범용 Job | 공통 Generation Job + 기능별 payload | 기존 API/14개 테스트 대조 |
| D-11 | Provider 선택 | hard filters 후 scoring; MANUAL silent fallback 금지 | 공급자 계약·실측 |
| D-12 | Credit | append-only ledger; reserve/capture/release/refund/adjust | 원장 동시성 테스트 |
| D-13 | 초기 결제 | 테스트 크레딧; PG 자동화는 이후 | 파일럿 운영·국가별 결제 검토 |
| D-14 | Marketplace | 권리·정산·분쟁 준비 전 공개 금지 | 법률·세무·운영 설계 |
| D-15 | Website coding | 별도 지시 전 보류 | 제품 책임자 별도 범위 승인 |
| D-16 | Video | 후속 파이프라인 | 기술·비용·권리 PoC 및 승인 |

---

## 10. 리스크와 대응

| 위험 | 영향 | 대응/통제 | 책임 |
|---|---|---|---|
| 기존 코드 상태 불명 | 재개발·일정 낭비 | G0 실행 감사, 재사용 근거 | 개발자 |
| 문서/API 불일치 | 통합 실패 | API/DB baseline freeze 전 diff | 개발자 + ChatGPT |
| 제품 범위 과대 | MVP 지연 | G0~G4 수직 슬라이스 우선 | 제품 책임자 |
| Try-on 품질 미달 | 고객 승인 실패 | 동일 입력 블라인드 PoC, 기준선 | 개발자 + 제품 책임자 |
| Provider 정책 변경 | 데이터/비용/권리 리스크 | Registry, 계약 확인일, 대체 Adapter | 개발자 |
| Timeout 중복 과금 | 손실·신뢰 하락 | Provider request ID, 상태 확인, idempotency | 개발자 |
| 결과 저장 전 성공 처리 | 데이터 유실 | persist-before-success 불변조건 | 개발자 |
| 인물/상품 권리 분쟁 | 법적·평판 리스크 | 권리 선언·동의·삭제 절차 | 제품 책임자 + 법률 전문가 |
| 국가별 결제/데이터 차이 | 출시 제한 | 국가별 readiness gate | 제품 책임자 |
| Marketplace 악용 | IP/정산 분쟁 | 판매자 검증·신고·분쟁·payout controls | 제품 책임자 + 개발자 |
| 허위 마케팅 주장 | 신뢰·법적 리스크 | 실측 근거 없는 ROI/성능 보장 금지 | 제품 책임자 + ChatGPT |

---

## 11. 현 상태와 증거의 경계

현재 확인된 문서 기준으로는 제품 방향·상위 아키텍처·초기 사용자 흐름·PoC 설계·개발자 착수 초안·마케팅/글로벌 계획이 존재한다. UI 프로토타입은 미리보기 승인 기록이 있으나, 실제 서비스 통합 완료를 의미하지 않는다.

현재 확인 가능한 자료만으로 다음을 완료라고 선언할 수 없다.
- 실제 저장소/브랜치/커밋 감사.
- FastAPI Mock의 현재 코드·테스트 재현.
- Three.js Viewer의 실제 GLB 실행 및 씬 저장/복원.
- 실제 FASHN 또는 다른 Provider API 호출과 결과/원가 측정.
- DB/Auth/Storage/Queue의 운영 통합.
- 공통 Job/Credit/Review/Export E2E.
- Photo Engine 실측 품질.
- 유료 고객 확보·반복 사용·고객 승인 사례.
- 글로벌 결제·법률·데이터 정책의 국가별 출시 준비.

이는 해당 구현이 없다는 뜻이 아니라, 현재 검토 가능한 문서에서 검증 증거를 확인하지 못했다는 뜻이다. 실행 증거가 들어오면 이 문서의 상태를 갱신한다.

---

## 12. 다음 실행 기준

실제 실행의 첫 작업은 **WP-00 저장소 감사**다. 이는 새로운 기능 개발 지시가 아니라 기존 산출물을 보존하고 재사용 여부를 확인하는 작업이다. 감사 결과가 확보되면 API prefix, Tenant DB, Job state, Asset relation, Identity Profile, Credit ledger를 실제 코드와 대조해 기준선을 확정한다.

그 다음 G1 3D Viewer와 G2 실제 Try-on PoC를 독립적으로 증명하고, G3에서 공통 업무 흐름으로 통합한다. Photo Engine, 유료 파일럿, 국가별 출시, Marketplace는 각 Gate의 증거와 승인 조건을 통과한 뒤 진행한다.

### Gate 완료 정의

Gate는 문서 작성 또는 코드 작성만으로 통과하지 않는다. 다음 네 가지가 모두 필요하다.
1. 요구사항과 구현 범위가 추적 가능할 것.
2. 재현 가능한 실행 환경/버전이 기록될 것.
3. 합격 기준에 대한 테스트 결과가 있을 것.
4. 결과 파일·로그·캡처·PR/commit 등 객관적 증거가 연결될 것.

---

## 부록 A. 문서 기준선과 상호 관계

| 문서 | 역할 | 이 통합 기준에서의 사용 |
|---|---|---|
| 개발자 기술검토 보고서 v1 | 기술·보안·운영 원칙 | 모듈형 모놀리스, Adapter, Job, Ledger, tenant isolation |
| 개발자 착수명세서 v0.1 | API/DB/상태/테스트 상세 원본 | Organization/Membership, 범용 Generation, 원본 테스트 시나리오 보존 |
| 기술 아키텍처 v0.2 | 3D/Try-on/Photo/Video 경계 | 초기 기술 구조 및 3D Viewer 검증 |
| 개발자 착수명세서 v0.2 | 확장 구현 제안 초안 | 참조하되 누락/충돌 수정 전 최종 기준으로 사용 금지 |
| Try-on PoC 실행 패키지 v0.2 | 실측 절차 | 동일 입력, 블라인드 평가, 품질·원가·권리 검증 |
| B2B 홈페이지 v3 | 고객 진입/업무 UX | 자산 중심 업무 진입 |
| 글로벌 통합 마스터 플랜 v0.1 | 사업·제품·Gate·협업 | Global-first 및 G0~G5 순서 |
| 글로벌 디지털 마케팅 전략 v0.1 | 채널·국가별 KPI | 가설/계획으로 사용, 실적과 구분 |
| 개발자 자료/설계도 검토 v0.1 | 문서 충돌 및 v0.2 패키지 결함 | 기존 자료 우선 보존 및 수정 목록 |

## 부록 B. 버전 관리 원칙

- 파일명 버전과 본문 버전, 작성일, 상태, 상위 문서, 승인 여부를 별도 관리.
- Draft / Under Technical Review / Pending PO Approval / Approved Baseline / Superseded 상태를 명시.
- 승인 전 초안은 개발 지시의 최종 기준이 아님.
- 요구사항 ID와 테스트 ID는 개정 사이에 추적성을 유지.
- 중요한 변경은 Change Request로 기록하고 기존 문서 삭제 대신 superseded 처리.
