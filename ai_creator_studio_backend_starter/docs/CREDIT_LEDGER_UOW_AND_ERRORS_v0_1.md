# Credit Ledger Unit of Work and Error Taxonomy v0.1

## Status

Contract-only. No SQLite/PostgreSQL transaction manager or persistence adapter is included.

## Unit of Work

`CreditLedgerUnitOfWork` binds a repository instance to one transaction scope. The adapter contract requires:

- commit only after successful operation completion;
- rollback when the operation exits with an exception;
- repository operations share the same connection/transaction;
- commit failure is surfaced and never reported as success;
- rollback is safe after an operation failure;
- transaction isolation/locking is selected and verified by the concrete adapter.

`CreditLedgerUnitOfWorkFactory` creates an isolated scope per application operation.

## Error taxonomy

- `CreditLedgerValidationError`: invalid event or batch.
- `CreditLedgerIdempotencyConflict`: same scoped key, different event content.
- `CreditLedgerReferenceNotFound`: referenced persisted event is absent.
- `CreditLedgerConcurrencyConflict`: unique/serialization race.
- `CreditLedgerTransactionError`: commit/rollback failure.

Adapters may preserve the original database exception as `__cause__`; API mapping must not leak SQL or provider details.

## Verification boundary

Tests use a fake in-memory transaction object. They verify protocol shape and expected context behavior only; they do not establish real database rollback, isolation, durability, or concurrent-writer correctness.
