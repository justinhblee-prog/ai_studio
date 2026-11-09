# Credit Ledger Repository Port v0.1

## Status

Contract-only. This document and Protocol do **not** implement persistent storage,
account balances, charging, or a production transaction adapter.

## Required operations

- `append_batch(events)`: atomic append-only batch operation.
- `get_event(event_id)`: immutable event lookup.
- `list_account_events(organization_id, credit_account_id)`: stable account history.

## Required adapter guarantees

1. Validate batch-local invariants before persistence.
2. Enforce event ID and `(idempotency_scope, idempotency_key)` uniqueness against persisted history.
3. Exact retries are idempotent; changed payload under a reused key is a conflict.
4. Resolve reservation settlements and refunds against persisted history inside the same transaction.
5. Commit all events or none; never update/delete prior ledger facts.
6. A database unique constraint is required for cross-process race safety. Application-level pre-checks alone are insufficient.

## Explicitly unresolved

- Credit account ownership and tenant binding rules.
- Credit unit precision and rounding.
- Balance locking/serialization strategy and isolation level.
- Expiry lots and allocation order.
- Partial capture, partial release, and partial refund.
- Refund ceilings/cumulative refund calculation.
- Quote pricing and credit conversion.

These choices must be approved before a production adapter or charging endpoint is implemented.

## Verification boundary

The tests use a contract-only in-memory test double to verify structural protocol compatibility and basic expected behavior. They do not prove SQL durability, database uniqueness under concurrency, rollback on process failure, or multi-instance correctness.
