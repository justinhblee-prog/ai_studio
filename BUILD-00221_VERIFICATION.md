# BUILD-00221 Verification

## Source baseline
Recovered `AI_CREATOR_STUDIO_FULL_HANDOFF_BUILD-00220.zip` from the Library root and extracted into a clean working directory.

- Archive size: 3,112,899 bytes.
- SHA-256: `959ba2110e645389baaad7de8a89c3d8cda5b0f3a473f1d8df46eca3a0ce0d6b`.
- ZIP integrity: `unzip -t` passed; no compressed-data errors.

## BUILD-00221 checks
- `python -m pytest -q`: **539 passed / 0 failed**.
- `python -m pytest -q tests/test_blob_storage.py`: **11 passed / 0 failed**.
- `python -m compileall -q app scripts tests`: PASS.
- `python scripts/export_runtime_openapi.py --check`: PASS.

## Added regression coverage
- Content-Length above the bucket maximum is rejected before bytes are returned.
- Chunked response without Content-Length is stopped when streamed bytes exceed the bucket maximum.
- Unsupported response Content-Type is rejected.
- Existing private upload/download/delete contract and secret-redaction tests pass.

## Not verified / not claimed
- Real Supabase Storage HTTP upload/download.
- Asset API lifecycle integration with Supabase Storage.
- Tenant RLS policy enforcement with separate Auth identities.
- PostgreSQL runtime/worker composition.
- Source-backed Vercel Preview deployment.
- Browser React/Three.js E2E, visible GLB rendering, or paid AI generation.

The 20-table Supabase test-project migration/grant/rollback evidence is inherited from BUILD-00220 and was not rerun in this build. Production was not changed.
