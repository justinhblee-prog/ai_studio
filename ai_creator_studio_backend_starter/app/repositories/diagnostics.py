"""Read-only Job diagnostics composition repository."""
from __future__ import annotations
from pathlib import Path
from typing import Any, Protocol, runtime_checkable
from app import config
from app.storage import get_storage


@runtime_checkable
class JobDiagnosticsRepository(Protocol):
    def get(self, job_id: str) -> dict[str, Any]: ...


class SQLiteJobDiagnosticsRepository:
    backend = "sqlite"

    def __init__(self, *, storage=None, events=None, outputs=None) -> None:
        self._storage = storage or get_storage()
        from app.repositories.event import SQLiteEventRepository
        from app.repositories.sqlite_output import build_output_repository
        self._events = events or SQLiteEventRepository()
        self._outputs = outputs or build_output_repository()

    def get(self, job_id: str) -> dict[str, Any]:
        from app.schema_sqlite import initialize_schema
        path = Path(getattr(config, "GENERATION_DATABASE_PATH", None) or config.ASSET_DATABASE_PATH).resolve()
        with self._storage.transaction(path) as conn:
            initialize_schema(conn)
            execution = conn.execute(
                "SELECT * FROM generation_executions WHERE job_id=? ORDER BY attempt_no DESC LIMIT 1", (job_id,)
            ).fetchone()
            outbox = conn.execute(
                "SELECT event_id,event_type,status,attempts,claimed_by,claimed_at,lease_expires_at,last_error,created_at,processed_at FROM generation_outbox WHERE job_id=? ORDER BY created_at DESC LIMIT 1", (job_id,)
            ).fetchone()
            poll = conn.execute(
                "SELECT task_id,phase,status,attempts,available_at,claimed_by,lease_expires_at,last_error,created_at,updated_at,completed_at FROM generation_poll_tasks WHERE job_id=?", (job_id,)
            ).fetchone()
        output = self._outputs.get(job_id)
        if output:
            output.pop("storage_key", None)
        events = self._events.list_for_job(job_id)
        for event in events:
            payload = event.get("payload")
            if isinstance(payload, dict):
                payload.pop("storage_key", None)
        return {
            "events": events,
            "execution": dict(execution) if execution else None,
            "output": output,
            "outbox": dict(outbox) if outbox else None,
            "poll_task": dict(poll) if poll else None,
        }


def build_job_diagnostics_repository(backend: str | None = None) -> JobDiagnosticsRepository:
    selected = (backend or getattr(config, "DATABASE_BACKEND", "sqlite")).strip().lower()
    if selected == "sqlite": return SQLiteJobDiagnosticsRepository()
    if selected == "postgresql":
        raise RuntimeError("PostgreSQL Job Diagnostics Repository is not implemented; refusing SQLite fallback.")
    raise ValueError(f"Unsupported DATABASE_BACKEND: {selected}")
