# BUILD-00202 Release Notes — Transaction Boundary and Outbox Lease Fencing

Date: 2026-11-06  
Base: BUILD-00201

## Changes

- Completed a focused review of the SQLite Job/Event Unit-of-Work boundary. Lifecycle state, Execution state, and append-only Event writes share the same connection and transaction; `SQLiteStorage.transaction()` owns commit/rollback and connection closure. The UoW remains an atomic-command port rather than exposing caller-managed nested transactions.
- Added failure-injection coverage proving that Job creation rolls back Job, Execution, Event, Outbox, and idempotency rows together when the audit Event insert fails.
- Added failure-injection coverage proving that Job metadata changes and their audit Event roll back together.
- Closed an Outbox lease-fencing gap: completion and unknown-outcome acknowledgement now require the worker identity, validate it before storage access, and require matching `claimed_by` plus a live lease.
- Repeated the owner/status/live-lease predicates in the Outbox mutation itself. A stale owner cannot finalize a provider submission or quarantine a newer owner's work.
- Expired in-flight provider submissions continue to move to `needs_reconciliation` rather than being replayed. Quarantine now clears stale `claimed_by` and `claimed_at` metadata as well as the lease expiry.
- Updated worker-facing protocols, compatibility facade, and worker call sites to pass the actual claiming worker identity.
- Added three dedicated Outbox lease-fencing regression tests and expanded atomic rollback tests.

## Verification

- Full backend suite: **447 passed / 0 failed**.
- Focused transaction, Job/Event UoW, Outbox lease, worker, API, and repository suite: **140 passed / 0 failed**.
- Backend app/scripts/tests Python compileall: passed.
- BUILD-00201 Viewer/API offline verification logs are carried forward unchanged; no Viewer source was changed and those checks were not rerun in this build.

## Compatibility and operational notes

- Outbox completion and unknown-outcome repository calls now require an explicit `worker_id`. Worker runtime and compatibility facades were updated. Any out-of-repository custom worker integration must pass the same identity returned by `claim_next_outbox`.
- No database schema migration or runtime dependency change.
- SQLite remains the only supported runtime database adapter.
- External PostgreSQL, React/Three.js E2E, and live paid AI-provider tests remain deferred by project decision.
