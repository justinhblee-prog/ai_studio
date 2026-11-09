from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.credits.domain import CreditLedgerEvent, CreditLedgerEventType, validate_event_batch
from app.credits.repository import CreditLedgerRepository


class ContractOnlyRepository:
    """Test double for the port contract; not a production persistence adapter."""
    def __init__(self):
        self._events = []

    def append_batch(self, events):
        canonical = validate_event_batch(tuple(self._events) + tuple(events))
        new_ids = {event.id for event in canonical}
        self._events = list(canonical)
        return tuple(event for event in self._events if event.id in new_ids)

    def get_event(self, event_id):
        return next((event for event in self._events if event.id == event_id), None)

    def list_account_events(self, organization_id, credit_account_id):
        return tuple(event for event in self._events
                     if event.organization_id == organization_id
                     and event.credit_account_id == credit_account_id)


def make_event(event_id="evt-1", key="key-1", amount="10"):
    return CreditLedgerEvent(
        id=event_id, organization_id="org-1", credit_account_id="acct-1",
        event_type=CreditLedgerEventType.GRANT, amount=Decimal(amount),
        idempotency_scope="credit-account", idempotency_key=key,
        actor_type="system", actor_id="billing", created_at=datetime.now(timezone.utc),
    )


def test_repository_protocol_is_runtime_checkable():
    assert isinstance(ContractOnlyRepository(), CreditLedgerRepository)


def test_contract_port_supports_append_and_readback():
    repository = ContractOnlyRepository()
    event = make_event()
    assert repository.append_batch([event]) == (event,)
    assert repository.get_event(event.id) == event
    assert repository.list_account_events("org-1", "acct-1") == (event,)
    assert repository.list_account_events("org-other", "acct-1") == ()


def test_contract_port_exact_replay_is_single_fact():
    repository = ContractOnlyRepository()
    event = make_event()
    repository.append_batch([event])
    assert repository.append_batch([event]) == (event,)
    assert len(repository.list_account_events("org-1", "acct-1")) == 1


def test_contract_port_rejects_idempotency_key_payload_conflict():
    repository = ContractOnlyRepository()
    repository.append_batch([make_event()])
    with pytest.raises(ValueError, match="different event content"):
        repository.append_batch([make_event(event_id="evt-2", amount="11")])


def test_contract_port_rejects_batch_without_partial_mutation():
    repository = ContractOnlyRepository()
    original = make_event()
    repository.append_batch([original])
    with pytest.raises(ValueError):
        repository.append_batch([
            make_event(event_id="evt-2", key="key-2"),
            make_event(event_id="evt-3", key="key-2", amount="99"),
        ])
    assert repository.list_account_events("org-1", "acct-1") == (original,)
