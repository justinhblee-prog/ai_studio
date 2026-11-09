# AI CREATOR STUDIO v0.78

## 변경 사항

- Poll Worker의 만료 Lease 회수 경합 테스트를 추가했습니다.
- 12개 동시 claimant가 만료된 동일 Poll Task를 회수할 때 단일 승자만 얻는지 검증합니다.
- 회수 완료 후 이전 Worker가 완료/재예약/실패 확정할 수 없고, 새 Worker만 완료할 수 있는지 검증합니다.
- 기존 SQLite 동시성 테스트 및 전체 Backend 테스트를 함께 실행했습니다.

## 검증

- Backend: `python -m pytest -q` — 234 passed
- Compile: `python -m compileall -q app scripts tests` — passed
- Viewer: `python scripts/validate_source.py` — 19/19 passed
- ZIP: `unzip -t` — passed

## 범위 및 한계

이번 결과는 SQLite 단일 호스트 환경에서의 회수 경합/이전 소유자 차단 회귀 테스트입니다. PostgreSQL, 다중 서버, 분산 락 또는 실서비스 부하 검증을 의미하지 않습니다. Provider status GET 작업의 재시도만 안전한 것으로 취급하며 Provider 제출 재실행 정책은 변경하지 않았습니다.
