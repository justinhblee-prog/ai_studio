# AI CREATOR STUDIO 인수인계 v5.38

기준 소스: v0.78

## 이번 완료 작업

- v0.77에서 추가된 Poll Worker Lease Fencing을 확장해 만료 Poll Task의 동시 회수 및 회수 후 이전 Worker 쓰기 차단 테스트를 추가했습니다.
- 12개 동시 claimant 중 단일 승자 검증.
- 이전 Worker의 complete/reschedule/exhaust 차단 및 새 Worker의 완료 권한 검증.

## 검증

- Backend pytest: 234 passed
- Python compileall: passed
- Viewer structural validation: 19/19 passed
- ZIP integrity: passed

## 현재 아키텍처 및 범위

- Modular Monolith 유지.
- SQLite가 유일한 실제 런타임 DB 어댑터입니다.
- PostgreSQL readiness 검사는 있으나 PostgreSQL 런타임 Repository Adapter 및 실서버 테스트는 없습니다.
- Poll Worker의 safe GET/output 재시도는 별도 Task Lease를 사용합니다.
- Provider 제출의 결과 불명 상태는 자동 재전송하지 않고 수동 조정 대상으로 둡니다.
- 이번 버전은 SQLite 단일 호스트 경합 테스트이며 다중 서버/분산 환경 증거가 아닙니다.

## 미해결 사항

1. Credit Ledger 영속 Repository Adapter 미구현.
2. Credit 단위 정밀도, 만료/lot 배분, 부분 Capture, Refund 한도, ADJUST 승인 정책 미결정.
3. PostgreSQL 런타임 어댑터 및 동시성 통합 테스트 미구현.
4. FASHN 계약/권리/보존기간/상업적 이용 조건 실검증 필요.
5. QA T-01~T-14 종결 및 G0~G5 Gate 승인 미완료.
6. TypeScript typecheck, 브라우저/WebGL 실기기, Android E2E, 배포 검증 미완료.

## 다음 작업

- v0.79: Poll Worker 상태 실패/성공 분기에서 Lease 소유권이 실제 Job 상태 변경까지 일관되게 적용되는지 코드 감사 및 회귀 테스트.
- 특히 `process_status`의 Provider terminal failure 경로와 일반 `transition_job` 경로를 점검합니다. Lease를 확인하지 않는 상태 전환이 있으면 Repository의 원자적 조건부 전환으로 보완합니다.
- PostgreSQL 또는 분산 환경의 검증으로 확대 해석하지 않습니다.

## 산출물

- 전체 소스 ZIP: `AI_CREATOR_STUDIO_v0_78_poll_recovery_race_tests.zip`
- README: `README_v0_78.md`
- 개발 기록: `AI_CREATOR_STUDIO_개발진행기록_v0_78.md`
