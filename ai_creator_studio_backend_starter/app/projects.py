"""Workspace-scoped project management. Asset relations and SKU policy remain separate decisions."""
from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Literal

from app.viewer_responses import ProjectListResponse, ProjectResponse
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from app.assets.routes import current_user
from app.assets.store import _connect, initialize as initialize_assets
from app.ports.projects import get_project_port
from app.repo_errors import raise_http

router = APIRouter(prefix="/v1/projects", tags=["projects"])
ProjectStatus = Literal["ACTIVE", "ARCHIVED", "COMPLETED"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _initialize() -> None:
    initialize_assets()
    with _connect() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS projects (
            project_id TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL REFERENCES workspaces(workspace_id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            project_type TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('ACTIVE','ARCHIVED','COMPLETED')),
            description TEXT,
            external_reference TEXT,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )""")
        db.execute("CREATE INDEX IF NOT EXISTS idx_projects_workspace_status ON projects(workspace_id, status, updated_at)")


class ProjectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workspace_id: str = Field(min_length=2, max_length=64)
    name: str = Field(min_length=1, max_length=120)
    project_type: str = Field(default="general", min_length=1, max_length=64)
    description: str | None = Field(default=None, max_length=2000)
    external_reference: str | None = Field(default=None, max_length=128)


class ProjectUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    project_type: str = Field(min_length=1, max_length=64)
    status: ProjectStatus
    description: str | None = Field(default=None, max_length=2000)


def _read(row: sqlite3.Row) -> dict:
    return {key: row[key] for key in (
        "project_id", "workspace_id", "name", "project_type", "status",
        "description", "external_reference", "created_by", "created_at", "updated_at",
    )}


def _get(project_id: str):
    _initialize()
    with _connect() as db:
        return db.execute("SELECT * FROM projects WHERE project_id=?", (project_id,)).fetchone()


@router.post("", status_code=201, response_model=ProjectResponse)
async def create_project(body: ProjectCreate, user_id: str = Depends(current_user)):
    try:
        return get_project_port().create(body.workspace_id, user_id, body.model_dump(exclude={"workspace_id"}))
    except Exception as exc:
        raise_http(exc)


@router.get("", response_model=ProjectListResponse)
async def list_projects(workspace_id: str = Query(min_length=2, max_length=64),
                        status: ProjectStatus | None = None,
                        user_id: str = Depends(current_user)):
    try:
        return get_project_port().list(workspace_id, user_id, status)
    except Exception as exc:
        raise_http(exc)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: str, user_id: str = Depends(current_user)):
    try:
        return get_project_port().get(project_id, user_id)
    except Exception as exc:
        raise_http(exc)


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(project_id: str, body: ProjectUpdate, user_id: str = Depends(current_user)):
    try:
        return get_project_port().update(project_id, user_id, body.model_dump())
    except Exception as exc:
        raise_http(exc)
