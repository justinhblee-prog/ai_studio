"""DB-neutral, immutable Credit Ledger event contracts.

This module deliberately does not choose account ownership, unit precision,
expiry/lot allocation, partial capture, or balance serialization strategy.
"""
from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CreditLedgerEventType(StrEnum):
    GRANT = "GRANT"
    RESERVE = "RESERVE"
    CAPTURE = "CAPTURE"
    RELEASE = "RELEASE"
    REFUND = "REFUND"
    ADJUST = "ADJUST"
    EXPIRE = "EXPIRE"


class CreditSettlementType(StrEnum):
    CAPTURED = "CAPTURED"
    RELEASED = "RELEASED"


class CreditLedgerEvent(BaseModel):
    """Immutable ledger fact; corrections are new events, never mutations."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(min_length=1)
    organization_id: str = Field(min_length=1)
    credit_account_id: str = Field(min_length=1)
    event_type: CreditLedgerEventType
    amount: Decimal = Field(gt=Decimal("0"))
    job_id: str | None = None
    execution_id: str | None = None
    quote_id: str | None = None
    reservation_event_id: str | None = None
    reversal_of_event_id: str | None = None
    idempotency_scope: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    reason_code: str | None = None
    actor_type: str = Field(min_length=1)
    actor_id: str = Field(min_length=1)
    approval_reference: str | None = None
    correlation_id: str | None = None
    created_at: datetime

    @model_validator(mode="after")
    def validate_event_references(self) -> Self:
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")
        if self.event_type == CreditLedgerEventType.RESERVE and not self.job_id:
            raise ValueError("RESERVE requires job_id")
        if self.event_type in {CreditLedgerEventType.CAPTURE, CreditLedgerEventType.RELEASE} and not self.reservation_event_id:
            raise ValueError(f"{self.event_type.value} requires reservation_event_id")
        if self.event_type == CreditLedgerEventType.REFUND:
            if not self.reversal_of_event_id:
                raise ValueError("REFUND requires reversal_of_event_id")
            if not self.reason_code:
                raise ValueError("REFUND requires reason_code")
        if self.event_type == CreditLedgerEventType.ADJUST:
            if not self.reason_code:
                raise ValueError("ADJUST requires reason_code")
            if not self.approval_reference:
                raise ValueError("ADJUST requires approval_reference")
        return self


class CreditReservationSettlement(BaseModel):
    """Single terminal settlement record; partial settlement is intentionally absent."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    reservation_event_id: str = Field(min_length=1)
    settlement_type: CreditSettlementType
    settlement_event_id: str = Field(min_length=1)
    settled_at: datetime

    @model_validator(mode="after")
    def validate_settlement_time(self) -> Self:
        if self.settled_at.tzinfo is None or self.settled_at.utcoffset() is None:
            raise ValueError("settled_at must be timezone-aware")
        return self


def validate_reservation_settlement(
    reserve_event: CreditLedgerEvent,
    settlement_event: CreditLedgerEvent,
) -> CreditReservationSettlement:
    """Validate one RESERVE -> CAPTURE/RELEASE settlement without DB assumptions."""
    if reserve_event.event_type != CreditLedgerEventType.RESERVE:
        raise ValueError("reservation_event must be RESERVE")
    expected = {
        CreditLedgerEventType.CAPTURE: CreditSettlementType.CAPTURED,
        CreditLedgerEventType.RELEASE: CreditSettlementType.RELEASED,
    }.get(settlement_event.event_type)
    if expected is None:
        raise ValueError("settlement event must be CAPTURE or RELEASE")
    if settlement_event.reservation_event_id != reserve_event.id:
        raise ValueError("settlement must reference the supplied RESERVE event")
    if (settlement_event.organization_id != reserve_event.organization_id
            or settlement_event.credit_account_id != reserve_event.credit_account_id
            or settlement_event.job_id != reserve_event.job_id):
        raise ValueError("settlement organization/account/job must match RESERVE")
    if settlement_event.amount != reserve_event.amount:
        raise ValueError("single settlement amount must equal the reservation amount")
    return CreditReservationSettlement(
        reservation_event_id=reserve_event.id,
        settlement_type=expected,
        settlement_event_id=settlement_event.id,
        settled_at=settlement_event.created_at,
    )


def validate_event_batch(events: list[CreditLedgerEvent] | tuple[CreditLedgerEvent, ...]) -> tuple[CreditLedgerEvent, ...]:
    """Validate an append-only batch before persistence, without choosing a DB strategy.

    Exact retries of the same event/idempotency key collapse to one canonical event.
    Reusing an event ID or scoped idempotency key for different facts is rejected.
    A reservation may have at most one terminal CAPTURE/RELEASE in the batch.
    Existing reservations may be settled in a later batch; callers must additionally
    validate those references against persisted history inside their transaction.
    """
    by_id: dict[str, CreditLedgerEvent] = {}
    by_key: dict[tuple[str, str], CreditLedgerEvent] = {}
    settlements: dict[str, CreditLedgerEvent] = {}
    canonical: list[CreditLedgerEvent] = []

    for event in events:
        prior_id = by_id.get(event.id)
        if prior_id is not None:
            if prior_id != event:
                raise ValueError(f"event id {event.id!r} is reused for different content")
            continue

        key = (event.idempotency_scope, event.idempotency_key)
        prior_key = by_key.get(key)
        if prior_key is not None:
            if prior_key != event:
                raise ValueError("idempotency scope/key is reused for different event content")
            by_id[event.id] = event
            continue

        if event.event_type in {CreditLedgerEventType.CAPTURE, CreditLedgerEventType.RELEASE}:
            assert event.reservation_event_id is not None
            prior_settlement = settlements.get(event.reservation_event_id)
            if prior_settlement is not None:
                raise ValueError("reservation has more than one terminal settlement in batch")
            settlements[event.reservation_event_id] = event

        by_id[event.id] = event
        by_key[key] = event
        canonical.append(event)

    # Validate relationships whose referenced events are included in this batch.
    for settlement in settlements.values():
        reserve = by_id.get(settlement.reservation_event_id or "")
        if reserve is not None:
            validate_reservation_settlement(reserve, settlement)
    for event in canonical:
        if event.event_type == CreditLedgerEventType.REFUND:
            original = by_id.get(event.reversal_of_event_id or "")
            if original is not None:
                validate_refund_reference(event, original)

    return tuple(canonical)


def validate_refund_reference(
    refund_event: CreditLedgerEvent,
    original_event: CreditLedgerEvent,
) -> None:
    """Validate refund provenance without imposing refund amount/partiality policy.

    Refund amount ceilings and cumulative refund accounting require persisted history
    and remain the responsibility of a future transactional adapter.
    """
    if refund_event.event_type != CreditLedgerEventType.REFUND:
        raise ValueError("refund_event must be REFUND")
    if original_event.event_type != CreditLedgerEventType.CAPTURE:
        raise ValueError("refund must reference a CAPTURE event")
    if refund_event.reversal_of_event_id != original_event.id:
        raise ValueError("refund must reference the supplied original event")
    if (refund_event.organization_id != original_event.organization_id
            or refund_event.credit_account_id != original_event.credit_account_id):
        raise ValueError("refund organization/account must match original CAPTURE")
