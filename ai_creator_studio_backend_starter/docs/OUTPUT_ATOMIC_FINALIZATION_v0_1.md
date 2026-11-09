# Output Atomic Finalization Contract v0.1

## Required invariant
A Generation Job MUST NOT enter `succeeded` unless its durable Output metadata and API-facing output reference are committed in the same database transaction.

## Transaction boundary
`finalize_output_success(task_id, worker_id, job_id, ...)` performs the following in one transaction:
1. Verify the Poll Task is `processing`, belongs to `worker_id`, and is in `persist_output` phase.
2. Verify the Job exists and permits `post_processing -> succeeded`.
3. Upsert the `generation_outputs` row.
4. Set Job status to `succeeded`, set `output_url`, clear provider URL/error state, and increment version.
5. Mark the latest Execution `succeeded` and set `finished_at`.
6. Append `OUTPUT_PERSISTED` lifecycle Event.
7. Complete and release the owned Poll Task.

Any exception rolls back all database writes. A lost lease returns `false` without committing any write.

## File-store boundary
The output binary is downloaded/stored before this DB transaction. This is not a distributed transaction. On DB failure, the Job remains `post_processing` and the durable task is retried. The current output store uses a job-scoped key, so a retry may overwrite the previous file. A future object-store design must add temporary object keys, checksum/size verification, atomic promotion or versioned references, and orphan reconciliation before asserting end-to-end atomicity.

## Engine scope
This v0.1 contract is implemented and tested on SQLite only. PostgreSQL must implement the same contract and pass live rollback, lease ownership, retry, and multi-instance concurrency tests before runtime selection is enabled.
