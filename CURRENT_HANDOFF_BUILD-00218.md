# AI CREATOR STUDIO — CURRENT HANDOFF BUILD-00218

- 작성일: 2026-11-06
- 기준 소스: BUILD-00216
- Engineering build: **BUILD-00218**
- 상태: PostgreSQL Job / Outbox / Poll / Operations의 초기 adapter vertical slice 구현. SQLite는 기본/유일 활성 backend. PostgreSQL runtime factory는 fail-closed 유지.

## 1. BUILD-00217/218 추가 구현

### PostgreSQL Poll adapter — `app/repositories/postgres_poll.py`
- `FOR UPDATE SKIP LOCKED` pending task claim.
- Poll lease expiry는 provider status GET / output persistence 작업이므로 pending으로 안전 재큐잉.
- Lease renewal은 task status + worker owner + 아직 만료되지 않은 lease를 모두 확인.
- Complete/reschedule/exhaust도 worker owner 및 live lease 조건으로 fencing.
- Retry budget exhaustion은 `needs_reconciliation`으로 격리하고 Job error/event를 같은 transaction에 기록.

### PostgreSQL Operations adapter — `app/repositories/postgres_operations.py`
- Worker heartbeat upsert.
- Alert delivery `SKIP LOCKED` claim.
- Alert delivery finish는 worker owner + live lease 확인 후 delivered/failed/retry 상태 처리.

## 2. 이전 PostgreSQL adapter 포함 범위

- Migration runner + 13개 핵심 테이블, RLS default-deny, append-only event triggers.
- Job: create/get/idempotency/list/transition/update/cancel/history.
- Outbox: atomic claim, lease-expiry quarantine, worker fencing, provider submission completion, Poll task enqueue, heartbeat.

## 3. 검증

- Backend pytest: **509 passed / 0 failed**.
- Python compileall (`app`, `tests`): PASS.
- Runtime OpenAPI snapshot: PASS.
- 추가 테스트는 SKIP LOCKED claim, expired lease, owner/expiry fencing, retry/reconciliation, heartbeat/delivery SQL 경계를 검증.
- 전부 controlled fake-connection/unit tests. 실제 PostgreSQL SQL 실행 또는 multi-instance race 검증으로 오인하지 말 것.

## 4. 활성화 제한 및 미완료

- `DATABASE_BACKEND=postgresql` 계속 비활성화; runtime factory fail-closed.
- PostgreSQL Asset/Output/Output Review, Workspace/Project/Product, Diagnostics/Operations Snapshot aggregate 미구현.
- Poll provider success/failure state transition 및 Output persistence path는 아직 완전 이식되지 않음.
- Supabase test DB schema migration 미적용; RLS tenant policies 미설계/미검증.
- Supabase Storage adapter/object policies 미구현.
- Vercel source-backed Preview 배포 미완료.
- Browser React/Three E2E, 실제 GLB 렌더, 실제 AI 생성 미검증.

## 5. 다음 연속 작업

1. PostgreSQL Poll provider-success/failure + Output persistence transaction 구현.
2. PostgreSQL Output/Asset metadata adapter 및 checksum/lifecycle parity.
3. Workspace membership/RBAC schema 및 tenant-safe RLS policy design.
4. SQLite/PostgreSQL 공통 repository contract suite 정리.
5. PostgreSQL 로컬 또는 Supabase test DB에 schema 적용 후 SQL/runtime/경합 테스트.
6. Storage adapter와 Vercel Preview source deployment.

## 6. 실환경 상태

BUILD-00214 읽기 전용 Supabase/Vercel 스모크 결과는 `docs/reports/BUILD-00214_SUPABASE_VERCEL_LIVE_SMOKE.md`. BUILD-00215~218에서는 외부 프로젝트 변경/배포 없음.
