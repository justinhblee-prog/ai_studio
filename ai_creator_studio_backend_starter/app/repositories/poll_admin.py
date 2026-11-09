"""Workspace-scoped operator Poll Task administration repository."""
from __future__ import annotations
from typing import Any, Protocol, runtime_checkable
from datetime import datetime, timezone
from pathlib import Path

@runtime_checkable
class PollTaskAdminRepository(Protocol):
    def list_for_workspace(self, workspace_id: str, *, status: str | None = None, limit: int = 100) -> list[dict[str, Any]]: ...
    def retry(self, task_id: str, workspace_id: str, *, actor_id: str, reason: str) -> dict[str, Any]: ...

class SQLitePollTaskAdminRepository:
    backend="sqlite"
    def __init__(self, implementation=None):
        # Optional legacy bridge is retained for isolated compatibility tests.
        self._impl=implementation
    @staticmethod
    def _context():
        from app import config
        from app.storage import get_storage
        path=Path(getattr(config,"GENERATION_DATABASE_PATH",None) or config.ASSET_DATABASE_PATH).resolve()
        return get_storage(),path
    def _initialize(self):
        if self._impl is not None: return self._impl.initialize()
        from app.schema_sqlite import initialize_schema
        storage,path=self._context()
        with storage.transaction(path) as conn: initialize_schema(conn)
    def list_for_workspace(self, workspace_id, *, status=None, limit=100):
        if self._impl is not None: return self._impl.list_poll_tasks(workspace_id,status=status,limit=limit)
        storage,path=self._context(); self._initialize(); limit=max(1,min(int(limit),200))
        with storage.transaction(path) as conn:
            base="SELECT p.task_id,p.job_id,j.workspace_id,j.status AS job_status,j.provider,j.model,j.provider_request_id,p.phase,p.status,p.attempts,p.available_at,p.claimed_by,p.lease_expires_at,p.last_error,p.created_at,p.updated_at,p.completed_at FROM generation_poll_tasks p JOIN generation_jobs j ON j.job_id=p.job_id WHERE j.workspace_id=?"
            if status:
                rows=conn.execute(base+" AND p.status=? ORDER BY p.updated_at DESC LIMIT ?",(workspace_id,status,limit)).fetchall()
            else:
                rows=conn.execute(base+" ORDER BY p.updated_at DESC LIMIT ?",(workspace_id,limit)).fetchall()
        return [dict(row) for row in rows]
    def retry(self, task_id, workspace_id, *, actor_id, reason):
        from app.repositories.operator_validation import validate_operator_action, validate_resource_id
        actor_id, reason = validate_operator_action(actor_id, reason)
        task_id = validate_resource_id(task_id, "task_id")
        workspace_id = validate_resource_id(workspace_id, "workspace_id")
        if self._impl is not None: return self._impl.retry_poll_task(task_id,workspace_id,actor_id=actor_id,reason=reason)
        from app.repositories.event import SQLiteEventRepository
        storage,path=self._context(); now=datetime.now(timezone.utc).isoformat(); self._initialize()
        with storage.transaction(path) as conn:
            storage.begin_write(conn)
            row=conn.execute("SELECT p.*,j.status AS job_status,j.provider_request_id,j.provider_output_url FROM generation_poll_tasks p JOIN generation_jobs j ON j.job_id=p.job_id WHERE p.task_id=? AND j.workspace_id=?",(task_id,workspace_id)).fetchone()
            if row is None: raise KeyError(task_id)
            if row["status"]!="needs_reconciliation": raise ValueError("Poll task is not awaiting operator review")
            if row["phase"]=="status" and (row["job_status"]!="running" or not row["provider_request_id"]): raise ValueError("Job is not eligible for status polling recovery")
            if row["phase"]=="persist_output" and (row["job_status"]!="post_processing" or not row["provider_output_url"]): raise ValueError("Job is not eligible for output persistence recovery")
            changed = conn.execute("UPDATE generation_poll_tasks SET status='pending',attempts=0,available_at=?,claimed_by=NULL,claimed_at=NULL,lease_expires_at=NULL,last_error=NULL,updated_at=?,completed_at=NULL WHERE task_id=? AND status='needs_reconciliation'",(now,now,task_id))
            if changed.rowcount != 1:
                raise ValueError("Poll task changed while retry was being authorized")
            job_changed = conn.execute("UPDATE generation_jobs SET error_code=NULL,message=?,updated_at=?,version=version+1 WHERE job_id=? AND status=?",("Operator authorized a bounded Provider polling/output retry.",now,row["job_id"],row["job_status"]))
            if job_changed.rowcount != 1:
                raise ValueError("Job state changed while retry was being authorized")
            SQLiteEventRepository().append_in_transaction(conn,job_id=row["job_id"],from_status=row["job_status"],to_status=row["job_status"],event_type="POLL_TASK_MANUALLY_REQUEUED",actor_id=actor_id,payload={"task_id":task_id,"phase":row["phase"],"reason":reason,"workspace_id":workspace_id},created_at=now)
        tasks=self.list_for_workspace(workspace_id,limit=200)
        return next(item for item in tasks if item["task_id"]==task_id)

def build_poll_task_admin_repository(backend: str | None = None) -> PollTaskAdminRepository:
    from app import config
    from app.storage import get_storage
    selected=(backend or getattr(config,"DATABASE_BACKEND","sqlite")).strip().lower()
    if selected != "sqlite":
        raise RuntimeError("PostgreSQL storage driver is not implemented; refusing SQLite fallback")
    get_storage()
    return SQLitePollTaskAdminRepository()
