"""Backward-compatible facade for extracted Generation Job repositories.

Aggregate SQL lives in app.repositories and app.sql. This module only preserves
legacy function names used by older callers and a narrow DB inspection helper.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app import config
from app.storage import get_storage


def _db_path() -> Path:
    # Resolve dynamically so tests and local deployments can override the path.
    return Path(getattr(config, "GENERATION_DATABASE_PATH", None) or config.ASSET_DATABASE_PATH).resolve()


def _connect() -> sqlite3.Connection:
    """Open a connection through the selected storage backend port."""
    return get_storage().connect(_db_path())


def initialize() -> None:
    """Initialize persistence schema through the SQLite schema module."""
    from app.schema_sqlite import initialize_schema
    with get_storage().transaction(_db_path()) as conn:
        initialize_schema(conn)


def create_job(job: dict[str, Any], idempotency_key: str | None = None) -> tuple[dict[str, Any], bool]:
    """Compatibility facade; Job creation SQL is owned by SQLiteJobRepository."""
    from app.repositories.job import SQLiteJobRepository
    return SQLiteJobRepository().create(job, idempotency_key)


def get_idempotent_job(workspace_id: str, key: str) -> tuple[dict[str, Any], str] | None:
    """Compatibility facade; idempotency lookup SQL is owned by SQLiteJobRepository."""
    from app.repositories.job import SQLiteJobRepository
    return SQLiteJobRepository().get_idempotent(workspace_id, key)


def get_job(job_id: str) -> dict[str, Any] | None:
    """Compatibility facade; Job lookup SQL is owned by SQLiteJobRepository."""
    from app.repositories.job import SQLiteJobRepository
    return SQLiteJobRepository().get(job_id)


def list_events(job_id: str) -> list[dict[str, Any]]:
    """Compatibility facade; Event reads are owned by SQLiteEventRepository."""
    from app.repositories.event import SQLiteEventRepository
    return SQLiteEventRepository().list_for_job(job_id)


def transition_job(job_id: str, target: str, *, updates: dict[str, Any] | None = None,
                   actor_id: str | None = None, event_type: str = "STATUS_CHANGED") -> dict[str, Any]:
    """Compatibility facade; Job lifecycle SQL is owned by SQLiteJobRepository."""
    from app.repositories.job import SQLiteJobRepository
    return SQLiteJobRepository().transition(job_id, target, updates=updates, actor_id=actor_id, event_type=event_type)


def update_job(job_id: str, updates: dict[str, Any], *, event_type: str = "JOB_UPDATED") -> dict[str, Any]:
    """Compatibility facade; Job metadata SQL is owned by SQLiteJobRepository."""
    from app.repositories.job import SQLiteJobRepository
    return SQLiteJobRepository().update(job_id, updates, event_type=event_type)


def _output_repository():
    from app.repositories.sqlite_output import build_output_repository
    return build_output_repository()


def record_output(job_id: str, storage_key: str, media_type: str, size_bytes: int) -> dict[str, Any]:
    """Compatibility facade; Output persistence lives in its aggregate repository."""
    return _output_repository().record(job_id, storage_key, media_type, size_bytes)


def get_output(job_id: str) -> dict[str, Any] | None:
    return _output_repository().get(job_id)


def list_output_storage_keys() -> set[str]:
    """List committed Output file references; used by explicit orphan cleanup."""
    return _output_repository().list_storage_keys()


def finalize_output_success(
    task_id: str, worker_id: str, job_id: str, *, storage_key: str,
    media_type: str, size_bytes: int, output_url: str, checksum_sha256: str | None = None,
) -> bool:
    """Compatibility facade for atomic Output aggregate finalization."""
    return _output_repository().finalize_success(
        task_id, worker_id, job_id, storage_key=storage_key, media_type=media_type,
        size_bytes=size_bytes, output_url=output_url, checksum_sha256=checksum_sha256,
    )


def diagnostics(job_id: str) -> dict[str, Any]:
    """Compatibility facade; diagnostics reads are composed by a dedicated repository."""
    from app.repositories.diagnostics import build_job_diagnostics_repository
    return build_job_diagnostics_repository().get(job_id)


# ---- Transactional outbox -------------------------------------------------

def claim_next_outbox(worker_id: str, lease_seconds: int = 60) -> dict[str, Any] | None:
    """Compatibility facade; Outbox SQL is owned by SQLiteOutboxRepository."""
    from app.repositories.outbox import SQLiteOutboxRepository
    return SQLiteOutboxRepository().claim_next_outbox(worker_id, lease_seconds)


def complete_outbox_submission(event_id: str, job_id: str, provider_request_id: str, worker_id: str) -> dict[str, Any]:
    """Compatibility facade; submission finalization is owned by OutboxRepository."""
    from app.repositories.outbox import SQLiteOutboxRepository
    return SQLiteOutboxRepository().complete_outbox_submission(event_id, job_id, provider_request_id, worker_id)


def mark_provider_succeeded_for_poll(task_id: str, worker_id: str, job_id: str, output_url: str) -> bool:
    """Compatibility facade; Poll SQL is owned by SQLitePollRepository."""
    from app.repositories.poll import SQLitePollRepository
    return SQLitePollRepository().mark_provider_succeeded_for_poll(task_id, worker_id, job_id, output_url)


def mark_outbox_unknown(event_id: str, job_id: str, error: str, worker_id: str) -> bool:
    """Compatibility facade; unknown submission handling is owned by OutboxRepository."""
    from app.repositories.outbox import SQLiteOutboxRepository
    return SQLiteOutboxRepository().mark_outbox_unknown(event_id, job_id, error, worker_id)


def _poll_task_counts() -> dict[str, int]:
    from app.repositories.operations import SQLiteWorkerHealthRepository
    return SQLiteWorkerHealthRepository().poll_task_counts()


def claim_next_poll_task(worker_id: str, lease_seconds: int = 60) -> dict[str, Any] | None:
    """Compatibility facade; Poll Task claiming SQL is owned by PollRepository."""
    from app.repositories.poll import SQLitePollRepository
    return SQLitePollRepository().claim_next_poll_task(worker_id, lease_seconds)


def reschedule_poll_task(task_id: str, worker_id: str, *, delay_seconds: float, error: str | None = None,
                         phase: str | None = None) -> bool:
    from app.repositories.poll import SQLitePollRepository
    return SQLitePollRepository().reschedule_poll_task(task_id, worker_id, delay_seconds=delay_seconds, error=error, phase=phase)


def complete_poll_task(task_id: str, worker_id: str) -> bool:
    from app.repositories.poll import SQLitePollRepository
    return SQLitePollRepository().complete_poll_task(task_id, worker_id)


def exhaust_poll_task(task_id: str, worker_id: str, job_id: str, *, phase: str, error: str) -> bool:
    from app.repositories.poll import SQLitePollRepository
    return SQLitePollRepository().exhaust_poll_task(task_id, worker_id, job_id, phase=phase, error=error)


def outbox_counts() -> dict[str, int]:
    from app.repositories.operations import SQLiteWorkerHealthRepository
    return SQLiteWorkerHealthRepository().outbox_counts()


# ---- Manual reconciliation / worker operations ---------------------------

def reconcile_unknown_submission(job_id: str, *, action: str, actor_id: str, reason: str,
                                 provider_request_id: str | None = None) -> dict[str, Any]:
    """Compatibility facade; Outbox reconciliation SQL is owned by OutboxAdminRepository."""
    from app.repositories.outbox_admin import SQLiteOutboxAdminRepository
    return SQLiteOutboxAdminRepository().reconcile_unknown_submission(job_id,action=action,actor_id=actor_id,
        reason=reason,provider_request_id=provider_request_id)


def list_poll_tasks(workspace_id: str, *, status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    """Compatibility facade; Poll Task administration SQL is repository-owned."""
    from app.repositories.poll_admin import SQLitePollTaskAdminRepository
    return SQLitePollTaskAdminRepository().list_for_workspace(workspace_id,status=status,limit=limit)


def retry_poll_task(task_id: str, workspace_id: str, *, actor_id: str, reason: str) -> dict[str, Any]:
    """Compatibility facade; operator retry SQL is repository-owned."""
    from app.repositories.poll_admin import SQLitePollTaskAdminRepository
    return SQLitePollTaskAdminRepository().retry(task_id,workspace_id,actor_id=actor_id,reason=reason)


def heartbeat_worker(worker_id: str, state: str = "running", metadata: dict[str, Any] | None = None) -> None:
    """Compatibility facade; worker heartbeat SQL is owned by WorkerHeartbeatRepository."""
    from app.repositories.operations import SQLiteWorkerHeartbeatRepository
    return SQLiteWorkerHeartbeatRepository().heartbeat(worker_id,state,metadata)

def worker_health(stale_after_seconds: int = 30) -> dict[str, Any]:
    from app.repositories.operations import SQLiteWorkerHealthRepository
    return SQLiteWorkerHealthRepository().worker_health(stale_after_seconds)


# ---- Operational metrics and durable alert state -------------------------

def operational_snapshot(worker_stale_seconds: int = 45) -> dict[str, Any]:
    """Compatibility facade; operational snapshot SQL is repository-owned."""
    from app.repositories.operations import SQLiteOperationsMonitoringRepository
    return SQLiteOperationsMonitoringRepository().snapshot(worker_stale_seconds)


def evaluate_operational_alerts(*, required_worker_types: tuple[str, ...] = ("outbox", "provider_poll"),
                                worker_stale_seconds: int = 45, queue_age_seconds: int = 120,
                                webhook_destination: str | None = None) -> list[dict[str, Any]]:
    """Compatibility facade; alert evaluation SQL is repository-owned."""
    from app.repositories.operations import SQLiteOperationsMonitoringRepository
    return SQLiteOperationsMonitoringRepository().evaluate_alerts(required_worker_types=required_worker_types,
        worker_stale_seconds=worker_stale_seconds,queue_age_seconds=queue_age_seconds,webhook_destination=webhook_destination)


def list_operational_alerts(*, status: str = "active", limit: int = 100) -> list[dict[str, Any]]:
    """Compatibility facade; alert read SQL is repository-owned."""
    from app.repositories.operations import SQLiteOperationsAlertReadRepository
    return SQLiteOperationsAlertReadRepository().list_alerts(status=status,limit=limit)


def claim_alert_delivery(worker_id: str, lease_seconds: int = 120) -> dict[str, Any] | None:
    """Compatibility facade; claim is fenced by an explicit Worker lease."""
    from app.repositories.operations import SQLiteAlertDeliveryRepository
    return SQLiteAlertDeliveryRepository().claim(worker_id,lease_seconds)


def finish_alert_delivery(delivery_id: str, *, worker_id: str, delivered: bool, error: str | None = None,
                          retry_delay_seconds: float = 30, max_attempts: int = 8) -> bool:
    """Compatibility facade; result acknowledgement requires the current lease owner."""
    from app.repositories.operations import SQLiteAlertDeliveryRepository
    return SQLiteAlertDeliveryRepository().finish(delivery_id,worker_id=worker_id,delivered=delivered,error=error,
        retry_delay_seconds=retry_delay_seconds,max_attempts=max_attempts)

def prometheus_metrics() -> str:
    """Compatibility facade; exposition formatting is owned by the metrics service."""
    from app.services.prometheus_metrics import render_operational_metrics
    return render_operational_metrics(operational_snapshot(config.WORKER_STALE_AFTER_SECONDS))


# Narrow storage inspection compatibility helpers retained for existing tests/tools.
def _now():
    """Legacy test/tool timestamp helper; business timestamps live in adapters."""
    return datetime.now(timezone.utc).isoformat()


def _db_path():
    from pathlib import Path
    return Path(getattr(config, "GENERATION_DATABASE_PATH", None) or config.ASSET_DATABASE_PATH).resolve()


def _connect():
    from app.storage import get_storage
    return get_storage().connect(_db_path())


# Test-only compatibility seam; production adapters import app.storage directly.
from app.storage import get_storage
