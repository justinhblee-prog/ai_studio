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

import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

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
        db.execute("INSERT INTO asset_reviews(review_id, workspace_id, asset_id, status, requested_by, requested_at, comment, updated_at) VALUES (?,?,?,?,?,?,?,?)",
                   (review_id, workspace_id, body.asset_id, "requested", user_id, now, comment, now))
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
        rows = [r for r in db.execute(sql + " ORDER BY requested_at DESC, review_id", args).fetchall() if takedown.visible_to(r["asset_id"], user_id)]
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
