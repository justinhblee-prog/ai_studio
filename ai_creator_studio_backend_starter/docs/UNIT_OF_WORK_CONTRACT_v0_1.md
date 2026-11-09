# Unit of Work Contract v0.1 (v0.28)

## Contract
`StorageBackend` now exposes `transaction(database_path)` as the owner of one connection lifetime. The context manager:
- Opens the connection through the selected backend.
- Yields the connection to repository orchestration.
- Commits on normal exit.
- Rolls back on any exception, including non-Exception BaseException subclasses.
- Always closes the connection.

SQLite write serialization remains explicit through `begin_write(connection)`, which uses `BEGIN IMMEDIATE`. The transaction context intentionally does not issue a second BEGIN because existing repositories call `begin_write` inside the unit of work.

## Adoption
All 31 Generation Job repository connection scopes now use `StorageBackend.transaction` rather than SQLite's raw connection context manager. This standardizes connection closure and exception handling without changing existing query/claim policy.

## Important nuance
A transaction is only atomic after a transaction has actually begun. Existing multi-statement critical paths call `begin_write`; single-statement autocommit operations retain their previous behavior. Future repository extraction must explicitly classify read, write, and serialized-write units rather than assume a context manager alone starts a transaction.

## Validation
- Backend pytest: 132 passed.
- Python compileall: passed.
- 3D Viewer structural validation: 19/19 passed.
- Rollback test proves an exception after `BEGIN IMMEDIATE` leaves no partial insert.

## Limitations
- This contract is currently implemented by SQLite only.
- It does not provide PostgreSQL connection pooling, isolation-level selection, savepoints, or `SKIP LOCKED` claims.
- No PostgreSQL runtime or live integration test is present.
