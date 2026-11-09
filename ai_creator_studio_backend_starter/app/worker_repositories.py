"""Worker-facing repository ports and SQLite compatibility adapters.

The ports separate worker responsibilities from the monolithic legacy SQL module.
Adapters intentionally delegate to the proven SQLite implementation until each
aggregate receives its own SQL implementation and PostgreSQL integration suite.
"""
from __future__ import annotations
from typing import Any, Protocol, runtime_checkable
from app.repositories.output import OutputRepository


@runtime_checkable
class OutboxRepository(Protocol):
    def initialize(self) -> None: ...
    def claim_next_outbox(self, worker_id: str, lease_seconds: int) -> dict[str, Any] | None: ...
    def get_job(self, job_id: str) -> dict[str, Any] | None: ...
    def mark_outbox_unknown(self, event_id: str, job_id: str, error: str, worker_id: str) -> bool: ...
    def complete_outbox_submission(self, event_id: str, job_id: str, provider_request_id: str, worker_id: str) -> dict[str, Any]: ...
    def heartbeat_worker(self, worker_id: str, state: str, metadata: dict[str, Any] | None = None) -> None: ...


@runtime_checkable
class PollRepository(Protocol):
    def initialize(self) -> None: ...
    def claim_next_poll_task(self, worker_id: str, lease_seconds: int) -> dict[str, Any] | None: ...
    def get_job(self, job_id: str) -> dict[str, Any] | None: ...
    def transition_job(self, job_id: str, target: str, **kwargs: Any) -> dict[str, Any]: ...
    def complete_poll_task(self, task_id: str, worker_id: str) -> bool: ...
    def mark_provider_succeeded_for_poll(self, task_id: str, worker_id: str, job_id: str, output_url: str) -> bool: ...
    def exhaust_poll_task(self, task_id: str, worker_id: str, job_id: str, **kwargs: Any) -> bool: ...
    def reschedule_poll_task(self, task_id: str, worker_id: str, **kwargs: Any) -> bool: ...
    def record_output(self, job_id: str, storage_key: str, media_type: str, size_bytes: int) -> dict[str, Any]: ...
    def finalize_output_success(self, task_id: str, worker_id: str, job_id: str, **kwargs: Any) -> bool: ...
    def update_job(self, job_id: str, updates: dict[str, Any], **kwargs: Any) -> dict[str, Any]: ...
    def heartbeat_worker(self, worker_id: str, state: str, metadata: dict[str, Any] | None = None) -> None: ...


@runtime_checkable
class OperationsRepository(Protocol):
    def initialize(self) -> None: ...
    def evaluate_operational_alerts(self, **kwargs: Any) -> list[dict[str, Any]]: ...
    def claim_alert_delivery(self, worker_id: str, lease_seconds: int = 120) -> dict[str, Any] | None: ...
    def finish_alert_delivery(self, delivery_id: str, *, worker_id: str, **kwargs: Any) -> bool: ...
    def heartbeat_worker(self, worker_id: str, state: str, metadata: dict[str, Any] | None = None) -> None: ...


from app.repositories.outbox import SQLiteOutboxRepository as _DedicatedSQLiteOutboxRepository

class SQLiteOutboxRepository(_DedicatedSQLiteOutboxRepository):
    """Backward-compatible worker-facing name for the dedicated Outbox adapter."""


from app.repositories.poll import SQLitePollRepository as _DedicatedSQLitePollRepository

class SQLitePollRepository(_DedicatedSQLitePollRepository):
    """Backward-compatible worker-facing name for the dedicated Poll adapter."""


class SQLiteOperationsRepository:
    """SQLite adapter; heartbeat persistence is dedicated, alert SQL remains bridged."""
    def __init__(self, implementation=None):
        self._impl=implementation
        from app.repositories.operations import (build_worker_heartbeat_repository,
            build_alert_delivery_repository, build_operations_monitoring_repository)
        self._heartbeats=build_worker_heartbeat_repository()
        self._deliveries=build_alert_delivery_repository()
        self._monitoring=build_operations_monitoring_repository()
    def initialize(self):
        if self._impl is not None: return self._impl.initialize()
        from app.schema_sqlite import initialize_schema
        from app.repositories.operations import SQLiteWorkerHeartbeatRepository
        storage,path=SQLiteWorkerHeartbeatRepository._context()
        with storage.transaction(path) as conn: initialize_schema(conn)
    def evaluate_operational_alerts(self, **kwargs):
        return self._monitoring.evaluate_alerts(**kwargs)
    def claim_alert_delivery(self, worker_id, lease_seconds=120):
        return self._deliveries.claim(worker_id, lease_seconds)
    def finish_alert_delivery(self, delivery_id, *, worker_id, **kwargs):
        return self._deliveries.finish(delivery_id, worker_id=worker_id, **kwargs)
    def heartbeat_worker(self, worker_id, state, metadata=None):
        if self._impl is not None: return self._impl.heartbeat_worker(worker_id,state,metadata)
        return self._heartbeats.heartbeat(worker_id,state,metadata)


def _ensure_sqlite() -> None:
    from app.storage import get_storage
    get_storage()  # fails closed for unimplemented PostgreSQL; no fallback


def build_outbox_repository() -> OutboxRepository:
    _ensure_sqlite()
    return SQLiteOutboxRepository()


def build_poll_repository() -> PollRepository:
    _ensure_sqlite()
    return SQLitePollRepository()


def build_operations_repository() -> OperationsRepository:
    _ensure_sqlite()
    return SQLiteOperationsRepository()


from dataclasses import dataclass


@dataclass(frozen=True)
class WorkerRepositories:
    """Single worker composition bundle for process-level dependency wiring."""
    outbox: OutboxRepository
    poll: PollRepository
    operations: OperationsRepository


def build_worker_repositories() -> WorkerRepositories:
    """Build worker ports from the configured backend without legacy-module coupling."""
    _ensure_sqlite()
    return WorkerRepositories(
        outbox=SQLiteOutboxRepository(),
        poll=SQLitePollRepository(),
        operations=SQLiteOperationsRepository(),
    )
