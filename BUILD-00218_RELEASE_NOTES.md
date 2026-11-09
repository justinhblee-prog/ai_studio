# BUILD-00218 Release Notes

- Added PostgreSQL Poll lease adapter: SKIP LOCKED claims, safe expired-lease requeue, owner-fenced renewal/completion/reschedule and retry-budget reconciliation.
- Added PostgreSQL Operations adapter: worker heartbeat upsert and alert delivery claim/finish with SKIP LOCKED and live-lease fencing.
- Retained earlier PostgreSQL Job and Outbox adapters plus migration foundation.
- SQLite remains the only enabled runtime backend; PostgreSQL factory remains fail-closed pending live SQL/contract/multi-instance validation.
