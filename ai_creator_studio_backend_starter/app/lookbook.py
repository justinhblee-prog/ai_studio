"""Lookbook planning, approved Photo output assembly, internal review and private export workflows."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import sqlite3
import stat
import time
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.viewer_responses import (LookbookDraftListResponse, LookbookDraftResponse, LookbookOutputListResponse, LookbookAssemblyReviewResponse, LookbookPackageExportListResponse, LookbookPackageExportResponse, ManifestExportResponse, LookbookOutputResponse, EventListResponse, LookbookPlanManifestResponse)
from fastapi import APIRouter, Depends, HTTPException, Query
from app.private_file_response import PrivateFileError, open_private_file_response
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app import config
from app.assets.routes import current_user, require_role
from app.assets.store import initialize as initialize_assets
from app.ports.lookbooks import get_lookbook_draft_port
from app.repo_errors import raise_http
from app.storage import get_storage

router = APIRouter(prefix="/v1/lookbook-drafts", tags=["lookbook"])


class ReviewDecisionInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    comment: str | None = Field(default=None, max_length=2000)


class LookbookAssemblyReviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    comment: str = Field(default="", max_length=2000)


class LookbookOutputAttachInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    photo_run_id: str = Field(min_length=8, max_length=80)
    page_order: int = Field(ge=1, le=100)
    product_id: str | None = Field(default=None, min_length=8, max_length=80)
    product_variant_id: str | None = Field(default=None, min_length=8, max_length=80)
    caption: str | None = Field(default=None, max_length=240)


class LookbookDraftInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    workspace_id: str = Field(min_length=2, max_length=64)
    title: str = Field(min_length=1, max_length=120)
    project_id: str | None = Field(default=None, min_length=8, max_length=80)
    character_id: str | None = Field(default=None, min_length=8, max_length=80)
    product_ids: list[str] = Field(default_factory=list, max_length=20)
    product_variant_ids: list[str] = Field(default_factory=list, max_length=40)
    product_asset_ids: list[str] = Field(default_factory=list, max_length=20)
    person_asset_id: str | None = Field(default=None, min_length=8, max_length=80)
    scene_preset: str | None = Field(default=None, max_length=120)
    output_count: int = Field(default=1, ge=1, le=20)

    @field_validator("product_asset_ids")
    @classmethod
    def valid_product_asset_ids(cls, values: list[str]) -> list[str]:
        if any(not value.strip() or len(value) > 80 for value in values):
            raise ValueError("Product asset IDs must be non-empty identifiers")
        return values

    @field_validator("product_variant_ids")
    @classmethod
    def valid_variant_ids(cls, values: list[str]) -> list[str]:
        if any(not value.strip() or len(value) > 80 for value in values):
            raise ValueError("product_variant_ids must contain non-empty identifiers")
        return values

    @field_validator("scene_preset")
    @classmethod
    def nonempty_scene(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("scene_preset must not be blank")
        return value

    @model_validator(mode="after")
    def unique_asset_ids(self):
        ids = list(self.product_asset_ids)
        if self.person_asset_id:
            ids.append(self.person_asset_id)
        if not self.product_ids and not self.product_variant_ids and not self.product_asset_ids:
            raise ValueError("At least one catalog product, product variant or direct product image is required")
        if (len(ids) != len(set(ids)) or len(self.product_ids) != len(set(self.product_ids))
                or len(self.product_variant_ids) != len(set(self.product_variant_ids))):
            raise ValueError("Product, variant and person references must be unique")
        return self

    def asset_roles(self) -> list[tuple[str, str]]:
        roles = [(asset_id, "product") for asset_id in self.product_asset_ids]
        if self.person_asset_id:
            roles.append((self.person_asset_id, "person"))
        return roles


def _connect() -> sqlite3.Connection:
    return get_storage().connect(config.ASSET_DATABASE_PATH)


def initialize() -> None:
    initialize_assets()
    from app.projects import _initialize as initialize_projects
    from app.characters import _initialize as initialize_characters
    from app.products import initialize as initialize_products
    from app.photo_engine import initialize as initialize_photo_engine
    initialize_projects()
    initialize_characters()
    initialize_products()
    initialize_photo_engine()
    db = _connect()
    try:
        db.execute("BEGIN IMMEDIATE")
        db.execute("""CREATE TABLE IF NOT EXISTS lookbook_drafts (
            draft_id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, created_by TEXT NOT NULL,
            payload_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            archived_at TEXT
        )""")
        draft_columns = {row["name"] for row in db.execute("PRAGMA table_info(lookbook_drafts)").fetchall()}
        for column, definition in (
            ("workflow_status", "TEXT NOT NULL DEFAULT 'DRAFT' CHECK(workflow_status IN ('DRAFT','IN_REVIEW','CHANGES_REQUESTED','APPROVED'))"),
            ("submitted_at", "TEXT"), ("submitted_by", "TEXT"),
            ("reviewed_at", "TEXT"), ("reviewed_by", "TEXT"), ("review_comment", "TEXT"),
        ):
            if column not in draft_columns:
                db.execute(f"ALTER TABLE lookbook_drafts ADD COLUMN {column} {definition}")
        db.execute("CREATE INDEX IF NOT EXISTS idx_lookbook_drafts_workspace ON lookbook_drafts(workspace_id, archived_at, updated_at)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_lookbook_drafts_review ON lookbook_drafts(workspace_id,workflow_status,updated_at)")
        db.execute("""CREATE TABLE IF NOT EXISTS lookbook_draft_assets (
            draft_id TEXT NOT NULL REFERENCES lookbook_drafts(draft_id) ON DELETE CASCADE,
            asset_id TEXT NOT NULL REFERENCES assets(asset_id),
            role TEXT NOT NULL CHECK(role IN ('product','person')),
            PRIMARY KEY(draft_id, asset_id, role)
        )""")
        db.execute("CREATE INDEX IF NOT EXISTS idx_lookbook_draft_assets_asset ON lookbook_draft_assets(asset_id)")
        db.execute("""CREATE TABLE IF NOT EXISTS lookbook_draft_entities (
            draft_id TEXT NOT NULL REFERENCES lookbook_drafts(draft_id) ON DELETE CASCADE,
            entity_type TEXT NOT NULL CHECK(entity_type IN ('project','character','product','product_variant')),
            entity_id TEXT NOT NULL,
            PRIMARY KEY(draft_id, entity_type, entity_id)
        )""")
        entity_schema = db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='lookbook_draft_entities'").fetchone()["sql"] or ""
        if "'product_variant'" not in entity_schema:
            db.execute("""CREATE TABLE lookbook_draft_entities_migrating (
                draft_id TEXT NOT NULL REFERENCES lookbook_drafts(draft_id) ON DELETE CASCADE,
                entity_type TEXT NOT NULL CHECK(entity_type IN ('project','character','product','product_variant')),
                entity_id TEXT NOT NULL,
                PRIMARY KEY(draft_id, entity_type, entity_id)
            )""")
            db.execute("INSERT OR IGNORE INTO lookbook_draft_entities_migrating(draft_id,entity_type,entity_id) SELECT draft_id,entity_type,entity_id FROM lookbook_draft_entities")
            db.execute("DROP TABLE lookbook_draft_entities")
            db.execute("ALTER TABLE lookbook_draft_entities_migrating RENAME TO lookbook_draft_entities")
        db.execute("CREATE INDEX IF NOT EXISTS idx_lookbook_draft_entities_ref ON lookbook_draft_entities(entity_type, entity_id)")
        db.executescript("""
        CREATE TRIGGER IF NOT EXISTS trg_lookbook_draft_assets_workspace_insert
        BEFORE INSERT ON lookbook_draft_assets BEGIN
            SELECT CASE WHEN NOT EXISTS (
                SELECT 1 FROM lookbook_drafts d JOIN assets a ON a.asset_id=NEW.asset_id
                WHERE d.draft_id=NEW.draft_id AND d.workspace_id=a.workspace_id
                  AND a.deleted_at IS NULL AND a.media_type LIKE 'image/%'
            ) THEN RAISE(ABORT, 'lookbook asset workspace mismatch') END;
        END;
        CREATE TRIGGER IF NOT EXISTS trg_lookbook_draft_assets_workspace_update
        BEFORE UPDATE OF draft_id,asset_id ON lookbook_draft_assets BEGIN
            SELECT CASE WHEN NOT EXISTS (
                SELECT 1 FROM lookbook_drafts d JOIN assets a ON a.asset_id=NEW.asset_id
                WHERE d.draft_id=NEW.draft_id AND d.workspace_id=a.workspace_id
                  AND a.deleted_at IS NULL AND a.media_type LIKE 'image/%'
            ) THEN RAISE(ABORT, 'lookbook asset workspace mismatch') END;
        END;
        CREATE TRIGGER IF NOT EXISTS trg_lookbook_draft_entities_workspace_insert
        BEFORE INSERT ON lookbook_draft_entities BEGIN
            SELECT CASE WHEN NOT (
                (NEW.entity_type='project' AND EXISTS (SELECT 1 FROM projects x JOIN lookbook_drafts d ON d.draft_id=NEW.draft_id WHERE x.project_id=NEW.entity_id AND x.workspace_id=d.workspace_id)) OR
                (NEW.entity_type='character' AND EXISTS (SELECT 1 FROM characters x JOIN lookbook_drafts d ON d.draft_id=NEW.draft_id WHERE x.character_id=NEW.entity_id AND x.workspace_id=d.workspace_id)) OR
                (NEW.entity_type='product' AND EXISTS (SELECT 1 FROM products x JOIN lookbook_drafts d ON d.draft_id=NEW.draft_id WHERE x.product_id=NEW.entity_id AND x.workspace_id=d.workspace_id)) OR
                (NEW.entity_type='product_variant' AND EXISTS (SELECT 1 FROM product_variants x JOIN products p ON p.product_id=x.product_id JOIN lookbook_drafts d ON d.draft_id=NEW.draft_id WHERE x.variant_id=NEW.entity_id AND x.workspace_id=p.workspace_id AND x.workspace_id=d.workspace_id))
            ) THEN RAISE(ABORT, 'lookbook entity workspace mismatch') END;
        END;
        CREATE TRIGGER IF NOT EXISTS trg_lookbook_draft_entities_workspace_update
        BEFORE UPDATE OF draft_id,entity_type,entity_id ON lookbook_draft_entities BEGIN
            SELECT CASE WHEN NOT (
                (NEW.entity_type='project' AND EXISTS (SELECT 1 FROM projects x JOIN lookbook_drafts d ON d.draft_id=NEW.draft_id WHERE x.project_id=NEW.entity_id AND x.workspace_id=d.workspace_id)) OR
                (NEW.entity_type='character' AND EXISTS (SELECT 1 FROM characters x JOIN lookbook_drafts d ON d.draft_id=NEW.draft_id WHERE x.character_id=NEW.entity_id AND x.workspace_id=d.workspace_id)) OR
                (NEW.entity_type='product' AND EXISTS (SELECT 1 FROM products x JOIN lookbook_drafts d ON d.draft_id=NEW.draft_id WHERE x.product_id=NEW.entity_id AND x.workspace_id=d.workspace_id)) OR
                (NEW.entity_type='product_variant' AND EXISTS (SELECT 1 FROM product_variants x JOIN products p ON p.product_id=x.product_id JOIN lookbook_drafts d ON d.draft_id=NEW.draft_id WHERE x.variant_id=NEW.entity_id AND x.workspace_id=p.workspace_id AND x.workspace_id=d.workspace_id))
            ) THEN RAISE(ABORT, 'lookbook entity workspace mismatch') END;
        END;
        """)
        db.execute("""CREATE TABLE IF NOT EXISTS lookbook_draft_events (
            event_id TEXT PRIMARY KEY, draft_id TEXT NOT NULL REFERENCES lookbook_drafts(draft_id),
            workspace_id TEXT NOT NULL, actor_id TEXT NOT NULL, event_type TEXT NOT NULL,
            details_json TEXT NOT NULL, created_at TEXT NOT NULL
        )""")
        db.execute("CREATE INDEX IF NOT EXISTS idx_lookbook_draft_events ON lookbook_draft_events(draft_id, created_at DESC)")
        db.execute("""CREATE TABLE IF NOT EXISTS lookbook_output_assets (
            output_item_id TEXT PRIMARY KEY, draft_id TEXT NOT NULL REFERENCES lookbook_drafts(draft_id),
            workspace_id TEXT NOT NULL, photo_run_id TEXT NOT NULL REFERENCES photo_processing_runs(run_id),
            asset_id TEXT NOT NULL REFERENCES assets(asset_id), asset_version_id TEXT NOT NULL,
            provenance_id TEXT NOT NULL, checksum_sha256 TEXT NOT NULL,
            product_id TEXT, product_sku TEXT, product_variant_id TEXT, variant_sku TEXT,
            variant_options_json TEXT NOT NULL DEFAULT '{}', page_order INTEGER NOT NULL CHECK(page_order BETWEEN 1 AND 100),
            caption TEXT, created_by TEXT NOT NULL, created_at TEXT NOT NULL,
            UNIQUE(draft_id,photo_run_id), UNIQUE(draft_id,page_order)
        )""")
        db.execute("CREATE INDEX IF NOT EXISTS idx_lookbook_outputs_draft ON lookbook_output_assets(draft_id,page_order)")
        db.execute("""CREATE TRIGGER IF NOT EXISTS trg_lookbook_outputs_no_update
            BEFORE UPDATE ON lookbook_output_assets
            BEGIN SELECT RAISE(ABORT, 'lookbook output items are immutable; create a new draft to change assembly'); END""")
        db.execute("""CREATE TRIGGER IF NOT EXISTS trg_lookbook_outputs_no_delete
            BEFORE DELETE ON lookbook_output_assets
            BEGIN SELECT RAISE(ABORT, 'lookbook output items are immutable; create a new draft to change assembly'); END""")
        db.execute("""CREATE TABLE IF NOT EXISTS lookbook_output_export_events (
            event_id TEXT PRIMARY KEY, draft_id TEXT NOT NULL REFERENCES lookbook_drafts(draft_id),
            workspace_id TEXT NOT NULL, actor_id TEXT NOT NULL, manifest_sha256 TEXT NOT NULL,
            output_count INTEGER NOT NULL CHECK(output_count > 0), created_at TEXT NOT NULL
        )""")
        db.execute("CREATE INDEX IF NOT EXISTS idx_lookbook_output_exports ON lookbook_output_export_events(draft_id,created_at,event_id)")
        db.execute("""CREATE TRIGGER IF NOT EXISTS trg_lookbook_output_exports_no_update
            BEFORE UPDATE ON lookbook_output_export_events
            BEGIN SELECT RAISE(ABORT, 'lookbook output export events are append-only'); END""")
        db.execute("""CREATE TRIGGER IF NOT EXISTS trg_lookbook_output_exports_no_delete
            BEFORE DELETE ON lookbook_output_export_events
            BEGIN SELECT RAISE(ABORT, 'lookbook output export events are append-only'); END""")
        db.execute("""CREATE TABLE IF NOT EXISTS lookbook_output_assembly_review_events (
            event_id TEXT PRIMARY KEY, draft_id TEXT NOT NULL REFERENCES lookbook_drafts(draft_id),
            workspace_id TEXT NOT NULL, actor_id TEXT NOT NULL,
            decision TEXT NOT NULL CHECK(decision IN ('submitted','approved','rejected')),
            comment TEXT NOT NULL DEFAULT '', snapshot_sha256 TEXT NOT NULL,
            output_count INTEGER NOT NULL CHECK(output_count > 0), created_at TEXT NOT NULL
        )""")
        db.execute("CREATE INDEX IF NOT EXISTS idx_lookbook_assembly_reviews ON lookbook_output_assembly_review_events(draft_id,created_at,event_id)")
        db.execute("""CREATE TRIGGER IF NOT EXISTS trg_lookbook_assembly_reviews_no_update
            BEFORE UPDATE ON lookbook_output_assembly_review_events
            BEGIN SELECT RAISE(ABORT, 'lookbook assembly review events are append-only'); END""")
        db.execute("""CREATE TRIGGER IF NOT EXISTS trg_lookbook_assembly_reviews_no_delete
            BEFORE DELETE ON lookbook_output_assembly_review_events
            BEGIN SELECT RAISE(ABORT, 'lookbook assembly review events are append-only'); END""")
        db.execute("""CREATE TABLE IF NOT EXISTS lookbook_output_package_exports (
            export_id TEXT PRIMARY KEY, draft_id TEXT NOT NULL REFERENCES lookbook_drafts(draft_id),
            workspace_id TEXT NOT NULL, actor_id TEXT NOT NULL, storage_key TEXT NOT NULL UNIQUE,
            package_sha256 TEXT NOT NULL, package_size_bytes INTEGER NOT NULL,
            manifest_sha256 TEXT NOT NULL, snapshot_sha256 TEXT NOT NULL,
            output_count INTEGER NOT NULL CHECK(output_count > 0),
            created_at TEXT NOT NULL, expires_at INTEGER NOT NULL
        )""")
        db.execute("CREATE INDEX IF NOT EXISTS idx_lookbook_package_exports ON lookbook_output_package_exports(draft_id,created_at DESC)")
        db.execute("""CREATE TRIGGER IF NOT EXISTS trg_lookbook_package_exports_no_update
            BEFORE UPDATE ON lookbook_output_package_exports
            BEGIN SELECT RAISE(ABORT, 'lookbook package export audit is append-only'); END""")
        db.execute("""CREATE TRIGGER IF NOT EXISTS trg_lookbook_package_exports_no_delete
            BEFORE DELETE ON lookbook_output_package_exports
            BEGIN SELECT RAISE(ABORT, 'lookbook package export audit is append-only'); END""")
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
    db.execute("""INSERT INTO lookbook_draft_events(event_id, draft_id, workspace_id,
        actor_id, event_type, details_json, created_at) VALUES(?,?,?,?,?,?,?)""",
        ("lbe_" + uuid.uuid4().hex, draft_id, workspace_id, actor_id, event_type,
         json.dumps(details or {}, ensure_ascii=False, separators=(",", ":")), _now()))


def _validate_references(db: sqlite3.Connection, body: LookbookDraftInput) -> tuple[list[tuple[str, str]], list[str]]:
    roles = list(body.asset_roles())
    product_image_ids: list[str] = []
    parent_product_ids: list[str] = list(body.product_ids)
    for product_id in body.product_ids:
        product = db.execute("SELECT 1 FROM products WHERE product_id=? AND workspace_id=? AND status='ACTIVE'",
                              (product_id, body.workspace_id)).fetchone()
        if not product:
            raise HTTPException(status_code=422, detail="Every catalog product must be active in this workspace")
        images = db.execute("SELECT pa.asset_id FROM product_assets pa JOIN assets a ON a.asset_id=pa.asset_id "
                             "WHERE pa.product_id=? AND a.workspace_id=? AND a.deleted_at IS NULL ORDER BY pa.sort_order",
                             (product_id, body.workspace_id)).fetchall()
        if not images:
            raise HTTPException(status_code=422, detail="Every catalog product must have at least one active image")
        product_image_ids.extend(item["asset_id"] for item in images)
    for variant_id in body.product_variant_ids:
        variant = db.execute("""SELECT pv.product_id FROM product_variants pv
            JOIN products p ON p.product_id=pv.product_id
            WHERE pv.variant_id=? AND pv.workspace_id=? AND pv.status='ACTIVE' AND p.status='ACTIVE'""",
            (variant_id, body.workspace_id)).fetchone()
        if not variant:
            raise HTTPException(status_code=422, detail="Every selected Product Variant must be active in this workspace")
        parent_id = variant["product_id"]
        parent_product_ids.append(parent_id)
        variant_images = db.execute("""SELECT pva.asset_id FROM product_variant_assets pva
            JOIN assets a ON a.asset_id=pva.asset_id
            WHERE pva.variant_id=? AND a.workspace_id=? AND a.deleted_at IS NULL ORDER BY pva.sort_order""",
            (variant_id, body.workspace_id)).fetchall()
        if variant_images:
            product_image_ids.extend(item["asset_id"] for item in variant_images)
        else:
            parent_images = db.execute("""SELECT pa.asset_id FROM product_assets pa JOIN assets a ON a.asset_id=pa.asset_id
                WHERE pa.product_id=? AND a.workspace_id=? AND a.deleted_at IS NULL ORDER BY pa.sort_order""",
                (parent_id, body.workspace_id)).fetchall()
            if not parent_images:
                raise HTTPException(status_code=422, detail="A selected Variant must have active variant or parent Product images")
            product_image_ids.extend(item["asset_id"] for item in parent_images)
    if body.person_asset_id and body.person_asset_id in product_image_ids:
        raise HTTPException(status_code=422, detail="Person image cannot also be a product catalog image")
    seen = {asset_id for asset_id, _ in roles}
    for asset_id in product_image_ids:
        if asset_id not in seen:
            roles.append((asset_id, "product")); seen.add(asset_id)
    asset_ids = [asset_id for asset_id, _ in roles]
    placeholders = ",".join("?" for _ in asset_ids)
    rows = db.execute(f"""SELECT asset_id FROM assets WHERE workspace_id=? AND deleted_at IS NULL
        AND media_type LIKE 'image/%' AND asset_id IN ({placeholders})""",
        (body.workspace_id, *asset_ids)).fetchall()
    if len(rows) != len(set(asset_ids)):
        raise HTTPException(status_code=422, detail={"code": "LOOKBOOK_IMAGE_ASSET_REQUIRED",
            "message": "All product/person references must be active image assets in this workspace."})
    if body.project_id:
        project = db.execute("SELECT status FROM projects WHERE project_id=? AND workspace_id=?",
                             (body.project_id, body.workspace_id)).fetchone()
        if not project:
            raise HTTPException(status_code=422, detail="Project must belong to this workspace")
        if project["status"] != "ACTIVE":
            raise HTTPException(status_code=409, detail="Lookbook Draft requires an ACTIVE Project")
    if body.character_id:
        character = db.execute("SELECT 1 FROM characters WHERE character_id=? AND workspace_id=? AND deleted_at IS NULL",
                               (body.character_id, body.workspace_id)).fetchone()
        if not character:
            raise HTTPException(status_code=422, detail="Character must be active in this workspace")
    return roles, list(dict.fromkeys(parent_product_ids))


def _public(row: sqlite3.Row) -> dict[str, Any]:
    value = dict(row)
    value["input"] = json.loads(value.pop("payload_json"))
    value["status"] = "archived" if value["archived_at"] else "draft"
    value["workflow_status"] = value.get("workflow_status", "DRAFT").lower()
    return value


def create_draft(body: LookbookDraftInput, actor_id: str) -> dict[str, Any]:
    initialize()
    draft_id, now = "lbd_" + uuid.uuid4().hex, _now()
    db = _connect()
    try:
        db.execute("BEGIN IMMEDIATE")
        roles, parent_product_ids = _validate_references(db, body)
        payload = body.model_dump(mode="json", exclude={"workspace_id"})
        db.execute("INSERT INTO lookbook_drafts(draft_id, workspace_id, created_by, payload_json, created_at, updated_at) VALUES(?,?,?,?,?,?)",
                   (draft_id, body.workspace_id, actor_id, json.dumps(payload, ensure_ascii=False), now, now))
        db.executemany("INSERT INTO lookbook_draft_assets(draft_id, asset_id, role) VALUES(?,?,?)",
                       [(draft_id, asset_id, role) for asset_id, role in roles])
        entities = []
        if body.project_id:
            entities.append((draft_id, "project", body.project_id))
        if body.character_id:
            entities.append((draft_id, "character", body.character_id))
        entities.extend((draft_id, "product", product_id) for product_id in parent_product_ids)
        entities.extend((draft_id, "product_variant", variant_id) for variant_id in body.product_variant_ids)
        entities = list(dict.fromkeys(entities))
        db.executemany("INSERT INTO lookbook_draft_entities(draft_id, entity_type, entity_id) VALUES(?,?,?)", entities)
        _event(db, draft_id, body.workspace_id, actor_id, "lookbook.draft_created",
               {"catalog_product_count": len(body.product_ids), "variant_count": len(body.product_variant_ids),
                "direct_image_count": len(body.product_asset_ids), "has_person": bool(body.person_asset_id)})
        result = db.execute("SELECT * FROM lookbook_drafts WHERE draft_id=?", (draft_id,)).fetchone()
        db.commit()
        return _public(result)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def list_drafts(workspace_id: str, include_archived: bool = False, *, limit: int = 50, offset: int = 0) -> dict[str, Any]:
    initialize(); db = _connect()
    try:
        where = "workspace_id=?" + ("" if include_archived else " AND archived_at IS NULL")
        total = int(db.execute(f"SELECT COUNT(*) AS n FROM lookbook_drafts WHERE {where}", (workspace_id,)).fetchone()["n"])
        rows = db.execute(f"SELECT * FROM lookbook_drafts WHERE {where} ORDER BY updated_at DESC, draft_id LIMIT ? OFFSET ?",
                          (workspace_id, limit, offset)).fetchall()
        return {"items": [_public(row) for row in rows], "total": total, "limit": limit, "offset": offset}
    finally:
        db.close()


def get_draft(draft_id: str, workspace_id: str) -> dict[str, Any] | None:
    initialize(); db = _connect()
    try:
        row = db.execute("SELECT * FROM lookbook_drafts WHERE draft_id=? AND workspace_id=?",
                         (draft_id, workspace_id)).fetchone()
        return _public(row) if row else None
    finally:
        db.close()


def update_draft(draft_id: str, body: LookbookDraftInput, actor_id: str) -> dict[str, Any]:
    initialize(); db = _connect()
    try:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT * FROM lookbook_drafts WHERE draft_id=? AND workspace_id=? AND archived_at IS NULL",
                         (draft_id, body.workspace_id)).fetchone()
        if not row:
            raise LookupError("Lookbook Draft not found")
        if row["workflow_status"] not in {"DRAFT", "CHANGES_REQUESTED"}:
            raise HTTPException(status_code=409, detail="Only DRAFT or CHANGES_REQUESTED Lookbook Drafts can be edited")
        roles, parent_product_ids = _validate_references(db, body)
        now = _now()
        payload = body.model_dump(mode="json", exclude={"workspace_id"})
        db.execute("UPDATE lookbook_drafts SET payload_json=?, updated_at=? WHERE draft_id=? AND workspace_id=?",
                   (json.dumps(payload, ensure_ascii=False), now, draft_id, body.workspace_id))
        db.execute("DELETE FROM lookbook_draft_assets WHERE draft_id=?", (draft_id,))
        db.executemany("INSERT INTO lookbook_draft_assets(draft_id, asset_id, role) VALUES(?,?,?)",
                       [(draft_id, asset_id, role) for asset_id, role in roles])
        db.execute("DELETE FROM lookbook_draft_entities WHERE draft_id=?", (draft_id,))
        entities = []
        if body.project_id:
            entities.append((draft_id, "project", body.project_id))
        if body.character_id:
            entities.append((draft_id, "character", body.character_id))
        entities.extend((draft_id, "product", product_id) for product_id in parent_product_ids)
        entities.extend((draft_id, "product_variant", variant_id) for variant_id in body.product_variant_ids)
        entities = list(dict.fromkeys(entities))
        db.executemany("INSERT INTO lookbook_draft_entities(draft_id, entity_type, entity_id) VALUES(?,?,?)", entities)
        _event(db, draft_id, body.workspace_id, actor_id, "lookbook.draft_updated",
               {"catalog_product_count": len(body.product_ids), "variant_count": len(body.product_variant_ids),
                "direct_image_count": len(body.product_asset_ids), "has_person": bool(body.person_asset_id)})
        result = db.execute("SELECT * FROM lookbook_drafts WHERE draft_id=?", (draft_id,)).fetchone()
        db.commit()
        return _public(result)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def submit_for_review(draft_id: str, workspace_id: str, actor_id: str) -> dict[str, Any]:
    initialize(); db = _connect()
    try:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT * FROM lookbook_drafts WHERE draft_id=? AND workspace_id=? AND archived_at IS NULL", (draft_id, workspace_id)).fetchone()
        if not row: raise LookupError("Lookbook Draft not found")
        if row["workflow_status"] not in {"DRAFT", "CHANGES_REQUESTED"}:
            raise HTTPException(status_code=409, detail="Only DRAFT or CHANGES_REQUESTED drafts can be submitted")
        now = _now()
        db.execute("UPDATE lookbook_drafts SET workflow_status='IN_REVIEW',submitted_at=?,submitted_by=?,reviewed_at=NULL,reviewed_by=NULL,review_comment=NULL,updated_at=? WHERE draft_id=?",
                   (now, actor_id, now, draft_id))
        _event(db, draft_id, workspace_id, actor_id, "lookbook.submitted_for_review", {"previous_status": row["workflow_status"]})
        result = _public(db.execute("SELECT * FROM lookbook_drafts WHERE draft_id=?", (draft_id,)).fetchone())
        db.commit(); return result
    except Exception:
        db.rollback(); raise
    finally: db.close()


def decide_review(draft_id: str, workspace_id: str, actor_id: str, decision: str, comment: str | None = None) -> dict[str, Any]:
    if decision not in {"APPROVED", "CHANGES_REQUESTED"}:
        raise ValueError("Unsupported review decision")
    if decision == "CHANGES_REQUESTED" and not (comment and comment.strip()):
        raise HTTPException(status_code=422, detail="A review comment is required when requesting changes")
    initialize(); db = _connect()
    try:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT * FROM lookbook_drafts WHERE draft_id=? AND workspace_id=? AND archived_at IS NULL", (draft_id, workspace_id)).fetchone()
        if not row: raise LookupError("Lookbook Draft not found")
        if row["workflow_status"] != "IN_REVIEW":
            raise HTTPException(status_code=409, detail="Only IN_REVIEW drafts can be approved or returned for changes")
        now = _now(); event = "lookbook.approved" if decision == "APPROVED" else "lookbook.changes_requested"
        normalized_comment = comment.strip() if comment else None
        db.execute("UPDATE lookbook_drafts SET workflow_status=?,reviewed_at=?,reviewed_by=?,review_comment=?,updated_at=? WHERE draft_id=?",
                   (decision, now, actor_id, normalized_comment, now, draft_id))
        _event(db, draft_id, workspace_id, actor_id, event, {"comment": normalized_comment})
        result = _public(db.execute("SELECT * FROM lookbook_drafts WHERE draft_id=?", (draft_id,)).fetchone())
        db.commit(); return result
    except Exception:
        db.rollback(); raise
    finally: db.close()


def _lookbook_output_public(row: sqlite3.Row) -> dict[str, Any]:
    value = dict(row)
    value["variant_options"] = json.loads(value.pop("variant_options_json") or "{}")
    return value


def list_lookbook_outputs(draft_id: str, workspace_id: str) -> dict[str, Any]:
    initialize(); db = _connect()
    try:
        draft = db.execute("SELECT 1 FROM lookbook_drafts WHERE draft_id=? AND workspace_id=? AND archived_at IS NULL",
                           (draft_id, workspace_id)).fetchone()
        if not draft:
            raise LookupError("Lookbook Draft not found")
        rows = db.execute("SELECT * FROM lookbook_output_assets WHERE draft_id=? AND workspace_id=? ORDER BY page_order,output_item_id",
                          (draft_id, workspace_id)).fetchall()
        return {"items": [_lookbook_output_public(row) for row in rows], "total": len(rows)}
    finally:
        db.close()


def get_photo_output_review_for_run(run_id: str, workspace_id: str) -> dict[str, Any] | None:
    from app.photo_engine import get_photo_output_review
    db = _connect()
    try:
        row = db.execute("SELECT draft_id FROM photo_processing_runs WHERE run_id=? AND workspace_id=?",
                         (run_id, workspace_id)).fetchone()
    finally:
        db.close()
    if not row:
        return None
    return get_photo_output_review(row["draft_id"], run_id, workspace_id)


def attach_approved_photo_output(draft_id: str, workspace_id: str, actor_id: str,
                                 body: LookbookOutputAttachInput) -> dict[str, Any]:
    initialize()
    from app.photo_engine import get_photo_output_review
    review = get_photo_output_review_for_run(body.photo_run_id, workspace_id)
    if review is None or review["status"] != "approved":
        raise ValueError("Only individually approved Photo outputs can be attached to a Lookbook")
    output = review["output"]
    db = _connect()
    try:
        db.execute("BEGIN IMMEDIATE")
        draft = db.execute("SELECT * FROM lookbook_drafts WHERE draft_id=? AND workspace_id=? AND archived_at IS NULL",
                           (draft_id, workspace_id)).fetchone()
        if not draft:
            raise LookupError("Lookbook Draft not found")
        if draft["workflow_status"] != "APPROVED":
            raise ValueError("Lookbook planning draft must be approved before output assembly")
        assembly_review = db.execute("SELECT decision FROM lookbook_output_assembly_review_events WHERE draft_id=? ORDER BY rowid DESC LIMIT 1",
                                     (draft_id,)).fetchone()
        if assembly_review:
            raise ValueError("Lookbook output assembly is frozen after review submission; create a new draft to change it")
        run = db.execute("SELECT * FROM photo_processing_runs WHERE run_id=? AND workspace_id=? AND status='succeeded'",
                         (body.photo_run_id, workspace_id)).fetchone()
        latest = db.execute("SELECT * FROM photo_output_review_events WHERE run_id=? ORDER BY rowid DESC LIMIT 1",
                            (body.photo_run_id,)).fetchone()
        from app.photo_engine import _photo_output_base, _verify_photo_output_version
        photo_base = _photo_output_base(db, run["draft_id"], body.photo_run_id, workspace_id) if run else None
        if (not run or not photo_base or not _verify_photo_output_version(photo_base)
                or not latest or latest["decision"] != "approved"
                or latest["asset_id"] != output["asset_id"]
                or latest["asset_version_id"] != output["asset_version_id"]
                or latest["provenance_id"] != output["provenance_id"]
                or latest["checksum_sha256"] != output["checksum_sha256"]):
            raise ValueError("Photo output approval snapshot is missing or no longer matches its immutable version")
        product_id = body.product_id
        product_sku = None
        variant_sku = None
        variant_options: dict[str, Any] = {}
        if body.product_variant_id:
            variant = db.execute("""SELECT v.variant_id,v.product_id,v.sku AS variant_sku,v.option_values_json,
                p.sku AS product_sku FROM product_variants v JOIN products p ON p.product_id=v.product_id
                WHERE v.variant_id=? AND v.workspace_id=? AND v.status='ACTIVE' AND p.status='ACTIVE'""",
                (body.product_variant_id, workspace_id)).fetchone()
            if not variant:
                raise ValueError("Selected Product Variant is not active in this workspace")
            if product_id and product_id != variant["product_id"]:
                raise ValueError("Product ID does not match the selected Product Variant")
            product_id = variant["product_id"]
            product_sku = variant["product_sku"]
            variant_sku = variant["variant_sku"]
            variant_options = json.loads(variant["option_values_json"])
            in_plan = db.execute("""SELECT 1 FROM lookbook_draft_entities WHERE draft_id=? AND
                ((entity_type='product_variant' AND entity_id=?) OR (entity_type='product' AND entity_id=?)) LIMIT 1""",
                (draft_id, body.product_variant_id, product_id)).fetchone()
            if not in_plan:
                raise ValueError("Selected Product Variant is not referenced by the approved Lookbook plan")
        elif product_id:
            product = db.execute("SELECT sku FROM products WHERE product_id=? AND workspace_id=? AND status='ACTIVE'",
                                 (product_id, workspace_id)).fetchone()
            if not product:
                raise ValueError("Selected Product is not active in this workspace")
            in_plan = db.execute("SELECT 1 FROM lookbook_draft_entities WHERE draft_id=? AND entity_type='product' AND entity_id=?",
                                 (draft_id, product_id)).fetchone()
            if not in_plan:
                raise ValueError("Selected Product is not referenced by the approved Lookbook plan")
            product_sku = product["sku"]
        output_item_id = "lbo_" + uuid.uuid4().hex
        now = _now()
        db.execute("""INSERT INTO lookbook_output_assets(output_item_id,draft_id,workspace_id,photo_run_id,
            asset_id,asset_version_id,provenance_id,checksum_sha256,product_id,product_sku,
            product_variant_id,variant_sku,variant_options_json,page_order,caption,created_by,created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (output_item_id, draft_id, workspace_id, body.photo_run_id, output["asset_id"],
             output["asset_version_id"], output["provenance_id"], output["checksum_sha256"],
             product_id, product_sku, body.product_variant_id, variant_sku,
             json.dumps(variant_options, ensure_ascii=False, separators=(",", ":")),
             body.page_order, body.caption, actor_id, now))
        _event(db, draft_id, workspace_id, actor_id, "lookbook.approved_photo_output_attached",
               {"output_item_id": output_item_id, "photo_run_id": body.photo_run_id,
                "asset_id": output["asset_id"], "asset_version_id": output["asset_version_id"],
                "product_id": product_id, "product_variant_id": body.product_variant_id,
                "page_order": body.page_order})
        row = db.execute("SELECT * FROM lookbook_output_assets WHERE output_item_id=?", (output_item_id,)).fetchone()
        db.commit()
        return _lookbook_output_public(row)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _verified_lookbook_output_snapshot(db: sqlite3.Connection, draft_id: str, workspace_id: str):
    from app.photo_engine import _photo_output_base, _verify_photo_output_version
    current = db.execute("SELECT * FROM lookbook_output_assets WHERE draft_id=? AND workspace_id=? ORDER BY page_order,output_item_id",
                         (draft_id, workspace_id)).fetchall()
    if not current:
        raise ValueError("Lookbook has no Photo outputs attached")
    snapshot = []
    for item in current:
        run = db.execute("SELECT draft_id FROM photo_processing_runs WHERE run_id=? AND workspace_id=? AND status='succeeded'",
                         (item["photo_run_id"], workspace_id)).fetchone()
        latest = db.execute("SELECT * FROM photo_output_review_events WHERE run_id=? ORDER BY rowid DESC LIMIT 1",
                            (item["photo_run_id"],)).fetchone()
        photo_base = _photo_output_base(db, run["draft_id"], item["photo_run_id"], workspace_id) if run else None
        if (not photo_base or not _verify_photo_output_version(photo_base) or not latest
                or latest["decision"] != "approved" or latest["asset_id"] != item["asset_id"]
                or latest["asset_version_id"] != item["asset_version_id"]
                or latest["provenance_id"] != item["provenance_id"]
                or latest["checksum_sha256"] != item["checksum_sha256"]):
            raise ValueError("A Lookbook output failed immutable Photo review or file integrity checks")
        snapshot.append({
            "output_item_id": item["output_item_id"], "page_order": item["page_order"],
            "photo_run_id": item["photo_run_id"], "asset_id": item["asset_id"],
            "asset_version_id": item["asset_version_id"], "provenance_id": item["provenance_id"],
            "checksum_sha256": item["checksum_sha256"], "product_id": item["product_id"],
            "product_sku": item["product_sku"], "product_variant_id": item["product_variant_id"],
            "variant_sku": item["variant_sku"],
            "variant_options": json.loads(item["variant_options_json"] or "{}"),
            "caption": item["caption"],
        })
    canonical = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return current, snapshot, hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def get_lookbook_output_assembly_review(draft_id: str, workspace_id: str) -> dict[str, Any] | None:
    initialize(); db = _connect()
    try:
        draft = db.execute("SELECT workflow_status FROM lookbook_drafts WHERE draft_id=? AND workspace_id=? AND archived_at IS NULL",
                           (draft_id, workspace_id)).fetchone()
        if not draft:
            return None
        count = int(db.execute("SELECT COUNT(*) AS n FROM lookbook_output_assets WHERE draft_id=? AND workspace_id=?",
                               (draft_id, workspace_id)).fetchone()["n"])
        rows = db.execute("SELECT * FROM lookbook_output_assembly_review_events WHERE draft_id=? AND workspace_id=? ORDER BY rowid DESC",
                          (draft_id, workspace_id)).fetchall()
        events = [dict(row) for row in rows]
        latest = events[0] if events else None
        status = ("in_review" if latest["decision"] == "submitted" else latest["decision"]) if latest else ("pending_review" if count else "no_outputs")
        if count and (not latest or latest["decision"] in {"submitted", "approved"}):
            try:
                _, _, current_hash = _verified_lookbook_output_snapshot(db, draft_id, workspace_id)
                if latest and current_hash != latest["snapshot_sha256"]:
                    status = "integrity_error"
            except ValueError:
                status = "integrity_error"
        return {"draft_id": draft_id, "planning_status": draft["workflow_status"],
                "status": status, "output_count": count,
                "snapshot_sha256": latest["snapshot_sha256"] if latest else None,
                "events": events}
    finally:
        db.close()


def submit_lookbook_output_assembly(draft_id: str, workspace_id: str, actor_id: str) -> dict[str, Any] | None:
    initialize(); db = _connect()
    try:
        db.execute("BEGIN IMMEDIATE")
        draft = db.execute("SELECT * FROM lookbook_drafts WHERE draft_id=? AND workspace_id=? AND archived_at IS NULL",
                           (draft_id, workspace_id)).fetchone()
        if not draft:
            return None
        if draft["workflow_status"] != "APPROVED":
            raise ValueError("Lookbook planning draft must be approved before assembly review")
        current, _, snapshot_hash = _verified_lookbook_output_snapshot(db, draft_id, workspace_id)
        latest = db.execute("SELECT decision FROM lookbook_output_assembly_review_events WHERE draft_id=? ORDER BY rowid DESC LIMIT 1",
                            (draft_id,)).fetchone()
        if latest:
            raise ValueError("Lookbook assembly review has already started; create a new draft to change the immutable output sequence")
        now = _now()
        db.execute("""INSERT INTO lookbook_output_assembly_review_events(event_id,draft_id,workspace_id,
            actor_id,decision,comment,snapshot_sha256,output_count,created_at) VALUES(?,?,?,?,?,?,?,?,?)""",
            ("lbasrev_" + uuid.uuid4().hex, draft_id, workspace_id, actor_id, "submitted", "",
             snapshot_hash, len(current), now))
        db.commit()
        return get_lookbook_output_assembly_review(draft_id, workspace_id)
    except Exception:
        db.rollback(); raise
    finally:
        db.close()


def decide_lookbook_output_assembly(draft_id: str, workspace_id: str, actor_id: str,
                                    decision: str, comment: str = "") -> dict[str, Any] | None:
    if decision not in {"approved", "rejected"}:
        raise ValueError("Unsupported Lookbook assembly review decision")
    clean_comment = comment.strip()
    if decision == "rejected" and not clean_comment:
        raise ValueError("A non-empty comment is required when rejecting the Lookbook assembly")
    initialize(); db = _connect()
    try:
        db.execute("BEGIN IMMEDIATE")
        draft = db.execute("SELECT * FROM lookbook_drafts WHERE draft_id=? AND workspace_id=? AND archived_at IS NULL",
                           (draft_id, workspace_id)).fetchone()
        if not draft:
            return None
        if draft["workflow_status"] != "APPROVED":
            raise ValueError("Lookbook planning draft is not approved")
        current, _, snapshot_hash = _verified_lookbook_output_snapshot(db, draft_id, workspace_id)
        latest = db.execute("SELECT * FROM lookbook_output_assembly_review_events WHERE draft_id=? ORDER BY rowid DESC LIMIT 1",
                            (draft_id,)).fetchone()
        if not latest or latest["decision"] != "submitted":
            raise ValueError("Lookbook assembly must be submitted and awaiting review")
        if latest["snapshot_sha256"] != snapshot_hash or latest["output_count"] != len(current):
            raise ValueError("Lookbook output sequence changed after assembly review submission")
        now = _now()
        db.execute("""INSERT INTO lookbook_output_assembly_review_events(event_id,draft_id,workspace_id,
            actor_id,decision,comment,snapshot_sha256,output_count,created_at) VALUES(?,?,?,?,?,?,?,?,?)""",
            ("lbasrev_" + uuid.uuid4().hex, draft_id, workspace_id, actor_id, decision, clean_comment,
             snapshot_hash, len(current), now))
        db.commit()
        return get_lookbook_output_assembly_review(draft_id, workspace_id)
    except Exception:
        db.rollback(); raise
    finally:
        db.close()


def create_lookbook_output_manifest(draft_id: str, workspace_id: str, actor_id: str) -> dict[str, Any]:
    initialize()
    db = _connect()
    try:
        db.execute("BEGIN IMMEDIATE")
        draft = db.execute("SELECT * FROM lookbook_drafts WHERE draft_id=? AND workspace_id=? AND archived_at IS NULL",
                           (draft_id, workspace_id)).fetchone()
        if not draft:
            raise LookupError("Lookbook Draft not found")
        if draft["workflow_status"] != "APPROVED":
            raise ValueError("Lookbook planning draft must be approved before output manifest export")
        current, snapshot, snapshot_hash = _verified_lookbook_output_snapshot(db, draft_id, workspace_id)
        latest = db.execute("SELECT * FROM lookbook_output_assembly_review_events WHERE draft_id=? ORDER BY rowid DESC LIMIT 1",
                            (draft_id,)).fetchone()
        if not latest or latest["decision"] != "approved":
            raise ValueError("Lookbook output assembly must be separately reviewed and approved before manifest export")
        if latest["snapshot_sha256"] != snapshot_hash or latest["output_count"] != len(current):
            raise ValueError("Approved Lookbook assembly snapshot no longer matches the immutable output sequence")
        manifest = {
            "manifest_type": "LOOKBOOK_APPROVED_PLAN_WITH_APPROVED_PHOTO_OUTPUTS",
            "manifest_version": 1,
            "draft_id": draft_id,
            "workspace_id": workspace_id,
            "planning_status": draft["workflow_status"],
            "planning_approved_at": draft["reviewed_at"],
            "planning_approved_by": draft["reviewed_by"],
            "input": json.loads(draft["payload_json"]),
            "outputs": [{**item, "photo_review_status": "approved",
                         "is_ai_generated": False, "provider_dispatched": False, "credit_charged": False}
                        for item in snapshot],
            "photo_outputs_individually_approved": True,
            "output_assembly_approved": True,
            "output_assembly_approved_by": latest["actor_id"],
            "output_assembly_reviewed_at": latest["created_at"],
            "output_assembly_snapshot_sha256": snapshot_hash,
            "publication_authorized": False,
            "commercial_rights_verified": False,
            "binary_files_included": False,
            "notice": "Internal Lookbook assembly manifest. The planning draft and assembled sequence were separately approved; no publication or commercial-use rights are granted.",
        }
        canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        now = _now()
        db.execute("INSERT INTO lookbook_output_export_events(event_id,draft_id,workspace_id,actor_id,manifest_sha256,output_count,created_at) VALUES(?,?,?,?,?,?,?)",
                   ("lboexp_" + uuid.uuid4().hex, draft_id, workspace_id, actor_id, digest, len(current), now))
        db.commit()
        return {"manifest": manifest, "manifest_sha256": digest, "exported_at": now}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _lookbook_package_dir() -> Path:
    root = config.ASSET_STORAGE_DIR.resolve()
    path = (root / "lookbook_exports").resolve()
    if path.parent != root:
        raise RuntimeError("Lookbook export directory must remain under private asset storage")
    path.mkdir(parents=True, exist_ok=True)
    return path


def _lookbook_package_signature(export_id: str, expires: int) -> str:
    secret = config.ASSET_SIGNING_SECRET.encode("utf-8")
    if len(secret) < 32:
        raise ValueError("Private Lookbook export signing is not configured")
    return hmac.new(secret, f"{export_id}:{expires}".encode("utf-8"), hashlib.sha256).hexdigest()


def package_export_list(rows: Any) -> dict[str, Any]:
    """Public list shape for package exports (shared by both backends); file state is observed, never repaired."""
    now = int(time.time())
    package_dir = _lookbook_package_dir()
    items = []
    for row in rows:
        value = dict(row)
        status = "expired" if row["expires_at"] < now else "available"
        storage_key = value.get("storage_key")
        if status == "available":
            if (not isinstance(storage_key, str) or not storage_key
                    or Path(storage_key).name != storage_key or "/" in storage_key or "\\" in storage_key):
                status = "missing"
            else:
                try:
                    file_info = (package_dir / storage_key).lstat()
                    if not stat.S_ISREG(file_info.st_mode):
                        status = "missing"
                except OSError:
                    status = "missing"
        value["status"] = status
        value.pop("storage_key", None)
        items.append(value)
    return {"items": items, "total": len(items)}


def list_lookbook_output_package_exports(draft_id: str, workspace_id: str) -> dict[str, Any]:
    initialize(); db = _connect()
    try:
        if not db.execute("SELECT 1 FROM lookbook_drafts WHERE draft_id=? AND workspace_id=? AND archived_at IS NULL",
                          (draft_id, workspace_id)).fetchone():
            raise LookupError("Lookbook Draft not found")
        rows = db.execute("""SELECT export_id,package_sha256,package_size_bytes,manifest_sha256,
            snapshot_sha256,output_count,created_at,expires_at,storage_key FROM lookbook_output_package_exports
            WHERE draft_id=? AND workspace_id=? ORDER BY created_at DESC,export_id DESC""",
            (draft_id, workspace_id)).fetchall()
        return package_export_list(rows)
    finally:
        db.close()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_lookbook_package(temp_path: Path, final_path: Path, package_manifest: dict[str, Any],
                           bases: list[tuple[Any, Any]]) -> tuple[str, str, int]:
    """Write the private Lookbook zip (pages + manifest.json) and move it into place.

    Shared by the SQLite and PostgreSQL paths. `bases` is [(output item, Photo output base)]; every source file is
    re-hashed while copying, so a change during packaging is refused. Returns (manifest_sha256, package_sha256, size).
    """
    with zipfile.ZipFile(temp_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for item, base in bases:
            sku_part = re.sub(r"[^A-Za-z0-9._-]+", "_", (item["variant_sku"] or item["product_sku"] or "asset"))[:48]
            ext = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}.get(base["version_media_type"], ".img")
            filename = f"pages/page_{int(item['page_order']):03d}_{sku_part}_{item['asset_version_id']}{ext}"
            root = config.ASSET_STORAGE_DIR.resolve()
            source_path = (root / base["version_storage_key"]).resolve()
            if source_path.parent != root or not source_path.is_file():
                raise ValueError("A Lookbook output file is missing from private storage")
            digest = hashlib.sha256(); copied = 0
            with source_path.open("rb") as source, archive.open(filename, "w") as target:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    copied += len(chunk); digest.update(chunk); target.write(chunk)
            if copied != int(base["version_size_bytes"]) or digest.hexdigest() != item["checksum_sha256"]:
                raise ValueError("A Lookbook output changed while the private package was being created")
            package_manifest["outputs"].append({
                "file": filename, "page_order": item["page_order"],
                "asset_id": item["asset_id"], "asset_version_id": item["asset_version_id"],
                "checksum_sha256": item["checksum_sha256"], "size_bytes": copied,
                "product_sku": item["product_sku"], "variant_sku": item["variant_sku"],
                "is_ai_generated": False, "provider_dispatched": False, "credit_charged": False,
                "caption": item["caption"]})
        manifest_bytes = json.dumps(package_manifest, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=False).encode("utf-8")
        archive.writestr("manifest.json", manifest_bytes)
    manifest_hash = hashlib.sha256(manifest_bytes).hexdigest()
    package_hash = _sha256_file(temp_path)
    package_size = temp_path.stat().st_size
    os.replace(temp_path, final_path)
    return manifest_hash, package_hash, package_size


def create_lookbook_output_package(draft_id: str, workspace_id: str, actor_id: str) -> dict[str, Any]:
    initialize()
    from app.photo_engine import _photo_output_base, _verify_photo_output_version
    db = _connect()
    temp_path: Path | None = None
    final_path: Path | None = None
    export_id = "lbx_" + uuid.uuid4().hex
    try:
        # Validate signing configuration before creating any package/audit artifact.
        _lookbook_package_signature(export_id, int(time.time()) + 15 * 60)
        draft = db.execute("SELECT * FROM lookbook_drafts WHERE draft_id=? AND workspace_id=? AND archived_at IS NULL",
                           (draft_id, workspace_id)).fetchone()
        if not draft:
            raise LookupError("Lookbook Draft not found")
        if draft["workflow_status"] != "APPROVED":
            raise ValueError("Lookbook planning draft must be approved before package export")
        current, snapshot, snapshot_hash = _verified_lookbook_output_snapshot(db, draft_id, workspace_id)
        latest = db.execute("SELECT * FROM lookbook_output_assembly_review_events WHERE draft_id=? ORDER BY rowid DESC LIMIT 1",
                            (draft_id,)).fetchone()
        if not latest or latest["decision"] != "approved" or latest["snapshot_sha256"] != snapshot_hash:
            raise ValueError("Lookbook output assembly must be separately approved before package export")
        if len(current) > 100:
            raise ValueError("Lookbook package is limited to 100 output pages")
        bases = []
        total_input_bytes = 0
        for item in current:
            run = db.execute("SELECT draft_id FROM photo_processing_runs WHERE run_id=? AND workspace_id=? AND status='succeeded'",
                             (item["photo_run_id"], workspace_id)).fetchone()
            base = _photo_output_base(db, run["draft_id"], item["photo_run_id"], workspace_id) if run else None
            if not base or not _verify_photo_output_version(base):
                raise ValueError("A Lookbook output failed immutable AssetVersion integrity checks")
            total_input_bytes += int(base["version_size_bytes"])
            if total_input_bytes > 250 * 1024 * 1024:
                raise ValueError("Lookbook private package exceeds the 250 MiB input limit")
            bases.append((item, base))
        package_dir = _lookbook_package_dir()
        final_path = package_dir / f"{export_id}.zip"
        temp_path = package_dir / f".{export_id}.tmp"
        package_manifest = {
            "manifest_type": "AI_CREATOR_STUDIO_PRIVATE_LOOKBOOK_PACKAGE",
            "manifest_version": 1,
            "draft_id": draft_id,
            "workspace_id": workspace_id,
            "output_assembly_approved": True,
            "output_assembly_approved_by": latest["actor_id"],
            "output_assembly_reviewed_at": latest["created_at"],
            "output_assembly_snapshot_sha256": snapshot_hash,
            "is_ai_generated": False,
            "provider_dispatched": False,
            "credit_charged": False,
            "planning_approved_by": draft["reviewed_by"],
            "planning_approved_at": draft["reviewed_at"],
            "planning_input": json.loads(draft["payload_json"]),
            "publication_authorized": False,
            "commercial_rights_verified": False,
            "public_distribution_authorized": False,
            "internal_use_only": True,
            "binary_files_included": True,
            "outputs": [],
            "notice": "Private internal-use package only. No publication, public distribution or commercial-use rights are granted.",
        }
        manifest_hash, package_hash, package_size = write_lookbook_package(temp_path, final_path, package_manifest, bases)
        created_at = _now()
        expires_at = int(time.time()) + 24 * 60 * 60
        db.execute("BEGIN IMMEDIATE")
        # Revalidate approval and sequence immediately before recording the private package.
        latest_now = db.execute("SELECT * FROM lookbook_output_assembly_review_events WHERE draft_id=? ORDER BY rowid DESC LIMIT 1",
                                (draft_id,)).fetchone()
        _, _, snapshot_hash_now = _verified_lookbook_output_snapshot(db, draft_id, workspace_id)
        if (not latest_now or latest_now["decision"] != "approved"
                or latest_now["snapshot_sha256"] != snapshot_hash_now
                or snapshot_hash_now != snapshot_hash):
            raise ValueError("Approved Lookbook assembly changed before package audit could be committed")
        storage_key = final_path.name
        download_expires = min(expires_at, int(time.time()) + 15 * 60)
        signature = _lookbook_package_signature(export_id, download_expires)
        db.execute("""INSERT INTO lookbook_output_package_exports(export_id,draft_id,workspace_id,actor_id,
            storage_key,package_sha256,package_size_bytes,manifest_sha256,snapshot_sha256,output_count,
            created_at,expires_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (export_id, draft_id, workspace_id, actor_id, storage_key, package_hash, package_size,
             manifest_hash, snapshot_hash, len(current), created_at, expires_at))
        db.commit()
        return {"export_id": export_id, "package_sha256": package_hash,
                "package_size_bytes": package_size, "manifest_sha256": manifest_hash,
                "output_count": len(current), "created_at": created_at, "expires_at": expires_at,
                "download_url": f"/v1/lookbook-drafts/exports/{export_id}/download?expires={download_expires}&signature={signature}",
                "internal_use_only": True, "publication_authorized": False,
                "commercial_rights_verified": False}
    except Exception:
        db.rollback()
        if temp_path and temp_path.exists():
            temp_path.unlink(missing_ok=True)
        if final_path and final_path.exists():
            final_path.unlink(missing_ok=True)
        raise
    finally:
        db.close()


def download_lookbook_output_package(export_id: str, expires: int, signature: str, user_id: str, *, fetch_row=None, authorize=None):
    now = int(time.time())
    if expires < now or expires > now + 901:
        raise HTTPException(status_code=403, detail="Lookbook package download URL expired or invalid")
    try:
        expected = _lookbook_package_signature(export_id, expires)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=403, detail="Invalid Lookbook package download signature")
    if fetch_row is not None:
        row = fetch_row(export_id)
    else:
        initialize(); db = _connect()
        try:
            row = db.execute("SELECT * FROM lookbook_output_package_exports WHERE export_id=?", (export_id,)).fetchone()
        finally:
            db.close()
    if not row:
        raise HTTPException(status_code=404, detail="Lookbook package export not found")
    # Signed URLs are short-lived bearer credentials, but they do not replace current
    # workspace authorization. Membership/role changes take effect immediately.
    (authorize or require_role)(row["workspace_id"], user_id, {"owner", "admin", "editor", "viewer"})
    if int(row["expires_at"]) < now or expires > int(row["expires_at"]):
        raise HTTPException(status_code=410, detail="Lookbook package export expired")
    package_dir = _lookbook_package_dir()
    storage_key = row["storage_key"]
    if not storage_key or Path(storage_key).name != storage_key:
        raise HTTPException(status_code=409, detail="Lookbook package storage reference is invalid")
    candidate = package_dir / storage_key
    try:
        entry_info = candidate.lstat()
    except OSError:
        raise HTTPException(status_code=410, detail="Lookbook package file is unavailable")
    if not stat.S_ISREG(entry_info.st_mode):
        raise HTTPException(status_code=409, detail="Lookbook package storage entry is not a regular file")
    path = candidate.resolve()
    if path.parent != package_dir or not path.is_file():
        raise HTTPException(status_code=410, detail="Lookbook package file is unavailable")
    try:
        actual_size = path.stat().st_size
        digest = _sha256_file(path)
    except OSError as exc:
        raise HTTPException(status_code=409, detail="Lookbook package file cannot be read") from exc
    if actual_size != int(row["package_size_bytes"]) or digest != row["package_sha256"]:
        raise HTTPException(status_code=409, detail="Lookbook package file integrity check failed")
    try:
        return open_private_file_response(path, media_type="application/zip",
            filename=f"lookbook-{row['draft_id']}.zip", expected_size=int(row["package_size_bytes"]),
            expected_sha256=row["package_sha256"])
    except PrivateFileError as exc:
        raise HTTPException(status_code=409, detail="Lookbook package failed descriptor integrity validation") from exc


def export_approved_manifest(draft_id: str, workspace_id: str) -> dict[str, Any]:
    initialize(); db = _connect()
    try:
        row = db.execute("SELECT * FROM lookbook_drafts WHERE draft_id=? AND workspace_id=? AND archived_at IS NULL", (draft_id, workspace_id)).fetchone()
        if not row: raise LookupError("Lookbook Draft not found")
        if row["workflow_status"] != "APPROVED":
            raise HTTPException(status_code=409, detail="Only approved Lookbook planning drafts can export a manifest")
        assets = db.execute("SELECT asset_id,role FROM lookbook_draft_assets WHERE draft_id=? ORDER BY role,asset_id", (draft_id,)).fetchall()
        return {"manifest_type": "LOOKBOOK_PLAN_ONLY", "generated_outputs_included": False,
                "draft_id": draft_id, "workspace_id": workspace_id,
                "workflow_status": row["workflow_status"], "approved_at": row["reviewed_at"],
                "approved_by": row["reviewed_by"], "input": json.loads(row["payload_json"]),
                "referenced_assets": [dict(item) for item in assets]}
    finally: db.close()


def archive_draft(draft_id: str, workspace_id: str, actor_id: str) -> dict[str, Any]:
    initialize(); db = _connect()
    try:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT * FROM lookbook_drafts WHERE draft_id=? AND workspace_id=? AND archived_at IS NULL",
                         (draft_id, workspace_id)).fetchone()
        if not row:
            raise LookupError("Lookbook Draft not found")
        now = _now()
        db.execute("UPDATE lookbook_drafts SET archived_at=?, updated_at=? WHERE draft_id=? AND workspace_id=?",
                   (now, now, draft_id, workspace_id))
        _event(db, draft_id, workspace_id, actor_id, "lookbook.draft_archived")
        result = db.execute("SELECT * FROM lookbook_drafts WHERE draft_id=?", (draft_id,)).fetchone()
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
        total = int(db.execute("SELECT COUNT(*) AS n FROM lookbook_draft_events WHERE draft_id=? AND workspace_id=?",
                               (draft_id, workspace_id)).fetchone()["n"])
        rows = db.execute("SELECT event_id, draft_id, actor_id, event_type, details_json, created_at FROM lookbook_draft_events WHERE draft_id=? AND workspace_id=? ORDER BY created_at DESC, event_id DESC LIMIT ? OFFSET ?",
                          (draft_id, workspace_id, limit, offset)).fetchall()
        items = [{**dict(row), "details": json.loads(row["details_json"])} for row in rows]
        return {"items": items, "total": total, "limit": limit, "offset": offset}
    finally:
        db.close()


@router.post("", status_code=201, response_model=LookbookDraftResponse)
async def create_lookbook_draft(body: LookbookDraftInput, user_id: str = Depends(current_user)):
    try:
        return get_lookbook_draft_port().create(body.workspace_id, user_id, body)
    except Exception as exc:  # noqa: BLE001 - mapped centrally, unknown errors re-raised
        raise_http(exc)


@router.get("", response_model=LookbookDraftListResponse)
async def read_lookbook_drafts(workspace_id: str = Query(min_length=2, max_length=64),
                              include_archived: bool = False,
                              limit: int = Query(default=50, ge=1, le=100),
                              offset: int = Query(default=0, ge=0),
                              user_id: str = Depends(current_user)):
    try:
        return get_lookbook_draft_port().list(workspace_id, user_id, include_archived, limit, offset)
    except Exception as exc:  # noqa: BLE001 - mapped centrally, unknown errors re-raised
        raise_http(exc)


@router.get("/{draft_id}/events", response_model=EventListResponse)
async def read_lookbook_events(draft_id: str, workspace_id: str = Query(min_length=2, max_length=64),
                               limit: int = Query(default=100, ge=1, le=500),
                               offset: int = Query(default=0, ge=0),
                               user_id: str = Depends(current_user)):
    try:
        return get_lookbook_draft_port().events(draft_id, workspace_id, user_id, limit, offset)
    except Exception as exc:  # noqa: BLE001 - mapped centrally, unknown errors re-raised
        raise_http(exc)


@router.get("/{draft_id}", response_model=LookbookDraftResponse)
async def read_lookbook_draft(draft_id: str, workspace_id: str = Query(min_length=2, max_length=64),
                              user_id: str = Depends(current_user)):
    try:
        return get_lookbook_draft_port().get(draft_id, workspace_id, user_id)
    except Exception as exc:  # noqa: BLE001 - mapped centrally, unknown errors re-raised
        raise_http(exc)


@router.put("/{draft_id}", response_model=LookbookDraftResponse)
async def revise_lookbook_draft(draft_id: str, body: LookbookDraftInput, user_id: str = Depends(current_user)):
    try:
        return get_lookbook_draft_port().update(draft_id, body.workspace_id, user_id, body)
    except Exception as exc:  # noqa: BLE001 - mapped centrally, unknown errors re-raised
        raise_http(exc)


@router.post("/{draft_id}/submit", response_model=LookbookDraftResponse)
async def submit_lookbook_for_review(draft_id: str, workspace_id: str = Query(min_length=2, max_length=64),
                                     user_id: str = Depends(current_user)):
    try:
        return get_lookbook_draft_port().submit(draft_id, workspace_id, user_id)
    except Exception as exc:  # noqa: BLE001 - mapped centrally, unknown errors re-raised
        raise_http(exc)


@router.post("/{draft_id}/approve", response_model=LookbookDraftResponse)
async def approve_lookbook_draft(draft_id: str, body: ReviewDecisionInput, workspace_id: str = Query(min_length=2, max_length=64),
                                 user_id: str = Depends(current_user)):
    try:
        return get_lookbook_draft_port().decide(draft_id, workspace_id, user_id, "APPROVED", body.comment)
    except Exception as exc:  # noqa: BLE001 - mapped centrally, unknown errors re-raised
        raise_http(exc)


@router.post("/{draft_id}/request-changes", response_model=LookbookDraftResponse)
async def request_lookbook_changes(draft_id: str, body: ReviewDecisionInput, workspace_id: str = Query(min_length=2, max_length=64),
                                   user_id: str = Depends(current_user)):
    try:
        return get_lookbook_draft_port().decide(draft_id, workspace_id, user_id, "CHANGES_REQUESTED", body.comment)
    except Exception as exc:  # noqa: BLE001 - mapped centrally, unknown errors re-raised
        raise_http(exc)


@router.get("/{draft_id}/outputs", response_model=LookbookOutputListResponse)
async def read_lookbook_outputs(draft_id: str, workspace_id: str = Query(min_length=2, max_length=64),
                                user_id: str = Depends(current_user)):
    try:
        return get_lookbook_draft_port().outputs(draft_id, workspace_id, user_id)
    except Exception as exc:  # noqa: BLE001
        raise_http(exc)


@router.post("/{draft_id}/outputs", status_code=201, response_model=LookbookOutputResponse)
async def attach_lookbook_photo_output(draft_id: str, body: LookbookOutputAttachInput,
                                       workspace_id: str = Query(min_length=2, max_length=64),
                                       user_id: str = Depends(current_user)):
    try:
        return get_lookbook_draft_port().attach_output(draft_id, workspace_id, user_id, body)
    except Exception as exc:  # noqa: BLE001
        raise_http(exc)


@router.get("/{draft_id}/outputs/review", response_model=LookbookAssemblyReviewResponse)
async def read_lookbook_output_assembly_review(draft_id: str,
                                               workspace_id: str = Query(min_length=2, max_length=64),
                                               user_id: str = Depends(current_user)):
    try:
        return get_lookbook_draft_port().assembly_review(draft_id, workspace_id, user_id)
    except Exception as exc:  # noqa: BLE001
        raise_http(exc)


@router.post("/{draft_id}/outputs/submit", response_model=LookbookAssemblyReviewResponse)
async def submit_lookbook_output_assembly_review(draft_id: str,
                                                workspace_id: str = Query(min_length=2, max_length=64),
                                                user_id: str = Depends(current_user)):
    try:
        return get_lookbook_draft_port().submit_assembly(draft_id, workspace_id, user_id)
    except Exception as exc:  # noqa: BLE001
        raise_http(exc)


async def _decide_lookbook_output_assembly_route(draft_id: str, body: LookbookAssemblyReviewInput,
                                                 decision: str, workspace_id: str, user_id: str):
    try:
        return get_lookbook_draft_port().decide_assembly(draft_id, workspace_id, user_id, decision, body.comment)
    except Exception as exc:  # noqa: BLE001
        raise_http(exc)


@router.post("/{draft_id}/outputs/approve", response_model=LookbookAssemblyReviewResponse)
async def approve_lookbook_output_assembly(draft_id: str, body: LookbookAssemblyReviewInput,
                                          workspace_id: str = Query(min_length=2, max_length=64),
                                          user_id: str = Depends(current_user)):
    return await _decide_lookbook_output_assembly_route(draft_id, body, "approved", workspace_id, user_id)


@router.post("/{draft_id}/outputs/reject", response_model=LookbookAssemblyReviewResponse)
async def reject_lookbook_output_assembly(draft_id: str, body: LookbookAssemblyReviewInput,
                                         workspace_id: str = Query(min_length=2, max_length=64),
                                         user_id: str = Depends(current_user)):
    return await _decide_lookbook_output_assembly_route(draft_id, body, "rejected", workspace_id, user_id)


@router.get("/{draft_id}/outputs/exports", response_model=LookbookPackageExportListResponse)
async def list_lookbook_output_exports(draft_id: str,
                                       workspace_id: str = Query(min_length=2, max_length=64),
                                       user_id: str = Depends(current_user)):
    try:
        return get_lookbook_draft_port().package_exports(draft_id, workspace_id, user_id)
    except Exception as exc:  # noqa: BLE001 - mapped centrally, unknown errors re-raised
        raise_http(exc)


@router.post("/{draft_id}/outputs/package-export", response_model=LookbookPackageExportResponse)
async def create_lookbook_output_package_route(draft_id: str,
                                               workspace_id: str = Query(min_length=2, max_length=64),
                                               user_id: str = Depends(current_user)):
    try:
        return get_lookbook_draft_port().create_package(draft_id, workspace_id, user_id)
    except Exception as exc:  # noqa: BLE001 - mapped centrally, unknown errors re-raised
        raise_http(exc)


@router.get("/exports/{export_id}/download")
async def download_lookbook_output_package_route(export_id: str, expires: int, signature: str,
                                                 user_id: str = Depends(current_user)):
    try:
        return get_lookbook_draft_port().download_package(export_id, expires, signature, user_id)
    except Exception as exc:  # noqa: BLE001 - mapped centrally, HTTPException passes through
        raise_http(exc)


@router.post("/{draft_id}/outputs/manifest", response_model=ManifestExportResponse)
async def export_lookbook_output_manifest(draft_id: str,
                                          workspace_id: str = Query(min_length=2, max_length=64),
                                          user_id: str = Depends(current_user)):
    try:
        return get_lookbook_draft_port().output_manifest(draft_id, workspace_id, user_id)
    except Exception as exc:  # noqa: BLE001
        raise_http(exc)


@router.get("/{draft_id}/manifest", response_model=LookbookPlanManifestResponse)
async def read_approved_lookbook_manifest(draft_id: str, workspace_id: str = Query(min_length=2, max_length=64),
                                          user_id: str = Depends(current_user)):
    try:
        return get_lookbook_draft_port().plan_manifest(draft_id, workspace_id, user_id)
    except Exception as exc:  # noqa: BLE001 - mapped centrally, unknown errors re-raised
        raise_http(exc)


@router.post("/{draft_id}/archive", response_model=LookbookDraftResponse)
async def archive_lookbook_draft(draft_id: str, workspace_id: str = Query(min_length=2, max_length=64),
                                 user_id: str = Depends(current_user)):
    try:
        return get_lookbook_draft_port().archive(draft_id, workspace_id, user_id)
    except Exception as exc:  # noqa: BLE001 - mapped centrally, unknown errors re-raised
        raise_http(exc)
