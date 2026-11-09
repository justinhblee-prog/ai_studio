# Storage Port Extraction v0.2 — v0.23

## Scope

The explicit `DATABASE_BACKEND` selection now governs both Generation Job persistence and asset/workspace metadata connection creation. Asset metadata no longer opens `sqlite3.connect` directly; it obtains its connection from `app.storage.get_storage()`.

## Preserved behavior

- SQLite remains the only enabled runtime backend.
- SQLite foreign-key enforcement, busy timeout, and WAL are applied by the storage adapter.
- Generation Job write transactions continue to use `BEGIN IMMEDIATE` through the adapter.
- Existing schema and SQL statements are unchanged in this milestone.
- Selecting `DATABASE_BACKEND=postgresql` fails closed for both storage domains. No silent SQLite fallback is allowed.

## Explicit non-goals

This is not SQL dialect portability and not a PostgreSQL adapter. Asset and Generation Job schema DDL still uses SQLite-compatible SQL. Query placeholders, `INSERT OR IGNORE`, SQLite integrity exceptions, row semantics, and claim transaction behavior still require deliberate adaptation and PostgreSQL integration tests.

## Verification

The test suite verifies that the asset store creates its schema through the shared storage port, receives the required SQLite pragmas, and rejects PostgreSQL selection rather than falling back. Full backend tests and compile checks are recorded in the v0.23 handoff.
