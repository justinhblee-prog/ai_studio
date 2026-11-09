"""Application-facing append-only Job Event repository port."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Protocol, runtime_checkable
from app import config
from app.storage import get_storage


@runtime_checkable
class EventRepository(Protocol):
    def list_for_job(self, job_id: str) -> list[dict[str, Any]]: ...
    def append_in_transaction(self, connection: Any, *, job_id: str,
                              from_status: str | None, to_status: str | None,
                              event_type: str, payload: dict[str, Any] | None,
                              created_at: str, actor_id: str | None = None) -> None: ...


class SQLiteEventRepository:
    """SQLite Event adapter; append uses the caller's connection to preserve atomicity."""
    backend = "sqlite"

    def __init__(self, implementation: Any | None = None) -> None:
        # `implementation` is accepted for compatibility with the former adapter constructor.
        self._implementation = implementation

    @staticmethod
    def _db_path() -> Path:
        return Path(getattr(config, "GENERATION_DATABASE_PATH", None) or config.ASSET_DATABASE_PATH).resolve()

    def list_for_job(self, job_id: str) -> list[dict[str, Any]]:
        if self._implementation is not None:
            return self._implementation.list_events(job_id)
        from app.schema_sqlite import initialize_schema
        with get_storage().transaction(self._db_path()) as conn:
            initialize_schema(conn)
            rows = conn.execute(
                "SELECT * FROM generation_job_events WHERE job_id=? ORDER BY event_id", (job_id,)
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["payload"] = json.loads(item.pop("payload_json"))
            result.append(item)
        return result

    def append_in_transaction(self, connection: Any, *, job_id: str,
                              from_status: str | None, to_status: str | None,
                              event_type: str, payload: dict[str, Any] | None,
                              created_at: str, actor_id: str | None = None) -> None:
        """Append to an existing transaction; never opens/commits a separate connection."""
        connection.execute(
            """INSERT INTO generation_job_events
            (job_id,from_status,to_status,event_type,actor_id,payload_json,created_at)
            VALUES(?,?,?,?,?,?,?)""",
            (job_id, from_status, to_status, event_type, actor_id,
             json.dumps(payload or {}, sort_keys=True), created_at),
        )
