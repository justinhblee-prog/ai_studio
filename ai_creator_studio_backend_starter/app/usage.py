"""Usage of a workspace (a customer company) for one month: how many jobs, by service, against the monthly limit, and per member (R-042).

Owners and admins see every member; any other member sees only their own row. Provider prices in USD are internal and never part of this
answer. Failed jobs are listed separately and are NOT counted in the job total (the provider did not do the work, and FASHN does not bill it).
Source: the generation_jobs table (one row per job). Every job so far is a virtual try-on job; the service key is kept for the other services.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app import cost_cap
from app.assets.routes import current_user, require_role

router = APIRouter(prefix="/v1/workspaces", tags=["usage"])
MONTH = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")
SERVICE_OF_JOB = "tryon"


def month_range(month: str | None) -> tuple[str, str, str]:
    """(label, start ISO, next-month start ISO) in UTC; defaults to the current month."""
    if month is None:
        now = datetime.now(timezone.utc)
        year, mon = now.year, now.month
    else:
        found = MONTH.match(month)
        if not found:
            raise ValueError("month must look like 2026-11")
        year, mon = int(found.group(1)), int(found.group(2))
    start = datetime(year, mon, 1, tzinfo=timezone.utc)
    nxt = datetime(year + (mon == 12), 1 if mon == 12 else mon + 1, 1, tzinfo=timezone.utc)
    return f"{year:04d}-{mon:02d}", start.isoformat(), nxt.isoformat()


def usage_for(workspace_id: str, user_id: str, role: str, month: str | None) -> dict:
    label, start, nxt = month_range(month)
    from app import job_repository
    job_repository.initialize()
    conn = job_repository._connect()
    try:
        rows = conn.execute("""SELECT owner_id, provider, status, COUNT(*) AS n FROM generation_jobs
            WHERE workspace_id=? AND created_at>=? AND created_at<? GROUP BY owner_id, provider, status""",
                            (workspace_id, start, nxt)).fetchall()
    finally:
        conn.close()
    see_all = role in {"owner", "admin"}
    members: dict[str, dict] = {}
    total = failed = counted = 0
    for r in rows:
        who, n = r["owner_id"], r["n"]
        if r["status"] == "failed":
            failed += n
        else:
            total += n
            if r["provider"] != cost_cap.MOCK_PROVIDER:
                counted += n
        if see_all or who == user_id:
            m = members.setdefault(who, {"user_id": who, "jobs": 0, "failed": 0, "services": {}})
            if r["status"] == "failed":
                m["failed"] += n
            else:
                m["jobs"] += n
                m["services"][SERVICE_OF_JOB] = m["services"].get(SERVICE_OF_JOB, 0) + n
    limit = cost_cap._int_env("AI_JOB_LIMIT_PER_WORKSPACE_MONTH", 100)
    own = members.get(user_id) or {"user_id": user_id, "jobs": 0, "failed": 0, "services": {}}
    if not see_all:   # an ordinary member sees only their own numbers, not the company's totals
        total, failed, counted = own["jobs"], own["failed"], None
    return {"workspace_id": workspace_id, "month": label, "scope": "workspace" if see_all else "self",
            "jobs": total, "failed": failed, "services": {SERVICE_OF_JOB: total},
            "limit": {"monthly_jobs": limit or None, "counted_against_limit": counted} if see_all else None,
            "members": sorted(members.values(), key=lambda m: (-m["jobs"], m["user_id"])) if see_all else [own]}


class MemberUsage(BaseModel):
    user_id: str
    jobs: int
    failed: int
    services: dict[str, int]


class LimitInfo(BaseModel):
    monthly_jobs: int | None
    counted_against_limit: int | None


class UsageResponse(BaseModel):
    workspace_id: str
    month: str
    scope: str
    jobs: int
    failed: int
    services: dict[str, int]
    limit: LimitInfo | None
    members: list[MemberUsage]


@router.get("/{workspace_id}/usage", response_model=UsageResponse, operation_id="getWorkspaceUsage")
async def workspace_usage(workspace_id: str, month: str | None = Query(default=None, max_length=7), user_id: str = Depends(current_user)):
    role = require_role(workspace_id, user_id, {"owner", "admin", "editor", "viewer"})
    try:
        return usage_for(workspace_id, user_id, role, month)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"code": "INVALID_MONTH", "message": str(exc)}) from exc
