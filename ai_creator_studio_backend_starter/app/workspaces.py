"""Workspace creation and membership management with role-based authorization."""
from __future__ import annotations

from typing import Literal
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.assets.routes import current_user
from app.ports.workspace import get_workspace_port
from app.repo_errors import raise_http

router = APIRouter(prefix="/v1/workspaces", tags=["workspaces"])


class CreateWorkspaceBody(BaseModel):
    workspace_id: str = Field(min_length=2, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]+$")


class AddMemberBody(BaseModel):
    user_id: str = Field(min_length=1, max_length=128)
    role: Literal["admin", "editor", "viewer"] = "viewer"


@router.post("", status_code=201)
async def create_workspace_endpoint(body: CreateWorkspaceBody, user_id: str = Depends(current_user)):
    try:
        return get_workspace_port().create(body.workspace_id, user_id)
    except Exception as exc:
        raise_http(exc)


@router.get("")
async def workspaces(user_id: str = Depends(current_user)):
    try:
        return get_workspace_port().list(user_id)
    except Exception as exc:
        raise_http(exc)


@router.post("/{workspace_id}/members", status_code=201)
async def add_member(workspace_id: str, body: AddMemberBody, user_id: str = Depends(current_user)):
    try:
        return get_workspace_port().add_member(workspace_id, user_id, body.user_id, body.role)
    except Exception as exc:
        raise_http(exc)
