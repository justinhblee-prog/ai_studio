"""R-042: the company usage answer: isolation, who sees whom, totals, failed jobs, no provider prices."""
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def auth(t):
    return {"Authorization": f"Bearer token-{t}"}


@pytest.fixture
def env(tmp_path, monkeypatch):
    import app.config as config
    monkeypatch.setattr(config, "ASSET_STORAGE_DIR", tmp_path / "private")
    monkeypatch.setattr(config, "ASSET_DATABASE_PATH", tmp_path / "a.sqlite3")
    monkeypatch.setattr(config, "GENERATION_DATABASE_PATH", tmp_path / "g.sqlite3")
    monkeypatch.setattr(config, "ASSET_SIGNING_SECRET", "u" * 48)
    monkeypatch.setattr(config, "asset_api_tokens", lambda: {f"token-{n}": f"user-{n}" for n in "abcd"})
    monkeypatch.setattr(config, "PROVIDER_MODE", "mock")
    monkeypatch.delenv("AI_JOB_LIMIT_PER_WORKSPACE_MONTH", raising=False)
    for ws, owner in (("ws-one", "a"), ("ws-two", "d")):
        assert client.post("/v1/workspaces", headers=auth(owner), json={"workspace_id": ws}).status_code == 201
    assert client.post("/v1/workspaces/ws-one/members", headers=auth("a"), json={"user_id": "user-b", "role": "editor"}).status_code == 201
    assert client.post("/v1/workspaces/ws-one/members", headers=auth("a"), json={"user_id": "user-c", "role": "viewer"}).status_code == 201
    return tmp_path


def job(ws, user, n):
    r = client.post("/v1/generation-jobs", headers=auth(user), json={"workspace_id": ws, "prompt": f"p{n}",
        "model_image_url": "https://images.example.org/m.png", "garment_image_url": "https://images.example.org/g.png"})
    assert r.status_code == 202, r.text
    return r.json()["job_id"]


def usage(ws, user, **params):
    return client.get(f"/v1/workspaces/{ws}/usage", headers=auth(user), params=params)


def test_owner_sees_every_member_and_the_totals_and_the_limit(env):
    for n in range(3):
        job("ws-one", "a", n)
    for n in range(2):
        job("ws-one", "b", 10 + n)
    body = usage("ws-one", "a").json()
    assert body["scope"] == "workspace" and body["jobs"] == 5 and body["failed"] == 0 and body["services"] == {"tryon": 5}
    assert [(m["user_id"], m["jobs"]) for m in body["members"]] == [("user-a", 3), ("user-b", 2)]
    assert body["limit"] == {"monthly_jobs": 100, "counted_against_limit": 0}, "mock jobs are shown but do not count against the limit"
    assert sum(m["jobs"] for m in body["members"]) == body["jobs"], "the total equals the sum of the rows"


def test_an_ordinary_member_sees_only_their_own_numbers(env):
    job("ws-one", "a", 1); job("ws-one", "b", 2); job("ws-one", "b", 3)
    for who, expected in (("b", 2), ("c", 0)):
        body = usage("ws-one", who).json()
        assert body["scope"] == "self" and body["jobs"] == expected and body["limit"] is None
        assert [m["user_id"] for m in body["members"]] == [f"user-{who}"]
        assert "user-a" not in str(body)


def test_another_company_is_invisible_in_both_directions(env):
    job("ws-one", "a", 1); job("ws-two", "d", 2); job("ws-two", "d", 3)
    assert usage("ws-one", "d").status_code == 404 and usage("ws-two", "a").status_code == 404, "not a member = no such workspace"
    assert usage("ws-one", "a").json()["jobs"] == 1 and usage("ws-two", "d").json()["jobs"] == 2
    assert usage("ws-one", "a").status_code == 200 and client.get("/v1/workspaces/ws-one/usage").status_code == 401


def test_failed_jobs_are_listed_apart_and_not_counted(env):
    ids = [job("ws-one", "a", n) for n in range(3)]
    import app.config as config
    db = sqlite3.connect(config.GENERATION_DATABASE_PATH)
    db.execute("UPDATE generation_jobs SET status='failed' WHERE job_id=?", (ids[0],)); db.commit()
    body = usage("ws-one", "a").json()
    assert body["jobs"] == 2 and body["failed"] == 1 and body["members"][0]["jobs"] == 2 and body["members"][0]["failed"] == 1


def test_months_are_separate_and_the_month_must_be_valid(env):
    import app.config as config
    ids = [job("ws-one", "a", n) for n in range(2)]
    db = sqlite3.connect(config.GENERATION_DATABASE_PATH)
    db.execute("UPDATE generation_jobs SET created_at='2026-10-31T23:59:59+00:00' WHERE job_id=?", (ids[0],)); db.commit()
    assert usage("ws-one", "a", month="2026-10").json()["jobs"] == 1
    assert usage("ws-one", "a").json()["jobs"] == 1, "the other job is in the current month"
    assert usage("ws-one", "a", month="2026-11").json()["month"] == "2026-11"
    for bad in ("2026-13", "26-1", "november", "2026-00"):
        assert usage("ws-one", "a", month=bad).status_code == 422, bad


def test_the_answer_never_contains_provider_prices(env):
    job("ws-one", "a", 1)
    text = usage("ws-one", "a").text.lower()
    assert "usd" not in text and "cost" not in text and "price" not in text
