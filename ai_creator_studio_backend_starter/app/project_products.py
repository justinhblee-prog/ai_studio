"""Workspace-safe Project ↔ Product assignments with retained assignment history."""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone

from app.schema_util import add_column
from app.viewer_responses import ProjectProductListResponse, EventListResponse
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.assets.routes import current_user
from app.ports.project_products import get_project_product_port
from app.repo_errors import raise_http
from app.assets.store import workspace_role
from app.projects import _initialize as initialize_projects
from app.products import initialize as initialize_products, _public as product_public, _connect

router = APIRouter(prefix="/v1/projects", tags=["project-products"])


class ProjectProductsInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    product_ids: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("product_ids")
    @classmethod
    def unique_ids(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)) or any(not value.strip() or len(value) > 80 for value in values):
            raise ValueError("product_ids must contain unique non-empty identifiers")
        return values


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def initialize() -> None:
    initialize_projects(); initialize_products()
    with _connect() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS project_product_assignments (
            assignment_id TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL,
            project_id TEXT NOT NULL REFERENCES projects(project_id),
            product_id TEXT NOT NULL REFERENCES products(product_id),
            assigned_by TEXT NOT NULL,
            assigned_at TEXT NOT NULL,
            removed_at TEXT,
            sort_order INTEGER NOT NULL DEFAULT 0
        )""")
        columns = {row["name"] for row in db.execute("PRAGMA table_info(project_product_assignments)").fetchall()}
        if "sort_order" not in columns:
            add_column(db, "ALTER TABLE project_product_assignments ADD COLUMN sort_order INTEGER NOT NULL DEFAULT 0")
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_project_product_active ON project_product_assignments(project_id,product_id) WHERE removed_at IS NULL")
        db.execute("CREATE INDEX IF NOT EXISTS idx_project_product_workspace ON project_product_assignments(workspace_id,project_id,removed_at,assigned_at)")
        db.execute("""CREATE TABLE IF NOT EXISTS project_product_events (
            event_id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, project_id TEXT NOT NULL,
            actor_id TEXT NOT NULL, event_type TEXT NOT NULL, details_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )""")
        db.execute("CREATE INDEX IF NOT EXISTS idx_project_product_events ON project_product_events(project_id,created_at DESC,event_id DESC)")


def _project(db: sqlite3.Connection, project_id: str):
    return db.execute("SELECT * FROM projects WHERE project_id=?", (project_id,)).fetchone()


def _get_project(project_id: str):
    db = _connect()
    try:
        return _project(db, project_id)
    finally:
        db.close()


def _require_role(workspace_id: str, user_id: str, write: bool = False) -> None:
    role = workspace_role(workspace_id, user_id)
    if role is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    if write and role not in {"owner", "admin", "editor"}:
        raise HTTPException(status_code=403, detail="Insufficient workspace role")


def list_project_products(project_id: str, workspace_id: str) -> dict:
    initialize()
    db = _connect()
    try:
        project = _project(db, project_id)
        if project is None or project["workspace_id"] != workspace_id:
            raise LookupError("Project not found")
        rows = db.execute("""SELECT p.* FROM project_product_assignments a
            JOIN products p ON p.product_id=a.product_id
            WHERE a.project_id=? AND a.workspace_id=? AND a.removed_at IS NULL AND p.status='ACTIVE'
            ORDER BY a.sort_order,a.assigned_at,a.assignment_id""", (project_id, workspace_id)).fetchall()
        return {"project_id": project_id, "workspace_id": workspace_id,
                "items": [product_public(row, db) for row in rows], "total": len(rows)}
    finally:
        db.close()


def replace_project_products(project_id: str, workspace_id: str, product_ids: list[str], actor_id: str) -> dict:
    initialize(); db = _connect()
    try:
        db.execute("BEGIN IMMEDIATE")
        project = _project(db, project_id)
        if project is None or project["workspace_id"] != workspace_id:
            raise LookupError("Project not found")
        if project["status"] != "ACTIVE":
            raise HTTPException(status_code=409, detail="Products can only be assigned to an ACTIVE Project")
        if product_ids:
            marks = ",".join("?" for _ in product_ids)
            found = db.execute(f"SELECT product_id FROM products WHERE workspace_id=? AND status='ACTIVE' AND product_id IN ({marks})",
                               (workspace_id, *product_ids)).fetchall()
            if len(found) != len(product_ids):
                raise HTTPException(status_code=422, detail="Every Product must be active in this workspace")
        existing_rows = db.execute("SELECT product_id,sort_order FROM project_product_assignments WHERE project_id=? AND removed_at IS NULL", (project_id,)).fetchall()
        existing = {row["product_id"] for row in existing_rows}
        existing_order = {row["product_id"]: row["sort_order"] for row in existing_rows}
        requested = set(product_ids)
        removed, added = sorted(existing - requested), [product_id for product_id in product_ids if product_id not in existing]
        reordered = any(existing_order.get(product_id) != index for index, product_id in enumerate(product_ids) if product_id in existing)
        now = _now()
        if removed:
            marks = ",".join("?" for _ in removed)
            db.execute(f"UPDATE project_product_assignments SET removed_at=? WHERE project_id=? AND removed_at IS NULL AND product_id IN ({marks})",
                       (now, project_id, *removed))
        db.executemany("INSERT INTO project_product_assignments(assignment_id,workspace_id,project_id,product_id,assigned_by,assigned_at,removed_at,sort_order) VALUES(?,?,?,?,?,?,NULL,?)",
                       [("ppa_" + uuid.uuid4().hex, workspace_id, project_id, product_id, actor_id, now, product_ids.index(product_id)) for product_id in added])
        for index, product_id in enumerate(product_ids):
            if product_id in existing:
                db.execute("UPDATE project_product_assignments SET sort_order=? WHERE project_id=? AND product_id=? AND removed_at IS NULL", (index, project_id, product_id))
        if added or removed or reordered:
            db.execute("INSERT INTO project_product_events(event_id,workspace_id,project_id,actor_id,event_type,details_json,created_at) VALUES(?,?,?,?,?,?,?)",
                       ("ppe_" + uuid.uuid4().hex, workspace_id, project_id, actor_id, "project.products_replaced",
                        json.dumps({"added": added, "removed": removed, "reordered": reordered}, separators=(",", ":")), now))
        db.commit()
    except Exception:
        db.rollback(); raise
    finally:
        db.close()
    return list_project_products(project_id, workspace_id)


@router.get("/{project_id}/products", response_model=ProjectProductListResponse)
async def get_project_products(project_id: str, user_id: str = Depends(current_user)):
    try:
        return get_project_product_port().list(project_id, user_id)
    except Exception as exc:
        raise_http(exc)


@router.put("/{project_id}/products", response_model=ProjectProductListResponse)
async def put_project_products(project_id: str, body: ProjectProductsInput, user_id: str = Depends(current_user)):
    try:
        return get_project_product_port().replace(project_id, user_id, body.product_ids)
    except Exception as exc:
        raise_http(exc)


@router.get("/{project_id}/product-events", response_model=EventListResponse)
async def get_project_product_events(project_id: str, user_id: str = Depends(current_user)):
    try:
        return get_project_product_port().events(project_id, user_id)
    except Exception as exc:
        raise_http(exc)
