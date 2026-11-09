# BUILD-00222 Verification

## Source baseline
- Recovered BUILD-00220 and applied BUILD-00221 as the preceding local baseline.
- BUILD-00221 source archive SHA-256: `75ba5cdf3672c59257a7d2da71d39461e1a522f7d20a2fe87fece0ac2b1b0adc`.

## BUILD-00222 checks
- `python -m pytest -q`: **546 passed / 0 failed**.
- `python -m pytest -q tests/test_asset_blob_lifecycle.py tests/test_blob_storage.py`: **18 passed / 0 failed**.
- `python -m compileall -q app scripts tests`: PASS.
- `python scripts/export_runtime_openapi.py --check`: PASS.

## New regression coverage
- Local gateway resolves to the pre-existing `ASSET_STORAGE_DIR` and flat key layout.
- Local put/get/delete and idempotent missing-object delete behavior.
- Supabase Asset locator uses the private `acs-assets` bucket and workspace-prefixed object key.
- Invalid backend, bucket mismatch, path traversal, and local bucket mismatch are rejected.

## Not verified / not claimed
- Asset API is not yet wired to this gateway.
- No remote Supabase Storage byte transfer was performed.
- No PostgreSQL runtime, tenant RLS identity, worker concurrency, browser E2E, GLB visual rendering, paid AI generation, or source-backed Vercel Preview was run.
- Production and the existing production Supabase project were not changed.
