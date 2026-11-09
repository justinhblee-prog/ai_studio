"""Application-facing Generation Job repository port."""
from __future__ import annotations
from typing import Any, Protocol, runtime_checkable
import base64
import json
import uuid

@runtime_checkable
class JobRepository(Protocol):
    def create(self, job: dict[str, Any], idempotency_key: str | None = None, daily_job_limit: int | None = None) -> tuple[dict[str, Any], bool]: ...
    def get(self, job_id: str) -> dict[str, Any] | None: ...
    def list_executions(self, job_id: str, *, limit: int = 20, cursor: str | None = None) -> dict[str, Any]: ...
    def list_outputs(self, job_id: str) -> dict[str, Any]: ...
    def list_for_workspace(self, workspace_id: str, *, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]: ...
    def get_idempotent(self, workspace_id: str, key: str) -> tuple[dict[str, Any], str] | None: ...
    def transition(self, job_id: str, target: str, **kwargs: Any) -> dict[str, Any]: ...
    def update(self, job_id: str, updates: dict[str, Any], **kwargs: Any) -> dict[str, Any]: ...
    def cancel_queued(self, job_id: str, *, actor_id: str, reason: str | None = None) -> dict[str, Any]: ...

class SQLiteJobRepository:
    """SQLite Job aggregate adapter with lifecycle and Execution SQL ownership.

    The optional implementation argument preserves the v0.31 compatibility seam
    used by tests and legacy callers. Normal construction uses this adapter's
    own transactional lifecycle implementation.
    """
    backend = "sqlite"

    def __init__(self, implementation: Any | None = None) -> None:
        self._impl = implementation

    @staticmethod
    def _context():
        from datetime import datetime, timezone
        from pathlib import Path
        from app import config
        from app.storage import get_storage
        path = Path(getattr(config, "GENERATION_DATABASE_PATH", None) or config.ASSET_DATABASE_PATH).resolve()
        return get_storage(), path, datetime.now(timezone.utc).isoformat()

    def initialize(self):
        if self._impl is not None:
            return self._impl.initialize()
        from app.schema_sqlite import initialize_schema
        storage, path, _ = self._context()
        with storage.transaction(path) as conn:
            initialize_schema(conn)

    def create(self, job, idempotency_key=None, daily_job_limit=None):
        # The v0.31 compatibility seam (_impl) predates the cap; it is not used by the runtime.
        if self._impl is not None: return self._impl.create_job(job, idempotency_key)
        from app.repositories.event import SQLiteEventRepository
        from app.repositories.execution import SQLiteExecutionRepository
        storage, path, now = self._context()
        self.initialize()
        with storage.transaction(path) as conn:
            storage.begin_write(conn)
            if idempotency_key:
                existing = conn.execute(
                    "SELECT j.* FROM generation_idempotency i JOIN generation_jobs j ON j.job_id=i.job_id WHERE i.workspace_id=? AND i.idempotency_key=?",
                    (job["workspace_id"], idempotency_key),
                ).fetchone()
                if existing:
                    value = self._decode_job(existing)
                    return value, False
            if daily_job_limit:
                from datetime import datetime as _dt, timezone as _tz
                from app.repositories.job_limits import check_limit, utc_day_start
                current = _dt.now(_tz.utc)
                used = conn.execute("SELECT COUNT(*) AS n FROM generation_jobs WHERE workspace_id=? AND created_at>=?",
                                    (job["workspace_id"], utc_day_start(current).isoformat())).fetchone()["n"]
                check_limit(daily_job_limit, int(used), current)
            from app.cost_cap import enforce_in_transaction
            enforce_in_transaction(conn, job)
            conn.execute("""INSERT INTO generation_jobs
                (job_id,workspace_id,owner_id,status,provider,model,provider_request_id,output_url,error_code,message,payload_hash,payload_json,provider_output_url,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (job["job_id"], job["workspace_id"], job["owner_id"], job["status"], job["provider"],
                 job.get("model"), job.get("provider_request_id"), job.get("output_url"), job.get("error_code"),
                 job.get("message"), job["payload_hash"], json.dumps(job["payload"], sort_keys=True),
                 job.get("provider_output_url"), now, now))
            SQLiteExecutionRepository().create_initial_attempt_in_transaction(
                conn, job_id=job["job_id"], execution_id="exec_" + uuid.uuid4().hex,
                provider=job["provider"], started_at=now)
            SQLiteEventRepository().append_in_transaction(
                conn, job_id=job["job_id"], from_status=None, to_status="queued",
                event_type="JOB_CREATED", actor_id=job["owner_id"], payload={}, created_at=now)
            if idempotency_key:
                conn.execute("INSERT INTO generation_idempotency(workspace_id,idempotency_key,payload_hash,job_id,created_at) VALUES(?,?,?,?,?)",
                             (job["workspace_id"], idempotency_key, job["payload_hash"], job["job_id"], now))
            conn.execute("INSERT INTO generation_outbox(event_id,job_id,event_type,payload_json,status,available_at,created_at) VALUES(?,?,?,?,?,?,?)",
                         ("obx_" + uuid.uuid4().hex, job["job_id"], "SUBMIT_GENERATION", "{}", "pending", now, now))
        return self.get(job["job_id"]), True

    @staticmethod
    def _decode_job(row):
        if row is None: return None
        value = dict(row)
        value["payload"] = json.loads(value.pop("payload_json"))
        return value

    def get(self, job_id):
        if self._impl is not None: return self._impl.get_job(job_id)
        storage, path, _ = self._context()
        self.initialize()
        with storage.transaction(path) as conn:
            row = conn.execute("SELECT * FROM generation_jobs WHERE job_id=?", (job_id,)).fetchone()
        return self._decode_job(row)

    def list_executions(self, job_id, *, limit=20, cursor=None):
        if self._impl is not None:
            method = getattr(self._impl, "list_executions", None)
            if not callable(method): raise NotImplementedError("Wrapped Job implementation does not support execution history.")
            return method(job_id, limit=limit, cursor=cursor)
        before_attempt = None
        if cursor:
            try:
                token = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode("ascii")
                prefix, raw_attempt = token.split(":", 1)
                before_attempt = int(raw_attempt)
                if prefix != "exec" or before_attempt < 1: raise ValueError
            except Exception as exc:
                raise ValueError("Invalid execution history cursor") from exc
        storage, path, _ = self._context()
        self.initialize()
        with storage.transaction(path) as conn:
            query = """SELECT e.execution_id,e.job_id,e.attempt_no,e.status,e.provider,e.provider_request_id,
                e.started_at,e.finished_at,e.error_code,j.model FROM generation_executions e
                JOIN generation_jobs j ON j.job_id=e.job_id WHERE e.job_id=?"""
            args: list[Any] = [job_id]
            if before_attempt is not None:
                query += " AND e.attempt_no<?"; args.append(before_attempt)
            query += " ORDER BY e.attempt_no DESC LIMIT ?"; args.append(limit + 1)
            rows = conn.execute(query, args).fetchall()
        has_more = len(rows) > limit
        rows = rows[:limit]
        status_map = {"queued": "PENDING", "submitted": "SUBMITTED", "running": "RUNNING", "post_processing": "RUNNING",
                      "succeeded": "SUCCEEDED", "failed": "FAILED", "cancelled": "CANCELED", "canceled": "CANCELED", "unknown": "UNKNOWN"}
        items = [{"id": row["execution_id"], "job_id": row["job_id"], "provider_id": row["provider"],
                  "model_id": row["model"], "attempt_number": row["attempt_no"],
                  "status": ("REQUIRES_RECONCILIATION" if row["status"] == "unknown" and row["error_code"] == "PROVIDER_START_UNKNOWN" else status_map.get(row["status"], "UNKNOWN")),
                  "provider_request_id": row["provider_request_id"], "started_at": row["started_at"],
                  "finished_at": row["finished_at"], "error_code": row["error_code"],
                  "created_at": row["started_at"]} for row in rows]
        next_cursor = None
        if has_more and rows:
            token = f"exec:{rows[-1]['attempt_no']}".encode("ascii")
            next_cursor = base64.urlsafe_b64encode(token).decode("ascii").rstrip("=")
        return {"data": items, "meta": {"next_cursor": next_cursor, "has_more": has_more}}

    def list_outputs(self, job_id):
        if self._impl is not None:
            method = getattr(self._impl, "list_outputs", None)
            if not callable(method): raise NotImplementedError("Wrapped Job implementation does not support Output history.")
            return method(job_id)
        storage, path, _ = self._context()
        self.initialize()
        with storage.transaction(path) as conn:
            rows = conn.execute("""SELECT o.output_id,o.job_id,o.media_type,o.size_bytes,o.created_at,o.checksum_sha256,
                l.status AS asset_link_status,l.asset_id,l.asset_version_id,l.provenance_id,
                COALESCE(l.checksum_sha256,o.checksum_sha256) AS resolved_checksum
                FROM generation_outputs o LEFT JOIN generation_output_asset_links l ON l.output_id=o.output_id
                WHERE o.job_id=? ORDER BY o.created_at DESC,o.output_id DESC""", (job_id,)).fetchall()
        return {"data": [{"id": row["output_id"], "job_id": row["job_id"], "mime_type": row["media_type"],
                          "size_bytes": row["size_bytes"], "created_at": row["created_at"],
                          "checksum_sha256": row["resolved_checksum"], "asset_link_status": row["asset_link_status"] or "not_queued",
                          "asset_id": row["asset_id"], "asset_version_id": row["asset_version_id"],
                          "provenance_record_id": row["provenance_id"]} for row in rows],
                "meta": {}}

    def list_for_workspace(self, workspace_id, *, limit=50, offset=0):
        if self._impl is not None:
            method = getattr(self._impl, "list_for_workspace", None)
            if not callable(method):
                raise NotImplementedError("Wrapped Job implementation does not support workspace listing.")
            return method(workspace_id, limit=limit, offset=offset)
        storage, path, _ = self._context()
        self.initialize()
        with storage.transaction(path) as conn:
            rows = conn.execute(
                "SELECT * FROM generation_jobs WHERE workspace_id=? ORDER BY created_at DESC, job_id DESC LIMIT ? OFFSET ?",
                (workspace_id, limit, offset),
            ).fetchall()
        return [self._decode_job(row) for row in rows]

    def get_idempotent(self, workspace_id, key):
        if self._impl is not None: return self._impl.get_idempotent_job(workspace_id, key)
        storage, path, _ = self._context()
        self.initialize()
        with storage.transaction(path) as conn:
            row = conn.execute("SELECT j.*,i.payload_hash AS idem_payload_hash FROM generation_idempotency i JOIN generation_jobs j ON j.job_id=i.job_id WHERE i.workspace_id=? AND i.idempotency_key=?", (workspace_id, key)).fetchone()
        if row is None: return None
        return self._decode_job(row), row["idem_payload_hash"]

    def transition(self, job_id, target, **kwargs):
        if self._impl is not None: return self._impl.transition_job(job_id, target, **kwargs)
        return self._write_lifecycle(job_id, target=target, **kwargs)

    def update(self, job_id, updates, **kwargs):
        if self._impl is not None: return self._impl.update_job(job_id, updates, **kwargs)
        return self._write_metadata(job_id, updates, **kwargs)

    def cancel_queued(self, job_id, *, actor_id, reason=None):
        """Cancel only before dispatch, atomically with the pending outbox event.

        The persisted lifecycle currently represents cancellation as terminal `failed`
        with the stable `JOB_CANCELLED` error code; this avoids changing the existing
        SQLite status CHECK constraint without a dedicated schema migration.
        """
        if self._impl is not None:
            method = getattr(self._impl, "cancel_queued", None)
            if not callable(method):
                raise NotImplementedError("Wrapped Job implementation does not support queued cancellation.")
            return method(job_id, actor_id=actor_id, reason=reason)
        from app.repositories.event import SQLiteEventRepository
        storage, path, now = self._context()
        self.initialize()
        with storage.transaction(path) as conn:
            storage.begin_write(conn)
            row = conn.execute("SELECT * FROM generation_jobs WHERE job_id=?", (job_id,)).fetchone()
            if row is None:
                raise KeyError(job_id)
            if row["status"] != "queued":
                raise ValueError("Only queued jobs can be cancelled; provider submission may already have started.")
            outbox = conn.execute(
                "SELECT * FROM generation_outbox WHERE job_id=? AND event_type='SUBMIT_GENERATION' ORDER BY created_at DESC LIMIT 1",
                (job_id,),
            ).fetchone()
            if outbox is None or outbox["status"] != "pending":
                raise ValueError("Job dispatch is already claimed or requires reconciliation; cancellation is unsafe.")
            message = "Cancelled before provider submission."
            if reason:
                message += " Reason: " + reason[:500]
            conn.execute(
                "UPDATE generation_jobs SET status='failed',error_code='JOB_CANCELLED',message=?,updated_at=?,version=version+1 WHERE job_id=? AND status='queued'",
                (message, now, job_id),
            )
            conn.execute(
                "UPDATE generation_outbox SET status='processed',processed_at=?,last_error='Cancelled before provider submission.' WHERE event_id=? AND status='pending'",
                (now, outbox["event_id"]),
            )
            conn.execute(
                "UPDATE generation_executions SET status='failed',finished_at=?,error_code='JOB_CANCELLED' WHERE job_id=? AND attempt_no=(SELECT MAX(attempt_no) FROM generation_executions WHERE job_id=?)",
                (now, job_id, job_id),
            )
            SQLiteEventRepository().append_in_transaction(
                conn, job_id=job_id, from_status="queued", to_status="failed",
                event_type="JOB_CANCELLED_BEFORE_DISPATCH", actor_id=actor_id,
                payload={"error_code": "JOB_CANCELLED", "reason": (reason or "")[:500], "outbox_event_id": outbox["event_id"]},
                created_at=now,
            )
        return self.get(job_id)

    def _write_lifecycle(self, job_id, *, target, updates=None, actor_id=None, event_type="STATUS_CHANGED"):
        from app.job_state import ALLOWED_TRANSITIONS, InvalidJobTransition
        from app.repositories.event import SQLiteEventRepository
        storage, path, now = self._context()
        updates = updates or {}
        allowed = {"provider_request_id", "output_url", "error_code", "message", "provider_output_url"}
        if set(updates) - allowed: raise ValueError("Unsupported job update field")
        self.initialize()
        with storage.transaction(path) as conn:
            storage.begin_write(conn)
            row = conn.execute("SELECT * FROM generation_jobs WHERE job_id=?", (job_id,)).fetchone()
            if row is None: raise KeyError(job_id)
            current = row["status"]
            if target not in ALLOWED_TRANSITIONS.get(current, frozenset()):
                raise InvalidJobTransition(f"Job status transition not allowed: {current} -> {target}")
            assignments = ["status=?", "updated_at=?", "version=version+1"]
            values = [target, now]
            for key, value in updates.items(): assignments.append(f"{key}=?"); values.append(value)
            values.append(job_id)
            conn.execute(f"UPDATE generation_jobs SET {','.join(assignments)} WHERE job_id=?", values)
            SQLiteEventRepository().append_in_transaction(
                conn, job_id=job_id, from_status=current, to_status=target,
                event_type=event_type, payload=updates, created_at=now, actor_id=actor_id)
            # Execution SQL is delegated but shares this exact transaction/connection.
            from app.repositories.execution import SQLiteExecutionRepository
            SQLiteExecutionRepository().apply_job_transition_in_transaction(
                conn, job_id=job_id, target_status=target, updates=updates, finished_at=now)
        return self.get(job_id)

    def _write_metadata(self, job_id, updates, *, event_type="JOB_UPDATED"):
        from app.repositories.event import SQLiteEventRepository
        storage, path, now = self._context()
        allowed = {"provider_request_id", "output_url", "error_code", "message", "provider_output_url"}
        if set(updates) - allowed: raise ValueError("Unsupported job update field")
        self.initialize()
        with storage.transaction(path) as conn:
            storage.begin_write(conn)
            row = conn.execute("SELECT status FROM generation_jobs WHERE job_id=?", (job_id,)).fetchone()
            if row is None: raise KeyError(job_id)
            assignments = [f"{key}=?" for key in updates] + ["updated_at=?", "version=version+1"]
            conn.execute(f"UPDATE generation_jobs SET {','.join(assignments)} WHERE job_id=?", [*updates.values(), now, job_id])
            SQLiteEventRepository().append_in_transaction(
                conn, job_id=job_id, from_status=row["status"], to_status=row["status"],
                event_type=event_type, payload=updates, created_at=now)
        return self.get(job_id)


def build_job_repository(backend: str | None = None) -> JobRepository:
    from app import config
    selected = (backend or getattr(config, "DATABASE_BACKEND", "sqlite")).strip().lower()
    if selected == "sqlite": return SQLiteJobRepository()
    if selected == "postgresql":
        raise RuntimeError("PostgreSQL Job Repository is not implemented; refusing SQLite fallback.")
    raise ValueError(f"Unsupported DATABASE_BACKEND: {selected}")
