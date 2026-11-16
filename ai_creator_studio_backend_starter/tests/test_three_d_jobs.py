"""Lane 5: picture -> 3D jobs with the mock provider: valid .glb stored and filed in the library, limits, roles, fail-closed for a real provider."""
import io
import json

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import config
from app.main import app
from tests.test_photo_steps_api import auth, env  # noqa: F401  (wa: owner a + viewer c, wb: owner b)

client = TestClient(app)
J = "/v1/workspaces/wa/three-d-jobs"


def picture(shade=40, kind="garment", ws="wa", who="a"):
    buf = io.BytesIO(); Image.new("RGB", (30, 30), (shade, 90, 160)).save(buf, format="PNG")
    r = client.post(f"/v1/workspaces/{ws}/library", headers=auth(who), data={"kind": kind, "name": "p", "rights_confirmed": "true"}, files={"file": ("p.png", buf.getvalue(), "image/png")})
    assert r.status_code == 201, r.text
    return r.json()


def make(item_id, who="a", ws="wa", **extra):
    return client.post(f"/v1/workspaces/{ws}/three-d-jobs", headers=auth(who), json={"input_item_id": item_id, **extra})


def test_a_picture_becomes_a_valid_3d_item_in_the_library_with_provenance(env):
    pic = picture()
    r = make(pic["item_id"], prompt="의자")
    assert r.status_code == 201, r.text
    job = r.json()
    assert job["status"] == "succeeded" and job["provider"] == "mock3d" and job["error_code"] is None and job["input_asset_id"] == pic["asset_id"] and job["prompt"] == "의자"
    item = client.get(f"/v1/workspaces/wa/library/{job['library_item_id']}", headers=auth("a")).json()
    assert item["kind"] == "3d" and item["asset_id"] == job["output_asset_id"] and item["attrs"] == {"service": "3d", "source_asset_ids": [pic["asset_id"]]}
    assert item["media_type"] == "model/gltf-binary" and item["thumbs"] is None
    info = client.get(f"/v1/workspaces/wa/library/{item['item_id']}/model-info", headers=auth("a"))
    assert info.status_code == 200, "the stored result is a model the normal 3D checks accept"
    prov = client.get(f"/v1/assets/{job['output_asset_id']}/provenance", headers=auth("a")).json()
    rows = prov["items"] if isinstance(prov, dict) else prov
    event = next(p for p in rows if p["event_type"] == "asset.three_d_output")
    details = event["details"] if "details" in event else json.loads(event["details_json"])
    assert details["mode"] == "mock" and details["is_ai_generated"] is False and details["is_reconstruction"] is False and details["job_id"] == job["job_id"]
    assert client.get(f"{J}/{job['job_id']}", headers=auth("c")).json()["status"] == "succeeded"
    assert [j["job_id"] for j in client.get(J, headers=auth("c")).json()["items"]] == [job["job_id"]]


def test_the_same_picture_gives_the_same_file_and_other_pictures_do_not(env):
    a, b = picture(40), picture(200)
    ja, ja2, jb = (make(x["item_id"]).json() for x in (a, a, b))
    def content(job):
        return open(next((config.ASSET_STORAGE_DIR).glob(f"{job['output_asset_id']}.*")), "rb").read()
    assert content(ja) == content(ja2) != content(jb) and b"source_sha256" in content(ja)


@pytest.mark.parametrize("body,status,code", [
    ({"input_item_id": "wli_nope"}, 404, "THREED_INPUT_NOT_FOUND"), ({"input_item_id": "x"}, 422, None), ({"input_item_id": "wli_nope", "extra": 1}, 422, None),
])
def test_bad_inputs_are_refused_and_nothing_is_stored(env, body, status, code):
    r = client.post(J, headers=auth("a"), json=body)
    assert r.status_code == status and (code is None or r.json()["detail"]["code"] == code)
    assert client.get(J, headers=auth("a")).json()["items"] == []


def test_a_3d_item_cannot_be_the_input_and_roles_apply(env):
    pic = picture()
    done = make(pic["item_id"]).json()
    r = make(done["library_item_id"])
    assert r.status_code == 422 and r.json()["detail"]["code"] == "THREED_INPUT_KIND"
    assert make(pic["item_id"], who="c").status_code == 403, "a viewer cannot"
    assert make(pic["item_id"], who="b", ws="wb").status_code in (403, 404, 404), "another workspace cannot use it"
    assert client.get(f"/v1/workspaces/wb/three-d-jobs/{done['job_id']}", headers=auth("b")).status_code == 404
    assert client.post(J, json={"input_item_id": pic["item_id"]}).status_code == 401


def test_the_daily_limit_and_the_generate_budget(env, monkeypatch):
    pic = picture()
    monkeypatch.setattr(config, "THREED_DAILY_LIMIT", 2)
    assert make(pic["item_id"]).status_code == 201 and make(pic["item_id"]).status_code == 201
    r = make(pic["item_id"])
    assert r.status_code == 429 and r.json()["detail"]["code"] == "THREED_DAILY_LIMIT" and r.json()["detail"]["retry_after_seconds"] >= 1
    monkeypatch.setattr(config, "THREED_DAILY_LIMIT", 20)
    monkeypatch.setattr(config, "RATE_LIMITS_ENABLED", True)
    monkeypatch.setattr(config, "RATE_GENERATE_USER_PER_MINUTE", 1)
    assert make(pic["item_id"]).status_code == 429, "3D jobs share the generate budget"


def test_a_real_provider_mode_fails_closed_before_any_picture_is_touched(env, monkeypatch):
    pic = picture()
    monkeypatch.setattr(config, "PROVIDER_MODE", "fashn")
    r = make(pic["item_id"])
    assert r.status_code == 409 and r.json()["detail"]["code"] == "THREED_PROVIDER_NOT_CONNECTED"
    assert client.get(J, headers=auth("a")).json()["items"] == []
