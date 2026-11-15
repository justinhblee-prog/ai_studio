"""AI cost cap: per-workspace monthly and global limits on non-mock provider jobs.

Counting unit is the job (not credits): no credit ledger is wired into the runtime.
Mock-provider jobs are never counted or blocked. Limits are read from the
environment on every call so an operator can flip the kill switch without redeploy
of code (process env change + restart is still required for a running service).

  AI_JOBS_DISABLED=1                   kill switch: no new non-mock jobs, worker will not call providers
  AI_JOB_LIMIT_PER_WORKSPACE_MONTH=N   default 100 (pilot); 0 disables this limit
  AI_JOB_LIMIT_GLOBAL_MONTH=N          default 500 (pilot); 0 disables this limit
  AI_JOB_STOP_PERCENT=P                default 90: real calls stop at P% of a limit (soft caps keep a reserve)
  AI_COST_LIMIT_USD_MONTH=X            total monthly provider spend in USD (estimated from the per-job unit cost below). NOT SET = real calls refused.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

MOCK_PROVIDER = "mock"
# Estimated provider price per job in USD (FASHN virtual try-on v1.6: 1 credit = $0.075, per the provider's documentation, not verified by a
# live call). Unknown providers are counted at the higher default so the cap errs on the safe side.
UNIT_COST_USD = {"fashn": 0.075}
DEFAULT_UNIT_COST_USD = 0.10


def unit_cost(provider: str) -> float:
    return UNIT_COST_USD.get(str(provider).lower(), DEFAULT_UNIT_COST_USD)


class CostCapExceeded(Exception):
    def __init__(self, code: str, message: str, extra: dict | None = None) -> None:
        super().__init__(message)
        self.code, self.message = code, message
        # Extra integer fields for the 429 body. Only the per-workspace limit sets them (its own limit/used);
        # the global limit never does, so service-wide operating numbers are not exposed.
        self.extra = dict(extra or {})


def _int_env(name: str, default: int) -> int:
    try:
        return max(0, int(os.getenv(name, str(default))))
    except ValueError:
        return default


def kill_switch_on() -> bool:
    return os.getenv("AI_JOBS_DISABLED", "").strip().lower() in {"1", "true", "yes", "on"}


def month_start(now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()


def stop_percent() -> int:
    """Real calls stop at this share of a limit (default 90): the caps are soft (calls in flight and delayed counting can overshoot),
    so the last part of the limit is a reserve. 100 = stop exactly at the limit."""
    return min(100, max(1, _int_env("AI_JOB_STOP_PERCENT", 90)))


def stop_at(limit: int) -> int:
    return max(1, (limit * stop_percent()) // 100)


def enforce_in_transaction(conn, job: dict, now: datetime | None = None) -> None:
    """Call inside the job-creating write transaction so concurrent creators serialize."""
    if job.get("provider") == MOCK_PROVIDER:
        return
    if kill_switch_on():
        raise CostCapExceeded("AI_JOBS_DISABLED", "AI generation is temporarily disabled.")
    start = month_start(now)
    try:
        usd_limit = float(os.getenv("AI_COST_LIMIT_USD_MONTH", "") or 0)
    except ValueError:
        usd_limit = 0.0
    if usd_limit <= 0:  # no total-spend limit configured: a real call would be unbounded in money, so refuse it
        raise CostCapExceeded("AI_JOBS_DISABLED", "AI generation is disabled until a monthly spend limit is configured.")
    spent = sum(unit_cost(row[0]) * row[1] for row in conn.execute(
        "SELECT provider, COUNT(*) FROM generation_jobs WHERE provider<>? AND created_at>=? GROUP BY provider", (MOCK_PROVIDER, start)))
    if spent + unit_cost(job.get("provider")) > usd_limit * stop_percent() / 100 + 1e-9:
        raise CostCapExceeded("GLOBAL_MONTHLY_LIMIT", "Monthly AI spend limit is reached.")
    per_ws = _int_env("AI_JOB_LIMIT_PER_WORKSPACE_MONTH", 100)
    if per_ws:
        used = conn.execute(
            "SELECT COUNT(*) FROM generation_jobs WHERE workspace_id=? AND provider<>? AND created_at>=?",
            (job["workspace_id"], MOCK_PROVIDER, start)).fetchone()[0]
        if used >= stop_at(per_ws):
            raise CostCapExceeded("WORKSPACE_MONTHLY_LIMIT", "Monthly AI generation limit for this workspace is reached.",
                                  {"limit": per_ws, "used": used})
    glob = _int_env("AI_JOB_LIMIT_GLOBAL_MONTH", 500)
    if glob:
        used = conn.execute(
            "SELECT COUNT(*) FROM generation_jobs WHERE provider<>? AND created_at>=?",
            (MOCK_PROVIDER, start)).fetchone()[0]
        if used >= stop_at(glob):
            raise CostCapExceeded("GLOBAL_MONTHLY_LIMIT", "Global monthly AI generation limit is reached.")
