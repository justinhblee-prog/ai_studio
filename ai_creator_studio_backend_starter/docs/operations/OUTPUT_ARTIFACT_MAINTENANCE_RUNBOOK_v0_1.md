# Output Artifact Maintenance Runbook v0.1

- Scope: BUILD-00083 same-host SQLite/local-filesystem deployment only
- Status: Operational procedure; not a distributed garbage-collection guarantee

## Purpose

Remove attempt-scoped Output files that have no committed `generation_outputs.storage_key` reference, without racing a Poll Worker that is downloading or finalizing an Output.

## Coordination model

- Poll Worker holds a shared POSIX `flock` on `<OUTPUT_DIR>/.output-maintenance.lock` from before download until the Output DB finalization finishes.
- Cleanup command takes the exclusive form of the same lock before reading committed references and scanning/deleting candidates.
- An exclusive cleanup waits for in-flight same-host Output attempts. New attempts wait until cleanup releases the lock.
- This protection assumes every Output writer and cleanup process uses the same lock file on the same host and a filesystem with working POSIX advisory locks.
- It does not coordinate a second host, an older worker version that does not take the lock, NFS/object storage, or a manually copied/deleted file.

## Operator procedure

1. Run cleanup from the same host and environment used by the API/Poll Worker. Confirm `OUTPUT_DIR` and `GENERATION_DATABASE_PATH` point to the intended deployment.
2. Review the dry-run candidate list:

   ```bash
   cd ai_creator_studio_backend_starter
   python scripts/cleanup_orphaned_outputs.py --older-than-hours 24
   ```

3. Confirm the listed files are not needed for incident investigation or manual recovery. The tool protects all storage keys currently referenced by committed Output rows and ignores files newer than the age threshold.
4. When approved, run the same command with explicit deletion:

   ```bash
   python scripts/cleanup_orphaned_outputs.py --older-than-hours 24 --apply
   ```

5. Retain the command output in the operator change record. Re-run dry-run to confirm the same candidates are gone.

The command takes the exclusive maintenance lock for both dry-run and apply. It may wait while an Output attempt is active. Do not bypass the lock or delete attempt files manually while workers are running.

## Lease renewal and fencing

- Poll Worker renews a `persist_output` lease every `min(30s, lease_seconds/3)` while the provider Output is downloading.
- Renewal succeeds only for a still-live lease matching task ID, worker ID, `processing` status, and `persist_output` phase.
- An expired lease cannot be resurrected. If renewal is rejected, the in-flight download is cancelled; the final DB commit remains independently fenced by the existing lease check.
- A worker that loses the lease before finalization cannot publish an Output reference. Any already-created uncommitted attempt artifact remains eligible for later cleanup.
- A process killed after temp-file fsync but before `os.replace` leaves a hidden application temp file. A process killed after `os.replace` but before DB commit leaves an immutable attempt artifact. Both are collected only after the configured age threshold; dry-run remains the default.

## Limitations

- SQLite single-host behavior only. PostgreSQL and multi-host coordination are not implemented or verified.
- POSIX advisory locking is cooperative; all writers must use this application version and lock.
- Filesystem operations and SQLite transactions are still not one atomic transaction. The runbook narrows races but does not claim cross-resource atomicity.
