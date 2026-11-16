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
