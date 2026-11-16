"""R-071: the demo seed: complete, valid through the application's own rules, idempotent, and it refuses anything that could be real."""
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app import config
from scripts import seed_demo

H = lambda who: {"Authorization": f"Bearer {seed_demo.USERS[who][0]}"}


@pytest.fixture
def fresh(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ASSET_STORAGE_DIR", tmp_path / "private")
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path / "outputs")
    monkeypatch.setattr(config, "ASSET_DATABASE_PATH", tmp_path / "demo.sqlite3")
    monkeypatch.setattr(config, "GENERATION_DATABASE_PATH", None)
    monkeypatch.setattr(config, "ASSET_SIGNING_SECRET", "d" * 48)
    monkeypatch.setattr(config, "PROVIDER_MODE", "mock")
    monkeypatch.setattr(config, "SUPABASE_URL", "")
    monkeypatch.setattr(config, "DATABASE_BACKEND", "sqlite")
    monkeypatch.setattr(config, "asset_api_tokens", config.asset_api_tokens)       # the seed replaces these in this process: restore afterwards
    monkeypatch.setattr(config, "RATE_LIMITS_ENABLED", config.RATE_LIMITS_ENABLED)
    for name in ("SUPABASE_URL", "APP_ENV", "ENVIRONMENT", "ENV", "VERCEL_ENV", "DATABASE_BACKEND"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("DEMO_SEED", "1")
    (tmp_path / "outputs").mkdir(exist_ok=True)
    return tmp_path


def rows(tmp, sql, *args):
    with sqlite3.connect(tmp / "demo.sqlite3") as c:
        return c.execute(sql, args).fetchall()


def snapshot(tmp):
    with sqlite3.connect(tmp / "demo.sqlite3") as c:
        return {t: c.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for (t,) in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}


def test_the_seed_creates_everything_the_request_lists(fresh, capsys):
    assert seed_demo.main([]) == 0
    out = capsys.readouterr().out
    assert "done" in out and "ASSET_API_TOKENS=demo-token-owner:demo-owner" in out
    members = dict(rows(fresh, "SELECT user_id, role FROM workspace_members WHERE workspace_id='demo-studio'"))
    assert members == {"demo-owner": "owner", "demo-admin": "admin", "demo-editor": "editor", "demo-editor2": "editor", "demo-viewer": "viewer"}
    kinds = dict(rows(fresh, "SELECT kind, COUNT(*) FROM workspace_library_items WHERE workspace_id='demo-studio' GROUP BY kind"))
    assert kinds == {"model": 3, "garment": 3, "bg": 3, "3d": 2, "render": 2}
    statuses = {r[0] for r in rows(fresh, "SELECT status FROM work_items WHERE workspace_id='demo-studio' AND title!='demo-seed-complete'")}
    assert statuses == {"draft", "req", "ok", "chg", "rej", "done"}
    review_states = {r[0] for r in rows(fresh, "SELECT status FROM asset_reviews WHERE workspace_id='demo-studio'")}
    assert review_states == {"requested", "approved", "changes_requested", "rejected"}
    assert rows(fresh, "SELECT COUNT(*), SUM(visibility='public') FROM market_listings") == [(1, 1)]
    assert rows(fresh, "SELECT COUNT(*) FROM market_reports") == [(1,)]


def test_what_it_made_passes_through_the_normal_api_and_looks_right_to_each_role(fresh):
    assert seed_demo.main([]) == 0
    from app.main import app
    client = TestClient(app)
    base = "/v1/workspaces/demo-studio"
    assert client.get(f"{base}/library", headers=H("viewer")).json()["total"] == 13
    assert client.get(f"{base}/library", headers=H("viewer"), params={"kind": "3d"}).json()["total"] == 2
    assert client.get(f"{base}/library/facets", headers=H("viewer")).json()["facets"]
    items = {i["title"]: i for i in client.get(f"{base}/work-items", headers=H("viewer")).json()["items"]}
    assert items["승인된 시착"]["asset_review_summary"] == "ok" and items["반려된 시착"]["asset_review_summary"] == "rej" and items["변경 요청받은 룩북"]["asset_review_summary"] == "chg"
    assert items["검수 요청한 시착"]["asset_review_summary"] == "req" and items["작성 중인 시착"]["asset_review_summary"] is None
    assert client.post(f"{base}/work-items", headers=H("viewer"), json={"kind": "x", "title": "t"}).status_code == 403, "the viewer really is a viewer"
    assert client.get(f"{base}/settings", headers=H("admin")).status_code == 200
    found = client.get("/v1/market/listings", headers=H("viewer")).json()
    assert found["total"] == 1 and found["items"][0]["title"] == "시연용 무료 프리셋" and found["items"][0]["payload"] is None
    assert client.get(f"/v1/market/listings/{found['items'][0]['listing_id']}", headers=H("viewer")).json()["payload"] == {"br": 8, "shadow": True}
    glb_items = client.get(f"{base}/library", headers=H("owner"), params={"kind": "3d"}).json()["items"]
    assert client.get(f"{base}/library/{glb_items[0]['item_id']}/model-info", headers=H("owner")).status_code == 200, "the .glb is a valid model"
    assert client.post(f"{base}/exports", headers=H("owner")).status_code == 201, "an export of the demo workspace works"


def test_running_it_again_changes_nothing(fresh, capsys):
    assert seed_demo.main([]) == 0
    before = snapshot(fresh)
    capsys.readouterr()
    assert seed_demo.main([]) == 0
    assert "already there" in capsys.readouterr().out and snapshot(fresh) == before


@pytest.mark.parametrize("what", ["no_flag", "wrong_flag", "supabase", "backend", "provider", "app_env", "environment", "vercel", "staging"])
def test_it_refuses_anything_that_could_be_real_and_creates_nothing(fresh, monkeypatch, capsys, what):
    if what == "no_flag":
        monkeypatch.delenv("DEMO_SEED")
    elif what == "wrong_flag":
        monkeypatch.setenv("DEMO_SEED", "true")
    elif what == "supabase":
        monkeypatch.setattr(config, "SUPABASE_URL", "https://example.supabase.co")
    elif what == "backend":
        monkeypatch.setenv("DATABASE_BACKEND", "postgresql")
    elif what == "provider":
        monkeypatch.setattr(config, "PROVIDER_MODE", "fashn")
    elif what == "app_env":
        monkeypatch.setenv("APP_ENV", "production")
    elif what == "environment":
        monkeypatch.setenv("ENVIRONMENT", "Production")
    elif what == "vercel":
        monkeypatch.setenv("VERCEL_ENV", "production")
    elif what == "staging":
        monkeypatch.setenv("APP_ENV", "staging")
    assert seed_demo.main([]) == 2
    assert "refused" in capsys.readouterr().out
    assert not (fresh / "demo.sqlite3").exists(), "not even the database file was created"


def test_it_refuses_a_database_that_already_holds_a_real_workspace(fresh, capsys):
    from app.assets import store
    store.initialize()
    store.create_workspace("acme-real", "user-real")
    assert seed_demo.main([]) == 2
    out = capsys.readouterr().out
    assert "non-demo workspaces" in out and "acme-real" in out
    assert rows(fresh, "SELECT workspace_id FROM workspaces") == [("acme-real",)], "nothing was added"


def test_other_demo_workspaces_do_not_block_it(fresh):
    from app.assets import store
    store.initialize()
    store.create_workspace("demo-other", "someone")
    assert seed_demo.main([]) == 0


def test_a_half_finished_seed_is_not_repaired_or_deleted(fresh, capsys):
    from app.assets import store
    store.initialize()
    store.create_workspace("demo-studio", "demo-owner")
    before = snapshot(fresh)
    assert seed_demo.main([]) == 2
    assert "half-finished" in capsys.readouterr().out and snapshot(fresh) == before


def test_the_demo_tokens_are_fake_and_exist_only_in_the_seed_process(fresh):
    assert seed_demo.main([]) == 0
    # the test fixture restores the real token function afterwards; here the seed's own are in force
    assert set(config.asset_api_tokens()) == {t for t, _ in seed_demo.USERS.values()} and all(t.startswith("demo-token-") for t in config.asset_api_tokens())
