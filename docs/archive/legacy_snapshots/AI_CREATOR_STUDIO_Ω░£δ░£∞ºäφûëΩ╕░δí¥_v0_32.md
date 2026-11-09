# AI CREATOR STUDIO 개발 진행 기록 v0.32

## 목표
API 전반에서 Generation Job 저장소를 직접 import하는 경로를 줄이고 composition root를 통한 DI로 통일한다.

## 변경
- `SQLiteJobRepository`에 initialize 및 호환 메서드 위임 추가.
- FastAPI dependency `get_job_repository`를 사용해 health, create/get job, event diagnostics, reconciliation, poll task list/retry, worker health, Prometheus metrics, operational alerts, output authorization 경로 주입.
- 앱 시작 시 `get_job_repository().initialize()`를 사용.
- 이벤트 API의 기존 응답 형식(execution/output/outbox/poll_task 포함)과 접근제어는 유지.
- PostgreSQL 설정은 fail-closed 상태 유지.

## 검증
- Backend pytest: 139 passed.
- Python compileall: passed.
- Viewer structural validation: 19/19 passed.

## 제한
- SQLite 어댑터는 미추출 기능을 기존 `job_repository` 모듈에 위임한다.
- PostgreSQL 실제 서버/드라이버 통합 검증 미완료.
- Multi-instance worker claim, lease, transaction 검증 미완료.
- Zero-downtime Dual Write/CDC/cutover/rollback 미구현.
- Credit Quote/Ledger 및 FASHN 계약/권리/보존/상업 이용 확인 미완료.
- QA T-01~T-14 추적성 유지.

## 다음 단계
- Worker entrypoint의 repository composition root DI 통일.
- Job/Event 쓰기 서비스 경계와 Unit of Work 통합.
- PostgreSQL 환경 확보 후 migration, idempotency, row lock, lease claim, rollback, multi-instance 테스트.
