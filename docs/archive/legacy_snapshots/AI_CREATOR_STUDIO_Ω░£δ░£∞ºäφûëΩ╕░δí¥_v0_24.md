# AI CREATOR STUDIO 개발 진행 기록 v0.24

날짜: 2026-11-02

## 작업 목표
v0.23 Storage Port 이후 Outbox / Provider Poll / Operations Worker가 거대 `job_repository` 모듈에 직접 결합된 부분을 역할별 저장소 계약으로 분리한다.

## 구현
- `app/worker_repositories.py` 추가.
- OutboxRepository, PollRepository, OperationsRepository Protocol 정의.
- 각 역할별 SQLite 어댑터 및 구성 빌더 추가.
- `worker.py`, `poll_worker.py`, `monitor_worker.py`가 역할별 저장소 빌더를 사용하도록 변경.
- PostgreSQL 선택 시 각 빌더가 실패 폐쇄하도록 보장.
- 기존 SQL 실행/트랜잭션은 변경하지 않아 기존 안정 동작 유지.

## 검증
- `PYTHONPATH=. pytest -q`: 119 passed.
- `python -m compileall -q app scripts tests`: passed.
- 3D Viewer `validate_source.py`: 19/19 passed.

## 주의 / 미완료
이번 단계는 Worker의 애플리케이션 의존성 경계 분리다. SQLite SQL 구현 자체를 세 aggregate로 분리한 것은 아니며, 세 어댑터는 기존 `job_repository`를 공유한다. PostgreSQL 드라이버/런타임, 실서버 통합 테스트, 다중 인스턴스 claim 경쟁 테스트, 무중단 cutover는 아직 완료되지 않았다.

## 다음 작업
1. Outbox / Poll Task / Operations(Alert) SQL repository를 실제 모듈과 트랜잭션 경계로 분리.
2. SQL dialect 및 session/transaction 추상화.
3. PostgreSQL schema migration runner 및 PostgreSQL adapter 구현.
4. PostgreSQL 실서버 통합 테스트와 다중 worker 경쟁 검증.
5. Credit Quote / append-only Credit Ledger는 별도 P0/P1 계획에 따라 설계·구현.
