# AI CREATOR STUDIO v0.19

v0.19 adds an independent operations monitor, durable operational alerts, Prometheus text metrics and optional HTTPS webhook delivery.

## Start the backend

Install dependencies and configure `ai_creator_studio_backend_starter/.env` from `.env.example`. Set `OPS_ADMIN_USER_IDS` to the user IDs allowed to access global operations diagnostics. This allowlist is empty by default; tenant workspace admins are not automatically platform operators.

Run four processes against the same database and private output volume:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
python -m app.worker
python -m app.poll_worker
python -m app.monitor_worker
```

## Operations

- `GET /internal/ops/workers`
- `GET /internal/ops/metrics`
- `GET /internal/ops/alerts?status=active`

All three require bearer authentication and membership in `OPS_ADMIN_USER_IDS`.

Alerts are persisted locally even when no webhook is configured. To deliver notifications, configure `OPS_ALERT_WEBHOOK_URL` with an HTTPS destination and optionally `OPS_ALERT_WEBHOOK_TOKEN`. Webhook delivery is at-least-once; receivers should deduplicate by `alert_id`.

See `AI_CREATOR_STUDIO_P1_ops_monitoring_alerting_notes_v0_1.md` for thresholds, security and limitations.

## Current boundaries

- SQLite/WAL and local filesystem remain single-host PoC infrastructure.
- PostgreSQL/multi-instance locking, production alert provider, dashboard, live FASHN contract verification and Credit Ledger are not complete.
- G2/G3 are not declared passed.
