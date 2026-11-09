"""Guarded in-memory job state transitions for the PoC backend.

Production must enforce the same rules transactionally in PostgreSQL.
"""
from __future__ import annotations

from typing import Any, Final

TERMINAL_STATES: Final[frozenset[str]] = frozenset({"succeeded", "failed"})
ALLOWED_TRANSITIONS: Final[dict[str, frozenset[str]]] = {
    "queued": frozenset({"running", "failed"}),
    "running": frozenset({"post_processing", "failed"}),
    "post_processing": frozenset({"succeeded"}),
    "succeeded": frozenset(),
    "failed": frozenset(),
}


class InvalidJobTransition(ValueError):
    """Raised when a job status change violates the lifecycle contract."""


def transition(job: dict[str, Any], target: str) -> None:
    """Apply a permitted status transition in-place or raise a clear error."""
    current = job.get("status")
    if target not in ALLOWED_TRANSITIONS:
        raise InvalidJobTransition(f"Unknown target job status: {target}")
    if current not in ALLOWED_TRANSITIONS:
        raise InvalidJobTransition(f"Unknown current job status: {current}")
    if target not in ALLOWED_TRANSITIONS[current]:
        raise InvalidJobTransition(f"Job status transition not allowed: {current} -> {target}")
    job["status"] = target
