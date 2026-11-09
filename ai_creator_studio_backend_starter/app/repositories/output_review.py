"""Append-only review and controlled manifest export for immutable generated outputs.

The repository intentionally exports metadata only. It never publishes binaries,
claims commercial rights, or grants public access to private assets.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app import config
from app.storage import get_storage


def _db_path() -> Path:
    return Path(getattr(config, "GENERATION_DATABASE_PATH", None) or config.ASSET_DATABASE_PATH).resolve()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _event(row: Any) -> dict[str, Any]:
    return {
        "event_id": row["event_id"], "output_id": row["output_id"],
        "job_id": row["job_id"], "actor_id": row["actor_id"],
        "decision": row["decision"], "comment": row["comment"],
        "asset_id": row["asset_id"], "asset_version_id": row["asset_version_id"],
        "provenance_id": row["provenance_id"], "checksum_sha256": row["checksum_sha256"],
        "created_at": row["created_at"],
    }


class SQLiteOutputReviewRepository:
    backend = "sqlite"

    def initialize(self) -> None:
        from app.schema_sqlite import initialize_schema
        with get_storage().transaction(_db_path()) as conn:
            initialize_schema(conn)

    def get_review(self, job_id: str, output_id: str) -> dict[str, Any] | None:
        self.initialize()
        with get_storage().transaction(_db_path()) as conn:
            base = conn.execute("""SELECT o.output_id,o.job_id,o.media_type,o.size_bytes,o.created_at,
                j.workspace_id,j.status AS job_status,j.provider,j.model,
                l.status AS asset_link_status,l.asset_id,l.asset_version_id,l.provenance_id,
                l.checksum_sha256
                FROM generation_outputs o JOIN generation_jobs j ON j.job_id=o.job_id
                LEFT JOIN generation_output_asset_links l ON l.output_id=o.output_id
                WHERE o.job_id=? AND o.output_id=?""", (job_id, output_id)).fetchone()
            if base is None:
                return None
            rows = conn.execute("""SELECT * FROM generation_output_review_events
                WHERE job_id=? AND output_id=? ORDER BY rowid DESC""",
                (job_id, output_id)).fetchall()
        events = [_event(row) for row in rows]
        latest = events[0] if events else None
        status = latest["decision"] if latest else "pending_review"
        if base["asset_link_status"] != "linked":
            status = "awaiting_asset_link" if not base["asset_link_status"] else f"asset_link_{base['asset_link_status']}"
        return {
            "output": {
                "output_id": base["output_id"], "job_id": base["job_id"],
                "media_type": base["media_type"], "size_bytes": base["size_bytes"],
                "created_at": base["created_at"], "provider": base["provider"],
                "model": base["model"], "asset_link_status": base["asset_link_status"] or "not_queued",
                "asset_id": base["asset_id"], "asset_version_id": base["asset_version_id"],
                "provenance_id": base["provenance_id"], "checksum_sha256": base["checksum_sha256"],
            },
            "status": status, "latest_decision": latest, "events": events,
            "job_status": base["job_status"], "workspace_id": base["workspace_id"],
        }

    def decide(self, job_id: str, output_id: str, workspace_id: str, actor_id: str,
               decision: str, comment: str = "") -> dict[str, Any] | None:
        if decision not in {"approved", "changes_requested", "rejected"}:
            raise ValueError("Unsupported review decision")
        clean_comment = comment.strip()
        if decision in {"changes_requested", "rejected"} and not clean_comment:
            raise ValueError("A non-empty comment is required for this decision")
        self.initialize()
        now = _now()
        with get_storage().transaction(_db_path()) as conn:
            get_storage().begin_write(conn)
            row = conn.execute("""SELECT o.output_id,o.job_id,j.workspace_id,j.status AS job_status,
                l.status AS link_status,l.asset_id,l.asset_version_id,l.provenance_id,l.checksum_sha256
                FROM generation_outputs o JOIN generation_jobs j ON j.job_id=o.job_id
                LEFT JOIN generation_output_asset_links l ON l.output_id=o.output_id
                WHERE o.job_id=? AND o.output_id=?""", (job_id, output_id)).fetchone()
            if row is None:
                return None
            if row["workspace_id"] != workspace_id:
                raise ValueError("Output workspace does not match the authorized workspace")
            if row["job_status"] != "succeeded":
                raise ValueError("Only outputs from succeeded jobs can be reviewed")
            if row["link_status"] != "linked" or not all(row[k] for k in ("asset_id", "asset_version_id", "provenance_id", "checksum_sha256")):
                raise ValueError("Output must be linked to a verified immutable AssetVersion before review")
            latest = conn.execute("""SELECT decision FROM generation_output_review_events
                WHERE job_id=? AND output_id=? ORDER BY rowid DESC LIMIT 1""",
                (job_id, output_id)).fetchone()
            if latest and latest["decision"] in {"approved", "rejected"}:
                raise ValueError("Approved or rejected outputs are terminal; create a new output to change the result")
            if latest and latest["decision"] == decision:
                raise ValueError("The requested review decision is already current")
            event_id = "orev_" + uuid.uuid4().hex
            conn.execute("""INSERT INTO generation_output_review_events
                (event_id,output_id,job_id,workspace_id,actor_id,decision,comment,asset_id,
                 asset_version_id,provenance_id,checksum_sha256,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                (event_id, output_id, job_id, workspace_id, actor_id, decision, clean_comment,
                 row["asset_id"], row["asset_version_id"], row["provenance_id"], row["checksum_sha256"], now))
        return self.get_review(job_id, output_id)

    def create_export_manifest(self, job_id: str, workspace_id: str, actor_id: str) -> dict[str, Any] | None:
        """Create and audit a metadata-only manifest for fully approved outputs."""
        self.initialize()
        now = _now()
        with get_storage().transaction(_db_path()) as conn:
            get_storage().begin_write(conn)
            job = conn.execute("SELECT workspace_id,status,provider,model,created_at FROM generation_jobs WHERE job_id=?",
                               (job_id,)).fetchone()
            if job is None:
                return None
            if job["workspace_id"] != workspace_id:
                raise ValueError("Output workspace does not match the authorized workspace")
            if job["status"] != "succeeded":
                raise ValueError("Only succeeded jobs can be exported")
            rows = conn.execute("""SELECT o.output_id,o.media_type,o.size_bytes,o.created_at,
                l.status AS link_status,l.asset_id,l.asset_version_id,l.provenance_id,l.checksum_sha256,
                (SELECT e.decision FROM generation_output_review_events e
                 WHERE e.job_id=o.job_id AND e.output_id=o.output_id
                 ORDER BY e.rowid DESC LIMIT 1) AS review_status,
                (SELECT e.actor_id FROM generation_output_review_events e
                 WHERE e.job_id=o.job_id AND e.output_id=o.output_id
                 ORDER BY e.rowid DESC LIMIT 1) AS approved_by,
                (SELECT e.created_at FROM generation_output_review_events e
                 WHERE e.job_id=o.job_id AND e.output_id=o.output_id
                 ORDER BY e.rowid DESC LIMIT 1) AS reviewed_at
                FROM generation_outputs o LEFT JOIN generation_output_asset_links l ON l.output_id=o.output_id
                WHERE o.job_id=? ORDER BY o.created_at,o.output_id""", (job_id,)).fetchall()
            if not rows:
                raise ValueError("Job has no generated outputs")
            if any(r["link_status"] != "linked" or not r["asset_id"] or not r["asset_version_id"] or not r["provenance_id"] or not r["checksum_sha256"] for r in rows):
                raise ValueError("Every output must be linked to a verified immutable AssetVersion before export")
            if any(r["review_status"] != "approved" for r in rows):
                raise ValueError("Every output must be individually approved before export")
            manifest = {
                "manifest_type": "AI_CREATOR_STUDIO_INTERNAL_OUTPUT_MANIFEST",
                "manifest_version": 1,
                "job": {"job_id": job_id, "workspace_id": workspace_id,
                        "provider": job["provider"], "model": job["model"], "created_at": job["created_at"]},
                "outputs": [{
                    "output_id": r["output_id"], "media_type": r["media_type"],
                    "size_bytes": r["size_bytes"], "created_at": r["created_at"],
                    "asset_id": r["asset_id"], "asset_version_id": r["asset_version_id"],
                    "provenance_id": r["provenance_id"], "checksum_sha256": r["checksum_sha256"],
                    "review_status": r["review_status"], "approved_by": r["approved_by"],
                    "reviewed_at": r["reviewed_at"],
                } for r in rows],
                "publication_authorized": False,
                "commercial_rights_verified": False,
                "binary_files_included": False,
                "notice": "Internal metadata manifest only. This does not grant publication, distribution, or commercial-use rights.",
            }
            canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
            conn.execute("""INSERT INTO generation_output_export_events
                (event_id,job_id,workspace_id,actor_id,manifest_sha256,output_count,created_at)
                VALUES(?,?,?,?,?,?,?)""",
                ("oexp_" + uuid.uuid4().hex, job_id, workspace_id, actor_id, digest, len(rows), now))
        return {"manifest": manifest, "manifest_sha256": digest, "exported_at": now}


def build_output_review_repository(backend: str | None = None):
    selected = (backend or getattr(config, "DATABASE_BACKEND", "sqlite")).strip().lower()
    if selected == "sqlite":
        return SQLiteOutputReviewRepository()
    if selected == "postgresql":
        raise RuntimeError("PostgreSQL Output Review Repository is not implemented; refusing SQLite fallback.")
    raise ValueError(f"Unsupported DATABASE_BACKEND: {selected}")
