# 개발 진행 기록 v0.78

## 목표

v0.77 Lease Fencing 후속으로, 만료된 Poll Task를 여러 Worker가 동시에 회수하는 경합과 이전 Worker의 늦은 쓰기를 검증했습니다.

## 구현

파일: `ai_creator_studio_backend_starter/tests/test_concurrent_claims.py`

1. `test_expired_poll_task_recovery_has_single_concurrent_winner`
   - Poll Task를 만료시킨 뒤 12개 Worker가 동시에 claim합니다.
   - 단 하나의 Worker만 동일 Task를 회수하는지 확인합니다.
2. `test_reclaimed_poll_task_fences_previous_worker`
   - 새 Worker가 만료 Task를 회수한 뒤 이전 Worker의 complete/reschedule/exhaust 요청이 모두 거부되는지 확인합니다.
   - Task 소유권이 새 Worker에 유지되고 새 Worker만 완료할 수 있는지 확인합니다.

## 검증 결과

- `python -m pytest -q`: 234 passed
- `python -m compileall -q app scripts tests`: passed
- Viewer `python scripts/validate_source.py`: 19/19 passed
- ZIP integrity: passed

## 제한 사항

SQLite 단일 호스트 테스트입니다. PostgreSQL 런타임 어댑터와 다중 인스턴스 검증은 포함하지 않습니다. Lease 만료 경계는 기존 저장소 구현을 그대로 사용했으며 분산 시계 동기화나 fencing token 기반의 다중 프로세스 장애 복구까지 증명하지 않습니다.
