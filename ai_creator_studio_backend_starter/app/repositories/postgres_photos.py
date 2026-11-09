"""PostgreSQL Photo Draft aggregate repository; not runtime-selected yet.

Mirrors app.photo_engine persistence semantics (drafts, image roles, events,
local processing runs with idempotency and leases). Request-model validation and
local image rendering stay in the route/adapter layer.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from app.postgres import apply_migrations, connect
from app.repo_errors import DetailedValueError, InsufficientRoleError, NotAMemberError, RepositoryConflictError

LOCAL_PHOTO_PROCESSOR_VERSION = "pillow-local-1.0"
LOCAL_PHOTO_OPERATIONS = {"ENHANCE", "LIGHTING"}
PHOTO_RUN_LEASE_SECONDS = 1800
_OPERATIONS = {"ENHANCE", "BACKGROUND", "LIGHTING", "RETOUCH", "COMPOSE"}


class PhotoSourceVersionError(RepositoryConflictError):
    """Source image has no current verified immutable AssetVersion."""


class PostgreSQLPhotoRepository:
    backend = "postgresql"
    WRITABLE_ROLES = {"owner", "admin", "editor"}
    READABLE_ROLES = WRITABLE_ROLES | {"viewer"}

    def initialize(self) -> None:
        apply_migrations()

    # ---- helpers -------------------------------------------------------
    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _jsonb(value: Any):
        from psycopg.types.json import Jsonb
        return Jsonb(value)

    @classmethod
    def _require(cls, conn: Any, workspace_id: str, actor_id: str, *, write: bool) -> None:
        row = conn.execute("SELECT role FROM workspace_members WHERE workspace_id=%s AND user_id=%s",
                           (workspace_id, actor_id)).fetchone()
        role = str(row["role"]) if row else None
        if role is None:
            raise NotAMemberError("User is not a member of this workspace")
        if role not in (cls.WRITABLE_ROLES if write else cls.READABLE_ROLES):
            raise InsufficientRoleError("Workspace role cannot " + ("modify" if write else "read") + " photo drafts")

    @staticmethod
    def _roles(payload: dict[str, Any]) -> list[tuple[str, str]]:
        source = payload.get("source_asset_id")
        if not isinstance(source, str) or not 8 <= len(source) <= 80:
            raise ValueError("source_asset_id is required")
        if payload.get("operation") not in _OPERATIONS:
            raise ValueError("operation is invalid")
        refs = payload.get("reference_asset_ids") or []
        if not isinstance(refs, list) or len(refs) > 8:
            raise ValueError("reference_asset_ids must be a list of at most 8 items")
        roles = [(source, "source")]
        if payload.get("mask_asset_id"):
            roles.append((payload["mask_asset_id"], "mask"))
        roles.extend((a, "reference") for a in refs)
        ids = [a for a, _ in roles]
        if len(ids) != len(set(ids)):
            raise ValueError("An image asset may appear only once in a Photo Draft")
        return roles

    @staticmethod
    def _validate_assets(conn: Any, workspace_id: str, roles: list[tuple[str, str]]) -> None:
        ids = [a for a, _ in roles]
        rows = conn.execute(
            """SELECT asset_id FROM assets WHERE workspace_id=%s AND deleted_at IS NULL
               AND media_type LIKE 'image/%%' AND asset_id = ANY(%s) ORDER BY asset_id FOR SHARE""", (workspace_id, ids)).fetchall()
        if len(rows) != len(ids):
            raise DetailedValueError({"code": "PHOTO_IMAGE_ASSET_REQUIRED",
                "message": "Every source, mask, and reference must be an active image asset in this workspace."})

    @staticmethod
    def _snapshot_source(conn: Any, workspace_id: str, asset_id: str) -> tuple[str, str]:
        row = conn.execute(
            """SELECT v.version_id, v.checksum_sha256 FROM assets a
               JOIN asset_versions v ON v.asset_id=a.asset_id AND v.workspace_id=a.workspace_id
               WHERE a.asset_id=%s AND a.workspace_id=%s AND a.deleted_at IS NULL
                 AND a.media_type LIKE 'image/%%' AND v.storage_key=a.storage_key FOR SHARE OF a""",
            (asset_id, workspace_id)).fetchone()
        if row is None:
            raise PhotoSourceVersionError("Source image has no current verified immutable AssetVersion")
        return str(row["version_id"]), str(row["checksum_sha256"])

    @classmethod
    def _event(cls, conn: Any, draft_id: str, workspace_id: str, actor_id: str, event_type: str,
               details: dict[str, Any] | None = None) -> None:
        conn.execute(
            """INSERT INTO photo_draft_events(event_id,draft_id,workspace_id,actor_id,event_type,details_json,created_at)
               VALUES(%s,%s,%s,%s,%s,%s,%s)""",
            ("pde_" + uuid.uuid4().hex, draft_id, workspace_id, actor_id, event_type,
             cls._jsonb(details or {}), cls._now()))

    @classmethod
    def _run_event(cls, conn: Any, run: Any, actor_id: str, event_type: str,
                   details: dict[str, Any] | None = None) -> None:
        conn.execute(
            """INSERT INTO photo_processing_events(event_id,run_id,draft_id,workspace_id,actor_id,event_type,details_json,created_at)
               VALUES(%s,%s,%s,%s,%s,%s,%s,%s)""",
            ("phe_" + uuid.uuid4().hex, run["run_id"], run["draft_id"], run["workspace_id"], actor_id,
             event_type, cls._jsonb(details or {}), cls._now()))

    @staticmethod
    def _public(row: Any) -> dict[str, Any]:
        value = dict(row)
        value["input"] = value.pop("payload_json")
        value["status"] = "archived" if value["archived_at"] else "draft"
        return value

    @staticmethod
    def _run_public(row: Any) -> dict[str, Any]:
        value = dict(row)
        value["quality"] = value.pop("quality_json") or {}
        for key in ("claimed_by", "lease_expires_at", "payload_hash", "idempotency_key"):
            value.pop(key, None)
        return value

    @staticmethod
    def _page(limit: int, offset: int, maximum: int) -> None:
        if not 1 <= limit <= maximum or offset < 0:
            raise ValueError("Pagination is outside the allowed range")

    # ---- drafts --------------------------------------------------------
    def _write_draft_assets(self, conn: Any, draft_id: str, roles: list[tuple[str, str]]) -> None:
        conn.execute("DELETE FROM photo_draft_assets WHERE draft_id=%s", (draft_id,))
        conn.cursor().executemany("INSERT INTO photo_draft_assets(draft_id,asset_id,role) VALUES(%s,%s,%s)",
                                  [(draft_id, a, r) for a, r in roles])

    def create_draft(self, workspace_id: str, actor_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        payload = {k: v for k, v in payload.items() if k != "workspace_id"}
        roles = self._roles(payload)
        draft_id, now = "phd_" + uuid.uuid4().hex, self._now()
        with connect() as conn:
            self._require(conn, workspace_id, actor_id, write=True)
            self._validate_assets(conn, workspace_id, roles)
            payload["source_version_id"], payload["source_checksum_sha256"] = self._snapshot_source(
                conn, workspace_id, payload["source_asset_id"])
            conn.execute(
                "INSERT INTO photo_drafts(draft_id,workspace_id,created_by,payload_json,created_at,updated_at) VALUES(%s,%s,%s,%s,%s,%s)",
                (draft_id, workspace_id, actor_id, self._jsonb(payload), now, now))
            self._write_draft_assets(conn, draft_id, roles)
            self._event(conn, draft_id, workspace_id, actor_id, "photo.draft_created", {"operation": payload["operation"]})
            return self._public(conn.execute("SELECT * FROM photo_drafts WHERE draft_id=%s", (draft_id,)).fetchone())

    def list_drafts(self, workspace_id: str, actor_id: str, include_archived: bool = False, *,
                    limit: int = 50, offset: int = 0) -> dict[str, Any]:
        self._page(limit, offset, 100)
        where = "workspace_id=%s" + ("" if include_archived else " AND archived_at IS NULL")
        with connect() as conn:
            self._require(conn, workspace_id, actor_id, write=False)
            total = int(conn.execute(f"SELECT COUNT(*) AS n FROM photo_drafts WHERE {where}", (workspace_id,)).fetchone()["n"])
            rows = conn.execute(
                f"SELECT * FROM photo_drafts WHERE {where} ORDER BY updated_at DESC, draft_id LIMIT %s OFFSET %s",
                (workspace_id, limit, offset)).fetchall()
            return {"items": [self._public(r) for r in rows], "total": total, "limit": limit, "offset": offset}

    def get_draft(self, draft_id: str, workspace_id: str, actor_id: str) -> dict[str, Any] | None:
        with connect() as conn:
            self._require(conn, workspace_id, actor_id, write=False)
            row = conn.execute("SELECT * FROM photo_drafts WHERE draft_id=%s AND workspace_id=%s",
                               (draft_id, workspace_id)).fetchone()
            return self._public(row) if row else None

    def update_draft(self, draft_id: str, workspace_id: str, actor_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        if payload.get("workspace_id", workspace_id) != workspace_id:
            raise ValueError("workspace_id cannot be changed")
        payload = {k: v for k, v in payload.items() if k != "workspace_id"}
        roles = self._roles(payload)
        with connect() as conn:
            self._require(conn, workspace_id, actor_id, write=True)
            row = conn.execute(
                "SELECT draft_id FROM photo_drafts WHERE draft_id=%s AND workspace_id=%s AND archived_at IS NULL FOR UPDATE",
                (draft_id, workspace_id)).fetchone()
            if row is None:
                raise LookupError("Photo Draft not found")
            self._validate_assets(conn, workspace_id, roles)
            payload["source_version_id"], payload["source_checksum_sha256"] = self._snapshot_source(
                conn, workspace_id, payload["source_asset_id"])
            conn.execute("UPDATE photo_drafts SET payload_json=%s, updated_at=%s WHERE draft_id=%s AND workspace_id=%s",
                         (self._jsonb(payload), self._now(), draft_id, workspace_id))
            self._write_draft_assets(conn, draft_id, roles)
            self._event(conn, draft_id, workspace_id, actor_id, "photo.draft_updated", {"operation": payload["operation"]})
            return self._public(conn.execute("SELECT * FROM photo_drafts WHERE draft_id=%s", (draft_id,)).fetchone())

    def archive_draft(self, draft_id: str, workspace_id: str, actor_id: str) -> dict[str, Any]:
        with connect() as conn:
            self._require(conn, workspace_id, actor_id, write=True)
            row = conn.execute(
                "SELECT draft_id FROM photo_drafts WHERE draft_id=%s AND workspace_id=%s AND archived_at IS NULL FOR UPDATE",
                (draft_id, workspace_id)).fetchone()
            if row is None:
                raise LookupError("Photo Draft not found")
            now = self._now()
            conn.execute("UPDATE photo_drafts SET archived_at=%s, updated_at=%s WHERE draft_id=%s AND workspace_id=%s",
                         (now, now, draft_id, workspace_id))
            self._event(conn, draft_id, workspace_id, actor_id, "photo.draft_archived")
            return self._public(conn.execute("SELECT * FROM photo_drafts WHERE draft_id=%s", (draft_id,)).fetchone())

    def list_events(self, draft_id: str, workspace_id: str, actor_id: str, *, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        self._page(limit, offset, 500)
        with connect() as conn:
            self._require(conn, workspace_id, actor_id, write=False)
            total = int(conn.execute("SELECT COUNT(*) AS n FROM photo_draft_events WHERE draft_id=%s AND workspace_id=%s",
                                     (draft_id, workspace_id)).fetchone()["n"])
            rows = conn.execute(
                """SELECT event_id,draft_id,actor_id,event_type,details_json,created_at FROM photo_draft_events
                   WHERE draft_id=%s AND workspace_id=%s ORDER BY created_at DESC, event_id DESC LIMIT %s OFFSET %s""",
                (draft_id, workspace_id, limit, offset)).fetchall()
            items = []
            for r in rows:
                v = dict(r); v["details"] = v.pop("details_json"); items.append(v)
            return {"items": items, "total": total, "limit": limit, "offset": offset}

    # ---- local processing runs ----------------------------------------
    def claim_local_run(self, draft_id: str, workspace_id: str, actor_id: str, idempotency_key: str,
                        *, lease_seconds: int = PHOTO_RUN_LEASE_SECONDS) -> dict[str, Any] | None:
        if not isinstance(idempotency_key, str) or not 1 <= len(idempotency_key) <= 200:
            raise ValueError("Idempotency-Key must contain 1 to 200 characters")
        now_dt, token = self._now(), uuid.uuid4().hex
        lease = now_dt + timedelta(seconds=lease_seconds)
        with connect() as conn:
            self._require(conn, workspace_id, actor_id, write=True)
            draft = conn.execute(
                "SELECT * FROM photo_drafts WHERE draft_id=%s AND workspace_id=%s AND archived_at IS NULL FOR UPDATE",
                (draft_id, workspace_id)).fetchone()
            if draft is None:
                return None
            payload = dict(draft["payload_json"])
            operation = payload.get("operation")
            if operation not in LOCAL_PHOTO_OPERATIONS:
                raise ValueError("This operation requires an AI Photo Engine; local processing supports ENHANCE and LIGHTING only")
            if int(payload.get("output_count", 1)) != 1:
                raise ValueError("Local processing supports exactly one output per run")
            if payload.get("mask_asset_id") or payload.get("reference_asset_ids"):
                raise ValueError("Local processing does not consume mask or reference images")
            if payload.get("target_style") or payload.get("prompt"):
                raise ValueError("Local processing does not interpret style notes or natural-language prompts")
            snap = None
            if payload.get("source_version_id"):
                snap = conn.execute(
                    """SELECT v.version_id,v.checksum_sha256 FROM assets a
                       JOIN asset_versions v ON v.asset_id=a.asset_id AND v.workspace_id=a.workspace_id
                       WHERE a.asset_id=%s AND a.workspace_id=%s AND a.deleted_at IS NULL AND v.version_id=%s""",
                    (payload["source_asset_id"], workspace_id, payload["source_version_id"])).fetchone()
            else:
                vid, csum = self._snapshot_source(conn, workspace_id, payload["source_asset_id"])
                payload["source_version_id"], payload["source_checksum_sha256"] = vid, csum
                conn.execute("UPDATE photo_drafts SET payload_json=%s, updated_at=%s WHERE draft_id=%s",
                             (self._jsonb(payload), now_dt, draft_id))
                self._event(conn, draft_id, workspace_id, actor_id, "photo.source_version_snapshotted",
                            {"source_version_id": vid, "source_checksum_sha256": csum})
                snap = {"version_id": vid, "checksum_sha256": csum}
            if snap is None or str(snap["checksum_sha256"]) != payload.get("source_checksum_sha256"):
                raise ValueError("Photo Draft source AssetVersion snapshot is missing or no longer matches its checksum")
            fingerprint = hashlib.sha256(json.dumps({"payload": payload, "processor": LOCAL_PHOTO_PROCESSOR_VERSION},
                                                      sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            existing = conn.execute(
                "SELECT * FROM photo_processing_runs WHERE workspace_id=%s AND idempotency_key=%s FOR UPDATE",
                (workspace_id, idempotency_key)).fetchone()
            if existing:
                if existing["payload_hash"] != fingerprint or existing["draft_id"] != draft_id:
                    raise ValueError("Idempotency-Key was already used with a different Photo Draft or input")
                if existing["status"] == "succeeded":
                    return {"already_succeeded": True, "run": self._run_public(existing), "payload": payload}
                if existing["status"] == "processing" and existing["lease_expires_at"] and existing["lease_expires_at"] > now_dt:
                    raise ValueError("This Photo processing run is already in progress")
                conn.execute(
                    """UPDATE photo_processing_runs SET status='processing',attempts=attempts+1,claimed_by=%s,
                       lease_expires_at=%s,error_message=NULL,updated_at=%s WHERE run_id=%s""",
                    (token, lease, now_dt, existing["run_id"]))
                self._run_event(conn, existing, actor_id,
                                "photo.local_run_reclaimed" if existing["status"] == "processing" else "photo.local_run_retried",
                                {"attempt": int(existing["attempts"]) + 1})
                run_id = existing["run_id"]
            else:
                run_id = "phr_" + uuid.uuid4().hex
                conn.execute(
                    """INSERT INTO photo_processing_runs(run_id,draft_id,workspace_id,created_by,idempotency_key,payload_hash,
                       processor_version,operation,source_version_id,source_checksum_sha256,status,attempts,claimed_by,
                       lease_expires_at,created_at,updated_at) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'processing',1,%s,%s,%s,%s)""",
                    (run_id, draft_id, workspace_id, actor_id, idempotency_key, fingerprint, LOCAL_PHOTO_PROCESSOR_VERSION,
                     operation, payload["source_version_id"], payload["source_checksum_sha256"], token, lease, now_dt, now_dt))
                self._run_event(conn, {"run_id": run_id, "draft_id": draft_id, "workspace_id": workspace_id}, actor_id,
                                "photo.local_run_started",
                                {"operation": operation, "processor_version": LOCAL_PHOTO_PROCESSOR_VERSION})
            return {"already_succeeded": False, "run_id": run_id, "claim_token": token, "payload": payload}

    def complete_local_run(self, run_id: str, claim_token: str, actor_id: str, *, asset_id: str,
                           version_id: str, checksum: str, quality: dict[str, Any]) -> bool:
        now = self._now()
        with connect() as conn:
            row = conn.execute(
                """SELECT * FROM photo_processing_runs WHERE run_id=%s AND status='processing' AND claimed_by=%s
                   AND lease_expires_at>%s FOR UPDATE""", (run_id, claim_token, now)).fetchone()
            if row is None:
                return False
            conn.execute(
                """UPDATE photo_processing_runs SET status='succeeded',output_asset_id=%s,output_version_id=%s,
                   output_checksum_sha256=%s,quality_json=%s,claimed_by=NULL,lease_expires_at=NULL,error_message=NULL,
                   updated_at=%s WHERE run_id=%s""",
                (asset_id, version_id, checksum, self._jsonb(quality), now, run_id))
            self._run_event(conn, row, actor_id, "photo.local_run_succeeded",
                            {"output_asset_id": asset_id, "output_version_id": version_id, "checksum_sha256": checksum})
            return True

    def fail_local_run(self, run_id: str, claim_token: str, actor_id: str, error: str) -> bool:
        now = self._now()
        with connect() as conn:
            row = conn.execute(
                "SELECT * FROM photo_processing_runs WHERE run_id=%s AND status='processing' AND claimed_by=%s FOR UPDATE",
                (run_id, claim_token)).fetchone()
            if row is None:
                return False
            conn.execute(
                """UPDATE photo_processing_runs SET status='failed',error_message=%s,claimed_by=NULL,lease_expires_at=NULL,
                   updated_at=%s WHERE run_id=%s""", (error[:500], now, run_id))
            self._run_event(conn, row, actor_id, "photo.local_run_failed", {"error": error[:500]})
            return True

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with connect() as conn:
            row = conn.execute("SELECT * FROM photo_processing_runs WHERE run_id=%s", (run_id,)).fetchone()
            return self._run_public(row) if row else None

    def list_processing_runs(self, draft_id: str, workspace_id: str, actor_id: str, *,
                             limit: int = 50, offset: int = 0) -> dict[str, Any]:
        self._page(limit, offset, 100)
        with connect() as conn:
            self._require(conn, workspace_id, actor_id, write=False)
            total = int(conn.execute("SELECT COUNT(*) AS n FROM photo_processing_runs WHERE draft_id=%s AND workspace_id=%s",
                                     (draft_id, workspace_id)).fetchone()["n"])
            rows = conn.execute(
                """SELECT r.*,
                   (SELECT e.decision FROM photo_output_review_events e WHERE e.run_id=r.run_id
                    ORDER BY e.seq DESC LIMIT 1) AS review_status
                   FROM photo_processing_runs r WHERE r.draft_id=%s AND r.workspace_id=%s
                   ORDER BY r.created_at DESC, r.run_id DESC LIMIT %s OFFSET %s""", (draft_id, workspace_id, limit, offset)).fetchall()
            return {"items": [self._run_public(r) for r in rows], "total": total, "limit": limit, "offset": offset}

    def list_processing_events(self, run_id: str, draft_id: str, workspace_id: str, actor_id: str, *,
                               limit: int = 100, offset: int = 0) -> dict[str, Any]:
        self._page(limit, offset, 500)
        with connect() as conn:
            self._require(conn, workspace_id, actor_id, write=False)
            total = int(conn.execute(
                "SELECT COUNT(*) AS n FROM photo_processing_events WHERE run_id=%s AND draft_id=%s AND workspace_id=%s",
                (run_id, draft_id, workspace_id)).fetchone()["n"])
            rows = conn.execute(
                """SELECT event_id,run_id,draft_id,actor_id,event_type,details_json,created_at FROM photo_processing_events
                   WHERE run_id=%s AND draft_id=%s AND workspace_id=%s ORDER BY created_at DESC, event_id DESC LIMIT %s OFFSET %s""",
                (run_id, draft_id, workspace_id, limit, offset)).fetchall()
            items = []
            for r in rows:
                v = dict(r); v["details"] = v.pop("details_json"); items.append(v)
            return {"items": items, "total": total, "limit": limit, "offset": offset}

    # ---- output review / export (legacy-contract operations) -------------
    REVIEW_ROLES = {"owner", "admin"}

    @classmethod
    def _require_roles(cls, conn: Any, workspace_id: str, actor_id: str, roles: set[str]) -> None:
        row = conn.execute("SELECT role FROM workspace_members WHERE workspace_id=%s AND user_id=%s",
                           (workspace_id, actor_id)).fetchone()
        if row is None:
            raise NotAMemberError("User is not a member of this workspace")
        if str(row["role"]) not in roles:
            raise InsufficientRoleError("Workspace role cannot review photo outputs")

    def check_access(self, workspace_id: str, actor_id: str, *, roles: set[str] | None = None, write: bool = False) -> None:
        """Role gate usable before any resource lookup so role-first ordering matches the SQLite port."""
        with connect() as conn:
            if roles is not None:
                self._require_roles(conn, workspace_id, actor_id, roles)
            else:
                self._require(conn, workspace_id, actor_id, write=write)

    @staticmethod
    def _iso(value: Any) -> Any:
        return value.astimezone(timezone.utc).isoformat() if isinstance(value, datetime) else value

    @staticmethod
    def _output_base(conn: Any, draft_id: str, run_id: str, workspace_id: str) -> dict[str, Any] | None:
        row = conn.execute(
            """SELECT r.run_id,r.draft_id,r.workspace_id,r.status AS run_status,
               r.operation,r.processor_version,r.source_version_id,r.source_checksum_sha256,
               r.output_asset_id,r.output_version_id,r.output_checksum_sha256,
               r.created_at,r.updated_at,a.asset_id AS active_asset_id,
               v.version_id AS verified_version_id,v.checksum_sha256 AS version_checksum,
               v.storage_key AS version_storage_key,v.size_bytes AS version_size_bytes,v.media_type AS version_media_type,
               (SELECT p.provenance_id FROM asset_provenance p WHERE p.asset_id=a.asset_id
                AND p.event_type='asset.photo_processed' ORDER BY p.created_at DESC,p.provenance_id DESC LIMIT 1) AS provenance_id
               FROM photo_processing_runs r LEFT JOIN assets a ON a.asset_id=r.output_asset_id
                   AND a.workspace_id=r.workspace_id AND a.deleted_at IS NULL
               LEFT JOIN asset_versions v ON v.asset_id=a.asset_id AND v.workspace_id=r.workspace_id
                   AND v.version_id=r.output_version_id
               WHERE r.draft_id=%s AND r.run_id=%s AND r.workspace_id=%s""",
            (draft_id, run_id, workspace_id)).fetchone()
        return dict(row) if row else None

    @classmethod
    def _review_view(cls, conn: Any, base: dict[str, Any], verify: Any) -> dict[str, Any]:
        rows = conn.execute(
            "SELECT * FROM photo_output_review_events WHERE run_id=%s AND draft_id=%s AND workspace_id=%s ORDER BY seq DESC",
            (base["run_id"], base["draft_id"], base["workspace_id"])).fetchall()
        keys = ("event_id", "run_id", "draft_id", "actor_id", "decision", "comment", "asset_id",
                "asset_version_id", "provenance_id", "checksum_sha256", "created_at")
        events = [{k: r[k] for k in keys} for r in rows]
        if base["run_status"] != "succeeded":
            status = base["run_status"]
        elif not verify(base):
            status = "output_integrity_error"
        else:
            status = events[0]["decision"] if events else "pending_review"
        return {"run_id": base["run_id"], "status": status,
                "output": {"asset_id": base["output_asset_id"], "asset_version_id": base["verified_version_id"],
                           "provenance_id": base["provenance_id"], "checksum_sha256": base["version_checksum"],
                           "media_type": base["version_media_type"], "size_bytes": base["version_size_bytes"]},
                "events": events}

    def output_review(self, draft_id: str, run_id: str, workspace_id: str, actor_id: str, verify: Any) -> dict[str, Any] | None:
        with connect() as conn:
            self._require(conn, workspace_id, actor_id, write=False)
            base = self._output_base(conn, draft_id, run_id, workspace_id)
            return None if base is None else self._review_view(conn, base, verify)

    def decide_output_review(self, draft_id: str, run_id: str, workspace_id: str, actor_id: str,
                             decision: str, comment: str, verify: Any) -> dict[str, Any] | None:
        if decision not in {"approved", "changes_requested", "rejected"}:
            raise RepositoryConflictError("Unsupported Photo output review decision")
        clean = (comment or "").strip()
        if decision in {"changes_requested", "rejected"} and not clean:
            raise RepositoryConflictError("A non-empty comment is required for this review decision")
        with connect() as conn:
            self._require_roles(conn, workspace_id, actor_id, self.REVIEW_ROLES)
            locked = conn.execute(
                "SELECT run_id FROM photo_processing_runs WHERE run_id=%s AND draft_id=%s AND workspace_id=%s FOR UPDATE",
                (run_id, draft_id, workspace_id)).fetchone()
            if locked is None:
                return None
            base = self._output_base(conn, draft_id, run_id, workspace_id)
            if base["run_status"] != "succeeded":
                raise RepositoryConflictError("Only succeeded Photo runs can be reviewed")
            if not verify(base):
                raise RepositoryConflictError("Photo output AssetVersion or provenance failed integrity checks")
            latest = self._latest_review(conn, run_id, workspace_id)
            if latest and latest["decision"] in {"approved", "rejected"}:
                raise RepositoryConflictError("Approved or rejected Photo outputs are terminal")
            if latest and latest["decision"] == decision:
                raise RepositoryConflictError("The requested Photo review decision is already current")
            conn.execute(
                """INSERT INTO photo_output_review_events(event_id,run_id,draft_id,workspace_id,actor_id,decision,comment,
                   asset_id,asset_version_id,provenance_id,checksum_sha256,created_at)
                   VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                ("phrev_" + uuid.uuid4().hex, run_id, draft_id, workspace_id, actor_id, decision, clean,
                 base["output_asset_id"], base["verified_version_id"], base["provenance_id"],
                 base["version_checksum"], self._now()))
            return self._review_view(conn, base, verify)

    def create_export_manifest(self, draft_id: str, run_id: str, workspace_id: str, actor_id: str,
                               verify: Any) -> dict[str, Any] | None:
        with connect() as conn:
            self._require(conn, workspace_id, actor_id, write=True)
            locked = conn.execute(
                "SELECT run_id FROM photo_processing_runs WHERE run_id=%s AND draft_id=%s AND workspace_id=%s FOR UPDATE",
                (run_id, draft_id, workspace_id)).fetchone()
            if locked is None:
                return None
            base = self._output_base(conn, draft_id, run_id, workspace_id)
            if base["run_status"] != "succeeded":
                raise RepositoryConflictError("Only succeeded Photo runs can be exported")
            if not verify(base):
                raise RepositoryConflictError("Photo output AssetVersion or provenance failed integrity checks")
            latest = self._latest_review(conn, run_id, workspace_id)
            if not latest or latest["decision"] != "approved":
                raise RepositoryConflictError("Photo output must be individually approved before export")
            if (latest["asset_id"] != base["output_asset_id"]
                    or latest["asset_version_id"] != base["verified_version_id"]
                    or latest["provenance_id"] != base["provenance_id"]
                    or latest["checksum_sha256"] != base["version_checksum"]):
                raise RepositoryConflictError("Approved review snapshot no longer matches the immutable Photo output")
            manifest = {
                "manifest_type": "AI_CREATOR_STUDIO_INTERNAL_PHOTO_OUTPUT_MANIFEST",
                "manifest_version": 1,
                "draft_id": draft_id,
                "run": {"run_id": run_id, "operation": base["operation"],
                        "processor_version": base["processor_version"], "created_at": self._iso(base["created_at"]),
                        "source_version_id": base["source_version_id"],
                        "source_checksum_sha256": base["source_checksum_sha256"]},
                "output": {"asset_id": base["output_asset_id"], "asset_version_id": base["verified_version_id"],
                           "provenance_id": base["provenance_id"], "checksum_sha256": base["version_checksum"],
                           "media_type": base["version_media_type"], "size_bytes": base["version_size_bytes"],
                           "review_status": "approved", "approved_by": latest["actor_id"],
                           "reviewed_at": self._iso(latest["created_at"])},
                "is_ai_generated": False,
                "publication_authorized": False,
                "commercial_rights_verified": False,
                "binary_files_included": False,
                "notice": "Internal metadata manifest only. No public distribution or commercial-use rights are granted.",
            }
            canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
            now = self._now()
            conn.execute(
                """INSERT INTO photo_output_export_events(event_id,run_id,draft_id,workspace_id,actor_id,manifest_sha256,created_at)
                   VALUES(%s,%s,%s,%s,%s,%s,%s)""",
                ("phexp_" + uuid.uuid4().hex, run_id, draft_id, workspace_id, actor_id, digest, now))
            return {"manifest": manifest, "manifest_sha256": digest, "exported_at": now.isoformat()}

    # ---- output review / export audit ---------------------------------
    def latest_output_review(self, run_id: str, workspace_id: str) -> dict[str, Any] | None:
        """Latest immutable review decision for a succeeded run (no role check; used by Lookbook)."""
        with connect() as conn:
            return self._latest_review(conn, run_id, workspace_id)

    @staticmethod
    def _latest_review(conn: Any, run_id: str, workspace_id: str) -> dict[str, Any] | None:
        row = conn.execute(
            "SELECT * FROM photo_output_review_events WHERE run_id=%s AND workspace_id=%s ORDER BY seq DESC LIMIT 1",
            (run_id, workspace_id)).fetchone()
        return dict(row) if row else None

    def record_output_review(self, draft_id: str, run_id: str, workspace_id: str, actor_id: str, *,
                             decision: str, comment: str = "", asset_id: str, asset_version_id: str,
                             provenance_id: str, checksum_sha256: str) -> dict[str, Any]:
        if decision not in {"approved", "changes_requested", "rejected"}:
            raise ValueError("Unsupported Photo output review decision")
        comment = (comment or "").strip()
        if decision != "approved" and not comment:
            raise ValueError("A comment is required unless approving")
        with connect() as conn:
            self._require(conn, workspace_id, actor_id, write=True)
            run = conn.execute(
                """SELECT * FROM photo_processing_runs WHERE run_id=%s AND draft_id=%s AND workspace_id=%s
                   AND status='succeeded' FOR UPDATE""", (run_id, draft_id, workspace_id)).fetchone()
            if run is None:
                raise LookupError("Succeeded Photo run not found")
            if (run["output_asset_id"], run["output_version_id"], run["output_checksum_sha256"]) != (
                    asset_id, asset_version_id, checksum_sha256):
                raise ValueError("Review snapshot does not match the run output")
            event_id = "phrev_" + uuid.uuid4().hex
            conn.execute(
                """INSERT INTO photo_output_review_events(event_id,run_id,draft_id,workspace_id,actor_id,decision,comment,
                   asset_id,asset_version_id,provenance_id,checksum_sha256,created_at)
                   VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (event_id, run_id, draft_id, workspace_id, actor_id, decision, comment, asset_id, asset_version_id,
                 provenance_id, checksum_sha256, self._now()))
            return self._latest_review(conn, run_id, workspace_id)

    def record_output_export(self, draft_id: str, run_id: str, workspace_id: str, actor_id: str,
                             manifest_sha256: str) -> str:
        with connect() as conn:
            self._require(conn, workspace_id, actor_id, write=True)
            latest = self._latest_review(conn, run_id, workspace_id)
            if latest is None or latest["decision"] != "approved":
                raise ValueError("Only approved Photo outputs can be exported")
            event_id = "phexp_" + uuid.uuid4().hex
            conn.execute(
                """INSERT INTO photo_output_export_events(event_id,run_id,draft_id,workspace_id,actor_id,manifest_sha256,created_at)
                   VALUES(%s,%s,%s,%s,%s,%s,%s)""",
                (event_id, run_id, draft_id, workspace_id, actor_id, manifest_sha256, self._now()))
            return event_id
