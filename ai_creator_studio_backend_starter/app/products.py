"""Workspace-scoped product/SKU catalog for non-billable Lookbook planning."""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

from app.viewer_responses import ProductListResponse, ProductResponse, ProductVariantListResponse, ProductVariantResponse, EventListResponse
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.assets.routes import current_user
from app.ports.products import get_product_port
from app.repo_errors import raise_http
from app.assets.store import initialize as initialize_assets
from app.storage import get_storage
from app import config

router = APIRouter(prefix="/v1/products", tags=["product-catalog"])


class ProductInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    workspace_id: str = Field(min_length=2, max_length=64)
    sku: str = Field(min_length=2, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]+$")
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    category: str = Field(default="general", min_length=1, max_length=64)
    image_asset_ids: list[str] = Field(min_length=1, max_length=12)

    @field_validator("image_asset_ids")
    @classmethod
    def unique_image_ids(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)) or any(not value.strip() or len(value) > 80 for value in values):
            raise ValueError("image_asset_ids must contain unique asset identifiers")
        return values

    @field_validator("sku")
    @classmethod
    def normalize_sku(cls, value: str) -> str:
        return value.upper()


class ProductVariantInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    workspace_id: str = Field(min_length=2, max_length=64)
    sku: str = Field(min_length=2, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]+$")
    option_values: dict[str, str] = Field(min_length=1, max_length=12)
    image_asset_ids: list[str] = Field(default_factory=list, max_length=12)

    @field_validator("sku")
    @classmethod
    def normalize_variant_sku(cls, value: str) -> str:
        return value.upper()

    @field_validator("option_values")
    @classmethod
    def validate_options(cls, value: dict[str, str]) -> dict[str, str]:
        normalized: dict[str, str] = {}
        for key, item in value.items():
            name = key.strip().lower()
            if not name or len(name) > 40 or not name.replace("_", "").isalnum():
                raise ValueError("Variant option names must be short alphanumeric identifiers")
            if not isinstance(item, str) or not item.strip() or len(item.strip()) > 80:
                raise ValueError("Variant option values must be non-empty strings up to 80 characters")
            if name in normalized:
                raise ValueError("Variant option names must be unique after normalization")
            normalized[name] = item.strip()
        return normalized

    @field_validator("image_asset_ids")
    @classmethod
    def unique_variant_images(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)) or any(not value.strip() or len(value) > 80 for value in values):
            raise ValueError("image_asset_ids must contain unique asset identifiers")
        return values


def _connect() -> sqlite3.Connection:
    return get_storage().connect(config.ASSET_DATABASE_PATH)


def initialize() -> None:
    initialize_assets()
    db = _connect()
    try:
        db.execute("""CREATE TABLE IF NOT EXISTS products (
            product_id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, sku TEXT NOT NULL COLLATE NOCASE,
            name TEXT NOT NULL, description TEXT, category TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('ACTIVE','ARCHIVED')),
            created_by TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            archived_at TEXT, UNIQUE(workspace_id, sku)
        )""")
        db.execute("CREATE INDEX IF NOT EXISTS idx_products_workspace_status ON products(workspace_id, status, updated_at)")
        db.execute("""CREATE TABLE IF NOT EXISTS product_assets (
            product_id TEXT NOT NULL REFERENCES products(product_id),
            asset_id TEXT NOT NULL REFERENCES assets(asset_id),
            sort_order INTEGER NOT NULL, role TEXT NOT NULL CHECK(role IN ('primary','gallery')),
            PRIMARY KEY(product_id, asset_id)
        )""")
        db.execute("CREATE INDEX IF NOT EXISTS idx_product_assets_asset ON product_assets(asset_id)")
        db.execute("""CREATE TABLE IF NOT EXISTS product_events (
            event_id TEXT PRIMARY KEY, product_id TEXT NOT NULL REFERENCES products(product_id),
            workspace_id TEXT NOT NULL, actor_id TEXT NOT NULL, event_type TEXT NOT NULL,
            details_json TEXT NOT NULL, created_at TEXT NOT NULL
        )""")
        db.execute("CREATE INDEX IF NOT EXISTS idx_product_events ON product_events(product_id, created_at DESC)")
        db.execute("""CREATE TABLE IF NOT EXISTS product_variants (
            variant_id TEXT PRIMARY KEY, product_id TEXT NOT NULL REFERENCES products(product_id),
            workspace_id TEXT NOT NULL, sku TEXT NOT NULL COLLATE NOCASE,
            option_values_json TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('ACTIVE','ARCHIVED')),
            created_by TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            archived_at TEXT, UNIQUE(workspace_id, sku)
        )""")
        db.execute("CREATE INDEX IF NOT EXISTS idx_product_variants_product ON product_variants(product_id,status,updated_at)")
        db.execute("""CREATE TABLE IF NOT EXISTS product_variant_assets (
            variant_id TEXT NOT NULL REFERENCES product_variants(variant_id),
            asset_id TEXT NOT NULL REFERENCES assets(asset_id), sort_order INTEGER NOT NULL,
            PRIMARY KEY(variant_id,asset_id)
        )""")
        db.execute("CREATE INDEX IF NOT EXISTS idx_product_variant_assets_asset ON product_variant_assets(asset_id)")
        db.executescript("""
        CREATE TRIGGER IF NOT EXISTS trg_product_assets_workspace_insert
        BEFORE INSERT ON product_assets BEGIN
            SELECT CASE WHEN NOT EXISTS (
                SELECT 1 FROM products p JOIN assets a ON a.asset_id=NEW.asset_id
                WHERE p.product_id=NEW.product_id AND p.workspace_id=a.workspace_id
            ) THEN RAISE(ABORT, 'product asset workspace mismatch') END;
        END;
        CREATE TRIGGER IF NOT EXISTS trg_product_assets_workspace_update
        BEFORE UPDATE OF product_id,asset_id ON product_assets BEGIN
            SELECT CASE WHEN NOT EXISTS (
                SELECT 1 FROM products p JOIN assets a ON a.asset_id=NEW.asset_id
                WHERE p.product_id=NEW.product_id AND p.workspace_id=a.workspace_id
            ) THEN RAISE(ABORT, 'product asset workspace mismatch') END;
        END;
        CREATE TRIGGER IF NOT EXISTS trg_product_variant_assets_workspace_insert
        BEFORE INSERT ON product_variant_assets BEGIN
            SELECT CASE WHEN NOT EXISTS (
                SELECT 1 FROM product_variants pv JOIN products p ON p.product_id=pv.product_id
                JOIN assets a ON a.asset_id=NEW.asset_id
                WHERE pv.variant_id=NEW.variant_id AND pv.workspace_id=p.workspace_id
                  AND pv.workspace_id=a.workspace_id
            ) THEN RAISE(ABORT, 'product variant asset workspace mismatch') END;
        END;
        CREATE TRIGGER IF NOT EXISTS trg_product_variant_assets_workspace_update
        BEFORE UPDATE OF variant_id,asset_id ON product_variant_assets BEGIN
            SELECT CASE WHEN NOT EXISTS (
                SELECT 1 FROM product_variants pv JOIN products p ON p.product_id=pv.product_id
                JOIN assets a ON a.asset_id=NEW.asset_id
                WHERE pv.variant_id=NEW.variant_id AND pv.workspace_id=p.workspace_id
                  AND pv.workspace_id=a.workspace_id
            ) THEN RAISE(ABORT, 'product variant asset workspace mismatch') END;
        END;
        """)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _event(db: sqlite3.Connection, product_id: str, workspace_id: str, actor_id: str,
           event_type: str, details: dict[str, Any] | None = None) -> None:
    db.execute("INSERT INTO product_events(event_id,product_id,workspace_id,actor_id,event_type,details_json,created_at) VALUES(?,?,?,?,?,?,?)",
               ("pev_" + uuid.uuid4().hex, product_id, workspace_id, actor_id, event_type,
                json.dumps(details or {}, ensure_ascii=False, separators=(",", ":")), _now()))


def _validate_images(db: sqlite3.Connection, workspace_id: str, asset_ids: list[str]) -> None:
    placeholders = ",".join("?" for _ in asset_ids)
    rows = db.execute(f"SELECT asset_id FROM assets WHERE workspace_id=? AND deleted_at IS NULL AND media_type LIKE 'image/%' AND asset_id IN ({placeholders})",
                      (workspace_id, *asset_ids)).fetchall()
    if len(rows) != len(asset_ids):
        raise HTTPException(status_code=422, detail={"code": "PRODUCT_IMAGE_ASSET_REQUIRED",
            "message": "All product images must be active image assets in this workspace."})


def _public(row: sqlite3.Row, db: sqlite3.Connection) -> dict[str, Any]:
    value = dict(row)
    value["image_asset_ids"] = [item["asset_id"] for item in db.execute(
        "SELECT asset_id FROM product_assets WHERE product_id=? ORDER BY sort_order", (row["product_id"],)).fetchall()]
    variants = db.execute("SELECT * FROM product_variants WHERE product_id=? ORDER BY created_at,variant_id", (row["product_id"],)).fetchall()
    value["variants"] = [_variant_public(item, db) for item in variants]
    value["status"] = "archived" if value["archived_at"] else value["status"].lower()
    return value


def _variant_public(row: sqlite3.Row, db: sqlite3.Connection) -> dict[str, Any]:
    value = dict(row)
    value["option_values"] = json.loads(value.pop("option_values_json"))
    value["image_asset_ids"] = [item["asset_id"] for item in db.execute(
        "SELECT asset_id FROM product_variant_assets WHERE variant_id=? ORDER BY sort_order", (row["variant_id"],)).fetchall()]
    value["status"] = "archived" if value["archived_at"] else value["status"].lower()
    return value


def _validate_variant_sku(db: sqlite3.Connection, workspace_id: str, sku: str, *, exclude_variant_id: str | None = None) -> None:
    product = db.execute("SELECT 1 FROM products WHERE workspace_id=? AND sku=? COLLATE NOCASE", (workspace_id, sku)).fetchone()
    query = "SELECT 1 FROM product_variants WHERE workspace_id=? AND sku=? COLLATE NOCASE"
    args: list[Any] = [workspace_id, sku]
    if exclude_variant_id:
        query += " AND variant_id<>?"; args.append(exclude_variant_id)
    variant = db.execute(query, args).fetchone()
    if product or variant:
        raise HTTPException(status_code=409, detail="SKU already exists in this workspace")


def _variant_parent(db: sqlite3.Connection, product_id: str, workspace_id: str) -> sqlite3.Row:
    row = db.execute("SELECT * FROM products WHERE product_id=? AND workspace_id=? AND status='ACTIVE'", (product_id, workspace_id)).fetchone()
    if not row:
        raise LookupError("Product not found")
    return row


def create_variant(product_id: str, body: ProductVariantInput, actor_id: str) -> dict[str, Any]:
    initialize(); variant_id = "pvr_" + uuid.uuid4().hex; now = _now(); db = _connect()
    try:
        db.execute("BEGIN IMMEDIATE")
        _variant_parent(db, product_id, body.workspace_id)
        _validate_variant_sku(db, body.workspace_id, body.sku)
        if body.image_asset_ids:
            _validate_images(db, body.workspace_id, body.image_asset_ids)
        db.execute("INSERT INTO product_variants(variant_id,product_id,workspace_id,sku,option_values_json,status,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
                   (variant_id, product_id, body.workspace_id, body.sku, json.dumps(body.option_values, ensure_ascii=False, separators=(",", ":")), "ACTIVE", actor_id, now, now))
        db.executemany("INSERT INTO product_variant_assets(variant_id,asset_id,sort_order) VALUES(?,?,?)", [(variant_id, aid, i) for i, aid in enumerate(body.image_asset_ids)])
        _event(db, product_id, body.workspace_id, actor_id, "product.variant_created", {"variant_id": variant_id, "sku": body.sku})
        result = _variant_public(db.execute("SELECT * FROM product_variants WHERE variant_id=?", (variant_id,)).fetchone(), db)
        db.commit(); return result
    except Exception:
        db.rollback(); raise
    finally:
        db.close()


def list_variants(product_id: str, workspace_id: str, include_archived: bool = False) -> list[dict[str, Any]]:
    initialize(); db = _connect()
    try:
        _variant_parent(db, product_id, workspace_id)
        where = "product_id=?" + ("" if include_archived else " AND status='ACTIVE'")
        rows = db.execute(f"SELECT * FROM product_variants WHERE {where} ORDER BY created_at,variant_id", (product_id,)).fetchall()
        return [_variant_public(row, db) for row in rows]
    finally:
        db.close()


def _active_lookbook_variant_reference(db: sqlite3.Connection, variant_id: str) -> bool:
    exists = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='lookbook_draft_entities'").fetchone()
    if not exists:
        return False
    return db.execute("""SELECT 1 FROM lookbook_draft_entities e JOIN lookbook_drafts d ON d.draft_id=e.draft_id
        WHERE e.entity_type='product_variant' AND e.entity_id=? AND d.archived_at IS NULL LIMIT 1""", (variant_id,)).fetchone() is not None


def update_variant(product_id: str, variant_id: str, body: ProductVariantInput, actor_id: str) -> dict[str, Any]:
    initialize(); db = _connect()
    try:
        db.execute("BEGIN IMMEDIATE")
        _variant_parent(db, product_id, body.workspace_id)
        row = db.execute("SELECT * FROM product_variants WHERE variant_id=? AND product_id=? AND workspace_id=? AND status='ACTIVE'", (variant_id, product_id, body.workspace_id)).fetchone()
        if not row: raise LookupError("Variant not found")
        if _active_lookbook_variant_reference(db, variant_id):
            raise HTTPException(status_code=409, detail="Variant is referenced by an active Lookbook Draft; archive the draft before editing the Variant")
        _validate_variant_sku(db, body.workspace_id, body.sku, exclude_variant_id=variant_id)
        if body.image_asset_ids: _validate_images(db, body.workspace_id, body.image_asset_ids)
        now = _now()
        db.execute("UPDATE product_variants SET sku=?,option_values_json=?,updated_at=? WHERE variant_id=?",
                   (body.sku, json.dumps(body.option_values, ensure_ascii=False, separators=(",", ":")), now, variant_id))
        db.execute("DELETE FROM product_variant_assets WHERE variant_id=?", (variant_id,))
        db.executemany("INSERT INTO product_variant_assets(variant_id,asset_id,sort_order) VALUES(?,?,?)", [(variant_id, aid, i) for i, aid in enumerate(body.image_asset_ids)])
        _event(db, product_id, body.workspace_id, actor_id, "product.variant_updated", {"variant_id": variant_id, "sku": body.sku})
        result = _variant_public(db.execute("SELECT * FROM product_variants WHERE variant_id=?", (variant_id,)).fetchone(), db)
        db.commit(); return result
    except Exception:
        db.rollback(); raise
    finally:
        db.close()


def archive_variant(product_id: str, variant_id: str, workspace_id: str, actor_id: str) -> dict[str, Any]:
    initialize(); db = _connect()
    try:
        db.execute("BEGIN IMMEDIATE")
        _variant_parent(db, product_id, workspace_id)
        row = db.execute("SELECT * FROM product_variants WHERE variant_id=? AND product_id=? AND workspace_id=? AND status='ACTIVE'", (variant_id, product_id, workspace_id)).fetchone()
        if not row: raise LookupError("Variant not found")
        if _active_lookbook_variant_reference(db, variant_id):
            raise HTTPException(status_code=409, detail="Variant is referenced by an active Lookbook Draft; archive the draft first")
        now = _now(); db.execute("UPDATE product_variants SET status='ARCHIVED',archived_at=?,updated_at=? WHERE variant_id=?", (now, now, variant_id))
        _event(db, product_id, workspace_id, actor_id, "product.variant_archived", {"variant_id": variant_id})
        result = _variant_public(db.execute("SELECT * FROM product_variants WHERE variant_id=?", (variant_id,)).fetchone(), db)
        db.commit(); return result
    except Exception:
        db.rollback(); raise
    finally:
        db.close()


def create_product(body: ProductInput, actor_id: str) -> dict[str, Any]:
    initialize(); product_id = "prd_" + uuid.uuid4().hex; now = _now(); db = _connect()
    try:
        db.execute("BEGIN IMMEDIATE")
        _validate_images(db, body.workspace_id, body.image_asset_ids)
        variant_collision = db.execute("SELECT 1 FROM product_variants WHERE workspace_id=? AND sku=? COLLATE NOCASE", (body.workspace_id, body.sku)).fetchone()
        if variant_collision:
            raise HTTPException(status_code=409, detail="SKU already exists in this workspace")
        db.execute("INSERT INTO products(product_id,workspace_id,sku,name,description,category,status,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                   (product_id, body.workspace_id, body.sku, body.name, body.description, body.category,
                    "ACTIVE", actor_id, now, now))
        db.executemany("INSERT INTO product_assets(product_id,asset_id,sort_order,role) VALUES(?,?,?,?)",
                       [(product_id, asset_id, index, "primary" if index == 0 else "gallery")
                        for index, asset_id in enumerate(body.image_asset_ids)])
        _event(db, product_id, body.workspace_id, actor_id, "product.created", {"sku": body.sku})
        row = db.execute("SELECT * FROM products WHERE product_id=?", (product_id,)).fetchone()
        result = _public(row, db); db.commit(); return result
    except Exception:
        db.rollback(); raise
    finally:
        db.close()


def list_products(workspace_id: str, *, include_archived: bool = False, limit: int = 50, offset: int = 0) -> dict[str, Any]:
    initialize(); db = _connect()
    try:
        where = "workspace_id=?" + ("" if include_archived else " AND status='ACTIVE'")
        total = int(db.execute(f"SELECT COUNT(*) AS n FROM products WHERE {where}", (workspace_id,)).fetchone()["n"])
        rows = db.execute(f"SELECT * FROM products WHERE {where} ORDER BY updated_at DESC, product_id LIMIT ? OFFSET ?",
                          (workspace_id, limit, offset)).fetchall()
        return {"items": [_public(row, db) for row in rows], "total": total, "limit": limit, "offset": offset}
    finally:
        db.close()


def get_product(product_id: str, workspace_id: str) -> dict[str, Any] | None:
    initialize(); db = _connect()
    try:
        row = db.execute("SELECT * FROM products WHERE product_id=? AND workspace_id=?", (product_id, workspace_id)).fetchone()
        return _public(row, db) if row else None
    finally:
        db.close()


def _active_lookbook_product_reference(db: sqlite3.Connection, product_id: str, workspace_id: str) -> bool:
    exists = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='lookbook_draft_entities'").fetchone()
    if not exists:
        return False
    return db.execute("""SELECT 1 FROM lookbook_draft_entities e
        JOIN lookbook_drafts d ON d.draft_id=e.draft_id
        WHERE e.entity_type='product' AND e.entity_id=? AND d.workspace_id=?
          AND d.archived_at IS NULL LIMIT 1""", (product_id, workspace_id)).fetchone() is not None


def update_product(product_id: str, body: ProductInput, actor_id: str) -> dict[str, Any]:
    initialize(); db = _connect()
    try:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT * FROM products WHERE product_id=? AND workspace_id=? AND status='ACTIVE'",
                         (product_id, body.workspace_id)).fetchone()
        if not row:
            raise LookupError("Product not found")
        if _active_lookbook_product_reference(db, product_id, body.workspace_id):
            raise HTTPException(status_code=409, detail="Product is referenced by an active Lookbook Draft; archive the draft before editing the Product")
        _validate_images(db, body.workspace_id, body.image_asset_ids)
        variant_collision = db.execute("SELECT 1 FROM product_variants WHERE workspace_id=? AND sku=? COLLATE NOCASE", (body.workspace_id, body.sku)).fetchone()
        if variant_collision:
            raise HTTPException(status_code=409, detail="SKU already exists in this workspace")
        now = _now()
        db.execute("UPDATE products SET sku=?,name=?,description=?,category=?,updated_at=? WHERE product_id=? AND workspace_id=?",
                   (body.sku, body.name, body.description, body.category, now, product_id, body.workspace_id))
        db.execute("DELETE FROM product_assets WHERE product_id=?", (product_id,))
        db.executemany("INSERT INTO product_assets(product_id,asset_id,sort_order,role) VALUES(?,?,?,?)",
                       [(product_id, asset_id, index, "primary" if index == 0 else "gallery")
                        for index, asset_id in enumerate(body.image_asset_ids)])
        _event(db, product_id, body.workspace_id, actor_id, "product.updated", {"sku": body.sku})
        result = _public(db.execute("SELECT * FROM products WHERE product_id=?", (product_id,)).fetchone(), db)
        db.commit(); return result
    except Exception:
        db.rollback(); raise
    finally:
        db.close()


def archive_product(product_id: str, workspace_id: str, actor_id: str) -> dict[str, Any]:
    initialize(); db = _connect()
    try:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT * FROM products WHERE product_id=? AND workspace_id=? AND status='ACTIVE'",
                         (product_id, workspace_id)).fetchone()
        if not row:
            raise LookupError("Product not found")
        referenced = db.execute("""SELECT 1 FROM lookbook_draft_entities e
            JOIN lookbook_drafts d ON d.draft_id=e.draft_id
            WHERE e.entity_type='product' AND e.entity_id=? AND d.workspace_id=? AND d.archived_at IS NULL LIMIT 1""",
            (product_id, workspace_id)).fetchone() if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='lookbook_draft_entities'").fetchone() else None
        if referenced:
            raise HTTPException(status_code=409, detail="Product is referenced by an active Lookbook Draft; archive the draft first")
        assignment_table = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='project_product_assignments'").fetchone()
        if assignment_table:
            assigned = db.execute("""SELECT 1 FROM project_product_assignments a JOIN projects p ON p.project_id=a.project_id
                WHERE a.product_id=? AND a.removed_at IS NULL AND p.status='ACTIVE' LIMIT 1""", (product_id,)).fetchone()
            if assigned:
                raise HTTPException(status_code=409, detail="Product is assigned to an active Project; remove the assignment first")
        now = _now()
        db.execute("UPDATE product_variants SET status='ARCHIVED',archived_at=?,updated_at=? WHERE product_id=? AND status='ACTIVE'", (now, now, product_id))
        db.execute("UPDATE products SET status='ARCHIVED',archived_at=?,updated_at=? WHERE product_id=?", (now, now, product_id))
        _event(db, product_id, workspace_id, actor_id, "product.archived")
        result = _public(db.execute("SELECT * FROM products WHERE product_id=?", (product_id,)).fetchone(), db)
        db.commit(); return result
    except Exception:
        db.rollback(); raise
    finally:
        db.close()


def list_events(product_id: str, workspace_id: str, *, limit: int = 100, offset: int = 0) -> dict[str, Any]:
    initialize(); db = _connect()
    try:
        total = int(db.execute("SELECT COUNT(*) AS n FROM product_events WHERE product_id=? AND workspace_id=?",
                               (product_id, workspace_id)).fetchone()["n"])
        rows = db.execute("SELECT event_id,product_id,actor_id,event_type,details_json,created_at FROM product_events WHERE product_id=? AND workspace_id=? ORDER BY created_at DESC,event_id DESC LIMIT ? OFFSET ?",
                          (product_id, workspace_id, limit, offset)).fetchall()
        return {"items": [{**dict(row), "details": json.loads(row["details_json"])} for row in rows],
                "total": total, "limit": limit, "offset": offset}
    finally:
        db.close()


@router.post("", status_code=201, response_model=ProductResponse)
async def create_product_route(body: ProductInput, user_id: str = Depends(current_user)):
    try:
        return get_product_port().create(user_id, body.model_dump())
    except Exception as exc:
        raise_http(exc)


@router.get("", response_model=ProductListResponse)
async def list_products_route(workspace_id: str = Query(min_length=2, max_length=64),
                             include_archived: bool = False,
                             limit: int = Query(default=50, ge=1, le=100),
                             offset: int = Query(default=0, ge=0), user_id: str = Depends(current_user)):
    try:
        return get_product_port().list(workspace_id, user_id, include_archived, limit, offset)
    except Exception as exc:
        raise_http(exc)


@router.get("/{product_id}", response_model=ProductResponse)
async def read_product_route(product_id: str, workspace_id: str = Query(min_length=2, max_length=64),
                             user_id: str = Depends(current_user)):
    try:
        return get_product_port().get(workspace_id, product_id, user_id)
    except Exception as exc:
        raise_http(exc)


@router.put("/{product_id}", response_model=ProductResponse)
async def update_product_route(product_id: str, body: ProductInput, user_id: str = Depends(current_user)):
    try:
        return get_product_port().update(product_id, user_id, body.model_dump())
    except Exception as exc:
        raise_http(exc)


@router.post("/{product_id}/archive", response_model=ProductResponse)
async def archive_product_route(product_id: str, workspace_id: str = Query(min_length=2, max_length=64),
                                user_id: str = Depends(current_user)):
    try:
        return get_product_port().archive(workspace_id, product_id, user_id)
    except Exception as exc:
        raise_http(exc)


@router.post("/{product_id}/variants", status_code=201, response_model=ProductVariantResponse)
async def create_product_variant(product_id: str, body: ProductVariantInput, user_id: str = Depends(current_user)):
    try:
        return get_product_port().create_variant(product_id, user_id, body.model_dump())
    except Exception as exc:
        raise_http(exc)


@router.get("/{product_id}/variants", response_model=ProductVariantListResponse)
async def read_product_variants(product_id: str, workspace_id: str = Query(min_length=2, max_length=64),
                                include_archived: bool = False, user_id: str = Depends(current_user)):
    try:
        return get_product_port().list_variants(workspace_id, product_id, user_id, include_archived)
    except Exception as exc:
        raise_http(exc)


@router.put("/{product_id}/variants/{variant_id}", response_model=ProductVariantResponse)
async def update_product_variant(product_id: str, variant_id: str, body: ProductVariantInput, user_id: str = Depends(current_user)):
    try:
        return get_product_port().update_variant(product_id, variant_id, user_id, body.model_dump())
    except Exception as exc:
        raise_http(exc)


@router.post("/{product_id}/variants/{variant_id}/archive", response_model=ProductVariantResponse)
async def archive_product_variant(product_id: str, variant_id: str, workspace_id: str = Query(min_length=2, max_length=64),
                                  user_id: str = Depends(current_user)):
    try:
        return get_product_port().archive_variant(workspace_id, product_id, variant_id, user_id)
    except Exception as exc:
        raise_http(exc)


@router.get("/{product_id}/events", response_model=EventListResponse)
async def read_product_events(product_id: str, workspace_id: str = Query(min_length=2, max_length=64),
                              limit: int = Query(default=100, ge=1, le=500),
                              offset: int = Query(default=0, ge=0), user_id: str = Depends(current_user)):
    try:
        return get_product_port().events(workspace_id, product_id, user_id, limit, offset)
    except Exception as exc:
        raise_http(exc)
