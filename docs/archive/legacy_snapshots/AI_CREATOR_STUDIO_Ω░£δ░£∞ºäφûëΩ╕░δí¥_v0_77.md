# AI CREATOR STUDIO 개발 진행 기록 v0.77

- 버전: v0.77
- 작업: Poll Worker Lease Fencing
- 기준 소스: v0.76

## 변경 사항
1. Poll Task 완료 시 worker 소유권뿐 아니라 `lease_expires_at >= now`를 확인하도록 변경했습니다.
2. Poll Task 재예약 및 retry exhaustion 처리에도 동일한 lease 유효성 조건을 추가했습니다.
3. Provider 성공 결과를 Job의 후처리 단계로 넘기는 트랜잭션에서 lease 만료 여부를 검증합니다.
4. Output/Job/Execution/Event/Poll Task를 원자적으로 성공 처리하기 전에도 lease를 검증합니다.
5. 만료된 lease를 가진 이전 worker가 늦게 돌아와 상태를 변경하는 회귀 테스트 4개를 추가했습니다.

## 검증 결과
- Backend pytest: 232 passed
- Python compileall: passed
- Viewer structural validation: 19/19 passed

## 범위 및 한계
- SQLite 단일 호스트 환경의 회귀 검증입니다.
- PostgreSQL 실서버, 다중 호스트 동시성, provider submission POST의 lease fencing은 이번 범위에 포함되지 않습니다.
- 만료된 Poll Task는 기존 lease recovery 경로가 다시 회수할 때까지 processing 상태로 남을 수 있습니다. 단, 만료된 기존 worker는 완료/재예약/실패/후처리 확정 작업을 수행할 수 없습니다.
