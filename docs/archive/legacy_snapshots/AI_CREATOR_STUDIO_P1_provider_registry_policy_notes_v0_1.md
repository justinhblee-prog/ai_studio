# AI CREATOR STUDIO — Provider Capability / Policy Registry Notes v0.1

- Date: 2026-11-02
- Source baseline: v0.15
- Output: v0.16 Provider Registry / Manual Policy Gate

## Delivered

1. Added a versioned static Provider / Model / Capability registry (`app/provider_registry.py`).
2. Registered Mock `mock-tryon` as flow-test-only; it is not production eligible and does not claim image generation.
3. Registered FASHN `tryon-v1.6` and `tryon-max` as `DOCUMENTED` / `PENDING_CONTRACT_TEST`; official API fundamentals are attached as evidence references. Both remain `production_eligible=false` until contract, rights, retention, usage and live verification gates are met.
4. Added explicit MANUAL routing resolution and disabled AUTO routing until PO-approved scoring/fallback rules exist.
5. `get_provider()` now applies registry/policy checks before constructing a real adapter. FASHN production dispatch is blocked at this stage; no automatic provider fallback exists.
6. Added adapter-side `describe_capabilities()` and `validate_request()` hooks. Validation executes before Job/Execution/Outbox persistence.
7. Added public capability metadata endpoint `GET /v1/engines/capabilities` and owner/admin-only operational registry endpoint `GET /internal/ops/provider-registry`.
8. Added tests for verification state/evidence, FASHN dispatch gate, AUTO routing block, ops RBAC and pre-persistence adapter validation.

## Validation evidence

- Backend pytest: **75 passed**.
- `python -m compileall -q app tests`: passed.
- FastAPI OpenAPI: **18 paths**; both new endpoints present.
- 3D Viewer source structural validation: **19/19 passed**.

## Important interpretation

- This is a static code-backed registry PoC, not a database-administered registry or approval workflow.
- FASHN remains documented only. The current repo does not contain a live/sandbox provider contract run or verified commercial-rights/data-retention/usage approval. The policy gate intentionally prevents production dispatch rather than treating payload-shape unit tests as live verification.
- Mock remains available solely for API/worker flow tests. Its `CONTRACT_TESTED` state applies only to the local mock contract, not to a real generation capability.
- AUTO routing is explicitly disabled. No scoring weights, tie-breakers or fallback policy have been invented.
- `PROVIDER_MODE` is the manually selected provider identifier; `PROVIDER_ROUTING_MODE` defaults to `MANUAL`.
- Existing FASHN adapter request/response implementation remains present but is not production-routable until evidence and approval promote the registry record.
- Provider status polling still occurs in the Job GET path; dedicated polling worker, rate-limit-aware backoff, PostgreSQL and multi-instance concurrency remain next tasks.

## API changes

- `GET /v1/engines/capabilities`: public registry snapshot, including verification status, capability flags and evidence references.
- `GET /internal/ops/provider-registry`: authenticated workspace owner/admin diagnostics.
- When `PROVIDER_ROUTING_MODE=AUTO`, Job creation returns `409 AUTO_ROUTING_NOT_APPROVED`.
- When `PROVIDER_MODE=fashn` before required verification, Job creation returns `503 PROVIDER_NOT_PRODUCTION_READY`.
- Adapter validation errors return `422 VALIDATION_ERROR` before a Job or Outbox row is created.

## QA traceability

- PRV-01/02: adapter hooks and pre-persistence validation.
- PRV-04: unverified/suspended/production eligibility gate.
- PRV-12: MANUAL-only selection; no fallback.
- PRV-13/14/15/16: AUTO routing/fallback remain disabled pending approval; not claimed as passed.
- PRV-22/23: live Provider and rights verification remain open.
- T-01..T-14 definitions unchanged. This milestone does not upgrade any global T-09/T-12/T-13/T-14 status.
