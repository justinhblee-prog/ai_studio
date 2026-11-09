# AI CREATOR STUDIO 개발 진행 기록 v0.22

## 목표
v0.21에서 정의한 저장소 경계의 다음 단계로, SQLite 드라이버 연결 및 쓰기 트랜잭션 시작 동작을 독립 Port로 추출한다.

## 구현
- `app/storage.py`
  - `StorageBackend` Protocol: connect / begin_write
  - `SQLiteStorage`: connection, foreign_keys, busy_timeout, WAL, BEGIN IMMEDIATE
  - `get_storage`: sqlite 지원, postgresql 명시적 미지원, 기타 backend 거부
- `app/job_repository.py`
  - `_connect()`가 Storage Port를 통해 연결
  - `BEGIN IMMEDIATE` 직접 실행을 `_begin_write()` 경유로 전환
- `tests/test_storage_port.py`
  - SQLite PRAGMA 설정 확인
  - immediate write transaction 확인
  - PostgreSQL fallback 차단 확인
- v0.21 Repository Contract Protocol/Adapter와 Idempotency/rollback 테스트 유지

## 검증
- `python -m pytest -q`: 114 passed
- `python -m compileall -q app scripts tests`: passed
- 3D Viewer 구조 검사: 19/19 passed

## 제한 / 미완료
- SQL dialect 및 DDL은 여전히 SQLite 전용: `executescript`, `INSERT OR IGNORE`, `?` placeholder, SQLite-specific schema and row behavior.
- Repository Protocol은 정의됐으나 API/Worker 전체가 DI로 주입받는 구조는 미완료.
- PostgreSQL adapter, driver/server integration, multi-instance race/lease tests 미실시.
- 따라서 무중단 전환 또는 PostgreSQL 운영 지원을 선언하지 않는다.
- Credit Quote / append-only Credit Ledger 미구현.
- FASHN live contract/rights/retention/commercial-use verification open.
- Browser/WebGL/Android E2E 및 production deployment unverified.
- QA T-01~T-14 추적 유지, Gate 상태를 임의로 닫지 않는다.

## 다음 순서
1. schema migration runner 및 SQL dialect 분리
2. Job/Outbox/Poll/Alert aggregate repository 추출
3. API/Worker repository DI
4. PostgreSQL adapter + real service integration suite
5. multi-instance claim/idempotency/recovery and cutover rehearsal
