# Viewer Response Contract Audit — BUILD-00117

## Purpose

This audit closes the response-schema gap for APIs consumed by the React Viewer. It checks Viewer `fetch()` endpoints against the actual FastAPI runtime OpenAPI document, including the Viewer source's narrow dynamic action branches.

## Coverage

| Measure | Result |
|---|---:|
| Viewer source files scanned | 7 |
| Unique Viewer endpoints | 48 |
| JSON success response endpoints with schema | 47 |
| Distinct Pydantic response models referenced | 27 |
| HTTP 204 no-body endpoints | 1 |
| Missing runtime routes | 0 |
| Missing JSON success schemas | 0 |
| Unresolved dynamic segments | 0 |

The sole no-body operation is `DELETE /v1/assets/{asset_id}` (204), which correctly has no JSON response payload.

## Response model coverage

- Asset list, Asset upload, AssetVersion list, AssetVersion upload/restore, signed preview URL
- Project list and detail; Character list
- Product list/detail and nested Variants; Project Product assignment list
- Photo Draft list/create/update/archive; Photo Run list and local-processing envelope; Photo output review and manifest
- Lookbook Draft list/create/update/archive; Lookbook output list/attach; assembly review/submit/approve/reject; package export list/create; plan/output manifests
- Generation Output list/review/decisions and metadata export manifest
- Shared event-list payloads

The full model reference list is in `ai_creator_studio_3d_viewer/docs/viewer_response_contract_audit.v1.json`.

## Important shape distinctions discovered

1. AssetVersion upload/restore responses are the current Asset record plus `version_id` and `version_number`; they are not the same shape as the AssetVersion history-list records.
2. Local Photo processing returns an envelope containing `run` and `output_asset`; it is not a bare PhotoRun record.
3. Lookbook package export returns integrity and rights-boundary metadata (`internal_use_only`, `publication_authorized`, `commercial_rights_verified`) in addition to the package reference.
4. Nullable source/version/review fields are explicitly modeled where the current runtime permits null.

These distinctions were confirmed by existing API integration tests. The implementation avoids forcing one model onto structurally different responses.

## Compatibility decisions

- No route path, method, query name, request body, authorization rule, or domain state transition was changed.
- Response models use Pydantic `extra="allow"` during this migration so existing additive metadata is retained rather than silently removed.
- The committed runtime OpenAPI snapshot is regenerated from the live FastAPI app, not hand-edited.
- This audit is static source/OpenAPI coverage. It does not prove every possible response instance, TypeScript compilation, or browser behavior.

## Reproduction

From `ai_creator_studio_3d_viewer/`:

```bash
python3 scripts/validate_viewer_response_contract.py
python3 scripts/validate_api_contract.py
python3 scripts/validate_viewer_request_contract.py
```

From `ai_creator_studio_backend_starter/`:

```bash
python scripts/export_runtime_openapi.py --check
python -m pytest -q tests/test_viewer_response_contract_audit.py tests/test_viewer_response_contracts_extended.py
python -m compileall -q app scripts tests
```

## Remaining validation gates

- Runtime payload fixture coverage for every Viewer success endpoint remains the next backend contract test improvement.
- TypeScript compilation needs installed React/Three.js packages and declarations.
- Browser/React/WebGL/Android execution remains unverified.
