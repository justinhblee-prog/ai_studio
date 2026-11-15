"""Pilot service switches: all off by default, explicit opt-in only, signed-in users only."""
import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import app

client = TestClient(app)
NAMES = ["tryon", "character", "three_d", "video", "market"]


@pytest.fixture(autouse=True)
def env(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "ASSET_DATABASE_PATH", tmp_path / "a.sqlite3")
    monkeypatch.setattr(config, "ASSET_STORAGE_DIR", tmp_path / "p")
    monkeypatch.setattr(config, "asset_api_tokens", lambda: {"t": "user-a"})
    for n in NAMES:
        monkeypatch.delenv("FEATURE_" + n.upper(), raising=False)


def get():
    return client.get("/v1/features", headers={"Authorization": "Bearer t"})


def test_all_services_are_off_by_default_and_labelled_as_pilot_preview():
    body = get().json()["features"]
    assert list(body) == NAMES
    assert all(v == {"enabled": False, "status": "pilot_preview"} for v in body.values())


def test_only_an_explicit_opt_in_turns_a_service_on(monkeypatch):
    monkeypatch.setenv("FEATURE_TRYON", "1")
    monkeypatch.setenv("FEATURE_VIDEO", "yes")
    monkeypatch.setenv("FEATURE_MARKET", "maybe")   # unknown text is OFF
    monkeypatch.setenv("FEATURE_THREE_D", "")       # empty is OFF
    body = get().json()["features"]
    assert body["tryon"] == {"enabled": True, "status": "available"} and body["video"]["enabled"] is True
    assert not body["market"]["enabled"] and not body["three_d"]["enabled"] and not body["character"]["enabled"]


def test_anonymous_callers_are_refused():
    assert client.get("/v1/features").status_code == 401
