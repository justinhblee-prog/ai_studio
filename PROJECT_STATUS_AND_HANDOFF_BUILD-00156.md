# AI CREATOR STUDIO — 전체 프로젝트 현황 및 인수인계 기준

- 최신 소스 빌드: **BUILD-00156**
- 기준일: 2026-11-04
- 패키지 목적: 실제 확보된 최신 소스 코드 + 제품/사업 설계 + 기술 기준 + 검증 증거 + 다음 작업 인수인계
- 문서의 판정 원칙: 설계 문서 존재, 소스 코드 존재, 자동화 테스트 통과, 실환경 검증 통과를 서로 다른 상태로 기록한다.

> **중요한 범위 고지:** 이 패키지는 현재 확보된 BUILD-00156 저장소 아카이브를 기반으로 합니다. 아카이브에서 실제 소스가 확인되는 주요 실행 모듈은 `ai_creator_studio_backend_starter/`와 `ai_creator_studio_3d_viewer/`입니다. 제품 설계에 등장하는 모든 기능(예: 전체 Character Studio, 실제 AI Try-on Provider, Photo AI Engine, Video Pipeline, Marketplace, Billing 등)의 완전한 구현 소스가 이 ZIP에 모두 들어 있다고 주장하지 않습니다. 설계·요구사항 문서는 포함하지만, 구현 여부는 아래 상태표와 저장소 증거를 기준으로 판단해야 합니다.

## 1. 제품 정의 및 사업 방향

AI CREATOR STUDIO는 인물·상품·브랜드 자산을 활용해 AI 비주얼 콘텐츠를 제작하고, 결과물의 품질·비용·권리·승인·버전을 관리하는 크리에이티브 운영 플랫폼을 목표로 합니다. 장기 제품 축은 다음과 같습니다.

- **Studio:** 사진 편집, 캐릭터 제작, 3D Studio, 가상 착장, Photo Engine, Lookbook/Campaign, 추후 Video.
- **Business:** Organization/Workspace, Project/SKU/Asset, Brand Kit, 반복·대량 제작, Review/Approval, Export.
- **Marketplace:** 캐릭터·모델·프리셋·템플릿·3D 에셋·콘텐츠의 권리 기반 등록·거래·라이선스·정산.

통합 실행 기준서의 초기 상업 진입 가설은 패션·의류 이커머스 B2B의 브랜드별 AI 룩북/상품 콘텐츠 파일럿입니다. 글로벌-ready 설계는 목표이며, 국가별 시장 진입 순위나 유료 사업성은 아직 검증 완료로 보지 않습니다.

## 2. 제품의 주요 사용자 흐름

1. 기존 사진 편집: 원본 업로드 → 편집 목적 선택 → 부분 변경/배경/의상/조명 조정 → 원본 대비 → 버전 저장.
2. 상품 콘텐츠: 상품 이미지/SKU → 배경·연출·규격화 → 검수 → 채널별 출력.
3. AI 모델/캐릭터: 기준 이미지 또는 외형 설정 → Character Identity Profile → 기준 버전/참조 에셋 관리 → 재사용.
4. 가상 착장/룩북: 의류 이미지 + 인물 참조 → Provider 실행 → 결과 영속화 → 품질 검수 → 룩북 조립.
5. 기업 운영: Workspace/Project/SKU → Asset/Version → Quote/Credit → Job/Execution → Review/Approval → Export.

위 흐름은 제품 목표입니다. 실제 구현 범위는 현재 기능 상태 표와 각 모듈의 테스트 증거를 확인하십시오.

## 3. 실제 소스 트리 및 포함 범위

### Backend — `ai_creator_studio_backend_starter/`
- FastAPI 기반 애플리케이션, API/도메인·저장소 계층, Worker/스크립트, 테스트, 로컬 출력·자산 디렉터리가 포함됩니다.
- BUILD-00156의 전체 Backend pytest 실행 증거는 367 passed입니다.
- 현재 소스 범위는 SQLite 기반 PoC 및 로컬 어댑터 경계를 포함합니다. PostgreSQL 운영 런타임/다중 호스트 검증 완료로 해석하면 안 됩니다.

### Viewer / Client — `ai_creator_studio_3d_viewer/`
- React/TypeScript 작업공간과 Three.js 기반 3D Viewer, 프로젝트·상품 카탈로그·Photo Draft·Lookbook·Asset/Output Review UI, 리소스 정리 및 다운로드 유틸리티가 포함됩니다.
- GLB/GLTF 인증 로딩, bounded download, URL base resolution, Object URL, cleanup lifecycle의 런타임·구조 테스트가 포함됩니다.
- 실제 React/Three 브라우저 E2E 및 시각적 GLB 렌더링은 미검증입니다.

### Docs — `docs/`
- 제품 기준 자료, 공통 데이터 모델 사전, Backend 구현 청사진, OpenAPI 통합 초안, 요구사항 추적 매트릭스, 릴리스·검증·인수인계 기록, 과거 문서 스냅샷이 포함됩니다.
- `docs/project-design/imported-reference/`에는 통합 사업·제품·아키텍처 초안 및 이전 인수인계 기준 문서를 원본 버전명으로 보존했습니다. 해당 문서들은 승인된 최종 기준이라고 단정하지 않습니다.

## 4. 모듈별 상태 판정

| 모듈 | 현재 판단 | 근거/경계 |
|---|---|---|
| Backend API 및 핵심 도메인 | 부분 구현 | 실제 FastAPI 소스 및 pytest 367 통과. 전체 제품 흐름 완성 의미 아님 |
| Project 관리 | 구현된 범위 있음 | Workspace 범위 CRUD/상태 및 lifecycle 관련 테스트 |
| Asset/AssetVersion | 부분 구현 | 로컬 PoC, 인증된 미리보기, 버전/복원 경계. 운영 Object Storage 미검증 |
| Product Catalog / SKU / Variant | 부분 구현 | SKU·Variant 및 이미지 참조/옵션 관련 소스·테스트 |
| Photo Draft | 제한 구현 | 비청구형 로컬 Pillow 처리·불변 파생 결과. AI 이미지 생성/Provider 실행 아님 |
| Output Review | 제한 구현 | 저장된 결과의 미리보기·검수 상태. 게시/상업권 부여 아님 |
| Lookbook Planning | 부분 구현 | Product/Variant 선택, planning review/manifest |
| Lookbook Output Assembly | 부분 구현 | 승인된 Photo output 버전 연결, 페이지 구성, 내부 ZIP/manifest, export history |
| 3D Viewer | 코드 구현 및 내부 자동화 검증 | GLB/GLTF 처리·cleanup. 실제 React/Three E2E 미검증 |
| Character Studio / Character DNA | 설계 및 제품 기준 존재 | 전체 통합 UI/실제 생성 파이프라인 완성 증거 부족 |
| Character Catalog | 설계·레퍼런스 제작 기준 존재 | 얼굴/눈/눈썹/코/입술/피부/헤어/체형/의상 등 전체 카탈로그 연결 검증 필요 |
| 3D Scene Editor | 부분/미확인 | Viewer와 씬 편집·저장/복원 전체 기능은 별도 검증 필요 |
| 3D Garment Simulation | R&D/미구현 범위 | 패턴·리깅·충돌·천 물리. Viewer와 별도 |
| AI Virtual Try-on | 검증 대기 | 실제 Provider 호출·품질·비용·권리 증거 없음 |
| AI Photo Engine | 미검증 | 현재 Photo Draft의 로컬 Pillow 처리와 AI Photo Engine을 혼동 금지 |
| AI Provider Hub / Routing | 설계 및 일부 경계 코드 확인 필요 | 실제 Provider capability/정책/비용 라우팅 운영 검증 미완료 |
| Video Pipeline | 후속 단계 | 실행 가능한 완성 소스/실환경 증거 미확인 |
| Credit Ledger / Billing | 운영 준비 미완료 | 테스트/설계와 실제 과금·결제 분리. 실결제 미검증 |
| Review / Approval | 일부 기능 | Photo/Lookbook 내부 검수와 기업 전사 승인 워크플로 구분 |
| Marketplace | 미구현/출시 금지 상태 | Listing/License/Refund/Dispute/Payout/Tax 운영 시스템 및 법무 검증 필요 |
| Public Website | 설계 단계/별도 범위 | 공개 웹 구현은 별도 승인 범위 |
| Android | 미검증 | 네이티브 앱·실기기 검증 미완료 |
| Production Operations | 미검증 | 운영 Secrets, RBAC, Storage, DB, 배포·모니터링 미완료 |

## 5. BUILD-00156 검증 결과

- Backend full pytest: **367 passed** (완료된 전체 실행 1회). 별도 중복 실행은 시간 초과했으며 통과로 계산하지 않음.
- Viewer lifecycle integration: **32 assertions**.
- Cleanup helper: **10 runtime assertions**; lifecycle structural **13/13**; diagnostic integration **4/4**.
- GLTF disposal: **33 assertions**; authenticated GLTF **15/15**.
- Bounded download: **17 runtime / 19 structural**.
- Model base path **10/10**; authenticated preview Object URL **5**; RequestScopeGate **7**; KeyedRequestGate **7**; project lifecycle **4**; Lookbook links **12**; Lookbook recovery **19/19**.
- Viewer API contract **63/63**; request body contract **15 checked / 0 findings**; response contract **50 JSON / 52 total endpoints / 28 models / 0 missing**.
- Offline structural validation **143**; TypeScript syntax **10 source + 10 declarations / 0 syntax errors**; package integrity **0 findings**; Python compileall passed.
- Chromium WebGL2 capability smoke passed under Xvfb/SwiftShader. 이것은 React/Three Viewer나 GLTF 실제 화면 렌더링 E2E가 아닙니다.
- Semantic TypeScript typecheck: **BLOCKED** — React/Three/addons/type declarations 미설치. 의존성 설치·lockfile 변경 없음.

세부 수치는 `BUILD-00156_VERIFICATION.md` 및 `BUILD-00156_CLEAN_EXTRACT_VERIFICATION.md`를 우선 참조하십시오.

## 6. 알려진 미완료·차단 항목

1. React/Three 실제 브라우저 컴포넌트 E2E와 실제 GLB/GLTF 시각 렌더링.
2. 신뢰 가능한 고정 버전 의존성 확보 후 semantic TypeScript typecheck.
3. 대용량 GLB 및 목표 디바이스 메모리·성능 프로파일링.
4. 외부 glTF buffer/image URI 및 multi-file GLTF import.
5. PostgreSQL 런타임, 동시성, 다중 호스트, cutover.
6. 운영 Object Storage/CDN, Secrets/KMS, RBAC 및 관측성.
7. 실제 AI Provider 호출, Try-on/Photo 품질·원가·지연·정책 검증.
8. 실사용 크레딧 원장, 결제·환불·세금.
9. Android, 공개 게시, Marketplace 라이선스·정산, 운영 배포.
10. 고객 인터뷰·유료 파일럿·글로벌 국가별 사업성.

## 7. G0~G5 제품 검증 Gate

| Gate | 목적 | 현재 판정 |
|---|---|---|
| G0 | 기존 저장소/UI/Mock/3D 재현 및 재사용 감사 | 기준 자료는 있으나 전체 증거 패키지/commit 추적 재확인 필요 |
| G1 | GLB 3개 이상, Viewer 조작, Scene 저장/복원 | Viewer 코드·자동화 테스트 일부 존재. 제품 Gate 완전 통과 증거 아님 |
| G2 | 실제 Try-on Provider 호출 및 품질/비용/권리 | 미검증 |
| G3 | Project/Asset/Job/Output/Credit 수직 통합 | 부분 구현은 있으나 전체 E2E 미검증 |
| G4 | 독립 Photo Engine 품질 검증 | 미검증 |
| G5 | 유료 파일럿·국가별 사업 준비 | 미검증 |

Gate 계획서의 존재는 Gate 통과가 아닙니다. 실제 commit, 실행 로그, 결과물, 비용 및 권리 증거를 기준으로 판정합니다.

## 8. 핵심 설계 결정 원칙

- Tenant/Organization/Workspace 소유권·멤버십 관계 보존.
- 원본 Asset은 불변, 파생 결과는 새 AssetVersion으로 기록.
- Character Identity Profile은 버전·참조 Asset과 연결하되 민감 속성의 불필요한 추론/저장 금지.
- 3D Viewer와 3D Garment Simulation, Image-based Try-on, Photo Engine, Video Pipeline은 별도 파이프라인.
- Provider Adapter는 capability/validate/estimate/submit/status/result/cancel/error normalization 계약을 기준으로 설계.
- MANUAL 선택에서 무단 silent fallback 금지. AUTO fallback은 공개된 정책·동의 범위에서만.
- Job과 Execution을 분리하고 이벤트 이력과 결과 영속화 후 성공 처리.
- Credit Ledger는 append-only, idempotent reserve/capture/release/refund/adjust 구조를 목표로 하며 실제 과금은 별도 승인.
- Marketplace 공개는 권리·라이선스·환불·분쟁·정산·세무 검토 전 금지.

## 9. 승인 경계

명시적 승인 전 금지: 유료 Provider/API 호출, 실제 크레딧/결제, 공개 게시, 권리·라이선스 부여, 운영 데이터·스토리지 변경, 배포, 파괴적 DB 마이그레이션, 보안/정책 미해결 상태에서의 기능 활성화. 신뢰할 수 있는 의존성 설치가 lockfile을 바꾸는 경우도 별도 확인합니다.

## 10. 다음 인수인계 작업 — BUILD-00157

1. BUILD-00156 소스 ZIP과 package manifest, scripts, lockfile, dependency state 확인.
2. 실제 Three.js 객체 기반 Renderer/Scene lifecycle 테스트 추가.
3. 공유 geometry/material/texture/render target 소유권과 중복 dispose 정책 검증.
4. renderer teardown, RAF, controls, observer, canvas, context-loss cleanup 검증.
5. React/Three E2E를 실행할 수 없으면 blocked/unverified로 분명히 기록.
6. backend 전체 테스트, viewer tests, API contracts, structural checks, package integrity 재실행.
7. README, CURRENT_HANDOFF, changelog, release, verification, clean extraction, SHA-256 갱신.

## 11. 시작 위치 및 실행 명령

- 저장소 루트: 이 문서가 위치한 `AI_CREATOR_STUDIO_BUILD-00156/`
- Backend: `cd ai_creator_studio_backend_starter && python -m pytest -q tests`
- Viewer: `cd ai_creator_studio_3d_viewer && npm run test:viewer-cleanup`
- Typecheck: `npm run typecheck` (현재는 의존성 미설치로 blocked일 수 있음)
- 세부 Viewer 스크립트는 `ai_creator_studio_3d_viewer/package.json` 참조.

## 12. 문서 우선순위 및 충돌 처리

1. 최신 소스와 BUILD-00156 검증 보고서: 실제 구현·테스트 판정의 우선 근거.
2. `docs/FEATURE_SCOPE_STATUS.md` 및 제품 기준 문서: 구현 범위/제약의 보조 근거. 단, 해당 문서에 과거 빌드 기준일이 있으면 BUILD-00156 검증과 대조.
3. `docs/project-design/imported-reference/`의 통합 계획/사업 초안: 제품 의도와 장기 설계 기준. 승인 전 초안은 현재 구현 명령이나 완료 증거가 아님.
4. 과거 handoff/release snapshots: 변경 이력 참고 전용.

이 문서는 프로젝트 전체 구현 완료를 선언하지 않습니다. 현재 확보된 실제 소스와 증거의 범위를 명시하고, 다음 개발자가 과장 없이 이어갈 수 있도록 작성했습니다.
