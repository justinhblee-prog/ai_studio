"""Shared validation for worker-owned task leases."""
from __future__ import annotations


def validate_worker_id(worker_id: str) -> None:
    """Validate a stable worker identity before any repository side effect."""
    if not isinstance(worker_id, str) or not worker_id.strip():
        raise ValueError("worker_id must be a non-empty string")
    if len(worker_id) > 128:
        raise ValueError("worker_id must be at most 128 characters")


def validate_worker_lease(worker_id: str, lease_seconds: int) -> None:
    """Reject ambiguous owners and invalid durations before touching storage."""
    validate_worker_id(worker_id)
    if isinstance(lease_seconds, bool) or not isinstance(lease_seconds, int) or lease_seconds < 1:
        raise ValueError("lease_seconds must be a positive integer")
