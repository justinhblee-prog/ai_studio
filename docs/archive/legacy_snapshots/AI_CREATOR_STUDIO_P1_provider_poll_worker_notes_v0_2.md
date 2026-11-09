# AI CREATOR STUDIO — Provider Poll Worker / Retry Controls Notes v0.1

- Date: 2026-11-02
- Source baseline: v0.16 Provider Capability / Policy Registry
- Output: v0.18 Dedicated Provider Poll Worker + Admin Recovery
- Backend API version: 0.6.0

## 1. Delivered

1. Added durable `generation_poll_tasks` table (schema migration version 4), with `status` / `persist_output` phases, bounded attempt counter, due time, lease owner/expiry, and last error.
2. Provider submission remains in `python -m app.worker`; successful submission atomically creates the poll task with the Job transition to `running`.
3. Added independent `python -m app.poll_worker` process for Provider status GET, output persistence, and final Job completion.
4. Removed all Provider status calls and output downloads from `GET /v1/generation-jobs/{job_id}`. Job GET is now a read-only status resource.
5. Provider success transition (`running` -> `post_processing`) and poll-task phase handoff (`status` -> `persist_output`) are committed in one SQLite transaction to avoid a crash window.
6. Poll lease expiry requeues safe status GET / output tasks. Provider submission outbox expiry remains `needs_reconciliation`; POST is never automatically replayed because provider acceptance may be ambiguous.
7. Added bounded exponential backoff: defaults are 2 seconds base, 300 seconds maximum backoff, 12 attempts, and 900 seconds maximum accepted `Retry-After`.
8. FASHN status adapter parses the standard `Retry-After` HTTP response header (delta seconds or HTTP date). HTTP 429 and 5xx are retryable; other HTTP status errors are not automatically retried. No JSON body field is treated as Retry-After.
9. Added atomic local output replacement (temporary file + fsync + replace) so concurrent/retried output persistence does not expose a partially written file.
10. Worker diagnostics now include poll task counts; `/health` and owner/admin `/internal/ops/workers` expose those counts.
11. Worker resolves the exact provider/model recorded on each Job and refuses silent provider/model rerouting if runtime configuration differs.
12. Manual reconciliation `attach_request_id` now creates/resets the durable poll task in the same transaction as attaching the request ID.
13. Added workspace-scoped owner/admin operations to list poll tasks and manually requeue tasks in `needs_reconciliation`.
14. Manual poll retry is phase-aware (`status` GET or `persist_output` only), resets the bounded retry budget, records actor/reason in Job Event history, and never inserts or replays a Provider submission Outbox event.

## 2. Validation evidence

- Backend pytest: **92 passed**.
- `python -m compileall -q app tests`: passed.
- FastAPI OpenAPI: **20 paths**.
- API version: **0.6.0**.
- 3D Viewer structural validation: **19/19 passed**.
- Source grep confirms Provider `.status()` is called only in `app/poll_worker.py`; API Job GET no longer performs Provider I/O.

New/expanded tests cover:
- read-only Job GET and durable poll task state;
- separate poll worker status -> output -> succeeded flow;
- poll lease expiry and safe requeue;
- atomic task handoff on Provider success;
- bounded exponential backoff and Retry-After cap;
- parsing standard Retry-After headers, mocked FASHN HTTP transport, and retryability classification;
- atomic private output file replacement;
- poll retry budget exhaustion to `needs_reconciliation`;
- no silent provider/model rerouting in both submission and polling workers;
- manual request-ID attachment scheduling a poll task;
- workspace-scoped owner/admin poll task listing;
- manual retry of status and output-persistence phases without Provider POST replay;
- retry rejection for tasks not awaiting operator review.

## 3. Runtime process topology

Run three independent processes against the same configured SQLite database and private output directory:

```bash
# Terminal 1 — API
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Terminal 2 — Provider submission / transactional outbox worker
python -m app.worker

# Terminal 3 — Provider status polling / output persistence worker
python -m app.poll_worker
```

All processes must share the same database path and storage volume. The poll worker is not launched by the API process.

## 4. Operational semantics

- `generation_poll_tasks.status`: `pending`, `processing`, `completed`, `needs_reconciliation`.
- `phase`: `status` or `persist_output`.
- Retry budget exhaustion does not fabricate a terminal Provider failure. The Job remains `running` or `post_processing`, receives an explicit review error code, and the poll task moves to `needs_reconciliation`.
- A Provider HTTP 429 or 5xx may be retried with exponential backoff. A verified `Retry-After` response header can extend the delay, bounded by the configured maximum.
- A non-retryable Provider HTTP response moves the task to operator review; it is not silently treated as a successful result.
- Submission POST ambiguity remains a manual reconciliation concern, distinct from safe status GET retries.
- Output files are written atomically to the private local output directory; metadata is persisted before the Job reaches `succeeded`.

## 5. Important limitations / not claimed

- FASHN remains `DOCUMENTED` / `PENDING_CONTRACT_TEST` and is still blocked by the Provider Registry from production dispatch. No live FASHN request was made in this milestone.
- SQLite/WAL is still a single-host PoC store. PostgreSQL, multi-host worker locking, HA, and production backup/restore are not implemented.
- Local output storage is not S3/object storage; shared volume configuration is required if processes run in separate containers.
- No webhook ingestion, Provider cancel, or customer-facing live progress push was added.
- Poll retry exhaustion has a workspace-scoped owner/admin list and retry API, but no dedicated visual admin UI yet.
- Worker heartbeat is operational telemetry, not a complete metrics/alerting integration. No PagerDuty/email/Slack alert has been configured.
- TypeScript compilation, browser/WebGL E2E, Android E2E, and live provider tests remain unverified.
- Credit Quote / append-only Credit Ledger remains unimplemented.

## 6. QA traceability

- T-09: Provider status polling is now isolated in a worker and transport header parsing is unit-tested; live Provider contract evidence remains open.
- T-12: provider/model selection remains MANUAL and the poll worker refuses silent rerouting; AUTO routing remains disabled.
- T-13: Job + Outbox atomic insertion remains covered; Provider success + poll phase handoff is additionally transactional.
- T-14: output metadata-before-SUCCEEDED remains enforced; output persistence retry now occurs in the durable poll worker.
- Existing T-01..T-14 definitions are unchanged. Targeted passing tests do not imply all global QA gates are closed.

## 7. Next engineering priorities

1. Add metrics and alert delivery for stale poll workers, queue age, exhausted tasks, and output persistence failures.
2. Add PostgreSQL repository implementation and cross-process/instance concurrency tests.
3. Expand Provider transport contract tests for timeout, malformed JSON, and terminal failure.
4. Complete FASHN rights, retention, commercial usage, pricing and live/sandbox verification before promoting its Registry record.
5. Integrate Credit Quote / append-only Credit Ledger before paid generation is enabled.
