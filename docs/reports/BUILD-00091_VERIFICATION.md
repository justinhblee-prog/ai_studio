# BUILD-00091 Verification Report

## Summary

- Backend pytest: **290 passed**
- Asset API tests: **26 passed**
- Python compileall: **PASS**
- Viewer offline structural checks: **21/21 PASS**
- OpenAPI route/schema audits: regenerated; exact contract match remains **false**
- TypeScript typecheck: **NOT VERIFIED** (missing React/Three.js runtime packages and type declarations)
- Browser/WebGL/Android E2E: **NOT VERIFIED**
- Live Provider generation: **NOT RUN**

## Commands and evidence

Run from `ai_creator_studio_backend_starter/`:

```bash
python -m pytest -q
python -m compileall -q app scripts tests
python scripts/audit_openapi_contract.py --spec ../../docs/product-baseline/AI_CREATOR_STUDIO_openapi_integrated_draft_v0_2.yaml --runtime-output ../docs/reports/BUILD-00091_runtime-openapi.json --output ../docs/reports/BUILD-00091_openapi-contract-drift.json
python scripts/audit_openapi_runtime.py --spec ../../docs/product-baseline/AI_CREATOR_STUDIO_openapi_integrated_draft_v0_2.yaml --output ../docs/reports/BUILD-00091_openapi-runtime-drift.json
```

Run from `ai_creator_studio_3d_viewer/`:

```bash
python scripts/validate_source.py
npm run typecheck
```

`npm run typecheck` was attempted and failed because `react`, `three`, `react/jsx-runtime`, and their type declarations are not installed. The resulting TypeScript diagnostics are dependency-resolution failures; no TypeScript pass is claimed.

## Restore-specific regression coverage

- Successful restore verifies that v1 bytes can be selected after v2 became current, but restoration creates v3 with a new version ID/storage artifact.
- The original v1 and v2 historical files remain byte-for-byte unchanged.
- Current Asset checksum and `is_current` marker point to v3 after restoration.
- Corrupted or missing historical bytes return HTTP 409 and do not create a version or mutate current metadata.
- Workspace viewer role receives HTTP 403; unknown version receives HTTP 404.
- Provenance records `asset.version_restored` with source version and previous current version metadata.

## OpenAPI audit result

- Design paths: 13
- Runtime paths: 30
- Runtime-only paths include `/assets/{asset_id}/versions/{version_id}/restore`.
- Design-only paths: 5 (credits account, ledger, job executions, job outputs, quotes).
- Structural contract drifts: 10 of 15 matched design operations.
- The imported design YAML was not modified to force a match.

## Scope limitations

This build is tested only against SQLite and local private filesystem. It does not prove filesystem/DB crash atomicity, PostgreSQL, multi-host behavior, object storage, production identity, browser/WebGL runtime, Android E2E, or production readiness. Actual FASHN generation was not run; Mock flow tests are not provider evidence. Credit persistence and release gates G0-G5 remain unimplemented/unpassed.
