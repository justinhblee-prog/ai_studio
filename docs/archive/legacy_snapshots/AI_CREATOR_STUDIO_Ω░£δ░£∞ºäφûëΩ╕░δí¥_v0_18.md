# AI CREATOR STUDIO 개발 진행 기록 v0.18

## 기준 버전
- 입력: v0.16 Provider Capability / Policy Registry
- 결과: v0.18 Dedicated Provider Poll Worker
- API 버전: 0.6.0

## 완료
- Provider status poll queue를 SQLite durable task로 분리
- API Job GET을 read-only로 변경
- submission worker와 poll/output worker 프로세스 분리
- Provider 성공 상태 변경과 output phase handoff 원자화
- Poll lease expiry 재큐잉
- 지수형 backoff 및 표준 Retry-After 헤더 제한 반영
- poll retry budget 소진 시 needs_reconciliation 전환
- output 파일 원자적 교체
- worker health에 poll task counts 추가
- 수동 request ID 연결 시 poll task 자동 생성
- Workspace owner/admin 전용 poll task 조회 및 안전 재시도 API
- 재시도는 status GET / output 저장 단계만 수행하고 Provider POST 재전송 금지
- 운영자, 사유, 재시도 phase를 Job Event에 감사 기록
- Job에 저장된 provider/model과 실행 설정 불일치 시 silent reroute 금지

## 검증
- Backend pytest 92/92
- compileall PASS
- OpenAPI 20 paths
- 3D Viewer 구조 검사 19/19

## 미완료 / 위험
- FASHN live contract, 권리, retention, 상업 이용 승인 미완료
- PostgreSQL 및 다중 인스턴스 lock 미구현
- poll task 수동 복구 API 구현 완료, 전용 시각적 admin UI는 미구현
- 모니터링 alert 전달 미연결
- Credit Quote / Ledger 미구현
- Browser/WebGL/Android E2E 미검증

## 다음 작업
1. metrics 및 alerting
2. PostgreSQL migration
3. Provider HTTP transport contract tests 확대
4. FASHN G2 verification
5. Credit Quote / Ledger

기존 T-01..T-14 정의는 변경하지 않는다. 부분 테스트 PASS를 전체 QA Gate PASS로 확대 해석하지 않는다.
