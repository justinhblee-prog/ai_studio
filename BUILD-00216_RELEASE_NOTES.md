# BUILD-00216 Release Notes

- Added initial PostgreSQL Job aggregate adapter for transactional create, idempotency, get/list, lifecycle transitions, metadata update, queued cancellation and history reads.
- Added PostgreSQL Outbox adapter using `FOR UPDATE SKIP LOCKED`, bounded worker leases, stale-owner fencing and unknown-dispatch quarantine (no automatic replay).
- Added worker heartbeat upsert and transactional Poll task creation after successful provider submission.
- Improved psycopg dictionary row support in connection/migration helpers.
- Preserved SQLite as the only enabled runtime backend; PostgreSQL adapters are not activated pending real database parity and concurrency tests.
