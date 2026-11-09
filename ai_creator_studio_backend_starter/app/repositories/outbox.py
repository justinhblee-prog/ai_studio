"""Provider submission Outbox repository port and dedicated SQLite adapter.

All Outbox state changes execute in the caller-selected storage transaction.
Unknown POST outcomes are quarantined for operator reconciliation, never replayed.
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Protocol, runtime_checkable
import uuid

@runtime_checkable
class OutboxRepository(Protocol):
    def initialize(self) -> None: ...
    def claim_next_outbox(self, worker_id: str, lease_seconds: int = 60) -> dict[str, Any] | None: ...
    def get_job(self, job_id: str) -> dict[str, Any] | None: ...
    def mark_outbox_unknown(self, event_id: str, job_id: str, error: str, worker_id: str) -> bool: ...
    def complete_outbox_submission(self, event_id: str, job_id: str, provider_request_id: str, worker_id: str) -> dict[str, Any]: ...
    def heartbeat_worker(self, worker_id: str, state: str, metadata: dict[str, Any] | None = None) -> None: ...

class SQLiteOutboxRepository:
    backend = "sqlite"
    def __init__(self, implementation=None) -> None:
        # Optional implementation is retained only as a compatibility seam for tests.
        self._impl = implementation
        from app.repositories.operations import build_worker_heartbeat_repository
        self._heartbeats = build_worker_heartbeat_repository() if implementation is None else None
        from app.repositories.job import build_job_repository
        self._jobs = build_job_repository() if implementation is None else None

    @staticmethod
    def _context():
        from app import config
        from app.storage import get_storage
        path = Path(getattr(config, "GENERATION_DATABASE_PATH", None) or config.ASSET_DATABASE_PATH).resolve()
        return get_storage(), path

    def initialize(self):
        if self._impl is not None:
            return self._impl.initialize()
        from app.schema_sqlite import initialize_schema
        storage, path = self._context()
        with storage.transaction(path) as conn:
            initialize_schema(conn)

    def get_job(self, job_id):
        if self._impl is not None:
            return self._impl.get_job(job_id)
        return self._jobs.get(job_id)

    def claim_next_outbox(self, worker_id, lease_seconds=60):
        from app.repositories.lease_validation import validate_worker_lease
        validate_worker_lease(worker_id, lease_seconds)
        if self._impl is not None:
            return self._impl.claim_next_outbox(worker_id, lease_seconds)
        from app.repositories.event import SQLiteEventRepository
        from app.repositories.execution import SQLiteExecutionRepository
        storage, path = self._context()
        now_dt = datetime.now(timezone.utc)
        now = now_dt.isoformat()
        lease = (now_dt + timedelta(seconds=lease_seconds)).isoformat()
        self.initialize()
        with storage.transaction(path) as conn:
            storage.begin_write(conn)
            expired = conn.execute("SELECT event_id,job_id FROM generation_outbox WHERE status='processing' AND lease_expires_at < ?", (now,)).fetchall()
            for item in expired:
                conn.execute("UPDATE generation_outbox SET status='needs_reconciliation',last_error=?,claimed_by=NULL,claimed_at=NULL,lease_expires_at=NULL WHERE event_id=?",
                    ("Worker lease expired after dispatch began; provider acceptance is unknown. Automatic replay suppressed.", item["event_id"]))
                conn.execute("UPDATE generation_jobs SET error_code='PROVIDER_START_UNKNOWN',message=?,updated_at=?,version=version+1 WHERE job_id=? AND status='queued'",
                    ("Provider dispatch outcome is unknown; manual reconciliation required.", now, item["job_id"]))
                SQLiteExecutionRepository().apply_job_transition_in_transaction(conn, job_id=item["job_id"], target_status="unknown", updates={"error_code":"PROVIDER_START_UNKNOWN"}, finished_at=now)
                SQLiteEventRepository().append_in_transaction(conn, job_id=item["job_id"], from_status="queued", to_status="queued", event_type="OUTBOX_LEASE_EXPIRED_UNKNOWN", payload={"outbox_event_id":item["event_id"]}, created_at=now)
            row = conn.execute("SELECT * FROM generation_outbox WHERE status='pending' AND available_at<=? ORDER BY created_at,event_id LIMIT 1", (now,)).fetchone()
            if row is None:
                return None
            changed = conn.execute("UPDATE generation_outbox SET status='processing',attempts=attempts+1,claimed_by=?,claimed_at=?,lease_expires_at=? WHERE event_id=? AND status='pending'",
                (worker_id, now, lease, row["event_id"]))
            if changed.rowcount != 1:
                return None
            return dict(row) | {"status":"processing", "claimed_by":worker_id, "claimed_at":now, "lease_expires_at":lease}

    def complete_outbox_submission(self, event_id, job_id, provider_request_id, worker_id):
        from app.repositories.lease_validation import validate_worker_id
        validate_worker_id(worker_id)
        if not isinstance(event_id, str) or not event_id.strip() or not isinstance(job_id, str) or not job_id.strip():
            raise ValueError("event_id and job_id must be non-empty strings")
        if not isinstance(provider_request_id, str) or not provider_request_id.strip():
            raise ValueError("provider_request_id must be a non-empty string")
        if self._impl is not None:
            return self._impl.complete_outbox_submission(event_id, job_id, provider_request_id, worker_id)
        from app.job_state import ALLOWED_TRANSITIONS, InvalidJobTransition
        from app.repositories.event import SQLiteEventRepository
        from app.repositories.execution import SQLiteExecutionRepository
        storage, path = self._context()
        now = datetime.now(timezone.utc).isoformat()
        self.initialize()
        with storage.transaction(path) as conn:
            storage.begin_write(conn)
            outbox = conn.execute("SELECT status,claimed_by,lease_expires_at FROM generation_outbox WHERE event_id=? AND job_id=?", (event_id, job_id)).fetchone()
            job = conn.execute("SELECT status FROM generation_jobs WHERE job_id=?", (job_id,)).fetchone()
            if (outbox is None or job is None or outbox["status"] != "processing"
                    or outbox["claimed_by"] != worker_id or not outbox["lease_expires_at"]
                    or outbox["lease_expires_at"] <= now):
                raise RuntimeError("Outbox lease is expired or not owned by this worker")
            current = job["status"]
            if "running" not in ALLOWED_TRANSITIONS.get(current, frozenset()):
                raise InvalidJobTransition(f"Job status transition not allowed: {current} -> running")
            changed_job = conn.execute("UPDATE generation_jobs SET status='running',provider_request_id=?,message=?,updated_at=?,version=version+1 WHERE job_id=? AND status=?",
                (provider_request_id, "Generation submitted; poll the job endpoint for status.", now, job_id, current))
            if changed_job.rowcount != 1:
                raise RuntimeError("Job state changed during Outbox finalization")
            SQLiteExecutionRepository().apply_job_transition_in_transaction(conn, job_id=job_id, target_status="running", updates={"provider_request_id":provider_request_id}, finished_at=now)
            changed_outbox = conn.execute("UPDATE generation_outbox SET status='processed',processed_at=?,lease_expires_at=NULL,last_error=NULL,claimed_by=NULL,claimed_at=NULL WHERE event_id=? AND job_id=? AND status='processing' AND claimed_by=? AND lease_expires_at>?", (now, event_id, job_id, worker_id, now))
            if changed_outbox.rowcount != 1:
                raise RuntimeError("Outbox lease was lost during finalization")
            SQLiteEventRepository().append_in_transaction(conn, job_id=job_id, from_status=current, to_status="running", event_type="PROVIDER_SUBMITTED", payload={"provider_request_id":provider_request_id,"outbox_event_id":event_id}, created_at=now)
            conn.execute("INSERT INTO generation_poll_tasks(task_id,job_id,phase,status,attempts,available_at,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
                ("poll_" + uuid.uuid4().hex, job_id, "status", "pending", 0, now, now, now))
        return self.get_job(job_id)

    def mark_outbox_unknown(self, event_id, job_id, error, worker_id):
        from app.repositories.lease_validation import validate_worker_id
        validate_worker_id(worker_id)
        if not isinstance(event_id, str) or not event_id.strip() or not isinstance(job_id, str) or not job_id.strip():
            raise ValueError("event_id and job_id must be non-empty strings")
        if not isinstance(error, str):
            raise ValueError("error must be a string")
        if self._impl is not None:
            return self._impl.mark_outbox_unknown(event_id, job_id, error, worker_id)
        from app.repositories.event import SQLiteEventRepository
        from app.repositories.execution import SQLiteExecutionRepository
        storage, path = self._context()
        now = datetime.now(timezone.utc).isoformat()
        safe_error = (error or "Provider dispatch outcome is unknown.")[:500]
        self.initialize()
        with storage.transaction(path) as conn:
            storage.begin_write(conn)
            changed = conn.execute("UPDATE generation_outbox SET status='needs_reconciliation',last_error=?,lease_expires_at=NULL,claimed_by=NULL,claimed_at=NULL WHERE event_id=? AND job_id=? AND status='processing' AND claimed_by=? AND lease_expires_at>?", (safe_error, event_id, job_id, worker_id, now))
            if changed.rowcount != 1:
                return False
            conn.execute("UPDATE generation_jobs SET error_code='PROVIDER_START_UNKNOWN',message=?,updated_at=?,version=version+1 WHERE job_id=? AND status='queued'", ("Provider dispatch outcome is unknown; manual reconciliation required.", now, job_id))
            SQLiteExecutionRepository().apply_job_transition_in_transaction(conn, job_id=job_id, target_status="unknown", updates={"error_code":"PROVIDER_START_UNKNOWN"}, finished_at=now)
            SQLiteEventRepository().append_in_transaction(conn, job_id=job_id, from_status="queued", to_status="queued", event_type="PROVIDER_START_UNKNOWN", payload={"outbox_event_id":event_id,"error":safe_error}, created_at=now)
            return True

    def heartbeat_worker(self, worker_id, state, metadata=None):
        if self._impl is not None:
            return self._impl.heartbeat_worker(worker_id, state, metadata)
        return self._heartbeats.heartbeat(worker_id, state, metadata)

def build_outbox_repository(backend: str | None = None) -> OutboxRepository:
    from app import config
    from app.storage import get_storage
    selected = (backend or getattr(config, "DATABASE_BACKEND", "sqlite")).strip().lower()
    if selected != "sqlite":
        raise RuntimeError("PostgreSQL storage driver is not implemented; refusing SQLite fallback")
    get_storage()
    return SQLiteOutboxRepository()
