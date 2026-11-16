"""R-066: the operator's read-only audit log: one filtered, paged list over the audit records that already exist.

Sources (all of them keep only ids, states and times; comments, notes, report details and file names are NEVER returned here):
  review   - asset review events (who asked / approved / ...)           asset_review_events
  contract - company contract and profile changes (operator or owner)    company_profile_history
  download - package downloads                                           download_audit
  report   - content reports opened and decided                          content_reports
  asset    - asset events from the provenance record (upload, import...) asset_provenance
This is a VIEW over those tables, not a new record: operator actions that have no audit record today (account suspension, settings, site content) do not exist yet
(R-052), so there is nothing to show for them; the ``coverage`` field says so.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app import config
from app.assets import store
from app.assets.routes import current_user

router = APIRouter(prefix="/internal/ops", tags=["ops-audit"])
SOURCES = ("review", "contract", "download", "report", "asset")
MAX_WINDOW = 1000          # offset + limit


class AuditRow(BaseModel):
    at: str
    source: str
    workspace_id: str | None
    actor_id: str | None
    action: str
    object_type: str
    object_id: str | None


class AuditResponse(BaseModel):
    items: list[AuditRow]
    next_offset: int | None
    sources: list[str]
    coverage: dict[str, Any]


COVERAGE = {
    "measured": {"review": "asset_review_events (append-only)", "contract": "company_profile_history (append-only)", "download": "download_audit",
                 "report": "content_reports (opened by the reporter, decided by the operator)", "asset": "asset_provenance"},
    "not_measured": ["operator actions with no audit record today: account suspension, settings, site content, role changes (they do not exist yet, R-052)",
                     "operator READS (who looked at which screen) are not recorded",
                     "job events (generation_job_events) are not included here: they are high volume; see usage / failed jobs",
                     "actor names and e-mail addresses: ids only (identity provider server key not available)"],
    "tamper_evidence": "review and contract history refuse UPDATE/DELETE in the database; the other sources are plain tables (no hash chain yet)",
}


def _has(db, name: str) -> bool:
    return db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


def _query(db, source: str, workspace_id, actor_id, start, end, window) -> list[dict[str, Any]]:
    def run(table, sql, cols_time, cols_ws, cols_actor, args_extra=()):
        if not _has(db, table):
            return []
        where, args = [], list(args_extra)
        if workspace_id:
            where.append(f"{cols_ws}=?"); args.append(workspace_id)
        if actor_id:
            where.append(f"{cols_actor}=?"); args.append(actor_id)
        if start:
            where.append(f"{cols_time}>=?"); args.append(start)
        if end:
            where.append(f"{cols_time}<?"); args.append(end)
        full = sql + (" WHERE " + " AND ".join(where) if where else "") + f" ORDER BY {cols_time} DESC LIMIT ?"
        return [dict(r) for r in db.execute(full, (*args, window)).fetchall()]

    out: list[dict[str, Any]] = []
    if source == "review":
        for r in run("asset_review_events", "SELECT at, workspace_id, actor_id, action, review_id AS oid FROM asset_review_events", "at", "workspace_id", "actor_id"):
            out.append({"at": r["at"], "source": "review", "workspace_id": r["workspace_id"], "actor_id": r["actor_id"], "action": "review." + r["action"], "object_type": "review", "object_id": r["oid"]})
    elif source == "contract":
        for r in run("company_profile_history", "SELECT at, workspace_id, actor_id, field FROM company_profile_history", "at", "workspace_id", "actor_id"):
            out.append({"at": r["at"], "source": "contract", "workspace_id": r["workspace_id"], "actor_id": r["actor_id"], "action": "company." + r["field"] + ".changed", "object_type": "company", "object_id": r["workspace_id"]})
    elif source == "download":
        for r in run("download_audit", "SELECT created_at AS at, workspace_id, actor_id, kind, object_id FROM download_audit", "created_at", "workspace_id", "actor_id"):
            out.append({"at": r["at"], "source": "download", "workspace_id": r["workspace_id"], "actor_id": r["actor_id"], "action": "download." + r["kind"], "object_type": "export", "object_id": r["object_id"]})
    elif source == "report":
        for r in run("content_reports", "SELECT created_at AS at, workspace_id, reporter_id AS actor_id, report_id AS oid FROM content_reports", "created_at", "workspace_id", "reporter_id"):
            out.append({"at": r["at"], "source": "report", "workspace_id": r["workspace_id"], "actor_id": r["actor_id"], "action": "report.opened", "object_type": "report", "object_id": r["oid"]})
        for r in run("content_reports", "SELECT resolved_at AS at, workspace_id, resolved_by AS actor_id, report_id AS oid, status FROM content_reports", "resolved_at", "workspace_id", "resolved_by"):
            if r["at"]:
                out.append({"at": r["at"], "source": "report", "workspace_id": r["workspace_id"], "actor_id": r["actor_id"], "action": "report." + r["status"], "object_type": "report", "object_id": r["oid"]})
    elif source == "asset":
        for r in run("asset_provenance", "SELECT created_at AS at, workspace_id, actor_id, event_type, asset_id FROM asset_provenance", "created_at", "workspace_id", "actor_id"):
            out.append({"at": r["at"], "source": "asset", "workspace_id": r["workspace_id"], "actor_id": r["actor_id"], "action": r["event_type"], "object_type": "asset", "object_id": r["asset_id"]})
    return out


@router.get("/audit", response_model=AuditResponse, operation_id="listOpsAudit")
async def ops_audit(workspace_id: str | None = Query(default=None, max_length=64), actor_id: str | None = Query(default=None, max_length=80),
                    source: list[Literal["review", "contract", "download", "report", "asset"]] = Query(default_factory=list),
                    start: str | None = Query(default=None, alias="from", max_length=40), end: str | None = Query(default=None, alias="to", max_length=40),
                    limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0), user_id: str = Depends(current_user)):
    if user_id not in config.OPS_ADMIN_USER_IDS:
        raise HTTPException(status_code=403, detail="Platform operations role required")
    for value in (start, end):
        if value:
            try:
                datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                raise HTTPException(status_code=422, detail={"code": "INVALID_RANGE", "message": "from/to must be ISO dates or times"})
    if offset + limit > MAX_WINDOW:
        raise HTTPException(status_code=422, detail={"code": "WINDOW_TOO_DEEP", "message": f"offset + limit must be at most {MAX_WINDOW}; narrow the time range instead"})
    wanted = list(dict.fromkeys(source)) or list(SOURCES)
    rows: list[dict[str, Any]] = []
    with store._connect() as db:
        store.initialize()
        try:
            from app.customers import _init as _c; _c(db)
            from app.reviews import _init as _r; _r(db)
        except Exception:  # noqa: BLE001
            pass
        for name in wanted:
            rows += _query(db, name, workspace_id, actor_id, start, end, offset + limit + 1)
    rows.sort(key=lambda r: (r["at"], r["source"], r["object_id"] or ""), reverse=True)
    page = rows[offset:offset + limit]
    more = len(rows) > offset + limit and offset + limit < MAX_WINDOW
    return {"items": page, "next_offset": offset + limit if more else None, "sources": wanted, "coverage": COVERAGE}
