# BUILD-00117 — Viewer Response Contract Coverage

## Scope

Completed the next Viewer/Backend response-contract increment on top of BUILD-00116. The change makes successful JSON response shapes explicit for Viewer-consumed APIs without changing endpoint paths, request payloads, authorization, workflow state transitions, or export rights policy.

## Implementation

- Added `app/viewer_responses.py` with reusable Pydantic response models for Asset and AssetVersion, Project, Character, Product/Variant, Project Product assignments, Photo Draft/Run/review/local-processing envelopes, Lookbook Draft/output/review/export/manifest, and event lists.
- Attached response models to the Viewer-consumed routes. The Asset version mutation response and local Photo processing response were modeled separately from list/detail records after integration tests showed their actual shapes differ (`asset + version_id/version_number`, and `{run, output_asset}`).
- Added a source/OpenAPI response audit at `ai_creator_studio_3d_viewer/scripts/validate_viewer_response_contract.py` and `npm run validate:response-contract`.
- Added regression tests for endpoint coverage, nullable values, nested structures, and internal-use/no-rights-grant export flags.
- Updated Viewer-local TypeScript declarations for Product, Variant, Project, PhotoRun, LookbookOutput, PackageExport, AssemblyReview, and AssetVersion fields.
- Regenerated the authoritative runtime OpenAPI snapshot (80 path items).

## Coverage result

- Viewer source files scanned: 7
- Unique Viewer endpoints: 48
- Endpoints with JSON success responses and explicit schemas: 47
- Endpoints with no JSON success body: 1 (`DELETE /v1/assets/{asset_id}`, HTTP 204)
- Distinct response models referenced by Viewer endpoints: 27
- Missing runtime routes: 0
- Missing success response schemas: 0
- Unresolved dynamic path segments: 0

## Compatibility

- Existing endpoint URLs, methods, request bodies, query names, permissions, and domain behavior are unchanged.
- Response models use `extra="allow"` during this compatibility pass so existing server metadata is not silently discarded. Required fields in the documented contract remain validated.
- No credit charging, live Provider dispatch, publication permission, or commercial rights were introduced.

## Verification

See `BUILD-00117_VERIFICATION.md`. Focused API/contract suite: 160 passed with clean exit; the packaged ZIP was extracted and the same focused suite passed again (160 passed). Full suite: 357 passed summary, but the process did not terminate after printing the summary; clean process exit is not claimed. The full suite reached its pytest summary with 355 passed, but the runner did not terminate after printing the summary; clean process exit is not claimed.

## Remaining limitations

- TypeScript compilation is blocked by unavailable `react`, `react-dom`, `three`, and their type declarations; the global `tsc` binary itself is available.
- Browser/React/WebGL/Android E2E remains unverified.
- PostgreSQL/multi-host, live Provider, credit policy, and production deployment remain separate gates.
