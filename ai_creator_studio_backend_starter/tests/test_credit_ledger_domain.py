from datetime import datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.credits.domain import (
    CreditLedgerEvent, CreditLedgerEventType, CreditSettlementType,
    validate_reservation_settlement,
)


def event(event_type, **overrides):
    values = {
        "id": f"evt-{event_type.lower()}",
        "organization_id": "org-1",
        "credit_account_id": "acct-1",
        "event_type": event_type,
        "amount": Decimal("25"),
        "job_id": "job-1" if event_type == "RESERVE" else None,
        "idempotency_scope": "generation-job",
        "idempotency_key": f"key-{event_type.lower()}",
        "actor_type": "user",
        "actor_id": "user-1",
        "created_at": datetime.now(timezone.utc),
    }
    values.update(overrides)
    return CreditLedgerEvent(**values)


def test_reserve_event_requires_job_and_positive_amount():
    reserve = event("RESERVE")
    assert reserve.amount == Decimal("25")
    with pytest.raises(ValidationError):
        event("RESERVE", job_id=None)
    with pytest.raises(ValidationError):
        event("GRANT", amount=Decimal("0"))


def test_ledger_event_is_immutable():
    reserve = event("RESERVE")
    with pytest.raises(ValidationError):
        reserve.amount = Decimal("10")


def test_capture_and_release_require_reservation_reference():
    with pytest.raises(ValidationError):
        event("CAPTURE")
    with pytest.raises(ValidationError):
        event("RELEASE")
    assert event("CAPTURE", reservation_event_id="evt-reserve")
    assert event("RELEASE", reservation_event_id="evt-reserve")


def test_refund_and_adjust_require_audit_references():
    with pytest.raises(ValidationError):
        event("REFUND", reversal_of_event_id="evt-capture")
    with pytest.raises(ValidationError):
        event("ADJUST", reason_code="support_credit")
    assert event("REFUND", reversal_of_event_id="evt-capture", reason_code="approved_refund")
    assert event("ADJUST", reason_code="support_credit", approval_reference="ticket-123")


def test_reservation_settlement_requires_matching_single_capture():
    reserve = event("RESERVE")
    capture = event("CAPTURE", id="evt-capture", reservation_event_id=reserve.id,
                    job_id=reserve.job_id)
    settlement = validate_reservation_settlement(reserve, capture)
    assert settlement.settlement_type == CreditSettlementType.CAPTURED
    with pytest.raises(ValidationError):
        settlement.settlement_type = CreditSettlementType.RELEASED


def test_reservation_settlement_rejects_mismatched_account_job_and_amount():
    reserve = event("RESERVE")
    with pytest.raises(ValueError, match="organization/account/job"):
        validate_reservation_settlement(reserve, event("RELEASE", reservation_event_id=reserve.id,
            job_id=reserve.job_id, credit_account_id="acct-other"))
    with pytest.raises(ValueError, match="amount"):
        validate_reservation_settlement(reserve, event("CAPTURE", reservation_event_id=reserve.id,
            job_id=reserve.job_id, amount=Decimal("24")))


def test_reservation_settlement_rejects_partial_and_unknown_event_types():
    reserve = event("RESERVE")
    with pytest.raises(ValueError, match="CAPTURE or RELEASE"):
        validate_reservation_settlement(reserve, event("REFUND", reversal_of_event_id="evt-capture",
            reason_code="duplicate", job_id=reserve.job_id))


def test_event_requires_timezone_aware_timestamp():
    with pytest.raises(ValidationError, match="timezone-aware"):
        event("GRANT", created_at=datetime(2026, 11, 2))


def test_event_batch_collapses_exact_idempotent_replays():
    from app.credits.domain import validate_event_batch
    grant = event("GRANT")
    assert validate_event_batch([grant, grant]) == (grant,)


def test_event_batch_rejects_idempotency_key_payload_conflict():
    from app.credits.domain import validate_event_batch
    first = event("GRANT", id="evt-a", idempotency_key="same")
    second = event("GRANT", id="evt-b", idempotency_key="same", amount=Decimal("26"))
    with pytest.raises(ValueError, match="different event content"):
        validate_event_batch([first, second])


def test_event_batch_rejects_event_id_payload_conflict():
    from app.credits.domain import validate_event_batch
    first = event("GRANT", id="evt-a", idempotency_key="one")
    second = event("GRANT", id="evt-a", idempotency_key="two", amount=Decimal("26"))
    with pytest.raises(ValueError, match="event id"):
        validate_event_batch([first, second])


def test_event_batch_rejects_two_terminal_settlements_for_one_reservation():
    from app.credits.domain import validate_event_batch
    reserve = event("RESERVE")
    capture = event("CAPTURE", id="evt-capture", idempotency_key="capture",
                    reservation_event_id=reserve.id, job_id=reserve.job_id)
    release = event("RELEASE", id="evt-release", idempotency_key="release",
                    reservation_event_id=reserve.id, job_id=reserve.job_id)
    with pytest.raises(ValueError, match="more than one terminal settlement"):
        validate_event_batch([reserve, capture, release])


def test_event_batch_validates_reservation_when_pair_is_present():
    from app.credits.domain import validate_event_batch
    reserve = event("RESERVE")
    capture = event("CAPTURE", id="evt-capture", idempotency_key="capture",
                    reservation_event_id=reserve.id, job_id=reserve.job_id)
    assert validate_event_batch([reserve, capture]) == (reserve, capture)


def test_refund_reference_requires_original_capture_and_matching_account():
    from app.credits.domain import validate_refund_reference
    capture = event("CAPTURE", id="evt-capture", reservation_event_id="evt-reserve")
    refund = event("REFUND", id="evt-refund", reversal_of_event_id=capture.id,
                   reason_code="approved", credit_account_id=capture.credit_account_id)
    validate_refund_reference(refund, capture)
    with pytest.raises(ValueError, match="CAPTURE event"):
        validate_refund_reference(refund, event("GRANT", id="evt-grant"))
    with pytest.raises(ValueError, match="organization/account"):
        validate_refund_reference(refund.model_copy(update={"credit_account_id":"acct-other"}), capture)


def test_refund_batch_validates_original_when_present_but_does_not_assume_amount_policy():
    from app.credits.domain import validate_event_batch
    capture = event("CAPTURE", id="evt-capture", idempotency_key="capture",
                    reservation_event_id="evt-reserve")
    refund = event("REFUND", id="evt-refund", idempotency_key="refund",
                   reversal_of_event_id=capture.id, reason_code="approved",
                   amount=Decimal("10"))
    assert validate_event_batch([capture, refund]) == (capture, refund)


def test_refund_batch_rejects_wrong_account_original():
    from app.credits.domain import validate_event_batch
    capture = event("CAPTURE", id="evt-capture", idempotency_key="capture",
                    reservation_event_id="evt-reserve")
    refund = event("REFUND", id="evt-refund", idempotency_key="refund",
                   reversal_of_event_id=capture.id, reason_code="approved",
                   credit_account_id="acct-other")
    with pytest.raises(ValueError, match="organization/account"):
        validate_event_batch([capture, refund])
