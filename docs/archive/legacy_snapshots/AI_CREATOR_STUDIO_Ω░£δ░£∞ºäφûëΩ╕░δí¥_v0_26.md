# AI CREATOR STUDIO 개발 진행 기록 v0.26

## 작업
- Outbox SQL statement를 `app/sql/sqlite_worker.py`로 분리했습니다.
- Poll Task claim/recovery SQL statement를 같은 SQLite 전용 모듈로 분리했습니다.
- `job_repository.py`의 트랜잭션 orchestration은 유지하고 SQL 문자열 의존만 명시적 dialect 모듈로 이동했습니다.
- claim compare-and-set 조건, 시도 횟수 증가, 결정적 정렬, Outbox UNKNOWN 보호, Poll 안전 재큐 조건을 테스트했습니다.

## 검증 결과
- pytest: 126 passed
- compileall: passed
- 3D Viewer structural validation: 19/19 passed

## 제한 사항
- SQLite 전용 SQL입니다.
- PostgreSQL adapter/dialect/live integration test는 아직 없습니다.
- Alert/Operations SQL, Job/Event/Output SQL은 아직 기존 저장소 모듈에 남아 있습니다.
- PostgreSQL 전환, 무중단 cutover, 다중 인스턴스 운영 완료로 간주하지 않습니다.

## 다음 단계
1. Operations/Alert SQL 분리
2. Job/Event/Output SQL 분리
3. 공통 transaction/session contract 정리
4. PostgreSQL 실서버 환경 확보 후 실제 adapter 구현 및 동시성/복구 테스트
5. 검증된 이후에만 staged cutover 및 rollback 절차 수행
