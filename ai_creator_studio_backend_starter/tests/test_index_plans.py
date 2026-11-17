"""B-11: the real per-workspace queries of the tables that got a ``workspace_id`` index (see test_index_coverage) are answered THROUGH that index, not by scanning the table.
The SQL strings are the ones the application runs (copied from the modules); the plan is read from SQLite with EXPLAIN QUERY PLAN on the schema the application itself created."""
import sqlite3

import pytest

from app import config
from tests.test_authz_matrix import _fill, _operations, auth, client, seeded  # noqa: F401

W = "ws"
QUERIES = {
    "asset_provenance: day usage": ("asset_provenance", "SELECT COUNT(*) AS n FROM asset_provenance WHERE workspace_id=? AND event_type=? AND created_at>=?", (W, "asset.x", "2026-01-01")),
    "data_exports: list": ("data_exports", "SELECT export_id FROM data_exports WHERE workspace_id=? ORDER BY created_at DESC", (W,)),
    "model_drafts: open count": ("model_drafts", "SELECT COUNT(*) AS n FROM model_drafts WHERE workspace_id=? AND status='ready'", (W,)),
    "model_drafts: list": ("model_drafts", "SELECT * FROM model_drafts WHERE workspace_id=? ORDER BY created_at DESC, draft_id LIMIT 100", (W,)),
    "three_d_jobs: day usage": ("three_d_jobs", "SELECT COUNT(*) AS n FROM three_d_jobs WHERE workspace_id=? AND created_at>=?", (W, "2026-01-01")),
    "three_d_jobs: list": ("three_d_jobs", "SELECT * FROM three_d_jobs WHERE workspace_id=? ORDER BY created_at DESC, job_id LIMIT 100", (W,)),
    "video_jobs: day usage": ("video_jobs", "SELECT COUNT(*) AS n FROM video_jobs WHERE workspace_id=? AND created_at>=?", (W, "2026-01-01")),
    "video_jobs: list": ("video_jobs", "SELECT * FROM video_jobs WHERE workspace_id=? ORDER BY created_at DESC, job_id LIMIT 100", (W,)),
    "workspace_member_events: history": ("workspace_member_events", "SELECT at, actor_id, member_id, event, from_role, to_role FROM workspace_member_events WHERE workspace_id=? ORDER BY event_id", (W,)),
    "workspace_settings_history: history": ("workspace_settings_history", "SELECT at, actor_id, field, old_value, new_value FROM workspace_settings_history WHERE workspace_id=? ORDER BY event_id", (W,)),
}


@pytest.fixture
def schema(seeded):
    for method, path, op in _operations():
        if method == "get":
            query = {p["name"]: seeded.get(p["name"], "x") for p in op.get("parameters", []) if p.get("in") == "query" and p.get("required")}
            client.get(_fill(path, seeded), headers=auth("tok-a"), params=query)
    con = sqlite3.connect(config.ASSET_DATABASE_PATH)
    yield con
    con.close()


@pytest.mark.parametrize("name", sorted(QUERIES))
def test_the_query_uses_an_index_and_does_not_scan_the_table(schema, name):
    table, sql, args = QUERIES[name]
    plan = [r[-1] for r in schema.execute("EXPLAIN QUERY PLAN " + sql, args).fetchall()]
    assert any("USING" in step and "INDEX" in step for step in plan), plan
    assert not any(step.startswith(f"SCAN {table}") and "INDEX" not in step for step in plan), f"full scan of {table}: {plan}"
