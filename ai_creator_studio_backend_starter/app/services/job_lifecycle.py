"""Job lifecycle service that writes state and append-only Events atomically."""
from __future__ import annotations
from typing import Any
from app.repositories.job_event_uow import JobEventUnitOfWork, build_job_event_uow


class JobLifecycleService:
    def __init__(self, unit_of_work: JobEventUnitOfWork | None = None) -> None:
        self._uow = unit_of_work or build_job_event_uow()

    def transition(self, job_id: str, target: str, **kwargs: Any) -> dict[str, Any]:
        return self._uow.transition_job(job_id, target, **kwargs)

    def update(self, job_id: str, updates: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        return self._uow.update_job(job_id, updates, **kwargs)

    def events(self, job_id: str) -> list[dict[str, Any]]:
        return self._uow.list_events(job_id)

    def reconcile_unknown_submission(self, job_id: str, **kwargs: Any) -> dict[str, Any]:
        return self._uow.reconcile_unknown_submission(job_id, **kwargs)
