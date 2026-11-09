# AI CREATOR STUDIO v0.77 — Poll Worker Lease Fencing

## Scope

Prevent a Poll Worker whose lease has expired from committing late task/job state transitions. The guard applies to poll-task completion, rescheduling, retry exhaustion, provider-success handoff, and atomic output finalization.

## Implementation

- `app/repositories/poll.py`: lease expiry is part of the ownership predicate for poll task state transitions.
- `app/repositories/sqlite_output.py`: atomic output finalization verifies the task lease is still valid before writing Output/Job/Execution/Event state.
- `tests/test_concurrent_claims.py`: regression tests force a claimed task's lease into the past and verify the former worker cannot complete, hand off provider success, reschedule, exhaust, or finalize output.

## Verification

- Backend: `python -m pytest -q` — 232 passed.
- Backend compile: `python -m compileall -q app scripts tests` — passed.
- 3D Viewer source validation: 19/19 passed.

## Boundaries

This is SQLite single-host evidence. It does not establish PostgreSQL runtime behavior, multi-host concurrency, provider submission fencing, or production readiness. Expired tasks remain in their current processing state until the normal lease-recovery path reclaims them; the stale worker cannot mutate them after expiry.
