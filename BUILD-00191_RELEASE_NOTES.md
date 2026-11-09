# BUILD-00191 Release Notes

## Summary

Hardens the SQLite → PostgreSQL migration export path so it cannot silently discard database-level invariants that the current PostgreSQL conversion utility does not implement.

## Changes

- `scripts/sqlite_to_postgres.py` now inventories SQLite tables, indexes, triggers, and views before creating an export bundle.
- Export fails closed when user-defined triggers, views, or virtual tables are present. The error identifies the unsupported objects and explains that explicit conversion/verification is required.
- Destination directories are created only after the source-object safety gate passes, preventing a rejected export from leaving a misleading partial bundle.
- Added regression tests for trigger, view, and virtual-table refusal.
- Updated `docs/POSTGRESQL_MULTI_INSTANCE_MIGRATION_v0_1.md` to document the limitation and the append-only invariant risk.

## Why this matters

The current project SQLite database contains append-only audit triggers. The prior export path selected only tables and indexes, so it could have migrated rows while omitting those trigger-enforced protections. BUILD-00191 prevents that silent loss.

## Scope

No API behavior, application runtime database backend, provider behavior, dependency versions, or lockfiles changed. PostgreSQL remains fail-closed and is not claimed as a supported runtime backend.
