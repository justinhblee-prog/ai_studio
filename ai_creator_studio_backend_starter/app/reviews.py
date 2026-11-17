"""R-063: review / approval records for assets of a workspace (the homepage's "검수 요청 → 승인 / 변경 요청 / 반려").

States:  requested -> approved | changes_requested | rejected | withdrawn ;  changes_requested -> requested (re-requested) | withdrawn.
approved, rejected and withdrawn are final for that review (a new review can be opened for the asset later, e.g. for a new version).
Roles (server roles owner / admin / editor / viewer; the homepage's "approver" is an owner or admin here, see docs/AIS_API_CONTRACT.md):
  * request / re-request / withdraw: editor, admin, owner (withdraw: the requester, or an owner/admin)
  * approve / request changes / reject: owner, admin
  * read (list, one review, history, status, export check): everyone in the workspace including viewers
Comments: required for "changes requested" and "rejected" (1..1000 characters), optional for the others.
Every transition is written to an append-only history (the database refuses UPDATE and DELETE on it). Only identifiers, states and the comment text are stored.
``export-check`` answers which assets may be exported: only those whose LATEST review is approved. Wiring it into the existing export endpoints is a separate step.
"""
from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, StrictBool

from app import takedown
from app.assets import store
from app.assets.routes import current_user, require_role

router = APIRouter(prefix="/v1/workspaces/{workspace_id}/reviews", tags=["reviews"])
Status = Literal["requested", "approved", "changes_requested", "rejected", "withdrawn"]
OPEN = ("requested", "changes_requested")
MAX_COMMENT = 1000
WRITERS = {"owner", "admin", "editor"}
DECIDERS = {"owner", "admin"}
READERS = {"owner", "admin", "editor", "viewer"}
# (from, action) -> to
TRANSITIONS = {("requested", "approve"): "approved", ("requested", "request-changes"): "changes_requested", ("requested", "reject"): "rejected",
               ("requested", "withdraw"): "withdrawn", ("changes_requested", "resubmit"): "requested", ("changes_requested", "withdraw"): "withdrawn"}
COMMENT_REQUIRED = {"request-changes", "reject"}


def _init(db) -> None:
    db.execute("""CREATE TABLE IF NOT EXISTS asset_reviews (
        review_id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, asset_id TEXT NOT NULL, status TEXT NOT NULL, requested_by TEXT NOT NULL, requested_at TEXT NOT NULL,
        handled_by TEXT, handled_at TEXT, comment TEXT, updated_at TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1)""")
    db.execute("CREATE INDEX IF NOT EXISTS idx_asset_reviews_ws ON asset_reviews(workspace_id, asset_id, requested_at)")
    try:     # B-08: the database itself refuses a second OPEN review of one asset (two workers asking at the same moment); an old database that already holds a duplicate keeps the check in request_review
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_asset_reviews_one_open ON asset_reviews(workspace_id, asset_id) WHERE status IN ('requested','changes_requested')")
    except Exception:  # noqa: BLE001
        pass
    db.execute("""CREATE TABLE IF NOT EXISTS asset_review_events (
        event_id INTEGER PRIMARY KEY AUTOINCREMENT, review_id TEXT NOT NULL, workspace_id TEXT NOT NULL, at TEXT NOT NULL, actor_id TEXT NOT NULL, actor_role TEXT NOT NULL,
        action TEXT NOT NULL, from_status TEXT, to_status TEXT NOT NULL, comment TEXT)""")
    for kind in ("UPDATE", "DELETE"):
        db.execute(f"""CREATE TRIGGER IF NOT EXISTS trg_asset_review_events_no_{kind.lower()} BEFORE {kind} ON asset_review_events
            BEGIN SELECT RAISE(ABORT, 'review history is append-only'); END""")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class RequestIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    asset_id: str = Field(min_length=3, max_length=80)
    comment: str | None = Field(default=None, max_length=MAX_COMMENT)


class DecideIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    comment: str | None = Field(default=None, max_length=MAX_COMMENT)


class ReviewOut(BaseModel):
    review_id: str
    workspace_id: str
    asset_id: str
    status: Status
    requested_by: str
    requested_at: str
    handled_by: str | None
    handled_at: str | None
    comment: str | None
    updated_at: str
    version: int


class ReviewListOut(BaseModel):
    items: list[ReviewOut]
    total: int


class EventOut(BaseModel):
    at: str
    actor_id: str
    actor_role: str
    action: str
    from_status: str | None
    to_status: str
    comment: str | None


def _public(row) -> dict[str, Any]:
    return {k: row[k] for k in ("review_id", "workspace_id", "asset_id", "status", "requested_by", "requested_at", "handled_by", "handled_at", "comment", "updated_at", "version")}


def _clean(comment: str | None) -> str | None:
    if comment is None:
        return None
    text = "".join(ch for ch in comment if ch in "\n\t" or ord(ch) >= 32).strip()
    return text or None


def _event(db, review_id: str, workspace_id: str, actor: str, role: str, action: str, old: str | None, new: str, comment: str | None) -> None:
    db.execute("INSERT INTO asset_review_events(review_id, workspace_id, at, actor_id, actor_role, action, from_status, to_status, comment) VALUES (?,?,?,?,?,?,?,?,?)",
               (review_id, workspace_id, _now(), actor, role, action, old, new, comment))


@router.post("", status_code=201, response_model=ReviewOut, operation_id="requestAssetReview")
async def request_review(workspace_id: str, body: RequestIn, user_id: str = Depends(current_user)):
    role = require_role(workspace_id, user_id, WRITERS)
    asset = store.get_asset(body.asset_id, workspace_id)
    if asset is None or not takedown.visible_to(body.asset_id, user_id):
        raise HTTPException(status_code=404, detail="Asset not found")
    comment = _clean(body.comment)
    with store._connect() as db:
        _init(db)
        if db.execute("SELECT 1 FROM asset_reviews WHERE workspace_id=? AND asset_id=? AND status IN ('requested','changes_requested')", (workspace_id, body.asset_id)).fetchone():
            raise HTTPException(status_code=409, detail={"code": "REVIEW_ALREADY_OPEN", "message": "this asset already has an open review"})
        review_id, now = "rev_" + uuid.uuid4().hex, _now()
        try:
            db.execute("INSERT INTO asset_reviews(review_id, workspace_id, asset_id, status, requested_by, requested_at, comment, updated_at) VALUES (?,?,?,?,?,?,?,?)",
                       (review_id, workspace_id, body.asset_id, "requested", user_id, now, comment, now))
        except sqlite3.IntegrityError as exc:       # lost the race against another request for the same asset
            raise HTTPException(status_code=409, detail={"code": "REVIEW_ALREADY_OPEN", "message": "this asset already has an open review"}) from exc
        _event(db, review_id, workspace_id, user_id, role, "request", None, "requested", comment)
        return _public(db.execute("SELECT * FROM asset_reviews WHERE review_id=?", (review_id,)).fetchone())


def _transition(workspace_id: str, review_id: str, action: str, body: DecideIn, user_id: str) -> dict[str, Any]:
    role = require_role(workspace_id, user_id, READERS)      # unknown workspace / non-member: 404 / 403 first
    comment = _clean(body.comment)
    with store._connect() as db:
        _init(db)
        row = db.execute("SELECT * FROM asset_reviews WHERE review_id=? AND workspace_id=?", (review_id, workspace_id)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Review not found")
        if action in ("approve", "request-changes", "reject"):
            allowed = DECIDERS
        elif action == "withdraw":
            allowed = DECIDERS | ({"editor"} if row["requested_by"] == user_id else set())
        else:
            allowed = WRITERS
        if role not in allowed:
            raise HTTPException(status_code=403, detail="Insufficient workspace role")
        if action == "approve" and row["requested_by"] == user_id and get_settings(db, workspace_id)["forbid_self_approval"]:
            raise HTTPException(status_code=403, detail={"code": "REVIEW_SELF_APPROVAL_FORBIDDEN", "message": "this workspace does not allow approving your own request"})
        target = TRANSITIONS.get((row["status"], action))
        if target is None:
            raise HTTPException(status_code=409, detail={"code": "REVIEW_TRANSITION_INVALID", "message": f"a review that is {row['status']} cannot be '{action}'"})
        if action in COMMENT_REQUIRED and not comment:
            raise HTTPException(status_code=422, detail={"code": "REVIEW_COMMENT_REQUIRED", "message": "give the reason in a comment"})
        handled = (None, None) if target == "requested" else (user_id, _now())
        cur = db.execute("UPDATE asset_reviews SET status=?, handled_by=?, handled_at=?, comment=?, updated_at=?, version=version+1 WHERE review_id=? AND version=?",
                         (target, handled[0], handled[1], comment if comment is not None else (None if target == "requested" else row["comment"]), _now(), review_id, row["version"]))
        if cur.rowcount != 1:
            raise HTTPException(status_code=409, detail={"code": "REVIEW_CHANGED", "message": "the review was changed by someone else; reload it"})
        _event(db, review_id, workspace_id, user_id, role, action, row["status"], target, comment)
        return _public(db.execute("SELECT * FROM asset_reviews WHERE review_id=?", (review_id,)).fetchone())


@router.post("/{review_id}/approve", response_model=ReviewOut, operation_id="approveAssetReview")
async def approve(workspace_id: str, review_id: str, body: DecideIn | None = None, user_id: str = Depends(current_user)):
    return _transition(workspace_id, review_id, "approve", body or DecideIn(), user_id)


@router.post("/{review_id}/request-changes", response_model=ReviewOut, operation_id="requestChangesAssetReview")
async def request_changes(workspace_id: str, review_id: str, body: DecideIn | None = None, user_id: str = Depends(current_user)):
    return _transition(workspace_id, review_id, "request-changes", body or DecideIn(), user_id)


@router.post("/{review_id}/reject", response_model=ReviewOut, operation_id="rejectAssetReview")
async def reject(workspace_id: str, review_id: str, body: DecideIn | None = None, user_id: str = Depends(current_user)):
    return _transition(workspace_id, review_id, "reject", body or DecideIn(), user_id)


@router.post("/{review_id}/resubmit", response_model=ReviewOut, operation_id="resubmitAssetReview")
async def resubmit(workspace_id: str, review_id: str, body: DecideIn | None = None, user_id: str = Depends(current_user)):
    return _transition(workspace_id, review_id, "resubmit", body or DecideIn(), user_id)


@router.post("/{review_id}/withdraw", response_model=ReviewOut, operation_id="withdrawAssetReview")
async def withdraw(workspace_id: str, review_id: str, body: DecideIn | None = None, user_id: str = Depends(current_user)):
    return _transition(workspace_id, review_id, "withdraw", body or DecideIn(), user_id)


@router.get("", response_model=ReviewListOut, operation_id="listAssetReviews")
async def list_reviews(workspace_id: str, status: Status | None = None, asset_id: str | None = Query(default=None, max_length=80), mine: bool = False,
                       limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0), user_id: str = Depends(current_user)):
    require_role(workspace_id, user_id, READERS)
    sql, args = "SELECT * FROM asset_reviews WHERE workspace_id=?", [workspace_id]
    if status:
        sql += " AND status=?"; args.append(status)
    if asset_id:
        sql += " AND asset_id=?"; args.append(asset_id)
    if mine:
        sql += " AND requested_by=?"; args.append(user_id)
    with store._connect() as db:
        _init(db)
        hidden = takedown.hidden_ids(user_id)      # R-076: one query instead of one connection per review
        rows = [r for r in db.execute(sql + " ORDER BY requested_at DESC, review_id", args).fetchall() if r["asset_id"] not in hidden]
    return {"items": [_public(r) for r in rows[offset:offset + limit]], "total": len(rows)}


@router.get("/status", operation_id="getAssetReviewStatus")
async def review_status(workspace_id: str, asset_ids: list[str] = Query(default_factory=list, max_length=100), user_id: str = Depends(current_user)):
    """For each asset id: the status of its LATEST review ('none' when it never had one) and whether it may be exported (latest review approved)."""
    require_role(workspace_id, user_id, READERS)
    out = []
    with store._connect() as db:
        _init(db)
        for aid in dict.fromkeys(asset_ids):
            row = db.execute("SELECT review_id, status FROM asset_reviews WHERE workspace_id=? AND asset_id=? ORDER BY requested_at DESC, rowid DESC LIMIT 1", (workspace_id, aid)).fetchone()
            out.append({"asset_id": aid, "status": row["status"] if row else "none", "review_id": row["review_id"] if row else None,
                        "exportable": bool(row and row["status"] == "approved")})
    return {"items": out}


@router.get("/{review_id}", response_model=ReviewOut, operation_id="getAssetReview")
async def get_review(workspace_id: str, review_id: str, user_id: str = Depends(current_user)):
    require_role(workspace_id, user_id, READERS)
    with store._connect() as db:
        _init(db)
        row = db.execute("SELECT * FROM asset_reviews WHERE review_id=? AND workspace_id=?", (review_id, workspace_id)).fetchone()
    if row is None or not takedown.visible_to(row["asset_id"], user_id):
        raise HTTPException(status_code=404, detail="Review not found")
    return _public(row)


@router.get("/{review_id}/events", response_model=list[EventOut], operation_id="listAssetReviewEvents")
async def review_events(workspace_id: str, review_id: str, user_id: str = Depends(current_user)):
    require_role(workspace_id, user_id, READERS)
    with store._connect() as db:
        _init(db)
        row = db.execute("SELECT asset_id FROM asset_reviews WHERE review_id=? AND workspace_id=?", (review_id, workspace_id)).fetchone()
        if row is None or not takedown.visible_to(row["asset_id"], user_id):
            raise HTTPException(status_code=404, detail="Review not found")
        rows = db.execute("SELECT at, actor_id, actor_role, action, from_status, to_status, comment FROM asset_review_events WHERE review_id=? ORDER BY event_id", (review_id,)).fetchall()
    return [dict(r) for r in rows]


# ------------------------------------------------------------------------------------------------------- workspace settings (reply 40)
settings_router = APIRouter(prefix="/v1/workspaces/{workspace_id}/settings", tags=["workspace-settings"])
SETTING_FIELDS = ("require_review_for_export", "forbid_self_approval")
SETTINGS_ADMINS = {"owner", "admin"}


def _init_settings(db) -> None:
    db.execute("""CREATE TABLE IF NOT EXISTS workspace_settings (
        workspace_id TEXT PRIMARY KEY, require_review_for_export INTEGER NOT NULL DEFAULT 0, forbid_self_approval INTEGER NOT NULL DEFAULT 0,
        updated_at TEXT, updated_by TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS workspace_settings_history (
        event_id INTEGER PRIMARY KEY AUTOINCREMENT, workspace_id TEXT NOT NULL, at TEXT NOT NULL, actor_id TEXT NOT NULL, field TEXT NOT NULL, old_value INTEGER NOT NULL, new_value INTEGER NOT NULL)""")
    # B-11: listing one workspace's rows must not scan the whole table
    db.execute("CREATE INDEX IF NOT EXISTS idx_workspace_settings_history_ws ON workspace_settings_history(workspace_id, event_id)")
    for kind in ("UPDATE", "DELETE"):
        db.execute(f"""CREATE TRIGGER IF NOT EXISTS trg_ws_settings_history_no_{kind.lower()} BEFORE {kind} ON workspace_settings_history
            BEGIN SELECT RAISE(ABORT, 'workspace settings history is append-only'); END""")


def get_settings(db, workspace_id: str) -> dict[str, Any]:
    _init_settings(db)
    row = db.execute("SELECT * FROM workspace_settings WHERE workspace_id=?", (workspace_id,)).fetchone()
    return {"workspace_id": workspace_id, "require_review_for_export": bool(row["require_review_for_export"]) if row else False,
            "forbid_self_approval": bool(row["forbid_self_approval"]) if row else False,
            "updated_at": row["updated_at"] if row else None, "updated_by": row["updated_by"] if row else None}


def require_approved(workspace_id: str, asset_ids: list[str | None]) -> None:
    """The export gate (reply 40 point 2). With ``require_review_for_export`` OFF (the default) nothing changes. With it ON every listed asset must have an APPROVED latest
    review, otherwise 409 ``REVIEW_NOT_APPROVED`` with the ids that are in the way. An asset that never had a review is refused too."""
    ids = list(dict.fromkeys(a for a in asset_ids if a))
    with store._connect() as db:
        _init(db)
        if not get_settings(db, workspace_id)["require_review_for_export"] or not ids:
            return
        blocked = []
        for aid in ids:
            row = db.execute("SELECT status FROM asset_reviews WHERE workspace_id=? AND asset_id=? ORDER BY requested_at DESC, rowid DESC LIMIT 1", (workspace_id, aid)).fetchone()
            if row is None or row["status"] != "approved":
                blocked.append(aid)
    if blocked:
        raise HTTPException(status_code=409, detail={"code": "REVIEW_NOT_APPROVED", "message": "these assets need an approved review before they can be exported", "asset_ids": blocked})


class SettingsOut(BaseModel):
    workspace_id: str
    require_review_for_export: bool
    forbid_self_approval: bool
    updated_at: str | None
    updated_by: str | None


class SettingsPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    require_review_for_export: StrictBool | None = None      # a real true / false (not "yes", not 1)
    forbid_self_approval: StrictBool | None = None


class SettingsEventOut(BaseModel):
    at: str
    actor_id: str
    field: str
    old_value: bool
    new_value: bool


@settings_router.get("", response_model=SettingsOut, operation_id="getWorkspaceSettings")
async def read_settings(workspace_id: str, user_id: str = Depends(current_user)):
    require_role(workspace_id, user_id, READERS)
    with store._connect() as db:
        _init(db)
        return get_settings(db, workspace_id)


@settings_router.patch("", response_model=SettingsOut, operation_id="updateWorkspaceSettings")
async def update_settings(workspace_id: str, body: SettingsPatch, user_id: str = Depends(current_user)):
    """Owner or admin only. Every change of a value is written to an append-only history."""
    require_role(workspace_id, user_id, SETTINGS_ADMINS)
    changes = {k: getattr(body, k) for k in SETTING_FIELDS if k in body.model_fields_set}
    if not changes or any(v is None for v in changes.values()):
        raise HTTPException(status_code=422, detail={"code": "SETTINGS_NOTHING_TO_CHANGE", "message": "send at least one setting as true or false"})
    with store._connect() as db:
        _init(db)
        before = get_settings(db, workspace_id)
        now = _now()
        db.execute("INSERT OR IGNORE INTO workspace_settings(workspace_id) VALUES (?)", (workspace_id,))
        for field, value in changes.items():
            if bool(before[field]) != value:
                db.execute("INSERT INTO workspace_settings_history(workspace_id, at, actor_id, field, old_value, new_value) VALUES (?,?,?,?,?,?)",
                           (workspace_id, now, user_id, field, int(before[field]), int(value)))
                db.execute(f"UPDATE workspace_settings SET {field}=?, updated_at=?, updated_by=? WHERE workspace_id=?", (int(value), now, user_id, workspace_id))
        return get_settings(db, workspace_id)


@settings_router.get("/history", response_model=list[SettingsEventOut], operation_id="listWorkspaceSettingsHistory")
async def settings_history(workspace_id: str, user_id: str = Depends(current_user)):
    require_role(workspace_id, user_id, SETTINGS_ADMINS)
    with store._connect() as db:
        _init(db)
        _init_settings(db)
        rows = db.execute("SELECT at, actor_id, field, old_value, new_value FROM workspace_settings_history WHERE workspace_id=? ORDER BY event_id", (workspace_id,)).fetchall()
    return [{"at": r["at"], "actor_id": r["actor_id"], "field": r["field"], "old_value": bool(r["old_value"]), "new_value": bool(r["new_value"])} for r in rows]
