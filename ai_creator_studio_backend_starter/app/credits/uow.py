"""Transaction boundary contracts for Credit Ledger persistence.

The contracts are deliberately adapter-neutral. No transaction manager or database
implementation is included in this release.
"""
from __future__ import annotations

from types import TracebackType
from typing import Protocol, Self, runtime_checkable

from app.credits.repository import CreditLedgerRepository


@runtime_checkable
class CreditLedgerUnitOfWork(Protocol):
    """One transaction scope binding all ledger operations to one DB transaction.

    Adapters must commit only on a clean context exit, roll back on exceptions, and
    make rollback safe after a failed commit. A failed commit must never be reported
    as successful. Repository operations obtained from this UoW must use this same
    transaction, not open independent connections.
    """

    @property
    def ledger(self) -> CreditLedgerRepository: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None: ...


@runtime_checkable
class CreditLedgerUnitOfWorkFactory(Protocol):
    """Creates an isolated transaction scope for one application operation."""

    def __call__(self) -> CreditLedgerUnitOfWork: ...
