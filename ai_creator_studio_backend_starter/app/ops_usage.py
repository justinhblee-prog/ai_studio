"""R-054: operator usage aggregation (`GET /internal/ops/usage`): who used what, how much, at what estimated cost, over a period.

One read-only endpoint over the tables that exist today. It says plainly which numbers are MEASURED (counted from our own records) and which are
ESTIMATED (unit price x count; never reconciled with a real invoice) and which are NOT MEASURED at all (``coverage``). Metadata only: ids, counts,
bytes and money; never a picture, an address, a prompt or a sentence. Company = workspace id and user = user id (names and e-mails need the identity
provider's server key, an open decision), operators only (``OPS_ADMIN_USER_IDS``; the lead/support/billing split is the R-052 proposal).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from app import config, cost_cap
from app.assets import store
from app.assets.routes import current_user

router = APIRouter(prefix="/internal/ops", tags=["ops"])
WIDTH = {"hour": 13, "day": 10, "month": 7}
MAX_BUCKETS, ROW_CAP = 400, 50000
STATUS = {"succeeded": "success", "success": "success", "failed": "failed", "queued": "pending", "running": "pending", "post_processing": "pending",
          "processing": "pending"}

COVERAGE = {
    "tryon": {"source": "generation_jobs", "measured": ["count", "status", "provider"], "estimated": ["cost_usd"], "not_measured": ["duration_ms", "bytes"]},
    "photo": {"source": "photo_processing_runs", "measured": ["count", "status", "duration_ms"], "estimated": [], "not_measured": ["bytes"], "note": "local processing: no provider cost"},
    "character": {"source": "model_drafts", "measured": ["count"], "estimated": [], "not_measured": ["duration_ms", "bytes"], "note": "mock only today"},
    "video": {"source": "video_jobs", "measured": ["count", "status", "provider"], "estimated": [], "not_measured": ["duration_ms", "bytes"], "note": "mock only today"},
    "3d": {"source": "assets (3D uploads)", "measured": ["count", "bytes"], "estimated": [], "not_measured": ["duration_ms"]},
    "download": {"source": "download_audit", "measured": ["count", "bytes"], "estimated": [], "not_measured": []},
    "assist": {"source": "assist_usage", "measured": ["count"], "estimated": [], "not_measured": ["duration_ms", "bytes"], "note": "no sentence text is stored"},
    "market": {"source": None, "measured": [], "estimated": [], "not_measured": ["count"], "note": "no marketplace exists yet"},
}
GLOBAL_NOT_MEASURED = ["blocked: jobs refused by a limit (HTTP 429) are not stored, so blocked is always 0 here",
                       "company/user names and e-mails: identity provider server key not available (ids only)",
                       "style / region: recorded only on try-on jobs (the one generation job the server has); every other service counts as 'unknown'",
                       "real provider invoices: cost_usd is unit price x count, never reconciled with a bill"]


def _iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).isoformat()


def _parse(value: str | None, fallback: datetime) -> datetime:
    if not value:
        return fallback
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _has(db, table: str) -> bool:
    return bool(db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone())


def collect_events(start: str, end: str) -> tuple[list[dict[str, Any]], list[str]]:
    """Usage events from every source that exists. Returns (events, services whose row cap was hit)."""
    events: list[dict[str, Any]] = []
    truncated: list[str] = []

    def add(service, t, ws, user, provider, status, cost=0.0, duration_ms=None, size=None, style="unknown", region="unknown"):
        events.append({"t": t, "company": ws, "user": user, "service": service, "provider": provider, "status": status,
                       "cost": cost, "duration_ms": duration_ms, "bytes": size, "style": style, "region": region})

    from app.dependencies import get_job_repository
    jobs = get_job_repository().ops_usage_rows(start, end, ROW_CAP)
    if len(jobs) >= ROW_CAP:
        truncated.append("tryon")
    for r in jobs:
        status = STATUS.get(r["status"], "pending")
        billed = 0 if r["provider"] == cost_cap.MOCK_PROVIDER else (1 if (status != "failed" or cost_cap.bills_failed(r["provider"])) and status != "pending" else 0)
        try:
            sent = json.loads(r.get("payload_json") or "{}")
        except ValueError:
            sent = {}
        add("tryon", r["created_at"], r["workspace_id"], r["owner_id"], r["provider"], status, billed * cost_cap.unit_cost(r["provider"]),
            style=sent.get("style") or "unknown", region=sent.get("region") or "unknown")
    with store._connect() as db:
        store.initialize()
        def rows(sql, args):
            return db.execute(sql + f" LIMIT {ROW_CAP}", args).fetchall()
        if _has(db, "photo_processing_runs"):
            got = rows("SELECT created_at, updated_at, workspace_id, created_by, status FROM photo_processing_runs WHERE created_at>=? AND created_at<? ORDER BY created_at DESC", (start, end))
            truncated += ["photo"] if len(got) >= ROW_CAP else []
            for r in got:
                try:
                    ms = max(0, int((datetime.fromisoformat(r["updated_at"]) - datetime.fromisoformat(r["created_at"])).total_seconds() * 1000)) if r["status"] != "processing" else None
                except ValueError:
                    ms = None
                add("photo", r["created_at"], r["workspace_id"], r["created_by"], "local", STATUS.get(r["status"], "pending"), 0.0, ms)
        if _has(db, "model_drafts"):
            for r in rows("SELECT created_at, workspace_id, owner_id, provider FROM model_drafts WHERE created_at>=? AND created_at<? ORDER BY created_at DESC", (start, end)):
                add("character", r["created_at"], r["workspace_id"], r["owner_id"], r["provider"], "success")
        if _has(db, "video_jobs"):
            for r in rows("SELECT created_at, workspace_id, owner_id, provider, status FROM video_jobs WHERE created_at>=? AND created_at<? ORDER BY created_at DESC", (start, end)):
                add("video", r["created_at"], r["workspace_id"], r["owner_id"], r["provider"], STATUS.get(r["status"], "pending"))
        for r in rows("SELECT created_at, workspace_id, owner_id, size_bytes FROM assets WHERE media_type LIKE 'model/%' AND created_at>=? AND created_at<? ORDER BY created_at DESC", (start, end)):
            add("3d", r["created_at"], r["workspace_id"], r["owner_id"], "local", "success", 0.0, None, r["size_bytes"])
        if _has(db, "download_audit"):
            for r in rows("SELECT created_at, workspace_id, actor_id, size_bytes FROM download_audit WHERE created_at>=? AND created_at<? ORDER BY created_at DESC", (start, end)):
                add("download", r["created_at"], r["workspace_id"], r["actor_id"], "local", "success", 0.0, None, r["size_bytes"])
        if _has(db, "assist_usage"):
            for r in rows("SELECT created_at, workspace_id, user_id, interpreter FROM assist_usage WHERE created_at>=? AND created_at<? ORDER BY created_at DESC", (start, end)):
                add("assist", r["created_at"], r["workspace_id"], r["user_id"], r["interpreter"], "success")
    return events, truncated


def build_usage(granularity: str, by: str, start: datetime | None, end: datetime | None) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    stop = end or (now + (timedelta(hours=1) if granularity == "hour" else timedelta(days=1)))
    begin = start or (stop - {"hour": timedelta(hours=24), "day": timedelta(days=7), "month": timedelta(days=366)}[granularity])
    if begin >= stop:
        raise ValueError("from must be before to")
    span_buckets = int((stop - begin) / {"hour": timedelta(hours=1), "day": timedelta(days=1), "month": timedelta(days=28)}[granularity]) + 1
    if span_buckets > MAX_BUCKETS:
        raise ValueError(f"at most {MAX_BUCKETS} buckets")
    width = WIDTH[granularity]
    events, truncated = collect_events(_iso(begin), _iso(stop))
    groups: dict[tuple[str, str], dict[str, Any]] = {}
    for e in events:
        key = e[by]
        g = groups.setdefault((e["t"][:width], key), {"bucket": e["t"][:width], "key": key, "events": 0, "success": 0, "failed": 0, "pending": 0, "blocked": 0,
                                                       "estimated_cost_usd": 0.0, "duration_ms_total": 0, "duration_ms_count": 0, "bytes": 0})
        g["events"] += 1
        g[e["status"]] += 1
        g["estimated_cost_usd"] = round(g["estimated_cost_usd"] + e["cost"], 6)
        if e["duration_ms"] is not None:
            g["duration_ms_total"] += e["duration_ms"]; g["duration_ms_count"] += 1
        if e["bytes"]:
            g["bytes"] += e["bytes"]
    rows = sorted(groups.values(), key=lambda g: (g["bucket"], g["key"]))
    totals = {"events": len(events), "success": sum(g["success"] for g in rows), "failed": sum(g["failed"] for g in rows), "pending": sum(g["pending"] for g in rows),
              "estimated_cost_usd": round(sum(g["estimated_cost_usd"] for g in rows), 6), "bytes": sum(g["bytes"] for g in rows)}
    with store._connect() as db:
        stored = db.execute("SELECT COALESCE(SUM(size_bytes),0) AS n FROM assets WHERE deleted_at IS NULL").fetchone()["n"]
    return {"granularity": granularity, "by": by, "from": _iso(begin), "to": _iso(stop), "rows": rows, "totals": totals, "truncated_services": truncated,
            "storage_bytes_now": stored,
            "limits": {"kill_switch_on": cost_cap.kill_switch_on(),
                       "workspace_monthly_limit": cost_cap._int_env("AI_JOB_LIMIT_PER_WORKSPACE_MONTH", 100),
                       "global_monthly_limit": cost_cap._int_env("AI_JOB_LIMIT_GLOBAL_MONTH", 500),
                       "stop_percent": cost_cap.stop_percent(),
                       "usd_limit_month_configured": bool(float(__import__("os").getenv("AI_COST_LIMIT_USD_MONTH", "") or 0) > 0)},
            "coverage": COVERAGE, "not_measured": GLOBAL_NOT_MEASURED}


class UsageRow(BaseModel):
    bucket: str
    key: str
    events: int
    success: int
    failed: int
    pending: int
    blocked: int
    estimated_cost_usd: float
    duration_ms_total: int
    duration_ms_count: int
    bytes: int


class UsageResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    granularity: str
    by: str
    from_: str = Field(alias="from")
    to: str
    rows: list[UsageRow]
    totals: dict[str, Any]
    truncated_services: list[str]
    storage_bytes_now: int
    limits: dict[str, Any]
    coverage: dict[str, Any]
    not_measured: list[str]


@router.get("/usage", response_model=UsageResponse, response_model_by_alias=True, operation_id="getOpsUsage")
async def ops_usage(granularity: Literal["hour", "day", "month"] = Query(default="day", alias="group_by"),
                    by: Literal["company", "user", "service", "provider", "style", "region"] = "service",
                    start: str | None = Query(default=None, alias="from", max_length=40), end: str | None = Query(default=None, alias="to", max_length=40),
                    user_id: str = Depends(current_user)):
    if user_id not in config.OPS_ADMIN_USER_IDS:
        raise HTTPException(status_code=403, detail="Platform operations role required")
    try:
        return build_usage(granularity, by, _parse(start, None) if start else None, _parse(end, None) if end else None)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"code": "INVALID_RANGE", "message": str(exc)}) from exc
