"""R-066: the operator audit view: operators only, filtered and paged, ids and states only (never comments, notes or report details)."""
import io
import json
import sqlite3
import uuid
from datetime import datetime, timezone

import pytest
from PIL import Image

from tests.test_ops_overview import auth, client, env  # noqa: F401  (co-paid: owner a + editor c; co-two: owner b; operator = user-o)

SECRETS = ("SECRET-COMMENT", "SECRET-NOTE", "SECRET-DETAIL", "SECRET-NAME")


def upload(ws="co-paid", who="a"):
    buf = io.BytesIO(); Image.new("RGB", (12, 12), (3, 3, 3)).save(buf, format="PNG")
    r = client.post("/v1/assets/images", headers=auth(who), data={"workspace_id": ws, "rights_confirmed": "true"}, files={"file": ("SECRET-NAME.png", buf.getvalue(), "image/png")})
    assert r.status_code == 201, r.text
    return r.json()["asset_id"]


def audit(user="o", **params):
    return client.get("/internal/ops/audit", headers=auth(user), params=params)


@pytest.fixture
def busy(env):
    import app.config as config
    asset = upload()
    rv = client.post("/v1/workspaces/co-paid/reviews", headers=auth("c"), json={"asset_id": asset, "comment": "SECRET-COMMENT"}).json()
    assert client.post(f"/v1/workspaces/co-paid/reviews/{rv['review_id']}/approve", headers=auth("a"), json={"comment": "SECRET-COMMENT"}).status_code == 200
    assert client.put("/internal/ops/customers/co-paid/contract", headers=auth("o"), json={"plan": "pilot", "status": "active"}).status_code == 200
    assert client.post("/v1/content-reports", headers=auth("b"), json={"asset_id": asset, "category": "other", "details": "SECRET-DETAIL"}).status_code == 202
    rid = client.get("/internal/moderation/reports", headers=auth("o")).json()
    rid = (rid["items"] if isinstance(rid, dict) else rid)[0]["report_id"]
    assert client.post(f"/internal/moderation/reports/{rid}/resolve", headers=auth("o"), json={"decision": "restore", "note": "SECRET-NOTE"}).status_code == 200
    with sqlite3.connect(config.ASSET_DATABASE_PATH) as c:
        c.execute("""CREATE TABLE IF NOT EXISTS download_audit (download_id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, actor_id TEXT NOT NULL, kind TEXT NOT NULL,
            object_id TEXT NOT NULL, size_bytes INTEGER NOT NULL, created_at TEXT NOT NULL)""")
        c.execute("INSERT INTO download_audit VALUES (?,?,?,?,?,?,?)", ("dl_" + uuid.uuid4().hex, "co-two", "user-b", "lookbook_package", "exp_1", 10, datetime.now(timezone.utc).isoformat()))
    return {"asset": asset, "review": rv["review_id"], "report": rid}


def test_every_source_shows_up_with_ids_and_states_only(busy):
    body = audit(limit=200).json()
    rows = body["items"]
    assert {r["source"] for r in rows} == {"review", "contract", "download", "report", "asset"}
    actions = {r["action"] for r in rows}
    assert {"review.request", "review.approve", "download.lookbook_package", "report.opened"} <= actions, actions
    assert all(set(r) == {"at", "source", "workspace_id", "actor_id", "action", "object_type", "object_id"} for r in rows)
    text = json.dumps(body)
    for secret in SECRETS:
        assert secret not in text, secret
    assert "@" not in text
    by = {r["action"]: r for r in rows}
    assert by["review.request"]["actor_id"] == "user-c" and by["review.approve"]["actor_id"] == "user-a" and by["review.approve"]["object_id"] == busy["review"]
    assert by["download.lookbook_package"]["workspace_id"] == "co-two" and by["report.opened"]["actor_id"] == "user-b" and by["report.opened"]["object_id"] == busy["report"]
    assert [r["at"] for r in rows] == sorted((r["at"] for r in rows), reverse=True), "newest first"


def test_filters_workspace_actor_source_and_time(busy):
    only_two = audit(workspace_id="co-two", limit=200).json()["items"]
    assert only_two and {r["workspace_id"] for r in only_two} == {"co-two"}
    mine = audit(actor_id="user-c", limit=200).json()["items"]
    assert mine and {r["actor_id"] for r in mine} == {"user-c"}
    two_sources = audit(source=["review", "download"], limit=200).json()
    assert {r["source"] for r in two_sources["items"]} == {"review", "download"} and two_sources["sources"] == ["review", "download"]
    assert audit(**{"from": "2000-01-01", "to": "2000-02-01"}).json()["items"] == []
    assert audit(**{"from": "2000-01-01T00:00:00Z"}).json()["items"], "ISO time with Z is accepted"
    assert audit(workspace_id="no-such", limit=200).json()["items"] == []
    both = audit(workspace_id="co-paid", actor_id="user-a", source="review", limit=200).json()["items"]
    assert [r["action"] for r in both] == ["review.approve"]


def test_paging_covers_everything_once(busy):
    everything = audit(limit=200).json()["items"]
    assert len(everything) >= 6
    seen, offset = [], 0
    while True:
        page = audit(limit=2, offset=offset).json()
        seen += page["items"]
        if page["next_offset"] is None:
            break
        assert page["next_offset"] == offset + 2 and len(page["items"]) == 2
        offset = page["next_offset"]
    assert seen == everything, "paging returns the same rows in the same order, none twice, none missing"


def test_bad_parameters_are_refused(busy):
    for params in ({"from": "soon"}, {"to": "later"}, {"limit": 0}, {"limit": 201}, {"offset": -1}, {"source": "nonsense"}, {"offset": 900, "limit": 200}):
        assert audit(**params).status_code == 422, params
    assert audit(offset=800, limit=200).status_code == 200, "the last allowed window"


def test_only_operators_may_read_it(busy):
    for who in "abc":
        assert audit(who).status_code == 403
    assert client.get("/internal/ops/audit").status_code == 401


def test_an_empty_system_gives_an_empty_list_and_still_says_what_is_not_measured(env):
    body = audit().json()
    assert body["items"] == []
    assert body["next_offset"] is None
    assert any("suspension" in n for n in body["coverage"]["not_measured"]) and any("READS" in n for n in body["coverage"]["not_measured"])
    assert set(body["coverage"]["measured"]) == {"review", "contract", "download", "report", "asset"}
