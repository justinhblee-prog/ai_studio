"""R-054: the operator usage aggregation: operators only, honest about measured / estimated / not measured, metadata only."""
import json
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from app import ops_usage
from tests.test_ops_overview import auth, client, env, job  # noqa: F401  (env: co-paid owned by a with editor c, co-two owned by b; operator = user-o)
from tests.test_workspace_library import glb


def usage(user="o", **params):
    return client.get("/internal/ops/usage", headers=auth(user), params=params)


def set_status(env_unused, job_id, status):
    import app.config as config
    with sqlite3.connect(config.GENERATION_DATABASE_PATH) as db:
        db.execute("UPDATE generation_jobs SET status=? WHERE job_id=?", (status, job_id))


@pytest.fixture
def seeded(env):
    ids = [job("co-paid", "a", 1), job("co-paid", "a", 2), job("co-paid", "c", 3), job("co-paid", "a", 4)]
    set_status(None, ids[0], "succeeded"); set_status(None, ids[1], "succeeded"); set_status(None, ids[2], "failed")   # ids[3] stays queued
    return ids


def rows_by_key(body):
    return {r["key"]: r for r in body["rows"]}


def test_only_an_operator_may_read_it(env):
    assert client.get("/internal/ops/usage").status_code == 401
    for who in "abc":
        assert usage(who).status_code == 403
    assert usage().status_code == 200


def test_by_service_counts_statuses_and_estimates_cost_only_for_billed_jobs(seeded):
    body = usage(by="service").json()
    tryon = rows_by_key(body)["tryon"]
    assert (tryon["events"], tryon["success"], tryon["failed"], tryon["pending"], tryon["blocked"]) == (4, 2, 1, 1, 0)
    assert tryon["estimated_cost_usd"] == 0.15, "two succeeded fashn jobs x $0.075; the failed one is not billed by this provider and the queued one is not billed yet"
    assert body["totals"]["events"] == 4 and body["totals"]["estimated_cost_usd"] == 0.15 and body["granularity"] == "day" and body["by"] == "service"


def test_by_company_user_and_provider(seeded):
    by_company = rows_by_key(usage(by="company").json())
    assert set(by_company) == {"co-paid"} and by_company["co-paid"]["events"] == 4
    by_user = rows_by_key(usage(by="user").json())
    assert by_user["user-a"]["events"] == 3 and by_user["user-c"]["events"] == 1
    assert by_user["user-a"]["success"] == 2 and by_user["user-c"]["failed"] == 1
    by_provider = rows_by_key(usage(by="provider").json())
    assert by_provider["fashn"]["events"] == 4


def test_other_services_appear_with_what_each_one_really_measures(env, monkeypatch):
    import app.config as config
    # a 3D upload (bytes), a model draft (character), a video job and an assist call, all in co-paid
    up = client.post("/v1/workspaces/co-paid/library", headers=auth("a"), data={"kind": "3d", "name": "chair"}, files={"file": ("c.glb", glb(), "model/gltf-binary")})
    assert up.status_code == 201, up.text
    assert client.post("/v1/workspaces/co-paid/model-drafts", headers=auth("a"), json={"v": {"hair": "wavy"}}).status_code == 201
    with sqlite3.connect(config.ASSET_DATABASE_PATH) as db:
        from app import video_jobs, assist
        video_jobs._init(db); assist._ensure(db)
        now = datetime.now(timezone.utc).isoformat()
        db.execute("INSERT INTO video_jobs(job_id, workspace_id, owner_id, status, provider, aspect, duration_seconds, motion, instruction, input_item_ids_json, created_at) VALUES ('v1','co-paid','user-a','failed','mock','9:16',6,'pan',NULL,'[]',?)", (now,))
        db.execute("INSERT INTO assist_usage VALUES ('co-paid','user-a','rules',1,1,10,?)", (now,))
    rows = rows_by_key(usage(by="service").json())
    assert rows["3d"]["events"] == 1 and rows["3d"]["bytes"] > 0
    assert rows["character"]["events"] == 1 and rows["video"]["failed"] == 1 and rows["assist"]["events"] == 1


def test_it_says_what_is_measured_estimated_and_not_measured(env):
    body = usage().json()
    cov = body["coverage"]
    assert cov["tryon"]["estimated"] == ["cost_usd"] and "duration_ms" in cov["tryon"]["not_measured"]
    assert cov["photo"]["measured"] == ["count", "status", "duration_ms"] and cov["market"]["source"] is None
    assert any("blocked" in n for n in body["not_measured"]) and any("invoice" in n for n in body["not_measured"]) and any("e-mail" in n for n in body["not_measured"])
    assert set(body["limits"]) == {"kill_switch_on", "workspace_monthly_limit", "global_monthly_limit", "stop_percent", "usd_limit_month_configured"}
    assert "from" in body and "to" in body and isinstance(body["storage_bytes_now"], int)


def test_the_period_and_the_bucket_size_are_checked(seeded):
    now = datetime.now(timezone.utc)
    hour = usage(group_by="hour", by="service", **{"from": (now - timedelta(hours=3)).isoformat(), "to": (now + timedelta(hours=1)).isoformat()}).json()
    assert {len(r["bucket"]) for r in hour["rows"]} == {13} and sum(r["events"] for r in hour["rows"]) == 4
    month = usage(group_by="month").json()
    assert {len(r["bucket"]) for r in month["rows"]} == {7}
    old = usage(**{"from": "2020-01-01T00:00:00Z", "to": "2020-01-03T00:00:00Z"}).json()
    assert old["rows"] == [] and old["totals"]["events"] == 0
    for bad in ({"from": "2026-11-17T00:00:00Z", "to": "2026-11-16T00:00:00Z"}, {"group_by": "hour", "from": "2026-01-01T00:00:00Z", "to": "2026-06-01T00:00:00Z"},
                {"from": "nonsense"}, {"group_by": "week"}, {"by": "name"}):
        assert usage(**bad).status_code == 422, bad


def test_nothing_private_is_in_the_answer(seeded):
    text = json.dumps(usage(by="user").json(), ensure_ascii=False) + json.dumps(usage(by="company").json(), ensure_ascii=False)
    for secret in ("secret prompt", "images.example.org", "private-model", "@"):
        assert secret not in text, secret


def test_a_row_cap_is_reported_not_hidden(seeded, monkeypatch):
    monkeypatch.setattr(ops_usage, "ROW_CAP", 2)
    body = usage().json()
    assert "tryon" in body["truncated_services"] and body["totals"]["events"] == 2
