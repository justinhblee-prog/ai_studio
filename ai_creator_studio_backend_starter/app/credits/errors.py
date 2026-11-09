"""Stable application-level Credit Ledger error taxonomy."""


class CreditLedgerError(Exception):
    """Base class for expected Credit Ledger domain/persistence failures."""


class CreditLedgerValidationError(CreditLedgerError, ValueError):
    """The event or batch violates a domain invariant."""


class CreditLedgerIdempotencyConflict(CreditLedgerError):
    """An idempotency key was reused with different immutable event content."""


class CreditLedgerReferenceNotFound(CreditLedgerError):
    """A referenced persisted ledger event does not exist."""


class CreditLedgerConcurrencyConflict(CreditLedgerError):
    """A concurrent write won a uniqueness/serialization race."""


class CreditLedgerTransactionError(CreditLedgerError):
    """A transaction could not be committed or rolled back safely."""
