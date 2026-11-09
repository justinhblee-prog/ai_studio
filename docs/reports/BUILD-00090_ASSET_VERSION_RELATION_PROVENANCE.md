# BUILD-00090 — Asset Version, Relations and Provenance

## Delivered

- Immutable per-asset version metadata and private byte snapshots.
- Upload creates version 1; legacy asset rows are backfilled as version 1.
- New version uploads are validated with the existing GLB/GLTF validator and promoted as current.
- Typed workspace-scoped asset relations: `derived_from`, `variant_of`, `uses_texture`, `paired_with`.
- Append-only provenance events for upload, version creation, relation creation, and deletion.
- Workspace RBAC: read for owner/admin/editor/viewer; mutation for owner/admin/editor.
- Version history API omits storage keys and filesystem paths.
- Asset deletion removes all retained version files.

## API

- `POST /v1/assets/{asset_id}/versions` — multipart `file`, creates and promotes next version.
- `GET /v1/assets/{asset_id}/versions` — immutable version metadata.
- `GET /v1/assets/{asset_id}/provenance?limit=&offset=` — audit events.
- `POST /v1/assets/{asset_id}/relations` — JSON `{ "target_asset_id": "...", "relation_type": "variant_of" }`.
- `GET /v1/assets/{asset_id}/relations` — incoming and outgoing relations.

## Data integrity / security

- Version number is allocated under the SQLite write transaction and protected by `UNIQUE(asset_id, version_number)`.
- Version content is hashed server-side and validated before persistence.
- Relation endpoints require both assets to be active members of the same workspace.
- Self-relations, unsupported types, duplicate relation tuples, and cross-workspace references are rejected.
- Read and write endpoints apply workspace role checks before returning data or changing state.
- Provenance details are structured JSON; no storage path or storage key is returned.

## Verification

- Backend suite: 287 passed.
- Asset API suite: 23 passed.
- Tests cover baseline creation, version promotion, immutable previous bytes, delete cleanup, role restrictions, provenance, relation validation, duplicate detection, and workspace isolation.

## Known limitations

- SQLite/local filesystem only. Database and filesystem cannot commit atomically; a process crash after file write can leave an orphan file.
- No PostgreSQL/object storage/distributed transaction or cross-host locking claim.
- No browser upload-to-Three.js visual E2E or TypeScript build claim.
- Existing OpenAPI design baseline has not been silently rewritten; runtime-only endpoints are recorded as drift until contract approval.
