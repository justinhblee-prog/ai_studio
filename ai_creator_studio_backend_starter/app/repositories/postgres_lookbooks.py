"""PostgreSQL Lookbook Draft aggregate repository; not runtime-selected yet.

Persistence, workflow transitions and DB-verifiable integrity checks only.
Reading/hashing immutable AssetVersion files and package building stay in the adapter.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from app.postgres import apply_migrations, connect
from app.repo_errors import DetailedValueError, InsufficientRoleError, NotAMemberError, RepositoryConflictError


class LookbookStateError(RepositoryConflictError):
    """Operation is not allowed in the current workflow state (maps to HTTP 409)."""


class PostgreSQLLookbookRepository:
    backend = "postgresql"
    WRITABLE_ROLES = {"owner", "admin", "editor"}
    REVIEWER_ROLES = {"owner", "admin"}
    READABLE_ROLES = WRITABLE_ROLES | {"viewer"}
    EDITABLE_STATES = {"DRAFT", "CHANGES_REQUESTED"}

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
    def _require(cls, conn: Any, workspace_id: str, actor_id: str, allowed: set[str]) -> None:
        row = conn.execute("SELECT role FROM workspace_members WHERE workspace_id=%s AND user_id=%s",
                           (workspace_id, actor_id)).fetchone()
        if row is None:
            raise NotAMemberError("User is not a member of this workspace")
        if str(row["role"]) not in allowed:
            raise InsufficientRoleError("Workspace role is not permitted for this Lookbook operation")

    @staticmethod
    def _public(row: Any) -> dict[str, Any]:
        value = dict(row)
        value["input"] = value.pop("payload_json")
        value["status"] = "archived" if value["archived_at"] else "draft"
        value["workflow_status"] = str(value["workflow_status"]).lower()
        return value

    @classmethod
    def _event(cls, conn: Any, draft_id: str, workspace_id: str, actor_id: str, event_type: str,
               details: dict[str, Any] | None = None) -> None:
        conn.execute(
            """INSERT INTO lookbook_draft_events(event_id,draft_id,workspace_id,actor_id,event_type,details_json,created_at)
               VALUES(%s,%s,%s,%s,%s,%s,%s)""",
            ("lbe_" + uuid.uuid4().hex, draft_id, workspace_id, actor_id, event_type, cls._jsonb(details or {}), cls._now()))

    @staticmethod
    def _page(limit: int, offset: int, maximum: int) -> None:
        if not 1 <= limit <= maximum or offset < 0:
            raise ValueError("Pagination is outside the allowed range")

    @staticmethod
    def _active_draft(conn: Any, draft_id: str, workspace_id: str, *, lock: bool = False):
        row = conn.execute(
            "SELECT * FROM lookbook_drafts WHERE draft_id=%s AND workspace_id=%s AND archived_at IS NULL"
            + (" FOR UPDATE" if lock else ""), (draft_id, workspace_id)).fetchone()
        if row is None:
            raise LookupError("Lookbook Draft not found")
        return row

    @staticmethod
    def _validate_input(p: dict[str, Any]) -> None:
        title = p.get("title")
        if not isinstance(title, str) or not 1 <= len(title.strip()) <= 120:
            raise ValueError("title must contain 1 to 120 characters")
        lists = {"product_ids": 20, "product_variant_ids": 40, "product_asset_ids": 20}
        for key, maximum in lists.items():
            value = p.get(key) or []
            if (not isinstance(value, list) or len(value) > maximum or len(value) != len(set(value))
                    or any(not isinstance(v, str) or not v.strip() or len(v) > 80 for v in value)):
                raise ValueError(f"{key} must be at most {maximum} unique non-empty identifiers")
        if not (p.get("product_ids") or p.get("product_variant_ids") or p.get("product_asset_ids")):
            raise ValueError("At least one catalog product, product variant or direct product image is required")
        ids = list(p.get("product_asset_ids") or []) + ([p["person_asset_id"]] if p.get("person_asset_id") else [])
        if len(ids) != len(set(ids)):
            raise ValueError("Product, variant and person references must be unique")
        count = p.get("output_count", 1)
        if not isinstance(count, int) or not 1 <= count <= 20:
            raise ValueError("output_count must be between 1 and 20")

    def _resolve_references(self, conn: Any, workspace_id: str, p: dict[str, Any]) -> tuple[list[tuple[str, str]], list[str]]:
        roles = [(a, "product") for a in p.get("product_asset_ids") or []]
        if p.get("person_asset_id"):
            roles.append((p["person_asset_id"], "person"))
        image_ids: list[str] = []
        parents: list[str] = list(p.get("product_ids") or [])
        for pid in p.get("product_ids") or []:
            if conn.execute("SELECT 1 FROM products WHERE product_id=%s AND workspace_id=%s AND status='ACTIVE' FOR SHARE",
                            (pid, workspace_id)).fetchone() is None:
                raise ValueError("Every catalog product must be active in this workspace")
            imgs = conn.execute(
                """SELECT pa.asset_id FROM product_assets pa JOIN assets a ON a.asset_id=pa.asset_id
                   WHERE pa.product_id=%s AND a.workspace_id=%s AND a.deleted_at IS NULL ORDER BY pa.sort_order""",
                (pid, workspace_id)).fetchall()
            if not imgs:
                raise ValueError("Every catalog product must have at least one active image")
            image_ids.extend(str(i["asset_id"]) for i in imgs)
        for vid in p.get("product_variant_ids") or []:
            v = conn.execute(
                """SELECT pv.product_id FROM product_variants pv JOIN products pr ON pr.product_id=pv.product_id
                   WHERE pv.variant_id=%s AND pv.workspace_id=%s AND pv.status='ACTIVE' AND pr.status='ACTIVE'
                   FOR SHARE OF pv, pr""",
                (vid, workspace_id)).fetchone()
            if v is None:
                raise ValueError("Every selected Product Variant must be active in this workspace")
            parents.append(str(v["product_id"]))
            imgs = conn.execute(
                """SELECT pva.asset_id FROM product_variant_assets pva JOIN assets a ON a.asset_id=pva.asset_id
                   WHERE pva.variant_id=%s AND a.workspace_id=%s AND a.deleted_at IS NULL ORDER BY pva.sort_order""",
                (vid, workspace_id)).fetchall()
            if not imgs:
                imgs = conn.execute(
                    """SELECT pa.asset_id FROM product_assets pa JOIN assets a ON a.asset_id=pa.asset_id
                       WHERE pa.product_id=%s AND a.workspace_id=%s AND a.deleted_at IS NULL ORDER BY pa.sort_order""",
                    (v["product_id"], workspace_id)).fetchall()
                if not imgs:
                    raise ValueError("A selected Variant must have active variant or parent Product images")
            image_ids.extend(str(i["asset_id"]) for i in imgs)
        if p.get("person_asset_id") and p["person_asset_id"] in image_ids:
            raise ValueError("Person image cannot also be a product catalog image")
        seen = {a for a, _ in roles}
        for a in image_ids:
            if a not in seen:
                roles.append((a, "product")); seen.add(a)
        asset_ids = [a for a, _ in roles]
        rows = conn.execute(
            """SELECT asset_id FROM assets WHERE workspace_id=%s AND deleted_at IS NULL
               AND media_type LIKE 'image/%%' AND asset_id = ANY(%s) ORDER BY asset_id FOR SHARE""", (workspace_id, asset_ids)).fetchall()
        if len(rows) != len(set(asset_ids)):
            raise DetailedValueError({"code": "LOOKBOOK_IMAGE_ASSET_REQUIRED",
                "message": "All product/person references must be active image assets in this workspace."})
        if p.get("project_id"):
            proj = conn.execute("SELECT status FROM projects WHERE project_id=%s AND workspace_id=%s FOR SHARE",
                                (p["project_id"], workspace_id)).fetchone()
            if proj is None:
                raise ValueError("Project must belong to this workspace")
            if proj["status"] != "ACTIVE":
                raise LookbookStateError("Lookbook Draft requires an ACTIVE Project")
        if p.get("character_id") and conn.execute(
                "SELECT 1 FROM characters WHERE character_id=%s AND workspace_id=%s AND deleted_at IS NULL FOR SHARE",
                (p["character_id"], workspace_id)).fetchone() is None:
            raise ValueError("Character must be active in this workspace")
        return roles, list(dict.fromkeys(parents))

    @staticmethod
    def _write_links(conn: Any, draft_id: str, p: dict[str, Any], roles: list[tuple[str, str]], parents: list[str]) -> None:
        conn.execute("DELETE FROM lookbook_draft_assets WHERE draft_id=%s", (draft_id,))
        conn.execute("DELETE FROM lookbook_draft_entities WHERE draft_id=%s", (draft_id,))
        conn.cursor().executemany("INSERT INTO lookbook_draft_assets(draft_id,asset_id,role) VALUES(%s,%s,%s)",
                                  [(draft_id, a, r) for a, r in roles])
        entities: list[tuple[str, str, str]] = []
        if p.get("project_id"):
            entities.append((draft_id, "project", p["project_id"]))
        if p.get("character_id"):
            entities.append((draft_id, "character", p["character_id"]))
        entities.extend((draft_id, "product", x) for x in parents)
        entities.extend((draft_id, "product_variant", x) for x in p.get("product_variant_ids") or [])
        conn.cursor().executemany("INSERT INTO lookbook_draft_entities(draft_id,entity_type,entity_id) VALUES(%s,%s,%s)",
                                  list(dict.fromkeys(entities)))

    @staticmethod
    def _summary(p: dict[str, Any]) -> dict[str, Any]:
        return {"catalog_product_count": len(p.get("product_ids") or []),
                "variant_count": len(p.get("product_variant_ids") or []),
                "direct_image_count": len(p.get("product_asset_ids") or []),
                "has_person": bool(p.get("person_asset_id"))}

    # ---- drafts --------------------------------------------------------
    def create_draft(self, workspace_id: str, actor_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        p = {k: v for k, v in payload.items() if k != "workspace_id"}
        self._validate_input(p)
        draft_id, now = "lbd_" + uuid.uuid4().hex, self._now()
        with connect() as conn:
            self._require(conn, workspace_id, actor_id, self.WRITABLE_ROLES)
            roles, parents = self._resolve_references(conn, workspace_id, p)
            conn.execute(
                "INSERT INTO lookbook_drafts(draft_id,workspace_id,created_by,payload_json,created_at,updated_at) VALUES(%s,%s,%s,%s,%s,%s)",
                (draft_id, workspace_id, actor_id, self._jsonb(p), now, now))
            self._write_links(conn, draft_id, p, roles, parents)
            self._event(conn, draft_id, workspace_id, actor_id, "lookbook.draft_created", self._summary(p))
            return self._public(conn.execute("SELECT * FROM lookbook_drafts WHERE draft_id=%s", (draft_id,)).fetchone())

    def list_drafts(self, workspace_id: str, actor_id: str, include_archived: bool = False, *,
                    limit: int = 50, offset: int = 0) -> dict[str, Any]:
        self._page(limit, offset, 100)
        where = "workspace_id=%s" + ("" if include_archived else " AND archived_at IS NULL")
        with connect() as conn:
            self._require(conn, workspace_id, actor_id, self.READABLE_ROLES)
            total = int(conn.execute(f"SELECT COUNT(*) AS n FROM lookbook_drafts WHERE {where}", (workspace_id,)).fetchone()["n"])
            rows = conn.execute(f"SELECT * FROM lookbook_drafts WHERE {where} ORDER BY updated_at DESC, draft_id LIMIT %s OFFSET %s",
                                (workspace_id, limit, offset)).fetchall()
            return {"items": [self._public(r) for r in rows], "total": total, "limit": limit, "offset": offset}

    def get_draft(self, draft_id: str, workspace_id: str, actor_id: str) -> dict[str, Any] | None:
        with connect() as conn:
            self._require(conn, workspace_id, actor_id, self.READABLE_ROLES)
            row = conn.execute("SELECT * FROM lookbook_drafts WHERE draft_id=%s AND workspace_id=%s",
                               (draft_id, workspace_id)).fetchone()
            return self._public(row) if row else None

    def update_draft(self, draft_id: str, workspace_id: str, actor_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        if payload.get("workspace_id", workspace_id) != workspace_id:
            raise ValueError("workspace_id cannot be changed")
        p = {k: v for k, v in payload.items() if k != "workspace_id"}
        self._validate_input(p)
        with connect() as conn:
            self._require(conn, workspace_id, actor_id, self.WRITABLE_ROLES)
            row = self._active_draft(conn, draft_id, workspace_id, lock=True)
            if row["workflow_status"] not in self.EDITABLE_STATES:
                raise LookbookStateError("Only DRAFT or CHANGES_REQUESTED Lookbook Drafts can be edited")
            roles, parents = self._resolve_references(conn, workspace_id, p)
            conn.execute("UPDATE lookbook_drafts SET payload_json=%s, updated_at=%s WHERE draft_id=%s",
                         (self._jsonb(p), self._now(), draft_id))
            self._write_links(conn, draft_id, p, roles, parents)
            self._event(conn, draft_id, workspace_id, actor_id, "lookbook.draft_updated", self._summary(p))
            return self._public(conn.execute("SELECT * FROM lookbook_drafts WHERE draft_id=%s", (draft_id,)).fetchone())

    def submit_for_review(self, draft_id: str, workspace_id: str, actor_id: str) -> dict[str, Any]:
        with connect() as conn:
            self._require(conn, workspace_id, actor_id, self.WRITABLE_ROLES)
            row = self._active_draft(conn, draft_id, workspace_id, lock=True)
            if row["workflow_status"] not in self.EDITABLE_STATES:
                raise LookbookStateError("Only DRAFT or CHANGES_REQUESTED drafts can be submitted")
            now = self._now()
            conn.execute(
                """UPDATE lookbook_drafts SET workflow_status='IN_REVIEW',submitted_at=%s,submitted_by=%s,reviewed_at=NULL,
                   reviewed_by=NULL,review_comment=NULL,updated_at=%s WHERE draft_id=%s""", (now, actor_id, now, draft_id))
            self._event(conn, draft_id, workspace_id, actor_id, "lookbook.submitted_for_review",
                        {"previous_status": row["workflow_status"]})
            return self._public(conn.execute("SELECT * FROM lookbook_drafts WHERE draft_id=%s", (draft_id,)).fetchone())

    def decide_review(self, draft_id: str, workspace_id: str, actor_id: str, decision: str,
                      comment: str | None = None) -> dict[str, Any]:
        if decision not in {"APPROVED", "CHANGES_REQUESTED"}:
            raise ValueError("Unsupported review decision")
        if decision == "CHANGES_REQUESTED" and not (comment and comment.strip()):
            raise ValueError("A review comment is required when requesting changes")
        with connect() as conn:
            self._require(conn, workspace_id, actor_id, self.REVIEWER_ROLES)
            row = self._active_draft(conn, draft_id, workspace_id, lock=True)
            if row["workflow_status"] != "IN_REVIEW":
                raise LookbookStateError("Only IN_REVIEW drafts can be approved or returned for changes")
            now = self._now()
            clean = comment.strip() if comment else None
            conn.execute(
                "UPDATE lookbook_drafts SET workflow_status=%s,reviewed_at=%s,reviewed_by=%s,review_comment=%s,updated_at=%s WHERE draft_id=%s",
                (decision, now, actor_id, clean, now, draft_id))
            self._event(conn, draft_id, workspace_id, actor_id,
                        "lookbook.approved" if decision == "APPROVED" else "lookbook.changes_requested", {"comment": clean})
            return self._public(conn.execute("SELECT * FROM lookbook_drafts WHERE draft_id=%s", (draft_id,)).fetchone())

    def archive_draft(self, draft_id: str, workspace_id: str, actor_id: str) -> dict[str, Any]:
        with connect() as conn:
            self._require(conn, workspace_id, actor_id, self.WRITABLE_ROLES)
            self._active_draft(conn, draft_id, workspace_id, lock=True)
            now = self._now()
            conn.execute("UPDATE lookbook_drafts SET archived_at=%s, updated_at=%s WHERE draft_id=%s", (now, now, draft_id))
            self._event(conn, draft_id, workspace_id, actor_id, "lookbook.draft_archived")
            return self._public(conn.execute("SELECT * FROM lookbook_drafts WHERE draft_id=%s", (draft_id,)).fetchone())

    def check_access(self, workspace_id: str, actor_id: str, allowed: set[str]) -> None:
        """Role gate usable before any resource lookup so role-first ordering matches the SQLite port."""
        with connect() as conn:
            self._require(conn, workspace_id, actor_id, allowed)

    def list_events(self, draft_id: str, workspace_id: str, actor_id: str, *, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        self._page(limit, offset, 500)
        with connect() as conn:
            self._require(conn, workspace_id, actor_id, self.READABLE_ROLES)
            total = int(conn.execute("SELECT COUNT(*) AS n FROM lookbook_draft_events WHERE draft_id=%s AND workspace_id=%s",
                                     (draft_id, workspace_id)).fetchone()["n"])
            rows = conn.execute(
                """SELECT event_id,draft_id,actor_id,event_type,details_json,created_at FROM lookbook_draft_events
                   WHERE draft_id=%s AND workspace_id=%s ORDER BY created_at DESC, event_id DESC LIMIT %s OFFSET %s""",
                (draft_id, workspace_id, limit, offset)).fetchall()
            items = []
            for r in rows:
                v = dict(r); v["details"] = v.pop("details_json"); items.append(v)
            return {"items": items, "total": total, "limit": limit, "offset": offset}

    def export_plan_manifest(self, draft_id: str, workspace_id: str, actor_id: str) -> dict[str, Any]:
        with connect() as conn:
            self._require(conn, workspace_id, actor_id, self.READABLE_ROLES)
            row = self._active_draft(conn, draft_id, workspace_id)
            if row["workflow_status"] != "APPROVED":
                raise LookbookStateError("Only approved Lookbook planning drafts can export a manifest")
            assets = conn.execute("SELECT asset_id,role FROM lookbook_draft_assets WHERE draft_id=%s ORDER BY role,asset_id",
                                  (draft_id,)).fetchall()
            return {"manifest_type": "LOOKBOOK_PLAN_ONLY", "generated_outputs_included": False,
                    "draft_id": draft_id, "workspace_id": workspace_id, "workflow_status": row["workflow_status"],
                    "approved_at": row["reviewed_at"], "approved_by": row["reviewed_by"],
                    "input": row["payload_json"], "referenced_assets": [dict(a) for a in assets]}

    # ---- outputs & assembly -------------------------------------------
    @staticmethod
    def _photo_base(conn: Any, run_id: str, workspace_id: str):
        """Output base of a succeeded Photo run (same query the Photo review uses), or None."""
        from app.repositories.postgres_photos import PostgreSQLPhotoRepository
        run = conn.execute("SELECT draft_id FROM photo_processing_runs WHERE run_id=%s AND workspace_id=%s AND status='succeeded'",
                           (run_id, workspace_id)).fetchone()
        return PostgreSQLPhotoRepository._output_base(conn, run["draft_id"], run_id, workspace_id) if run else None

    @staticmethod
    def _iso(value: Any) -> Any:
        return value.astimezone(timezone.utc).isoformat() if isinstance(value, datetime) else value

    @staticmethod
    def _latest_assembly(conn: Any, draft_id: str):
        return conn.execute(
            "SELECT * FROM lookbook_output_assembly_review_events WHERE draft_id=%s ORDER BY seq DESC LIMIT 1",
            (draft_id,)).fetchone()

    def list_outputs(self, draft_id: str, workspace_id: str, actor_id: str) -> dict[str, Any]:
        with connect() as conn:
            self._require(conn, workspace_id, actor_id, self.READABLE_ROLES)
            self._active_draft(conn, draft_id, workspace_id)
            rows = conn.execute(
                "SELECT * FROM lookbook_output_assets WHERE draft_id=%s AND workspace_id=%s ORDER BY page_order, output_item_id",
                (draft_id, workspace_id)).fetchall()
            items = []
            for r in rows:
                v = dict(r); v["variant_options"] = v.pop("variant_options_json"); items.append(v)
            return {"items": items, "total": len(items)}

    def attach_approved_photo_output(self, draft_id: str, workspace_id: str, actor_id: str, *, photo_run_id: str,
                                     page_order: int, product_id: str | None = None,
                                     product_variant_id: str | None = None, caption: str | None = None,
                                     verify: Any) -> dict[str, Any]:
        """Attach an individually approved Photo output; ``verify`` re-checks the output file bytes."""
        if not isinstance(page_order, int) or not 1 <= page_order <= 100:
            raise ValueError("page_order must be between 1 and 100")
        if caption is not None and len(caption) > 240:
            raise ValueError("caption exceeds 240 characters")
        with connect() as conn:
            self._require(conn, workspace_id, actor_id, self.WRITABLE_ROLES)
            base = self._photo_base(conn, photo_run_id, workspace_id)
            first = conn.execute(
                "SELECT * FROM photo_output_review_events WHERE run_id=%s AND workspace_id=%s ORDER BY seq DESC LIMIT 1",
                (photo_run_id, workspace_id)).fetchone()
            if base is None or not verify(base) or first is None or first["decision"] != "approved":
                raise LookbookStateError("Only individually approved Photo outputs can be attached to a Lookbook")
            draft = self._active_draft(conn, draft_id, workspace_id, lock=True)
            if draft["workflow_status"] != "APPROVED":
                raise LookbookStateError("Lookbook planning draft must be approved before output assembly")
            if self._latest_assembly(conn, draft_id) is not None:
                raise LookbookStateError("Lookbook output assembly is frozen after review submission; create a new draft to change it")
            run = conn.execute("SELECT * FROM photo_processing_runs WHERE run_id=%s AND workspace_id=%s AND status='succeeded'",
                               (photo_run_id, workspace_id)).fetchone()
            latest = conn.execute(
                "SELECT * FROM photo_output_review_events WHERE run_id=%s AND workspace_id=%s ORDER BY seq DESC LIMIT 1",
                (photo_run_id, workspace_id)).fetchone()
            if (run is None or latest is None or latest["decision"] != "approved"
                    or latest["asset_id"] != run["output_asset_id"]
                    or latest["asset_version_id"] != run["output_version_id"]
                    or latest["provenance_id"] != base["provenance_id"]
                    or latest["checksum_sha256"] != run["output_checksum_sha256"]):
                raise LookbookStateError("Photo output approval snapshot is missing or no longer matches its immutable version")
            product_sku = variant_sku = None
            options: dict[str, Any] = {}
            if product_variant_id:
                v = conn.execute(
                    """SELECT v.product_id,v.sku AS variant_sku,v.option_values,p.sku AS product_sku FROM product_variants v
                       JOIN products p ON p.product_id=v.product_id
                       WHERE v.variant_id=%s AND v.workspace_id=%s AND v.status='ACTIVE' AND p.status='ACTIVE'""",
                    (product_variant_id, workspace_id)).fetchone()
                if v is None:
                    raise LookbookStateError("Selected Product Variant is not active in this workspace")
                if product_id and product_id != v["product_id"]:
                    raise LookbookStateError("Product ID does not match the selected Product Variant")
                product_id, product_sku, variant_sku, options = v["product_id"], v["product_sku"], v["variant_sku"], v["option_values"]
                if conn.execute(
                        """SELECT 1 FROM lookbook_draft_entities WHERE draft_id=%s AND
                           ((entity_type='product_variant' AND entity_id=%s) OR (entity_type='product' AND entity_id=%s)) LIMIT 1""",
                        (draft_id, product_variant_id, product_id)).fetchone() is None:
                    raise LookbookStateError("Selected Product Variant is not referenced by the approved Lookbook plan")
            elif product_id:
                pr = conn.execute("SELECT sku FROM products WHERE product_id=%s AND workspace_id=%s AND status='ACTIVE'",
                                  (product_id, workspace_id)).fetchone()
                if pr is None:
                    raise LookbookStateError("Selected Product is not active in this workspace")
                if conn.execute("SELECT 1 FROM lookbook_draft_entities WHERE draft_id=%s AND entity_type='product' AND entity_id=%s",
                                (draft_id, product_id)).fetchone() is None:
                    raise LookbookStateError("Selected Product is not referenced by the approved Lookbook plan")
                product_sku = pr["sku"]
            item_id = "lbo_" + uuid.uuid4().hex
            try:
                conn.execute(
                    """INSERT INTO lookbook_output_assets(output_item_id,draft_id,workspace_id,photo_run_id,asset_id,asset_version_id,
                       provenance_id,checksum_sha256,product_id,product_sku,product_variant_id,variant_sku,variant_options_json,
                       page_order,caption,created_by,created_at) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (item_id, draft_id, workspace_id, photo_run_id, latest["asset_id"], latest["asset_version_id"],
                     latest["provenance_id"], latest["checksum_sha256"], product_id, product_sku, product_variant_id,
                     variant_sku, self._jsonb(options), page_order, caption, actor_id, self._now()))
            except Exception as exc:
                if getattr(exc, "sqlstate", None) == "23505":
                    raise LookbookStateError("Photo output is already attached or page order is in use") from exc
                raise
            self._event(conn, draft_id, workspace_id, actor_id, "lookbook.approved_photo_output_attached",
                        {"output_item_id": item_id, "photo_run_id": photo_run_id, "asset_id": latest["asset_id"],
                         "asset_version_id": latest["asset_version_id"], "product_id": product_id,
                         "product_variant_id": product_variant_id, "page_order": page_order})
            row = conn.execute("SELECT * FROM lookbook_output_assets WHERE output_item_id=%s", (item_id,)).fetchone()
            v = dict(row); v["variant_options"] = v.pop("variant_options_json")
            return v

    def _verified_snapshot(self, conn: Any, draft_id: str, workspace_id: str, verify: Any):
        current = conn.execute(
            "SELECT * FROM lookbook_output_assets WHERE draft_id=%s AND workspace_id=%s ORDER BY page_order, output_item_id",
            (draft_id, workspace_id)).fetchall()
        if not current:
            raise LookbookStateError("Lookbook has no Photo outputs attached")
        snapshot = []
        for item in current:
            run = conn.execute("SELECT * FROM photo_processing_runs WHERE run_id=%s AND workspace_id=%s AND status='succeeded'",
                               (item["photo_run_id"], workspace_id)).fetchone()
            latest = conn.execute(
                "SELECT * FROM photo_output_review_events WHERE run_id=%s AND workspace_id=%s ORDER BY seq DESC LIMIT 1",
                (item["photo_run_id"], workspace_id)).fetchone()
            photo_base = self._photo_base(conn, item["photo_run_id"], workspace_id) if run else None
            if (run is None or photo_base is None or not verify(photo_base) or latest is None or latest["decision"] != "approved"
                    or (latest["asset_id"], latest["asset_version_id"], latest["provenance_id"], latest["checksum_sha256"])
                    != (item["asset_id"], item["asset_version_id"], item["provenance_id"], item["checksum_sha256"])
                    or (run["output_asset_id"], run["output_version_id"], run["output_checksum_sha256"])
                    != (item["asset_id"], item["asset_version_id"], item["checksum_sha256"])):
                raise LookbookStateError("A Lookbook output failed immutable Photo review or file integrity checks")
            snapshot.append({
                "output_item_id": item["output_item_id"], "page_order": item["page_order"],
                "photo_run_id": item["photo_run_id"], "asset_id": item["asset_id"],
                "asset_version_id": item["asset_version_id"], "provenance_id": item["provenance_id"],
                "checksum_sha256": item["checksum_sha256"], "product_id": item["product_id"],
                "product_sku": item["product_sku"], "product_variant_id": item["product_variant_id"],
                "variant_sku": item["variant_sku"], "variant_options": item["variant_options_json"],
                "caption": item["caption"]})
        canonical = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return current, snapshot, hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def get_assembly_review(self, draft_id: str, workspace_id: str, actor_id: str, verify: Any) -> dict[str, Any] | None:
        with connect() as conn:
            self._require(conn, workspace_id, actor_id, self.READABLE_ROLES)
            draft = conn.execute(
                "SELECT workflow_status FROM lookbook_drafts WHERE draft_id=%s AND workspace_id=%s AND archived_at IS NULL",
                (draft_id, workspace_id)).fetchone()
            if draft is None:
                return None
            count = int(conn.execute("SELECT COUNT(*) AS n FROM lookbook_output_assets WHERE draft_id=%s AND workspace_id=%s",
                                     (draft_id, workspace_id)).fetchone()["n"])
            events = [dict(r) for r in conn.execute(
                "SELECT * FROM lookbook_output_assembly_review_events WHERE draft_id=%s AND workspace_id=%s ORDER BY seq DESC",
                (draft_id, workspace_id)).fetchall()]
            latest = events[0] if events else None
            status = (("in_review" if latest["decision"] == "submitted" else latest["decision"]) if latest
                      else ("pending_review" if count else "no_outputs"))
            if count and (latest is None or latest["decision"] in {"submitted", "approved"}):
                try:
                    _, _, current = self._verified_snapshot(conn, draft_id, workspace_id, verify)
                    if latest and current != latest["snapshot_sha256"]:
                        status = "integrity_error"
                except LookbookStateError:
                    status = "integrity_error"
            return {"draft_id": draft_id, "planning_status": draft["workflow_status"], "status": status,
                    "output_count": count, "snapshot_sha256": latest["snapshot_sha256"] if latest else None,
                    "events": events}

    def submit_assembly(self, draft_id: str, workspace_id: str, actor_id: str, verify: Any) -> dict[str, Any] | None:
        with connect() as conn:
            self._require(conn, workspace_id, actor_id, self.WRITABLE_ROLES)
            draft = conn.execute(
                "SELECT * FROM lookbook_drafts WHERE draft_id=%s AND workspace_id=%s AND archived_at IS NULL FOR UPDATE",
                (draft_id, workspace_id)).fetchone()
            if draft is None:
                return None
            if draft["workflow_status"] != "APPROVED":
                raise LookbookStateError("Lookbook planning draft must be approved before assembly review")
            current, _, digest = self._verified_snapshot(conn, draft_id, workspace_id, verify)
            if self._latest_assembly(conn, draft_id) is not None:
                raise LookbookStateError("Lookbook assembly review has already started; create a new draft to change the immutable output sequence")
            conn.execute(
                """INSERT INTO lookbook_output_assembly_review_events(event_id,draft_id,workspace_id,actor_id,decision,comment,
                   snapshot_sha256,output_count,created_at) VALUES(%s,%s,%s,%s,'submitted','',%s,%s,%s)""",
                ("lbasrev_" + uuid.uuid4().hex, draft_id, workspace_id, actor_id, digest, len(current), self._now()))
        return self.get_assembly_review(draft_id, workspace_id, actor_id, verify)

    def decide_assembly(self, draft_id: str, workspace_id: str, actor_id: str, decision: str,
                        comment: str, verify: Any) -> dict[str, Any] | None:
        if decision not in {"approved", "rejected"}:
            raise LookbookStateError("Unsupported Lookbook assembly review decision")
        clean = (comment or "").strip()
        if decision == "rejected" and not clean:
            raise LookbookStateError("A non-empty comment is required when rejecting the Lookbook assembly")
        with connect() as conn:
            self._require(conn, workspace_id, actor_id, self.REVIEWER_ROLES)
            draft = conn.execute(
                "SELECT * FROM lookbook_drafts WHERE draft_id=%s AND workspace_id=%s AND archived_at IS NULL FOR UPDATE",
                (draft_id, workspace_id)).fetchone()
            if draft is None:
                return None
            if draft["workflow_status"] != "APPROVED":
                raise LookbookStateError("Lookbook planning draft is not approved")
            current, _, digest = self._verified_snapshot(conn, draft_id, workspace_id, verify)
            latest = self._latest_assembly(conn, draft_id)
            if latest is None or latest["decision"] != "submitted":
                raise LookbookStateError("Lookbook assembly must be submitted and awaiting review")
            if latest["snapshot_sha256"] != digest or latest["output_count"] != len(current):
                raise LookbookStateError("Lookbook output sequence changed after assembly review submission")
            conn.execute(
                """INSERT INTO lookbook_output_assembly_review_events(event_id,draft_id,workspace_id,actor_id,decision,comment,
                   snapshot_sha256,output_count,created_at) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                ("lbasrev_" + uuid.uuid4().hex, draft_id, workspace_id, actor_id, decision, clean, digest, len(current), self._now()))
        return self.get_assembly_review(draft_id, workspace_id, actor_id, verify)

    def create_output_manifest(self, draft_id: str, workspace_id: str, actor_id: str, verify: Any) -> dict[str, Any]:
        with connect() as conn:
            self._require(conn, workspace_id, actor_id, self.WRITABLE_ROLES)
            draft = self._active_draft(conn, draft_id, workspace_id, lock=True)
            if draft["workflow_status"] != "APPROVED":
                raise LookbookStateError("Lookbook planning draft must be approved before output manifest export")
            current, snapshot, digest = self._verified_snapshot(conn, draft_id, workspace_id, verify)
            latest = self._latest_assembly(conn, draft_id)
            if latest is None or latest["decision"] != "approved":
                raise LookbookStateError("Lookbook output assembly must be separately reviewed and approved before manifest export")
            if latest["snapshot_sha256"] != digest or latest["output_count"] != len(current):
                raise LookbookStateError("Approved Lookbook assembly snapshot no longer matches the immutable output sequence")
            manifest = {
                "manifest_type": "LOOKBOOK_APPROVED_PLAN_WITH_APPROVED_PHOTO_OUTPUTS", "manifest_version": 1,
                "draft_id": draft_id, "workspace_id": workspace_id, "planning_status": draft["workflow_status"],
                "planning_approved_at": self._iso(draft["reviewed_at"]),
                "planning_approved_by": draft["reviewed_by"], "input": draft["payload_json"],
                "outputs": [{**item, "photo_review_status": "approved", "is_ai_generated": False,
                             "provider_dispatched": False, "credit_charged": False} for item in snapshot],
                "photo_outputs_individually_approved": True, "output_assembly_approved": True,
                "output_assembly_approved_by": latest["actor_id"],
                "output_assembly_reviewed_at": self._iso(latest["created_at"]),
                "output_assembly_snapshot_sha256": digest, "publication_authorized": False,
                "commercial_rights_verified": False, "binary_files_included": False,
                "notice": "Internal Lookbook assembly manifest. The planning draft and assembled sequence were separately approved; no publication or commercial-use rights are granted.",
            }
            canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            manifest_sha = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
            now = self._now()
            conn.execute(
                """INSERT INTO lookbook_output_export_events(event_id,draft_id,workspace_id,actor_id,manifest_sha256,output_count,created_at)
                   VALUES(%s,%s,%s,%s,%s,%s,%s)""",
                ("lboexp_" + uuid.uuid4().hex, draft_id, workspace_id, actor_id, manifest_sha, len(current), now))
            return {"manifest": manifest, "manifest_sha256": manifest_sha, "exported_at": now.isoformat()}

    PACKAGE_MAX_PAGES = 100

    def prepare_package(self, draft_id: str, workspace_id: str, actor_id: str, verify: Any) -> dict[str, Any]:
        """Everything the private package needs, re-verified: approved plan + approved, unchanged output sequence."""
        with connect() as conn:
            self._require(conn, workspace_id, actor_id, self.WRITABLE_ROLES)
            draft = self._active_draft(conn, draft_id, workspace_id)
            if draft["workflow_status"] != "APPROVED":
                raise LookbookStateError("Lookbook planning draft must be approved before package export")
            current, snapshot, digest = self._verified_snapshot(conn, draft_id, workspace_id, verify)
            latest = self._latest_assembly(conn, draft_id)
            if latest is None or latest["decision"] != "approved" or latest["snapshot_sha256"] != digest:
                raise LookbookStateError("Lookbook output assembly must be separately approved before package export")
            if len(current) > self.PACKAGE_MAX_PAGES:
                raise LookbookStateError("Lookbook package is limited to 100 output pages")
            bases, total = [], 0
            for item in current:
                base = self._photo_base(conn, item["photo_run_id"], workspace_id)
                total += int(base["version_size_bytes"])
                if total > 250 * 1024 * 1024:
                    raise LookbookStateError("Lookbook private package exceeds the 250 MiB input limit")
                bases.append((item, base))
            return {
                "snapshot_sha256": digest, "bases": bases,
                "assembly_actor_id": latest["actor_id"], "assembly_reviewed_at": self._iso(latest["created_at"]),
                "planning_approved_by": draft["reviewed_by"], "planning_approved_at": self._iso(draft["reviewed_at"]),
                "planning_input": draft["payload_json"]}

    def record_package_export(self, draft_id: str, workspace_id: str, actor_id: str, *, storage_key: str,
                              package_sha256: str, package_size_bytes: int, manifest_sha256: str,
                              snapshot_sha256: str, output_count: int, expires_at: int,
                              export_id: str | None = None, verify: Any = None) -> str:
        """Append the audit row. When `verify` is given the approval and output sequence are re-checked in the same
        transaction (after the file was written), so a change made while packaging is refused."""
        with connect() as conn:
            self._require(conn, workspace_id, actor_id, self.WRITABLE_ROLES)
            self._active_draft(conn, draft_id, workspace_id, lock=True)
            if verify is not None:
                _, _, digest = self._verified_snapshot(conn, draft_id, workspace_id, verify)
                latest = self._latest_assembly(conn, draft_id)
                if (latest is None or latest["decision"] != "approved" or latest["snapshot_sha256"] != digest
                        or digest != snapshot_sha256):
                    raise LookbookStateError("Approved Lookbook assembly changed before package audit could be committed")
            export_id = export_id or "lbpkg_" + uuid.uuid4().hex
            conn.execute(
                """INSERT INTO lookbook_output_package_exports(export_id,draft_id,workspace_id,actor_id,storage_key,package_sha256,
                   package_size_bytes,manifest_sha256,snapshot_sha256,output_count,created_at,expires_at)
                   VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (export_id, draft_id, workspace_id, actor_id, storage_key, package_sha256, package_size_bytes,
                 manifest_sha256, snapshot_sha256, output_count, self._now(), expires_at))
            return export_id

    def get_package_export(self, export_id: str) -> dict[str, Any] | None:
        """Row for a signed download. Authorisation is the caller's job (signature, then current workspace role)."""
        with connect() as conn:
            row = conn.execute("SELECT * FROM lookbook_output_package_exports WHERE export_id=%s", (export_id,)).fetchone()
            return dict(row) if row else None

    def list_package_exports(self, draft_id: str, workspace_id: str, actor_id: str) -> list[dict[str, Any]]:
        with connect() as conn:
            self._require(conn, workspace_id, actor_id, self.READABLE_ROLES)
            return [dict(r) for r in conn.execute(
                "SELECT * FROM lookbook_output_package_exports WHERE draft_id=%s AND workspace_id=%s ORDER BY created_at DESC, export_id DESC",
                (draft_id, workspace_id)).fetchall()]
