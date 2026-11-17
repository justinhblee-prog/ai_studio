"""B-11: index coverage. Every table that is read per workspace (it has a ``workspace_id`` column) needs an index or primary key that STARTS with ``workspace_id``,
otherwise listing one workspace's rows scans the whole table as the data grows. Tables are created by the application itself (every module makes its own), so the
test first calls every GET operation once, then reads the schema from SQLite. Known gaps are listed in KNOWN (with a reason) and should shrink."""
import sqlite3

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


def test_every_workspace_table_has_an_index_that_starts_with_workspace_id(seeded):
    _touch_everything(seeded)
    con = sqlite3.connect(config.ASSET_DATABASE_PATH)
    try:
        tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()]
        scoped = [t for t in tables if "workspace_id" in {r[1] for r in con.execute(f'PRAGMA table_info("{t}")').fetchall()}]
        missing = sorted(t for t in scoped if "workspace_id" not in _leading_columns(con, t) and t not in KNOWN)
    finally:
        con.close()
    print("SCOPED", len(scoped), "MISSING", missing)
    assert len(scoped) >= 15, scoped
    assert not missing, f"workspace tables without a leading workspace_id index: {missing}"
