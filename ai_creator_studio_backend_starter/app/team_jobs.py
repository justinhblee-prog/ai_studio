"""R-TEAM-01: the team's JOBS (the homepage's "팀 작업 보드"): a job record per piece of work, its status history, comments, a team list and a weekly summary.

  POST   /v1/workspaces/{id}/jobs                      {workroom, title, thumb_asset_id?, due_at?}   editor or above; the caller is the owner; status starts as ``draft``
  GET    /v1/workspaces/{id}/jobs?owner=&workroom=&status=&since=&q=&limit=&offset=
  GET    /v1/workspaces/{id}/jobs/{job_id}              the job + its status history + its comments
  POST   /v1/workspaces/{id}/jobs/{job_id}/transition   {to, note?}
  POST   /v1/workspaces/{id}/jobs/{job_id}/comments     {body}
  POST   /v1/workspaces/{id}/jobs:bulk-transition       {ids, to, note?}    partial failure allowed, one result per id
  GET    /v1/workspaces/{id}/team/summary?period=week   per member {jobs, approved, credits_used} + counts per status + due within 24 h

Permissions (the same table as reviews / members: owner, admin, editor, viewer; the homepage's "approver" is an owner or admin):
  * list / read: owner and admin see ALL jobs; an editor sees only their OWN; a viewer sees all but may change nothing (a decision, see docs/TEAM_JOBS.md)
  * create: editor and above. Comment: owner/admin on any job, an editor on their own job; a viewer may not.
  * transition: draft/changes -> review: the job's owner or an owner/admin. review -> approved / changes / rejected: owner or admin only. An editor can never move someone else's job (403).
  * ``changes`` and ``rejected`` need a note (1..1000 characters, 422 ``JOB_NOTE_REQUIRED``). Only the transitions of ``TRANSITIONS`` are allowed (409 ``JOB_TRANSITION_INVALID``); approved and rejected are final.
Every status change is written to an append-only history (the database refuses UPDATE and DELETE on it), as are comments. Other workspaces: 404.
``credits_used`` is null: the credit ledger (``app/credits``) is kept per organisation account and carries no user, so a per-member figure does not exist yet (not connected).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from app.assets import store
from app.assets.routes import current_user, require_role

router = APIRouter(prefix="/v1/workspaces/{workspace_id}", tags=["team-jobs"])
Workroom = Literal["photo", "tryon", "character", "3d", "video"]
Status = Literal["draft", "review", "changes", "approved", "rejected"]
ALL, DECIDERS, WRITERS = {"owner", "admin", "editor", "viewer"}, {"owner", "admin"}, {"owner", "admin", "editor"}
TRANSITIONS: dict[str, set[str]] = {"draft": {"review"}, "review": {"approved", "changes", "rejected"}, "changes": {"review"}, "approved": set(), "rejected": set()}
DECISIONS = {"approved", "changes", "rejected"}
NOTE_REQUIRED = {"changes", "rejected"}
MAX_NOTE, MAX_TITLE, MAX_BULK, PAGE_MAX = 1000, 120, 50, 200
PERIODS = {"day": 1, "week": 7, "month": 30}
DUE_SOON = timedelta(hours=24)


def _init(db) -> None:
    db.execute("""CREATE TABLE IF NOT EXISTS team_jobs (
        job_id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, owner_user_id TEXT NOT NULL, workroom TEXT NOT NULL, title TEXT NOT NULL, status TEXT NOT NULL,
        thumb_asset_id TEXT, due_at TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
    db.execute("CREATE INDEX IF NOT EXISTS idx_team_jobs_ws ON team_jobs(workspace_id, status, updated_at)")
    db.execute("""CREATE TABLE IF NOT EXISTS team_job_events (
        event_id INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT NOT NULL, workspace_id TEXT NOT NULL, from_status TEXT, to_status TEXT NOT NULL, by_user TEXT NOT NULL, note TEXT, at TEXT NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS team_job_comments (
        comment_id INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT NOT NULL, workspace_id TEXT NOT NULL, by_user TEXT NOT NULL, body TEXT NOT NULL, at TEXT NOT NULL)""")
    for table in ("team_job_events", "team_job_comments"):
        for kind in ("UPDATE", "DELETE"):
            db.execute(f"CREATE TRIGGER IF NOT EXISTS trg_{table}_no_{kind.lower()} BEFORE {kind} ON {table} BEGIN SELECT RAISE(ABORT, 'append-only'); END")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _err(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def _parse(value: str | None, name: str) -> str | None:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc).isoformat()
    except ValueError:
        raise _err(422, "JOB_DATE_INVALID", f"{name} must be an ISO date-time") from None


class TeamJobIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workroom: Workroom
    title: str = Field(min_length=1, max_length=MAX_TITLE)
    thumb_asset_id: str | None = Field(default=None, max_length=80)
    due_at: str | None = Field(default=None, max_length=40)


class TeamJobTransitionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    to: Status
    note: str | None = Field(default=None, max_length=MAX_NOTE)


class TeamJobCommentIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    body: str = Field(min_length=1, max_length=MAX_NOTE)


class TeamJobBulkIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ids: list[str] = Field(min_length=1, max_length=MAX_BULK)
    to: Status
    note: str | None = Field(default=None, max_length=MAX_NOTE)


COMMENT_COUNT = "(SELECT COUNT(*) FROM team_job_comments c WHERE c.job_id=team_jobs.job_id)"


def _job(row) -> dict[str, Any]:
    out = {k: row[k] for k in ("job_id", "workspace_id", "owner_user_id", "workroom", "title", "status", "thumb_asset_id", "due_at", "created_at", "updated_at")}
    if "comment_count" in row.keys():
        out["comment_count"] = row["comment_count"]                                   # D-6: the board shows how many comments a job has (the screen's "cm")
    return out


def _get(db, workspace_id: str, job_id: str):
    row = db.execute(f"SELECT team_jobs.*, {COMMENT_COUNT} AS comment_count FROM team_jobs WHERE workspace_id=? AND job_id=?", (workspace_id, job_id)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return row


def _may_see(role: str, user_id: str, row) -> bool:
    return role in DECIDERS or role == "viewer" or row["owner_user_id"] == user_id


def _check_transition(role: str, user_id: str, row, to: str, note: str | None) -> None:
    """Raises the HTTPException a refused transition deserves; returns when it is allowed."""
    if role == "viewer":
        raise HTTPException(status_code=403, detail="Insufficient workspace role")
    if to not in TRANSITIONS[row["status"]]:
        raise _err(409, "JOB_TRANSITION_INVALID", f"a job that is {row['status']} cannot become {to}")
    if to in DECISIONS:
        if role not in DECIDERS:
            raise HTTPException(status_code=403, detail="Only an owner or admin can decide a job")
    elif role not in DECIDERS and row["owner_user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Only the job's owner or an admin can move it")
    if to in NOTE_REQUIRED and not (note or "").strip():
        raise _err(422, "JOB_NOTE_REQUIRED", "a note is required to request changes or reject")


def _apply(db, workspace_id: str, user_id: str, row, to: str, note: str | None) -> dict[str, Any]:
    now = _now()
    db.execute("UPDATE team_jobs SET status=?, updated_at=? WHERE job_id=? AND workspace_id=? AND status=?", (to, now, row["job_id"], workspace_id, row["status"]))
    if db.execute("SELECT changes()").fetchone()[0] != 1:
        raise _err(409, "JOB_TRANSITION_INVALID", "the job changed at the same moment; read it again")
    db.execute("INSERT INTO team_job_events(job_id, workspace_id, from_status, to_status, by_user, note, at) VALUES (?,?,?,?,?,?,?)",
               (row["job_id"], workspace_id, row["status"], to, user_id, (note or "").strip() or None, now))
    return _job(_get(db, workspace_id, row["job_id"]))


@router.post("/jobs", status_code=201, operation_id="createTeamJob")
async def create_job(workspace_id: str, body: TeamJobIn, user_id: str = Depends(current_user)) -> dict[str, Any]:
    require_role(workspace_id, user_id, WRITERS)
    due, title = _parse(body.due_at, "due_at"), body.title.strip()
    if not title:
        raise _err(422, "JOB_TITLE_REQUIRED", "the title must not be blank")
    job_id, now = "job_" + uuid.uuid4().hex[:16], _now()
    store.initialize()
    with store._connect() as db:
        _init(db)
        db.execute("INSERT INTO team_jobs VALUES (?,?,?,?,?,?,?,?,?,?)", (job_id, workspace_id, user_id, body.workroom, title, "draft", body.thumb_asset_id, due, now, now))
        db.execute("INSERT INTO team_job_events(job_id, workspace_id, from_status, to_status, by_user, note, at) VALUES (?,?,?,?,?,?,?)", (job_id, workspace_id, None, "draft", user_id, None, now))
        return _job(_get(db, workspace_id, job_id))


@router.get("/jobs", operation_id="listTeamJobs")
async def list_jobs(workspace_id: str, owner: str | None = None, workroom: Workroom | None = None, status: Status | None = None, since: str | None = None,
                    q: str | None = Query(default=None, max_length=80), limit: int = Query(default=50, ge=1, le=PAGE_MAX), offset: int = Query(default=0, ge=0),
                    user_id: str = Depends(current_user)) -> dict[str, Any]:
    role = require_role(workspace_id, user_id, ALL)
    since_iso = _parse(since, "since")
    where, args = ["workspace_id=?"], [workspace_id]
    if role == "editor":
        where.append("owner_user_id=?"); args.append(user_id)
    for column, value in (("owner_user_id", owner), ("workroom", workroom), ("status", status)):
        if value:
            where.append(f"{column}=?"); args.append(value)
    if since_iso:
        where.append("updated_at>=?"); args.append(since_iso)
    if q and q.strip():
        where.append("title LIKE ? ESCAPE '\\'"); args.append("%" + q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%")
    store.initialize()
    with store._connect() as db:
        _init(db)
        total = db.execute(f"SELECT COUNT(*) FROM team_jobs WHERE {' AND '.join(where)}", args).fetchone()[0]
        rows = db.execute(f"SELECT team_jobs.*, {COMMENT_COUNT} AS comment_count FROM team_jobs WHERE {' AND '.join(where)} ORDER BY updated_at DESC, job_id LIMIT ? OFFSET ?", [*args, limit, offset]).fetchall()
    return {"items": [_job(r) for r in rows], "total": total}


@router.post("/jobs:bulk-transition", operation_id="bulkTransitionTeamJobs")
async def bulk_transition(workspace_id: str, body: TeamJobBulkIn, user_id: str = Depends(current_user)) -> dict[str, Any]:
    role = require_role(workspace_id, user_id, ALL)
    if role == "viewer":
        raise HTTPException(status_code=403, detail="Insufficient workspace role")
    if len(set(body.ids)) != len(body.ids):
        raise _err(422, "JOB_BULK_DUPLICATE", "each job may appear once")
    results = []
    store.initialize()
    with store._connect() as db:
        _init(db)
        for job_id in body.ids:
            row = db.execute("SELECT * FROM team_jobs WHERE workspace_id=? AND job_id=?", (workspace_id, job_id)).fetchone()
            if row is None:
                results.append({"id": job_id, "ok": False, "status": None, "error_code": "NOT_FOUND"})
                continue
            try:
                _check_transition(role, user_id, row, body.to, body.note)
                results.append({"id": job_id, "ok": True, "status": _apply(db, workspace_id, user_id, row, body.to, body.note)["status"], "error_code": None})
            except HTTPException as exc:
                code = exc.detail.get("code") if isinstance(exc.detail, dict) else ("FORBIDDEN" if exc.status_code == 403 else "ERROR")
                results.append({"id": job_id, "ok": False, "status": row["status"], "error_code": code})
    return {"results": results, "succeeded": sum(1 for r in results if r["ok"]), "failed": sum(1 for r in results if not r["ok"])}


@router.get("/jobs/{job_id}", operation_id="getTeamJob")
async def get_job(workspace_id: str, job_id: str, user_id: str = Depends(current_user)) -> dict[str, Any]:
    role = require_role(workspace_id, user_id, ALL)
    store.initialize()
    with store._connect() as db:
        _init(db)
        row = _get(db, workspace_id, job_id)
        if not _may_see(role, user_id, row):
            raise HTTPException(status_code=404, detail="Job not found")
        events = db.execute("SELECT from_status, to_status, by_user, note, at FROM team_job_events WHERE job_id=? ORDER BY event_id", (job_id,)).fetchall()
        comments = db.execute("SELECT by_user, body, at FROM team_job_comments WHERE job_id=? ORDER BY comment_id", (job_id,)).fetchall()
    return {**_job(row), "events": [{"from": e["from_status"], "to": e["to_status"], "by": e["by_user"], "note": e["note"], "at": e["at"]} for e in events],
            "comments": [{"by": c["by_user"], "body": c["body"], "at": c["at"]} for c in comments]}


@router.post("/jobs/{job_id}/transition", operation_id="transitionTeamJob")
async def transition(workspace_id: str, job_id: str, body: TeamJobTransitionIn, user_id: str = Depends(current_user)) -> dict[str, Any]:
    role = require_role(workspace_id, user_id, ALL)
    store.initialize()
    with store._connect() as db:
        _init(db)
        row = _get(db, workspace_id, job_id)
        _check_transition(role, user_id, row, body.to, body.note)         # an editor on someone else's job gets 403 here (the job exists in the workspace)
        return _apply(db, workspace_id, user_id, row, body.to, body.note)


@router.post("/jobs/{job_id}/comments", status_code=201, operation_id="commentTeamJob")
async def comment(workspace_id: str, job_id: str, body: TeamJobCommentIn, user_id: str = Depends(current_user)) -> dict[str, Any]:
    role = require_role(workspace_id, user_id, ALL)
    store.initialize()
    with store._connect() as db:
        _init(db)
        row = _get(db, workspace_id, job_id)
        if role == "viewer" or (role == "editor" and row["owner_user_id"] != user_id):
            raise HTTPException(status_code=403, detail="Insufficient workspace role")
        text = body.body.strip()
        if not text:
            raise _err(422, "JOB_COMMENT_REQUIRED", "the comment must not be blank")
        now = _now()
        db.execute("INSERT INTO team_job_comments(job_id, workspace_id, by_user, body, at) VALUES (?,?,?,?,?)", (job_id, workspace_id, user_id, text, now))
    return {"job_id": job_id, "by": user_id, "body": text, "at": now}


@router.get("/team/summary", operation_id="getTeamSummary")
async def summary(workspace_id: str, period: Literal["day", "week", "month"] = "week", user_id: str = Depends(current_user)) -> dict[str, Any]:
    role = require_role(workspace_id, user_id, ALL)
    if role == "editor":
        raise HTTPException(status_code=403, detail="Only owners, admins and viewers see the team summary")
    now = datetime.now(timezone.utc)
    since = (now - timedelta(days=PERIODS[period])).isoformat()
    store.initialize()
    with store._connect() as db:
        _init(db)
        rows = db.execute("SELECT * FROM team_jobs WHERE workspace_id=? AND updated_at>=?", (workspace_id, since)).fetchall()
        members = [r["user_id"] for r in db.execute("SELECT user_id FROM workspace_members WHERE workspace_id=?", (workspace_id,)).fetchall()]
    per: dict[str, dict[str, Any]] = {m: {"user_id": m, "jobs": 0, "approved": 0, "credits_used": None} for m in members}
    by_status = {s: 0 for s in TRANSITIONS}
    due_soon = 0
    for r in rows:
        member = per.setdefault(r["owner_user_id"], {"user_id": r["owner_user_id"], "jobs": 0, "approved": 0, "credits_used": None})
        member["jobs"] += 1
        member["approved"] += r["status"] == "approved"
        by_status[r["status"]] += 1
        if r["due_at"] and r["status"] in ("draft", "review", "changes"):
            due = datetime.fromisoformat(r["due_at"])
            if now <= due <= now + DUE_SOON:
                due_soon += 1
    return {"period": period, "since": since, "members": sorted(per.values(), key=lambda m: (-m["jobs"], m["user_id"])), "by_status": by_status, "due_soon_24h": due_soon,
            "credits_note": "credits_used is null: the credit ledger is kept per organisation account and carries no user (not connected)"}
