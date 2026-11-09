# AI CREATOR STUDIO — Handoff v3.2

- Date: 2026-11-02
- Latest source: `AI_CREATOR_STUDIO_v0_19_ops_monitoring_alerting.zip`
- Previous baseline: v0.18 Provider Poll Worker + Admin Recovery
- Backend API version: 0.7.0
- Status: Operations monitoring/alerting slice implemented; PostgreSQL and production operations remain open.

## 1. v0.19 completion

- Added migration v5: durable operational alerts and webhook delivery queue.
- Added operational snapshot metrics for worker health, outbox/poll counts, due queue age and alert delivery status.
- Added alert rules for missing/stale workers, overdue queues and reconciliation backlog.
- Added independent `python -m app.monitor_worker` process.
- Added optional HTTPS webhook delivery with bearer token, bounded retry and claim recovery.
- Added `/internal/ops/metrics` and `/internal/ops/alerts`.
- Global operations diagnostics (workers, metrics, alerts, provider registry) now require explicit `OPS_ADMIN_USER_IDS`; tenant workspace admin is not enough.
- Existing workspace-scoped poll-task routes remain owner/admin protected within their workspace.
- API version incremented to 0.7.0.

## 2. Validation

- Backend pytest: 99 passed.
- Python compileall: passed.
- OpenAPI: 22 paths.
- 3D Viewer structural checks: 19/19 passed.
- See `AI_CREATOR_STUDIO_P1_ops_monitoring_alerting_notes_v0_1.md`.

## 3. Process topology

1. API: `uvicorn app.main:app --host 0.0.0.0 --port 8000`
2. Submission worker: `python -m app.worker`
3. Provider poll/output worker: `python -m app.poll_worker`
4. Operations monitor: `python -m app.monitor_worker`

All processes must share the same SQLite database and private output volume. A process supervisor is required for monitor restart; it cannot alert on its own complete absence.

## 4. Configuration

- `OPS_ADMIN_USER_IDS`: comma-separated platform operator IDs; empty by default.
- `REQUIRED_WORKER_TYPES=outbox,provider_poll`
- `OPS_ALERT_WORKER_STALE_SECONDS=45`
- `OPS_ALERT_QUEUE_AGE_SECONDS=120`
- `OPS_MONITOR_POLL_SECONDS=5`
- `OPS_ALERT_WEBHOOK_URL`: optional HTTPS endpoint; unset disables outbound delivery.
- `OPS_ALERT_WEBHOOK_TOKEN`: optional bearer token.
- `OPS_ALERT_WEBHOOK_TIMEOUT_SECONDS=5`
- `OPS_ALERT_WEBHOOK_MAX_ATTEMPTS=8`

Webhook delivery is at-least-once; receiver deduplication by `alert_id` is required.

## 5. Existing constraints retained

- FASHN models remain DOCUMENTED / PENDING_CONTRACT_TEST, not production eligible.
- Mock remains flow-test-only.
- AUTO routing/fallback remain disabled.
- Provider submission ambiguity is never automatically replayed.
- T-01..T-14 definitions are unchanged.
- SQLite/local filesystem remains a PoC; PostgreSQL, distributed locking and object storage remain open.
- Credit Quote / append-only Credit Ledger remains open.

## 6. Open risks

- No external webhook service has been configured; delivery was tested with mocked transport only.
- No Prometheus/Grafana/PagerDuty/Slack/email integration is provisioned.
- Prometheus metrics require authenticated scraping and network controls.
- Monitor process absence requires external process supervision.
- No dedicated visual admin UI.
- No live FASHN contract/rights/retention/commercial-use evidence.
- Browser/WebGL, TypeScript, Android E2E and production deployment remain unverified.

## 7. Next sequence (owned by engineering)

1. PostgreSQL repository adapter and migration path.
2. Cross-process/instance lock and claim semantics tests.
3. Production metrics scrape and webhook delivery deployment validation.
4. Provider transport timeout/malformed JSON/terminal failure tests.
5. FASHN G2 verification and explicit approval.
6. Credit Quote / Ledger integration.

## 8. Key implementation paths

- `ai_creator_studio_backend_starter/app/monitor_worker.py`
- `ai_creator_studio_backend_starter/app/job_repository.py`
- `ai_creator_studio_backend_starter/app/main.py`
- `ai_creator_studio_backend_starter/app/worker.py`
- `ai_creator_studio_backend_starter/app/poll_worker.py`
- `ai_creator_studio_backend_starter/tests/test_api.py`
