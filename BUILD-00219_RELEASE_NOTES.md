# BUILD-00219 Release Notes

## Scope
PostgreSQL Output aggregate adapter and Workspace/Asset metadata foundation.

## Implemented
- Added `PostgreSQLOutputRepository` with private output URL validation, strict media/extension checks, size bounds, checksum validation, transactional finalization, worker lease ownership/expiry checks, output-asset link enqueue, Job/Execution/Event/Poll state updates.
- Updated `build_output_repository("postgresql")` to select the PostgreSQL adapter without SQLite fallback. SQLite remains the default and unchanged.
- Added PostgreSQL migration `0002_assets_workspaces.sql` for Workspace membership, Assets, immutable Asset versions, relations, and provenance.
- Added `PostgreSQLAssetMetadataRepository` for workspace creation, role lookup, owner/admin membership management, workspace listing, asset metadata registration, and asset listing.
- New adapters remain deliberately outside runtime/API wiring until live Supabase parity, RLS, and Storage integration tests pass.

## Verification
- Backend pytest: 524 passed, 0 failed.
- Focused new adapter tests: 16 passed.
- `python -m compileall -q app tests`: passed.
- PostgreSQL migration inventory: `0001_generation_core.sql`, `0002_assets_workspaces.sql` detected in order.
- Live PostgreSQL/Supabase execution: NOT RUN.
- Vercel Preview deployment: NOT RUN.

## Safety
- No Supabase schema changes or data writes.
- No Vercel deployment or environment changes.
- No Production changes.
- No AI provider calls.

## Remaining
- Add adapter contract parity tests against SQLite behavior.
- Live-apply migration 0002 to the dedicated Supabase test project after review.
- Verify tenant isolation and Storage object policies with separate users.
- Implement object-byte operations through Supabase Storage; metadata adapter does not upload bytes.
- Complete PostgreSQL Poll/Outbox/Operations composition before runtime wiring.

### Additional BUILD-00219 continuation
- Extended Asset metadata adapter with version creation, version history, provenance history, same-workspace relation creation/listing, and soft deletion.
- Added bounded pagination and role checks for mutating Asset metadata operations.
- Updated final local verification after these additions: 528 passed / 0 failed.
