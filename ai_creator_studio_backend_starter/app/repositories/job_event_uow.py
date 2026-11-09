"""Atomic application boundary for Job lifecycle writes and append-only Events.

The current SQLite implementation owns a transaction per lifecycle command and
inserts its Event in that same transaction. This port intentionally exposes
atomic commands, not a caller-managed transaction spanning multiple commits.
"""
from __future__ import annotations
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class JobEventUnitOfWork(Protocol):
    def transition_job(self, job_id: str, target: str, **kwargs: Any) -> dict[str, Any]: ...
    def update_job(self, job_id: str, updates: dict[str, Any], **kwargs: Any) -> dict[str, Any]: ...
    def list_events(self, job_id: str) -> list[dict[str, Any]]: ...
    def reconcile_unknown_submission(self, job_id: str, **kwargs: Any) -> dict[str, Any]: ...


class SQLiteJobEventUnitOfWork:
    """Compose the existing transactional Job writer and append-only Event reader."""
    backend = "sqlite"

    def __init__(self, implementation: Any | None = None) -> None:
        # An explicitly supplied implementation remains a narrow compatibility seam.
        self._implementation = implementation
        from app.repositories.event import SQLiteEventRepository
        from app.repositories.job import SQLiteJobRepository
        self._jobs = SQLiteJobRepository(implementation)
        self._events = SQLiteEventRepository(implementation)
        if implementation is None:
            from app.repositories.outbox_admin import build_outbox_admin_repository
            self._outbox_admin = build_outbox_admin_repository()
        else:
            self._outbox_admin = None

    def transition_job(self, job_id: str, target: str, **kwargs: Any) -> dict[str, Any]:
        # The implementation updates Job/Execution and appends Event in one DB transaction.
        return self._jobs.transition(job_id, target, **kwargs)

    def update_job(self, job_id: str, updates: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        # Metadata mutation and its audit Event are likewise one transaction.
        return self._jobs.update(job_id, updates, **kwargs)

    def list_events(self, job_id: str) -> list[dict[str, Any]]:
        return self._events.list_for_job(job_id)

    def reconcile_unknown_submission(self, job_id: str, **kwargs: Any) -> dict[str, Any]:
        # Operator resolution, Job mutation, and audit Event are one legacy transaction.
        if self._implementation is not None:
            return self._implementation.reconcile_unknown_submission(job_id, **kwargs)
        return self._outbox_admin.reconcile_unknown_submission(job_id, **kwargs)


def build_job_event_uow(backend: str | None = None) -> JobEventUnitOfWork:
    from app import config
    selected = (backend or getattr(config, "DATABASE_BACKEND", "sqlite")).strip().lower()
    if selected == "sqlite":
        return SQLiteJobEventUnitOfWork()
    if selected == "postgresql":
        raise RuntimeError("PostgreSQL Job/Event Unit of Work is not implemented; refusing SQLite fallback.")
    raise ValueError(f"Unsupported DATABASE_BACKEND: {selected}")
