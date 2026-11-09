"""Worker heartbeat and operational repository ports."""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Protocol, runtime_checkable
import json
import uuid

@runtime_checkable
class WorkerHeartbeatRepository(Protocol):
    def heartbeat(self, worker_id: str, state: str, metadata: dict[str, Any] | None = None) -> None: ...

class SQLiteWorkerHeartbeatRepository:
    backend="sqlite"
    @staticmethod
    def _context():
        from app import config
        from app.storage import get_storage
        path=Path(getattr(config,"GENERATION_DATABASE_PATH",None) or config.ASSET_DATABASE_PATH).resolve()
        return get_storage(),path
    def heartbeat(self, worker_id, state, metadata=None):
        from app.schema_sqlite import initialize_schema
        storage,path=self._context(); now=datetime.now(timezone.utc).isoformat(); metadata_json=json.dumps(metadata or {},sort_keys=True)
        with storage.transaction(path) as conn:
            initialize_schema(conn)
            conn.execute("INSERT INTO generation_worker_heartbeats(worker_id,started_at,last_seen_at,state,metadata_json) VALUES(?,?,?,?,?) ON CONFLICT(worker_id) DO UPDATE SET last_seen_at=excluded.last_seen_at,state=excluded.state,metadata_json=excluded.metadata_json",(worker_id,now,now,state,metadata_json))

def build_worker_heartbeat_repository(backend: str | None = None) -> WorkerHeartbeatRepository:
    from app import config
    from app.storage import get_storage
    selected=(backend or getattr(config,"DATABASE_BACKEND","sqlite")).strip().lower()
    if selected!="sqlite": raise RuntimeError("PostgreSQL Worker Heartbeat Repository is not implemented; refusing SQLite fallback")
    get_storage()
    return SQLiteWorkerHeartbeatRepository()

@runtime_checkable
class AlertDeliveryRepository(Protocol):
    def claim(self, worker_id: str, lease_seconds: int = 120) -> dict[str, Any] | None: ...
    def finish(self, delivery_id: str, *, worker_id: str, delivered: bool, error: str | None = None,
               retry_delay_seconds: float = 30, max_attempts: int = 8) -> bool: ...

class SQLiteAlertDeliveryRepository:
    backend="sqlite"
    @staticmethod
    def _context():
        from app import config
        from app.storage import get_storage
        path=Path(getattr(config,"GENERATION_DATABASE_PATH",None) or config.ASSET_DATABASE_PATH).resolve()
        return get_storage(),path
    def claim(self, worker_id, lease_seconds=120):
        from app.schema_sqlite import initialize_schema
        from app.sql import sqlite_operations as sql
        from app.repositories.lease_validation import validate_worker_lease
        validate_worker_lease(worker_id, lease_seconds)
        storage,path=self._context(); now_dt=datetime.now(timezone.utc); now=now_dt.isoformat()
        expires=(now_dt+timedelta(seconds=lease_seconds)).isoformat()
        with storage.transaction(path) as conn:
            initialize_schema(conn); storage.begin_write(conn)
            conn.execute(sql.REQUEUE_STALE_DELIVERY,(now,now))
            row=conn.execute(sql.SELECT_READY_DELIVERY,(now,)).fetchone()
            if row is None: return None
            changed=conn.execute(sql.CLAIM_DELIVERY,(now,worker_id,expires,row["delivery_id"],now))
            if changed.rowcount!=1: return None
            item=dict(row); item["details"]=json.loads(item.pop("details_json"))
            item["claimed_by"]=worker_id; item["lease_expires_at"]=expires
            return item
    def finish(self, delivery_id, *, worker_id, delivered, error=None, retry_delay_seconds=30, max_attempts=8):
        from app.schema_sqlite import initialize_schema
        from app.sql import sqlite_operations as sql
        from app.repositories.lease_validation import validate_worker_id
        validate_worker_id(worker_id)
        if not isinstance(delivery_id,str) or not delivery_id.strip(): raise ValueError("delivery_id must be a non-empty string")
        if not isinstance(delivered,bool): raise ValueError("delivered must be a boolean")
        if isinstance(max_attempts,bool) or not isinstance(max_attempts,int) or max_attempts<1: raise ValueError("max_attempts must be a positive integer")
        if isinstance(retry_delay_seconds,bool) or not isinstance(retry_delay_seconds,(int,float)) or retry_delay_seconds<0: raise ValueError("retry_delay_seconds must be non-negative")
        if error is not None and not isinstance(error,str): raise ValueError("error must be a string or None")
        storage,path=self._context(); now_dt=datetime.now(timezone.utc); now=now_dt.isoformat()
        with storage.transaction(path) as conn:
            initialize_schema(conn)
            row=conn.execute(sql.DELIVERY_ATTEMPTS,(delivery_id,worker_id,now)).fetchone()
            if row is None: return False
            attempts=int(row["attempts"])
            if delivered:
                changed=conn.execute(sql.DELIVERY_MARK_SENT,(now,delivery_id,worker_id,now))
            elif attempts>=max_attempts:
                changed=conn.execute(sql.DELIVERY_MARK_FAILED,((error or "delivery failed")[:500],delivery_id,worker_id,now))
            else:
                available=(now_dt+timedelta(seconds=max(1,retry_delay_seconds))).isoformat()
                changed=conn.execute(sql.DELIVERY_RESCHEDULE,(available,(error or "delivery failed")[:500],delivery_id,worker_id,now))
            return changed.rowcount==1

def build_alert_delivery_repository(backend: str | None = None) -> AlertDeliveryRepository:
    from app import config
    from app.storage import get_storage
    selected=(backend or getattr(config,"DATABASE_BACKEND","sqlite")).strip().lower()
    if selected!="sqlite": raise RuntimeError("PostgreSQL Alert Delivery Repository is not implemented; refusing SQLite fallback")
    get_storage()
    return SQLiteAlertDeliveryRepository()

@runtime_checkable
class WorkerHealthRepository(Protocol):
    def outbox_counts(self) -> dict[str, int]: ...
    def poll_task_counts(self) -> dict[str, int]: ...
    def worker_health(self, stale_after_seconds: int = 30) -> dict[str, Any]: ...

class SQLiteWorkerHealthRepository:
    backend="sqlite"
    @staticmethod
    def _context():
        from app import config
        from app.storage import get_storage
        path=Path(getattr(config,"GENERATION_DATABASE_PATH",None) or config.ASSET_DATABASE_PATH).resolve()
        return get_storage(),path
    def outbox_counts(self):
        from app.schema_sqlite import initialize_schema
        storage,path=self._context()
        with storage.transaction(path) as conn:
            initialize_schema(conn)
            rows=conn.execute("SELECT status,COUNT(*) AS n FROM generation_outbox GROUP BY status").fetchall()
        return {row["status"]:int(row["n"]) for row in rows}
    def poll_task_counts(self):
        from app.schema_sqlite import initialize_schema
        storage,path=self._context()
        with storage.transaction(path) as conn:
            initialize_schema(conn)
            rows=conn.execute("SELECT status,COUNT(*) AS n FROM generation_poll_tasks GROUP BY status").fetchall()
        return {row["status"]:int(row["n"]) for row in rows}
    def worker_health(self, stale_after_seconds=30):
        from app.schema_sqlite import initialize_schema
        from app.sql import sqlite_operations as sql
        storage,path=self._context(); now_dt=datetime.now(timezone.utc); cutoff=(now_dt-timedelta(seconds=stale_after_seconds)).isoformat()
        with storage.transaction(path) as conn:
            initialize_schema(conn)
            rows=conn.execute(sql.HEARTBEATS).fetchall()
        workers=[]
        for row in rows:
            item=dict(row); item["metadata"]=json.loads(item.pop("metadata_json")); item["healthy"]=item["state"]=="running" and item["last_seen_at"]>=cutoff; workers.append(item)
        return {"workers":workers,"outbox_counts":self.outbox_counts(),"poll_task_counts":self.poll_task_counts(),"stale_after_seconds":stale_after_seconds}

def build_worker_health_repository(backend: str | None = None) -> WorkerHealthRepository:
    from app import config
    from app.storage import get_storage
    selected=(backend or getattr(config,"DATABASE_BACKEND","sqlite")).strip().lower()
    if selected!="sqlite": raise RuntimeError("PostgreSQL Worker Health Repository is not implemented; refusing SQLite fallback")
    get_storage()
    return SQLiteWorkerHealthRepository()


@runtime_checkable
class OperationsAlertReadRepository(Protocol):
    def list_alerts(self, *, status: str = "active", limit: int = 100) -> list[dict[str, Any]]: ...

class SQLiteOperationsAlertReadRepository:
    backend="sqlite"
    @staticmethod
    def _context():
        from app import config
        from app.storage import get_storage
        path=Path(getattr(config,"GENERATION_DATABASE_PATH",None) or config.ASSET_DATABASE_PATH).resolve()
        return get_storage(),path
    def list_alerts(self, *, status="active", limit=100):
        from app.schema_sqlite import initialize_schema
        from app.sql import sqlite_operations as sql
        storage,path=self._context(); limit=max(1,min(int(limit),200))
        with storage.transaction(path) as conn:
            initialize_schema(conn)
            rows=conn.execute(sql.LIST_ALERTS,(status,limit)).fetchall()
        result=[]
        for row in rows:
            item=dict(row); item["details"]=json.loads(item.pop("details_json")); result.append(item)
        return result

def build_operations_alert_read_repository(backend: str | None = None) -> OperationsAlertReadRepository:
    from app import config
    from app.storage import get_storage
    selected=(backend or getattr(config,"DATABASE_BACKEND","sqlite")).strip().lower()
    if selected!="sqlite": raise RuntimeError("PostgreSQL Operations Alert Read Repository is not implemented; refusing SQLite fallback")
    get_storage()
    return SQLiteOperationsAlertReadRepository()

@runtime_checkable
class OperationsMonitoringRepository(Protocol):
    def snapshot(self, worker_stale_seconds: int = 45) -> dict[str, Any]: ...
    def evaluate_alerts(self, *, required_worker_types: tuple[str, ...] = ("outbox", "provider_poll"),
                        worker_stale_seconds: int = 45, queue_age_seconds: int = 120,
                        webhook_destination: str | None = None) -> list[dict[str, Any]]: ...

class SQLiteOperationsMonitoringRepository:
    backend="sqlite"
    @staticmethod
    def _context():
        from app import config
        from app.storage import get_storage
        path=Path(getattr(config,"GENERATION_DATABASE_PATH",None) or config.ASSET_DATABASE_PATH).resolve()
        return get_storage(),path
    def snapshot(self, worker_stale_seconds=45):
        from app.schema_sqlite import initialize_schema
        from app.sql import sqlite_operations as sql
        storage,path=self._context(); now_dt=datetime.now(timezone.utc); now=now_dt.isoformat()
        cutoff=(now_dt-timedelta(seconds=max(1,worker_stale_seconds))).isoformat()
        with storage.transaction(path) as conn:
            initialize_schema(conn)
            heartbeat_rows=conn.execute(sql.HEARTBEATS).fetchall()
            outbox_rows=conn.execute(sql.OUTBOX_AGGREGATES).fetchall()
            poll_rows=conn.execute(sql.POLL_AGGREGATES).fetchall()
            alert_rows=conn.execute(sql.ALERT_AGGREGATES).fetchall()
            delivery_rows=conn.execute(sql.DELIVERY_AGGREGATES).fetchall()
        workers=[]
        for row in heartbeat_rows:
            item=dict(row)
            try: metadata=json.loads(item.pop("metadata_json"))
            except Exception: metadata={}
            item["metadata"]=metadata; item["worker_type"]=metadata.get("worker_type","unknown")
            item["healthy"]=item["state"]=="running" and item["last_seen_at"]>=cutoff
            workers.append(item)
        outbox={key:0 for key in ("pending","processing","processed","needs_reconciliation")}
        outbox.update({r["status"]:int(r["n"]) for r in outbox_rows})
        poll={f"{status}:{phase}":0 for status in ("pending","processing","completed","needs_reconciliation") for phase in ("status","persist_output")}
        for row in poll_rows: poll[f'{row["status"]}:{row["phase"]}']=int(row["n"])
        def age_seconds(value):
            if not value: return None
            try:
                parsed=datetime.fromisoformat(value)
                if parsed.tzinfo is None: parsed=parsed.replace(tzinfo=timezone.utc)
                return max(0.0,(now_dt-parsed).total_seconds())
            except (ValueError,TypeError): return None
        oldest_outbox=max((age_seconds(r["oldest"]) for r in outbox_rows if r["oldest"]),default=None)
        oldest_poll=max((age_seconds(r["oldest"]) for r in poll_rows if r["oldest"]),default=None)
        alerts={f'{r["status"]}:{r["severity"]}':int(r["n"]) for r in alert_rows}
        deliveries={r["status"]:int(r["n"]) for r in delivery_rows}
        return {"generated_at":now,"workers":workers,"outbox_counts":outbox,"poll_task_counts":poll,
                "oldest_pending_outbox_age_seconds":oldest_outbox,"oldest_pending_poll_age_seconds":oldest_poll,
                "alerts":alerts,"alert_deliveries":deliveries,"worker_stale_after_seconds":worker_stale_seconds}
    def evaluate_alerts(self, *, required_worker_types=("outbox","provider_poll"), worker_stale_seconds=45,
                        queue_age_seconds=120, webhook_destination=None):
        from app.schema_sqlite import initialize_schema
        from app.sql import sqlite_operations as sql
        snapshot=self.snapshot(worker_stale_seconds); observed={}
        for worker in snapshot["workers"]: observed.setdefault(worker["worker_type"],worker)
        breaches={}
        for worker_type in required_worker_types:
            worker=observed.get(worker_type)
            if worker is None or not worker["healthy"]:
                fingerprint=f"worker:{worker_type}:stale"
                breaches[fingerprint]={"alert_type":"worker_stale","severity":"critical","title":f"Required worker unavailable: {worker_type}",
                    "details":{"worker_type":worker_type,"worker_id":worker.get("worker_id") if worker else None,
                               "last_seen_at":worker.get("last_seen_at") if worker else None,"stale_after_seconds":worker_stale_seconds}}
        for key,age_key in (("outbox","oldest_pending_outbox_age_seconds"),("poll","oldest_pending_poll_age_seconds")):
            age=snapshot[age_key]
            if age is not None and age>queue_age_seconds:
                fingerprint=f"queue:{key}:age"
                breaches[fingerprint]={"alert_type":"queue_age","severity":"warning","title":f"{key} queue is older than the configured threshold",
                    "details":{"queue":key,"oldest_age_seconds":round(age,2),"threshold_seconds":queue_age_seconds}}
        unknown=int(snapshot["outbox_counts"].get("needs_reconciliation",0))
        poll_unknown=sum(v for k,v in snapshot["poll_task_counts"].items() if k.startswith("needs_reconciliation:"))
        if unknown: breaches["outbox:needs_reconciliation"]={"alert_type":"reconciliation_backlog","severity":"critical","title":"Provider submission reconciliation required","details":{"count":unknown,"queue":"outbox"}}
        if poll_unknown: breaches["poll:needs_reconciliation"]={"alert_type":"reconciliation_backlog","severity":"warning","title":"Provider poll tasks require operator review","details":{"count":poll_unknown,"queue":"poll"}}
        storage,path=self._context(); now=datetime.now(timezone.utc).isoformat(); active=[]
        with storage.transaction(path) as conn:
            initialize_schema(conn); storage.begin_write(conn)
            existing=conn.execute(sql.ACTIVE_FINGERPRINTS).fetchall(); existing_set={r["fingerprint"] for r in existing}
            for fingerprint,breach in breaches.items():
                current=conn.execute(sql.ALERT_BY_FINGERPRINT,(fingerprint,)).fetchone()
                if current:
                    alert_id=current["alert_id"]
                    conn.execute(sql.UPDATE_ALERT,(breach["severity"],breach["title"],json.dumps(breach["details"],sort_keys=True),now,fingerprint))
                    if fingerprint not in existing_set and webhook_destination:
                        conn.execute(sql.UPSERT_DELIVERY,("ald_"+uuid.uuid4().hex,alert_id,webhook_destination,now,now))
                else:
                    alert_id="alt_"+uuid.uuid4().hex
                    conn.execute(sql.INSERT_ALERT,(alert_id,fingerprint,breach["alert_type"],breach["severity"],"active",breach["title"],json.dumps(breach["details"],sort_keys=True),now,now))
                    if webhook_destination: conn.execute(sql.INSERT_DELIVERY,("ald_"+uuid.uuid4().hex,alert_id,webhook_destination,now,now))
                active.append({"fingerprint":fingerprint,**breach})
            for fingerprint in existing_set-set(breaches): conn.execute(sql.RESOLVE_ALERT,(now,now,fingerprint))
        return active

def build_operations_monitoring_repository(backend: str | None = None) -> OperationsMonitoringRepository:
    from app import config
    from app.storage import get_storage
    selected=(backend or getattr(config,"DATABASE_BACKEND","sqlite")).strip().lower()
    if selected!="sqlite": raise RuntimeError("PostgreSQL Operations Monitoring Repository is not implemented; refusing SQLite fallback")
    get_storage()
    return SQLiteOperationsMonitoringRepository()
