# AI CREATOR STUDIO — CURRENT HANDOFF BUILD-00215

- 작성일: 2026-11-06
- 기준 소스: BUILD-00214 full handoff source
- Engineering build: **BUILD-00215**
- 상태: PostgreSQL migration foundation 및 schema 설치기 구현. SQLite 기본 런타임 유지. Supabase 실 DB에는 아직 적용하지 않음.

## 1. BUILD-00215 구현

- `ai_creator_studio_backend_starter/app/postgres.py`
  - `DATABASE_URL` 필수, 미설정 시 fail-closed.
  - psycopg 3 연결 timeout 및 application name 지정.
  - 순서가 있는 `NNNN_*.sql` 마이그레이션 검색.
  - transaction-scoped advisory lock으로 동시 migration 실행 직렬화.
  - `acs_schema_migrations` ledger와 SHA-256 checksum으로 적용 이력 및 변경된 migration 감지.
  - read-only migration status 조회.
- `app/sql/postgres/migrations/0001_generation_core.sql`
  - Generation Job, Execution, Event, Output, Idempotency, Outbox, Worker Heartbeat, Poll, Ops Alert/Delivery, Output Review/Export 등 13개 테이블.
  - FK, unique, index, lease columns 및 JSONB 타입.
  - Output Review/Export 이벤트 UPDATE/DELETE 차단 트리거.
  - 전체 앱 테이블 RLS 활성화. 아직 client policy를 만들지 않아 anon/authenticated 접근은 default-deny.
- `requirements.txt`: `psycopg[binary]>=3.2,<4.0` 추가.
- migration 구조 및 실행기 테스트 5개 추가.

## 2. 검증

- Backend pytest: **500 passed / 0 failed**.
- Python compileall (`app`, `tests`): PASS.
- Runtime OpenAPI snapshot: PASS.
- 테스트는 로컬에서 수행. PostgreSQL 서버 연결이나 Supabase schema 적용은 아직 수행하지 않음.

## 3. Supabase / Vercel 상태

BUILD-00214 읽기 전용 스모크 테스트 결과는 `docs/reports/BUILD-00214_SUPABASE_VERCEL_LIVE_SMOKE.md` 참조.
- Supabase 전용 테스트 프로젝트 ACTIVE_HEALTHY, private buckets 3개, advisors 0 lints.
- 아직 app tables, Storage object policies, test users, objects 없음.
- Vercel 기존 Production bootstrap deployment READY, `/`와 `/health` HTTP 200.
- Vercel Preview deployments 0. 전체 앱 소스 미배포.
- BUILD-00215에서는 외부 프로젝트 변경 없음.

## 4. 미완료 / 안전장치

- PostgreSQL runtime Repository Adapter: 미구현. `DATABASE_BACKEND=postgresql` 선택은 계속 거부됨.
- Migration 0001: 로컬 SQL 구조 테스트만 완료. Supabase 테스트 DB 적용 전.
- `FOR UPDATE SKIP LOCKED` lease claim 구현 및 multi-worker 경합 검증: 미완료.
- tenant membership/RLS policies: 미완료. 현재 RLS default-deny 상태로 앱 사용자 접근 불가.
- Supabase Storage application adapter 및 object policies: 미완료.
- Vercel source-backed Preview deployment: 미배포.
- Browser React/Three E2E, 실제 GLB render: 미검증.
- Real AI generation: 미실행; mock 기본.

## 5. 다음 자율 작업

1. SQLite aggregate query inventory와 PostgreSQL schema 컬럼/상태 parity 대조.
2. PostgreSQL transaction adapter와 row mapping 구현.
3. Job create/get/idempotency/transition을 먼저 PostgreSQL로 구현하고 contract tests 작성.
4. Outbox/Poll/Alert claim에 `FOR UPDATE SKIP LOCKED` + lease ownership fencing 구현.
5. 로컬 PostgreSQL 컨테이너가 가능한 환경인지 확인하고 실제 DB integration tests 준비.
6. 핵심 aggregate contract가 통과하면 Supabase 테스트 프로젝트에 schema를 배치 적용하고 advisors 재검사.
7. 이후 Storage adapter와 Vercel Preview source deployment 진행.

## 6. 운영 원칙

- SQLite 기본 동작 유지; PostgreSQL 자동 전환 금지.
- 운영 Supabase와 Vercel Production 변경 금지.
- 실환경 테스트는 기능 단위로 묶어 실행.
- 로컬/Mock 검증과 실환경 검증을 구분.
- 비밀값은 소스·문서·로그·채팅에 기록하지 않음.
