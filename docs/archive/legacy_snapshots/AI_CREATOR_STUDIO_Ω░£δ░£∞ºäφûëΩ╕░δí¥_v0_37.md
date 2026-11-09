# AI CREATOR STUDIO 개발 진행 기록 v0.37

## 목표
v0.36에서 남은 Generation Job 상태 변경 SQL과 Execution 상태 변경 SQL을 각각 전용 Repository로 분리하되, Job/Event/Execution이 하나의 원자적 트랜잭션 경계를 유지하도록 한다.

## 구현
1. `app/repositories/job.py`
   - `SQLiteJobRepository`가 transition/update의 실제 SQLite 쓰기 로직을 소유한다.
   - 기존 `app.job_repository.transition_job` 및 `update_job`은 호환 Facade로 전환했다.
   - 미분리된 조회/운영 메서드는 임시 호환 위임을 유지한다.
2. `app/repositories/execution.py`
   - `ExecutionRepository` Protocol 및 `SQLiteExecutionRepository`를 추가했다.
   - 최신 Execution의 running/post_processing/succeeded/failed 변경 SQL을 전용 Adapter로 이동했다.
   - Adapter는 전달받은 connection만 사용하고 별도 커밋/연결을 만들지 않는다.
3. `app/repositories/job_event_uow.py`
   - lifecycle transition/update를 전용 Job Repository에 위임한다.
4. 테스트
   - 전용 Job Repository 및 Execution Repository 계약 확인
   - Job 상태와 Execution 상태의 동시 변경 확인
   - Event INSERT 실패 시 Job과 Execution 모두 롤백되는지 확인

## 검증 결과
- Backend pytest: 151 passed
- Python compileall: passed
- 3D Viewer structural checks: 19/19 passed

## 남은 작업
- Job 생성/조회/idempotency SQL을 전용 Repository로 추가 이전
- Execution 조회/attempt 생성/재시도 경로를 완전 분리
- Outbox/Poll/Operations에서 남은 Legacy Repository 위임 제거
- PostgreSQL runtime adapter 및 실제 서버 통합 테스트
- Credit Quote 및 append-only Credit Ledger
- FASHN 계약/권리/보존기간/상업적 이용 검증
- TypeScript 빌드, 브라우저/WebGL, Android E2E 및 운영 배포 검증

## 주의
이번 버전은 SQLite 내 트랜잭션 경계와 Repository 분리 작업이다. PostgreSQL 실서버 검증, 무중단 배포, 무중단 DB 전환을 구현했다고 주장하지 않는다.
