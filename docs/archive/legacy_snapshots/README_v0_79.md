# AI CREATOR STUDIO v0.79

## 변경 사항

- Poll Worker의 Provider terminal failure 처리에서 Job 상태 변경과 Poll Task 완료가 별도 호출로 분리되어 있던 경로를 원자적 Repository 메서드로 통합했습니다.
- `fail_provider_poll_task`는 동일 트랜잭션 안에서 status-phase Task의 활성 Lease 소유권/만료 여부를 확인합니다.
- 유효한 Lease일 때만 Job을 failed로 전환하고 Execution 및 Event를 기록한 뒤 Poll Task를 completed로 처리합니다.
- Provider가 실패를 반환했더라도 Lease가 만료된 이전 Worker는 Job 상태를 변경할 수 없습니다.
- Provider 성공 응답에 output URL이 없는 경우도 같은 원자적 실패 경로를 사용합니다.

## 검증

- Backend: `python -m pytest -q` — 236 passed
- Compile: `python -m compileall -q app scripts tests` — passed
- Viewer: `python scripts/validate_source.py` — 19/19 passed
- ZIP: `unzip -t` — passed

## 범위 및 한계

SQLite 단일 호스트 구현과 테스트입니다. PostgreSQL, 다중 서버, 분산 시계/Lease 동기화는 검증하지 않았습니다. Provider submission retry 정책은 변경하지 않았습니다.
