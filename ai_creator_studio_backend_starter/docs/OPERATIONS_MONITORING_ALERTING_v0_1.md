# AI CREATOR STUDIO — Operations Metrics & Alerting Notes v0.1

- Date: 2026-11-02
- Source baseline: v0.18 Provider Poll Worker + Admin Recovery
- Output: v0.19 Operations Monitor, metrics, durable alerts and optional webhook delivery
- Backend API version: 0.7.0
- Status: Local operational monitoring slice implemented; external monitoring and production alert routing remain unconfigured.

> **2026-11-17 갱신 메모 (B-03 점검)**: 아래 시험 수치(pytest 99, OpenAPI 22 paths 등)는 **2026-11-02 기준의 옛 값**이며 현재 저장소와 다릅니다(현재 수치는 각 PR의 CI 기록 참조). 경보 규칙은 아래 5개뿐이고 5xx·429·백업·파기 실패 경보는 **없음**(확장 예정). 외부 수신처·업타임 감시는 **미설정(NEED_USER)**, 실서버 `/internal/ops/metrics` 동작은 **미확인**. 증상별 대응은 `docs/RUNBOOK.md` 5-1.

## 1. Delivered

1. Added schema migration v5 with durable `generation_ops_alerts` and `generation_ops_alert_deliveries` tables.
2. Added operational snapshot aggregation for worker heartbeats, outbox/poll queue counts, oldest due work age, active/resolved alert counts, and webhook delivery state.
3. Added alert evaluation for missing/stale required worker types, old due outbox/poll work, outbox submission reconciliation backlog, and poll/output reconciliation backlog.
4. Alert fingerprints deduplicate repeated observations; alerts are resolved when the condition clears and can reopen if the same condition returns.
5. Added independent `python -m app.monitor_worker` process. It evaluates alerts, updates its heartbeat and dispatches at most one webhook delivery per loop.
6. Optional HTTPS webhook delivery uses a configured bearer token, bounded attempts, exponential retry delay and a two-minute claim recovery window.
7. Webhook payload contains operational alert metadata only; it excludes job payloads, image URLs, source images and user identifiers.
8. Added owner-facing operational routes restricted to explicit platform operator IDs (`OPS_ADMIN_USER_IDS`), not ordinary tenant workspace admins.
9. Added Prometheus text exposition at `/internal/ops/metrics`; endpoint remains bearer-authenticated and platform-operator-only.
10. Added `.env.example` and runtime documentation for thresholds, required worker types and webhook configuration.

## 2. Validation evidence

- Backend pytest: **99 passed**.
- `python -m compileall -q app tests`: passed.
- FastAPI OpenAPI: **22 paths**.
- Backend API version: **0.7.0**.
- 3D Viewer structural validation: **19/19 passed**.
- Alert tests cover worker stale detection/resolution, newest heartbeat selection, queue age, reconciliation backlog, webhook HTTPS enforcement, sanitized payload, successful delivery, bounded failure retries and platform-operator authorization.

## 3. Alert rules

| Fingerprint | Severity | Trigger |
|---|---|---|
| `worker:<type>:stale` | critical | Required worker heartbeat missing or older than `OPS_ALERT_WORKER_STALE_SECONDS` |
| `queue:outbox:age` | warning | Oldest due pending/processing outbox work exceeds `OPS_ALERT_QUEUE_AGE_SECONDS` |
| `queue:poll:age` | warning | Oldest due pending/processing poll work exceeds `OPS_ALERT_QUEUE_AGE_SECONDS` |
| `outbox:needs_reconciliation` | critical | One or more ambiguous Provider submission outbox tasks need human reconciliation |
| `poll:needs_reconciliation` | warning | One or more Provider polling/output tasks need operator review |

Queue age uses `available_at` for pending tasks and `claimed_at` (or creation time) for processing tasks. Future-backoff tasks are not treated as overdue before their due time.

## 4. Runtime topology

Run four independent processes against the same configured SQLite database and private output volume:

```bash
# 1 — API
uvicorn app.main:app --host 0.0.0.0 --port 8000

# 2 — Provider submission / transactional outbox worker
python -m app.worker

# 3 — Provider status polling / output persistence worker
python -m app.poll_worker

# 4 — Operational monitor / optional webhook delivery
python -m app.monitor_worker
```

A process supervisor (systemd, Docker restart policy, Kubernetes, etc.) is still required to restart a crashed monitor. The monitor cannot reliably alert on its own complete absence; external process supervision is a required layer.

## 5. Configuration

- `OPS_ADMIN_USER_IDS`: comma-separated platform operator user IDs. Empty by default. Workspace owner/admin membership does **not** grant global operations access.
- `REQUIRED_WORKER_TYPES`: default `outbox,provider_poll`.
- `OPS_ALERT_WORKER_STALE_SECONDS`: default 45.
- `OPS_ALERT_QUEUE_AGE_SECONDS`: default 120.
- `OPS_MONITOR_POLL_SECONDS`: default 5.
- `OPS_ALERT_WEBHOOK_URL`: optional HTTPS endpoint; unset means alerts are persisted locally only and no webhook delivery is attempted.
- `OPS_ALERT_WEBHOOK_TOKEN`: optional bearer token; do not embed credentials in the URL.
- `OPS_ALERT_WEBHOOK_TIMEOUT_SECONDS`: default 5.
- `OPS_ALERT_WEBHOOK_MAX_ATTEMPTS`: default 8.

Webhook delivery is at-least-once. A receiver should deduplicate by `alert_id` or `fingerprint`, because a remote endpoint may accept a request while the sender loses the response.

## 6. Operations endpoints

- `GET /internal/ops/workers` — worker heartbeat diagnostics.
- `GET /internal/ops/metrics` — Prometheus text exposition (authenticated; platform operator only).
- `GET /internal/ops/alerts?status=active&limit=100` — operational snapshot and alert list.
- Existing workspace-scoped poll task listing/retry routes remain workspace owner/admin scoped.

Metric families include `acs_worker_healthy`, `acs_outbox_tasks`, `acs_poll_tasks`, `acs_oldest_pending_outbox_age_seconds`, `acs_oldest_pending_poll_age_seconds`, and `acs_ops_alerts`.

## 7. Important limitations / not claimed

- No webhook endpoint has been configured or tested against an external production service. Delivery was validated with mocked HTTP transport only.
- No Prometheus server, Grafana dashboard, PagerDuty, Slack or email destination has been provisioned.
- Metrics endpoint requires platform operator bearer authentication; Prometheus scrape credentials and network policy must be configured by deployment operators.
- SQLite/WAL remains a single-host PoC. PostgreSQL, multi-host locking, HA and backup/restore are not implemented.
- Monitor process supervision remains external. Monitor heartbeat cannot detect a process that never starts without an independent external watchdog.
- No dedicated visual admin UI was added.
- FASHN live contract/rights/retention/commercial-use verification remains open; no live Provider call was made.
- Credit Quote / append-only Credit Ledger remains unimplemented.
- TypeScript compile, browser/WebGL E2E, Android E2E and production deployment remain unverified.

## 8. Security decisions

- Global worker/metrics/alert/registry diagnostics are now restricted by explicit `OPS_ADMIN_USER_IDS` allowlist. This prevents a tenant workspace admin from seeing global operational state.
- Webhook URL must use HTTPS and may not contain embedded username/password credentials. Redirect following is disabled.
- Webhook token is sent in Authorization header only.
- Alert detail payloads contain bounded operational metadata and no customer/job input content.
- Webhook payload delivery is at-least-once; receivers must deduplicate.

## 9. QA traceability

- T-09: Poll worker status handling remains isolated; operations telemetry now exposes queue age and worker health. Live Provider contract evidence remains open.
- T-12: Provider/model selection remains MANUAL and no silent rerouting is introduced.
- T-13: Outbox atomicity remains covered; operational monitor observes reconciliation backlog without auto-replaying Provider POST.
- T-14: Output persistence remains in poll worker; alerting observes output/poll tasks awaiting operator review.
- Existing T-01..T-14 definitions are unchanged. Targeted passing tests do not imply global QA closure.
