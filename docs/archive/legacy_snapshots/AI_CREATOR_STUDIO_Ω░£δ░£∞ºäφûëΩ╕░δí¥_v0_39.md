# AI CREATOR STUDIO 개발 진행 기록 v0.39

## 목표
Legacy Job Repository에 남은 진단 조회 SQL을 전용 Diagnostics Repository로 분리한다.

## 구현
- `JobDiagnosticsRepository` Protocol 추가
- `SQLiteJobDiagnosticsRepository` 구현
- Event/Output은 각각의 전용 Repository를 통해 조회
- Execution/Outbox/Poll Task 진단 데이터는 하나의 read transaction에서 조회
- 기존 `job_repository.diagnostics()`는 호환 Facade로 전환
- PostgreSQL 선택 시 fail-closed

## 검증
- Backend pytest: 156 passed
- Python compileall: passed
- 3D Viewer structural checks: 19/19 passed
- Diagnostics 구성 요소 통합 테스트와 PostgreSQL fail-closed 테스트 추가

## 후속 작업
- Outbox/Poll/Admin reconciliation SQL의 전용 Repository 이전
- Operations 모니터링 SQL의 완전한 Legacy 분리
- PostgreSQL 런타임 Adapter 및 실제 서버 통합 테스트
- Credit Quote / append-only Credit Ledger
- FASHN 계약/권리/보존기간/상업적 이용 검증
- TypeScript 및 브라우저/WebGL/Android E2E와 운영 배포 검증

## 주의
이번 버전은 진단 조회의 Repository 분리다. PostgreSQL 실서버 검증, 무중단 배포, 무중단 DB 전환을 완료했다는 의미가 아니다.
