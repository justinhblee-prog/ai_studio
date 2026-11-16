"""R-044 A-4 (brand presets): validated, per-workspace, role-checked, unique names, capped, removed with the workspace data."""
import pytest
from fastapi.testclient import TestClient

from app import photo_presets
from app.main import app
from tests.test_photo_steps_api import auth, env  # noqa: F401  (same workspaces: wa owner a, viewer c; wb owner b)

client = TestClient(app)
STEPS = [{"op": "auto_crop", "margin_pct": 3}, {"op": "fit_canvas", "width": 800, "height": 800, "color": "#f0f0f0"}]


def post(name="브랜드 기본", steps=STEPS, who="a", ws="wa"):
    return client.post(f"/v1/workspaces/{ws}/photo-presets", headers=auth(who), json={"name": name, "steps": steps})


def test_create_list_delete_roundtrip_with_defaults_filled(env):
    r = post(steps=[{"op": "auto_crop"}])
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["name"] == "브랜드 기본" and body["owner_id"] == "user-a"
    assert body["steps"] == [{"op": "auto_crop", "tolerance": 24, "margin_pct": 5}], "normalised steps are stored"
    assert [p["preset_id"] for p in client.get("/v1/workspaces/wa/photo-presets", headers=auth("a")).json()["items"]] == [body["preset_id"]]
    assert client.get("/v1/workspaces/wa/photo-presets", headers=auth("c")).status_code == 200, "a viewer may read"
    assert client.delete(f"/v1/workspaces/wa/photo-presets/{body['preset_id']}", headers=auth("a")).status_code == 204
    assert client.get("/v1/workspaces/wa/photo-presets", headers=auth("a")).json()["items"] == []
    assert client.delete(f"/v1/workspaces/wa/photo-presets/{body['preset_id']}", headers=auth("a")).status_code == 404


def test_roles_and_isolation_between_workspaces(env):
    pid = post().json()["preset_id"]
    assert client.get("/v1/workspaces/wa/photo-presets").status_code == 401
    assert post(who="c").status_code == 403, "a viewer cannot save"
    assert client.delete(f"/v1/workspaces/wa/photo-presets/{pid}", headers=auth("c")).status_code == 403
    assert client.get("/v1/workspaces/wa/photo-presets", headers=auth("b")).status_code in (403, 404), "not a member"
    assert post(who="b", ws="wb").status_code == 201, "the same name in another workspace is fine"
    assert client.get("/v1/workspaces/wb/photo-presets", headers=auth("b")).json()["items"][0]["name"] == "브랜드 기본"
    assert client.delete(f"/v1/workspaces/wb/photo-presets/{pid}", headers=auth("b")).status_code == 404, "another workspace's id"
    assert len(client.get("/v1/workspaces/wa/photo-presets", headers=auth("a")).json()["items"]) == 1


@pytest.mark.parametrize("payload, status, code", [
    ({"name": "x", "steps": [{"op": "sharpen"}]}, 422, "STEP_UNKNOWN"),
    ({"name": "x", "steps": [{"op": "auto_crop", "tolerance": 999}]}, 422, "STEP_PARAMETER_INVALID"),
    ({"name": "   ", "steps": [{"op": "auto_crop"}]}, 422, "PRESET_NAME_REQUIRED"),
])
def test_bad_presets_are_refused_and_nothing_is_saved(env, payload, status, code):
    r = client.post("/v1/workspaces/wa/photo-presets", headers=auth("a"), json=payload)
    assert r.status_code == status and r.json()["detail"]["code"] == code
    assert client.get("/v1/workspaces/wa/photo-presets", headers=auth("a")).json()["items"] == []


def test_schema_level_refusals(env):
    for bad in ({"name": "", "steps": STEPS}, {"name": "x" * 61, "steps": STEPS}, {"name": "x", "steps": []}, {"name": "x", "steps": STEPS, "extra": 1}):
        assert client.post("/v1/workspaces/wa/photo-presets", headers=auth("a"), json=bad).status_code == 422, bad


def test_names_are_unique_per_workspace_and_the_count_is_capped(env, monkeypatch):
    assert post(name="A").status_code == 201
    dup = post(name=" A ")
    assert dup.status_code == 409 and dup.json()["detail"]["code"] == "PRESET_NAME_TAKEN"
    monkeypatch.setattr(photo_presets, "MAX_PRESETS", 2)
    assert post(name="B").status_code == 201
    full = post(name="C")
    assert full.status_code == 409 and full.json()["detail"]["code"] == "PRESET_LIMIT"
