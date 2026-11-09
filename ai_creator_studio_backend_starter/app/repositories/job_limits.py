"""Per-workspace daily cap on created generation jobs (cost control).

A job counts when it is created, whatever happens to it later (a job may already have cost money at the
provider). The day is the UTC calendar day. Idempotent replays create no job and are never counted or blocked.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone


class DailyJobLimitExceeded(RuntimeError):
    def __init__(self, limit: int, used: int, retry_after_seconds: int):
        super().__init__(f"Daily generation job limit reached ({used}/{limit}); it resets at 00:00 UTC.")
        self.limit, self.used, self.retry_after_seconds = limit, used, retry_after_seconds


def utc_day_start(now: datetime) -> datetime:
    now = now.astimezone(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def seconds_until_next_utc_day(now: datetime) -> int:
    nxt = utc_day_start(now) + timedelta(days=1)
    return max(1, int((nxt - now.astimezone(timezone.utc)).total_seconds()) + 1)


def check_limit(limit: int | None, used: int, now: datetime) -> None:
    if limit and used >= limit:
        raise DailyJobLimitExceeded(limit, used, seconds_until_next_utc_day(now))
