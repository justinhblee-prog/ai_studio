"""Rights-infringement reports and operator handling (L-08).

Flow: a user reports an asset -> the asset is put on hold at once (only its owner can still see it) -> a platform
operator rejects the report (the hold is lifted and the asset is exactly as before) or upholds it (the asset stays hidden
for everyone; nothing is erased). The reporter is never shown to the asset's owner.

Not decided here (no procedure or policy exists yet; see docs/LAUNCH_STATUS.md): who may report beyond signed-in users,
response deadlines, an appeal path for the owner, notifying the owner, and what "removed" means for stored files.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from app import config, takedown
from app.assets.routes import current_user, require_role
from app.assets.store import _connect, initialize

router = APIRouter(tags=["moderation"])
CATEGORIES = ("copyright", "likeness", "other")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _require_ops(user_id: str) -> None:
    if user_id not in config.OPS_ADMIN_USER_IDS:
        raise HTTPException(status_code=403, detail="Platform operations role required")


class ReportInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    asset_id: str = Field(min_length=4, max_length=80)
    category: Literal["copyright", "likeness", "other"]
    details: str | None = Field(default=None, max_length=2000)


class ResolveInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["restore", "remove"]
    note: str | None = Field(default=None, max_length=1000)


@router.post("/v1/content-reports", status_code=202)
async def report_content(body: ReportInput, user_id: str = Depends(current_user)):
    """File a report. The answer is the same whether or not the asset exists or the report changed anything, so the
    endpoint cannot be used to find out which asset ids exist."""
    initialize()
    received = {"status": "received"}
    with _connect() as db:
        db.execute("BEGIN IMMEDIATE")
        asset = db.execute("SELECT asset_id, workspace_id, owner_id FROM assets WHERE asset_id=? AND deleted_at IS NULL",
                           (body.asset_id,)).fetchone()
        if asset is None or asset["owner_id"] == user_id:
            return received
        since = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        filed = db.execute("SELECT COUNT(*) AS n FROM content_reports WHERE reporter_id=? AND created_at>=?", (user_id, since)).fetchone()["n"]
        if filed >= config.CONTENT_REPORT_DAILY_LIMIT:
            raise HTTPException(status_code=429, detail="Too many reports today")
        if db.execute("SELECT 1 FROM content_reports WHERE asset_id=? AND reporter_id=? AND status='open'", (body.asset_id, user_id)).fetchone():
            return received
        now = _now()
        db.execute("""INSERT INTO content_reports(report_id,asset_id,workspace_id,reporter_id,category,details,status,created_at)
            VALUES(?,?,?,?,?,?,'open',?)""", ("rpt_" + uuid.uuid4().hex, body.asset_id, asset["workspace_id"], user_id, body.category,
                                              (body.details or "").strip() or None, now))
        db.execute("""INSERT INTO asset_takedowns(asset_id,workspace_id,state,since,updated_at) VALUES(?,?,?,?,?)
            ON CONFLICT(asset_id) DO NOTHING""", (body.asset_id, asset["workspace_id"], takedown.UNDER_REVIEW, now, now))
    return received


@router.get("/v1/assets/{asset_id}/takedown")
async def asset_takedown_status(asset_id: str, user_id: str = Depends(current_user)):
    """The hold on an asset, for people allowed to see the asset. Carries no reporter or report text."""
    initialize()
    with _connect() as db:
        asset = db.execute("SELECT workspace_id, owner_id FROM assets WHERE asset_id=? AND deleted_at IS NULL", (asset_id,)).fetchone()
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    require_role(asset["workspace_id"], user_id, {"owner", "admin", "editor", "viewer"})
    current = takedown.state_of(asset_id)
    if current is not None and asset["owner_id"] != user_id:
        raise HTTPException(status_code=404, detail="Asset not found")
    return {"asset_id": asset_id, "state": current["state"] if current else "none", "since": current["since"] if current else None}


@router.get("/v1/me/takedowns")
async def my_takedowns(user_id: str = Depends(current_user)):
    """Assets of the caller that are on hold, with the state. No reporter and no report text."""
    initialize()
    with _connect() as db:
        rows = db.execute("""SELECT t.asset_id, t.workspace_id, t.state, t.since FROM asset_takedowns t
            JOIN assets a ON a.asset_id=t.asset_id WHERE a.owner_id=? ORDER BY t.since""", (user_id,)).fetchall()
    return {"items": [dict(r) for r in rows]}


@router.get("/internal/moderation/reports")
async def list_reports(status: Literal["open", "upheld", "rejected", "all"] = Query(default="open"), user_id: str = Depends(current_user)):
    """Operators only. Includes the reporter, because the operator has to be able to follow up."""
    _require_ops(user_id)
    initialize()
    with _connect() as db:
        rows = db.execute("SELECT * FROM content_reports" + ("" if status == "all" else " WHERE status=?") + " ORDER BY created_at",
                          () if status == "all" else (status,)).fetchall()
    return {"items": [dict(r) for r in rows]}


@router.post("/internal/moderation/reports/{report_id}/resolve")
async def resolve_report(report_id: str, body: ResolveInput, user_id: str = Depends(current_user)):
    """Operators only. ``restore`` rejects the report; the hold is lifted once no other report on the asset is open.
    ``remove`` upholds it; the asset stays hidden for everyone (nothing is erased)."""
    _require_ops(user_id)
    initialize()
    with _connect() as db:
        db.execute("BEGIN IMMEDIATE")
        report = db.execute("SELECT * FROM content_reports WHERE report_id=?", (report_id,)).fetchone()
        if report is None:
            raise HTTPException(status_code=404, detail="Report not found")
        if report["status"] != "open":
            raise HTTPException(status_code=409, detail="Report is already resolved")
        now = _now()
        db.execute("UPDATE content_reports SET status=?, resolved_at=?, resolved_by=?, resolution_note=? WHERE report_id=?",
                   ("rejected" if body.decision == "restore" else "upheld", now, user_id, body.note, report_id))
        if body.decision == "remove":
            db.execute("""INSERT INTO asset_takedowns(asset_id,workspace_id,state,since,updated_at) VALUES(?,?,?,?,?)
                ON CONFLICT(asset_id) DO UPDATE SET state=excluded.state, updated_at=excluded.updated_at""",
                       (report["asset_id"], report["workspace_id"], takedown.REMOVED, now, now))
        elif not db.execute("SELECT 1 FROM content_reports WHERE asset_id=? AND status='open'", (report["asset_id"],)).fetchone():
            db.execute("DELETE FROM asset_takedowns WHERE asset_id=? AND state=?", (report["asset_id"], takedown.UNDER_REVIEW))
    return {"report_id": report_id, "status": "rejected" if body.decision == "restore" else "upheld"}


@router.post("/internal/moderation/assets/{asset_id}/reinstate")
async def reinstate_asset(asset_id: str, user_id: str = Depends(current_user)):
    """Operators only: undo a removal. The asset is exactly as before; the upheld reports stay on record."""
    _require_ops(user_id)
    initialize()
    with _connect() as db:
        cur = db.execute("DELETE FROM asset_takedowns WHERE asset_id=? AND state=?", (asset_id, takedown.REMOVED))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="No removed asset with this id")
    return {"asset_id": asset_id, "state": "none"}
