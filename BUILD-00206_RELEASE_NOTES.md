# BUILD-00206 — Output Asset Provenance & Workspace Integrity

## Changes

- Corrected generated Output import provenance: the background worker is now the recorded actor (`system:output_asset_link_worker`), while the initiating user and claimed worker ID are preserved in provenance details.
- Hardened deterministic Output Asset retry verification to compare the Asset owner and workspace as well as storage/content metadata.
- Hardened immutable AssetVersion verification across workspace, version number, storage key, MIME type, size, checksum, and creator.
- Hardened Provenance verification across workspace, version number, event type, actor class, and source/job/output linkage; malformed or mismatched records fail closed.
- Added adversarial regression tests for cross-workspace AssetVersion tampering and Asset owner mismatch.
- Added security documentation describing compatibility for historical provenance and remaining cross-database recovery boundaries.

## Compatibility

- No API routes or response schemas changed; runtime OpenAPI snapshot remains current.
- Historical records attributed to the initiating user remain accepted during deterministic recovery. New imports use the explicit worker service principal.

## Deferred

- Live PostgreSQL, real AI provider, and React/Three.js E2E tests remain deferred by project constraints.
