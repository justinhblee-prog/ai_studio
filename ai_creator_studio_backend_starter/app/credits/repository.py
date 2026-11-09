"""Persistence-neutral Credit Ledger repository contract.

No adapter is provided in this release. Implementations must satisfy the atomicity,
append-only, idempotency, and reference-validation contract documented here.
"""
from __future__ import annotations

from typing import Protocol, Sequence, runtime_checkable

from app.credits.domain import CreditLedgerEvent


@runtime_checkable
class CreditLedgerRepository(Protocol):
    """Transactional port for immutable Credit Ledger facts.

    ``append_batch`` is one all-or-nothing transaction. It must:
    - validate the complete input with ``validate_event_batch``;
    - enforce event-id and scoped-idempotency uniqueness against persisted rows;
    - treat an exact retry as an idempotent replay, not a second ledger fact;
    - reject key reuse with different content;
    - resolve RESERVE/CAPTURE/RELEASE and REFUND/CAPTURE references against both
      the batch and persisted history before committing;
    - never update or delete an existing ledger event.

    Balance serialization/locking, account ownership, expiry lots, precision, and
    partial settlement/refund policies are intentionally not specified here.
    """

    def append_batch(
        self, events: Sequence[CreditLedgerEvent]
    ) -> tuple[CreditLedgerEvent, ...]:
        """Atomically append facts and return canonical inserted/replayed events.

        Raises ValueError for domain/reference/idempotency conflicts. Implementations
        must not expose a partially committed batch if any item fails.
        """
        ...

    def get_event(self, event_id: str) -> CreditLedgerEvent | None:
        """Return one immutable fact by globally unique event ID."""
        ...

    def list_account_events(
        self, organization_id: str, credit_account_id: str
    ) -> tuple[CreditLedgerEvent, ...]:
        """Return account facts in stable append order; pagination is adapter-level."""
        ...
