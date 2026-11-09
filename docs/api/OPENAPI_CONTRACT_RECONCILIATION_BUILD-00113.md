# OpenAPI Contract Reconciliation — BUILD-00113

## Decision

The FastAPI-generated OpenAPI document is the authoritative description of **currently implemented runtime behavior**. The product-design draft `docs/product-baseline/AI_CREATOR_STUDIO_openapi_integrated_draft_v0_2.yaml` remains a target/design artifact and is not silently rewritten to pretend that unimplemented or structurally different behavior already exists.

A version-controlled runtime snapshot is stored at `docs/api/openapi.runtime.v1.json`. It is generated from `app.main:app.openapi()` and can be checked with:

```bash
cd ai_creator_studio_backend_starter
python scripts/export_runtime_openapi.py
python scripts/export_runtime_openapi.py --check
```

The snapshot test fails if routes, parameters, request/response schemas, operation IDs, security metadata, or other generated OpenAPI details change without review.

## Reconciliation rules

1. Existing runtime behavior is preserved in this build; no request/response envelope, status code, pagination, or authentication behavior is changed solely to match the design draft.
2. The 12 structurally different operations remain documented as drift against the design draft. These are not assumed to be harmless: each change must be reviewed against consumers before a runtime migration.
3. Generated FastAPI operation IDs are retained for now. Renaming them can break generated SDK method names and therefore requires an explicit SDK compatibility/release decision.
4. Runtime pagination currently uses `limit` + `offset` for generation-job listing; the design draft's `cursor` is not implemented. The runtime snapshot records the actual contract.
5. `Idempotency-Key` is accepted but optional for generation-job creation; this build does not silently make it required.
6. Cancellation accepts an optional request body and currently returns the existing Job response with HTTP 200. It only cancels queued work; it does not cancel an in-flight Provider request.
7. The three design operations `/credits/accounts/{account_id}`, `/credits/accounts/{account_id}/ledger`, and `/quotes` are absent at runtime. They remain deferred because credit reservation, ledger persistence, quote expiry/consumption, and billing policy are not approved. No placeholder endpoints are added.
8. Runtime-only endpoints are included in the runtime snapshot. Internal operations routes remain subject to their existing authorization dependencies; this document does not declare them public.

## Current structural audit (BUILD-00113)

The design draft has 13 path items and 15 operations. The runtime has 80 path items. The comparison reports 12 matched design operations with structural drift and 3 design operations with no runtime implementation. This is a structural comparison, not proof of semantic equivalence or runtime payload conformance.

## Deferred decisions

- Whether public responses should use a common `{data, meta}` envelope.
- Cursor pagination strategy and backward compatibility with `offset` clients.
- Whether quote creation and asset/project creation require idempotency keys.
- Stable public operation IDs and generated SDK compatibility policy.
- Credit account/ledger/quote semantics and persistence.
- Whether to split internal operations endpoints into a separate OpenAPI document.

No billing, PostgreSQL, Provider, or rights-policy decision is made by this reconciliation.
