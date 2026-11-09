# AI CREATOR STUDIO v0.15 — Manual Reconciliation & Worker Operations

This package builds on v0.14 and adds an audited, workspace-admin-only manual reconciliation workflow for ambiguous provider submissions, worker heartbeat persistence, worker/outbox health diagnostics, and FASHN's documented secondary output CDN host.

## Backend setup

```bash
cd ai_creator_studio_backend_starter
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

In a second terminal:

```bash
cd ai_creator_studio_backend_starter
. .venv/bin/activate
python -m app.worker
```

Configure unique `ASSET_API_TOKENS` and `ASSET_SIGNING_SECRET` before exposing the service. Set `GENERATION_DATABASE_PATH` to a durable DB path shared by API and worker. If omitted, `ASSET_DATABASE_PATH` is reused. Configure `WORKER_STALE_AFTER_SECONDS` for the health threshold.

## New operational endpoints

- `GET /health`: liveness plus aggregate worker heartbeat/outbox summary; it does not expose tenant/job details.
- `GET /internal/ops/workers`: workspace owner/admin-only worker heartbeat and outbox diagnostics.
- `POST /v1/generation-jobs/{job_id}/reconciliation`: workspace owner/admin-only manual resolution of `needs_reconciliation`.

Reconciliation actions:

1. `attach_request_id`: use only after locating the accepted prediction in provider request history. The known provider ID is attached and normal status polling can resume.
2. `confirm_not_submitted`: use only after verifying that the provider did not accept the prior request. This explicitly authorizes a new execution attempt and outbox event.

Both actions require a reason (12–1000 characters) and append an actor-attributed job event. No automated code path performs either action.

Example request:

```json
{
  "action": "attach_request_id",
  "provider_request_id": "provider-prediction-id",
  "reason": "Located the accepted prediction in provider request history."
}
```

## Provider support boundary

FASHN's public API documents `POST /v1/run` returning a prediction ID and `GET /v1/status/{id}` for status polling. Its public documentation does not specify a client-supplied idempotency key or lookup by an AI CREATOR STUDIO correlation key. Therefore FASHN is currently declared as not supporting those two capabilities in this adapter, and ambiguous POST outcomes are not automatically replayed. Provider request history may be inspected by an authorized operator; no unsupported API lookup endpoint is assumed.

FASHN documentation lists both `cdn.fashn.ai` and `media.fashn.ai` as official output delivery hosts; both are included in the default allowlist. Webhooks are not enabled because the public guide recommends verification but does not provide a verifiable signing contract in the integration evidence used for this version.

## Tests

```bash
PYTHONPATH=. pytest -q
python -m compileall -q app tests
```

## Limitations

- SQLite single-node PoC; PostgreSQL, HA, and multi-instance locking remain unverified.
- Heartbeat is a DB self-report, not an external supervisor; no alert delivery or process orchestration is included.
- Provider status polling remains triggered by authenticated Job reads; a dedicated polling worker is not yet implemented.
- Manual reconciliation depends on an operator accurately checking provider history. It is an auditable control, not an automatic guarantee.
- No real paid-provider call, OS process-kill campaign, multi-process load, backup/restore, or Android deployment test was run.

## Official provider references checked (2026-11-02)
- API fundamentals: https://docs.fashn.ai/api-overview/api-fundamentals
- Data retention and privacy: https://docs.fashn.ai/api-overview/data-retention-privacy
- Webhooks: https://docs.fashn.ai/api-overview/webhooks
