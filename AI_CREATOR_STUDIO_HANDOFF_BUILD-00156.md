# AI CREATOR STUDIO — 프로젝트 인수인계 문서

- 기준 빌드: **BUILD-00156**
- 직전 기준: BUILD-00155
- 작성일: 2026-11-04
- 프로젝트: AI CREATOR STUDIO
- 현재 집중 영역: 3D Viewer의 GLTF 리소스 수명주기, 모델 교체, 렌더러 종료 안정성
- 문서 목적: 새 대화·개발 환경·담당자에서 프로젝트를 중단 없이 이어가기 위한 기준 문서

---

## 1. 새 작업 시작 시 반드시 지킬 원칙

1. 최신 기준 소스는 BUILD-00156 압축파일을 독립 경로에 해제한 프로젝트 디렉터리입니다. 이전 빌드 ZIP이나 오래된 대화 내용을 기준으로 작업하지 않습니다.
2. 사용자는 자율 연속 개발을 요청했습니다. 매 단계마다 진행 여부를 묻거나 중간 승인 보고를 하지 말고, 안전한 범위에서 구현·테스트·수정을 이어갑니다.
3. 아래 승인 경계에 해당하는 작업은 사용자 명시 승인 전에는 실행하지 않습니다.
4. 실제 검증하지 않은 기능을 완료로 표시하지 않습니다. 정적 구조 검사, 단위 테스트, 브라우저 기능 스모크, 실제 React/Three 렌더링 E2E를 구분해서 기록합니다.
5. 각 빌드마다 인수인계 문서, 릴리스 노트, 검증 보고서, 빌드 정보, 변경 이력을 함께 갱신합니다. ZIP, SHA-256, 압축 무결성 및 독립 추출 확인도 유지합니다.
6. 사용자는 한국어 존댓말 응답을 선호합니다. 진행 중 메시지는 최소화하고, 의미 있는 작업 단위가 끝났을 때 결과와 산출물을 보고합니다.

## 2. 승인 경계

명시적 승인 없이 다음 작업을 수행하지 않습니다.

- 유료 API, 유료 Provider, 유료 크레딧 사용 또는 실제 과금 발생
- 실제 외부 Provider 호출, 운영 계정 인증정보 또는 비밀정보 사용
- 공개 게시, 사용자 콘텐츠 공개, 권리 부여 또는 라이선스 확정
- 운영 데이터 변경, 운영 스토리지 변경, 배포
- 파괴적 DB 마이그레이션 또는 데이터 삭제
- 보안·개인정보·정책상 미해결 판단을 전제로 한 기능 활성화
- 의존성 설치나 버전 변경이 네트워크·공급망 신뢰 문제를 수반하는 경우

일반적인 로컬 코드 수정, 의존성 없는 테스트 작성, 오프라인 검증, 문서화 및 비파괴적 패키징은 위 경계를 침범하지 않는 범위에서 진행합니다.

## 3. 현재 빌드 요약

### BUILD-00156 — Viewer Lifecycle Integration & Disposal Diagnostics

이번 빌드는 BUILD-00155의 실패 격리형 정리 절차를 기반으로, GLTF 리소스 해제 과정의 오류가 조용히 사라지지 않도록 수명주기 경계에 진단을 연결했습니다.

주요 구현:

- `ai_creator_studio_3d_viewer/src/disposeViewerResources.mjs`
- `ai_creator_studio_3d_viewer/src/disposeViewerResources.d.mts`
- `ai_creator_studio_3d_viewer/scripts/test_viewer_lifecycle_integration.mjs`
- `ai_creator_studio_3d_viewer/package.json`의 Viewer 생명주기 테스트 스크립트 등록
- `Studio3DViewer.tsx`의 모델 교체, 로드된 GLTF 종료, stage 리소스 종료 경로에 진단 전달 연결
- 인증 GLTF 로더 및 소스 구조 검사 기준을 현재 `GLTFLoader.parse`와 `/preview-content` 경로에 맞게 조정

핵심 동작:

- GLTF 리소스 전체에 대해 가능한 해제 작업을 먼저 best-effort로 시도합니다.
- 해제 과정에서 발생한 오류를 요약 진단으로 묶어 수명주기 정리 러너에 전달합니다.
- 정리 러너는 해당 오류를 기록하되 이후 cleanup step을 계속 실행합니다.
- 공유 texture/material/geometry/skeleton, 중첩 scene graph, 모델 교체 및 renderer teardown 순서를 테스트합니다.

변경하지 않은 영역:

- Backend API, DB schema, migration
- Dependency version 및 lockfile
- Provider 호출, 과금/credit
- Publication, rights grant
- Production data, 배포

## 4. 검증 현황

BUILD-00156 검증 보고서에 기록된 결과:

| 검증 영역 | 결과 |
|---|---:|
| Backend 전체 pytest | 367 passed (완료된 전체 실행 1회) |
| Viewer lifecycle integration | 32 assertions passed |
| Viewer cleanup helper | 10 runtime assertions |
| Viewer lifecycle structural | 13/13 |
| Disposal diagnostic integration | 4/4 |
| GLTF disposal regression | 33 assertions |
| Authenticated GLTF lifecycle | 15/15 |
| Bounded download | 17 runtime / 19 structural |
| Model base path | 10/10 |
| Authenticated preview Object URL | 5 |
| RequestScopeGate / KeyedRequestGate | 각 7 |
| Project lifecycle events | 4 |
| Lookbook preview links / recovery | 12 / 19 |
| Viewer API contract | 63/63 |
| Request body contract | 15 checked / 0 findings |
| Response contract | 50 JSON / 52 total endpoints / 28 models / 0 missing |
| Offline source structural validation | 143 checks passed |
| TypeScript syntax/transpilation | 10 source + 10 declaration files / 0 syntax errors |
| Package integrity | 0 findings |
| Python compileall | passed |
| Chromium WebGL2 capability smoke | Xvfb에서 통과 (React/Three E2E 아님) |

주의:

- Backend 전체 pytest는 367개 통과한 완료 실행이 증거입니다. 별도 중복 실행은 약 42% 지점에서 시간 초과되었으며 테스트 실패를 보고하지 않았습니다. 시간 초과 실행을 통과로 계산하지 않습니다.
- `npm run typecheck`는 React, Three.js, `three/addons/*` 및 관련 타입 선언이 설치되어 있지 않아 BLOCKED입니다. 의존성을 임의 설치하거나 lockfile을 바꾸지 않았습니다.
- WebGL2 스모크는 브라우저의 WebGL2/셰이더/ResizeObserver/animation frame 기능만 확인합니다. React/Three Viewer 컴포넌트나 GLTF 모델을 로드한 실제 렌더링 테스트가 아닙니다.
- 독립 추출 검증은 Viewer·계약·구조·패키지 검증을 수행했습니다. Backend clean-extract 전체 재실행은 완료 증거로 주장하지 않습니다.

자세한 결과는 `BUILD-00156_VERIFICATION.md`, `BUILD-00156_CLEAN_EXTRACT_VERIFICATION.md`, `BUILD-00156_TYPECHECK_BLOCKER.md`를 확인합니다.

## 5. 알려진 미완료 및 위험 항목

1. React/Three 실제 컴포넌트 브라우저 E2E 및 GLB/GLTF 화면 렌더링 미검증
2. 신뢰 가능한 React/Three 의존성이 준비되지 않아 semantic TypeScript typecheck 차단
3. 대표 대형 모델과 실제 타깃 디바이스에서 메모리 사용량/누수 프로파일링 미실시
4. 외부 glTF buffer/image URI는 거부하며 다중 파일 glTF import 미구현
5. PostgreSQL 실제 런타임 및 multi-host 동작 미검증
6. Android 실기기 검증 미완료
7. 운영 object storage, secrets, RBAC 설정 검증 미완료
8. Live Provider, credit charging, publication, rights grant, production deployment 미실행 및 미검증

위 항목은 완료로 표현하지 말고 후속 검증 대상으로 유지합니다.

## 6. 프로젝트 구조 및 주요 위치

- `ai_creator_studio_backend_starter/` — Backend 애플리케이션 및 테스트
- `ai_creator_studio_3d_viewer/` — Viewer UI, 3D 리소스 관리, 브라우저 측 테스트
- `docs/` — 프로젝트 문서, 기능 범위, 버전 정책, 변경 이력 및 인수인계
- `BUILD-00156_VERIFICATION.md` — 이번 빌드 검증 결과
- `BUILD-00156_RELEASE_NOTES.md` — 이번 빌드 변경 요약
- `BUILD-00156_TYPECHECK_BLOCKER.md` — 타입 검사 차단 사유
- `BUILD-00156_CLEAN_EXTRACT_VERIFICATION.md` — ZIP 독립 추출 검증
- `BUILD_INFO.md` — 현재 빌드 메타데이터
- `CURRENT_HANDOFF_BUILD-00156.md` — 간략한 현재 인수인계
- `AI_CREATOR_STUDIO_HANDOFF_BUILD-00156.md` — 본 상세 인수인계 문서
- `docs/handoff/CURRENT_HANDOFF.md` — canonical handoff 경로

Viewer의 핵심 수명주기 파일:

- `src/Studio3DViewer.tsx`
- `src/disposeGltfResources.mjs` 및 `.d.mts`
- `src/disposeViewerResources.mjs` 및 `.d.mts`
- `src/runViewerCleanupSteps.mjs` 및 `.d.mts`
- `scripts/test_dispose_gltf_resources.mjs`
- `scripts/test_viewer_cleanup_steps.mjs`
- `scripts/test_viewer_cleanup_lifecycle.py`
- `scripts/test_viewer_lifecycle_integration.mjs`

## 7. 재현 가능한 주요 테스트 명령

Viewer 프로젝트 디렉터리로 이동한 뒤 실행합니다.

```bash
cd ai_creator_studio_3d_viewer

# 통합 cleanup runner: runtime + structural + lifecycle integration
npm run test:viewer-cleanup

# GLTF 리소스 해제 회귀
npm run test:dispose-gltf-resources

# 인증 GLTF 로딩 계약
npm run test:authenticated-gltf-loading

# bounded download runtime 및 structural
npm run test:bounded-gltf-download-runtime
npm run test:bounded-gltf-download

# 계약/소스/패키지 검증
npm run validate:api-contract
npm run validate:request-contract
npm run test:request-contract
npm run validate:response-contract
npm run validate:syntax
npm run validate:package-integrity

# 의미론적 TypeScript 검사: 의존성 준비 여부에 따라 BLOCKED일 수 있음
npm run typecheck
```

Backend 전체 테스트는 저장소 루트가 아니라 다음 경로/명령을 사용합니다.

```bash
cd ai_creator_studio_backend_starter
python -m pytest -q tests
```

주의: Viewer의 일부 Python 테스트 스크립트는 pytest collection 시 독립 실행을 시도할 수 있습니다. Backend 전체 pytest를 실행할 때 반드시 `ai_creator_studio_backend_starter` 디렉터리의 `tests`만 지정합니다.

Chromium capability smoke는 X server가 필요하므로 다음 형태로 실행합니다.

```bash
cd ai_creator_studio_3d_viewer
xvfb-run -a python scripts/probe_browser_runtime.py
```

## 8. 다음 작업 권장 — BUILD-00157

### 목표
실제 Three.js renderer 및 scene 객체를 포함하는 통합 검증을 도입하고, 현재 의존성 없는 lifecycle harness와 실제 렌더러 자원 해제 사이의 간극을 줄입니다.

### 권장 진행 순서

1. 현재 설치된 환경에서 Three.js/React 패키지와 lockfile, package manager 상태를 재확인합니다. 네트워크 접근이나 새 패키지 설치가 필요하면 승인 경계를 확인합니다.
2. 기존 cleanup helper와 `disposeViewerResources` 계약을 분석하고, 테스트용 renderer/scene/geometry/material/texture의 최소 fixture를 설계합니다.
3. 신뢰 가능한 이미 설치된 Three.js가 있으면 실제 객체의 dispose 호출, 공유 리소스 deduplication, renderer teardown 순서를 검증합니다.
4. 의존성이 없으면 fake/mock 기반 테스트를 실제 Three.js E2E로 오인하지 않도록 분리하고, blocker를 기록한 뒤 의존성 없는 추가 검증을 진행합니다.
5. React/Three 컴포넌트 브라우저 E2E는 최소 GLB 및 data-URI GLTF fixture를 사용하되, 실제 모델 로딩·렌더링·교체·unmount까지 관찰 가능한 검증으로 설계합니다.
6. 전체 회귀 테스트, source validation, package integrity, ZIP CRC, SHA-256 및 clean extraction을 실행합니다.
7. BUILD-00157 인수인계·릴리스 노트·검증 보고서·빌드 정보를 갱신합니다.

### BUILD-00157 완료 기준

- 실제 Three.js 객체를 사용한 검증과 dependency-free harness를 명확히 구분
- 모델 교체와 unmount/renderer teardown 후 리소스 dispose 동작 확인
- 하나의 리소스 해제 실패가 나머지 cleanup을 중단시키지 않음을 확인
- 실행한 테스트와 실행하지 못한 테스트를 구분해 기록
- 승인 경계 침범 없음

## 9. 버전 히스토리 — 최근 Viewer 작업

- BUILD-00148: Bounded GLTF Download Memory & Header Validation
- BUILD-00149: Unknown-Length GLTF Buffer Growth Hardening
- BUILD-00150: Final GLTF Buffer Trim Failure Handling
- BUILD-00151: Relative GLTF Model URL Base Resolution
- BUILD-00152: Complete GLTF Resource Lifecycle Disposal
- BUILD-00153: Viewer GPU Resource Lifecycle Completion
- BUILD-00154: Failure-Resilient GLTF Resource Disposal
- BUILD-00155: Viewer Renderer Teardown Resilience
- BUILD-00156: Viewer Lifecycle Integration & Disposal Diagnostics

## 10. 인수인계 완료 체크리스트

- [x] 최신 기준 빌드 및 부모 빌드 명시
- [x] 이번 빌드의 변경 범위 및 핵심 파일 기록
- [x] 검증 결과와 제한 사항 구분
- [x] 승인 경계 기록
- [x] 주요 테스트 실행 명령 기록
- [x] 다음 빌드 목표 및 완료 기준 기록
- [x] ZIP/체크섬/검증 문서 위치 기록

---

## 다음 대화에서 사용할 시작 지시문

> AI CREATOR STUDIO 프로젝트를 BUILD-00156 기준으로 이어서 진행합니다. 먼저 `AI_CREATOR_STUDIO_HANDOFF_BUILD-00156.md`, `CURRENT_HANDOFF_BUILD-00156.md`, `BUILD-00156_VERIFICATION.md`를 읽고 현재 소스와 테스트 상태를 확인하세요. 사용자의 자율 연속 개발 지침과 승인 경계를 유지하면서 BUILD-00157을 진행하세요. 중간 승인이나 진행 보고를 반복하지 말고, 실제 검증한 결과만 완료로 기록하세요. 빌드가 끝나면 인수인계 문서, 릴리스 노트, 검증 보고서, 빌드 정보, 변경 이력, ZIP, SHA-256 및 독립 추출 검증을 모두 갱신하세요.


# BUILD-00157 추가 인수인계

현재 최신 빌드는 BUILD-00157입니다. RAF lifecycle controller를 추가하고 Studio3DViewer에 통합했습니다. 자세한 내용은 `BUILD-00157_RELEASE_NOTES.md`, `BUILD-00157_VERIFICATION.md`, `CURRENT_HANDOFF_BUILD-00156.md`를 참조하십시오. BUILD-00157에서 Backend 367 tests, Viewer 구조 143, lifecycle 32 assertions, animation controller 19 assertions, API 계약 63/63, response 계약 누락 0, package integrity 0 findings, Chromium WebGL2 capability smoke를 확인했습니다.

실제 Three.js 객체 기반 resource graph 통합, React/Three Viewer+GLTF 브라우저 E2E, semantic TypeScript, GPU 누수/성능 및 context-loss recovery는 아직 미검증/차단 상태입니다. npm install은 timeout되었고 dependency/lockfile은 변경하지 않았습니다.
