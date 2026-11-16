"""Lane 6: workspace members: list, change role, remove (the "add" call already exists in workspaces.py), and ``GET /v1/me`` (who am I, which workspaces, which role).

Who may do what: everyone in the workspace reads the member list (ids and roles only: names and e-mail addresses are kept by the sign-in service, not here).
The OWNER may change any non-owner's role (to admin / editor / viewer) and remove any non-owner. An ADMIN may switch editors and viewers between editor and viewer and remove editors and viewers;
an admin cannot make or unmake another admin. Any member may leave (remove themselves), except the owner: the owner role is never changed or removed here (ownership transfer is not built).
Every change is written to an append-only history (who, whom, from role, to role, when).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict

from app.assets import store
from app.assets.routes import current_user, require_role

router = APIRouter(tags=["members"])
READERS = {"owner", "admin", "editor", "viewer"}


def _init(db) -> None:
    db.execute("""CREATE TABLE IF NOT EXISTS workspace_member_events (
        event_id INTEGER PRIMARY KEY AUTOINCREMENT, workspace_id TEXT NOT NULL, at TEXT NOT NULL, actor_id TEXT NOT NULL, member_id TEXT NOT NULL, event TEXT NOT NULL,
        from_role TEXT, to_role TEXT)""")
    for kind in ("UPDATE", "DELETE"):
        db.execute(f"""CREATE TRIGGER IF NOT EXISTS trg_member_events_no_{kind.lower()} BEFORE {kind} ON workspace_member_events
            BEGIN SELECT RAISE(ABORT, 'member history is append-only'); END""")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class MemberOut(BaseModel):
    user_id: str
    role: Literal["owner", "admin", "editor", "viewer"]
    created_at: str


class MemberListOut(BaseModel):
    items: list[MemberOut]


class RolePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["admin", "editor", "viewer"]


class MeWorkspace(BaseModel):
    workspace_id: str
    role: Literal["owner", "admin", "editor", "viewer"]


class MeOut(BaseModel):
    user_id: str
    workspaces: list[MeWorkspace]


def _event(db, workspace_id: str, actor: str, member: str, event: str, old: str | None, new: str | None) -> None:
    db.execute("INSERT INTO workspace_member_events(workspace_id, at, actor_id, member_id, event, from_role, to_role) VALUES (?,?,?,?,?,?,?)", (workspace_id, _now(), actor, member, event, old, new))


@router.get("/v1/me", response_model=MeOut, operation_id="getMe")
async def me(user_id: str = Depends(current_user)):
    """The caller's id and the workspaces they belong to (with their role). No name or e-mail: the server does not know them."""
    return {"user_id": user_id, "workspaces": [{"workspace_id": w["workspace_id"], "role": w["role"]} for w in store.list_workspaces(user_id)]}


@router.get("/v1/workspaces/{workspace_id}/members", response_model=MemberListOut, operation_id="listWorkspaceMembers")
async def list_members(workspace_id: str, user_id: str = Depends(current_user)):
    require_role(workspace_id, user_id, READERS)
    with store._connect() as db:
        store.initialize()
        rows = db.execute("SELECT user_id, role, created_at FROM workspace_members WHERE workspace_id=? ORDER BY CASE role WHEN 'owner' THEN 0 WHEN 'admin' THEN 1 WHEN 'editor' THEN 2 ELSE 3 END, created_at, user_id",
                          (workspace_id,)).fetchall()
    return {"items": [dict(r) for r in rows]}


def _target(db, workspace_id: str, member_id: str):
    row = db.execute("SELECT role FROM workspace_members WHERE workspace_id=? AND user_id=?", (workspace_id, member_id)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Member not found")
    return row["role"]


@router.patch("/v1/workspaces/{workspace_id}/members/{member_id}", response_model=MemberOut, operation_id="changeWorkspaceMemberRole")
async def change_role(workspace_id: str, member_id: str, body: RolePatch, user_id: str = Depends(current_user)):
    actor = require_role(workspace_id, user_id, {"owner", "admin"})
    with store._connect() as db:
        store.initialize()
        _init(db)
        old = _target(db, workspace_id, member_id)
        if old == "owner":
            raise HTTPException(status_code=409, detail={"code": "MEMBER_OWNER_PROTECTED", "message": "the owner's role cannot be changed here"})
        if actor == "admin" and (old == "admin" or body.role == "admin"):
            raise HTTPException(status_code=403, detail={"code": "MEMBER_ROLE_FORBIDDEN", "message": "only the owner can make or unmake an admin"})
        if old != body.role:
            db.execute("UPDATE workspace_members SET role=? WHERE workspace_id=? AND user_id=?", (body.role, workspace_id, member_id))
            _event(db, workspace_id, user_id, member_id, "role_changed", old, body.role)
        return dict(db.execute("SELECT user_id, role, created_at FROM workspace_members WHERE workspace_id=? AND user_id=?", (workspace_id, member_id)).fetchone())


@router.delete("/v1/workspaces/{workspace_id}/members/{member_id}", status_code=204, operation_id="removeWorkspaceMember")
async def remove_member(workspace_id: str, member_id: str, user_id: str = Depends(current_user)):
    actor = require_role(workspace_id, user_id, READERS)
    with store._connect() as db:
        store.initialize()
        _init(db)
        old = _target(db, workspace_id, member_id)
        if old == "owner":
            raise HTTPException(status_code=409, detail={"code": "MEMBER_OWNER_PROTECTED", "message": "the owner cannot be removed or leave here"})
        leaving = member_id == user_id
        if not leaving and (actor not in {"owner", "admin"} or (actor == "admin" and old == "admin")):
            raise HTTPException(status_code=403, detail={"code": "MEMBER_ROLE_FORBIDDEN", "message": "you cannot remove this member"})
        db.execute("DELETE FROM workspace_members WHERE workspace_id=? AND user_id=?", (workspace_id, member_id))
        _event(db, workspace_id, user_id, member_id, "left" if leaving else "removed", old, None)
    return None


class EventOut(BaseModel):
    at: str
    actor_id: str
    member_id: str
    event: str
    from_role: str | None
    to_role: str | None


@router.get("/v1/workspaces/{workspace_id}/members-history", response_model=list[EventOut], operation_id="listWorkspaceMemberEvents")
async def member_history(workspace_id: str, user_id: str = Depends(current_user)):
    require_role(workspace_id, user_id, {"owner", "admin"})
    with store._connect() as db:
        store.initialize()
        _init(db)
        rows = db.execute("SELECT at, actor_id, member_id, event, from_role, to_role FROM workspace_member_events WHERE workspace_id=? ORDER BY event_id", (workspace_id,)).fetchall()
    return [dict(r) for r in rows]
