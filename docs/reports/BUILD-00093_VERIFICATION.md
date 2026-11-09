# BUILD-00093 Verification Report

## Automated checks

| Check | Result |
|---|---:|
| Backend pytest | 307 passed |
| Asset API + Photo Draft + Lookbook Draft tests | 43 passed |
| Python compileall | PASS |
| Viewer / Photo / Lookbook offline structural checks | 30/30 PASS |
| OpenAPI runtime inventory | 13 design paths / 39 runtime paths; exact match false |
| OpenAPI contract audit | 15 design operations; 10 structural drifts; 5 unmatched design operations |
| TypeScript typecheck | NOT VERIFIED — dependencies/type declarations absent |
| Browser/WebGL/Android E2E | NOT VERIFIED |
| Live FASHN / real Photo or Lookbook generation | NOT RUN / NOT VERIFIED |

## Commands

Backend, from `ai_creator_studio_backend_starter/`:

```bash
python -m pytest -q
python -m compileall -q app scripts tests
python scripts/audit_openapi_contract.py --spec ../../docs/product-baseline/AI_CREATOR_STUDIO_openapi_integrated_draft_v0_2.yaml --runtime-output ../docs/reports/BUILD-00093_runtime-openapi.json --output ../docs/reports/BUILD-00093_openapi-contract-drift.json
python scripts/audit_openapi_runtime.py --spec ../../docs/product-baseline/AI_CREATOR_STUDIO_openapi_integrated_draft_v0_2.yaml --output ../docs/reports/BUILD-00093_openapi-runtime-drift.json
```

Viewer, from `ai_creator_studio_3d_viewer/`:

```bash
python scripts/validate_source.py
npm run typecheck
```

`npm run typecheck` was attempted. It cannot resolve `react`, `react/jsx-runtime`, `three`, or Three.js addon modules/types because `node_modules` is absent. TypeScript errors caused by missing modules/JSX types are not counted as a pass. No network dependency installation was performed in this build.

## Feature evidence

- Asset image upload: PNG/JPEG/WebP format detection, extension agreement, full decode, frame count, byte/dimension/pixel bounds; workspace RBAC and private storage.
- Asset version lifecycle: image/model kind preservation, SHA-256 integrity, version history, restore to a new immutable version.
- Photo Draft: active same-workspace image source/mask/reference validation; operation/output options; create/update/archive; append-only events; active references prevent source deletion.
- Lookbook Draft: product/person image validation; optional ACTIVE Project and active Character references; create/update/archive; append-only events; active references prevent image deletion, Project archival and Character deletion.
- UI: AssetWorkspace filters 3D models; PhotoDraftWorkspace and LookbookDraftWorkspace provide preparation-only flows and explicitly disclaim generation/charges.

## OpenAPI drift

- 13 design paths and 39 runtime paths.
- 5 design-only paths remain: credit account, credit ledger, job executions, job outputs and quotes.
- 31 runtime-only paths remain, including image upload, asset restore, Photo Draft and Lookbook Draft endpoints.
- 10 of 15 matched design operations have structural request/response/parameter/status/operationId drift.
- The imported OpenAPI design baseline was not overwritten or changed to force a match.

## Non-goals / limitations

- Photo Draft is input preparation only; no Generation Job, Quote, Credit reservation, Provider request, Output image, or quality evaluation is created.
- Lookbook Draft is campaign composition preparation only; SKU/catalog, multi-product UI, generated outputs, review/approval, export and pricing are not implemented.
- Pillow image upload preserves the original uploaded bytes and metadata privately. No external Provider receives the images in this build.
- SQLite/local filesystem only. This does not establish filesystem/DB crash atomicity, PostgreSQL, object storage, multi-host concurrency, browser runtime, Android E2E or production readiness.
- Actual FASHN generation is not run. Mock and Draft flows are not evidence of actual AI image generation.
- Credit Ledger persistence remains blocked by unresolved product/accounting policy. G0-G5 remain unpassed.
