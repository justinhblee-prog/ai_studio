"""Operator-controlled resolution of uncertain provider submissions."""
from __future__ import annotations
from typing import Any, Protocol, runtime_checkable
from datetime import datetime, timezone
from pathlib import Path
import json, uuid

@runtime_checkable
class OutboxAdminRepository(Protocol):
    def reconcile_unknown_submission(self, job_id: str, *, action: str, actor_id: str,
                                     reason: str, provider_request_id: str | None = None) -> dict[str, Any]: ...

class SQLiteOutboxAdminRepository:
    backend="sqlite"
    def __init__(self, implementation=None):
        # Optional legacy implementation remains only for compatibility tests.
        self._impl=implementation
    @staticmethod
    def _context():
        from app import config
        from app.storage import get_storage
        path=Path(getattr(config,"GENERATION_DATABASE_PATH",None) or config.ASSET_DATABASE_PATH).resolve()
        return get_storage(),path
    def reconcile_unknown_submission(self, job_id, *, action, actor_id, reason, provider_request_id=None):
        from app.repositories.operator_validation import validate_operator_action, validate_resource_id
        actor_id, reason = validate_operator_action(actor_id, reason)
        job_id = validate_resource_id(job_id, "job_id")
        if provider_request_id is not None:
            if not isinstance(provider_request_id, str) or not provider_request_id.strip() or len(provider_request_id) > 256:
                raise ValueError("provider_request_id must be a non-empty string of at most 256 characters")
            provider_request_id = provider_request_id.strip()
        if self._impl is not None:
            return self._impl.reconcile_unknown_submission(job_id,action=action,actor_id=actor_id,reason=reason,provider_request_id=provider_request_id)
        if action not in {"attach_request_id","confirm_not_submitted"}:
            raise ValueError("Unsupported reconciliation action")
        if action=="attach_request_id" and not provider_request_id:
            raise ValueError("provider_request_id is required")
        if action=="confirm_not_submitted" and provider_request_id:
            raise ValueError("provider_request_id must be omitted")
        from app.schema_sqlite import initialize_schema
        from app.repositories.event import SQLiteEventRepository
        storage,path=self._context(); now=datetime.now(timezone.utc).isoformat()
        with storage.transaction(path) as conn:
            initialize_schema(conn); storage.begin_write(conn)
            job=conn.execute("SELECT * FROM generation_jobs WHERE job_id=?",(job_id,)).fetchone()
            outbox=conn.execute("SELECT * FROM generation_outbox WHERE job_id=? AND status='needs_reconciliation' ORDER BY created_at DESC LIMIT 1",(job_id,)).fetchone()
            execution=conn.execute("SELECT * FROM generation_executions WHERE job_id=? ORDER BY attempt_no DESC LIMIT 1",(job_id,)).fetchone()
            if job is None or outbox is None or execution is None or job["status"]!="queued":
                raise ValueError("Job is not awaiting provider reconciliation")
            if action=="attach_request_id":
                conn.execute("UPDATE generation_jobs SET status='running',provider_request_id=?,error_code=NULL,message=?,updated_at=?,version=version+1 WHERE job_id=?",(provider_request_id,"Provider request located by authorized operator; status polling can resume.",now,job_id))
                conn.execute("UPDATE generation_executions SET status='running',provider_request_id=?,error_code=NULL WHERE execution_id=?",(provider_request_id,execution["execution_id"]))
                changed = conn.execute("UPDATE generation_outbox SET status='processed',processed_at=?,last_error=NULL,lease_expires_at=NULL,claimed_by=NULL,claimed_at=NULL WHERE event_id=? AND status='needs_reconciliation'",(now,outbox["event_id"]))
                if changed.rowcount != 1:
                    raise ValueError("Outbox state changed during reconciliation")
                conn.execute("INSERT INTO generation_poll_tasks(task_id,job_id,phase,status,attempts,available_at,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(job_id) DO UPDATE SET phase='status',status='pending',attempts=0,available_at=excluded.available_at,claimed_by=NULL,claimed_at=NULL,lease_expires_at=NULL,last_error=NULL,updated_at=excluded.updated_at,completed_at=NULL",("poll_"+uuid.uuid4().hex,job_id,"status","pending",0,now,now,now))
                event_type="MANUAL_RECONCILIATION_REQUEST_ATTACHED"
                payload={"action":action,"provider_request_id":provider_request_id,"reason":reason,"outbox_event_id":outbox["event_id"]}
            else:
                next_attempt=int(execution["attempt_no"])+1
                changed = conn.execute("UPDATE generation_outbox SET status='processed',processed_at=?,last_error=?,lease_expires_at=NULL,claimed_by=NULL,claimed_at=NULL WHERE event_id=? AND status='needs_reconciliation'",(now,"Operator confirmed provider did not accept the previous submission.",outbox["event_id"]))
                if changed.rowcount != 1:
                    raise ValueError("Outbox state changed during reconciliation")
                conn.execute("INSERT INTO generation_executions(execution_id,job_id,attempt_no,status,provider,started_at,metadata_json) VALUES(?,?,?,?,?,?,?)",("exec_"+uuid.uuid4().hex,job_id,next_attempt,"queued",job["provider"],now,json.dumps({"authorized_retry":True,"authorized_by":actor_id})))
                new_event_id="obx_"+uuid.uuid4().hex
                conn.execute("INSERT INTO generation_outbox(event_id,job_id,event_type,payload_json,status,available_at,created_at) VALUES(?,?,?,?,?,?,?)",(new_event_id,job_id,"SUBMIT_GENERATION","{}","pending",now,now))
                conn.execute("UPDATE generation_jobs SET provider_request_id=NULL,error_code=NULL,message=?,updated_at=?,version=version+1 WHERE job_id=?",("Operator confirmed no provider submission was accepted; a new attempt is queued.",now,job_id))
                event_type="MANUAL_RECONCILIATION_CONFIRMED_NOT_SUBMITTED"
                payload={"action":action,"reason":reason,"previous_outbox_event_id":outbox["event_id"],"new_outbox_event_id":new_event_id,"attempt_no":next_attempt}
            SQLiteEventRepository().append_in_transaction(conn,job_id=job_id,from_status="queued",to_status="running" if action=="attach_request_id" else "queued",event_type=event_type,actor_id=actor_id,payload=payload,created_at=now)
        from app.repositories.job import build_job_repository
        return build_job_repository().get(job_id)

def build_outbox_admin_repository(backend: str | None = None) -> OutboxAdminRepository:
    from app import config
    from app.storage import get_storage
    selected=(backend or getattr(config,"DATABASE_BACKEND","sqlite")).strip().lower()
    if selected != "sqlite":
        raise RuntimeError("PostgreSQL storage driver is not implemented; refusing SQLite fallback")
    get_storage()
    return SQLiteOutboxAdminRepository()
