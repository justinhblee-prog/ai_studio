# BUILD-00208 — Read-only Historical Workspace Integrity Auditor

Date: 2026-11-06
Base: BUILD-00207

## Delivered

- Added `app.integrity_audit`, a read-only SQLite metadata auditor for historical relation rows.
- Audits Product↔Asset, Variant↔Product↔Asset, Character↔Asset, Lookbook↔Asset and Lookbook entity references.
- Reports missing references, cross-workspace references, deleted Asset references, invalid Lookbook media types, and Variant parent/workspace mismatches.
- Deterministic JSON findings include stable finding codes and per-code counts; the CLI opens the database with SQLite `mode=ro` and `PRAGMA query_only=ON`.
- Added regression tests proving detection and clean-database behavior without changing source rows.

## Explicit limits

- This is an inventory tool, not a repair tool. It never deletes, rewrites, or silently relinks historical data.
- It currently audits the SQLite schema only. PostgreSQL parity and live migration validation remain unverified.
- Private-file orphan cleanup is intentionally not automated. A safe implementation requires a grace period, storage inventory, reference recheck under a coordinated lock/lease, and quarantine before irreversible deletion.
