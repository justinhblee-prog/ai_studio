# Historical Workspace Integrity Audit — BUILD-00208

## Purpose

BUILD-00207 added SQLite triggers for new writes. Those triggers do not prove that older rows are valid, so BUILD-00208 adds a separate read-only inventory pass before any production migration or cleanup.

## Run

From `ai_creator_studio_backend_starter`:

```bash
python -m app.integrity_audit /absolute/path/to/assets.sqlite3
python -m app.integrity_audit /absolute/path/to/assets.sqlite3 --output integrity-audit.json
```

The database must already exist. The auditor does not initialize tables or apply migrations. It opens SQLite with `mode=ro` and enables `query_only`.

## Finding codes

- `PRODUCT_ASSET_MISSING`, `PRODUCT_ASSET_CROSS_WORKSPACE`, `PRODUCT_ASSET_DELETED`
- `VARIANT_PARENT_MISMATCH`, `VARIANT_ASSET_MISSING`, `VARIANT_ASSET_CROSS_WORKSPACE`
- `CHARACTER_ASSET_MISSING`, `CHARACTER_ASSET_CROSS_WORKSPACE`, `CHARACTER_ASSET_DELETED`
- `LOOKBOOK_ASSET_MISSING`, `LOOKBOOK_ASSET_INVALID`
- `LOOKBOOK_ENTITY_MISSING_OR_CROSS_WORKSPACE`

The JSON output is deterministic and includes finding count and counts by code. Findings are evidence for human-reviewed remediation; no automatic repairs are attempted.

## Safe remediation policy

1. Take a verified database backup and storage snapshot.
2. Run the auditor against a read-only snapshot and retain the JSON report with a timestamp and database checksum.
3. Classify each finding: stale reference, deleted source, cross-workspace security violation, or legacy schema issue.
4. For cross-workspace rows, do not infer the intended workspace from the linked Asset. Confirm ownership and business provenance before changing a relation.
5. For missing/deleted Assets, preserve the relation and source evidence until an authorized recovery/archive decision is recorded.
6. Apply approved repairs in a separate migration with transaction boundaries, row-count assertions, and before/after audit reports.
7. Re-run the read-only auditor and require zero unresolved critical findings before enabling the corresponding production constraints.

## Orphan private files

Do not delete a file merely because a single metadata query finds no reference. Generation output and Asset metadata are stored through separate flows and may be in-flight. A future cleanup worker must: inventory only files older than a configured grace period; acquire a per-storage-key lease; recheck all Asset, AssetVersion, Output, and active import references while holding the lease; quarantine first; wait through a second retention interval; then delete only if the lease and zero-reference condition still hold. Failed or ambiguous checks must retain the file and emit an audit event.

## PostgreSQL migration design notes (not implemented/tested)

- Prefer composite unique keys `(workspace_id, entity_id)` on referenced parent tables and composite foreign keys from relation tables wherever the relation schema can carry `workspace_id`.
- For polymorphic Lookbook entity references, use a validated trigger function or replace polymorphism with typed relation tables; a normal FK cannot target several tables based on `entity_type`.
- Use `NOT VALID` constraints only as a staged deployment mechanism, then validate after the historical audit/remediation is complete.
- Run migrations and concurrency tests on a real PostgreSQL instance before claiming parity. No PostgreSQL support is claimed by this build.
