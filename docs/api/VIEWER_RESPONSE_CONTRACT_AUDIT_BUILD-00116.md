# Viewer Response Contract Audit — BUILD-00116

## Decision

The request-body audit in BUILD-00115 did not establish response compatibility. This build begins response validation by making selected, high-value API responses explicit in FastAPI/OpenAPI and matching the corresponding Viewer declarations.

## Contracts made explicit

| Viewer operation | Runtime response contract | Important optional/null fields |
|---|---|---|
| Generated output list | `GeneratedOutputListResponse` | `checksum_sha256`, `asset_id`, `asset_version_id`, `provenance_record_id` |
| Generated output review detail | `GeneratedOutputReviewResponse` | `latest_decision`, asset linkage IDs, provenance/checksum, provider/model |
| Review approve/request-changes/reject | `GeneratedOutputReviewResponse` | Same review snapshot semantics |
| Asset preview URL | `AssetPreviewUrlResponse` | `asset_id`, `version_id` absent on asset-level URL |
| AssetVersion preview URL | `AssetPreviewUrlResponse` | Exact `asset_id` and `version_id` included |

## Compatibility safeguards

- Existing JSON envelope keys (`data`, `meta`, `output`, `status`, `events`) remain unchanged.
- Existing extra metadata is retained by Pydantic models configured with `extra="allow"`.
- No private storage path or binary content is exposed by these models.
- Nullable asset-link fields are explicitly represented as nullable rather than assuming a linked AssetVersion always exists at read time.
- `latest_decision` is nullable while review is pending.

## Coverage boundary

The runtime OpenAPI document still contains 80 path items. This audit types the generated-output review and preview flows only. Other Viewer-consumed endpoints (Asset metadata/version lists, Products/Variants, Projects/assignments, Photo Drafts/Runs, Lookbook Drafts/Outputs/exports) need additional response schemas and runtime examples. This build does not claim complete Viewer response compatibility.
