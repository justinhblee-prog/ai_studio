# AI CREATOR STUDIO — 통합 인수인계 v1.5

- 기준일: 2026-11-02
- 문서 상태: OpenAPI 통합 초안 v0.2 및 내부 검증 반영
- 프로젝트 운영 기준: Global-first, 증거 기반 Gate, 무운영 문서 진행

## 1. 현재 프로젝트 방향

- 초기 유료 진입은 B2B 패션/e-commerce 브랜드 대상 맞춤형 AI 룩북·상품 콘텐츠 파일럿이다.
- 장기 제품 구조는 Studio / Business / Marketplace다.
- 홈페이지 프로토타입 작업은 사용자 요청 전까지 재개하지 않는다.
- Character Studio, 3D Viewer, 3D Garment Simulation, Image-based AI Try-on, Photo Engine은 서로 다른 기능 경계로 유지한다.
- Photo Engine은 독립 2D 파이프라인이며 3D Viewer 스크린샷으로 대체하지 않는다.

## 2. 기준 아키텍처 원칙

- 초기에는 Modular Monolith를 우선 검토하고 API와 Worker는 필요 시 분리한다.
- Provider-neutral Adapter 및 Capability/Policy Registry를 둔다.
- Generation Job은 비동기 처리하고 Execution/Event/Output 이력을 분리한다.
- Output 파일과 DB 참조가 영속화되기 전에는 Job을 SUCCEEDED로 처리하지 않는다.
- Credit Ledger는 RESERVE/CAPTURE/RELEASE/REFUND/ADJUST append-only 구조를 원칙으로 한다.
- Tenant isolation, 업로드 검증, 권리·지역·보존 정책을 공통 기반으로 취급한다.
- 실제 DB/ORM/API 경로와 인증은 저장소 감사 후 확정한다.

## 3. Gate 현황

| Gate | 목적 | 상태 |
|---|---|---|
| G0 | 기존 저장소/UI/Mock/3D 재현 및 재사용 감사 | 증거 대기 |
| G1 | GLB 3개 이상 로드, Viewer 조작, Scene 저장/복원 | 검증 증거 대기 |
| G2 | 실제 Try-on Provider 호출 및 결과/비용/권리 검증 | 미검증 |
| G3 | Project/Asset/Job/Output/Credit 통합 | 미검증 |
| G4 | 독립 Photo Engine 품질 검증 | 미검증 |
| G5 | 유료 파일럿 및 국가별 사업 준비 | 미검증 |

문서 작성 및 내부 정적 검증은 Gate 통과 증거가 아니다. 실제 Commit SHA, 실행 로그, 테스트 리포트가 확보되어야 한다. 저장소에 증거가 없다는 이유만으로 코드가 없다고 단정하지 않는다.

## 4. 기존 QA 테스트 ID

T-01 로그인 및 Organization/Workspace 접근
T-02 정상 이미지 업로드
T-03 MIME/Signature/용량 오류
T-04 타 Organization Asset/Job 접근 차단
T-05 Quote 후 Job 생성
T-06 Credit 부족
T-07 Provider 성공 및 결과 저장
T-08 Idempotency Key 중복 요청
T-09 Provider Timeout 및 결과 불명
T-10 실행 중 취소
T-11 원본/생성 결과 비교
T-12 실패/재시도/Fallback 이력
T-13 DB Commit 후 Queue Publish 전 장애
T-14 Provider 성공 후 결과 저장 실패

ID와 의미를 임의 변경하지 않는다.

## 5. 완료된 기준 문서 및 산출물

### Gate 및 제품 실행
- G0 Audit & Evidence Pack v0.1
- G1 3D Viewer Validation Plan v0.1
- G2 Try-on Provider Validation Plan v0.1
- G3 Core Integration Validation Plan v0.1
- G4 Photo Engine Validation Plan v0.1
- G5 Paid Pilot Validation Plan v0.1
- Requirements Traceability Matrix v1.0

### 데이터/API/QA
- Common Data Model Dictionary v0.1
- API Contract Decision Register v0.1
- API Contract Test Matrix v0.1 (대화 내 WritingBlock)
- OpenAPI 3.x Common Schema & API Structure v0.1 (대화 내 WritingBlock)
- API Contract Automation & CI Validation Specification v0.1 (대화 내 WritingBlock)
- OpenAPI 3.1.0 Draft v0.1
  - Library: `/AI_CREATOR_STUDIO/AI_CREATOR_STUDIO_openapi_draft_v0_1.yaml`
  - Library ID: `libfile_92cc9b3027c881918c13856dc0be4e42`
  - 기존 검증: YAML 파서 통과, Path 8개, Schema 24개
- API Error Code, Idempotency & Failure Recovery Specification v0.1
  - Library: `/AI_CREATOR_STUDIO/AI_CREATOR_STUDIO_API_error_idempotency_recovery_spec_v0_1.md`
  - Library ID: `libfile_ebf8006cbe9881918192040f2d051cbe`
- **OpenAPI Integrated Draft v0.2**
  - Library: `/AI_CREATOR_STUDIO/AI_CREATOR_STUDIO_openapi_integrated_draft_v0_2.yaml`
  - OpenAPI 3.1.0, Path 13개, Schema 37개
  - YAML 파서 PASS, 내부 `$ref` 56개 PASS, Path Parameter PASS, Operation ID 15개 중복 없음
  - 공식 OpenAPI Validator, 서버 코드 정합성, SDK 생성 호환성은 미검증
- **OpenAPI Validation Report v0.2**
  - Library: `/AI_CREATOR_STUDIO/AI_CREATOR_STUDIO_openapi_validation_report_v0_2.md`

## 6. API 설계 핵심 결정 및 미결정

확정 원칙:
- Generic Generation Job + 기능별 Try-on/Photo Input Schema
- Provider Adapter와 AUTO/MANUAL Routing 분리
- MANUAL은 자동 fallback 금지
- Job / Execution / Event / Output 분리
- Credit Ledger append-only 및 Idempotency
- Outbox + 멱등 Consumer를 통한 DB/Queue 정합성
- Provider Timeout은 결과 불명으로 취급하고 확인 전 무조건 재호출하지 않음
- Output 영속화 후 SUCCEEDED

미결정:
- API Prefix `/v1` 또는 `/api/v1` (ADR-API-001, G0 전 확정 금지)
- 인증 방식 및 실제 Security Scheme
- OpenAPI 3.1.x 및 코드 생성 호환성 검증
- ID 물리 포맷
- DTO/OpenAPI 단일 원천
- Event 전달 방식(Polling/SSE/WebSocket)
- Idempotency TTL/Hash 규칙
- Queue/Outbox/Retry/DLQ 구체 구현
- Provider별 상태조회·취소·멱등성 지원
- Credit Ledger amount 부호/표현 규칙
- Asset 업로드 발급·완료 API 상세 계약

## 7. OpenAPI v0.2 주의 사항

- API Prefix는 기존 ADR-API-001에 따라 저장소 감사 전 보류했다. YAML은 prefix 없는 상대 경로를 사용한다.
- 인증 계약이 확인되지 않아 Security Scheme을 임의 선언하지 않았다.
- Tenant 모델(Organization/Membership/Workspace)을 API 경계에서 제거한 것이 아니다. 서버와 Worker가 반드시 권한을 재검증해야 한다.
- LookbookInput은 제안 스키마이며 제품/Provider 검증 전이다.
- `upload_reference` 기반 Asset 등록 계약만 존재하며 실제 업로드 발급/완료 흐름은 별도 보완 대상이다.
- Credit amount 표현과 Idempotency TTL/Hash는 미결정이다.
- 내부 참조 검증은 완료했으나 공식 OpenAPI Validator 및 실제 서버/SDK 정합성은 미실행이다.

## 8. 저장소 및 증거 상태

- 실제 Repository/Branch/Commit SHA 확인: 미완료
- 실제 UI 실행 상태: 미확인
- FastAPI Mock 테스트 로그: 문서상 과거 4개 통과 기록은 있으나 원본 증거 미확인
- Three.js/GLTFLoader/OrbitControls 및 실제 GLB 실행: 미확인
- FASHN 실제 API 호출 및 품질/비용 측정: 미확인
- DB/Auth/Storage/Credit/Payment/배포 통합: 미확인 또는 미완료로 기록
- 사용자의 Termux 저장소는 현재 대화에서 접근 불가. 사용자가 직접 명령을 실행하도록 요구하지 않고 저장소 감사는 별도 협업 입력이 제공될 때 수행한다.

## 9. 무운영 진행 방식

- 사용자가 “다음”, “ㄱㄱ”, “진행해”라고 하면 별도 승인 질문 없이 다음 산출물을 진행한다.
- 중간에 다음 작업 예고만 하고 멈추지 않는다.
- 사용자에게 반복적으로 지시·승인을 요구하지 않는다.
- 실제 실행하지 않은 코드/테스트/배포/업로드를 완료로 표시하지 않는다.
- 가능한 문서 작업은 실제 파일로 생성하고 Library 업로드를 확인한다.
- 작업 세션 종료 시 결정, 산출물, 미결정, 다음 단계, 증거 상태를 handoff에 반영한다.

## 10. 이어지는 실행 백로그

1. DTO/Schema 대응표와 실제 구현 차이 기록 템플릿
2. Job/Execution/Event/Output 상태 전이표 및 동시성 테스트 케이스
3. Credit Ledger 트랜잭션/동시성/보상 테스트 명세
4. Provider Adapter 공통 인터페이스 및 Capability Registry 명세
5. API 보안·Tenant Isolation 테스트 상세화
6. 전체 문서 버전/결정/요구사항 추적성 통합 갱신

각 항목은 저장소 실물 확인 전까지 설계 초안으로 유지한다.

## 11. 변경 이력

| 버전 | 날짜 | 변경 |
|---|---|---|
| v1.5 | 2026-11-02 | OpenAPI 통합 초안 v0.2 및 내부 검증 결과, 미결정 사항, 다음 백로그 반영 |
