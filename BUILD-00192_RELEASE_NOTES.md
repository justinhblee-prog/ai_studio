# BUILD-00192 Release Notes

## Summary

Adds a narrowly scoped SQLite-to-PostgreSQL translation for the project's append-only and immutable triggers, allowing the current source databases to be exported without silently dropping those protections.

## Changes

- Added translation for SQLite `BEFORE UPDATE` and `BEFORE DELETE` triggers whose body is exactly `SELECT RAISE(ABORT, '<literal message>')`.
- PostgreSQL export emits a shared `acs_raise_append_only_error()` PL/pgSQL trigger function and one row-level PostgreSQL trigger per source trigger.
- Trigger names are recorded in `manifest.json` with a `trigger_count`.
- The importer now splits statements without breaking semicolons inside PostgreSQL dollar-quoted PL/pgSQL bodies.
- Uses `CREATE FUNCTION` (not `CREATE OR REPLACE FUNCTION`) so an existing same-signature function is not overwritten in a non-empty target schema.
- Unsupported trigger bodies, views, and virtual tables remain fail-closed.
- Added regression tests for trigger translation, unsupported trigger refusal, and dollar-quoted statement splitting.
- Updated the PostgreSQL migration guide.

## Current database export evidence

- `assets.sqlite3`: 44 tables, 9 rows, 18 supported triggers exported; all table JSONL checksums verified.
- Separate `../assets.sqlite3`: 15 tables, 9 rows, 4 supported triggers exported; all table JSONL checksums verified.

These are export/DDL-generation results only. They do not establish that the generated SQL has been executed successfully on PostgreSQL.

## Scope

No application runtime database backend, API behavior, provider behavior, dependency versions, or lockfiles changed. PostgreSQL remains unsupported as an application runtime until a real PostgreSQL environment and integration tests are available.
