"""E-09e: one recipe (steps or a saved preset) over many images: per-image results, partial failure, the rate limit, roles, and the sources left alone."""
import io
import sqlite3

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import config
from app.main import app
from tests.test_photo_steps_api import auth, env, product_png  # noqa: F401

client = TestClient(app)
STEPS = [{"op": "auto_crop", "margin_pct": 0}, {"op": "fit_canvas", "width": 120, "height": 120}]


def upload(name="shoe.png", who="a", ws="wa"):
    r = client.post("/v1/assets/images", headers=auth(who), data={"workspace_id": ws, "rights_confirmed": "true"}, files={"file": (name, product_png(), "image/png")})
    assert r.status_code == 201, r.text
    return r.json()["asset_id"]


def batch(body, who="a", ws="wa"):
    return client.post(f"/v1/workspaces/{ws}/photo-steps/batch", headers=auth(who), json=body)


def stored(env, asset_id):
    return Image.open(next((env["tmp"] / "private").glob(f"{asset_id}.*")))


def test_one_recipe_runs_over_every_image_and_each_result_is_a_new_asset(env):
    ids = [env["asset"], upload("a.png"), upload("b.png")]
    before = {i: open(next((env["tmp"] / "private").glob(f"{i}.*")), "rb").read() for i in ids}
    r = batch({"asset_ids": ids, "steps": STEPS})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["batch_id"].startswith("pbt_") and (body["total"], body["succeeded"], body["failed"], body["not_run"]) == (3, 3, 0, 0) and body["preset_id"] is None
    assert [i["asset_id"] for i in body["items"]] == ids and all(i["status"] == "ok" for i in body["items"])
    new_ids = {i["asset"]["asset_id"] for i in body["items"]}
    assert len(new_ids) == 3 and not new_ids & set(ids)
    assert all(stored(env, n).size == (120, 120) for n in new_ids)
    assert {i: open(next((env["tmp"] / "private").glob(f"{i}.*")), "rb").read() for i in ids} == before, "sources unchanged"
    db = sqlite3.connect(env["tmp"] / "a.sqlite3")
    import json
    rows = db.execute("SELECT details_json FROM asset_provenance WHERE event_type='asset.photo_steps'").fetchall()
    assert len(rows) == 3 and all(json.loads(r[0])["batch_id"] == body["batch_id"] and json.loads(r[0])["is_ai_generated"] is False for r in rows)


def test_a_saved_preset_is_the_recipe_and_its_id_is_recorded(env):
    preset = client.post("/v1/workspaces/wa/photo-presets", headers=auth("a"), json={"name": "shop", "steps": STEPS}).json()
    r = batch({"asset_ids": [env["asset"], upload("x.png")], "preset_id": preset["preset_id"]})
    assert r.status_code == 201 and r.json()["preset_id"] == preset["preset_id"] and r.json()["succeeded"] == 2
    assert batch({"asset_ids": [env["asset"]], "preset_id": "pst_missing"}).status_code == 404
    assert batch({"asset_ids": [env["asset"]], "preset_id": preset["preset_id"]}, who="b", ws="wb").status_code in (403, 404), "another workspace's preset is not usable"


def test_one_bad_image_does_not_stop_the_others(env):
    r = batch({"asset_ids": [env["asset"], "ast_missing", upload("ok.png")], "steps": STEPS})
    body = r.json()
    assert r.status_code == 201 and (body["succeeded"], body["failed"]) == (2, 1)
    assert [i["status"] for i in body["items"]] == ["ok", "failed", "ok"] and body["items"][1]["error_code"] == "ASSET_NOT_FOUND" and body["items"][1]["asset"] is None


def test_a_result_that_would_be_too_large_fails_only_that_image(env):
    big = client.post("/v1/assets/images", headers=auth("a"), data={"workspace_id": "wa", "rights_confirmed": "true"}, files={"file": ("big.png", _png((4500, 100)), "image/png")}).json()["asset_id"]
    body = batch({"asset_ids": [env["asset"], big], "steps": [{"op": "upscale", "factor_pct": 400, "sharpen_pct": 0}]}).json()
    assert [i["status"] for i in body["items"]] == ["ok", "failed"] and body["items"][1]["error_code"] == "STEP_RESULT_TOO_LARGE"


def _png(size):
    buf = io.BytesIO()
    Image.new("RGB", size, (200, 30, 30)).save(buf, format="PNG")
    return buf.getvalue()


@pytest.mark.parametrize("body, code", [
    ({"asset_ids": ["ast_x"]}, "BATCH_RECIPE_REQUIRED"),
    ({"asset_ids": ["ast_x"], "steps": STEPS, "preset_id": "pst_1"}, "BATCH_RECIPE_REQUIRED"),
    ({"asset_ids": ["ast_x", "ast_x"], "steps": STEPS}, "BATCH_DUPLICATE_ASSET"),
    ({"asset_ids": ["ast_x"], "steps": [{"op": "sharpen"}]}, "STEP_UNKNOWN"),
    ({"asset_ids": ["ast_x"], "steps": [{"op": "auto_crop", "tolerance": 999}]}, "STEP_PARAMETER_INVALID")])
def test_a_bad_recipe_is_refused_as_a_whole_before_anything_runs(env, body, code):
    r = batch(body)
    assert r.status_code == 422 and r.json()["detail"]["code"] == code
    assert len(client.get("/v1/assets?workspace_id=wa&kind=image", headers=auth("a")).json()["items"]) == 1, "nothing was stored"


@pytest.mark.parametrize("body", [{"asset_ids": [], "steps": STEPS}, {"asset_ids": [f"ast_{i}" for i in range(21)], "steps": STEPS}, {"asset_ids": ["ast_x"], "steps": STEPS, "extra": 1}])
def test_malformed_bodies_are_422(env, body):
    assert batch(body).status_code == 422


def test_roles_and_sign_in(env):
    assert client.post("/v1/workspaces/wa/photo-steps/batch", json={"asset_ids": [env["asset"]], "steps": STEPS}).status_code == 401
    assert batch({"asset_ids": [env["asset"]], "steps": STEPS}, who="c").status_code == 403, "a viewer cannot create assets"
    assert batch({"asset_ids": [env["asset"]], "steps": STEPS}, who="b", ws="wb").json()["items"][0]["status"] == "failed", "another workspace's asset id is simply not found"


def test_the_generation_rate_limit_counts_every_image_and_the_rest_is_reported_not_run(env, monkeypatch):
    monkeypatch.setattr(config, "RATE_LIMITS_ENABLED", True)
    monkeypatch.setattr(config, "RATE_GENERATE_USER_PER_MINUTE", 2)
    from app import rate_limit
    limits = rate_limit.current_limits("generate")
    assert any(k == "user" for k, _, _ in limits), limits
    body = batch({"asset_ids": [env["asset"], upload("a.png"), upload("b.png"), upload("c.png")], "steps": STEPS}).json()
    statuses = [i["status"] for i in body["items"]]
    assert statuses.count("ok") == 2 and statuses[2:] == ["not_run", "not_run"] and body["not_run"] == 2 and body["items"][2]["error_code"] == "RATE_LIMITED"
