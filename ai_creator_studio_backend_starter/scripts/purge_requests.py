"""Process pending deletion requests (L-01). Dry-run by default; deletes nothing without
`--apply --confirm <request_id>`.

Scope discovery is schema-driven and fails closed: a table that cannot be tied to a
workspace, a user column, or a foreign-key chain makes the plan BLOCKED, so a newly
added table is never silently skipped.

  workspace_content  -> deletes the workspace's content (all tables scoped to it, plus files);
                        the workspace row and its members stay.
  account            -> deletes the user's consent/acceptance rows (unless keep_history),
                        removes the user from shared workspaces and anonymizes their
                        actor/owner/created_by references there, and deletes workspaces
                        where the user is the only member. Blocked if the user is the only
                        owner of a workspace that has other members.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ANON = "deleted-user"
TERMINAL_JOB_STATES = {"succeeded", "failed"}
GLOBAL_TABLES = {
    "acs_schema_migrations", "generation_schema_migrations", "generation_worker_heartbeats",
    "generation_ops_alerts", "generation_ops_alert_deliveries", "deletion_requests", "sqlite_sequence",
}
USER_TABLES = ("legal_acceptances", "consents")
ANON_COLUMNS = ("actor_id", "owner_id", "created_by")
SHELL_TABLES = {"workspaces", "workspace_members"}


def _tables(conn):
    return [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]


def _cols(conn, table):
    return [r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')]


def _fks(conn, table):
    return [(r[2], r[3], r[4]) for r in conn.execute(f'PRAGMA foreign_key_list("{table}")')]


@dataclass
class Plan:
    request_id: str
    scope: str
    user_id: str
    blocked: list = field(default_factory=list)
    rows: dict = field(default_factory=dict)
    anonymize: dict = field(default_factory=dict)
    files: list = field(default_factory=list)
    workspaces_deleted: list = field(default_factory=list)
    memberships_removed: list = field(default_factory=list)


def _scope_clauses(conn, workspaces, include_shell):
    """table -> (where_sql, params) selecting rows that belong to `workspaces`."""
    if not workspaces:
        return {}, []
    ph = ",".join("?" * len(workspaces))
    tables = [t for t in _tables(conn) if t not in GLOBAL_TABLES and t not in USER_TABLES]
    if not include_shell:
        tables = [t for t in tables if t not in SHELL_TABLES]
    own = {t for t in tables if "workspace_id" in _cols(conn, t)}
    fks = {t: _fks(conn, t) for t in tables}
    scoped = set(own)
    changed = True
    while changed:
        changed = False
        for t in tables:
            if t not in scoped and any(p in scoped and p != t for p, _, _ in fks[t]):
                scoped.add(t); changed = True
    memo = {}

    def clause(t, seen=()):
        if t in memo:
            return memo[t]
        parts, params = [], []
        if t in own:
            parts.append(f"workspace_id IN ({ph})"); params += list(workspaces)
        for parent, fk, pk in fks[t]:
            if parent in scoped and parent != t and parent not in seen:
                pw, pp = clause(parent, seen + (t,))
                parts.append(f'"{fk}" IN (SELECT "{pk}" FROM "{parent}" WHERE {pw})'); params += pp
        result = ("(" + " OR ".join(parts) + ")", params)
        if not seen:
            memo[t] = result
        return result

    clauses = {t: clause(t) for t in scoped}
    return clauses, tables


def _delete_order(conn, scoped):
    """Children before parents among scoped tables."""
    remaining, order = set(scoped), []
    while remaining:
        free = [t for t in sorted(remaining)
                if not any(p == t and c != t for c in remaining for p, _, _ in _fks(conn, c))]
        if not free:
            raise RuntimeError("foreign-key cycle among scoped tables")
        order += free
        remaining -= set(free)
    return order


def build_plan(conns, request, asset_dir, output_dir, keep_history=False):
    main = conns[0]
    plan = Plan(request["request_id"], request["scope"], request["user_id"])
    user = request["user_id"]
    full_ws, shell_ws, content_ws = [], [], []
    if request["scope"] == "workspace_content":
        content_ws = [request["workspace_id"]]
    else:
        ws_ids = {r[0] for r in main.execute("SELECT workspace_id FROM workspace_members WHERE user_id=?", (user,))}
        ws_ids |= {r[0] for r in main.execute("SELECT workspace_id FROM workspaces WHERE owner_id=?", (user,))}
        for ws in sorted(ws_ids):
            members = {r[0]: r[1] for r in main.execute(
                "SELECT user_id, role FROM workspace_members WHERE workspace_id=?", (ws,))}
            others = set(members) - {user}
            owners = {u for u, role in members.items() if role == "owner"}
            if not others:
                full_ws.append(ws)
            elif user in owners and not (owners - {user}):
                plan.blocked.append(f"LAST_OWNER:{ws}")
            else:
                shell_ws.append(ws)
        plan.workspaces_deleted, plan.memberships_removed = full_ws, shell_ws
    delete_ws = full_ws + content_ws
    counts, files = {}, []
    for conn in conns:
        clauses, tables = _scope_clauses(conn, delete_ws, include_shell=bool(full_ws))
        for t in tables:
            cols = _cols(conn, t)
            if t in clauses:
                continue
            if t in SHELL_TABLES or any(c in cols for c in ANON_COLUMNS + ("user_id",)):
                continue
            if delete_ws or request["scope"] == "account":
                plan.blocked.append(f"UNMAPPED_TABLE:{t}")
        if full_ws and "workspaces" in _tables(conn):
            clauses["workspaces"] = ("workspace_id IN (%s)" % ",".join("?" * len(full_ws)), list(full_ws))
            clauses.setdefault("workspace_members", clauses["workspaces"])
        for t, (w, p) in clauses.items():
            n = conn.execute(f'SELECT COUNT(*) FROM "{t}" WHERE {w}', p).fetchone()[0]
            if n:
                counts[t] = counts.get(t, 0) + n
            cols = _cols(conn, t)
            if "storage_key" in cols:
                root = Path(output_dir if t.startswith("generation_") else asset_dir).resolve()
                for (key,) in conn.execute(f'SELECT DISTINCT storage_key FROM "{t}" WHERE {w}', p):
                    path = (root / key).resolve()
                    if root in path.parents:
                        files.append(path)
        if "generation_jobs" in clauses:
            w, p = clauses["generation_jobs"]
            ph = ",".join("?" * len(TERMINAL_JOB_STATES))
            busy = conn.execute(
                f"SELECT job_id FROM generation_jobs WHERE {w} AND status NOT IN ({ph})",
                p + sorted(TERMINAL_JOB_STATES)).fetchall()
            plan.blocked += [f"JOB_IN_PROGRESS:{r[0]}" for r in busy]
    if request["scope"] == "account":
        for t in USER_TABLES:
            if t in _tables(main) and not keep_history:
                n = main.execute(f'SELECT COUNT(*) FROM "{t}" WHERE user_id=?', (user,)).fetchone()[0]
                if n:
                    counts[t] = counts.get(t, 0) + n
        if shell_ws:
            n = main.execute(
                f"SELECT COUNT(*) FROM workspace_members WHERE user_id=? AND workspace_id IN ({','.join('?'*len(shell_ws))})",
                [user] + shell_ws).fetchone()[0]
            if n:
                counts["workspace_members"] = counts.get("workspace_members", 0) + n
        for conn in conns:
            for t in _tables(conn):
                if t in GLOBAL_TABLES or t == "deletion_requests":
                    continue
                for c in ANON_COLUMNS:
                    if c in _cols(conn, t):
                        n = conn.execute(f'SELECT COUNT(*) FROM "{t}" WHERE "{c}"=?', (user,)).fetchone()[0]
                        if n:
                            plan.anonymize[f"{t}.{c}"] = plan.anonymize.get(f"{t}.{c}", 0) + n
    plan.rows = counts
    plan.files = sorted(set(files))
    return plan


def apply_plan(conns, request, plan, keep_history=False, now=None):
    """Delete rows (one transaction per DB), then files. Returns (rows_deleted, files_deleted, failed_files)."""
    if plan.blocked:
        raise RuntimeError("plan is blocked: " + ", ".join(plan.blocked))
    user = request["user_id"]
    full_ws = plan.workspaces_deleted
    content_ws = [request["workspace_id"]] if request["scope"] == "workspace_content" else []
    deleted = 0
    for i, conn in enumerate(conns):
        conn.execute("BEGIN IMMEDIATE")
        try:
            clauses, _ = _scope_clauses(conn, full_ws + content_ws, include_shell=bool(full_ws))
            if full_ws and "workspaces" in _tables(conn):
                clauses["workspaces"] = ("workspace_id IN (%s)" % ",".join("?" * len(full_ws)), list(full_ws))
                clauses.setdefault("workspace_members", clauses["workspaces"])
            scoped = {t: v for t, v in clauses.items()}
            for t in _delete_order(conn, scoped):
                w, p = scoped[t]
                deleted += conn.execute(f'DELETE FROM "{t}" WHERE {w}', p).rowcount
            if i == 0 and request["scope"] == "account":
                if not keep_history:
                    for t in USER_TABLES:
                        if t in _tables(conn):
                            deleted += conn.execute(f'DELETE FROM "{t}" WHERE user_id=?', (user,)).rowcount
                if plan.memberships_removed:
                    ph = ",".join("?" * len(plan.memberships_removed))
                    deleted += conn.execute(
                        f"DELETE FROM workspace_members WHERE user_id=? AND workspace_id IN ({ph})",
                        [user] + plan.memberships_removed).rowcount
            if request["scope"] == "account":
                for t in _tables(conn):
                    if t in GLOBAL_TABLES:
                        continue
                    for c in ANON_COLUMNS:
                        if c in _cols(conn, t):
                            conn.execute(f'UPDATE "{t}" SET "{c}"=? WHERE "{c}"=?', (ANON, user))
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
    removed, failed = 0, []
    for path in plan.files:
        try:
            if path.exists():
                path.unlink()
            removed += 1
        except OSError as exc:
            failed.append(f"{path.name}: {type(exc).__name__}")
    if not failed:
        stamp = (now or datetime.now(timezone.utc)).isoformat()
        conns[0].execute("UPDATE deletion_requests SET status='completed', reason=NULL, resolved_at=? WHERE request_id=?",
                         (stamp, request["request_id"]))
    return deleted, removed, failed


def due_requests(conn, grace_days, now=None):
    cutoff = ((now or datetime.now(timezone.utc)) - timedelta(days=grace_days)).isoformat()
    conn.row_factory = sqlite3.Row
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='deletion_requests'").fetchone():
        return []  # no deletion request was ever recorded
    return [dict(r) for r in conn.execute(
        "SELECT * FROM deletion_requests WHERE status='pending' AND requested_at<=? ORDER BY requested_at", (cutoff,))]


def _open(path):
    conn = sqlite3.connect(path, timeout=15, isolation_level=None)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 15000")
    return conn


def main(argv=None) -> int:
    from app import config
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", default=str(config.ASSET_DATABASE_PATH))
    parser.add_argument("--generation-db", default=str(config.GENERATION_DATABASE_PATH) if config.GENERATION_DATABASE_PATH else None)
    parser.add_argument("--assets-dir", default=str(config.ASSET_STORAGE_DIR))
    parser.add_argument("--outputs-dir", default=str(config.OUTPUT_DIR))
    parser.add_argument("--grace-days", type=int, default=int(os.getenv("PURGE_GRACE_DAYS", "7")))
    parser.add_argument("--keep-history", action="store_true", help="keep legal_acceptances and consents rows")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm", help="request_id to process (required with --apply)")
    parser.add_argument("--log", help="append a counts-only JSON line per processed request")
    args = parser.parse_args(argv)
    if args.apply and not args.confirm:
        parser.error("--apply requires --confirm <request_id>")
    conns = [_open(args.db)]
    if args.generation_db and Path(args.generation_db).resolve() != Path(args.db).resolve():
        conns.append(_open(args.generation_db))
    due = due_requests(conns[0], args.grace_days)
    if args.confirm:
        due = [r for r in due if r["request_id"] == args.confirm]
        if not due:
            print(f"request {args.confirm} is not pending or not past the {args.grace_days}-day grace period")
            return 2
    for req in due:
        plan = build_plan(conns, req, args.assets_dir, args.outputs_dir, args.keep_history)
        total = sum(plan.rows.values())
        size = sum(p.stat().st_size for p in plan.files if p.exists())
        print(f"{req['request_id']} scope={req['scope']} rows={total} files={len(plan.files)} bytes={size} "
              f"blocked={plan.blocked or 'no'}")
        for t, n in sorted(plan.rows.items()):
            print(f"  {t}: {n}")
        for k, n in sorted(plan.anonymize.items()):
            print(f"  anonymize {k}: {n}")
        if not args.apply:
            continue
        if plan.blocked:
            print("  not processed (blocked)")
            continue
        rows, files, failed = apply_plan(conns, req, plan, args.keep_history)
        print(f"  processed rows={rows} files={files} failed_files={len(failed)}")
        for f in failed:
            print(f"  retry: {f}")
        if args.log:
            with open(args.log, "a", encoding="utf-8") as fh:
                fh.write(json.dumps({"request_id": req["request_id"], "scope": req["scope"], "rows": rows,
                                     "files": files, "failed_files": len(failed),
                                     "at": datetime.now(timezone.utc).isoformat()}) + "\n")
    if not args.apply:
        print("dry-run: nothing was changed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
