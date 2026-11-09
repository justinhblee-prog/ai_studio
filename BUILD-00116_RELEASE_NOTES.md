# BUILD-00116 Release Notes — Viewer Response Contract

## Scope

Added explicit, typed success-response contracts for the Viewer-critical generated-output review flow and private Asset preview URL issuance. The response models document actual payloads rather than changing the payload envelope or business behavior.

## Changes

- Added `GeneratedOutputItemResponse` and `GeneratedOutputListResponse` for `GET /v1/generation-jobs/{job_id}/outputs`.
- Added typed nested review models for output detail, append-only review events, and `latest_decision` nullable state.
- Applied the review response model to GET, approve, request-changes, and reject endpoints.
- Added `AssetPreviewUrlResponse` to both Asset and immutable AssetVersion preview-url endpoints.
- Updated `OutputReviewWorkspace.tsx` response types to include backend-required identity/status fields and nullable `latest_decision`.
- Regenerated the authoritative runtime OpenAPI snapshot.
- Added regression tests for OpenAPI success schemas, nested nullable fields, and Viewer type declarations.

## Compatibility

- No endpoint paths, HTTP methods, request bodies, response envelope keys, state transitions, or authorization rules changed.
- Response models allow additional fields to avoid dropping existing response metadata while documenting fields consumed by the Viewer.
- No provider calls, credit charging, public publishing, or commercial-rights flags were added.
