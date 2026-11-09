# Output → Asset Workspace & Provenance Integrity — BUILD-00206

## Scope

This audit covers the internal Output Asset Link worker's cross-database import path from a persisted Generation Output into the Asset database. It checks the deterministic Asset, immutable AssetVersion, and Provenance records used by review/export flows. It does not claim a live PostgreSQL or external-provider validation.

## Findings fixed

1. **Worker action was attributed to the requesting user.** The `asset.generated_output_imported` provenance row used the generation owner's user ID as `actor_id`, even though the actual database mutation was performed by the background Output Asset Link worker. New imports now use the explicit service principal `system:output_asset_link_worker`. The original requester remains recorded separately as `details.initiated_by`, and the claimed worker identity is retained as `details.worker_id`.
2. **Existing deterministic Asset verification omitted ownership.** Retry/recovery checked workspace and content metadata but did not compare `assets.owner_id` with the originating Output task's `owner_id`. This could allow a tampered or conflicting deterministic row to pass the recovery check. Owner identity is now part of the equality check.
3. **Immutable Version verification was too narrow.** Existing records were previously accepted when the deterministic version existed and its checksum matched. The worker now verifies workspace, version number, storage key, MIME type, byte size, checksum, and creator identity.
4. **Provenance verification checked existence only.** Existing provenance is now checked for workspace, version number, expected event type, actor class, and the exact source/job/output relationship in its JSON details. Invalid JSON and mismatched cross-resource references fail closed.

## Compatibility

- Historical deterministic imports created before this change may have the requesting user in `actor_id`; that legacy attribution is accepted during idempotent retry so a deployment does not strand already-committed Asset imports.
- New imports use the service principal. `initiated_by` and `worker_id` are additive details and do not change the public API response schema.
- AssetVersion `created_by` remains the initiating user, preserving the distinction between who requested the generated output and which service performed the import/provenance action.

## Regression coverage

- New import records the worker service principal, initiating user, worker ID, job ID, and output ID.
- Existing cross-workspace AssetVersion metadata is rejected on retry.
- Existing Asset owner mismatch is rejected on retry.
- Existing crash-recovery/idempotency test still proves that an Asset commit followed by a lost Outbox acknowledgement reuses the deterministic Asset/Version/Provenance records.

## Remaining boundaries

- The Asset and Generation databases are separate stores; the worker's deterministic IDs and retry verification provide idempotent recovery, not a distributed transaction.
- A process crash after writing the deterministic private file but before committing Asset metadata can leave an unreferenced file. The same deterministic retry can reuse valid bytes; automated orphan-file garbage collection remains a separate retention-controlled task.
- Live PostgreSQL adapter tests, production identity-provider integration, and external AI provider tests remain deferred.
