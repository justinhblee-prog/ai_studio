"""Durable cross-database Output→Asset linking outbox (SQLite adapter)."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from app import config
from app.storage import get_storage


def _db_path() -> Path:
    return Path(getattr(config, "GENERATION_DATABASE_PATH", None) or config.ASSET_DATABASE_PATH).resolve()


def _now() -> datetime:
    return datetime.now(timezone.utc)


class SQLiteOutputAssetLinkRepository:
    backend = "sqlite"

    def initialize(self) -> None:
        from app.schema_sqlite import initialize_schema
        with get_storage().transaction(_db_path()) as conn:
            initialize_schema(conn)

    def claim_one(self, worker_id: str, lease_seconds: int = 120) -> dict[str, Any] | None:
        from app.repositories.lease_validation import validate_worker_lease
        validate_worker_lease(worker_id, lease_seconds)
        self.initialize(); now = _now(); now_text = now.isoformat()
        lease_until = (now + timedelta(seconds=lease_seconds)).isoformat()
        with get_storage().transaction(_db_path()) as conn:
            get_storage().begin_write(conn)
            row = conn.execute("""SELECT l.*,o.storage_key,o.media_type,o.size_bytes,o.checksum_sha256 AS output_checksum_sha256
                FROM generation_output_asset_links l JOIN generation_outputs o ON o.output_id=l.output_id
                WHERE (l.status='pending' AND l.available_at<=?)
                   OR (l.status='processing' AND l.lease_expires_at IS NOT NULL AND l.lease_expires_at<=?)
                ORDER BY l.created_at,l.link_id LIMIT 1""", (now_text, now_text)).fetchone()
            if row is None: return None
            updated = conn.execute("""UPDATE generation_output_asset_links SET status='processing',attempts=attempts+1,
                claimed_by=?,claimed_at=?,lease_expires_at=?,updated_at=?
                WHERE link_id=? AND ((status='pending' AND available_at<=?) OR (status='processing' AND lease_expires_at<=?))""",
                (worker_id, now_text, lease_until, now_text, row["link_id"], now_text, now_text))
            if updated.rowcount != 1: return None
            value = dict(row); value["attempts"] += 1; value["claimed_by"] = worker_id
            value["claimed_at"] = now_text; value["lease_expires_at"] = lease_until
            return value

    def mark_linked(self, link_id: str, worker_id: str, *, asset_id: str, asset_version_id: str,
                    provenance_id: str, checksum_sha256: str) -> bool:
        from app.repositories.lease_validation import validate_worker_id
        validate_worker_id(worker_id)
        if not isinstance(link_id, str) or not link_id.strip():
            raise ValueError("link_id must be a non-empty string")
        self.initialize(); now = _now().isoformat()
        with get_storage().transaction(_db_path()) as conn:
            get_storage().begin_write(conn)
            result = conn.execute("""UPDATE generation_output_asset_links SET status='linked',asset_id=?,
                asset_version_id=?,provenance_id=?,checksum_sha256=?,last_error=NULL,claimed_by=NULL,
                claimed_at=NULL,lease_expires_at=NULL,updated_at=?
                WHERE link_id=? AND status='processing' AND claimed_by=? AND lease_expires_at>?""",
                (asset_id, asset_version_id, provenance_id, checksum_sha256, now, link_id, worker_id, now))
            return result.rowcount == 1

    def retry_failed(self, job_id: str, output_id: str, actor_id: str, reason: str) -> dict[str, Any] | None:
        from app.repositories.operator_validation import validate_operator_action, validate_resource_id
        actor_id, reason = validate_operator_action(actor_id, reason)
        job_id = validate_resource_id(job_id, "job_id")
        output_id = validate_resource_id(output_id, "output_id")
        self.initialize(); now = _now().isoformat()
        import json, uuid
        with get_storage().transaction(_db_path()) as conn:
            get_storage().begin_write(conn)
            row = conn.execute("""SELECT * FROM generation_output_asset_links
                WHERE job_id=? AND output_id=?""", (job_id, output_id)).fetchone()
            if row is None: return None
            if row["status"] != "failed":
                raise ValueError("Only failed Output Asset links can be manually retried")
            details = json.dumps({"reason": reason, "previous_error": row["last_error"], "previous_attempts": row["attempts"]}, separators=(",", ":"))
            conn.execute("""INSERT INTO generation_output_asset_link_events
                (event_id,link_id,output_id,job_id,actor_id,event_type,details_json,created_at)
                VALUES(?,?,?,?,?,'output_asset_link.retry_requested',?,?)""",
                ("oale_" + uuid.uuid4().hex, row["link_id"], output_id, job_id, actor_id, details, now))
            changed = conn.execute("""UPDATE generation_output_asset_links SET status='pending',attempts=0,available_at=?,
                claimed_by=NULL,claimed_at=NULL,lease_expires_at=NULL,last_error=NULL,updated_at=? WHERE link_id=? AND status='failed'""",
                (now, now, row["link_id"]))
            if changed.rowcount != 1:
                raise ValueError("Output Asset link changed while retry was being authorized")
            return {"link_id": row["link_id"], "output_id": output_id, "job_id": job_id, "status": "pending"}

    def has_link(self, job_id: str, output_id: str) -> bool:
        self.initialize()
        with get_storage().transaction(_db_path()) as conn:
            return conn.execute("SELECT 1 FROM generation_output_asset_links WHERE job_id=? AND output_id=?", (job_id, output_id)).fetchone() is not None

    def list_link_events(self, job_id: str, output_id: str) -> list[dict[str, Any]]:
        import json
        self.initialize()
        with get_storage().transaction(_db_path()) as conn:
            rows = conn.execute("""SELECT event_id,link_id,output_id,job_id,actor_id,event_type,details_json,created_at
                FROM generation_output_asset_link_events WHERE job_id=? AND output_id=? ORDER BY created_at DESC,event_id DESC""",
                (job_id, output_id)).fetchall()
        return [{**dict(row), "details": json.loads(row["details_json"])} for row in rows]

    def record_failure(self, link_id: str, worker_id: str, *, error: str, max_attempts: int = 5) -> bool:
        from app.repositories.lease_validation import validate_worker_id
        validate_worker_id(worker_id)
        if not isinstance(link_id, str) or not link_id.strip():
            raise ValueError("link_id must be a non-empty string")
        if isinstance(max_attempts, bool) or not isinstance(max_attempts, int) or max_attempts < 1:
            raise ValueError("max_attempts must be a positive integer")
        if not isinstance(error, str):
            raise ValueError("error must be a string")
        self.initialize(); now = _now()
        with get_storage().transaction(_db_path()) as conn:
            get_storage().begin_write(conn)
            row = conn.execute("SELECT attempts FROM generation_output_asset_links WHERE link_id=? AND status='processing' AND claimed_by=? AND lease_expires_at>?",
                               (link_id, worker_id, now.isoformat())).fetchone()
            if row is None: return False
            terminal = int(row["attempts"]) >= max_attempts
            delay = min(300, 2 ** max(0, int(row["attempts"]) - 1))
            available = (now + timedelta(seconds=delay)).isoformat()
            updated = conn.execute("""UPDATE generation_output_asset_links SET status=?,available_at=?,last_error=?,
                claimed_by=NULL,claimed_at=NULL,lease_expires_at=NULL,updated_at=? WHERE link_id=? AND status='processing' AND claimed_by=? AND lease_expires_at>?""",
                ("failed" if terminal else "pending", available, error[:500], now.isoformat(), link_id, worker_id, now.isoformat()))
            if updated.rowcount != 1:
                return False
            return True


def build_output_asset_link_repository(backend: str | None = None):
    selected = (backend or getattr(config, "DATABASE_BACKEND", "sqlite")).strip().lower()
    if selected == "sqlite": return SQLiteOutputAssetLinkRepository()
    if selected == "postgresql":
        raise RuntimeError("PostgreSQL Output Asset Link Repository is not implemented; refusing SQLite fallback.")
    raise ValueError(f"Unsupported DATABASE_BACKEND: {selected}")
