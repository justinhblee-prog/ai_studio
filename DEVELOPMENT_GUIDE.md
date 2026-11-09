# 개발 및 검증 가이드 — BUILD-00156

## 기준 소스
이 문서가 포함된 저장소의 `ai_creator_studio_backend_starter/`, `ai_creator_studio_3d_viewer/`가 BUILD-00156 소스입니다. 과거 ZIP을 섞지 마십시오.

## Backend
```bash
cd ai_creator_studio_backend_starter
python -m pytest -q tests
```

## Viewer
```bash
cd ai_creator_studio_3d_viewer
npm run test:viewer-cleanup
npm run test:dispose-gltf-resources
npm run test:authenticated-gltf-loading
npm run test:bounded-gltf-download-runtime
npm run test:bounded-gltf-download
npm run validate:api-contract
npm run validate:request-contract
npm run test:request-contract
npm run validate:response-contract
npm run validate:syntax
npm run validate:package-integrity
npm run typecheck
```

`npm run typecheck`는 현재 React/Three 및 타입 선언 의존성 부재로 막힐 수 있으며, 통과한 것으로 간주하지 마십시오. 의존성/lockfile을 승인 없이 변경하지 마십시오.

## 승인 경계
유료 Provider/API, 실제 크레딧/결제, 외부 게시, 권리 부여, 운영 데이터·스토리지 변경, 배포, 파괴적 DB migration은 명시적 승인 전 금지합니다.

## 보고 원칙
구문 검사, 구조 검사, 단위 테스트, WebGL capability smoke, 실제 React/Three E2E, 운영 실환경 검증을 구분합니다. 실행하지 못한 항목은 BLOCKED/UNVERIFIED로 기록합니다.
