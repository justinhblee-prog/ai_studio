# BUILD-00089 — Private Asset Integrity Audit

## 구현

- `GET /v1/assets/integrity?workspace_id=...&limit=100&offset=0` 추가.
- Workspace membership/RBAC를 통과한 사용자(owner/admin/editor/viewer)만 해당 workspace의 결과를 조회할 수 있습니다.
- 업로드 시 저장한 `size_bytes`와 `checksum_sha256`를 기준으로 실제 private storage 파일을 스트리밍 방식(1 MiB chunk)으로 검사합니다.
- 결과 상태: `ok`, `missing`, `size_mismatch`, `checksum_mismatch`.
- 응답에는 asset ID와 상태만 포함하며 storage key, filesystem path, checksum 원문은 노출하지 않습니다.
- `limit`은 1~500, `offset`은 0 이상으로 제한합니다. 전체 workspace 수와 현재 페이지 검사 수를 구분해 반환합니다.

## 보안/정확성 경계

- Asset 파일을 수정, 삭제, 자동 복구하지 않는 읽기 전용 감사 기능입니다.
- workspace 범위는 DB 쿼리에서 강제하며 저장 경로는 configured root 내부로 resolve되는지 확인합니다.
- 이 검사는 저장된 bytes의 크기/해시 일치만 확인합니다. glTF semantic validity, 실제 WebGL 로딩, 백업/복구 가능성을 증명하지 않습니다.
- SQLite/local filesystem 경계에서 검증했습니다. PostgreSQL/object storage adapter 검증은 별도입니다.

## 검증

- Asset API tests: 17 passed.
- Backend full suite: 281 passed.
- Python compileall: passed.
- Viewer structural validation: 19/19 passed.
- OpenAPI runtime route inventory regenerated; exact match remains false.
- OpenAPI schema audit regenerated; design contract drift remains and is not represented as conformance PASS.
