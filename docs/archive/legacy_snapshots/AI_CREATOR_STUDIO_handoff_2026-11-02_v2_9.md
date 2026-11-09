# AI CREATOR STUDIO — Handoff v2.9

- Date: 2026-11-02
- Latest source: `AI_CREATOR_STUDIO_v0_16_provider_registry.zip`
- Previous baseline: v0.15 Manual Reconciliation / Worker Operations
- Current status: Provider Capability / Policy Registry PoC implemented; G2/G3 remain open.

## 1. Completed in v0.16

- Static, versioned Provider / Model / Capability registry.
- Mock is explicitly flow-test-only, never a real image generation provider.
- FASHN `tryon-v1.6` and `tryon-max` are `DOCUMENTED` but `PENDING_CONTRACT_TEST`, not production eligible.
- MANUAL routing policy is explicit. AUTO routing is disabled until PO approval of scoring, tie-breakers and fallback.
- Provider selection now checks registry/policy before constructing real adapters.
- Adapter `describe_capabilities()` and `validate_request()` hooks added; validation runs before Job/Execution/Outbox persistence.
- Public capability snapshot and owner/admin operational registry endpoints added.
- Added tests for provider verification gates, AUTO disablement, RBAC and validation-before-persistence.

## 2. Validation

- Backend pytest: 75 passed.
- Python compileall: passed.
- OpenAPI: 18 paths.
- 3D Viewer structural checks: 19/19 passed.

Detailed report: `AI_CREATOR_STUDIO_P1_provider_registry_policy_notes_v0_1.md`.

## 3. Critical constraints / unresolved

- Registry is static code data; no DB-backed admin workflow, promotion approval or evidence attachment workflow yet.
- FASHN live/sandbox contract, rights, retention, usage and commercial-use approvals are not established. Real production dispatch is intentionally blocked.
- No AUTO routing or automatic fallback.
- FASHN adapter exists, but not promoted to production eligibility.
- Provider polling remains coupled to authenticated Job GET; separate poll worker is next.
- Rate-limit-aware backoff, worker alerts, PostgreSQL, multi-instance locks, full kill/restart campaigns, backup/restore and Android E2E remain unverified.
- Credit Quote / append-only Credit Ledger integration remains open.
- Existing QA T-01..T-14 definitions remain unchanged; do not overstate global PASS based on targeted tests.

## 4. Next sequence

1. Move Provider status polling from Job GET into a dedicated durable worker queue.
2. Add bounded exponential backoff and honor Provider `Retry-After` only when verified from response headers.
3. Add poll lease/recovery and worker heartbeat/metrics for poll tasks.
4. Add Provider contract tests with HTTP transport mocking, clearly separate from live G2 evidence.
5. Complete FASHN G2 rights/data/retention/pricing review and obtain explicit approval before registry promotion.
6. PostgreSQL migration and multi-instance concurrency verification.
7. Credit Quote / Ledger integration.

## 5. Key implementation paths

- `ai_creator_studio_backend_starter/app/provider_registry.py`
- `ai_creator_studio_backend_starter/app/providers/base.py`
- `ai_creator_studio_backend_starter/app/providers/fashn.py`
- `ai_creator_studio_backend_starter/app/providers/mock.py`
- `ai_creator_studio_backend_starter/app/main.py`
- `ai_creator_studio_backend_starter/tests/test_api.py`

## 6. API behavior changes

- `GET /v1/engines/capabilities` exposes capability verification metadata.
- `GET /internal/ops/provider-registry` requires owner/admin membership.
- `PROVIDER_ROUTING_MODE=AUTO` is rejected with `AUTO_ROUTING_NOT_APPROVED`.
- `PROVIDER_MODE=fashn` is blocked with `PROVIDER_NOT_PRODUCTION_READY` until required verification and approval.
- Adapter validation errors are returned before any Job/outbox persistence.

## 7. Operational command

Backend tests:

```bash
cd ai_creator_studio_backend_starter
python -m pytest -q
python -m compileall -q app tests
```

Viewer structural validation:

```bash
cd ai_creator_studio_3d_viewer
python scripts/validate_source.py
```
