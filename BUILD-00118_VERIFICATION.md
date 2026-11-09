# BUILD-00118 Verification Report

## Base and scope
- Base archive: BUILD-00117
- Scope: independent clean verification of the packaged backend and Viewer response-contract checks
- Application behavior/source changes: none
- This is a verification checkpoint, not a product-version or Gate promotion.

## Passed in this environment
- Full backend pytest: **357 passed in 20.08s**, clean process exit.
- Focused API/response-contract regression selection: **88 passed in 7.93s**, clean process exit.
- Python compileall (`app`, `scripts`, `tests`): passed.
- Runtime OpenAPI snapshot `--check`: passed; 80 path items.
- Viewer response contract: 47 JSON endpoints across 48 unique endpoints, 27 models, 0 missing routes/schemas/unresolved dynamic segments.
- Viewer API contract: 58/58 calls matched; 0 missing, 0 query mismatches, 0 unresolved dynamic segments.
- Viewer request body contract: 10 JSON bodies checked; 0 findings.
- ZIP archive integrity and SHA-256: verified after packaging.

## Important distinction
The 88-test focused selection includes real API integration coverage in asset, project, character, and project-product test modules, plus response-model and OpenAPI contract tests. The 357-test full suite passes. However, the 47/47 response endpoint figure is static source/OpenAPI schema coverage; it is **not** evidence that 47 independently seeded live HTTP success payload fixtures exist. Per-endpoint runtime fixture coverage remains the next contract-testing task.

## Not verified / blocked
- TypeScript compilation remains blocked by missing React/Three.js packages and type declarations. No dependency installation was attempted in this offline environment.
- Browser React runtime, WebGL rendering, Android E2E, and production deployment were not run.
- PostgreSQL/multi-host runtime behavior remains unverified; SQLite-only tests do not establish it.
- Live Provider generation, paid API usage, credit charging, publication authorization, and commercial-rights assumptions were not exercised.

## Approval boundaries retained
- No live Provider calls or paid API usage.
- No credit charging or changes to production data.
- No publication/commercial-rights authorization assumptions.
- No destructive migration or deployment.
- PostgreSQL runtime selection and credit policy remain undecided.

## Reproduction
From `ai_creator_studio_backend_starter/`:
```bash
python scripts/export_runtime_openapi.py --check
python -m compileall -q app scripts tests
python -m pytest -q
python -m pytest -q tests/test_viewer_response_contract_audit.py tests/test_viewer_response_contracts.py tests/test_viewer_response_contracts_extended.py tests/test_assets_api.py tests/test_projects_api.py tests/test_characters_api.py tests/test_project_products_api.py
```

From `ai_creator_studio_3d_viewer/`:
```bash
python scripts/validate_viewer_response_contract.py
python scripts/validate_api_contract.py
python scripts/validate_viewer_request_contract.py
```
