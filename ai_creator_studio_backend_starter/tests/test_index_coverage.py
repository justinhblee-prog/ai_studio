"""B-11: index coverage. A table that the SQLite code reads with ``... FROM <table> WHERE workspace_id=? ...`` (workspace_id as the FIRST condition) needs an index or primary key
that STARTS with ``workspace_id``, otherwise listing one workspace's rows scans the whole table as the data grows. (Tables that merely carry a copy of workspace_id and are
read by their own id, like event tables, are not asked for one.) The tables are created by the application itself, so the test first calls every GET operation once, then reads the
schema from SQLite. Known gaps are listed in KNOWN (with a reason) and should shrink."""
import re
import sqlite3
from pathlib import Path

from tests.test_authz_matrix import _fill, _operations, auth, client, seeded  # noqa: F401
from app import config

KNOWN: dict[str, str] = {}


def _touch_everything(seeded_ids):
    for method, path, op in _operations():
        if method != "get":
            continue
        query = {p["name"]: seeded_ids.get(p["name"], "x") for p in op.get("parameters", []) if p.get("in") == "query" and p.get("required")}
        client.get(_fill(path, seeded_ids), headers=auth("tok-a"), params=query)


def _leading_columns(con, table):
    lead = set()
    for _, name, *_rest in con.execute(f'PRAGMA index_list("{table}")').fetchall():
        cols = [r[2] for r in con.execute(f'PRAGMA index_info("{name}")').fetchall()]
        if cols:
            lead.add(cols[0])
    pk = [r[1] for r in sorted(con.execute(f'PRAGMA table_info("{table}")').fetchall(), key=lambda r: r[5]) if r[5]]
    if pk:
        lead.add(pk[0])
    return lead


FIRST_CONDITION = re.compile(r'FROM\s+"?(\w+)"?(?:\s+\w+)?\s+WHERE\s+(?:\w+\.)?workspace_id\s*=', re.I)


def tables_read_by_workspace() -> set[str]:
    found = set()
    for path in Path(__file__).resolve().parents[1].glob("app/**/*.py"):
        if path.name.startswith("postgres_"):          # the PostgreSQL adapters are not active; their SQL is checked by their own tests
            continue
        found |= set(FIRST_CONDITION.findall(path.read_text(encoding="utf-8", errors="ignore")))
    return found


def test_every_table_read_by_workspace_has_an_index_that_starts_with_workspace_id(seeded):
    _touch_everything(seeded)
    con = sqlite3.connect(config.ASSET_DATABASE_PATH)
    try:
        tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()]
        wanted = tables_read_by_workspace()
        scoped = [t for t in tables if t in wanted]
        missing = sorted(t for t in scoped if "workspace_id" not in _leading_columns(con, t) and t not in KNOWN)
    finally:
        con.close()
    print("SCOPED", len(scoped), "MISSING", missing)
    assert len(scoped) >= 10, scoped
    assert not missing, f"workspace tables without a leading workspace_id index: {missing}"
