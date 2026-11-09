# 개발 진행 기록 v0.42

## 구현
- Poll Task 운영자 조회/재시도 전용 Repository Port와 SQLite Adapter 추가.
- Dependency Composition Root에 `get_poll_task_admin_repository` 추가.
- `/internal/ops/poll-tasks` 및 `/internal/ops/poll-tasks/{task_id}/retry`가 전용 Port를 사용하도록 변경.
- 기존 workspace owner/admin 권한, status allowlist, 404/409 오류 변환을 보존.
- PostgreSQL 선택은 fail-closed.

## 검증
- Backend pytest: 162 passed
- Python compileall: passed
- Viewer structural checks: 19/19 passed

## 한계
운영자 Repository Adapter의 데이터 접근은 현재 `job_repository` 구현을 위임합니다. 이 버전은 API 경계와 DI 분리이며, SQL 소유권의 완전한 이동이나 PostgreSQL 런타임 구현을 의미하지 않습니다.
