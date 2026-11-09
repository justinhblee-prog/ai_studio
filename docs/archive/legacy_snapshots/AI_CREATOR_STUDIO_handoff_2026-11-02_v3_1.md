# AI CREATOR STUDIO — Handoff v3.1

- Date: 2026-11-02
- Latest source: `AI_CREATOR_STUDIO_v0_18_provider_poll_worker_admin_ops.zip`
- Previous baseline: v0.17 Dedicated Provider Poll Worker
- Backend API version: 0.6.0
- Status: Dedicated Provider Poll Worker implemented; G2/G3 remain open.

## 1. v0.18 completion

- Durable `generation_poll_tasks` schema (migration v4) added.
- Submission/outbox worker and Provider status/output worker are separate processes.
- Successful submission creates a durable poll task in the same transaction as the `running` Job transition.
- Job GET is read-only; it no longer calls Provider status or downloads output.
- Poll worker performs status GET, `running` reschedule, Provider terminal failure, output download, metadata persistence, and final `succeeded` transition.
- Provider success and poll phase handoff are atomic.
- Poll lease expiry requeues safe GET/output work; outbox POST ambiguity still requires manual reconciliation.
- Bounded exponential backoff and standard HTTP `Retry-After` parsing added.
- Local output file persistence uses atomic replacement.
- Poll task counts appear in worker health diagnostics.
- Exact Job provider/model mismatch blocks both submission and polling worker execution; no silent fallback/reroute.
- Manual request-ID attachment schedules polling.
- Added workspace-scoped owner/admin poll task listing and phase-aware retry API for `needs_reconciliation` tasks.
- Manual poll retry records actor/reason in Job Event history and never creates or replays a Provider submission POST.

## 2. Validation

- Backend pytest: 92 passed.
- Python compileall: passed.
- OpenAPI: 20 paths.
- API version: 0.6.0.
- 3D Viewer structural checks: 19/19 passed.
- See `AI_CREATOR_STUDIO_P1_provider_poll_worker_notes_v0_2.md`.

## 3. Process topology

1. API: `uvicorn app.main:app --host 0.0.0.0 --port 8000`
2. Submission worker: `python -m app.worker`
3. Poll/output worker: `python -m app.poll_worker`

All processes must share the same SQLite DB and output storage volume. Do not run multiple isolated local databases and expect workers to coordinate.

## 4. Configuration

New environment settings in backend `.env.example`:

- `POLL_WORKER_POLL_SECONDS=1.0`
- `POLL_WORKER_LEASE_SECONDS=90`
- `POLL_RETRY_BASE_SECONDS=2`
- `POLL_RETRY_MAX_SECONDS=300`
- `POLL_RETRY_MAX_ATTEMPTS=12`
- `POLL_RETRY_AFTER_MAX_SECONDS=900`

## 5. Existing constraints retained

- FASHN `tryon-v1.6` and `tryon-max` remain `DOCUMENTED` / `PENDING_CONTRACT_TEST`, not production eligible.
- Mock remains flow-test-only and does not generate images.
- AUTO routing/fallback remain disabled pending explicit PO policy approval.
- Provider submission ambiguity is not auto-replayed.
- T-01..T-14 definitions are unchanged; global QA closure is not implied by targeted tests.
- SQLite/local filesystem remains a PoC; PostgreSQL, distributed locks and object storage remain open.
- Credit Quote / append-only Credit Ledger remains open.

## 6. Open risks

- Poll task recovery is exposed as an owner/admin API, but a dedicated visual admin UI is not implemented.
- No alert delivery or external metrics backend is connected.
- No live FASHN contract/rights/retention/commercial-use evidence has been produced.
- No PostgreSQL or multi-instance concurrency verification.
- Browser/WebGL, TypeScript, Android E2E and production deployment are not verified.

## 7. Next sequence (owned by engineering)

1. Worker metrics and alerting.
2. PostgreSQL migration and multi-instance locking tests.
3. Provider transport contract tests with mocked HTTP behavior.
4. FASHN G2 verification and explicit approval.
5. Credit Quote / Ledger integration.

## 8. Key implementation paths

- `ai_creator_studio_backend_starter/app/poll_worker.py`
- `ai_creator_studio_backend_starter/app/worker.py`
- `ai_creator_studio_backend_starter/app/job_repository.py`
- `ai_creator_studio_backend_starter/app/providers/fashn.py`
- `ai_creator_studio_backend_starter/app/providers/base.py`
- `ai_creator_studio_backend_starter/app/main.py`
- `ai_creator_studio_backend_starter/tests/test_api.py`
