"""R-043: the operator overview: operators only, correct totals and estimated spend, metadata only."""
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class PaidStub:
    name = "fashn"
    model = "stub"

    async def start(self, payload):
        return {"request_id": "r"}


def auth(t):
    return {"Authorization": f"Bearer token-{t}"}


@pytest.fixture
def env(tmp_path, monkeypatch):
    import app.config as config
    import app.main as main
    monkeypatch.setattr(config, "ASSET_STORAGE_DIR", tmp_path / "p")
    monkeypatch.setattr(config, "ASSET_DATABASE_PATH", tmp_path / "a.sqlite3")
    monkeypatch.setattr(config, "GENERATION_DATABASE_PATH", tmp_path / "g.sqlite3")
    monkeypatch.setattr(config, "ASSET_SIGNING_SECRET", "o" * 48)
    monkeypatch.setattr(config, "asset_api_tokens", lambda: {f"token-{n}": f"user-{n}" for n in "abco"})
    monkeypatch.setattr(config, "OPS_ADMIN_USER_IDS", frozenset({"user-o"}))
    monkeypatch.setattr(config, "PROVIDER_MODE", "mock")
    monkeypatch.setattr(main, "get_provider_for_job", lambda job: PaidStub() if job["workspace_id"] == "co-paid" else main.get_provider())
    monkeypatch.setattr(main, "get_provider", lambda: PaidStub())
    for k in ("AI_JOB_LIMIT_PER_WORKSPACE_MONTH", "AI_JOB_LIMIT_GLOBAL_MONTH", "AI_JOBS_DISABLED"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("AI_COST_LIMIT_USD_MONTH", "1000")
    for ws, owner in (("co-paid", "a"), ("co-two", "b")):
        assert client.post("/v1/workspaces", headers=auth(owner), json={"workspace_id": ws}).status_code == 201
    assert client.post("/v1/workspaces/co-paid/members", headers=auth("a"), json={"user_id": "user-c", "role": "editor"}).status_code == 201
    return monkeypatch


def job(ws, user, n):
    r = client.post("/v1/generation-jobs", headers=auth(user), json={"workspace_id": ws, "prompt": f"secret prompt {n}",
        "model_image_url": "https://images.example.org/private-model.png", "garment_image_url": "https://images.example.org/g.png"})
    assert r.status_code == 202, r.text
    return r.json()["job_id"]


def overview(user="o", **params):
    return client.get("/internal/ops/overview", headers=auth(user), params=params)


def test_only_an_operator_may_read_it(env):
    assert client.get("/internal/ops/overview").status_code == 401
    for who in "abc":
        assert overview(who).status_code == 403
    assert overview("o").status_code == 200


def test_totals_companies_providers_and_estimated_spend_add_up(env):
    import app.main as main
    for n in range(3):
        job("co-paid", "a", n)
    job("co-paid", "c", 9)
    env.setattr(main, "get_provider", lambda: main.get_provider.__wrapped__() if hasattr(main.get_provider, "__wrapped__") else PaidStub())
    body = overview().json()
    assert body["jobs"] == 4 and body["failed"] == 0 and body["failure_rate"] == 0.0 and body["active_companies"] == 1
    assert body["companies"] == [{"workspace_id": "co-paid", "members": 2, "jobs": 4, "failed": 0, "estimated_cost_usd": 0.3}]
    assert body["providers"] == [{"provider": "fashn", "jobs": 4, "failed": 0, "estimated_cost_usd": 0.3}]
    assert body["estimated_cost_usd"] == 0.3 == round(sum(p["estimated_cost_usd"] for p in body["providers"]), 6)


def test_failed_jobs_are_counted_apart_and_not_billed_for_fashn(env):
    import app.config as config
    ids = [job("co-paid", "a", n) for n in range(2)]
    db = sqlite3.connect(config.GENERATION_DATABASE_PATH)
    db.execute("UPDATE generation_jobs SET status='failed' WHERE job_id=?", (ids[0],)); db.commit()
    body = overview().json()
    assert body["jobs"] == 1 and body["failed"] == 1 and body["failure_rate"] == 0.5
    assert body["estimated_cost_usd"] == 0.075, "the failed job is not billed"


def test_controls_show_the_kill_switch_and_the_configured_limits(env):
    assert overview().json()["controls"] == {"kill_switch_on": False, "workspace_monthly_limit": 100, "global_monthly_limit": 500,
                                            "stop_percent": 90, "usd_limit_month_configured": True}
    env.setenv("AI_JOBS_DISABLED", "1")
    assert overview().json()["controls"]["kill_switch_on"] is True
    env.delenv("AI_COST_LIMIT_USD_MONTH")
    assert overview().json()["controls"]["usd_limit_month_configured"] is False


def test_only_metadata_is_returned_never_photos_prompts_or_addresses(env):
    job("co-paid", "a", 1)
    text = overview().text
    for forbidden in ("secret prompt", "images.example.org", "private-model", "payload", "prompt", "http"):
        assert forbidden not in text, forbidden


def test_the_month_must_be_valid_and_other_months_are_separate(env):
    job("co-paid", "a", 1)
    assert overview(month="2026-13").status_code == 422
    assert overview(month="2026-01").json()["jobs"] == 0


def test_latency_percentiles_come_from_finished_executions_of_the_month(env):
    import app.config as config
    from app.ops_overview import percentile
    ids = [job("co-paid", "a", n) for n in range(10)]
    db = sqlite3.connect(config.GENERATION_DATABASE_PATH)
    for i, job_id in enumerate(ids):   # run times 1..10 seconds
        db.execute("UPDATE generation_executions SET started_at='2026-11-16T10:00:00+00:00', finished_at=? WHERE job_id=?",
                   (f"2026-11-16T10:00:{i + 1:02d}+00:00", job_id))
    db.execute("UPDATE generation_jobs SET created_at='2026-11-16T10:00:00+00:00'"); db.commit()
    lat = overview(month="2026-11").json()["latency_seconds"]
    assert lat == {"count": 10, "avg": 5.5, "p50": 5.0, "p95": 10.0}
    assert overview(month="2026-10").json()["latency_seconds"] == {"count": 0, "avg": None, "p50": None, "p95": None}
    assert [percentile([], 50), percentile([5.0], 95), percentile([1.0, 2.0, 3.0, 4.0], 50)] == [None, 5.0, 2.0]


def test_failed_jobs_list_is_operator_only_newest_first_and_metadata_only(env):
    import app.config as config
    ids = [job("co-paid", "a", n) for n in range(3)]
    db = sqlite3.connect(config.GENERATION_DATABASE_PATH)
    for i, job_id in enumerate(ids[:2]):
        db.execute("UPDATE generation_jobs SET status='failed', error_code=?, updated_at=? WHERE job_id=?",
                   (f"PROVIDER_GENERATION_FAILED", f"2026-11-16T10:00:0{i}+00:00", job_id))
    db.commit()
    assert client.get("/internal/ops/failed-jobs").status_code == 401
    assert client.get("/internal/ops/failed-jobs", headers=auth("a")).status_code == 403
    rows = client.get("/internal/ops/failed-jobs", headers=auth("o")).json()
    assert [r["job_id"] for r in rows] == [ids[1], ids[0]], "newest first, the healthy job is not listed"
    assert rows[0]["error_code"] == "PROVIDER_GENERATION_FAILED" and rows[0]["workspace_id"] == "co-paid"
    assert set(rows[0]) == {"job_id", "workspace_id", "provider", "error_code", "created_at", "updated_at"}
    assert len(client.get("/internal/ops/failed-jobs", headers=auth("o"), params={"limit": 1}).json()) == 1
    assert client.get("/internal/ops/failed-jobs", headers=auth("o"), params={"limit": 0}).status_code == 422


def test_downloads_list_is_operator_only_newest_first(env):
    import app.config as config
    from app import lookbook
    lookbook.initialize()
    db = sqlite3.connect(config.ASSET_DATABASE_PATH)
    for i in range(3):
        db.execute("INSERT INTO download_audit(download_id,workspace_id,actor_id,kind,object_id,size_bytes,created_at) VALUES(?,?,?,?,?,?,?)",
                   (f"dl_{i}", "co-paid", "user-a", "lookbook_package", f"lbx_{i}", 100 + i, f"2026-11-16T10:00:0{i}+00:00"))
    db.commit()
    assert client.get("/internal/ops/downloads").status_code == 401
    assert client.get("/internal/ops/downloads", headers=auth("b")).status_code == 403
    rows = client.get("/internal/ops/downloads", headers=auth("o")).json()
    assert [r["download_id"] for r in rows] == ["dl_2", "dl_1", "dl_0"] and rows[0]["size_bytes"] == 102
    assert len(client.get("/internal/ops/downloads", headers=auth("o"), params={"limit": 2}).json()) == 2


def test_deletion_requests_list_shows_the_grace_deadline_and_never_the_reason(env):
    import app.config as config
    from datetime import datetime, timedelta, timezone
    client.get("/v1/me/legal-status", headers=auth("a"))   # creates the legal / deletion tables
    now = datetime.now(timezone.utc)
    db = sqlite3.connect(config.ASSET_DATABASE_PATH)
    for rid, who, status, days in (("del_old", "user-a", "pending", 10), ("del_new", "user-b", "pending", 2), ("del_done", "user-c", "completed", 20)):
        db.execute("INSERT INTO deletion_requests(request_id,user_id,scope,workspace_id,status,reason,requested_at) VALUES(?,?,?,?,?,?,?)",
                   (rid, who, "workspace_content", "co-paid", status, "private reason text", (now - timedelta(days=days)).isoformat()))
    db.commit()
    assert client.get("/internal/ops/deletion-requests").status_code == 401
    assert client.get("/internal/ops/deletion-requests", headers=auth("a")).status_code == 403
    rows = client.get("/internal/ops/deletion-requests", headers=auth("o")).json()
    assert [(r["request_id"], r["grace_expired"]) for r in rows] == [("del_old", True), ("del_new", False)], "pending only, oldest first"
    assert rows[0]["due_at"][:10] == (now - timedelta(days=3)).isoformat()[:10]
    assert "private reason text" not in str(rows) and "reason" not in rows[0]
    done = client.get("/internal/ops/deletion-requests", headers=auth("o"), params={"status": "completed"}).json()
    assert [r["request_id"] for r in done] == ["del_done"]
    assert client.get("/internal/ops/deletion-requests", headers=auth("o"), params={"status": "x"}).status_code == 422


def test_rollup_has_every_bucket_with_correct_counts_and_estimated_cost(env):
    import app.config as config
    ids = [job("co-paid", "a", n) for n in range(5)]
    db = sqlite3.connect(config.GENERATION_DATABASE_PATH)
    stamps = ["2026-11-14T10:05:00+00:00", "2026-11-14T10:55:00+00:00", "2026-11-14T11:00:00+00:00", "2026-11-16T23:59:59+00:00", "2026-11-16T09:00:00+00:00"]
    for job_id, stamp in zip(ids, stamps):
        db.execute("UPDATE generation_jobs SET created_at=? WHERE job_id=?", (stamp, job_id))
    db.execute("UPDATE generation_jobs SET status='failed' WHERE job_id=?", (ids[1],)); db.commit()
    day = client.get("/internal/ops/rollup", headers=auth("o"), params={"granularity": "day", "start": "2026-11-13T00:00:00Z", "end": "2026-11-17T00:00:00Z"}).json()
    assert [b["bucket"] for b in day["buckets"]] == ["2026-11-13", "2026-11-14", "2026-11-15", "2026-11-16"], "empty days are present"
    assert [(b["jobs"], b["failed"], b["estimated_cost_usd"]) for b in day["buckets"]] == [(0, 0, 0.0), (2, 1, 0.15), (0, 0, 0.0), (2, 0, 0.15)]
    hour = client.get("/internal/ops/rollup", headers=auth("o"), params={"granularity": "hour", "start": "2026-11-14T10:00:00Z", "end": "2026-11-14T12:00:00Z"}).json()
    assert [(b["bucket"], b["jobs"], b["failed"]) for b in hour["buckets"]] == [("2026-11-14T10", 1, 1), ("2026-11-14T11", 1, 0)]
    month = client.get("/internal/ops/rollup", headers=auth("o"), params={"granularity": "month", "start": "2026-10-01T00:00:00Z", "end": "2026-12-01T00:00:00Z"}).json()
    assert [(b["bucket"], b["jobs"], b["failed"]) for b in month["buckets"]] == [("2026-10", 0, 0), ("2026-11", 4, 1)]
    assert sum(b["jobs"] for b in day["buckets"]) == sum(b["jobs"] for b in month["buckets"]) == 4, "the granularities agree"


def test_rollup_is_operator_only_and_checks_its_range(env):
    assert client.get("/internal/ops/rollup").status_code == 401
    assert client.get("/internal/ops/rollup", headers=auth("a")).status_code == 403
    ok = client.get("/internal/ops/rollup", headers=auth("o"))
    assert ok.status_code == 200 and len(ok.json()["buckets"]) == 7, "default: the last 7 days, today included"
    assert client.get("/internal/ops/rollup", headers=auth("o"), params={"granularity": "week"}).status_code == 422
    for bad in ({"start": "2026-11-17T00:00:00Z", "end": "2026-11-16T00:00:00Z"}, {"start": "nonsense"},
                {"granularity": "hour", "start": "2026-01-01T00:00:00Z", "end": "2026-06-01T00:00:00Z"}):
        assert client.get("/internal/ops/rollup", headers=auth("o"), params=bad).status_code == 422, bad
