# BUILD-00223 Release Notes — Persisted Asset Storage Locators

## Scope
Added backwards-compatible metadata support for recording the storage backend and bucket alongside Asset and AssetVersion rows. This prepares the schema for safely routing each immutable version to its own object store.

## Changes
- SQLite Asset and AssetVersion schemas now include `storage_backend` and `storage_bucket` with legacy-safe local defaults.
- Existing SQLite databases receive additive `ALTER TABLE` migrations during initialization; existing asset records remain local.
- Added PostgreSQL migration `0005_asset_storage_locators.sql` with equivalent columns and backend allowlist constraints.
- Extended the PostgreSQL Asset metadata adapter registration and version-creation methods to accept and validate storage locator metadata.
- Added regression coverage for legacy SQLite database upgrades and invalid PostgreSQL adapter backend values.

## Verification
- Full backend pytest: **548 passed / 0 failed**.
- Focused Asset API, PostgreSQL adapter, and blob lifecycle tests: **91 passed / 0 failed**.
- Python compileall (`app`, `scripts`, `tests`): PASS.
- Runtime OpenAPI snapshot check: PASS; no API contract changed.

## Explicitly not completed
- Asset API binary operations are not yet routed through `blob_lifecycle.py`.
- PostgreSQL migration 0005 has not been applied to the live test project in this build.
- No remote Storage transfer or live PostgreSQL repository test was run.
- Restore/preview/integrity/delete still use the existing local filesystem implementation.

## Safety
- SQLite migration is additive; legacy records default to local storage.
- Local remains the runtime default. No existing files were moved.
- No Supabase resources, secrets, Vercel settings, or Production deployments were changed.
