"""Read-only operational check for cron/uptime monitors. Exit 0 = OK, 1 = WARN, 2 = CRITICAL.

Usage: python scripts/ops_check.py [--db PATH] [--backup-dir DIR] [--json]
Checks (all thresholds overridable by flags): worker heartbeat, stuck jobs, stale outbox, monthly job
volume vs the cost cap, deletion requests overdue past the grace period, newest backup age.
Opens the database read-only; never writes.
"""
from __future__ import annotations
import argparse, json, os, sqlite3, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OK, WARN, CRIT = 0, 1, 2


def _has(conn, table):
    return bool(conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone())


def run_checks(conn, *, now=None, backup_dir=None, worker_stale_s=60, job_stuck_min=30, outbox_stale_min=10,
               grace_days=7, backup_max_age_h=36, ws_limit=None, global_limit=None):
    from app import cost_cap
    now = now or datetime.now(timezone.utc)
    iso = lambda d: d.isoformat()
    conn.row_factory = sqlite3.Row
    out = []

    def add(name, level, detail): out.append({"check": name, "level": level, "detail": detail})

    if _has(conn, "generation_worker_heartbeats"):
        cutoff = iso(now - timedelta(seconds=worker_stale_s))
        from app.repositories.operations import ALIVE_WORKER_STATES  # idle/working workers are alive, not just 'running'
        marks = ",".join("?" * len(ALIVE_WORKER_STATES))
        n = conn.execute(f"SELECT COUNT(*) FROM generation_worker_heartbeats WHERE state IN ({marks}) AND last_seen_at>=?",
                         (*sorted(ALIVE_WORKER_STATES), cutoff)).fetchone()[0]
        add("worker_heartbeat", OK if n else CRIT, f"{n} worker(s) seen in the last {worker_stale_s}s")
    else:
        add("worker_heartbeat", WARN, "no heartbeat table (worker never started?)")

    if _has(conn, "generation_jobs"):
        cutoff = iso(now - timedelta(minutes=job_stuck_min))
        n = conn.execute("SELECT COUNT(*) FROM generation_jobs WHERE status NOT IN ('succeeded','failed') AND updated_at<?", (cutoff,)).fetchone()[0]
        add("stuck_jobs", OK if n == 0 else WARN, f"{n} unfinished job(s) not updated for {job_stuck_min} min")
        start = cost_cap.month_start(now)
        total = conn.execute("SELECT COUNT(*) FROM generation_jobs WHERE provider!='mock' AND created_at>=?", (start,)).fetchone()[0]
        wl = ws_limit if ws_limit is not None else cost_cap._int_env("AI_JOB_LIMIT_PER_WORKSPACE_MONTH", 200)
        gl = global_limit if global_limit is not None else cost_cap._int_env("AI_JOB_LIMIT_GLOBAL_MONTH", 0)
        top = conn.execute("SELECT workspace_id, COUNT(*) n FROM generation_jobs WHERE provider!='mock' AND created_at>=? GROUP BY workspace_id ORDER BY n DESC LIMIT 1", (start,)).fetchone()
        level, msg = OK, f"{total} paid job(s) this month"
        if gl and total >= gl: level, msg = CRIT, msg + f"; global limit {gl} reached"
        elif gl and total >= 0.8 * gl: level, msg = WARN, msg + f"; {total}/{gl} of global limit"
        if wl and top and top["n"] >= wl: level, msg = CRIT, msg + f"; workspace {top['workspace_id']} at limit {wl}"
        elif wl and top and top["n"] >= 0.8 * wl: level = max(level, WARN); msg += f"; top workspace {top['n']}/{wl}"
        add("cost_cap", level, msg)
    if _has(conn, "generation_outbox"):
        cutoff = iso(now - timedelta(minutes=outbox_stale_min))
        n = conn.execute("SELECT COUNT(*) FROM generation_outbox WHERE status='pending' AND available_at<?", (cutoff,)).fetchone()[0]
        add("outbox_backlog", OK if n == 0 else WARN, f"{n} pending event(s) older than {outbox_stale_min} min")

    if _has(conn, "deletion_requests"):
        cutoff = iso(now - timedelta(days=grace_days))
        n = conn.execute("SELECT COUNT(*) FROM deletion_requests WHERE status='pending' AND requested_at<=?", (cutoff,)).fetchone()[0]
        add("deletion_due", OK if n == 0 else WARN, f"{n} deletion request(s) past the {grace_days}-day grace period awaiting purge")

    if backup_dir is not None:
        # Age comes from the manifest a finished backup writes last, so a half-written or copied folder does not count.
        found = []
        for manifest in (Path(backup_dir).glob("backup-*/manifest.json") if Path(backup_dir).is_dir() else []):
            try:
                found.append((datetime.fromisoformat(json.loads(manifest.read_text(encoding="utf-8"))["created_at"]), manifest.parent.name))
            except (OSError, ValueError, KeyError, TypeError):
                continue
        if not found:
            add("backup_age", CRIT, "no complete backup found")
        else:
            created, name = max(found)
            age = (now - created).total_seconds() / 3600
            add("backup_age", OK if age <= backup_max_age_h else CRIT, f"newest backup {name} is {age:.1f} h old (max {backup_max_age_h})")
    return out


def main(argv=None) -> int:
    from app import config
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--db", type=Path)
    p.add_argument("--backup-dir", type=Path)
    p.add_argument("--grace-days", type=int, default=7)
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)
    db = (a.db or getattr(config, "GENERATION_DATABASE_PATH", None) or config.ASSET_DATABASE_PATH)
    try:
        conn = sqlite3.connect(f"file:{Path(db).resolve()}?mode=ro", uri=True, timeout=10)
    except sqlite3.Error as exc:
        print(f"CRITICAL cannot open database read-only: {exc}"); return CRIT
    results = run_checks(conn, backup_dir=a.backup_dir, grace_days=a.grace_days)
    worst = max(r["level"] for r in results) if results else OK
    if a.json: print(json.dumps({"status": ["OK", "WARN", "CRITICAL"][worst], "checks": results}, ensure_ascii=False))
    else:
        for r in results: print(f"{['OK','WARN','CRIT'][r['level']]:5} {r['check']}: {r['detail']}")
    return worst


if __name__ == "__main__":
    raise SystemExit(main())
