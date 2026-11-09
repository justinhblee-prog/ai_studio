# AI CREATOR STUDIO 개발 진행 기록 v0.36

## 목표
generation_job_events 테이블의 SQL 소유권을 legacy Job 모듈에서 전용 Event Repository로 이동하면서 기존 트랜잭션 원자성을 유지한다.

## 변경
- `EventRepository`에 `append_in_transaction(connection, ...)` 추가.
- `SQLiteEventRepository`가 Event 조회 SELECT 및 append INSERT SQL의 단일 소유자가 됨.
- append는 호출자가 전달한 DB connection에서만 실행하고 별도 connection/commit을 수행하지 않음.
- `job_repository.py` 내 모든 Event INSERT를 `_append_event()`를 통해 전용 Event Repository로 위임.
- `job_repository.list_events()`도 Event Repository로 위임.
- `SQLiteOutputRepository.finalize_success()`가 Output Event를 전용 Event Repository에 기록.
- 기존 worker SQL 상수에 있던 Output Event INSERT SQL 제거.
- Job/Event UoW의 Event 조회도 전용 Event Repository 사용.
- 호환 테스트에서 명시적으로 주입한 Fake implementation은 기존 `list_events` read path를 유지.

## 검증
- Backend pytest: 149 passed.
- Python compileall: 통과.
- Viewer structural validation: 19/19 통과.
- 구조 검사: `generation_job_events` SELECT/INSERT SQL이 Event adapter에만 존재.
- Event INSERT 실패 시 Job rollback, Output atomic finalization rollback 등 기존 원자성 테스트 통과.

## 제한 및 미완료
- Job/Execution 변경 SQL은 아직 legacy Job 모듈에 남아 있으며 Event adapter 호출을 같은 connection으로 orchestration한다.
- PostgreSQL Event adapter 및 실제 서버 통합 검증 미완료. PostgreSQL 선택은 fail-closed.
- Credit Quote 및 append-only Credit Ledger 미구현.
- FASHN 실계약/권리/보존/상업 이용 검증 미완료.
- Browser/WebGL/Android E2E 및 Production 배포 검증 미완료.
- QA T-01~T-14 추적성 유지.

## 다음 단계
1. Job Repository의 상태 변경 및 Execution SQL을 별도 adapter로 분리하되 기존 UoW transaction connection을 공유한다.
2. Event append-only 권한 및 변경/삭제 방지 검증을 강화한다.
3. PostgreSQL 서버/드라이버 확보 시 Event append, transaction rollback, isolation 및 multi-instance 동시성 테스트를 수행한다.
