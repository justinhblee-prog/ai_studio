# AI CREATOR STUDIO 개발 진행 기록 v0.15

## 기준 및 범위
- 기준: v0.14 Outbox / Recovery PoC
- 추가: provider ambiguity 수동 대조 API, worker heartbeat, 운영 진단, FASHN 공식 CDN host allowlist 보완

## 구현
- `ReconcileProviderSubmission` schema 추가: `attach_request_id` / `confirm_not_submitted`, 사유 필수
- `POST /v1/generation-jobs/{job_id}/reconciliation`: Workspace owner/admin만 수행 가능
- `attach_request_id`: provider request ID를 Job/Execution에 연결하고 outbox를 processed 처리, Job을 running으로 전이
- `confirm_not_submitted`: 기존 unknown outbox를 종결하고 다음 Execution attempt + 새 pending outbox를 생성
- 두 동작 모두 actor/reason/이전·신규 outbox ID를 Job Event에 기록
- 자동 retry 코드 경로에서는 reconciliation 함수를 호출하지 않음
- `generation_worker_heartbeats` 테이블 및 heartbeat upsert 추가
- Worker 실행 루프에서 DB heartbeat 갱신
- `/health`에 민감한 상세정보 없이 worker count/outbox count 요약 노출
- `/internal/ops/workers`는 Workspace owner/admin에게 상세 heartbeat 및 outbox 상태 제공
- FASHN output allowlist 기본값에 `media.fashn.ai` 추가
- Schema migration version 3 기록

## Provider contract 확인
- FASHN 공식 API 문서: `POST /v1/run`은 prediction ID를 반환하고 `GET /v1/status/{id}`로 조회
- 공개 문서상 고객 지정 idempotency key 또는 자체 correlation key로 prediction을 찾는 API 계약은 확인되지 않음
- 따라서 Adapter capability로 `supports_idempotency=False`, `supports_lookup_by_client_key=False` 선언
- 공식 데이터 전달 문서상 CDN 결과는 3일 후 만료 예정이며, `cdn.fashn.ai`와 `media.fashn.ai` 모두 공식 delivery domain
- FASHN webhook 문서는 webhook 사용과 재시도를 설명하지만, 현재 확인한 공개 가이드에는 검증 가능한 서명 규약이 명시되지 않아 이번 버전에서는 수신 endpoint를 구현하지 않음

## 검증 결과
- Backend pytest: 69 passed
- Python compileall: passed
- OpenAPI: 16 paths
- Viewer structural validation: 19/19 passed
- 수동 대조: request ID 연결, 미접수 확인 후 새 attempt 생성, viewer 권한 거부, 필수 필드 검증 테스트 포함
- Worker health: heartbeat healthy 판정 및 owner/admin 접근 제어 테스트 포함
- FASHN 공식 media CDN host allowlist 테스트 포함

## 남은 제한
- SQLite 단일 노드 PoC; PostgreSQL/HA/multi-instance lock 미검증
- Heartbeat는 Worker 자체 DB 보고; 외부 supervisor/alert delivery 미구현
- Status polling은 Job GET 요청에 종속; 별도 polling worker 미구현
- Manual reconciliation은 운영자가 FASHN request history를 확인해야 하며, operator 실수 위험은 남음
- 실제 유료 Provider, process kill, 네트워크 분리, 백업/복구, Android E2E 미실행
- T-09/T-12/T-13/T-14 전체 시나리오 PASS 아님; 기존 targeted test만 통과

## 다음 개발
1. Provider Capability/Policy Registry에 idempotency/lookup/webhook verification capability 정식 반영
2. FASHN status polling을 Worker task로 분리하고 rate-limit/backoff 적용
3. Worker supervisor, heartbeat timeout alert, dead-letter/reconciliation queue 운영 절차
4. PostgreSQL migration 및 multi-instance locking/lease 경합 테스트
5. Credit Quote/Ledger 원자적 reserve/commit/release/compensation 통합

## v0.16 Provider Capability / Policy Registry
- Added static versioned provider/model/capability registry and evidence references.
- Added MANUAL policy gate; AUTO disabled pending PO approval.
- FASHN entries remain DOCUMENTED / PENDING_CONTRACT_TEST and are blocked from production dispatch.
- Added adapter validation before Job/Outbox persistence and capability/ops endpoints.
- Backend tests 75 passed; compileall passed; OpenAPI 18 paths; Viewer structural checks 19/19.
- Details: AI_CREATOR_STUDIO_P1_provider_registry_policy_notes_v0_1.md; handoff v2.9.
