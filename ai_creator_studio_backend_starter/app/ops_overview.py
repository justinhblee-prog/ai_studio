"""Operator console, first read-only view (R-043): all companies' usage and the estimated provider spend for one month.

Only operators (OPS_ADMIN_USER_IDS) may call it. It returns counts and estimated money only: never a photo, an image address, a prompt or a
payload. Spend is ESTIMATED from the per-job unit price (see cost_cap) and excludes failed jobs of providers that do not bill failures.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app import config, cost_cap
from app.assets.routes import current_user
from app.usage import month_range

router = APIRouter(prefix="/internal/ops", tags=["ops"])


def percentile(sorted_values: list[float], p: float) -> float | None:
    """Nearest-rank percentile of an ascending list (None when empty)."""
    if not sorted_values:
        return None
    rank = max(1, int(-(-p * len(sorted_values) // 100)))   # ceil(p% of n)
    return round(sorted_values[min(rank, len(sorted_values)) - 1], 3)


def build_overview(month: str | None) -> dict:
    label, start, nxt = month_range(month)
    from app.dependencies import get_job_repository
    rows = get_job_repository().ops_overview_rows(start, nxt)
    by_provider: dict[str, dict] = {}
    by_workspace: dict[str, dict] = {}
    users: set = set()
    for r in rows:
        p = by_provider.setdefault(r["provider"], {"provider": r["provider"], "jobs": 0, "failed": 0, "estimated_cost_usd": 0.0})
        w = by_workspace.setdefault(r["workspace_id"], {"workspace_id": r["workspace_id"], "jobs": 0, "failed": 0, "estimated_cost_usd": 0.0})
        n, failed = r["n"], r["status"] == "failed"
        billed = 0 if r["provider"] == cost_cap.MOCK_PROVIDER else (n if (not failed or cost_cap.bills_failed(r["provider"])) else 0)
        cost = round(billed * cost_cap.unit_cost(r["provider"]), 6)
        for bucket in (p, w):
            bucket["failed" if failed else "jobs"] += n
            bucket["estimated_cost_usd"] = round(bucket["estimated_cost_usd"] + cost, 6)
    from app.assets import store
    store.initialize()
    with store._connect() as db:
        members = {r["workspace_id"]: r["n"] for r in db.execute("SELECT workspace_id, COUNT(*) AS n FROM workspace_members GROUP BY workspace_id")}
    companies = sorted(({**w, "members": members.get(w["workspace_id"], 0)} for w in by_workspace.values()), key=lambda c: (-c["jobs"], c["workspace_id"]))
    total_jobs = sum(p["jobs"] for p in by_provider.values())
    total_failed = sum(p["failed"] for p in by_provider.values())
    seconds = sorted(get_job_repository().ops_execution_seconds(start, nxt))
    latency = {"count": len(seconds), "avg": round(sum(seconds) / len(seconds), 3) if seconds else None,
               "p50": percentile(seconds, 50), "p95": percentile(seconds, 95)}
    return {
        "month": label, "latency_seconds": latency, "jobs": total_jobs, "failed": total_failed,
        "failure_rate": round(total_failed / (total_jobs + total_failed), 4) if (total_jobs + total_failed) else 0.0,
        "estimated_cost_usd": round(sum(p["estimated_cost_usd"] for p in by_provider.values()), 6),
        "active_companies": len(by_workspace), "providers": sorted(by_provider.values(), key=lambda p: p["provider"]),
        "companies": companies,
        "controls": {"kill_switch_on": cost_cap.kill_switch_on(),
                     "workspace_monthly_limit": cost_cap._int_env("AI_JOB_LIMIT_PER_WORKSPACE_MONTH", 100),
                     "global_monthly_limit": cost_cap._int_env("AI_JOB_LIMIT_GLOBAL_MONTH", 500),
                     "stop_percent": cost_cap.stop_percent(),
                     "usd_limit_month_configured": bool(float(__import__("os").getenv("AI_COST_LIMIT_USD_MONTH", "") or 0) > 0)},
    }


class ProviderRow(BaseModel):
    provider: str
    jobs: int
    failed: int
    estimated_cost_usd: float


class CompanyRow(BaseModel):
    workspace_id: str
    members: int
    jobs: int
    failed: int
    estimated_cost_usd: float


class Controls(BaseModel):
    kill_switch_on: bool
    workspace_monthly_limit: int
    global_monthly_limit: int
    stop_percent: int
    usd_limit_month_configured: bool


class Latency(BaseModel):
    count: int
    avg: float | None
    p50: float | None
    p95: float | None


class OverviewResponse(BaseModel):
    month: str
    latency_seconds: Latency
    jobs: int
    failed: int
    failure_rate: float
    estimated_cost_usd: float
    active_companies: int
    providers: list[ProviderRow]
    companies: list[CompanyRow]
    controls: Controls


@router.get("/overview", response_model=OverviewResponse, operation_id="getOpsOverview")
async def ops_overview(month: str | None = Query(default=None, max_length=7), user_id: str = Depends(current_user)):
    if user_id not in config.OPS_ADMIN_USER_IDS:
        raise HTTPException(status_code=403, detail="Platform operations role required")
    try:
        return build_overview(month)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"code": "INVALID_MONTH", "message": str(exc)}) from exc


class FailedJob(BaseModel):
    job_id: str
    workspace_id: str
    provider: str
    error_code: str | None
    created_at: str
    updated_at: str


class DownloadRow(BaseModel):
    download_id: str
    workspace_id: str
    actor_id: str
    kind: str
    object_id: str
    size_bytes: int
    created_at: str


def _require_operator(user_id: str) -> None:
    if user_id not in config.OPS_ADMIN_USER_IDS:
        raise HTTPException(status_code=403, detail="Platform operations role required")


@router.get("/failed-jobs", response_model=list[FailedJob], operation_id="listOpsFailedJobs")
async def ops_failed_jobs(limit: int = Query(default=50, ge=1, le=200), user_id: str = Depends(current_user)):
    _require_operator(user_id)
    from app.dependencies import get_job_repository
    return get_job_repository().ops_failed_jobs(limit)


@router.get("/downloads", response_model=list[DownloadRow], operation_id="listOpsDownloads")
async def ops_downloads(limit: int = Query(default=50, ge=1, le=200), user_id: str = Depends(current_user)):
    """The newest package downloads (who took what, when, how big) of every workspace: the download audit trail (R-035)."""
    _require_operator(user_id)
    from app import lookbook
    lookbook.initialize()
    db = lookbook._connect()
    try:
        return [dict(r) for r in db.execute("SELECT download_id, workspace_id, actor_id, kind, object_id, size_bytes, created_at FROM download_audit "
                                            "ORDER BY created_at DESC, download_id DESC LIMIT ?", (limit,)).fetchall()]
    finally:
        db.close()


GRACE_DAYS = 7  # the deletion grace period (scripts/purge_requests.py --grace-days default)


class DeletionRow(BaseModel):
    request_id: str
    scope: str
    workspace_id: str | None
    user_id: str
    status: str
    requested_at: str
    due_at: str
    grace_expired: bool


@router.get("/deletion-requests", response_model=list[DeletionRow], operation_id="listOpsDeletionRequests")
async def ops_deletion_requests(status: str = Query(default="pending", pattern="^(pending|cancelled|completed)$"),
                                limit: int = Query(default=100, ge=1, le=500), user_id: str = Depends(current_user)):
    """Deletion requests with their grace deadline, so the operator sees what is waiting and what is due. Nothing is deleted here: the purge
    itself stays the documented manual procedure (scripts/purge_requests.py with an explicit confirmation). The free-text reason is not shown."""
    _require_operator(user_id)
    from datetime import datetime, timedelta, timezone
    from app.legal import _initialize
    from app.assets import store
    _initialize()
    now = datetime.now(timezone.utc)
    with store._connect() as db:
        rows = db.execute("SELECT request_id, scope, workspace_id, user_id, status, requested_at FROM deletion_requests WHERE status=? "
                          "ORDER BY requested_at LIMIT ?", (status, limit)).fetchall()
    out = []
    for r in rows:
        due = datetime.fromisoformat(r["requested_at"]) + timedelta(days=GRACE_DAYS)
        out.append({**dict(r), "due_at": due.isoformat(), "grace_expired": due <= now})
    return out
