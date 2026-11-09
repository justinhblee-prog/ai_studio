# BUILD-00131 — Workspace Mutation Scope Safety

## 변경 사항
- 공통 `useRequestScope` hook을 추가해 API origin, access token, workspace/job scope가 바뀌거나 컴포넌트가 unmount된 뒤 완료되는 비동기 작업이 현재 UI 상태를 덮어쓰지 못하도록 했습니다.
- Asset, Photo Draft, Lookbook, Product Catalog/Variant, Project Product Assignment, Project, Output Review의 주요 mutation callback에 scope snapshot 검증을 적용했습니다.
- Photo/Lookbook/Asset/Output Review 및 Project Product 데이터 loader의 mutation 후속 reload가 이전 scope 결과를 반영하지 않도록 방어했습니다.
- workspace/job scope 변경 시 각 화면의 이전 workspace 데이터, 폼/선택, manifest/preview 및 busy/error 상태를 초기화했습니다.
- 구조 검증을 87개에서 103개로 확장해 scope helper, mutation guards, stale reload rejection, scope state reset을 검사합니다.

## 범위 및 비변경 사항
- Backend/API/DB/schema/dependency/provider/credit 동작 변경 없음.
- 서버에서 이미 접수된 mutation 자체를 취소하는 기능은 아닙니다. 요청이 서버에 반영된 뒤 scope가 바뀌면 이전 화면의 UI 갱신만 무시합니다.
