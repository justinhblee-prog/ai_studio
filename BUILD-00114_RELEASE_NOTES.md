# BUILD-00114 Release Notes — Viewer API Integration Contract Audit

## Summary

Viewer `fetch()` calls were audited against the BUILD-00113 committed runtime OpenAPI snapshot. The audit covers path, HTTP method, and query parameter names, including dynamic review/action path segments.

## Changes

- Added `ai_creator_studio_3d_viewer/scripts/validate_api_contract.py`.
- Added two validator regression tests in `scripts/test_api_contract_validator.py`.
- Added `npm run validate:api-contract`.
- Added a human-readable Viewer ↔ Backend integration audit and machine-readable JSON report.
- Removed ignored `limit=100` query arguments from the Product Catalog and Lookbook asset list calls. The actual `/v1/assets` endpoint declares `workspace_id` and `kind`, not `limit`; pagination is not implemented by that route.
- Updated Viewer README and build changelog.

## Verification

- 58/58 Viewer fetch call sites matched runtime OpenAPI path + method + declared query parameter names.
- 48 unique method + path combinations.
- Missing routes/methods: 0.
- Undeclared query parameters: 0.
- Unresolved dynamic path segments: 0.
- Validator regression tests: 2 passed.
- Python compileall for Viewer scripts: passed.

## Limitations

- No backend runtime behavior was changed.
- Request body and response payload schemas are not yet checked by this source-level validator.
- `npm install` did not complete within the execution timeout; TypeScript typecheck remains unverified.
- Browser, React runtime, WebGL, and Android E2E remain unverified.
- No external Provider dispatch, credit charging, PostgreSQL migration, or rights-policy change was made.
