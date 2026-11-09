# AI CREATOR STUDIO 개발 진행 기록 v0.38

## 목표
v0.37의 Job lifecycle SQL 분리에 이어 Job 생성·조회·idempotency SQL을 전용 Repository로 이전하고 Execution 초기 attempt 생성 SQL도 Execution Repository로 귀속한다.

## 구현
1. `SQLiteJobRepository`
   - `create`, `get`, `get_idempotent`를 직접 구현한다.
   - Job 생성, 선택적 workspace idempotency, Event append, 초기 Execution, Outbox 등록을 한 트랜잭션에서 수행한다.
   - Legacy `create_job`, `get_job`, `get_idempotent_job`, `transition_job`, `update_job`은 호환 Facade로 남긴다.
2. `SQLiteExecutionRepository`
   - 초기 queued Execution attempt 생성과 최신 attempt 상태 갱신을 담당한다.
   - 전달받은 DB connection만 사용해 Job 생성/상태 변경과 원자성을 유지한다.
3. `SQLiteEventRepository`
   - Event 조회와 append를 계속 전담한다.
4. 테스트
   - Legacy module create/read 함수 호출 없이 전용 Repository가 직접 작동하는지 검증
   - 중복 idempotency key가 기존 Job을 반환하는지 검증
   - 기존 Outbox insert 실패 rollback 테스트 포함 전체 회귀 확인

## 검증 결과
- Backend pytest: 153 passed
- Python compileall: passed
- 3D Viewer structural checks: 19/19 passed

## 남은 작업
- Diagnostics / Execution read SQL 분리
- Outbox/Poll/Operations 및 admin reconciliation에서 Legacy Repository 의존 제거
- PostgreSQL runtime adapter와 실제 서버 통합 테스트
- Credit Quote 및 append-only Credit Ledger
- FASHN 계약/권리/보존기간/상업적 이용 검증
- TypeScript 빌드, 브라우저/WebGL, Android E2E, 배포 검증

## 주의
SQLite 기반 Repository 추출 단계이며 PostgreSQL 실서버 검증이나 무중단 배포·전환을 구현했다고 주장하지 않는다.
