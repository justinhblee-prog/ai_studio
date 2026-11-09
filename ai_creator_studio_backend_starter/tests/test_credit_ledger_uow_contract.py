from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.credits.domain import CreditLedgerEvent, CreditLedgerEventType
from app.credits.errors import (
    CreditLedgerConcurrencyConflict, CreditLedgerIdempotencyConflict,
    CreditLedgerReferenceNotFound, CreditLedgerTransactionError,
    CreditLedgerValidationError,
)
from app.credits.repository import CreditLedgerRepository
from app.credits.uow import CreditLedgerUnitOfWork, CreditLedgerUnitOfWorkFactory


class FakeLedger:
    def __init__(self):
        self.events = []

    def append_batch(self, events):
        self.events.extend(events)
        return tuple(events)

    def get_event(self, event_id):
        return next((event for event in self.events if event.id == event_id), None)

    def list_account_events(self, organization_id, credit_account_id):
        return tuple(e for e in self.events if e.organization_id == organization_id
                     and e.credit_account_id == credit_account_id)


class FakeUow:
    def __init__(self, committed, fail_commit=False):
        self._committed = committed
        self._working = FakeLedger()
        self._working.events = list(committed.events)
        self._fail_commit = fail_commit
        self.did_commit = False
        self.did_rollback = False

    @property
    def ledger(self):
        return self._working

    def commit(self):
        if self._fail_commit:
            raise CreditLedgerTransactionError("simulated commit failure")
        self._committed.events = list(self._working.events)
        self.did_commit = True

    def rollback(self):
        self.did_rollback = True
        self._working.events = list(self._committed.events)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        if exc_type is None:
            self.commit()
        else:
            self.rollback()
        return False


class FakeFactory:
    def __init__(self, committed):
        self.committed = committed

    def __call__(self):
        return FakeUow(self.committed)


def make_event():
    return CreditLedgerEvent(
        id="evt-1", organization_id="org-1", credit_account_id="acct-1",
        event_type=CreditLedgerEventType.GRANT, amount=Decimal("10"),
        idempotency_scope="account", idempotency_key="key-1",
        actor_type="system", actor_id="test", created_at=datetime.now(timezone.utc),
    )


def test_uow_and_factory_protocols_are_runtime_checkable():
    ledger = FakeLedger()
    factory = FakeFactory(ledger)
    uow = factory()
    assert isinstance(uow, CreditLedgerUnitOfWork)
    assert isinstance(uow.ledger, CreditLedgerRepository)
    assert isinstance(factory, CreditLedgerUnitOfWorkFactory)


def test_uow_context_commits_on_success():
    ledger = FakeLedger()
    event = make_event()
    with FakeFactory(ledger)() as uow:
        uow.ledger.append_batch([event])
    assert ledger.events == [event]


def test_uow_context_rolls_back_on_operation_error():
    ledger = FakeLedger()
    with pytest.raises(RuntimeError):
        with FakeFactory(ledger)() as uow:
            uow.ledger.append_batch([make_event()])
            raise RuntimeError("abort")
    assert ledger.events == []


def test_credit_error_taxonomy_has_stable_specific_types():
    errors = [CreditLedgerValidationError, CreditLedgerIdempotencyConflict,
              CreditLedgerReferenceNotFound, CreditLedgerConcurrencyConflict,
              CreditLedgerTransactionError]
    assert all(issubclass(error, Exception) for error in errors)
    assert len(set(errors)) == 5
