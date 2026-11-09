# BUILD-00222 Release Notes — Asset Blob Lifecycle Gateway Foundation

## Scope
Introduced a backend-aware binary-storage boundary for the Asset domain. This is a compatibility-preserving foundation; existing Asset API routes still use the legacy local filesystem implementation and Supabase Storage is not yet wired into upload/version/restore/preview/integrity/delete flows.

## Changes
- Added `app/assets/blob_lifecycle.py` with validated `AssetBlobRef` locators and explicit put/get/delete operations.
- Local adapter maps to the existing `ASSET_STORAGE_DIR` directory and preserves the historical flat object-key format, so existing assets and filesystem-based consumers are not relocated.
- Supabase adapter uses the private `acs-assets` bucket and workspace-scoped keys (`workspace_id/asset_id/asset_id.ext`).
- Persisted locator validation rejects unknown backends, incorrect buckets, traversal keys, and mismatched local bucket names.
- Added regression tests for local-layout compatibility, workspace key scoping, locator validation, and unsafe-key rejection.

## Verification
- Full backend pytest: **546 passed / 0 failed**.
- Focused Asset BlobStore + BlobStore tests: **18 passed / 0 failed**.
- Python compileall (`app`, `scripts`, `tests`): PASS.
- Runtime OpenAPI snapshot check: PASS; no API contract changed.

## Explicitly not completed
- Asset route/store integration with the new gateway.
- Backend identity persistence on Asset and AssetVersion rows.
- Remote upload/version/restore/preview/integrity/delete compensation and retry workflow.
- Live Supabase Storage transfer, tenant RLS identity tests, PostgreSQL runtime composition, or Vercel Preview.

## Safety
- Local storage remains the default and existing on-disk layout is unchanged.
- No Supabase resources, secrets, database schema, Vercel settings, or Production deployments were changed.
