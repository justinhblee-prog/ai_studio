# AI CREATOR STUDIO v0.18 — Provider Poll Worker + Admin Recovery

Dedicated durable Provider status polling and output persistence worker layered on v0.17.

## Validation
- Backend pytest: 92 passed
- Python compileall: passed
- FastAPI OpenAPI: 20 paths
- API version: 0.6.0
- 3D Viewer structural validation: 19/19 passed

## Run the three processes

```bash
# API
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Provider submission / transactional outbox
python -m app.worker

# Provider status polling / output persistence
python -m app.poll_worker
```

All processes must share the same configured SQLite database and private output storage volume.

## Poll controls

Defaults: 2s base exponential backoff, 300s max backoff, 12 attempts, and 900s maximum accepted standard `Retry-After` header. Job GET is read-only.

## Poll task operations

Workspace owner/admin operations:
- `GET /internal/ops/poll-tasks?workspace_id=<id>&status=needs_reconciliation`
- `POST /internal/ops/poll-tasks/{task_id}/retry` with `workspace_id` and an operator reason.

The retry endpoint resumes only the persisted status-GET or output-persistence phase. It never replays Provider submission POST.

## Important
FASHN remains documented but not production-eligible. Mock is flow-test-only. AUTO routing is disabled. SQLite and local output storage remain PoC-only; PostgreSQL, multi-instance coordination, production alerting, live Provider verification, and Credit Ledger integration remain open.

See `AI_CREATOR_STUDIO_P1_provider_poll_worker_notes_v0_2.md` and handoff v3.1.
