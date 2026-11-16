"""R-057: customer / marketing statistics data: how a company found us, its contract, when it first worked and was last active, when it left.

One row per company (company = workspace) in ``company_profiles``; EVERY later change of a stored value is appended to ``company_profile_history``
(append-only, ids and values only). The acquisition record is written once by the company's owner (first write wins; the browser sends the values that
src/ais.js keeps under ``ais_acq``); the survey may be updated by the owner. Contract fields are changed only by an operator (the same allow-list as the
other operator endpoints; the lead/marketing/billing role split of the R-052 proposal does not exist yet).
Privacy by construction: no IP address, no e-mail, no names are stored or accepted. Hosts and landing paths are reduced to a bare host / path (no query,
no fragment, no ``@``), so nothing here can identify a person or be used to contact one. Money (MRR etc.) is out of scope until prices are decided.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from app import config
from app.assets import store
from app.assets.routes import current_user, require_role

router = APIRouter(tags=["customers"])
CHANNELS = ("search", "social", "ads", "email", "referral", "direct", "event", "partner", "other")
STATUSES = ("trial", "active", "expiring", "ended")
STORED_STATUSES = ("trial", "active", "ended")      # "expiring" is derived: active with an end date within EXPIRING_DAYS
EXPIRING_DAYS = 30
HOST_RE = re.compile(r"^(?=.{1,100}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24}$")
TOKEN_RE = re.compile(r"^[A-Za-z0-9._~+\- ]{0,60}$")        # utm values and survey texts: no '@', no slashes, no '='
LANDING_RE = re.compile(r"^/[A-Za-z0-9._~\-/]{0,119}$")
SIZE_RE = re.compile(r"^[A-Za-z0-9._~+\-]{1,20}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")


def _init(db) -> None:
    db.execute("""CREATE TABLE IF NOT EXISTS company_profiles (
        workspace_id TEXT PRIMARY KEY, joined_at TEXT NOT NULL, contract_start TEXT, contract_end TEXT,
        contract_status TEXT NOT NULL DEFAULT 'trial', plan TEXT, churned_at TEXT, churn_reason TEXT,
        acquisition_json TEXT, survey_json TEXT, updated_at TEXT NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS company_profile_history (
        history_id INTEGER PRIMARY KEY AUTOINCREMENT, workspace_id TEXT NOT NULL, at TEXT NOT NULL, actor_id TEXT NOT NULL,
        field TEXT NOT NULL, old_value TEXT, new_value TEXT)""")
    db.execute("""CREATE TRIGGER IF NOT EXISTS trg_company_history_no_update BEFORE UPDATE ON company_profile_history
        BEGIN SELECT RAISE(ABORT, 'company profile history is append-only'); END""")
    db.execute("""CREATE TRIGGER IF NOT EXISTS trg_company_history_no_delete BEFORE DELETE ON company_profile_history
        BEGIN SELECT RAISE(ABORT, 'company profile history is append-only'); END""")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _profile(db, workspace_id: str):
    """The company's row, created on first use: joined_at is the workspace's own creation time."""
    row = db.execute("SELECT * FROM company_profiles WHERE workspace_id=?", (workspace_id,)).fetchone()
    if row is None:
        ws = db.execute("SELECT created_at FROM workspaces WHERE workspace_id=?", (workspace_id,)).fetchone()
        if ws is None:
            raise HTTPException(status_code=404, detail="Workspace not found")
        db.execute("INSERT INTO company_profiles(workspace_id, joined_at, updated_at) VALUES (?,?,?)", (workspace_id, ws["created_at"], _now()))
        row = db.execute("SELECT * FROM company_profiles WHERE workspace_id=?", (workspace_id,)).fetchone()
    return row


def _record(db, workspace_id: str, actor: str, field: str, old: Any, new: Any) -> None:
    if old != new:
        db.execute("INSERT INTO company_profile_history(workspace_id, at, actor_id, field, old_value, new_value) VALUES (?,?,?,?,?,?)",
                   (workspace_id, _now(), actor, field, None if old is None else json.dumps(old, ensure_ascii=False), None if new is None else json.dumps(new, ensure_ascii=False)))


# ----------------------------------------------------------------------------------------------------------- the owner's part
class Acquisition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    channel: Literal["search", "social", "ads", "email", "referral", "direct", "event", "partner", "other"] = "other"
    referrer_host: str | None = Field(default=None, max_length=100)
    utm_source: str | None = Field(default=None, max_length=60)
    utm_medium: str | None = Field(default=None, max_length=60)
    utm_campaign: str | None = Field(default=None, max_length=60)
    landing_page: str | None = Field(default=None, max_length=300)
    first_visit_at: str | None = Field(default=None, max_length=40)


class Survey(BaseModel):
    model_config = ConfigDict(extra="forbid")
    found: str | None = Field(default=None, max_length=60)
    industry: str | None = Field(default=None, max_length=60)
    team_size: str | None = Field(default=None, max_length=30)


class ProfileIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    acquisition: Acquisition | None = None
    survey: Survey | None = None


def clean_acquisition(a: Acquisition) -> dict[str, Any]:
    out: dict[str, Any] = {"channel": a.channel}
    if a.referrer_host:
        host = a.referrer_host.strip().lower()
        host = re.sub(r"^https?://", "", host).split("/")[0].split("?")[0].split("#")[0].split(":")[0]
        if not HOST_RE.match(host):
            raise HTTPException(status_code=422, detail={"code": "ACQ_HOST_INVALID", "message": "referrer_host must be a plain host name"})
        out["referrer_host"] = host
    for key in ("utm_source", "utm_medium", "utm_campaign"):
        value = getattr(a, key)
        if value:
            if not TOKEN_RE.match(value.strip()):
                raise HTTPException(status_code=422, detail={"code": "ACQ_TOKEN_INVALID", "message": f"{key} may hold letters, digits and . _ ~ + - only"})
            out[key] = value.strip()
    if a.landing_page:
        path = a.landing_page.strip().split("?")[0].split("#")[0]      # path only: a query string can carry anything
        if not LANDING_RE.match(path):
            raise HTTPException(status_code=422, detail={"code": "ACQ_LANDING_INVALID", "message": "landing_page must be a plain path such as /pricing"})
        out["landing_page"] = path
    if a.first_visit_at:
        if not DATE_RE.match(a.first_visit_at):
            raise HTTPException(status_code=422, detail={"code": "ACQ_DATE_INVALID", "message": "first_visit_at must be an ISO date or time"})
        out["first_visit_at"] = a.first_visit_at
    return out


def clean_survey(s: Survey) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in ("found", "industry"):
        value = getattr(s, key)
        if value and value.strip():
            if not TOKEN_RE.match(value.strip()):
                raise HTTPException(status_code=422, detail={"code": "SURVEY_TOKEN_INVALID", "message": f"{key} may hold letters, digits and . _ ~ + - only"})
            out[key] = value.strip()
    if s.team_size and s.team_size.strip():
        if not SIZE_RE.match(s.team_size.strip()):
            raise HTTPException(status_code=422, detail={"code": "SURVEY_SIZE_INVALID", "message": "team_size must be a short code such as 1-5 or 50+"})
        out["team_size"] = s.team_size.strip()
    return out


class ProfileOut(BaseModel):
    workspace_id: str
    acquisition: dict[str, Any] | None
    survey: dict[str, Any] | None


@router.post("/v1/workspaces/{workspace_id}/acquisition", response_model=ProfileOut, operation_id="recordWorkspaceAcquisition")
async def record_acquisition(workspace_id: str, body: ProfileIn, user_id: str = Depends(current_user)):
    """Owner only. The acquisition record is written ONCE (a second call keeps the first: first touch is the fact); the survey can be updated."""
    require_role(workspace_id, user_id, {"owner"})
    with store._connect() as db:
        _init(db)
        row = _profile(db, workspace_id)
        acq = json.loads(row["acquisition_json"]) if row["acquisition_json"] else None
        survey = json.loads(row["survey_json"]) if row["survey_json"] else None
        if body.acquisition is not None and acq is None:
            acq = clean_acquisition(body.acquisition)
            _record(db, workspace_id, user_id, "acquisition", None, acq)
        if body.survey is not None:
            new = clean_survey(body.survey)
            if new != (survey or {}):
                _record(db, workspace_id, user_id, "survey", survey, new)
                survey = new
        db.execute("UPDATE company_profiles SET acquisition_json=?, survey_json=?, updated_at=? WHERE workspace_id=?",
                   (json.dumps(acq, ensure_ascii=False) if acq else None, json.dumps(survey, ensure_ascii=False) if survey else None, _now(), workspace_id))
    return {"workspace_id": workspace_id, "acquisition": acq, "survey": survey}


# ---------------------------------------------------------------------------------------------------------- the operator's part
def _require_operator(user_id: str) -> None:
    if user_id not in config.OPS_ADMIN_USER_IDS:
        raise HTTPException(status_code=403, detail="Platform operations role required")


def _effective_status(row, now: datetime) -> str:
    end, status = row["contract_end"], row["contract_status"]
    if row["churned_at"] or status == "ended":
        return "ended"
    if end:
        try:
            end_dt = datetime.fromisoformat(end if "T" in end else end + "T23:59:59+00:00")
            end_dt = end_dt if end_dt.tzinfo else end_dt.replace(tzinfo=timezone.utc)
        except ValueError:
            return status
        if end_dt < now:
            return "ended"
        if status == "active" and end_dt - now <= timedelta(days=EXPIRING_DAYS):
            return "expiring"
    return status


def customer_rows(db, start: str | None, end: str | None) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc)
    from app.dependencies import get_job_repository   # jobs may live in a separate database from the assets
    spans = get_job_repository().ops_job_spans()
    for ws in db.execute("SELECT workspace_id FROM workspaces").fetchall():
        _profile(db, ws["workspace_id"])
    rows = db.execute("SELECT * FROM company_profiles ORDER BY joined_at, workspace_id").fetchall()
    out = []
    for r in rows:
        if (start and r["joined_at"] < start) or (end and r["joined_at"] >= end):
            continue
        ws = r["workspace_id"]
        users = db.execute("SELECT COUNT(*) AS n FROM workspace_members WHERE workspace_id=?", (ws,)).fetchone()["n"]
        first_job, last_job = spans.get(ws, (None, None))
        a = db.execute("SELECT MAX(created_at) AS b FROM assets WHERE workspace_id=?", (ws,)).fetchone()["b"]
        last_active = max([t for t in (last_job, a) if t], default=None)
        out.append({"company": ws, "email_domain": None, "plan": r["plan"], "joined_at": r["joined_at"], "contract_start": r["contract_start"],
                    "contract_end": r["contract_end"], "contract_status": _effective_status(r, now), "churned_at": r["churned_at"], "churn_reason": r["churn_reason"],
                    "acquisition": json.loads(r["acquisition_json"]) if r["acquisition_json"] else None,
                    "survey": json.loads(r["survey_json"]) if r["survey_json"] else None,
                    "users": users, "first_job_at": first_job, "last_active_at": last_active})
    return out


class CustomerRow(BaseModel):
    company: str
    email_domain: str | None
    plan: str | None
    joined_at: str
    contract_start: str | None
    contract_end: str | None
    contract_status: Literal["trial", "active", "expiring", "ended"]
    churned_at: str | None
    churn_reason: str | None
    acquisition: dict[str, Any] | None
    survey: dict[str, Any] | None
    users: int
    first_job_at: str | None
    last_active_at: str | None


@router.get("/internal/ops/customers", response_model=list[CustomerRow], operation_id="listOpsCustomers")
async def ops_customers(start: str | None = Query(default=None, alias="from", max_length=40), end: str | None = Query(default=None, alias="to", max_length=40),
                        user_id: str = Depends(current_user)):
    """`from` / `to` select companies by their joining time (UTC, `to` excluded). `email_domain` is always null: e-mail addresses live with the identity provider."""
    _require_operator(user_id)
    for value in (start, end):
        if value and not DATE_RE.match(value):
            raise HTTPException(status_code=422, detail={"code": "INVALID_RANGE", "message": "from/to must be ISO dates"})
    with store._connect() as db:
        store.initialize()
        _init(db)
        return customer_rows(db, start, end)


class ContractIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plan: str | None = Field(default=None, max_length=40)
    contract_start: str | None = Field(default=None, max_length=10)
    contract_end: str | None = Field(default=None, max_length=10)
    contract_status: Literal["trial", "active", "ended"] | None = None
    churn_reason: str | None = Field(default=None, max_length=120)
    clear_contract_end: bool = False


@router.put("/internal/ops/customers/{workspace_id}/contract", response_model=CustomerRow, operation_id="putOpsCustomerContract")
async def put_contract(workspace_id: str, body: ContractIn, user_id: str = Depends(current_user)):
    """Operator: set plan / contract dates / status. Setting status ``ended`` records ``churned_at`` (now) and the reason; going back to trial/active clears it.
    Every changed field is written to the append-only history with the operator's id."""
    _require_operator(user_id)
    for key in ("contract_start", "contract_end"):
        v = getattr(body, key)
        if v is not None and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
            raise HTTPException(status_code=422, detail={"code": "CONTRACT_DATE_INVALID", "message": f"{key} must be YYYY-MM-DD"})
    if body.plan and not TOKEN_RE.match(body.plan):
        raise HTTPException(status_code=422, detail={"code": "CONTRACT_PLAN_INVALID", "message": "plan may hold letters, digits and . _ ~ + - only"})
    if body.churn_reason and not TOKEN_RE.match(body.churn_reason):
        raise HTTPException(status_code=422, detail={"code": "CONTRACT_REASON_INVALID", "message": "churn_reason may hold letters, digits and . _ ~ + - only"})
    with store._connect() as db:
        store.initialize()
        _init(db)
        row = _profile(db, workspace_id)
        new = {"plan": row["plan"], "contract_start": row["contract_start"], "contract_end": row["contract_end"], "contract_status": row["contract_status"],
               "churned_at": row["churned_at"], "churn_reason": row["churn_reason"]}
        old = dict(new)
        if body.plan is not None:
            new["plan"] = body.plan
        if body.contract_start is not None:
            new["contract_start"] = body.contract_start
        if body.contract_end is not None:
            new["contract_end"] = body.contract_end
        if body.clear_contract_end:
            new["contract_end"] = None
        if body.contract_status is not None:
            new["contract_status"] = body.contract_status
            if body.contract_status == "ended" and not new["churned_at"]:
                new["churned_at"] = _now()
            if body.contract_status != "ended":
                new["churned_at"], new["churn_reason"] = None, None
        if body.churn_reason is not None and new["contract_status"] == "ended":
            new["churn_reason"] = body.churn_reason
        for field, value in new.items():
            _record(db, workspace_id, user_id, field, old[field], value)
        db.execute("""UPDATE company_profiles SET plan=?, contract_start=?, contract_end=?, contract_status=?, churned_at=?, churn_reason=?, updated_at=?
                      WHERE workspace_id=?""", (new["plan"], new["contract_start"], new["contract_end"], new["contract_status"], new["churned_at"], new["churn_reason"], _now(), workspace_id))
        return next(c for c in customer_rows(db, None, None) if c["company"] == workspace_id)


class HistoryRow(BaseModel):
    at: str
    actor_id: str
    field: str
    old_value: Any | None
    new_value: Any | None


@router.get("/internal/ops/customers/{workspace_id}/history", response_model=list[HistoryRow], operation_id="getOpsCustomerHistory")
async def customer_history(workspace_id: str, user_id: str = Depends(current_user)):
    _require_operator(user_id)
    with store._connect() as db:
        store.initialize()
        _init(db)
        if db.execute("SELECT 1 FROM workspaces WHERE workspace_id=?", (workspace_id,)).fetchone() is None:
            raise HTTPException(status_code=404, detail="Workspace not found")
        rows = db.execute("SELECT at, actor_id, field, old_value, new_value FROM company_profile_history WHERE workspace_id=? ORDER BY history_id", (workspace_id,)).fetchall()
    return [{"at": r["at"], "actor_id": r["actor_id"], "field": r["field"], "old_value": json.loads(r["old_value"]) if r["old_value"] is not None else None,
             "new_value": json.loads(r["new_value"]) if r["new_value"] is not None else None} for r in rows]


# ---------------------------------------------------------------------------------------------------------------- marketing
def _bucket_labels(period: str, now: datetime) -> list[str]:
    if period == "y":
        return [str(now.year - i) for i in range(4, -1, -1)]
    labels, y, m = [], now.year, now.month
    for _ in range(12):
        labels.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return labels[::-1]


def build_marketing(rows: list[dict[str, Any]], period: str) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    width = 4 if period == "y" else 7
    labels = _bucket_labels(period, now)
    def key(ts: str | None) -> str | None:
        return ts[:width] if ts else None
    series = []
    for label in labels:
        new = sum(1 for r in rows if key(r["joined_at"]) == label)
        ended = sum(1 for r in rows if key(r["churned_at"]) == label)
        active = sum(1 for r in rows if key(r["joined_at"]) <= label and not (r["churned_at"] and key(r["churned_at"]) <= label))
        series.append({"bucket": label, "new": new, "ended": ended, "net": new - ended, "active": active})
    def group(name_of):
        out: dict[str, dict[str, int]] = {}
        for r in rows:
            g = out.setdefault(name_of(r), {"signups": 0, "first_job": 0, "retained": 0})
            g["signups"] += 1
            g["first_job"] += 1 if r["first_job_at"] else 0
            g["retained"] += 0 if r["churned_at"] else 1
        return [{"key": k, **v} for k, v in sorted(out.items())]
    dist = lambda field: sorted(({"key": k, "count": n} for k, n in __import__("collections").Counter(
        (r["survey"] or {}).get(field) or "unknown" for r in rows).items()), key=lambda d: d["key"])
    return {"period": period, "series": series, "totals": {"companies": len(rows), "ended": sum(1 for r in rows if r["churned_at"]),
                                                          "with_first_job": sum(1 for r in rows if r["first_job_at"])},
            "by_channel": group(lambda r: (r["acquisition"] or {}).get("channel", "unknown")),
            "by_campaign": group(lambda r: (r["acquisition"] or {}).get("utm_campaign") or "(none)"),
            "industry": dist("industry"), "team_size": dist("team_size"),
            "notes": ["no revenue figures: prices are not decided", "companies without an acquisition record count as channel 'unknown'",
                      "retained = not ended (a company that never ended counts as retained, however recently it joined)"]}


@router.get("/internal/ops/marketing", operation_id="getOpsMarketing")
async def ops_marketing(period: Literal["m", "y"] = "m", user_id: str = Depends(current_user)):
    _require_operator(user_id)
    with store._connect() as db:
        store.initialize()
        _init(db)
        rows = customer_rows(db, None, None)
    return build_marketing(rows, period)
