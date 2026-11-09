# AI CREATOR STUDIO 개발 진행 기록 v0.27

## 작업
- Operations snapshot의 Worker/Outbox/Poll/Alert/Delivery 집계 SQL을 분리했습니다.
- Alert fingerprint 조회·갱신·생성·해결 SQL을 분리했습니다.
- Alert webhook delivery enqueue/upsert, stale lease requeue, claim, 완료/실패/재시도 SQL을 분리했습니다.
- Repository orchestration과 트랜잭션 경계는 유지했습니다.
- SQLite query boundary 회귀 테스트 4개를 추가했습니다.

## 검증
- pytest: 130 passed
- compileall: passed
- Viewer structural validation: 19/19 passed

## 제한
- SQLite dialect 전용 SQL이며 PostgreSQL SQL이 아닙니다.
- Job/Event/Output SQL은 아직 monolithic repository에 남아 있습니다.
- PostgreSQL 실서버 테스트 및 zero-downtime cutover는 미실시입니다.

## 다음 단계
1. Job/Event/Output SQL을 aggregate별 SQLite repository로 분리
2. 공통 transaction/session 계약과 unit-of-work 경계 확정
3. PostgreSQL 실서버 기반 구현·통합·동시성 검증
4. 검증 이후에만 staged migration 및 rollback 설계
