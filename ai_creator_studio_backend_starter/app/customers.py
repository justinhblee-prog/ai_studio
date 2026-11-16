"""R-057: customer / marketing statistics data: how a company found us, its contract, when it first worked and was last active, when it left.

One row per company (company = workspace) in ``company_profiles``; EVERY later change of a stored value is appended to ``company_profile_history``
(append-only, ids and values only). The acquisition record is written once by the company's owner (first write wins; the browser sends the values that
src/ais.js keeps under ``ais_acq``) and ONLY while ``CUSTOMER_STATS_COLLECTION`` is on (default off until the privacy notice and the retention period are
decided); the survey may be updated by the owner. Contract fields are changed only by an operator (the same allow-list as the other operator endpoints;
the lead/marketing/billing role split of the R-052 proposal does not exist yet).
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
STATUSES = ("trial", "active", "ended", "cancelled")   # ended = the term ran out, cancelled = terminated early; both count as churn
CHURN_STATUSES = ("ended", "cancelled")
HOST_RE = re.compile(r"^(?=.{1,100}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24}$")
TOKEN_RE = re.compile(r"^[A-Za-z0-9._~+\- ]{0,60}$")        # utm values and survey texts: no '@', no slashes, no '='
LANDING_RE = re.compile(r"^/[A-Za-z0-9._~\-/]{0,119}$")
SIZE_RE = re.compile(r"^[A-Za-z0-9._~+\-]{1,20}$")
DATE_RE = re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?")      # a year, a month or a day (ranges and first_seen)


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
    """The browser's own names (reply 37): source, medium, campaign, referrer_host, landing, first_seen. No allow-list of values; only shape and length."""
    model_config = ConfigDict(extra="forbid")
    source: str | None = Field(default=None, max_length=60)
    medium: str | None = Field(default=None, max_length=60)
    campaign: str | None = Field(default=None, max_length=60)
    referrer_host: str | None = Field(default=None, max_length=100)
    landing: str | None = Field(default=None, max_length=300)
    first_seen: str | None = Field(default=None, max_length=40)


class Survey(BaseModel):
    model_config = ConfigDict(extra="forbid")
    found: str | None = Field(default=None, max_length=60)
    industry: str | None = Field(default=None, max_length=60)
    size: str | None = Field(default=None, max_length=30)


class ProfileIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    acq: Acquisition | None = None
    survey: Survey | None = None


def _token(value: str, name: str, code: str) -> str:
    v = value.strip()
    if not TOKEN_RE.match(v):
        raise HTTPException(status_code=422, detail={"code": code, "message": f"{name} may hold letters, digits and . _ ~ + - only"})
    return v


def clean_acquisition(a: Acquisition) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in ("source", "medium", "campaign"):
        value = getattr(a, key)
        if value and value.strip():
            out[key] = _token(value, key, "ACQ_TOKEN_INVALID")
    if a.referrer_host and a.referrer_host.strip():
        host = a.referrer_host.strip().lower()
        host = re.sub(r"^https?://", "", host).split("/")[0].split("?")[0].split("#")[0].split(":")[0]   # host only: no path, query, port
        if not HOST_RE.match(host):
            raise HTTPException(status_code=422, detail={"code": "ACQ_HOST_INVALID", "message": "referrer_host must be a plain host name"})
        out["referrer_host"] = host
    if a.landing and a.landing.strip():
        path = a.landing.strip().split("?")[0].split("#")[0]      # path only: a query string can carry anything
        if not LANDING_RE.match(path):
            raise HTTPException(status_code=422, detail={"code": "ACQ_LANDING_INVALID", "message": "landing must be a plain path such as /pricing"})
        out["landing"] = path
    if a.first_seen and a.first_seen.strip():
        if not DATE_RE.match(a.first_seen.strip()):
            raise HTTPException(status_code=422, detail={"code": "ACQ_DATE_INVALID", "message": "first_seen must be an ISO date or time"})
        out["first_seen"] = a.first_seen.strip()
    return out


def clean_survey(s: Survey) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in ("found", "industry"):
        value = getattr(s, key)
        if value and value.strip():
            out[key] = _token(value, key, "SURVEY_TOKEN_INVALID")
    if s.size and s.size.strip():
        if not SIZE_RE.match(s.size.strip()):
            raise HTTPException(status_code=422, detail={"code": "SURVEY_SIZE_INVALID", "message": "size must be a short code such as 1-5 or 50+"})
        out["size"] = s.size.strip()
    return out


class ProfileOut(BaseModel):
    workspace_id: str
    acq: dict[str, Any] | None
    survey: dict[str, Any] | None


@router.post("/v1/workspaces/{workspace_id}/acquisition", response_model=ProfileOut, operation_id="recordWorkspaceAcquisition")
async def record_acquisition(workspace_id: str, body: ProfileIn, user_id: str = Depends(current_user)):
    """Owner only, and only while collection is switched on. ``acq`` is written ONCE (a second call keeps the first: first touch is the fact);
    ``survey`` can be updated. Neither carries an IP address, an e-mail address or a name."""
    require_role(workspace_id, user_id, {"owner"})
    if not config.CUSTOMER_STATS_COLLECTION:
        raise HTTPException(status_code=409, detail={"code": "COLLECTION_DISABLED", "message": "Collecting acquisition and survey values is switched off."})
    with store._connect() as db:
        _init(db)
        row = _profile(db, workspace_id)
        acq = json.loads(row["acquisition_json"]) if row["acquisition_json"] else None
        survey = json.loads(row["survey_json"]) if row["survey_json"] else None
        if body.acq is not None and acq is None:
            acq = clean_acquisition(body.acq)
            _record(db, workspace_id, user_id, "acq", None, acq)
        if body.survey is not None:
            new = clean_survey(body.survey)
            if new != (survey or {}):
                _record(db, workspace_id, user_id, "survey", survey, new)
                survey = new
        db.execute("UPDATE company_profiles SET acquisition_json=?, survey_json=?, updated_at=? WHERE workspace_id=?",
                   (json.dumps(acq, ensure_ascii=False) if acq else None, json.dumps(survey, ensure_ascii=False) if survey else None, _now(), workspace_id))
    return {"workspace_id": workspace_id, "acq": acq, "survey": survey}


# ---------------------------------------------------------------------------------------------------------- the operator's part
def _require_operator(user_id: str) -> None:
    if user_id not in config.OPS_ADMIN_USER_IDS:
        raise HTTPException(status_code=403, detail="Platform operations role required")


def _ever_trial_and_converted(db, workspace_id: str, status: str) -> tuple[bool, bool]:
    """Every company starts as a trial; it 'converted' when its status was ever set to active (history) or is active now."""
    hist = db.execute("SELECT old_value, new_value FROM company_profile_history WHERE workspace_id=? AND field='contract_status' ORDER BY history_id", (workspace_id,)).fetchall()
    news = [json.loads(h["new_value"]) for h in hist if h["new_value"] is not None]
    converted = status == "active" or "active" in news
    return True, converted


def company_rows(db) -> list[dict[str, Any]]:
    from app.dependencies import get_job_repository   # jobs may live in a separate database from the assets
    spans = get_job_repository().ops_job_spans()
    for ws in db.execute("SELECT workspace_id FROM workspaces").fetchall():
        _profile(db, ws["workspace_id"])
    out = []
    for r in db.execute("SELECT * FROM company_profiles ORDER BY joined_at, workspace_id").fetchall():
        ws = r["workspace_id"]
        users = db.execute("SELECT COUNT(*) AS n FROM workspace_members WHERE workspace_id=?", (ws,)).fetchone()["n"]
        first_job, last_job = spans.get(ws, (None, None))
        a = db.execute("SELECT MAX(created_at) AS b FROM assets WHERE workspace_id=?", (ws,)).fetchone()["b"]
        trial, converted = _ever_trial_and_converted(db, ws, r["contract_status"])
        out.append({"company": ws, "plan": r["plan"], "joined_at": r["joined_at"], "contract": {"start": r["contract_start"], "end": r["contract_end"], "status": r["contract_status"], "plan": r["plan"]},
                    "churned_at": r["churned_at"], "churn_reason": r["churn_reason"], "acq": json.loads(r["acquisition_json"]) if r["acquisition_json"] else None,
                    "survey": json.loads(r["survey_json"]) if r["survey_json"] else None, "users": users, "first_job_at": first_job,
                    "last_active_at": max([t for t in (last_job, a) if t], default=None), "was_trial": trial, "converted": converted})
    return out


class ContractOut(BaseModel):
    start: str | None
    end: str | None
    status: Literal["trial", "active", "ended", "cancelled"]
    plan: str | None


class CompanyRow(BaseModel):
    company: str
    plan: str | None
    joined_at: str
    contract: ContractOut
    churned_at: str | None
    churn_reason: str | None
    acq: dict[str, Any] | None
    survey: dict[str, Any] | None
    users: int
    first_job_at: str | None
    last_active_at: str | None
    was_trial: bool
    converted: bool


def _check_range(start: str | None, end: str | None) -> None:
    for value in (start, end):
        if value and not DATE_RE.match(value):
            raise HTTPException(status_code=422, detail={"code": "INVALID_RANGE", "message": "from/to must be ISO dates"})


@router.get("/internal/ops/customers/companies", response_model=list[CompanyRow], operation_id="listOpsCompanies")
async def ops_companies(start: str | None = Query(default=None, alias="from", max_length=40), end: str | None = Query(default=None, alias="to", max_length=40),
                        user_id: str = Depends(current_user)):
    """One row per company (company = workspace id; names and e-mail addresses live with the identity provider). `from`/`to` select by joining time."""
    _require_operator(user_id)
    _check_range(start, end)
    with store._connect() as db:
        store.initialize()
        _init(db)
        return [c for c in company_rows(db) if not ((start and c["joined_at"] < start) or (end and c["joined_at"] >= end))]


class ContractIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plan: str | None = Field(default=None, max_length=40)
    start: str | None = Field(default=None, max_length=10)
    end: str | None = Field(default=None, max_length=10)
    status: Literal["trial", "active", "ended", "cancelled"] | None = None
    churn_reason: str | None = Field(default=None, max_length=120)
    clear_end: bool = False


class ContractResponse(BaseModel):
    workspace_id: str
    contract: ContractOut
    churned_at: str | None
    churn_reason: str | None


def _contract_response(row) -> dict[str, Any]:
    return {"workspace_id": row["workspace_id"], "contract": {"start": row["contract_start"], "end": row["contract_end"], "status": row["contract_status"], "plan": row["plan"]},
            "churned_at": row["churned_at"], "churn_reason": row["churn_reason"]}


@router.get("/internal/ops/customers/{workspace_id}/contract", response_model=ContractResponse, operation_id="getOpsCustomerContract")
async def get_contract(workspace_id: str, user_id: str = Depends(current_user)):
    _require_operator(user_id)
    with store._connect() as db:
        store.initialize()
        _init(db)
        return _contract_response(_profile(db, workspace_id))


@router.put("/internal/ops/customers/{workspace_id}/contract", response_model=ContractResponse, operation_id="putOpsCustomerContract")
async def put_contract(workspace_id: str, body: ContractIn, user_id: str = Depends(current_user)):
    """Operator: set plan (a text slot, no amounts) / contract dates / status. A churn status (ended, cancelled) records ``churned_at`` (now, kept on later
    edits) and the reason; going back to trial/active clears it. Every changed field is written to the append-only history with the operator's id."""
    _require_operator(user_id)
    for key in ("start", "end"):
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
        if body.start is not None:
            new["contract_start"] = body.start
        if body.end is not None:
            new["contract_end"] = body.end
        if body.clear_end:
            new["contract_end"] = None
        if body.status is not None:
            new["contract_status"] = body.status
            if body.status in CHURN_STATUSES and not new["churned_at"]:
                new["churned_at"] = _now()
            if body.status not in CHURN_STATUSES:
                new["churned_at"], new["churn_reason"] = None, None
        if body.churn_reason is not None and new["contract_status"] in CHURN_STATUSES:
            new["churn_reason"] = body.churn_reason
        for field, value in new.items():
            _record(db, workspace_id, user_id, field, old[field], value)
        db.execute("""UPDATE company_profiles SET plan=?, contract_start=?, contract_end=?, contract_status=?, churned_at=?, churn_reason=?, updated_at=?
                      WHERE workspace_id=?""", (new["plan"], new["contract_start"], new["contract_end"], new["contract_status"], new["churned_at"], new["churn_reason"], _now(), workspace_id))
        return _contract_response(_profile(db, workspace_id))


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


# ------------------------------------------------------------------------------------------------ aggregation (reply 37, request 1)
BY = {"channel": lambda c: (c["acq"] or {}).get("source") or "unknown", "industry": lambda c: (c["survey"] or {}).get("industry") or "unknown",
      "size": lambda c: (c["survey"] or {}).get("size") or "unknown", "plan": lambda c: c["plan"] or "(none)"}
WIDTH = {"month": 7, "year": 4}
MAX_BUCKETS = 120
COVERAGE = {"signups": {"source": "company_profiles.joined_at (= workspace creation)", "measured": ["count"], "estimated": [], "not_measured": []},
            "churned": {"source": "company_profiles.churned_at (set when an operator ends or cancels a contract)", "measured": ["count"], "estimated": [],
                        "not_measured": ["churn before this feature existed (no history)", "a company that simply stopped using the service is NOT churned until an operator says so"]},
            "active_end": {"source": "joined and not churned at the end of the bucket", "measured": ["count"], "estimated": [], "not_measured": []},
            "trials": {"source": "every company starts as a trial", "measured": ["count"], "estimated": ["trial length is not tracked"], "not_measured": []},
            "converted": {"source": "contract status history: ever set to active", "measured": ["count"], "estimated": [], "not_measured": ["payment: no billing exists, so 'converted' means an operator marked it active"]},
            "by=channel": {"source": "acq.source recorded once by the owner while collection was on", "measured": ["source value"], "estimated": [],
                           "not_measured": ["companies created before collection was switched on or whose owner never reported: 'unknown'", "real attribution: the value is what the browser reported"]},
            "by=industry|size": {"source": "survey (optional, owner-entered)", "measured": ["owner's answer"], "estimated": [], "not_measured": ["companies that did not answer: 'unknown'"]}}


def _bucket_range(granularity: str, start: str | None, end: str | None, now: datetime) -> list[str]:
    width = WIDTH[granularity]
    last = now.isoformat()[:width] if not end else end[:width]
    labels: list[str] = []
    if granularity == "year":
        first = int(start[:4]) if start else int(last) - 4
        labels = [str(y) for y in range(first, int(last) + 1)]
    else:
        y, m = (int(start[:4]), int(start[5:7])) if start and len(start) >= 7 else (int(last[:4]) - (1 if int(last[5:7]) < 12 else 0), (int(last[5:7]) % 12) + 1)
        ly, lm = int(last[:4]), int(last[5:7])
        while (y, m) <= (ly, lm) and len(labels) <= MAX_BUCKETS:
            labels.append(f"{y:04d}-{m:02d}")
            y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    if len(labels) > MAX_BUCKETS:
        raise HTTPException(status_code=422, detail={"code": "INVALID_RANGE", "message": f"at most {MAX_BUCKETS} buckets"})
    return labels


def build_customers(rows: list[dict[str, Any]], granularity: str, by: str, start: str | None, end: str | None) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    width = WIDTH[granularity]
    labels = _bucket_range(granularity, start, end, now)
    keys = sorted({BY[by](c) for c in rows})
    out = []
    for label in labels:
        for key in keys:
            mine = [c for c in rows if BY[by](c) == key]
            joined = [c for c in mine if c["joined_at"][:width] == label]
            row = {"bucket": label, "key": key, "signups": len(joined), "churned": sum(1 for c in mine if c["churned_at"] and c["churned_at"][:width] == label),
                   "active_end": sum(1 for c in mine if c["joined_at"][:width] <= label and not (c["churned_at"] and c["churned_at"][:width] <= label)),
                   "trials": sum(1 for c in joined if c["was_trial"]), "converted": sum(1 for c in joined if c["was_trial"] and c["converted"])}
            if any(row[k] for k in ("signups", "churned", "active_end", "trials", "converted")):
                out.append(row)
    latest = labels[-1] if labels else None
    totals = {"signups": sum(r["signups"] for r in out), "churned": sum(r["churned"] for r in out), "trials": sum(r["trials"] for r in out), "converted": sum(r["converted"] for r in out),
              "active_end": sum(r["active_end"] for r in out if r["bucket"] == latest)}
    return {"group_by": granularity, "by": by, "from": labels[0] if labels else None, "to": latest, "rows": out, "totals": totals, "coverage": COVERAGE,
            "collection_enabled": bool(config.CUSTOMER_STATS_COLLECTION),
            "notes": ["no revenue figures: prices are not decided", "company = workspace id; names and e-mail addresses are not available",
                      "retention of the underlying records decides how far back this can look (privacy-policy period: undecided)"]}


class Totals(BaseModel):
    signups: int
    churned: int
    trials: int
    converted: int
    active_end: int


class AggRow(BaseModel):
    bucket: str
    key: str
    signups: int
    churned: int
    active_end: int
    trials: int
    converted: int


class CustomersResponse(BaseModel):
    group_by: str
    by: str
    from_: str | None = Field(alias="from")
    to: str | None
    rows: list[AggRow]
    totals: Totals
    coverage: dict[str, Any]
    collection_enabled: bool
    notes: list[str]
    model_config = ConfigDict(populate_by_name=True)


@router.get("/internal/ops/customers", response_model=CustomersResponse, response_model_by_alias=True, operation_id="getOpsCustomerStats")
async def ops_customers(start: str | None = Query(default=None, alias="from", max_length=40), end: str | None = Query(default=None, alias="to", max_length=40),
                        group_by: Literal["month", "year"] = "month", by: Literal["channel", "industry", "size", "plan"] = "channel", user_id: str = Depends(current_user)):
    """`AIS_API.ops.customers({from,to,group_by,by})`: per bucket and key: signups, churned, active_end, trials, converted (+ totals, coverage)."""
    _require_operator(user_id)
    _check_range(start, end)
    with store._connect() as db:
        store.initialize()
        _init(db)
        rows = company_rows(db)
    return build_customers(rows, group_by, by, start, end)


@router.get("/internal/ops/customers/retention", operation_id="getOpsCustomerRetention")
async def ops_retention(user_id: str = Depends(current_user)):
    """Cohorts by joining month: how many companies had NOT churned n months after joining. A cell exists only when the cohort is at least n months old."""
    _require_operator(user_id)
    now = datetime.now(timezone.utc)
    with store._connect() as db:
        store.initialize()
        _init(db)
        rows = company_rows(db)
    def months(a: str, b: str) -> int:
        return (int(b[:4]) - int(a[:4])) * 12 + int(b[5:7]) - int(a[5:7])
    cohorts: dict[str, list[dict[str, Any]]] = {}
    for c in rows:
        cohorts.setdefault(c["joined_at"][:7], []).append(c)
    this = now.isoformat()[:7]
    out = []
    for label in sorted(cohorts):
        members, age = cohorts[label], months(label, this)
        cells = []
        for n in range(0, age + 1):
            kept = sum(1 for c in members if not c["churned_at"] or months(label, c["churned_at"][:7]) > n)
            cells.append({"month": n, "retained": kept, "rate": round(kept / len(members), 4)})
        out.append({"cohort": label, "size": len(members), "retention": cells})
    return {"cohorts": out, "coverage": {"retention": {"source": "churned_at set by an operator", "measured": ["retained count"], "estimated": [],
                                                       "not_measured": ["inactivity: a company that stopped using the service but was not ended by an operator counts as retained"]}}}
