# AI CREATOR STUDIO v0.36 — Event Repository SQL Extraction

## Scope
- Expanded `EventRepository` from read-only access to append-only Event read/write operations.
- Implemented `SQLiteEventRepository.list_for_job()` and `append_in_transaction()` as the sole owner of `generation_job_events` SELECT/INSERT SQL.
- The append operation receives the caller's open transaction connection and never commits or opens a second connection, preserving atomicity with Job/Execution/Outbox/Poll/Output mutations.
- Replaced all Event INSERT statements in the legacy Job repository with the Event adapter; removed Event table SQL from Output repository and worker SQL constants.
- Routed `list_events()` and Job/Event UoW event reads through the dedicated Event repository.

## Validation
- Backend pytest: 149 passed.
- Python compileall: passed.
- 3D Viewer structural validation: 19/19 passed.
- Source-boundary test confirms `generation_job_events` SQL exists only in the Event adapter, not the legacy Job module or Output adapter.
- Existing transaction rollback tests still pass, including Event INSERT failure and atomic Output finalization.

## Known limits
- Job writes still orchestrate Job/Execution and call the Event adapter using the same SQLite connection; full Job aggregate SQL extraction remains in progress.
- PostgreSQL Event adapter/runtime and live server integration remain unavailable; backend selection fails closed.
- Credit Quote / append-only Credit Ledger remain unimplemented.
- FASHN live contract, rights, retention, and commercial-use verification remain open.
- Browser/WebGL/Android end-to-end tests and production deployment remain unverified.
