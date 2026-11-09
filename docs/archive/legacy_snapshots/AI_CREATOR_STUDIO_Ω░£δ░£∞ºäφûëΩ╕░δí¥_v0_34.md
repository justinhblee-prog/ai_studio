# AI CREATOR STUDIO 개발 진행 기록 v0.34

## 목표
Generation Job 상태 변경과 append-only Event 기록의 애플리케이션 경계를 명시하고, Poll Worker의 상태 변경을 해당 경계로 통합한다.

## 변경
- `app/repositories/job_event_uow.py`에 `JobEventUnitOfWork` Protocol과 `SQLiteJobEventUnitOfWork` 구현 추가.
- `transition_job`, `update_job`, `list_events`를 하나의 Job/Event aggregate boundary로 제공.
- SQLite 구현은 기존 `job_repository.transition_job` 및 `update_job`을 호출한다. 두 메서드는 각각 Job/Execution 변경과 Event INSERT를 동일 SQLite transaction 안에서 수행한다.
- `app/services/job_lifecycle.py`에 `JobLifecycleService` 추가.
- `SQLitePollRepository`가 UoW와 Lifecycle Service를 구성하고 transition/update를 서비스에 위임.
- PostgreSQL UoW는 구현되지 않았으므로 fail-closed.
- 호출자가 여러 개의 독립 저장 작업을 임의로 묶는 외부 transaction manager인 것처럼 오해하지 않도록, 현재 UoW는 각 lifecycle command 단위의 원자성을 제공한다고 명시.

## 검증
- Backend pytest: 147 passed.
- Python compileall: 통과.
- Viewer structural validation: 19/19 통과.
- Event INSERT trigger로 실패를 주입했을 때 Job 상태가 이전 값으로 롤백되고 실패 Event가 남지 않는 통합 테스트 추가.

## 제한 및 미완료
- SQLite SQL/transaction 소유권은 검증된 legacy 구현에 남아 있으며 완전한 aggregate SQL 추출은 미완료.
- PostgreSQL runtime UoW 및 실제 서버 통합 테스트 미완료. PostgreSQL 선택은 fail-closed.
- Credit Quote 및 append-only Credit Ledger 미구현.
- FASHN 실계약/권리/보존/상업 이용 검증 미완료.
- Browser/WebGL/Android E2E 및 Production 배포 검증 미완료.
- QA T-01~T-14 추적성 유지.

## 다음 단계
1. Job/Event repository adapter가 legacy 모듈의 SQL 세부사항에 의존하는 지점을 더 분리한다.
2. API reconciliation 및 운영자 명령도 atomic Job/Event application service 경계로 정리하되 기존 권한과 응답 계약을 유지한다.
3. PostgreSQL 서버/드라이버 확보 시 동등한 트랜잭션·rollback·idempotency·lease 테스트를 수행한다.
