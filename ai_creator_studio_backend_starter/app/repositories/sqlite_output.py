"""SQLite implementation of the Output aggregate repository."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app import config
from app.job_state import ALLOWED_TRANSITIONS, InvalidJobTransition
from app.storage import get_storage
from app.sql import sqlite_worker as sql
from app.repositories.event import SQLiteEventRepository


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _db_path() -> Path:
    return Path(getattr(config, "GENERATION_DATABASE_PATH", None) or config.ASSET_DATABASE_PATH).resolve()


class SQLiteOutputRepository:
    backend = "sqlite"

    def _initialize(self) -> None:
        from app.schema_sqlite import initialize_schema
        with get_storage().transaction(_db_path()) as conn:
            initialize_schema(conn)

    def get(self, job_id: str) -> dict[str, Any] | None:
        self._initialize()
        with get_storage().transaction(_db_path()) as conn:
            row = conn.execute("SELECT * FROM generation_outputs WHERE job_id=?", (job_id,)).fetchone()
        return dict(row) if row else None

    def list_storage_keys(self) -> set[str]:
        """Return committed Output references for safe orphan-file maintenance."""
        self._initialize()
        with get_storage().transaction(_db_path()) as conn:
            rows = conn.execute("SELECT storage_key FROM generation_outputs").fetchall()
        return {str(row["storage_key"]) for row in rows if row["storage_key"]}

    def record(self, job_id: str, storage_key: str, media_type: str, size_bytes: int) -> dict[str, Any]:
        self._initialize()
        now = _now()
        with get_storage().transaction(_db_path()) as conn:
            get_storage().begin_write(conn)
            conn.execute(sql.OUTPUT_UPSERT,
                         ("out_" + uuid.uuid4().hex, job_id, storage_key, media_type, size_bytes, now, None))
        result = self.get(job_id)
        if result is None:
            raise RuntimeError("Output record was not visible after commit")
        return result

    @staticmethod
    def _validate_final_output(job_id: str, *, storage_key: str, media_type: str,
                               size_bytes: int, output_url: str) -> None:
        """Validate the private stored-output reference before DB success is committed."""
        extensions = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}
        if media_type not in extensions:
            raise ValueError("Final output media type is not supported.")
        if not isinstance(storage_key, str) or not storage_key or Path(storage_key).name != storage_key:
            raise ValueError("Final output storage key must be a plain file name.")
        if Path(storage_key).suffix.lower() != extensions[media_type]:
            raise ValueError("Final output file extension does not match its media type.")
        if isinstance(size_bytes, bool) or not isinstance(size_bytes, int) or size_bytes <= 0 or size_bytes > config.MAX_OUTPUT_BYTES:
            raise ValueError("Final output size is outside the configured limits.")
        safe_id = "".join(c for c in job_id if c.isalnum() or c in "-_")[:100]
        expected_url = f"/v1/generation-jobs/{safe_id}/output"
        if not safe_id or output_url != expected_url:
            raise ValueError("Final output URL must be the authenticated private output route for this Job.")

    def finalize_success(self, task_id: str, worker_id: str, job_id: str, *, storage_key: str,
                         media_type: str, size_bytes: int, output_url: str,
                         checksum_sha256: str | None = None) -> bool:
        """Commit Output, Job, Execution, Event and Poll Task state as one unit."""
        self._validate_final_output(job_id, storage_key=storage_key, media_type=media_type,
                                   size_bytes=size_bytes, output_url=output_url)
        if checksum_sha256 is not None:
            if not isinstance(checksum_sha256, str) or len(checksum_sha256) != 64 or any(ch not in "0123456789abcdef" for ch in checksum_sha256.lower()):
                raise ValueError("Output checksum must be a SHA-256 hex digest")
            checksum_sha256 = checksum_sha256.lower()
        self._initialize()
        now = _now()
        with get_storage().transaction(_db_path()) as conn:
            get_storage().begin_write(conn)
            task = conn.execute(
                "SELECT status,claimed_by,phase,lease_expires_at FROM generation_poll_tasks WHERE task_id=? AND job_id=?",
                (task_id, job_id),
            ).fetchone()
            job = conn.execute("SELECT status,workspace_id,owner_id FROM generation_jobs WHERE job_id=?", (job_id,)).fetchone()
            if (task is None or task["status"] != "processing" or task["claimed_by"] != worker_id
                    or task["phase"] != "persist_output" or not task["lease_expires_at"]
                    or task["lease_expires_at"] < now or job is None):
                return False
            if "succeeded" not in ALLOWED_TRANSITIONS.get(job["status"], frozenset()):
                raise InvalidJobTransition(f"Job status transition not allowed: {job['status']} -> succeeded")
            conn.execute(sql.OUTPUT_UPSERT,
                         ("out_" + uuid.uuid4().hex, job_id, storage_key, media_type, size_bytes, now, checksum_sha256))
            output = conn.execute("SELECT output_id FROM generation_outputs WHERE job_id=?", (job_id,)).fetchone()
            if output is None:
                raise RuntimeError("Output row was not visible inside finalization transaction")
            conn.execute("""INSERT OR IGNORE INTO generation_output_asset_links
                (link_id,output_id,job_id,workspace_id,owner_id,status,attempts,available_at,created_at,updated_at)
                VALUES(?,?,?,?,?,'pending',0,?,?,?)""",
                ("oal_" + uuid.uuid4().hex, output["output_id"], job_id, job["workspace_id"], job["owner_id"], now, now, now))
            conn.execute(sql.OUTPUT_JOB_SUCCEED,
                         (output_url, "Output downloaded and stored by the server.", now, job_id))
            conn.execute(sql.OUTPUT_EXECUTION_SUCCEED, (now, job_id, job_id))
            SQLiteEventRepository().append_in_transaction(
                conn, job_id=job_id, from_status=job["status"], to_status="succeeded",
                event_type="OUTPUT_PERSISTED",
                payload={"storage_key": storage_key, "media_type": media_type,
                         "size_bytes": size_bytes}, created_at=now,
            )
            conn.execute(sql.OUTPUT_POLL_COMPLETE, (now, now, task_id, worker_id))
        return True


def build_output_repository(backend: str | None = None) -> OutputRepository:
    selected = (backend or getattr(config, "DATABASE_BACKEND", "sqlite")).strip().lower()
    if selected == "sqlite":
        return SQLiteOutputRepository()
    if selected == "postgresql":
        from app.repositories.postgres_output import PostgreSQLOutputRepository
        return PostgreSQLOutputRepository()
    raise ValueError(f"Unsupported DATABASE_BACKEND: {selected}")
