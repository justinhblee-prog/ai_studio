# BUILD-00221 Release Notes — Bounded Supabase Storage Downloads

## Scope
Hardened the explicit Supabase Storage BlobStore download path. This build does not wire the BlobStore into Asset API lifecycle routes and does not change the default local storage backend.

## Changes
- Replaced eager Supabase Storage GET buffering with streamed reads.
- Enforced the approved bucket's maximum object size using both Content-Length preflight and an actual streamed-byte ceiling.
- Rejected unsupported response MIME types before returning bytes.
- Preserved private bucket allowlisting, HTTPS-only endpoint validation, service-role credential handling, and secret-safe provider errors.
- Added regression tests for declared oversize responses, chunked/unknown-length oversize responses, and MIME mismatch.

## Verification
- Full backend pytest: **539 passed / 0 failed**.
- Focused BlobStore tests: **11 passed / 0 failed**.
- Python compileall (`app`, `scripts`, `tests`): PASS.
- Runtime OpenAPI snapshot check: PASS; no API contract changed.
- Supabase live Storage upload/download: NOT RUN.
- Asset API remote-storage lifecycle integration: NOT IMPLEMENTED.

## Compatibility and safety
- `BLOB_STORAGE_BACKEND=local` remains the default.
- Supabase Storage remains explicit opt-in and is not wired into Asset API upload, version, restore, preview, integrity, or delete routes.
- No environment variables, secrets, database schemas, Supabase resources, Vercel settings, or Production deployments were changed.
