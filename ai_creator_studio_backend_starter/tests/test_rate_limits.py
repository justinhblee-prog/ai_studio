"""R-067: request-rate rules (upload / generate / download / report), one 429 format, refusals recorded and visible to the operator, nothing stored for a refused action."""
import io
import json
import sqlite3
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import config
from app.main import app
from tests.test_photo_steps_api import auth, env  # noqa: F401  (wa: owner a + viewer c, wb: owner b)

client = TestClient(app)
KEYS = {"code", "message", "retry_after_seconds", "retry_at"}


@pytest.fixture
def on(env, monkeypatch):
    """Rate limiting ON (the older tests run with it off) and an operator + an extra editor."""
    monkeypatch.setattr(config, "RATE_LIMITS_ENABLED", True)
    monkeypatch.setattr(config, "asset_api_tokens", lambda: {"token-a": "user-a", "token-b": "user-b", "token-c": "user-c", "token-d": "user-d", "token-o": "user-o"})
    monkeypatch.setattr(config, "OPS_ADMIN_USER_IDS", frozenset({"user-o"}))
    assert client.post("/v1/workspaces/wa/members", headers=auth("a"), json={"user_id": "user-d", "role": "editor"}).status_code == 201
    return env


def png(shade):
    buf = io.BytesIO(); Image.new("RGB", (10, 10), (shade, shade, shade)).save(buf, format="PNG"); return buf.getvalue()


def up(who="a", ws="wa", shade=1):
    return client.post("/v1/assets/images", headers=auth(who), data={"workspace_id": ws, "rights_confirmed": "true"}, files={"file": ("a.png", png(shade), "image/png")})


def assert_429(r, code, **extra):
    assert r.status_code == 429, (r.status_code, r.text)
    d = r.json()["detail"]
    assert KEYS <= set(d), d
    assert d["code"] == code and d["retry_after_seconds"] >= 1 and r.headers["Retry-After"] == str(d["retry_after_seconds"])
    assert datetime.fromisoformat(d["retry_at"]) > datetime.now(timezone.utc)
    for k, v in extra.items():
        assert d[k] == v, (k, d)
    return d


def asset_count(ws="wa"):
    return len(client.get(f"/v1/assets?workspace_id={ws}&kind=image", headers=auth("a" if ws == "wa" else "b")).json()["items"])


def test_the_user_limit_allows_exactly_n_then_refuses_and_stores_nothing(on, monkeypatch):
    monkeypatch.setattr(config, "RATE_UPLOAD_USER_PER_MINUTE", 3)
    before = asset_count()
    for i in range(3):
        assert up(shade=10 + i).status_code == 201, i
    d = assert_429(up(shade=50), "RATE_LIMITED", scope="upload", limit=3, window_seconds=60, per="user")
    assert d["retry_after_seconds"] <= 60 and "retry_estimated" not in d
    assert asset_count() == before + 3, "the refused upload stored nothing"
    assert_429(up(shade=51), "RATE_LIMITED"), "still refused: a refusal is not counted as a hit, but the window is still full"
    assert up("b", "wb", 60).status_code == 201, "another user has their own allowance"


def test_the_workspace_limit_is_shared_by_its_members_and_independent_of_other_workspaces(on, monkeypatch):
    monkeypatch.setattr(config, "RATE_UPLOAD_USER_PER_MINUTE", 100)
    monkeypatch.setattr(config, "RATE_UPLOAD_WORKSPACE_PER_HOUR", 4)
    assert up("a", shade=1).status_code == 201 and up("a", shade=2).status_code == 201
    assert up("d", shade=3).status_code == 201 and up("d", shade=4).status_code == 201
    d = assert_429(up("a", shade=5), "RATE_LIMITED", scope="upload", per="workspace", limit=4, window_seconds=3600)
    assert_429(up("d", shade=6), "RATE_LIMITED", per="workspace")
    assert up("b", "wb", 7).status_code == 201, "another workspace"


def test_the_window_slides_and_the_retry_time_is_real(on, monkeypatch):
    monkeypatch.setattr(config, "RATE_UPLOAD_USER_PER_MINUTE", 2)
    up(shade=1); up(shade=2)
    d = assert_429(up(shade=3), "RATE_LIMITED")
    with sqlite3.connect(config.ASSET_DATABASE_PATH) as c:
        c.execute("UPDATE rate_limit_hits SET at=at-61")
    assert up(shade=4).status_code == 201, "after the window the user may go on"
    assert up(shade=5).status_code == 201
    import time
    with sqlite3.connect(config.ASSET_DATABASE_PATH) as c:      # age the older of the two hits that are still in the window by 30 seconds
        c.execute("UPDATE rate_limit_hits SET at=at-30 WHERE hit_id=(SELECT hit_id FROM rate_limit_hits WHERE at>? ORDER BY at LIMIT 1)", (time.time() - 60,))
    d2 = assert_429(up(shade=6), "RATE_LIMITED")
    assert 1 <= d2["retry_after_seconds"] <= 31, "the wait is until the OLDEST hit in the window leaves it"


def test_a_zero_limit_and_the_master_switch_turn_the_rule_off(on, monkeypatch):
    monkeypatch.setattr(config, "RATE_UPLOAD_USER_PER_MINUTE", 0)
    monkeypatch.setattr(config, "RATE_UPLOAD_WORKSPACE_PER_HOUR", 0)
    for i in range(5):
        assert up(shade=i + 1).status_code == 201
    monkeypatch.setattr(config, "RATE_UPLOAD_USER_PER_MINUTE", 1)
    monkeypatch.setattr(config, "RATE_LIMITS_ENABLED", False)
    assert up(shade=20).status_code == 201 and up(shade=21).status_code == 201


def test_generate_is_one_budget_across_jobs_drafts_and_photo_steps(on, monkeypatch):
    monkeypatch.setattr(config, "RATE_GENERATE_USER_PER_MINUTE", 3)
    job = lambda n: client.post("/v1/generation-jobs", headers=auth("a"), json={"workspace_id": "wa", "prompt": f"p{n}", "model_image_url": "https://images.example.org/m.png", "garment_image_url": "https://images.example.org/g.png"})
    draft = lambda: client.post("/v1/workspaces/wa/model-drafts", headers=auth("a"), json={"v": {"gender": "female"}})
    assert job(1).status_code == 202 and draft().status_code == 201
    assert client.post("/v1/workspaces/wa/photo-steps", headers=auth("a"), json={"asset_id": on["asset"], "steps": [{"op": "auto_crop", "margin_pct": 0}]}).status_code == 201
    assert_429(job(2), "RATE_LIMITED", scope="generate", limit=3)
    assert_429(draft(), "RATE_LIMITED", scope="generate")
    assert up().status_code == 201, "uploads have their own budget"
    assert len(client.get("/v1/generation-jobs", params={"workspace_id": "wa"}, headers=auth("a")).json()) == 1, "the refused job was not created"


def test_replaying_an_idempotency_key_is_not_a_new_action(on, monkeypatch):
    monkeypatch.setattr(config, "RATE_GENERATE_USER_PER_MINUTE", 1)
    h = {**auth("a"), "Idempotency-Key": "k-1"}
    body = {"workspace_id": "wa", "model_image_url": "https://images.example.org/m.png", "garment_image_url": "https://images.example.org/g.png"}
    first = client.post("/v1/generation-jobs", headers=h, json=body)
    again = client.post("/v1/generation-jobs", headers=h, json=body)
    assert first.status_code == 202 and again.status_code == 202 and again.json()["job_id"] == first.json()["job_id"]
    assert client.post("/v1/generation-jobs", headers=auth("a"), json={**body, "prompt": "new"}).status_code == 429


def test_downloads_are_limited_per_user(on, monkeypatch):
    monkeypatch.setattr(config, "RATE_DOWNLOAD_USER_PER_MINUTE", 2)
    asset = on["asset"]
    versions = client.get(f"/v1/assets/{asset}/versions", headers=auth("a")).json()
    vid = (versions["items"] if isinstance(versions, dict) else versions)[0]["version_id"]
    get = lambda who="a": client.get(f"/v1/assets/{asset}/versions/{vid}/preview-content", headers=auth(who))
    assert get().status_code == 200 and get().status_code == 200
    assert_429(get(), "RATE_LIMITED", scope="download", per="user", limit=2)
    assert get("c").status_code == 200, "a different user"


def test_reports_are_limited_per_minute_and_the_answer_still_reveals_nothing_else(on, monkeypatch):
    monkeypatch.setattr(config, "RATE_REPORT_USER_PER_MINUTE", 2)
    ids = [up("a", shade=40 + i).json()["asset_id"] for i in range(3)]
    rep = lambda aid: client.post("/v1/content-reports", headers=auth("b"), json={"asset_id": aid, "category": "other"})
    assert rep(ids[0]).status_code == 202 and rep("ast_does_not_exist").status_code == 202
    assert_429(rep(ids[1]), "RATE_LIMITED", scope="report", limit=2)


def test_every_older_quota_answers_in_the_same_shape(on, monkeypatch):
    # daily job limit
    monkeypatch.setattr(config, "GENERATION_DAILY_JOB_LIMIT_PER_WORKSPACE", 1)
    body = {"workspace_id": "wa", "model_image_url": "https://images.example.org/m.png", "garment_image_url": "https://images.example.org/g.png"}
    assert client.post("/v1/generation-jobs", headers=auth("a"), json=body).status_code == 202
    d = assert_429(client.post("/v1/generation-jobs", headers=auth("a"), json={**body, "prompt": "x"}), "DAILY_JOB_LIMIT_EXCEEDED")
    assert d["limit"] == 1 and d["used"] == 1
    # content reports per day
    monkeypatch.setattr(config, "CONTENT_REPORT_DAILY_LIMIT", 1)
    a1, a2 = up("a", shade=70).json()["asset_id"], up("a", shade=71).json()["asset_id"]
    assert client.post("/v1/content-reports", headers=auth("b"), json={"asset_id": a1, "category": "other"}).status_code == 202
    d = assert_429(client.post("/v1/content-reports", headers=auth("b"), json={"asset_id": a2, "category": "other"}), "REPORT_DAILY_LIMIT", limit=1)
    assert d["retry_after_seconds"] <= 86400 and "retry_estimated" not in d, "computed from the oldest report"
    # exports per day
    monkeypatch.setattr(config, "EXPORT_DAILY_LIMIT_PER_WORKSPACE", 1)
    assert client.post("/v1/workspaces/wa/exports", headers=auth("a")).status_code == 201
    assert_429(client.post("/v1/workspaces/wa/exports", headers=auth("a")), "EXPORT_LIMIT")
    # video per day (an estimate is flagged as one)
    monkeypatch.setattr(config, "VIDEO_DAILY_LIMIT", 1)
    from tests.test_video_jobs import item, make, pattern
    ids = [item(pattern(1), name="a"), item(pattern(2), name="b")]
    assert make({"input_item_ids": ids}).status_code == 201
    d = assert_429(make({"input_item_ids": ids}), "VIDEO_DAILY_LIMIT")
    assert d.get("retry_estimated") is True and d["limit"] == 1


def test_refusals_are_recorded_and_the_operator_sees_the_policies_and_the_counts(on, monkeypatch):
    monkeypatch.setattr(config, "RATE_UPLOAD_USER_PER_MINUTE", 1)
    up(shade=1); up(shade=2); up(shade=3)
    rl = client.get("/internal/ops/rate-limits", headers=auth("o"))
    assert rl.status_code == 200, rl.text
    body = rl.json()
    pol = {(p["scope"], p["per"]): p for p in body["policies"]}
    assert pol[("upload", "user")]["limit"] == 1 and pol[("upload", "user")]["enabled"] is True and pol[("upload", "workspace")]["limit"] == 300
    assert pol[("generate", "user")]["env"] == "RATE_GENERATE_USER_PER_MINUTE" and set(s for s, _ in pol) == {"upload", "generate", "download", "report"}
    assert sum(b["n"] for b in body["blocked"] if b["scope"] == "upload" and b["kind"] == "user") == 2
    assert any("sign-up" in n for n in body["coverage"]["not_measured"]) and any("per-IP" in n for n in body["coverage"]["not_measured"])
    assert "user-a" not in json.dumps(body) and "wa" not in json.dumps(body["blocked"])
    usage = client.get("/internal/ops/usage", headers=auth("o"), params={"by": "service"}).json()
    row = next(r for r in usage["rows"] if r["key"] == "upload")
    assert row["blocked"] == 2 and usage["totals"]["blocked"] == 2
    assert client.get("/internal/ops/rate-limits", headers=auth("a")).status_code == 403 and client.get("/internal/ops/rate-limits").status_code == 401
    for days in (0, 91):
        assert client.get("/internal/ops/rate-limits", headers=auth("o"), params={"days": days}).status_code == 422


def test_the_counters_hold_only_hashes(on, monkeypatch):
    monkeypatch.setattr(config, "RATE_UPLOAD_USER_PER_MINUTE", 5)
    up()
    with sqlite3.connect(config.ASSET_DATABASE_PATH) as c:
        rows = c.execute("SELECT scope, kind, subject FROM rate_limit_hits").fetchall()
    assert rows and all(len(r[2]) == 20 and "user-a" not in r[2] and r[2] != "wa" for r in rows)


def test_the_real_defaults_are_conservative_and_on():
    import os, subprocess, sys
    from pathlib import Path
    clean = {k: v for k, v in os.environ.items() if not k.startswith("RATE_")}
    out = subprocess.run([sys.executable, "-c", "import app.config as c; print(c.RATE_LIMITS_ENABLED, c.RATE_UPLOAD_USER_PER_MINUTE, c.RATE_UPLOAD_WORKSPACE_PER_HOUR, c.RATE_GENERATE_USER_PER_MINUTE, "
                         "c.RATE_GENERATE_WORKSPACE_PER_HOUR, c.RATE_DOWNLOAD_USER_PER_MINUTE, c.RATE_REPORT_USER_PER_MINUTE)"], cwd=Path(__file__).resolve().parents[1], env=clean,
                         capture_output=True, text=True, check=True).stdout.strip()
    assert out == "True 30 300 10 120 60 5"


def test_the_new_tables_do_not_block_a_purge_and_the_blocked_rows_go_with_the_workspace(on, monkeypatch):
    from scripts import purge_requests as purge
    monkeypatch.setattr(config, "RATE_UPLOAD_USER_PER_MINUTE", 1)
    up(shade=1); up(shade=2)
    with sqlite3.connect(config.ASSET_DATABASE_PATH, isolation_level=None) as db:
        assert db.execute("SELECT COUNT(*) FROM rate_limit_blocked WHERE workspace_id='wa'").fetchone()[0] == 1
        db.execute("PRAGMA foreign_keys=ON")
        plan = purge.build_plan([db], {"request_id": "r", "scope": "workspace_content", "user_id": "user-a", "workspace_id": "wa"}, config.ASSET_STORAGE_DIR, config.OUTPUT_DIR)
        assert plan.blocked == [] and plan.rows.get("rate_limit_blocked") == 1
        acct = purge.build_plan([db], {"request_id": "r2", "scope": "account", "user_id": "user-a", "workspace_id": None}, config.ASSET_STORAGE_DIR, config.OUTPUT_DIR)
        assert not [b for b in acct.blocked if b.startswith("UNMAPPED")], acct.blocked
