"""Non-billable Photo Engine draft preparation; no provider dispatch or output generation."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import timedelta
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Literal

from app.viewer_responses import PhotoDraftListResponse, PhotoDraftResponse, PhotoRunListResponse, PhotoRunResponse, PhotoOutputReviewResponse, EventListResponse, PhotoLocalProcessingResponse, ManifestExportResponse
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app import config
from app.assets.routes import current_user, require_role
from app.ports.photos import LocalProcessingFailed, get_photo_draft_port
from app.repo_errors import raise_http
from app.storage import get_storage

router = APIRouter(prefix="/v1/photo-drafts", tags=["photo-engine"])


class PhotoOutputReviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    comment: str = Field(default="", max_length=2000)


class PhotoDraftInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    workspace_id: str = Field(min_length=2, max_length=64)
    source_asset_id: str = Field(min_length=8, max_length=80)
    operation: Literal["ENHANCE", "BACKGROUND", "LIGHTING", "RETOUCH", "COMPOSE"]
    mask_asset_id: str | None = Field(default=None, min_length=8, max_length=80)
    reference_asset_ids: list[str] = Field(default_factory=list, max_length=8)
    preserve_identity: bool = True
    preserve_product_geometry: bool = True
    preserve_text_and_logo: bool = True
    target_style: str | None = Field(default=None, max_length=160)
    prompt: str | None = Field(default=None, max_length=1000)
    output_format: Literal["PNG", "JPEG", "WEBP"] = "PNG"
    output_count: int = Field(default=1, ge=1, le=10)

    @field_validator("target_style", "prompt")
    @classmethod
    def nonempty_optional_text(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("Text values must not be blank")
        return value

    def asset_roles(self) -> list[tuple[str, str]]:
        roles = [(self.source_asset_id, "source")]
        if self.mask_asset_id:
            roles.append((self.mask_asset_id, "mask"))
        roles.extend((asset_id, "reference") for asset_id in self.reference_asset_ids)
        ids = [asset_id for asset_id, _ in roles]
        if len(ids) != len(set(ids)):
            raise ValueError("An image asset may appear only once in a Photo Draft")
        return roles


def _connect() -> sqlite3.Connection:
    db = get_storage().connect(config.ASSET_DATABASE_PATH)
    return db


def initialize() -> None:
    from app.assets.store import initialize as initialize_assets
    initialize_assets()
    db = _connect()
    try:
        db.execute("""CREATE TABLE IF NOT EXISTS photo_drafts (
            draft_id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, created_by TEXT NOT NULL,
            payload_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            archived_at TEXT
        )""")
        db.execute("CREATE INDEX IF NOT EXISTS idx_photo_drafts_workspace ON photo_drafts(workspace_id, archived_at, updated_at)")
        db.execute("""CREATE TABLE IF NOT EXISTS photo_draft_assets (
            draft_id TEXT NOT NULL REFERENCES photo_drafts(draft_id) ON DELETE CASCADE,
            asset_id TEXT NOT NULL REFERENCES assets(asset_id),
            role TEXT NOT NULL CHECK(role IN ('source','mask','reference')),
            PRIMARY KEY(draft_id, asset_id, role)
        )""")
        db.execute("CREATE INDEX IF NOT EXISTS idx_photo_draft_assets_asset ON photo_draft_assets(asset_id)")
        db.execute("""CREATE TABLE IF NOT EXISTS photo_draft_events (
            event_id TEXT PRIMARY KEY, draft_id TEXT NOT NULL REFERENCES photo_drafts(draft_id),
            workspace_id TEXT NOT NULL, actor_id TEXT NOT NULL, event_type TEXT NOT NULL,
            details_json TEXT NOT NULL, created_at TEXT NOT NULL
        )""")
        db.execute("CREATE INDEX IF NOT EXISTS idx_photo_draft_events ON photo_draft_events(draft_id, created_at DESC)")
        db.execute("""CREATE TABLE IF NOT EXISTS photo_processing_runs (
            run_id TEXT PRIMARY KEY, draft_id TEXT NOT NULL REFERENCES photo_drafts(draft_id),
            workspace_id TEXT NOT NULL, created_by TEXT NOT NULL, idempotency_key TEXT NOT NULL,
            payload_hash TEXT NOT NULL, processor_version TEXT NOT NULL, operation TEXT NOT NULL,
            source_version_id TEXT, source_checksum_sha256 TEXT,
            status TEXT NOT NULL CHECK(status IN ('processing','succeeded','failed')),
            attempts INTEGER NOT NULL DEFAULT 1, claimed_by TEXT, lease_expires_at TEXT,
            output_asset_id TEXT, output_version_id TEXT, output_checksum_sha256 TEXT,
            quality_json TEXT NOT NULL DEFAULT '{}', error_message TEXT,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            UNIQUE(workspace_id,idempotency_key)
        )""")
        run_columns = {row["name"] for row in db.execute("PRAGMA table_info(photo_processing_runs)").fetchall()}
        if "source_version_id" not in run_columns:
            db.execute("ALTER TABLE photo_processing_runs ADD COLUMN source_version_id TEXT")
        if "source_checksum_sha256" not in run_columns:
            db.execute("ALTER TABLE photo_processing_runs ADD COLUMN source_checksum_sha256 TEXT")
        db.execute("CREATE INDEX IF NOT EXISTS idx_photo_runs_draft ON photo_processing_runs(draft_id,created_at DESC)")
        db.execute("""CREATE TABLE IF NOT EXISTS photo_processing_events (
            event_id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES photo_processing_runs(run_id),
            draft_id TEXT NOT NULL, workspace_id TEXT NOT NULL, actor_id TEXT NOT NULL,
            event_type TEXT NOT NULL, details_json TEXT NOT NULL, created_at TEXT NOT NULL
        )""")
        db.execute("CREATE INDEX IF NOT EXISTS idx_photo_run_events ON photo_processing_events(run_id,created_at,event_id)")
        db.execute("""CREATE TRIGGER IF NOT EXISTS trg_photo_run_events_no_update
            BEFORE UPDATE ON photo_processing_events
            BEGIN SELECT RAISE(ABORT, 'photo processing events are append-only'); END""")
        db.execute("""CREATE TRIGGER IF NOT EXISTS trg_photo_run_events_no_delete
            BEFORE DELETE ON photo_processing_events
            BEGIN SELECT RAISE(ABORT, 'photo processing events are append-only'); END""")
        db.execute("""CREATE TABLE IF NOT EXISTS photo_output_review_events (
            event_id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES photo_processing_runs(run_id),
            draft_id TEXT NOT NULL, workspace_id TEXT NOT NULL, actor_id TEXT NOT NULL,
            decision TEXT NOT NULL CHECK(decision IN ('approved','changes_requested','rejected')),
            comment TEXT NOT NULL DEFAULT '', asset_id TEXT NOT NULL, asset_version_id TEXT NOT NULL,
            provenance_id TEXT NOT NULL, checksum_sha256 TEXT NOT NULL, created_at TEXT NOT NULL
        )""")
        db.execute("CREATE INDEX IF NOT EXISTS idx_photo_output_reviews ON photo_output_review_events(run_id,created_at,event_id)")
        db.execute("""CREATE TRIGGER IF NOT EXISTS trg_photo_output_reviews_no_update
            BEFORE UPDATE ON photo_output_review_events
            BEGIN SELECT RAISE(ABORT, 'photo output review events are append-only'); END""")
        db.execute("""CREATE TRIGGER IF NOT EXISTS trg_photo_output_reviews_no_delete
            BEFORE DELETE ON photo_output_review_events
            BEGIN SELECT RAISE(ABORT, 'photo output review events are append-only'); END""")
        db.execute("""CREATE TABLE IF NOT EXISTS photo_output_export_events (
            event_id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES photo_processing_runs(run_id),
            draft_id TEXT NOT NULL, workspace_id TEXT NOT NULL, actor_id TEXT NOT NULL,
            manifest_sha256 TEXT NOT NULL, created_at TEXT NOT NULL
        )""")
        db.execute("CREATE INDEX IF NOT EXISTS idx_photo_output_exports ON photo_output_export_events(run_id,created_at,event_id)")
        db.execute("""CREATE TRIGGER IF NOT EXISTS trg_photo_output_exports_no_update
            BEFORE UPDATE ON photo_output_export_events
            BEGIN SELECT RAISE(ABORT, 'photo output export events are append-only'); END""")
        db.execute("""CREATE TRIGGER IF NOT EXISTS trg_photo_output_exports_no_delete
            BEFORE DELETE ON photo_output_export_events
            BEGIN SELECT RAISE(ABORT, 'photo output export events are append-only'); END""")
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _event(db: sqlite3.Connection, draft_id: str, workspace_id: str, actor_id: str,
           event_type: str, details: dict[str, Any] | None = None) -> None:
    db.execute("""INSERT INTO photo_draft_events(event_id, draft_id, workspace_id,
        actor_id, event_type, details_json, created_at) VALUES(?,?,?,?,?,?,?)""",
        ("pde_" + uuid.uuid4().hex, draft_id, workspace_id, actor_id, event_type,
         json.dumps(details or {}, ensure_ascii=False, separators=(",", ":")), _now()))


def _validate_assets(db: sqlite3.Connection, workspace_id: str, body: PhotoDraftInput) -> list[tuple[str, str]]:
    try:
        roles = body.asset_roles()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    ids = [asset_id for asset_id, _ in roles]
    placeholders = ",".join("?" for _ in ids)
    rows = db.execute(f"""SELECT asset_id FROM assets WHERE workspace_id=? AND deleted_at IS NULL
        AND media_type LIKE 'image/%' AND asset_id IN ({placeholders})""", (workspace_id, *ids)).fetchall()
    if len(rows) != len(ids):
        raise HTTPException(status_code=422, detail={"code": "PHOTO_IMAGE_ASSET_REQUIRED",
            "message": "Every source, mask, and reference must be an active image asset in this workspace."})
    return roles


def _public(row: sqlite3.Row) -> dict[str, Any]:
    value = dict(row)
    value["input"] = json.loads(value.pop("payload_json"))
    value["status"] = "archived" if value["archived_at"] else "draft"
    return value


def _snapshot_source_version(db: sqlite3.Connection, workspace_id: str, source_asset_id: str) -> tuple[str, str]:
    row = db.execute("""SELECT v.version_id,v.checksum_sha256 FROM assets a
        JOIN asset_versions v ON v.asset_id=a.asset_id AND v.workspace_id=a.workspace_id
        WHERE a.asset_id=? AND a.workspace_id=? AND a.deleted_at IS NULL
          AND a.media_type LIKE 'image/%' AND v.storage_key=a.storage_key""",
        (source_asset_id, workspace_id)).fetchone()
    if not row:
        raise HTTPException(status_code=409, detail="Source image has no current verified immutable AssetVersion")
    from app.takedown import held_among
    if held_among(db, [source_asset_id]):   # L-08: no new work is built on content that is under a report
        raise HTTPException(status_code=409, detail={"code": "ASSET_UNDER_REVIEW", "message": "The source image is under review and cannot be used."})
    return row["version_id"], row["checksum_sha256"]


def create_draft(workspace_id: str, actor_id: str, body: PhotoDraftInput) -> dict[str, Any]:
    initialize()
    draft_id = "phd_" + uuid.uuid4().hex
    now = _now()
    payload = body.model_dump(mode="json", exclude={"workspace_id"})
    db = _connect()
    try:
        db.execute("BEGIN IMMEDIATE")
        roles = _validate_assets(db, workspace_id, body)
        source_version_id, source_checksum = _snapshot_source_version(db, workspace_id, body.source_asset_id)
        payload["source_version_id"] = source_version_id
        payload["source_checksum_sha256"] = source_checksum
        db.execute("INSERT INTO photo_drafts(draft_id, workspace_id, created_by, payload_json, created_at, updated_at) VALUES(?,?,?,?,?,?)",
                   (draft_id, workspace_id, actor_id, json.dumps(payload, ensure_ascii=False), now, now))
        db.executemany("INSERT INTO photo_draft_assets(draft_id, asset_id, role) VALUES(?,?,?)",
                       [(draft_id, asset_id, role) for asset_id, role in roles])
        _event(db, draft_id, workspace_id, actor_id, "photo.draft_created", {"operation": body.operation})
        row = db.execute("SELECT * FROM photo_drafts WHERE draft_id=?", (draft_id,)).fetchone()
        db.commit()
        return _public(row)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def list_drafts(workspace_id: str, include_archived: bool = False, *, limit: int = 50, offset: int = 0) -> dict[str, Any]:
    initialize(); db = _connect()
    try:
        where = "workspace_id=?" + ("" if include_archived else " AND archived_at IS NULL")
        total = int(db.execute(f"SELECT COUNT(*) AS n FROM photo_drafts WHERE {where}", (workspace_id,)).fetchone()["n"])
        rows = db.execute(f"SELECT * FROM photo_drafts WHERE {where} ORDER BY updated_at DESC, draft_id LIMIT ? OFFSET ?",
                          (workspace_id, limit, offset)).fetchall()
        return {"items": [_public(row) for row in rows], "total": total, "limit": limit, "offset": offset}
    finally:
        db.close()


def get_draft(draft_id: str, workspace_id: str) -> dict[str, Any] | None:
    initialize()
    db = _connect()
    try:
        row = db.execute("SELECT * FROM photo_drafts WHERE draft_id=? AND workspace_id=?",
                         (draft_id, workspace_id)).fetchone()
        return _public(row) if row else None
    finally:
        db.close()


def update_draft(draft_id: str, workspace_id: str, actor_id: str, body: PhotoDraftInput) -> dict[str, Any]:
    initialize()
    db = _connect()
    try:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT * FROM photo_drafts WHERE draft_id=? AND workspace_id=? AND archived_at IS NULL",
                         (draft_id, workspace_id)).fetchone()
        if not row:
            raise LookupError("Photo Draft not found")
        roles = _validate_assets(db, workspace_id, body)
        now = _now()
        if body.workspace_id != workspace_id:
            raise HTTPException(status_code=422, detail="workspace_id cannot be changed")
        payload = body.model_dump(mode="json", exclude={"workspace_id"})
        source_version_id, source_checksum = _snapshot_source_version(db, workspace_id, body.source_asset_id)
        payload["source_version_id"] = source_version_id
        payload["source_checksum_sha256"] = source_checksum
        db.execute("UPDATE photo_drafts SET payload_json=?, updated_at=? WHERE draft_id=? AND workspace_id=?",
                   (json.dumps(payload, ensure_ascii=False), now, draft_id, workspace_id))
        db.execute("DELETE FROM photo_draft_assets WHERE draft_id=?", (draft_id,))
        db.executemany("INSERT INTO photo_draft_assets(draft_id, asset_id, role) VALUES(?,?,?)",
                       [(draft_id, asset_id, role) for asset_id, role in roles])
        _event(db, draft_id, workspace_id, actor_id, "photo.draft_updated", {"operation": body.operation})
        result = db.execute("SELECT * FROM photo_drafts WHERE draft_id=?", (draft_id,)).fetchone()
        db.commit()
        return _public(result)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def archive_draft(draft_id: str, workspace_id: str, actor_id: str) -> dict[str, Any]:
    initialize()
    db = _connect()
    try:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT * FROM photo_drafts WHERE draft_id=? AND workspace_id=? AND archived_at IS NULL",
                         (draft_id, workspace_id)).fetchone()
        if not row:
            raise LookupError("Photo Draft not found")
        now = _now()
        db.execute("UPDATE photo_drafts SET archived_at=?, updated_at=? WHERE draft_id=? AND workspace_id=?",
                   (now, now, draft_id, workspace_id))
        _event(db, draft_id, workspace_id, actor_id, "photo.draft_archived")
        result = db.execute("SELECT * FROM photo_drafts WHERE draft_id=?", (draft_id,)).fetchone()
        db.commit()
        return _public(result)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def list_events(draft_id: str, workspace_id: str, *, limit: int = 100, offset: int = 0) -> dict[str, Any]:
    initialize(); db = _connect()
    try:
        total = int(db.execute("SELECT COUNT(*) AS n FROM photo_draft_events WHERE draft_id=? AND workspace_id=?",
                               (draft_id, workspace_id)).fetchone()["n"])
        rows = db.execute("SELECT event_id, draft_id, actor_id, event_type, details_json, created_at FROM photo_draft_events WHERE draft_id=? AND workspace_id=? ORDER BY created_at DESC, event_id DESC LIMIT ? OFFSET ?",
                          (draft_id, workspace_id, limit, offset)).fetchall()
        items = [{**dict(row), "details": json.loads(row["details_json"])} for row in rows]
        return {"items": items, "total": total, "limit": limit, "offset": offset}
    finally:
        db.close()


LOCAL_PHOTO_PROCESSOR_VERSION = "pillow-local-1.0"
LOCAL_PHOTO_OPERATIONS = {"ENHANCE", "LIGHTING"}
PHOTO_RUN_LEASE_SECONDS = 1800


def _run_event(db: sqlite3.Connection, run_id: str, draft_id: str, workspace_id: str,
               actor_id: str, event_type: str, details: dict[str, Any] | None = None) -> None:
    db.execute("""INSERT INTO photo_processing_events(event_id,run_id,draft_id,workspace_id,
        actor_id,event_type,details_json,created_at) VALUES(?,?,?,?,?,?,?,?)""",
        ("phe_" + uuid.uuid4().hex, run_id, draft_id, workspace_id, actor_id, event_type,
         json.dumps(details or {}, ensure_ascii=False, separators=(",", ":")), _now()))


def _run_public(row: sqlite3.Row) -> dict[str, Any]:
    value = dict(row)
    value["quality"] = json.loads(value.pop("quality_json") or "{}")
    value.pop("claimed_by", None)
    value.pop("lease_expires_at", None)
    value.pop("payload_hash", None)
    value.pop("idempotency_key", None)
    return value


def claim_local_run(draft_id: str, workspace_id: str, actor_id: str, idempotency_key: str) -> dict[str, Any] | None:
    initialize()
    now_dt = datetime.now(timezone.utc)
    now = now_dt.isoformat()
    token = uuid.uuid4().hex
    db = _connect()
    try:
        db.execute("BEGIN IMMEDIATE")
        draft = db.execute("SELECT * FROM photo_drafts WHERE draft_id=? AND workspace_id=? AND archived_at IS NULL",
                           (draft_id, workspace_id)).fetchone()
        if not draft:
            return None
        payload = json.loads(draft["payload_json"])
        operation = payload.get("operation")
        if operation not in LOCAL_PHOTO_OPERATIONS:
            raise ValueError("This operation requires an AI Photo Engine; local processing supports ENHANCE and LIGHTING only")
        if int(payload.get("output_count", 1)) != 1:
            raise ValueError("Local processing supports exactly one output per run")
        if payload.get("mask_asset_id") or payload.get("reference_asset_ids"):
            raise ValueError("Local processing does not consume mask or reference images")
        if payload.get("target_style") or payload.get("prompt"):
            raise ValueError("Local processing does not interpret style notes or natural-language prompts")
        source_snapshot = db.execute("""SELECT a.asset_id,v.version_id,v.checksum_sha256 FROM assets a
            JOIN asset_versions v ON v.asset_id=a.asset_id AND v.workspace_id=a.workspace_id
            WHERE a.asset_id=? AND a.workspace_id=? AND a.deleted_at IS NULL
              AND v.version_id=?""",
            (payload["source_asset_id"], workspace_id, payload.get("source_version_id"))).fetchone() if payload.get("source_version_id") else None
        if source_snapshot is None and not payload.get("source_version_id"):
            source_version_id, source_checksum = _snapshot_source_version(db, workspace_id, payload["source_asset_id"])
            payload["source_version_id"] = source_version_id
            payload["source_checksum_sha256"] = source_checksum
            db.execute("UPDATE photo_drafts SET payload_json=?,updated_at=? WHERE draft_id=?",
                       (json.dumps(payload, ensure_ascii=False), now, draft_id))
            _event(db, draft_id, workspace_id, actor_id, "photo.source_version_snapshotted",
                   {"source_version_id": source_version_id, "source_checksum_sha256": source_checksum})
            source_snapshot = db.execute("SELECT asset_id,version_id,checksum_sha256 FROM assets a JOIN asset_versions v ON v.asset_id=a.asset_id WHERE a.asset_id=? AND a.workspace_id=? AND v.version_id=?",
                                         (payload["source_asset_id"], workspace_id, source_version_id)).fetchone()
        if (source_snapshot is None or source_snapshot["checksum_sha256"] != payload.get("source_checksum_sha256")):
            raise ValueError("Photo Draft source AssetVersion snapshot is missing or no longer matches its checksum")
        fingerprint = hashlib.sha256(json.dumps({"payload": payload, "processor": LOCAL_PHOTO_PROCESSOR_VERSION},
                                                  sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        existing = db.execute("SELECT * FROM photo_processing_runs WHERE workspace_id=? AND idempotency_key=?",
                              (workspace_id, idempotency_key)).fetchone()
        if existing:
            if existing["payload_hash"] != fingerprint or existing["draft_id"] != draft_id:
                raise ValueError("Idempotency-Key was already used with a different Photo Draft or input")
            if existing["status"] == "succeeded":
                return {"already_succeeded": True, "run": _run_public(existing), "payload": payload}
            lease = datetime.fromisoformat(existing["lease_expires_at"]) if existing["lease_expires_at"] else None
            if existing["status"] == "processing" and lease and lease > now_dt:
                raise ValueError("This Photo processing run is already in progress")
            db.execute("""UPDATE photo_processing_runs SET status='processing',attempts=attempts+1,
                claimed_by=?,lease_expires_at=?,error_message=NULL,updated_at=? WHERE run_id=?""",
                (token, (now_dt + timedelta(seconds=PHOTO_RUN_LEASE_SECONDS)).isoformat(), now, existing["run_id"]))
            _run_event(db, existing["run_id"], draft_id, workspace_id, actor_id,
                       "photo.local_run_reclaimed" if existing["status"] == "processing" else "photo.local_run_retried",
                       {"attempt": int(existing["attempts"]) + 1})
            run_id = existing["run_id"]
        else:
            run_id = "phr_" + uuid.uuid4().hex
            db.execute("""INSERT INTO photo_processing_runs(run_id,draft_id,workspace_id,created_by,
                idempotency_key,payload_hash,processor_version,operation,source_version_id,source_checksum_sha256,
                status,attempts,claimed_by,lease_expires_at,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,'processing',1,?,?,?,?)""",
                (run_id, draft_id, workspace_id, actor_id, idempotency_key, fingerprint,
                 LOCAL_PHOTO_PROCESSOR_VERSION, operation, payload["source_version_id"],
                 payload["source_checksum_sha256"], token,
                 (now_dt + timedelta(seconds=PHOTO_RUN_LEASE_SECONDS)).isoformat(), now, now))
            _run_event(db, run_id, draft_id, workspace_id, actor_id, "photo.local_run_started",
                       {"operation": operation, "processor_version": LOCAL_PHOTO_PROCESSOR_VERSION})
        db.commit()
        return {"already_succeeded": False, "run_id": run_id, "claim_token": token, "payload": payload}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def complete_local_run(run_id: str, claim_token: str, actor_id: str, *, asset_id: str,
                       version_id: str, checksum: str, quality: dict[str, Any]) -> bool:
    db = _connect()
    try:
        db.execute("BEGIN IMMEDIATE")
        now = datetime.now(timezone.utc).isoformat()
        row = db.execute("SELECT * FROM photo_processing_runs WHERE run_id=? AND status='processing' AND claimed_by=? AND lease_expires_at>?",
                         (run_id, claim_token, now)).fetchone()
        if not row:
            return False
        db.execute("""UPDATE photo_processing_runs SET status='succeeded',output_asset_id=?,
            output_version_id=?,output_checksum_sha256=?,quality_json=?,claimed_by=NULL,
            lease_expires_at=NULL,error_message=NULL,updated_at=? WHERE run_id=?""",
            (asset_id, version_id, checksum, json.dumps(quality, separators=(",", ":")), now, run_id))
        _run_event(db, run_id, row["draft_id"], row["workspace_id"], actor_id,
                   "photo.local_run_succeeded", {"output_asset_id": asset_id,
                   "output_version_id": version_id, "checksum_sha256": checksum})
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def fail_local_run(run_id: str, claim_token: str, actor_id: str, error: str) -> None:
    db = _connect()
    try:
        db.execute("BEGIN IMMEDIATE")
        now = _now()
        row = db.execute("SELECT * FROM photo_processing_runs WHERE run_id=? AND status='processing' AND claimed_by=?",
                         (run_id, claim_token)).fetchone()
        if row:
            db.execute("UPDATE photo_processing_runs SET status='failed',error_message=?,claimed_by=NULL,lease_expires_at=NULL,updated_at=? WHERE run_id=?",
                       (error[:500], now, run_id))
            _run_event(db, run_id, row["draft_id"], row["workspace_id"], actor_id,
                       "photo.local_run_failed", {"error": error[:500]})
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def list_processing_runs(draft_id: str, workspace_id: str, *, limit: int = 50, offset: int = 0) -> dict[str, Any]:
    initialize()
    db = _connect()
    try:
        total = int(db.execute("SELECT COUNT(*) AS n FROM photo_processing_runs WHERE draft_id=? AND workspace_id=?",
                               (draft_id, workspace_id)).fetchone()["n"])
        rows = db.execute("""SELECT r.*,
            (SELECT e.decision FROM photo_output_review_events e WHERE e.run_id=r.run_id
             ORDER BY e.rowid DESC LIMIT 1) AS review_status
            FROM photo_processing_runs r WHERE r.draft_id=? AND r.workspace_id=?
            ORDER BY r.created_at DESC,r.run_id DESC LIMIT ? OFFSET ?""",
                          (draft_id, workspace_id, limit, offset)).fetchall()
        return {"items": [_run_public(row) for row in rows], "total": total, "limit": limit, "offset": offset}
    finally:
        db.close()


def list_processing_events(run_id: str, draft_id: str, workspace_id: str, *, limit: int = 100, offset: int = 0) -> dict[str, Any]:
    initialize()
    db = _connect()
    try:
        total = int(db.execute("SELECT COUNT(*) AS n FROM photo_processing_events WHERE run_id=? AND draft_id=? AND workspace_id=?",
                               (run_id, draft_id, workspace_id)).fetchone()["n"])
        rows = db.execute("SELECT * FROM photo_processing_events WHERE run_id=? AND draft_id=? AND workspace_id=? ORDER BY rowid DESC LIMIT ? OFFSET ?",
                          (run_id, draft_id, workspace_id, limit, offset)).fetchall()
        return {"items": [{**dict(row), "details": json.loads(row["details_json"])} for row in rows],
                "total": total, "limit": limit, "offset": offset}
    finally:
        db.close()


def _photo_output_base(db: sqlite3.Connection, draft_id: str, run_id: str, workspace_id: str):
    return db.execute("""SELECT r.run_id,r.draft_id,r.workspace_id,r.status AS run_status,
        r.operation,r.processor_version,r.source_version_id,r.source_checksum_sha256,
        r.output_asset_id,r.output_version_id,r.output_checksum_sha256,
        r.quality_json,r.created_at,r.updated_at,a.asset_id AS active_asset_id,
        v.version_id AS verified_version_id,v.checksum_sha256 AS version_checksum,
        v.storage_key AS version_storage_key,v.size_bytes AS version_size_bytes,v.media_type AS version_media_type,
        (SELECT p.provenance_id FROM asset_provenance p WHERE p.asset_id=a.asset_id
         AND p.event_type='asset.photo_processed' ORDER BY p.created_at DESC,p.provenance_id DESC LIMIT 1) AS provenance_id
        FROM photo_processing_runs r LEFT JOIN assets a ON a.asset_id=r.output_asset_id
            AND a.workspace_id=r.workspace_id AND a.deleted_at IS NULL
        LEFT JOIN asset_versions v ON v.asset_id=a.asset_id AND v.workspace_id=r.workspace_id
            AND v.version_id=r.output_version_id
        WHERE r.draft_id=? AND r.run_id=? AND r.workspace_id=?""",
        (draft_id, run_id, workspace_id)).fetchone()


def _verify_photo_output_version(base: sqlite3.Row) -> bool:
    if (not base["active_asset_id"] or not base["verified_version_id"] or not base["provenance_id"]
            or base["version_checksum"] != base["output_checksum_sha256"]):
        return False
    storage_key = base["version_storage_key"]
    if not storage_key or Path(storage_key).name != storage_key:
        return False
    root = config.ASSET_STORAGE_DIR.resolve()
    path = (root / storage_key).resolve()
    if path.parent != root or not path.is_file():
        return False
    digest = hashlib.sha256()
    size = 0
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                size += len(chunk)
                digest.update(chunk)
    except OSError:
        return False
    return size == int(base["version_size_bytes"]) and digest.hexdigest() == base["version_checksum"]


def get_photo_output_review(draft_id: str, run_id: str, workspace_id: str) -> dict[str, Any] | None:
    initialize(); db = _connect()
    try:
        base = _photo_output_base(db, draft_id, run_id, workspace_id)
        if not base:
            return None
        rows = db.execute("SELECT * FROM photo_output_review_events WHERE run_id=? AND draft_id=? AND workspace_id=? ORDER BY rowid DESC",
                          (run_id, draft_id, workspace_id)).fetchall()
        events = [{k: row[k] for k in ("event_id", "run_id", "draft_id", "actor_id", "decision", "comment",
                    "asset_id", "asset_version_id", "provenance_id", "checksum_sha256", "created_at")} for row in rows]
        latest = events[0] if events else None
        if base["run_status"] != "succeeded":
            status = base["run_status"]
        elif not _verify_photo_output_version(base):
            status = "output_integrity_error"
        else:
            status = latest["decision"] if latest else "pending_review"
        return {"run_id": run_id, "status": status,
                "output": {"asset_id": base["output_asset_id"], "asset_version_id": base["verified_version_id"],
                           "provenance_id": base["provenance_id"], "checksum_sha256": base["version_checksum"],
                           "media_type": base["version_media_type"], "size_bytes": base["version_size_bytes"]},
                "events": events}
    finally:
        db.close()


def decide_photo_output_review(draft_id: str, run_id: str, workspace_id: str, actor_id: str,
                               decision: str, comment: str = "") -> dict[str, Any] | None:
    if decision not in {"approved", "changes_requested", "rejected"}:
        raise ValueError("Unsupported Photo output review decision")
    clean_comment = comment.strip()
    if decision in {"changes_requested", "rejected"} and not clean_comment:
        raise ValueError("A non-empty comment is required for this review decision")
    initialize(); db = _connect()
    try:
        db.execute("BEGIN IMMEDIATE")
        base = _photo_output_base(db, draft_id, run_id, workspace_id)
        if not base:
            return None
        if base["run_status"] != "succeeded":
            raise ValueError("Only succeeded Photo runs can be reviewed")
        if not _verify_photo_output_version(base):
            raise ValueError("Photo output AssetVersion or provenance failed integrity checks")
        latest = db.execute("SELECT decision FROM photo_output_review_events WHERE run_id=? ORDER BY rowid DESC LIMIT 1",
                            (run_id,)).fetchone()
        if latest and latest["decision"] in {"approved", "rejected"}:
            raise ValueError("Approved or rejected Photo outputs are terminal")
        if latest and latest["decision"] == decision:
            raise ValueError("The requested Photo review decision is already current")
        now = _now()
        db.execute("""INSERT INTO photo_output_review_events(event_id,run_id,draft_id,workspace_id,actor_id,
            decision,comment,asset_id,asset_version_id,provenance_id,checksum_sha256,created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            ("phrev_" + uuid.uuid4().hex, run_id, draft_id, workspace_id, actor_id, decision,
             clean_comment, base["output_asset_id"], base["verified_version_id"], base["provenance_id"],
             base["version_checksum"], now))
        db.commit()
        return get_photo_output_review(draft_id, run_id, workspace_id)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def create_photo_output_export_manifest(draft_id: str, run_id: str, workspace_id: str,
                                        actor_id: str) -> dict[str, Any] | None:
    initialize(); db = _connect()
    try:
        db.execute("BEGIN IMMEDIATE")
        base = _photo_output_base(db, draft_id, run_id, workspace_id)
        if not base:
            return None
        if base["run_status"] != "succeeded":
            raise ValueError("Only succeeded Photo runs can be exported")
        if not _verify_photo_output_version(base):
            raise ValueError("Photo output AssetVersion or provenance failed integrity checks")
        latest = db.execute("SELECT decision,actor_id,created_at,asset_id,asset_version_id,provenance_id,checksum_sha256 FROM photo_output_review_events WHERE run_id=? ORDER BY rowid DESC LIMIT 1",
                            (run_id,)).fetchone()
        if not latest or latest["decision"] != "approved":
            raise ValueError("Photo output must be individually approved before export")
        if (latest["asset_id"] != base["output_asset_id"]
                or latest["asset_version_id"] != base["verified_version_id"]
                or latest["provenance_id"] != base["provenance_id"]
                or latest["checksum_sha256"] != base["version_checksum"]):
            raise ValueError("Approved review snapshot no longer matches the immutable Photo output")
        manifest = {
            "manifest_type": "AI_CREATOR_STUDIO_INTERNAL_PHOTO_OUTPUT_MANIFEST",
            "manifest_version": 1,
            "draft_id": draft_id,
            "run": {"run_id": run_id, "operation": base["operation"],
                    "processor_version": base["processor_version"], "created_at": base["created_at"],
                    "source_version_id": base["source_version_id"],
                    "source_checksum_sha256": base["source_checksum_sha256"]},
            "output": {"asset_id": base["output_asset_id"], "asset_version_id": base["verified_version_id"],
                       "provenance_id": base["provenance_id"], "checksum_sha256": base["version_checksum"],
                       "media_type": base["version_media_type"], "size_bytes": base["version_size_bytes"],
                       "review_status": "approved", "approved_by": latest["actor_id"],
                       "reviewed_at": latest["created_at"]},
            "is_ai_generated": False,
            "publication_authorized": False,
            "commercial_rights_verified": False,
            "binary_files_included": False,
            "notice": "Internal metadata manifest only. No public distribution or commercial-use rights are granted.",
        }
        canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        now = _now()
        db.execute("""INSERT INTO photo_output_export_events(event_id,run_id,draft_id,workspace_id,
            actor_id,manifest_sha256,created_at) VALUES(?,?,?,?,?,?,?)""",
            ("phexp_" + uuid.uuid4().hex, run_id, draft_id, workspace_id, actor_id, digest, now))
        db.commit()
        return {"manifest": manifest, "manifest_sha256": digest, "exported_at": now}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _render_local_image(source_asset_id: str, source_version_id: str, source_checksum_sha256: str,
                        workspace_id: str, payload: dict[str, Any]) -> tuple[bytes, Any, dict[str, Any]]:
    from app.assets.store import get_asset, get_asset_version_record
    from app.takedown import state_of

    if state_of(source_asset_id) is not None:   # L-08: also when the hold came after the draft was saved
        raise ValueError("The source image is under review and cannot be processed")
    source = get_asset(source_asset_id, workspace_id)
    version = get_asset_version_record(source_asset_id, workspace_id, source_version_id)
    if not source or not version:
        raise ValueError("Snapshotted source image version is missing or inactive")
    version_path = (config.ASSET_STORAGE_DIR.resolve() / version["storage_key"]).resolve()
    if version_path.parent != config.ASSET_STORAGE_DIR.resolve() or not version_path.is_file():
        raise ValueError("Snapshotted source image version file is missing")
    original = version_path.read_bytes()
    digest = hashlib.sha256(original).hexdigest()
    if len(original) != int(version["size_bytes"]) or digest != source_checksum_sha256 or digest != version["checksum_sha256"]:
        raise ValueError("Snapshotted source image failed its immutable version integrity check")
    return render_local_image_bytes(original, source_version_id, source_checksum_sha256, payload)


def render_local_image_bytes(original: bytes, source_version_id: str, source_checksum_sha256: str,
                             payload: dict[str, Any]) -> tuple[bytes, Any, dict[str, Any]]:
    """Backend-independent deterministic rendering of already integrity-checked source bytes."""
    import io
    from PIL import Image, ImageEnhance, ImageOps
    from app.assets.validation import validate_image_upload

    with Image.open(io.BytesIO(original)) as opened:
        opened.load()
        width, height = opened.size
        has_alpha = "A" in opened.getbands() or "transparency" in opened.info
        alpha = opened.convert("RGBA").getchannel("A") if has_alpha else None
        image = opened.convert("RGB")
    operation = payload["operation"]
    if operation == "ENHANCE":
        extrema = image.getextrema()
        if any(high - low >= 16 for low, high in extrema):
            image = ImageOps.autocontrast(image, cutoff=0.5)
        image = ImageEnhance.Color(image).enhance(1.04)
        image = ImageEnhance.Sharpness(image).enhance(1.12)
    elif operation == "LIGHTING":
        image = ImageEnhance.Brightness(image).enhance(1.08)
        image = ImageEnhance.Contrast(image).enhance(1.03)
    else:
        raise ValueError("Unsupported local Photo operation")
    if alpha is not None and payload["output_format"] != "JPEG":
        image.putalpha(alpha)
    output = io.BytesIO()
    fmt = payload["output_format"]
    if fmt == "JPEG":
        image = image.convert("RGB")
        image.save(output, format="JPEG", quality=94, optimize=True)
        extension = "jpg"
    elif fmt == "WEBP":
        image.save(output, format="WEBP", quality=94, method=4)
        extension = "webp"
    else:
        image.save(output, format="PNG", optimize=True)
        extension = "png"
    content = output.getvalue()
    filename = f"photo-{operation.lower()}-{uuid.uuid4().hex[:8]}.{extension}"
    validated = validate_image_upload(filename, content, max_bytes=config.ASSET_MAX_UPLOAD_BYTES)
    quality = {
        "processor": "Pillow deterministic local image processor",
        "processor_version": LOCAL_PHOTO_PROCESSOR_VERSION,
        "source_version_id": source_version_id,
        "source_checksum_sha256": source_checksum_sha256,
        "operation": operation,
        "input_width": width, "input_height": height,
        "output_width": width, "output_height": height,
        "spatial_geometry_preserved": True,
        "semantic_identity_preservation_verified": False,
        "text_and_logo_preservation_verified": False,
        "requested_preservation": {
            "identity": bool(payload.get("preserve_identity", True)),
            "product_geometry": bool(payload.get("preserve_product_geometry", True)),
            "text_and_logo": bool(payload.get("preserve_text_and_logo", True)),
        },
        "review_required": True,
        "is_ai_generated": False,
        "provider_dispatched": False,
        "credit_charged": False,
    }
    return content, validated, quality


def execute_local_processing(draft_id: str, workspace_id: str, actor_id: str, idempotency_key: str) -> dict[str, Any] | None:
    # L-08: refuse before a run is claimed, so a held source leaves no failed run behind and the answer names the real reason.
    # (_render_local_image checks again for a hold that arrives between the claim and the render.)
    pre = _connect()
    try:
        row = pre.execute("SELECT payload_json FROM photo_drafts WHERE draft_id=? AND workspace_id=?", (draft_id, workspace_id)).fetchone()
        from app.takedown import held_among
        if row and held_among(pre, [json.loads(row["payload_json"]).get("source_asset_id")]):
            raise ValueError("The source image is under review and cannot be used.")   # the port turns a ValueError into a 409
    finally:
        pre.close()
    claim = claim_local_run(draft_id, workspace_id, actor_id, idempotency_key)
    if claim is None:
        return None
    from app.assets.store import get_asset, save_derived_image_asset
    if claim["already_succeeded"]:
        run = claim["run"]
        asset = get_asset(run["output_asset_id"], workspace_id)
        return {"run": run, "output_asset": asset | {"version_id": run["output_version_id"]} if asset else None}
    run_id, token, payload = claim["run_id"], claim["claim_token"], claim["payload"]
    try:
        content, validated, quality = _render_local_image(payload["source_asset_id"], payload["source_version_id"],
                                                          payload["source_checksum_sha256"], workspace_id, payload)
        asset_id = "ast_photo_" + run_id.removeprefix("phr_")
        asset = save_derived_image_asset(asset_id=asset_id, owner_id=actor_id,
            workspace_id=workspace_id, source_asset_id=payload["source_asset_id"],
            source_version_id=payload["source_version_id"], source_checksum_sha256=payload["source_checksum_sha256"],
            filename=f"photo-{payload['operation'].lower()}.{payload['output_format'].lower()}",
            content=content, validated=validated, run_id=run_id,
            operation=payload["operation"], processor_version=LOCAL_PHOTO_PROCESSOR_VERSION)
        if not complete_local_run(run_id, token, actor_id, asset_id=asset_id,
                                  version_id=asset["version_id"], checksum=asset["checksum_sha256"], quality=quality):
            db = _connect()
            try:
                row = db.execute("SELECT * FROM photo_processing_runs WHERE run_id=?", (run_id,)).fetchone()
            finally:
                db.close()
            if not row or row["status"] != "succeeded":
                raise RuntimeError("Photo processing lease was lost before finalization")
            run = _run_public(row)
        else:
            db = _connect()
            try:
                row = db.execute("SELECT * FROM photo_processing_runs WHERE run_id=?", (run_id,)).fetchone()
            finally:
                db.close()
            run = _run_public(row)
        return {"run": run, "output_asset": asset}
    except Exception as exc:
        safe_error = "Source image integrity validation failed" if isinstance(exc, ValueError) else "Local image processing failed"
        fail_local_run(run_id, token, actor_id, safe_error)
        raise RuntimeError(safe_error) from exc


@router.post("", status_code=201, response_model=PhotoDraftResponse)
async def create_photo_draft(body: PhotoDraftInput, user_id: str = Depends(current_user)):
    try:
        return get_photo_draft_port().create(body.workspace_id, user_id, body)
    except Exception as exc:  # noqa: BLE001 - mapped centrally, unknown errors re-raised
        raise_http(exc)


@router.get("", response_model=PhotoDraftListResponse)
async def get_photo_drafts(workspace_id: str = Query(min_length=2, max_length=64),
                           include_archived: bool = False,
                           limit: int = Query(default=50, ge=1, le=100),
                           offset: int = Query(default=0, ge=0),
                           user_id: str = Depends(current_user)):
    try:
        return get_photo_draft_port().list(workspace_id, user_id, include_archived, limit, offset)
    except Exception as exc:  # noqa: BLE001
        raise_http(exc)


@router.get("/{draft_id}/events", response_model=EventListResponse)
async def get_photo_draft_events(draft_id: str, workspace_id: str = Query(min_length=2, max_length=64),
                                 limit: int = Query(default=100, ge=1, le=500),
                                 offset: int = Query(default=0, ge=0),
                                 user_id: str = Depends(current_user)):
    try:
        return get_photo_draft_port().events(draft_id, workspace_id, user_id, limit, offset)
    except Exception as exc:  # noqa: BLE001
        raise_http(exc)


@router.post("/{draft_id}/process-local", response_model=PhotoLocalProcessingResponse)
async def process_photo_draft_locally(draft_id: str,
                                      workspace_id: str = Query(min_length=2, max_length=64),
                                      idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
                                      user_id: str = Depends(current_user)):
    idempotency_key = idempotency_key.strip() if idempotency_key else ""
    if not 8 <= len(idempotency_key) <= 128:
        raise HTTPException(status_code=422, detail="Idempotency-Key header is required (8..128 characters)")
    try:
        return get_photo_draft_port().process_local(draft_id, workspace_id, user_id, idempotency_key)
    except LocalProcessingFailed as exc:
        raise HTTPException(status_code=422, detail={"code": "PHOTO_LOCAL_PROCESSING_FAILED", "message": str(exc)}) from exc
    except Exception as exc:  # noqa: BLE001
        raise_http(exc)


@router.get("/{draft_id}/runs", response_model=PhotoRunListResponse)
async def get_photo_processing_runs(draft_id: str, workspace_id: str = Query(min_length=2, max_length=64),
                                    limit: int = Query(default=50, ge=1, le=100),
                                    offset: int = Query(default=0, ge=0),
                                    user_id: str = Depends(current_user)):
    try:
        return get_photo_draft_port().runs(draft_id, workspace_id, user_id, limit, offset)
    except Exception as exc:  # noqa: BLE001
        raise_http(exc)


@router.get("/{draft_id}/runs/{run_id}/events", response_model=EventListResponse)
async def get_photo_processing_run_events(draft_id: str, run_id: str,
                                          workspace_id: str = Query(min_length=2, max_length=64),
                                          limit: int = Query(default=100, ge=1, le=500),
                                          offset: int = Query(default=0, ge=0),
                                          user_id: str = Depends(current_user)):
    try:
        return get_photo_draft_port().run_events(draft_id, run_id, workspace_id, user_id, limit, offset)
    except Exception as exc:  # noqa: BLE001
        raise_http(exc)


@router.get("/{draft_id}/runs/{run_id}/review", response_model=PhotoOutputReviewResponse)
async def get_photo_run_review(draft_id: str, run_id: str,
                               workspace_id: str = Query(min_length=2, max_length=64),
                               user_id: str = Depends(current_user)):
    try:
        return get_photo_draft_port().review(draft_id, run_id, workspace_id, user_id)
    except Exception as exc:  # noqa: BLE001
        raise_http(exc)


async def _decide_photo_run_review(draft_id: str, run_id: str, body: PhotoOutputReviewInput,
                                   decision: str, workspace_id: str, user_id: str):
    try:
        return get_photo_draft_port().decide(draft_id, run_id, workspace_id, user_id, decision, body.comment)
    except Exception as exc:  # noqa: BLE001
        raise_http(exc)


@router.post("/{draft_id}/runs/{run_id}/review/approve", response_model=PhotoOutputReviewResponse)
async def approve_photo_run_output(draft_id: str, run_id: str, body: PhotoOutputReviewInput,
                                   workspace_id: str = Query(min_length=2, max_length=64),
                                   user_id: str = Depends(current_user)):
    return await _decide_photo_run_review(draft_id, run_id, body, "approved", workspace_id, user_id)


@router.post("/{draft_id}/runs/{run_id}/review/request-changes", response_model=PhotoOutputReviewResponse)
async def request_photo_run_output_changes(draft_id: str, run_id: str, body: PhotoOutputReviewInput,
                                            workspace_id: str = Query(min_length=2, max_length=64),
                                            user_id: str = Depends(current_user)):
    return await _decide_photo_run_review(draft_id, run_id, body, "changes_requested", workspace_id, user_id)


@router.post("/{draft_id}/runs/{run_id}/review/reject", response_model=PhotoOutputReviewResponse)
async def reject_photo_run_output(draft_id: str, run_id: str, body: PhotoOutputReviewInput,
                                 workspace_id: str = Query(min_length=2, max_length=64),
                                 user_id: str = Depends(current_user)):
    return await _decide_photo_run_review(draft_id, run_id, body, "rejected", workspace_id, user_id)


@router.post("/{draft_id}/runs/{run_id}/export-manifest", response_model=ManifestExportResponse)
async def export_photo_run_manifest(draft_id: str, run_id: str,
                                    workspace_id: str = Query(min_length=2, max_length=64),
                                    user_id: str = Depends(current_user)):
    try:
        return get_photo_draft_port().export_manifest(draft_id, run_id, workspace_id, user_id)
    except Exception as exc:  # noqa: BLE001
        raise_http(exc)


@router.get("/{draft_id}")
async def read_photo_draft(draft_id: str, workspace_id: str = Query(min_length=2, max_length=64),
                           user_id: str = Depends(current_user)):
    try:
        return get_photo_draft_port().get(draft_id, workspace_id, user_id)
    except Exception as exc:  # noqa: BLE001
        raise_http(exc)


@router.put("/{draft_id}", response_model=PhotoDraftResponse)
async def revise_photo_draft(draft_id: str, body: PhotoDraftInput, user_id: str = Depends(current_user)):
    try:
        return get_photo_draft_port().update(draft_id, body.workspace_id, user_id, body)
    except Exception as exc:  # noqa: BLE001
        raise_http(exc)


@router.post("/{draft_id}/archive", response_model=PhotoDraftResponse)
async def archive_photo_draft(draft_id: str, workspace_id: str = Query(min_length=2, max_length=64),
                              user_id: str = Depends(current_user)):
    try:
        return get_photo_draft_port().archive(draft_id, workspace_id, user_id)
    except Exception as exc:  # noqa: BLE001
        raise_http(exc)
