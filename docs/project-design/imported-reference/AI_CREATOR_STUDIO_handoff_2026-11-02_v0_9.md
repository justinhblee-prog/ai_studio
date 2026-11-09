# AI CREATOR STUDIO 프로젝트 인수인계 v0.9

- 기준일: 2026-11-02
- 문서 상태: 작업 인수인계 / 미승인
- 이전 인수인계: v0.8

## 1. 고정된 제품·사업 기준
- 글로벌 확장 가능성을 제품·브랜드·데이터·권리·현지화·결제·마켓플레이스 설계의 출발점으로 삼는다.
- 초기 유료 진입은 패션/의류 이커머스 B2B 맞춤형 룩북·상품 콘텐츠 파일럿이다.
- 장기 제품 축은 Studio / Business / Marketplace.
- Character Studio, 3D Viewer, 3D Garment Simulation, Image-based AI Try-on, Photo Engine, Video Pipeline은 서로 다른 기술·검증 범위다.
- Replit 사용 금지. 실제 코드·로그·실행 증거 없이는 구현 완료를 선언하지 않는다.

## 2. 최근 추가 산출물
1. `AI_CREATOR_STUDIO_G2_tryon_provider_validation_plan_v0_1.md`
   - 실제 Provider 호출, 권리 확인 입력 데이터셋, 비동기 Job, 결과 영속화, 블라인드 품질 평가, 원가·지연·정책 검증.
2. `AI_CREATOR_STUDIO_G3_core_integration_validation_plan_v0_1.md`
   - Login부터 Export까지 공통 코어 수직 흐름, tenant isolation, 업로드, Quote/Credit, Job/Execution/Event/Result, idempotency, timeout/retry/cancel, 결과 저장 복구, 원본 T-01~T-14 추적.

## 3. Gate 현황

| 단계 | 상태 | 근거/필요 증거 |
|---|---|---|
| 통합 실행 기준 | 문서 작성 완료 | integrated execution baseline v0.2 |
| G0 감사 기준·증거 패키지 | 준비 완료 | G0 audit and evidence pack v0.1 |
| G0 실제 저장소 감사 | 증거 대기 | 저장소/branch/commit/실행·테스트 로그 |
| G1 3D Viewer 검증 계획 | 준비 완료 | G1 validation plan v0.1 |
| G1 실제 구현·실행 | 대기 | G0 감사 및 GLB 3종 실행 증거 |
| G2 Try-on 검증 계획 | 준비 완료 | G2 validation plan v0.1 |
| G2 실제 Provider 연동 | 증거 대기 | 공식 정책·계정 연결·마스킹 요청/응답·request ID·결과 저장 |
| G3 통합 검증 계획 | 준비 완료 | G3 core integration plan v0.1 |
| G3 실제 통합 테스트 | 대기 | 저장소·DB/API/Queue·Provider E2E 및 QA 로그 |
| G4 Photo Engine | 대기 | 별도 파이프라인 및 품질 비교 증거 |
| G5 유료 파일럿 | 대기 | 고객 승인, 권리·비용·운영·법무 증거 |

## 4. 중요 기준 및 주의사항
- G2: 기준 모델 이미지 1장과 개별 의류 이미지 3~5장. 콜라주를 API 입력으로 사용하지 않는다. 공급자명을 가린 평가로 디자인 보존·착장 자연스러움·모델 일관성·결함·재현성·상품 적합성을 평가한다.
- G2: Provider request ID와 내부 Job/Execution/Result/AssetVersion을 연결한다. timeout은 실패로 단정하지 않고 중복 제출·과금을 막는다.
- G2: 결과 파일 저장과 DB 참조가 끝나기 전에 `SUCCEEDED`로 전환하지 않는다.
- G2: 공급자 상업 이용·데이터 보존/삭제·학습 이용·처리 지역 정책을 확인하기 전 고객 데이터 전송 금지.
- G3: Organization/Membership/Workspace 분리, tenant isolation, idempotency, append-only Credit Ledger, Queue/DB 장애 복구, 결과 저장 실패 복구를 검증한다.
- 원본 개발자 착수명세서 T-01~T-14 ID를 보존한다. 신규 QA ID로 대체하지 않는다.
- API prefix `/v1` 대 `/api/v1`은 저장소 감사 후 결정한다.

## 5. 확인된 사실과 미확인 사실

### 확인된 문서 기준
- G2는 실제 Provider 1개 호출과 Job, 결과 저장, 실제 원가·시간·권리 기록이 필요하다.
- G3는 공통 코어 수직 통합과 권한·상태·중복 요청·실패 복구 테스트가 필요하다.
- 기존 Try-on PoC 설계는 FASHN Try-On v1.6을 후보로, Try-On Max/fal.ai를 비교 후보로 언급했으나 현재 버전·가격·정책·계정은 다시 확인해야 한다.

### 미확인
- 실제 저장소/branch/commit 및 기존 코드 상태
- UI, FastAPI Mock, Three.js/GLB의 현재 실행 상태
- Provider 계정/API 키 연결 및 실제 요청/응답
- 실제 DB/Auth/Storage/Queue 연결
- 결과 파일의 내부 저장 및 AssetVersion 연결
- 품질 점수, 성공률, 지연시간, 실제 비용
- 권리/동의 및 공급자 데이터 정책 검토
- 개발자에게 문서가 실제 전달되었는지 여부

## 6. 다음 작업 순서
1. G0 증거 제출 및 재현 감사가 최우선이다.
2. G0 결과를 기준으로 기존 구현을 재사용/수정/대체 판정한다.
3. G0가 통과되기 전 G1~G3 실구현 Gate는 통과 처리하지 않는다.
4. G1과 G2 실행은 의존성·리소스가 허용될 때 병렬 가능하나, 각 Gate 증거를 별도로 관리한다.
5. G2 결과를 바탕으로 Provider 선택/제외 결정을 기록한다.
6. G3는 실제 공통 코어와 Provider를 연결해 원본 T-01~T-14 및 신규 통합 QA를 실행한다.
7. 이후 G4 Photo Engine, G5 유료 파일럿 준비로 진행한다.

## 7. 사용자와 합의한 작업 방식
- 단계별 완료 시 현황표를 제시한다.
- 완료 여부와 근거를 명확히 구분한다.
- 현황표를 제시한 뒤 다음 가능한 작업을 이어서 수행한다.
- 증거가 없는 실행·개발·전달·배포는 완료라고 말하지 않는다.
- 매 작업 종료 시 handoff 파일을 새 버전으로 갱신한다.
