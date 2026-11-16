"""R-044 A-2: POST /v1/workspaces/{id}/photo-steps: new asset from a local step run; source untouched; roles; validation; no AI label."""
import sqlite3
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app

client = TestClient(app)


def auth(t):
    return {"Authorization": f"Bearer token-{t}"}


def product_png():
    img = Image.new("RGB", (200, 100), (250, 250, 250))
    img.paste(Image.new("RGB", (80, 60), (20, 60, 160)), (60, 20))
    buf = BytesIO(); img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def env(tmp_path, monkeypatch):
    import app.config as config
    monkeypatch.setattr(config, "ASSET_STORAGE_DIR", tmp_path / "private")
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path / "outputs")
    monkeypatch.setattr(config, "ASSET_DATABASE_PATH", tmp_path / "a.sqlite3")
    monkeypatch.setattr(config, "GENERATION_DATABASE_PATH", None)
    monkeypatch.setattr(config, "ASSET_SIGNING_SECRET", "s" * 48)
    monkeypatch.setattr(config, "asset_api_tokens", lambda: {"token-a": "user-a", "token-b": "user-b", "token-c": "user-c"})
    monkeypatch.setattr(config, "PROVIDER_MODE", "mock")
    for ws, u in (("wa", "a"), ("wb", "b")):
        assert client.post("/v1/workspaces", headers=auth(u), json={"workspace_id": ws}).status_code == 201
    assert client.post("/v1/workspaces/wa/members", headers=auth("a"), json={"user_id": "user-c", "role": "viewer"}).status_code == 201
    (tmp_path / "outputs").mkdir(exist_ok=True)
    up = client.post("/v1/assets/images", headers=auth("a"), data={"workspace_id": "wa", "rights_confirmed": "true"},
                     files={"file": ("shoe.png", product_png(), "image/png")})
    assert up.status_code == 201, up.text
    return {"tmp": tmp_path, "asset": up.json()["asset_id"]}


STEPS = [{"op": "auto_crop", "margin_pct": 0}, {"op": "fit_canvas", "width": 120, "height": 120}]


def run(env, steps=STEPS, who="a", ws="wa", asset=None):
    return client.post(f"/v1/workspaces/{ws}/photo-steps", headers=auth(who), json={"asset_id": asset or env["asset"], "steps": steps})


def test_run_stores_a_new_asset_with_the_result_and_leaves_the_source_alone(env):
    before = open(next((env["tmp"] / "private").glob(f"{env['asset']}.*")), "rb").read()
    r = run(env)
    assert r.status_code == 201, r.text
    body = r.json()
    new_id = body["asset"]["asset_id"]
    assert new_id != env["asset"] and body["asset"]["original_filename"] == "shoe-edited.png"
    assert [(s["op"], s["size_in"], s["size_out"]) for s in body["steps"]] == [("auto_crop", [200, 100], [80, 60]), ("fit_canvas", [80, 60], [120, 120])]
    stored = Image.open(next((env["tmp"] / "private").glob(f"{new_id}.*")))
    assert stored.size == (120, 120)
    assert open(next((env["tmp"] / "private").glob(f"{env['asset']}.*")), "rb").read() == before, "source bytes unchanged"
    listed = client.get("/v1/assets?workspace_id=wa&kind=image", headers=auth("a")).json()["items"]
    assert {a["asset_id"] for a in listed} == {env["asset"], new_id}


def test_provenance_says_local_not_ai_and_names_the_source_and_steps(env):
    new_id = run(env).json()["asset"]["asset_id"]
    db = sqlite3.connect(env["tmp"] / "a.sqlite3")
    rows = db.execute("SELECT event_type, details_json FROM asset_provenance WHERE asset_id=? AND event_type='asset.photo_steps'", (new_id,)).fetchall()
    assert len(rows) == 1
    import json
    d = json.loads(rows[0][1])
    assert d["source_asset_id"] == env["asset"] and d["mode"] == "local" and d["is_ai_generated"] is False
    assert [s["op"] for s in d["steps"]] == ["auto_crop", "fit_canvas"]


def test_roles_and_scopes(env):
    assert client.post("/v1/workspaces/wa/photo-steps", json={"asset_id": env["asset"], "steps": STEPS}).status_code == 401
    assert run(env, who="c").status_code == 403, "a viewer cannot create assets"
    assert run(env, who="b", ws="wb").status_code == 404, "another workspace's asset id is not found"
    assert run(env, who="b").status_code in (403, 404), "not a member"
    assert run(env, asset="ast_missing").status_code == 404


@pytest.mark.parametrize("steps, code", [
    ([{"op": "sharpen"}], "STEP_UNKNOWN"), ([{"op": "auto_crop", "tolerance": 999}], "STEP_PARAMETER_INVALID"),
    ([{"op": "solid_background", "color": "red"}], "STEP_COLOR_INVALID"),
])
def test_bad_steps_are_422_and_store_nothing(env, steps, code):
    r = run(env, steps=steps)
    assert r.status_code == 422 and r.json()["detail"]["code"] == code
    assert len(client.get("/v1/assets?workspace_id=wa&kind=image", headers=auth("a")).json()["items"]) == 1


def test_empty_or_extra_fields_are_refused(env):
    assert run(env, steps=[]).status_code == 422
    assert client.post("/v1/workspaces/wa/photo-steps", headers=auth("a"), json={"asset_id": env["asset"], "steps": STEPS, "x": 1}).status_code == 422
