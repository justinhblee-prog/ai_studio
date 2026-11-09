# 개발 진행 기록 v0.79

## 감사 결과

Poll Worker의 Provider status terminal failure 분기에서 `transition_job(...)` 후 `complete_poll_task(...)`를 별도 호출하고 있었습니다. 이 경로는 Job 상태 변경 직전에 Lease 소유권을 원자적으로 확인하지 않아, 늦게 도착한 이전 Worker의 terminal failure 결과가 Job을 실패 처리할 가능성이 있었습니다.

## 구현

- `PollRepository` Protocol에 `fail_provider_poll_task` 추가.
- SQLite 구현에서 단일 트랜잭션으로 Task 상태/Worker/phase/Lease 만료 확인.
- Lease가 유효할 때만 Job failed 전환, Execution 전환, Event append, Poll Task completed 처리를 수행.
- `poll_worker._process_status`의 Provider failed 및 succeeded-without-output 분기를 새 원자적 API로 변경.

## 테스트

1. 만료된 Lease의 이전 Worker가 Provider terminal failure로 Job을 실패 처리하지 못함.
2. 유효한 Lease의 Provider terminal failure가 Job/Execution/Event/Task 상태를 일관되게 확정함.

## 검증 결과

- Backend pytest: 236 passed
- Python compileall: passed
- Viewer structural validation: 19/19 passed
- ZIP integrity: passed

## 제한

SQLite 단일 호스트 범위입니다. PostgreSQL 및 다중 인스턴스 검증은 포함하지 않습니다.
