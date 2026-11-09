# AI CREATOR STUDIO — CURRENT HANDOFF BUILD-00216

- 작성일: 2026-11-06
- 기준 소스: BUILD-00215
- Engineering build: **BUILD-00216**
- 상태: PostgreSQL Job 및 Outbox vertical-slice adapter 구현. SQLite는 계속 기본/유일 활성 backend이며, PostgreSQL runtime factory는 fail-closed 유지.

## 1. BUILD-00216 구현

- `app/repositories/postgres_job.py`
  - Job create/get/idempotency/list/transition/update/cancel queued.
  - Job create는 advisory lock으로 workspace + idempotency key 경쟁을 직렬화하고 Job, Execution, Event, Idempotency, Outbox를 단일 transaction으로 기록.
  - payload hash가 다른 동일 idempotency key는 충돌 처리.
  - lifecycle 전환은 `SELECT ... FOR UPDATE`, 상태 전이표, event append 및 latest Execution update를 단일 transaction으로 수행.
  - execution/output history response shape 및 reconciliation 상태 매핑 제공.
- `app/repositories/postgres_outbox.py`
  - `FOR UPDATE SKIP LOCKED` 기반 atomic pending claim.
  - Worker ID 및 lease duration 검증.
  - expired dispatch lease는 `needs_reconciliation`으로 격리하고 자동 재전송하지 않음.
  - complete/unknown 처리에 worker owner + unexpired lease 조건을 적용하여 stale worker fencing.
  - provider submit 완료 후 Poll task와 Event를 같은 transaction으로 기록.
  - Worker heartbeat upsert.
- `app/postgres.py` psycopg dict-row 지원 및 migration ledger row handling 보강.

## 2. 검증

- Backend pytest: **505 passed / 0 failed**.
- Python compileall (`app`, `tests`): PASS.
- Runtime OpenAPI snapshot: PASS.
- 신규 테스트는 idempotency atomicity, payload mismatch, SKIP LOCKED claim, expired lease quarantine, owner/lease fencing을 검증.
- PostgreSQL 서버에 실제 접속한 테스트는 아직 수행하지 않음. Fake connection 테스트는 SQL 호출 구조/트랜잭션 경계를 검증할 뿐 실제 SQL 실행 성공을 증명하지 않음.

## 3. 활성화 제한

- `DATABASE_BACKEND=postgresql`은 계속 거부됨.
- `PostgreSQLJobRepository` 및 `PostgreSQLOutboxRepository`는 부분 aggregate adapter이며 runtime factory에 연결하지 않음.
- Poll, Operations/Alert, Output/Asset, Workspace/Project, Product 등 나머지 aggregate adapter 미완료.
- 실제 PostgreSQL schema migration은 Supabase 테스트 프로젝트에 적용 전.
- Supabase Storage adapter/policies 미완료.
- Vercel source-backed Preview deployment 미완료.

## 4. 다음 연속 작업

1. PostgreSQL Poll repository 구현: claim, lease expiry, retry scheduling, completion fencing.
2. Operations/Alert delivery 및 heartbeat repository 구현.
3. Job/Outbox/Poll 통합 contract suite를 SQLite/PostgreSQL 공통 테스트로 추출.
4. 로컬 PostgreSQL 실행 환경이 가능한지 확인하고 실제 DB integration tests 구성.
5. 전 aggregate adapter 최소 핵심 동작이 준비되면 Supabase 전용 테스트 DB에 migration 적용 및 SQL/RLS 검증.
6. 이후 Storage adapter와 Vercel Preview 배포.

## 5. 실환경 현황

BUILD-00214의 읽기 전용 Supabase/Vercel 스모크 결과는 `docs/reports/BUILD-00214_SUPABASE_VERCEL_LIVE_SMOKE.md` 참조. BUILD-00215/216에서는 Supabase 및 Vercel에 변경을 가하지 않음.
