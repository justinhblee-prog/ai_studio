"""Storage boundary for Generation Job persistence.

The protocol deliberately describes the application-facing operations rather
than leaking SQL/driver details. SQLiteRepository is a compatibility adapter
around the proven v0.20 implementation. PostgreSQL is intentionally rejected
until its transaction/claim semantics have live integration coverage.
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class GenerationJobRepository(Protocol):
    def initialize(self) -> None: ...
    def create_job(self, job: dict[str, Any], idempotency_key: str | None = None) -> tuple[dict[str, Any], bool]: ...
    def get_job(self, job_id: str) -> dict[str, Any] | None: ...
    def get_idempotent_job(self, workspace_id: str, idempotency_key: str) -> tuple[dict[str, Any], str] | None: ...
    def transition_job(self, job_id: str, to_status: str, updates: dict[str, Any] | None = None, actor_id: str | None = None) -> dict[str, Any]: ...
    def claim_next_outbox(self, worker_id: str, lease_seconds: int) -> dict[str, Any] | None: ...
    def complete_outbox_submission(self, event_id: str, job_id: str, provider_request_id: str, worker_id: str) -> dict[str, Any]: ...
    def claim_next_poll_task(self, worker_id: str, lease_seconds: int) -> dict[str, Any] | None: ...
    def claim_alert_delivery(self, worker_id: str, lease_seconds: int = 120) -> dict[str, Any] | None: ...
    def finish_alert_delivery(self, delivery_id: str, *, worker_id: str, delivered: bool, error: str | None = None, retry_delay_seconds: float = 30, max_attempts: int = 8) -> bool: ...
    def heartbeat_worker(self, worker_id: str, state: str, metadata: dict[str, Any] | None = None) -> None: ...
    def worker_health(self, stale_after_seconds: int) -> dict[str, Any]: ...
    def diagnostics(self, job_id: str) -> dict[str, Any]: ...
    def operational_snapshot(self, stale_after_seconds: int) -> dict[str, Any]: ...


class SQLiteRepository:
    """Compatibility composition adapter over the extracted repository ports."""
    backend = "sqlite"

    def __init__(self) -> None:
        from app.repositories.job import build_job_repository
        from app.repositories.outbox import build_outbox_repository
        from app.repositories.poll import build_poll_repository
        from app.repositories.operations import (
            build_alert_delivery_repository, build_worker_heartbeat_repository,
            build_worker_health_repository, build_operations_monitoring_repository,
        )
        from app.repositories.diagnostics import build_job_diagnostics_repository
        self._jobs = build_job_repository()
        self._outbox = build_outbox_repository()
        self._poll = build_poll_repository()
        self._deliveries = build_alert_delivery_repository()
        self._heartbeats = build_worker_heartbeat_repository()
        self._worker_health = build_worker_health_repository()
        self._monitoring = build_operations_monitoring_repository()
        self._diagnostics = build_job_diagnostics_repository()

    def initialize(self) -> None:
        return self._jobs.initialize()

    def create_job(self, job: dict[str, Any], idempotency_key: str | None = None):
        return self._jobs.create(job, idempotency_key)

    def get_job(self, job_id: str):
        return self._jobs.get(job_id)

    def get_idempotent_job(self, workspace_id: str, idempotency_key: str):
        return self._jobs.get_idempotent(workspace_id, idempotency_key)

    def transition_job(self, job_id: str, to_status: str, updates=None, actor_id=None):
        return self._jobs.transition(job_id, to_status, updates=updates, actor_id=actor_id)

    def claim_next_outbox(self, worker_id: str, lease_seconds: int):
        return self._outbox.claim_next_outbox(worker_id, lease_seconds)

    def complete_outbox_submission(self, event_id: str, job_id: str, provider_request_id: str, worker_id: str):
        return self._outbox.complete_outbox_submission(event_id, job_id, provider_request_id, worker_id)

    def claim_next_poll_task(self, worker_id: str, lease_seconds: int):
        return self._poll.claim_next_poll_task(worker_id, lease_seconds)

    def claim_alert_delivery(self, worker_id: str, lease_seconds: int = 120):
        return self._deliveries.claim(worker_id, lease_seconds)

    def finish_alert_delivery(self, delivery_id: str, *, worker_id: str, delivered: bool, error=None, retry_delay_seconds=30, max_attempts=8):
        return self._deliveries.finish(delivery_id, worker_id=worker_id, delivered=delivered, error=error, retry_delay_seconds=retry_delay_seconds, max_attempts=max_attempts)

    def heartbeat_worker(self, worker_id: str, state: str, metadata=None):
        return self._heartbeats.heartbeat(worker_id, state, metadata)

    def worker_health(self, stale_after_seconds: int):
        return self._worker_health.worker_health(stale_after_seconds)

    def diagnostics(self, job_id: str):
        return self._diagnostics.get(job_id)

    def operational_snapshot(self, stale_after_seconds: int):
        return self._monitoring.snapshot(stale_after_seconds)


def build_repository(backend: str | None = None) -> GenerationJobRepository:
    """Build the configured adapter; never silently fall back across engines."""
    from app import config
    selected = (backend or getattr(config, "DATABASE_BACKEND", "sqlite")).strip().lower()
    if selected == "sqlite":
        return SQLiteRepository()
    if selected == "postgresql":
        raise RuntimeError(
            "DATABASE_BACKEND=postgresql is not available yet: the PostgreSQL runtime adapter "
            "must pass live transaction, idempotency, lease-claim, and multi-instance tests first."
        )
    raise ValueError(f"Unsupported DATABASE_BACKEND: {selected}")
