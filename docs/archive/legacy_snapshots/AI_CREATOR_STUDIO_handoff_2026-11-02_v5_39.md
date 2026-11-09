# AI CREATOR STUDIO 인수인계 v5.39

기준 소스: v0.79

## v0.79 완료

- Poll Worker Provider terminal failure 경로의 Lease 검증 누락을 수정했습니다.
- `fail_provider_poll_task`에서 활성 Lease 확인, Job failed 전환, Execution 갱신, Event append, Poll Task 완료를 단일 SQLite 트랜잭션으로 처리합니다.
- Provider failed와 succeeded-without-output 경로가 이 원자적 메서드를 사용합니다.
- 만료 Lease의 늦은 실패 응답은 Job에 반영되지 않습니다.

## 검증

- Backend pytest: 236 passed
- Python compileall: passed
- Viewer validation: 19/19 passed
- ZIP integrity: passed

## 현재 제한

- SQLite만 런타임 DB 어댑터로 구현되어 있습니다.
- PostgreSQL 런타임 어댑터 및 실서버 테스트 미구현.
- 이번 수정은 SQLite 단일 호스트 기준이며 다중 서버/분산 Lease 검증이 아닙니다.
- Credit Ledger 영속화 및 Credit 정책 결정 미완료.
- FASHN 계약/권리/보존기간/상업 이용 조건 검증 필요.
- QA T-01~T-14 및 G0~G5 승인 미완료.
- Browser/WebGL 실기기, Android E2E, TypeScript typecheck 및 배포 검증 미완료.

## 다음 작업

- v0.80: Provider `succeeded` 응답과 `output_url` 누락/유효 여부 처리의 Lease 경계 및 Job 상태 전환 원자성 점검.
- `mark_provider_succeeded_for_poll` 경로와 동시 Worker/만료 Lease 테스트를 추가 확인합니다.
- SQLite 단일 호스트 증거만 주장합니다.
