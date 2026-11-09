# Worker Repository Ports v0.1

## Purpose
Decouple long-running worker responsibilities from direct imports of the monolithic `app.job_repository` module without changing persistence semantics in this milestone.

## Ports
- `OutboxRepository`: submission event claim, job lookup, submission completion/unknown reconciliation, worker heartbeat.
- `PollRepository`: poll-task claim, job lifecycle transitions, output metadata persistence, retry/exhaustion, worker heartbeat.
- `OperationsRepository`: operational alert evaluation, alert delivery claim/completion, worker heartbeat.

## Current adapter behavior
`SQLiteOutboxRepository`, `SQLitePollRepository`, and `SQLiteOperationsRepository` are explicit role adapters. They delegate operations to the existing SQLite `job_repository` implementation. This preserves transaction behavior and avoids a risky SQL rewrite during the boundary extraction.

## Fail-closed policy
Each builder validates the configured storage backend. PostgreSQL currently raises an explicit not-implemented error. It must never silently instantiate SQLite when PostgreSQL is requested.

## Limitations
The worker ports are now distinct application contracts, but SQL tables, SQL dialect, and transaction implementation are not yet physically separated. Adapters share the legacy implementation and therefore do not establish PostgreSQL compatibility or independent aggregate storage.

## Acceptance evidence
- Runtime-checkable protocol conformance tests for all three adapters.
- Shared legacy implementation test documents the intentional transitional delegation.
- PostgreSQL fail-closed tests for each builder.
- Full backend test suite and viewer structural checks recorded in v0.24 handoff.
