# AI CREATOR STUDIO v0.71

## Credit Ledger batch validation
- Added DB-neutral `validate_event_batch` to validate append-only event batches before persistence.
- Exact event retries collapse to one canonical event.
- Rejects event ID reuse with changed content and scoped idempotency-key reuse with changed content.
- Rejects more than one terminal CAPTURE/RELEASE for a reservation within the submitted batch.
- If a RESERVE is included in the same batch, validates organization/account/job/reference/amount consistency.
- Supports settling a reservation from prior persisted history only as a deferred validation responsibility; the persistence adapter must verify that history inside its transaction.

## Verification
- Backend pytest: 211 passed.
- Python compileall: passed.
- 3D Viewer structural validation: 19/19 passed.
- No DB schema, persistence adapter, API, billing, balance projection, or account/expiry policy was introduced.
