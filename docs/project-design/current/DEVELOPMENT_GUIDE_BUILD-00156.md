# 개발 및 검증 가이드

## 이전 인수인계에 기록된 경로

-   Backend: `ai_creator_studio_backend_starter/`
-   Viewer: `ai_creator_studio_3d_viewer/`
-   Cleanup runner:
    `ai_creator_studio_3d_viewer/src/runViewerCleanupSteps.mjs`
-   Cleanup declarations:
    `ai_creator_studio_3d_viewer/src/runViewerCleanupSteps.d.mts`
-   Cleanup runtime test:
    `ai_creator_studio_3d_viewer/scripts/test_viewer_cleanup_steps.mjs`
-   Lifecycle structural test:
    `ai_creator_studio_3d_viewer/scripts/test_viewer_cleanup_lifecycle.py`

위 경로는 이전 BUILD-00155 기록입니다. BUILD-00156 소스에서 실제 존재
여부를 확인하십시오.

## 기록된 테스트 명령

``` bash
cd ai_creator_studio_backend_starter
python -m pytest -q tests
```

``` bash
cd ai_creator_studio_3d_viewer
npm run test:viewer-cleanup
```

``` bash
xvfb-run -a python scripts/probe_browser_runtime.py
```

``` bash
npm run typecheck
```

이전 기록에서 typecheck는 React, Three, `three/addons/*` 및 타입 선언이
설치되지 않아 blocked였습니다. 성공으로 간주하지 마십시오.

## 검증 기록 규칙

각 빌드마다 명령, 실행 위치, 통과/실패/차단, 테스트 수, 환경/의존성,
실패 로그, 수정 후 재실행, 브라우저 capability와 실제 E2E 구분, ZIP
CRC/SHA-256/clean extraction 결과를 남깁니다.

## 빌드 산출물

완료 빌드마다 전체 소스 ZIP, SHA-256, CURRENT_HANDOFF.md, 검증 보고서,
릴리스 노트, BUILD_INFO, CHANGELOG, clean extraction 보고서를
갱신합니다. 기존 빌드를 덮어쓰지 않습니다.

## 주의

React/Three 의존성을 임의 설치하지 말고 기존 lockfile과 정책을
확인합니다. DB schema/data, Provider, credits, publication, rights,
deployment는 승인 없이 변경하지 않습니다.
