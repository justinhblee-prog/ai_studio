"""PostgreSQL Output aggregate adapter; deliberately not runtime-selected yet."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app import config
from app.job_state import ALLOWED_TRANSITIONS, InvalidJobTransition
from app.postgres import connect, apply_migrations


class PostgreSQLOutputRepository:
    backend = "postgresql"

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _validate_final_output(job_id: str, *, storage_key: str, media_type: str,
                               size_bytes: int, output_url: str) -> None:
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
        if not safe_id or output_url != f"/v1/generation-jobs/{safe_id}/output":
            raise ValueError("Final output URL must be the authenticated private output route for this Job.")

    @staticmethod
    def _jsonb(value: Any):
        try:
            from psycopg.types.json import Jsonb
            return Jsonb(value)
        except ImportError as exc:
            raise RuntimeError("psycopg 3 is required for PostgreSQL Output repository") from exc

    def initialize(self) -> None:
        apply_migrations()

    def get(self, job_id: str) -> dict[str, Any] | None:
        with connect() as conn:
            row = conn.execute("SELECT * FROM generation_outputs WHERE job_id=%s", (job_id,)).fetchone()
        return dict(row) if row else None

    def list_storage_keys(self) -> set[str]:
        with connect() as conn:
            rows = conn.execute("SELECT storage_key FROM generation_outputs").fetchall()
        return {str(row["storage_key"]) for row in rows if row.get("storage_key")}

    def record(self, job_id: str, storage_key: str, media_type: str, size_bytes: int) -> dict[str, Any]:
        if not isinstance(storage_key, str) or not storage_key or Path(storage_key).name != storage_key:
            raise ValueError("Output storage key must be a plain file name.")
        if isinstance(size_bytes, bool) or not isinstance(size_bytes, int) or size_bytes < 0 or size_bytes > config.MAX_OUTPUT_BYTES:
            raise ValueError("Output size is outside the configured limits.")
        if media_type not in {"image/png", "image/jpeg", "image/webp"}:
            raise ValueError("Output media type is not supported.")
        with connect() as conn:
            conn.execute(
                """INSERT INTO generation_outputs(output_id,job_id,storage_key,media_type,size_bytes,created_at)
                VALUES (%s,%s,%s,%s,%s,%s)
                ON CONFLICT(job_id) DO UPDATE SET storage_key=EXCLUDED.storage_key,
                  media_type=EXCLUDED.media_type,size_bytes=EXCLUDED.size_bytes,created_at=EXCLUDED.created_at""",
                ("out_" + uuid.uuid4().hex, job_id, storage_key, media_type, size_bytes, self._now()),
            )
        result = self.get(job_id)
        if result is None:
            raise RuntimeError("Output record was not visible after commit")
        return result

    def finalize_success(self, task_id: str, worker_id: str, job_id: str, *, storage_key: str,
                         media_type: str, size_bytes: int, output_url: str,
                         checksum_sha256: str | None = None) -> bool:
        self._validate_final_output(job_id, storage_key=storage_key, media_type=media_type,
                                    size_bytes=size_bytes, output_url=output_url)
        if checksum_sha256 is not None:
            if (not isinstance(checksum_sha256, str) or len(checksum_sha256) != 64
                    or any(ch not in "0123456789abcdef" for ch in checksum_sha256.lower())):
                raise ValueError("Output checksum must be a SHA-256 hex digest")
            checksum_sha256 = checksum_sha256.lower()
        now = self._now()
        with connect() as conn:
            # Lock both lease and aggregate; all state changes commit or roll back together.
            task = conn.execute(
                """SELECT status,claimed_by,phase,lease_expires_at FROM generation_poll_tasks
                WHERE task_id=%s AND job_id=%s FOR UPDATE""", (task_id, job_id)
            ).fetchone()
            job = conn.execute(
                "SELECT status,workspace_id,owner_id FROM generation_jobs WHERE job_id=%s FOR UPDATE", (job_id,)
            ).fetchone()
            if (task is None or task["status"] != "processing" or task["claimed_by"] != worker_id
                    or task["phase"] != "persist_output" or task["lease_expires_at"] is None
                    or task["lease_expires_at"] <= now or job is None):
                return False
            current = job["status"]
            if "succeeded" not in ALLOWED_TRANSITIONS.get(current, frozenset()):
                raise InvalidJobTransition(f"Job status transition not allowed: {current} -> succeeded")
            output_id = "out_" + uuid.uuid4().hex
            conn.execute(
                """INSERT INTO generation_outputs(output_id,job_id,storage_key,media_type,size_bytes,created_at,checksum_sha256)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT(job_id) DO UPDATE SET storage_key=EXCLUDED.storage_key,
                  media_type=EXCLUDED.media_type,size_bytes=EXCLUDED.size_bytes,
                  created_at=EXCLUDED.created_at,checksum_sha256=EXCLUDED.checksum_sha256""",
                (output_id, job_id, storage_key, media_type, size_bytes, now, checksum_sha256),
            )
            output = conn.execute("SELECT output_id FROM generation_outputs WHERE job_id=%s", (job_id,)).fetchone()
            conn.execute(
                """INSERT INTO generation_output_asset_links
                (link_id,output_id,job_id,workspace_id,owner_id,status,attempts,available_at,created_at,updated_at)
                VALUES (%s,%s,%s,%s,%s,'pending',0,%s,%s,%s)
                ON CONFLICT(output_id) DO NOTHING""",
                ("oal_" + uuid.uuid4().hex, output["output_id"], job_id, job["workspace_id"], job["owner_id"], now, now, now),
            )
            conn.execute(
                """UPDATE generation_jobs SET status='succeeded',output_url=%s,
                message=%s,updated_at=%s,version=version+1 WHERE job_id=%s""",
                (output_url, "Output downloaded and stored by the server.", now, job_id),
            )
            conn.execute(
                """UPDATE generation_executions SET status='succeeded',finished_at=%s
                WHERE job_id=%s AND attempt_no=(SELECT MAX(attempt_no) FROM generation_executions WHERE job_id=%s)""",
                (now, job_id, job_id),
            )
            conn.execute(
                """INSERT INTO generation_job_events
                (job_id,from_status,to_status,event_type,payload_json,created_at)
                VALUES (%s,%s,'succeeded','OUTPUT_PERSISTED',%s,%s)""",
                (job_id, current, self._jsonb({"storage_key": storage_key, "media_type": media_type,
                                               "size_bytes": size_bytes}), now),
            )
            conn.execute(
                """UPDATE generation_poll_tasks SET status='completed',claimed_by=NULL,claimed_at=NULL,
                lease_expires_at=NULL,completed_at=%s,updated_at=%s WHERE task_id=%s AND claimed_by=%s""",
                (now, now, task_id, worker_id),
            )
        return True
