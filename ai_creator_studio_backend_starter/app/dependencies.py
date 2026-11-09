"""Composition-root dependencies shared by API and worker entry points."""
from __future__ import annotations
from functools import lru_cache
from app.repositories.job import JobRepository, SQLiteJobRepository
from app.repositories.event import EventRepository, SQLiteEventRepository
from app import config

@lru_cache(maxsize=1)
def get_job_repository() -> JobRepository:
    backend = getattr(config, "DATABASE_BACKEND", "sqlite").strip().lower()
    if backend == "sqlite": return SQLiteJobRepository()
    if backend == "postgresql":
        raise RuntimeError("PostgreSQL JobRepository is not implemented; refusing SQLite fallback.")
    raise ValueError(f"Unsupported DATABASE_BACKEND: {backend}")

@lru_cache(maxsize=1)
def get_event_repository() -> EventRepository:
    backend = getattr(config, "DATABASE_BACKEND", "sqlite").strip().lower()
    if backend == "sqlite": return SQLiteEventRepository()
    if backend == "postgresql":
        raise RuntimeError("PostgreSQL EventRepository is not implemented; refusing SQLite fallback.")
    raise ValueError(f"Unsupported DATABASE_BACKEND: {backend}")


@lru_cache(maxsize=1)
def get_job_event_uow():
    from app.repositories.job_event_uow import build_job_event_uow
    return build_job_event_uow()


def get_job_lifecycle_service():
    from app.services.job_lifecycle import JobLifecycleService
    return JobLifecycleService(get_job_event_uow())


@lru_cache(maxsize=1)
def get_poll_task_admin_repository():
    from app.repositories.poll_admin import build_poll_task_admin_repository
    return build_poll_task_admin_repository()


@lru_cache(maxsize=1)
def get_outbox_admin_repository():
    from app.repositories.outbox_admin import build_outbox_admin_repository
    return build_outbox_admin_repository()


@lru_cache(maxsize=1)
def get_worker_health_repository():
    from app.repositories.operations import build_worker_health_repository
    return build_worker_health_repository()


@lru_cache(maxsize=1)
def get_operations_monitoring_repository():
    from app.repositories.operations import build_operations_monitoring_repository
    return build_operations_monitoring_repository()


@lru_cache(maxsize=1)
def get_operations_alert_read_repository():
    from app.repositories.operations import build_operations_alert_read_repository
    return build_operations_alert_read_repository()


@lru_cache(maxsize=1)
def get_job_diagnostics_repository():
    from app.repositories.diagnostics import build_job_diagnostics_repository
    return build_job_diagnostics_repository()
