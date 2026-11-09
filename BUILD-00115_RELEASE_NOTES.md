# BUILD-00115 — Viewer Request Body Contract Validation

## Scope

Added static validation of Viewer JSON request bodies against the committed FastAPI runtime OpenAPI snapshot. The audit covers top-level body field names, required fields, dynamic review-action routes, and the Viewer union types for Photo operation and output format enums.

## Changes

- Added `ai_creator_studio_3d_viewer/scripts/validate_viewer_request_contract.py`.
- Added regression tests for shorthand object properties, nested object parsing, all discovered JSON request call sites, and enum agreement.
- Added `npm run validate:request-contract` and `npm run test:request-contract` scripts.
- Added machine-readable `docs/viewer_request_contract_audit.v1.json`.
- Dynamic review-action calls are matched against compatible OpenAPI operation schemas; the report retains all equivalent candidate operation paths rather than implying a single action was selected.
- No application request payload or Backend runtime behavior was changed. Audit work identified no field-name or required-field mismatch, so no UI payload patch was needed.

## Boundaries

- The validator checks literal JSON object keys and required-field presence. It does not replace the TypeScript compiler and does not prove runtime values satisfy every Pydantic scalar constraint.
- `PhotoOperation` and `OutputFormat` Viewer unions are compared exactly with their runtime OpenAPI enum sets.
- Multipart/FormData calls are outside this JSON-body audit.
- TypeScript typecheck, browser/React/WebGL/Android E2E remain unverified.
