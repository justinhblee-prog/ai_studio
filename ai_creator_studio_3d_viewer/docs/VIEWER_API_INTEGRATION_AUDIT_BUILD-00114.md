# Viewer ↔ Backend API 계약 검증 — BUILD-00114

## 범위

- Viewer `src/*.tsx` 7개 파일에서 `fetch()`로 호출하는 `/v1/` URL과 HTTP method를 추출했습니다.
- 동적 path segment는 해당 callback의 허용 action union을 적용해 구체 경로로 확장했습니다.
- Backend BUILD-00113 runtime OpenAPI snapshot과 경로, HTTP method, query parameter 이름을 대조했습니다.
- 동일 파일/경로/method의 중복 호출은 호출 단위 보고서에 유지하고 고유 method+path 수는 별도 집계했습니다.

## 결과

| 항목 | 결과 |
|---|---:|
| Viewer source files | 7 |
| Fetch call sites after dynamic expansion | 58 |
| Unique method + path combinations | 48 |
| Path + method matches | 58/58 |
| Missing path/method | [] |
| Undeclared query parameters | [] |
| Unresolved dynamic path segments | [] |

**결과: Source-level API path/method/query contract 검사 통과.**

## 발견 및 수정

- `ProductCatalogWorkspace.tsx`, `LookbookDraftWorkspace.tsx`가 `/v1/assets` 호출에 `limit=100`을 전달했으나 실제 FastAPI route는 `workspace_id`, `kind`만 선언하고 있었습니다. FastAPI가 알 수 없는 query parameter를 무시하므로 호출은 실패하지 않지만 UI가 100개 제한을 적용한다고 오해할 수 있습니다. 두 호출에서 무시되는 `limit`을 제거했습니다.
- `LookbookDraftWorkspace`의 review action, assembly decision, `PhotoDraftWorkspace`/`OutputReviewWorkspace`의 review action은 동적 path union을 확장해 검증하도록 처리했습니다.
- 새 `scripts/validate_api_contract.py`와 `npm run validate:api-contract` 명령을 추가했습니다.

## 검증 한계

이 검사는 정적 소스 분석입니다. Request body schema, response payload field/type, auth/session behavior, CORS, network timing, React state lifecycle, browser rendering 및 WebGL을 검증하지 않습니다. TypeScript 의존성 설치는 실행 환경에서 npm install이 제한 시간 내 완료되지 않아 typecheck를 수행하지 못했습니다. 브라우저 E2E도 실행하지 않았습니다.

## 재실행

```bash
cd ai_creator_studio_3d_viewer
python3 scripts/validate_api_contract.py
# 또는
npm run validate:api-contract
```

기계 판독 결과: `viewer_api_contract.v1.json`
