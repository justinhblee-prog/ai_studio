"""Provider polling and output-persistence task repository boundary.

The SQLite adapter preserves the existing atomic SQL paths while providing a
stable aggregate-specific port. SQL ownership is migrated in a later step.
"""
from __future__ import annotations
from typing import Any, Protocol, runtime_checkable
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urlparse

@runtime_checkable
class PollRepository(Protocol):
    def initialize(self) -> None: ...
    def claim_next_poll_task(self, worker_id: str, lease_seconds: int) -> dict[str, Any] | None: ...
    def renew_poll_task_lease(self, task_id: str, worker_id: str, lease_seconds: int) -> bool: ...
    def get_job(self, job_id: str) -> dict[str, Any] | None: ...
    def transition_job(self, job_id: str, target: str, **kwargs: Any) -> dict[str, Any]: ...
    def complete_poll_task(self, task_id: str, worker_id: str) -> bool: ...
    def mark_provider_succeeded_for_poll(self, task_id: str, worker_id: str, job_id: str, output_url: str) -> bool: ...
    def fail_provider_poll_task(self, task_id: str, worker_id: str, job_id: str, *, error_code: str, message: str, event_type: str) -> bool: ...
    def exhaust_poll_task(self, task_id: str, worker_id: str, job_id: str, **kwargs: Any) -> bool: ...
    def reschedule_poll_task(self, task_id: str, worker_id: str, **kwargs: Any) -> bool: ...
    def record_output(self, job_id: str, storage_key: str, media_type: str, size_bytes: int) -> dict[str, Any]: ...
    def finalize_output_success(self, task_id: str, worker_id: str, job_id: str, **kwargs: Any) -> bool: ...
    def update_job(self, job_id: str, updates: dict[str, Any], **kwargs: Any) -> dict[str, Any]: ...
    def heartbeat_worker(self, worker_id: str, state: str, metadata: dict[str, Any] | None = None) -> None: ...

class SQLitePollRepository:
    backend = "sqlite"
    def __init__(self, implementation=None) -> None:
        # Optional implementation is a compatibility seam; default operation owns Poll SQL.
        self._impl=implementation
        from app.repositories.sqlite_output import build_output_repository
        from app.repositories.job_event_uow import SQLiteJobEventUnitOfWork
        from app.services.job_lifecycle import JobLifecycleService
        self._output=build_output_repository()
        if self._impl is None:
            from app.repositories.job import build_job_repository
            from app.repositories.operations import build_worker_heartbeat_repository
            self._jobs=build_job_repository()
            self._heartbeats=build_worker_heartbeat_repository()
        else:
            self._jobs=None
            self._heartbeats=None
        self._job_event_uow=SQLiteJobEventUnitOfWork(self._impl)
        self._lifecycle=JobLifecycleService(self._job_event_uow)
    @staticmethod
    def _context():
        from app import config
        from app.storage import get_storage
        path=Path(getattr(config,"GENERATION_DATABASE_PATH",None) or config.ASSET_DATABASE_PATH).resolve()
        return get_storage(),path
    def initialize(self):
        if self._impl is not None: return self._impl.initialize()
        from app.schema_sqlite import initialize_schema
        storage,path=self._context()
        with storage.transaction(path) as conn: initialize_schema(conn)
    def claim_next_poll_task(self, worker_id, lease_seconds):
        from app.repositories.lease_validation import validate_worker_lease
        validate_worker_lease(worker_id, lease_seconds)
        if self._impl is not None: return self._impl.claim_next_poll_task(worker_id,lease_seconds)
        storage,path=self._context(); now_dt=datetime.now(timezone.utc); now=now_dt.isoformat()
        lease=(now_dt+timedelta(seconds=lease_seconds)).isoformat(); self.initialize()
        with storage.transaction(path) as conn:
            storage.begin_write(conn)
            conn.execute("UPDATE generation_poll_tasks SET status='pending',claimed_by=NULL,claimed_at=NULL,lease_expires_at=NULL,available_at=?,last_error='Poll worker lease expired; safe GET/output task requeued.',updated_at=? WHERE status='processing' AND lease_expires_at < ?",(now,now,now))
            row=conn.execute("SELECT * FROM generation_poll_tasks WHERE status='pending' AND available_at<=? ORDER BY available_at,created_at LIMIT 1",(now,)).fetchone()
            if row is None: return None
            changed=conn.execute("UPDATE generation_poll_tasks SET status='processing',attempts=attempts+1,claimed_by=?,claimed_at=?,lease_expires_at=?,updated_at=? WHERE task_id=? AND status='pending'",(worker_id,now,lease,now,row["task_id"]))
            if changed.rowcount != 1: return None
            return dict(row)|{"status":"processing","attempts":int(row["attempts"])+1,"claimed_by":worker_id,"claimed_at":now,"lease_expires_at":lease}
    def renew_poll_task_lease(self, task_id, worker_id, lease_seconds):
        """Extend only a still-live lease owned by this worker.

        An expired lease is never resurrected: the claim/recovery path may already
        have transferred ownership, so renewal is fenced by status, owner, and expiry.
        """
        from app.repositories.lease_validation import validate_worker_lease
        validate_worker_lease(worker_id, lease_seconds)
        if not isinstance(task_id, str) or not task_id.strip():
            raise ValueError("task_id must be a non-empty string")
        if self._impl is not None:
            renew = getattr(self._impl, "renew_poll_task_lease", None)
            return bool(renew(task_id, worker_id, lease_seconds)) if renew else False
        storage, path = self._context()
        now_dt = datetime.now(timezone.utc)
        now = now_dt.isoformat()
        lease = (now_dt + timedelta(seconds=lease_seconds)).isoformat()
        self.initialize()
        from app.sql import sqlite_worker as sql
        with storage.transaction(path) as conn:
            changed = conn.execute(sql.POLL_LEASE_RENEW, (lease, now, task_id, worker_id, now))
            return changed.rowcount == 1

    def get_job(self, job_id):
        if self._impl is not None: return self._impl.get_job(job_id)
        return self._jobs.get(job_id)
    def transition_job(self, job_id, target, **kwargs): return self._lifecycle.transition(job_id, target, **kwargs)
    def complete_poll_task(self, task_id, worker_id):
        if self._impl is not None: return self._impl.complete_poll_task(task_id,worker_id)
        storage,path=self._context(); now=datetime.now(timezone.utc).isoformat(); self.initialize()
        with storage.transaction(path) as conn:
            changed=conn.execute("UPDATE generation_poll_tasks SET status='completed',claimed_by=NULL,claimed_at=NULL,lease_expires_at=NULL,last_error=NULL,updated_at=?,completed_at=? WHERE task_id=? AND status='processing' AND claimed_by=? AND lease_expires_at>=?",(now,now,task_id,worker_id,now))
            return changed.rowcount==1
    def reschedule_poll_task(self, task_id, worker_id, *, delay_seconds, error=None, phase=None):
        if self._impl is not None: return self._impl.reschedule_poll_task(task_id,worker_id,delay_seconds=delay_seconds,error=error,phase=phase)
        storage,path=self._context(); now_dt=datetime.now(timezone.utc); now=now_dt.isoformat(); available=(now_dt+timedelta(seconds=max(0.0,delay_seconds))).isoformat(); self.initialize()
        with storage.transaction(path) as conn:
            changed=conn.execute("UPDATE generation_poll_tasks SET attempts=CASE WHEN ? IS NOT NULL AND ? != phase THEN 0 ELSE attempts END,status='pending',phase=COALESCE(?,phase),available_at=?,claimed_by=NULL,claimed_at=NULL,lease_expires_at=NULL,last_error=?,updated_at=? WHERE task_id=? AND status='processing' AND claimed_by=? AND lease_expires_at>=?",(phase,phase,phase,available,(error or "")[:500] or None,now,task_id,worker_id,now))
            return changed.rowcount==1
    def fail_provider_poll_task(self, task_id, worker_id, job_id, *, error_code, message, event_type):
        """Atomically fail a Job only while this worker still owns its live status-poll lease."""
        if self._impl is not None:
            return self._impl.fail_provider_poll_task(
                task_id, worker_id, job_id, error_code=error_code, message=message, event_type=event_type
            )
        from app.job_state import ALLOWED_TRANSITIONS, InvalidJobTransition
        from app.repositories.event import SQLiteEventRepository
        from app.repositories.execution import SQLiteExecutionRepository
        storage, path = self._context()
        now = datetime.now(timezone.utc).isoformat()
        self.initialize()
        with storage.transaction(path) as conn:
            storage.begin_write(conn)
            task = conn.execute(
                "SELECT status,claimed_by,phase,lease_expires_at FROM generation_poll_tasks WHERE task_id=? AND job_id=?",
                (task_id, job_id),
            ).fetchone()
            job = conn.execute("SELECT status FROM generation_jobs WHERE job_id=?", (job_id,)).fetchone()
            if (task is None or task["status"] != "processing" or task["claimed_by"] != worker_id
                    or task["phase"] != "status" or not task["lease_expires_at"]
                    or task["lease_expires_at"] < now or job is None):
                return False
            if "failed" not in ALLOWED_TRANSITIONS.get(job["status"], frozenset()):
                raise InvalidJobTransition(f"Job status transition not allowed: {job['status']} -> failed")
            conn.execute(
                "UPDATE generation_jobs SET status='failed',error_code=?,message=?,updated_at=?,version=version+1 WHERE job_id=?",
                (error_code, message, now, job_id),
            )
            SQLiteExecutionRepository().apply_job_transition_in_transaction(
                conn, job_id=job_id, target_status="failed", updates={}, finished_at=now
            )
            SQLiteEventRepository().append_in_transaction(
                conn, job_id=job_id, from_status=job["status"], to_status="failed",
                event_type=event_type, payload={"error_code": error_code}, created_at=now,
            )
            conn.execute(
                "UPDATE generation_poll_tasks SET status='completed',claimed_by=NULL,claimed_at=NULL,lease_expires_at=NULL,last_error=NULL,updated_at=?,completed_at=? WHERE task_id=?",
                (now, now, task_id),
            )
            return True

    @staticmethod
    def _validate_provider_output_reference(output_url: str) -> None:
        """Reject malformed provider references before making them durable."""
        if not isinstance(output_url, str) or not output_url or len(output_url) > 4096:
            raise ValueError("Provider output reference must be a non-empty URL of at most 4096 characters.")
        if any(ord(char) < 32 or char.isspace() for char in output_url):
            raise ValueError("Provider output reference contains whitespace or control characters.")
        parsed = urlparse(output_url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("Provider output reference must be a credential-free HTTPS URL.")

    def mark_provider_succeeded_for_poll(self, task_id, worker_id, job_id, output_url):
        self._validate_provider_output_reference(output_url)
        if self._impl is not None: return self._impl.mark_provider_succeeded_for_poll(task_id,worker_id,job_id,output_url)
        from app.job_state import ALLOWED_TRANSITIONS, InvalidJobTransition
        from app.repositories.event import SQLiteEventRepository
        from app.repositories.execution import SQLiteExecutionRepository
        storage,path=self._context(); now=datetime.now(timezone.utc).isoformat(); self.initialize()
        with storage.transaction(path) as conn:
            storage.begin_write(conn)
            task=conn.execute("SELECT status,claimed_by,phase,lease_expires_at FROM generation_poll_tasks WHERE task_id=? AND job_id=?",(task_id,job_id)).fetchone()
            job=conn.execute("SELECT status FROM generation_jobs WHERE job_id=?",(job_id,)).fetchone()
            if (task is None or task["status"]!="processing" or task["claimed_by"]!=worker_id
                    or task["phase"]!="status" or not task["lease_expires_at"]
                    or task["lease_expires_at"] < now or job is None): return False
            if "post_processing" not in ALLOWED_TRANSITIONS.get(job["status"],frozenset()):
                raise InvalidJobTransition(f"Job status transition not allowed: {job['status']} -> post_processing")
            conn.execute("UPDATE generation_jobs SET status='post_processing',provider_output_url=?,message=?,error_code=NULL,updated_at=?,version=version+1 WHERE job_id=?",(output_url,"Provider completed; output persistence is pending.",now,job_id))
            SQLiteExecutionRepository().apply_job_transition_in_transaction(conn,job_id=job_id,target_status="post_processing",updates={},finished_at=now)
            SQLiteEventRepository().append_in_transaction(conn,job_id=job_id,from_status=job["status"],to_status="post_processing",event_type="PROVIDER_SUCCEEDED",payload={"provider_output_url":output_url},created_at=now)
            conn.execute("UPDATE generation_poll_tasks SET phase='persist_output',status='pending',attempts=0,available_at=?,claimed_by=NULL,claimed_at=NULL,lease_expires_at=NULL,last_error=NULL,updated_at=? WHERE task_id=?",(now,now,task_id))
            return True
    def exhaust_poll_task(self, task_id, worker_id, job_id, *, phase, error):
        if self._impl is not None: return self._impl.exhaust_poll_task(task_id,worker_id,job_id,phase=phase,error=error)
        from app.repositories.event import SQLiteEventRepository
        storage,path=self._context(); now=datetime.now(timezone.utc).isoformat(); safe=(error or "Polling retry budget exhausted.")[:500]; self.initialize()
        with storage.transaction(path) as conn:
            storage.begin_write(conn)
            changed=conn.execute("UPDATE generation_poll_tasks SET status='needs_reconciliation',claimed_by=NULL,claimed_at=NULL,lease_expires_at=NULL,last_error=?,updated_at=? WHERE task_id=? AND status='processing' AND claimed_by=? AND lease_expires_at>=?",(safe,now,task_id,worker_id,now))
            if changed.rowcount!=1: return False
            job=conn.execute("SELECT status FROM generation_jobs WHERE job_id=?",(job_id,)).fetchone()
            if job:
                code="OUTPUT_SAVE_REQUIRES_REVIEW" if phase=="persist_output" else "PROVIDER_POLL_REQUIRES_REVIEW"
                message="Output persistence retry budget exhausted; operator review required." if phase=="persist_output" else "Provider status polling retry budget exhausted; operator review required."
                conn.execute("UPDATE generation_jobs SET error_code=?,message=?,updated_at=?,version=version+1 WHERE job_id=?",(code,message,now,job_id))
                SQLiteEventRepository().append_in_transaction(conn,job_id=job_id,from_status=job["status"],to_status=job["status"],event_type="POLL_RETRY_BUDGET_EXHAUSTED",payload={"phase":phase,"error":safe},created_at=now)
            return True
    def record_output(self, job_id, storage_key, media_type, size_bytes): return self._output.record(job_id, storage_key, media_type, size_bytes)
    def get_output(self, job_id): return self._output.get(job_id)
    def finalize_output_success(self, task_id, worker_id, job_id, **kwargs): return self._output.finalize_success(task_id, worker_id, job_id, **kwargs)
    def update_job(self, job_id, updates, **kwargs): return self._lifecycle.update(job_id, updates, **kwargs)
    def heartbeat_worker(self, worker_id, state, metadata=None):
        if self._impl is not None: return self._impl.heartbeat_worker(worker_id,state,metadata)
        return self._heartbeats.heartbeat(worker_id,state,metadata)

def build_poll_repository(backend: str | None = None) -> PollRepository:
    from app import config
    from app.storage import get_storage
    selected=(backend or getattr(config, "DATABASE_BACKEND", "sqlite")).strip().lower()
    if selected != "sqlite":
        raise RuntimeError("PostgreSQL storage driver is not implemented; refusing SQLite fallback")
    get_storage()
    return SQLitePollRepository()
