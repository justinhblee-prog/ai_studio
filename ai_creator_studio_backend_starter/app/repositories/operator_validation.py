"""Validation for privileged, human-initiated recovery actions."""
from __future__ import annotations


def validate_operator_action(actor_id: str, reason: str) -> tuple[str, str]:
    if not isinstance(actor_id, str) or not actor_id.strip() or len(actor_id) > 128:
        raise ValueError("actor_id must be a non-empty string of at most 128 characters")
    if not isinstance(reason, str):
        raise ValueError("reason must be a string")
    normalized = reason.strip()
    if not normalized or len(normalized) > 500:
        raise ValueError("reason must contain 1..500 non-whitespace characters")
    return actor_id.strip(), normalized


def validate_resource_id(value: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 128:
        raise ValueError(f"{field} must be a non-empty string of at most 128 characters")
    return value.strip()
