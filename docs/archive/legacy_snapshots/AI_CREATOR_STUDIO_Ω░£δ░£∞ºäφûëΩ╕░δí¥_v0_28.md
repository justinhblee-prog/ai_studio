# AI CREATOR STUDIO 개발 진행 기록 v0.28

## 작업
- StorageBackend Protocol에 `transaction(database_path)` 계약을 추가했습니다.
- SQLiteStorage가 연결 생성, 정상 종료 commit, 예외 rollback, 연결 close를 소유합니다.
- Generation Job Repository의 31개 connection scope를 StorageBackend transaction context로 변경했습니다.
- 기존 `BEGIN IMMEDIATE`를 유지해 critical multi-statement write/claim 경합 동작을 바꾸지 않았습니다.
- transaction commit, rollback, close 및 create-job 부분 실패 rollback 테스트를 보강했습니다.

## 검증
- pytest: 132 passed
- compileall: passed
- Viewer structural validation: 19/19 passed

## 제한
- 현재 구현은 SQLite only입니다.
- PostgreSQL connection pool, isolation level, savepoint, SKIP LOCKED 등은 미구현입니다.
- context manager 자체가 자동으로 transaction을 시작하지는 않습니다. 원자성이 필요한 경로는 `begin_write`를 명시적으로 호출해야 합니다.
- 무중단 cutover 및 PostgreSQL 실서버 검증은 미실시입니다.
