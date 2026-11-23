"""D-3: the couple try-on job (own3d mock): flag, requests, a synthetic couple photo (two rendered mannequins side by side), overlap refusal, match modes, roles."""
import io
import time

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import config, couple_jobs, render3d_scene, render3d_soft
from app.main import app
from tests.test_photo_steps_api import auth, env  # noqa: F401  (wa: owner a + viewer c, wb: owner b)

client = TestClient(app)
BASE = "/v1/workspaces/wa/couple-tryon"


def couple_photo(gap=60):
    left, _, _ = render3d_scene.build_layers("female", None, [])
    right, _, _ = render3d_scene.build_layers("male", None, [])
    h = max(render3d_soft.height_of(left), render3d_soft.height_of(right))
    a = render3d_soft.render(left, 0, (240, 480), background=(214, 224, 236), height_m=h)
    b = render3d_soft.render(right, 0, (240, 480), background=(214, 224, 236), height_m=h)
    img = Image.new("RGB", (480 - 2 * 20 + gap, 480), (214, 224, 236))
    img.paste(a.crop((20, 0, 220, 480)), (0, 0))
    img.paste(b.crop((20, 0, 220, 480)), (200 + gap, 0))
    return img


def upload(img, who="a", ws="wa"):
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    r = client.post("/v1/assets/images", headers=auth(who), data={"workspace_id": ws, "rights_confirmed": "true"}, files={"file": ("couple.png", buf.getvalue(), "image/png")})
    assert r.status_code == 201, r.text
    return r.json()["asset_id"]


@pytest.fixture
def opened(env, monkeypatch):
    monkeypatch.setattr(config, "RENDER3D_ENABLED", True)
    return env


def wait(job_id, who="a"):
    for _ in range(100):
        j = client.get(f"{BASE}/{job_id}", headers=auth(who)).json()
        if j["status"] in ("succeeded", "failed"):
            return j
        time.sleep(0.1)
    raise AssertionError("job did not finish")


def test_closed_by_default(env):
    assert client.post(BASE, headers=auth("a"), json={"asset_id": "ast_x", "slots": {"a": ["top"], "b": []}}).json()["detail"]["code"] == "RENDER3D_CLOSED"
    assert client.get(BASE, headers=auth("a")).status_code == 409


def test_a_couple_photo_is_split_dressed_person_by_person_and_put_back(opened):
    aid = upload(couple_photo())
    r = client.post(BASE, headers=auth("a"), json={"asset_id": aid, "slots": {"a": ["top", "skirt"], "b": ["jacket", "bottom"]}})
    assert r.status_code == 202, r.text
    job = wait(r.json()["job_id"])
    assert job["status"] == "succeeded", job
    assert job["qc"]["overlap_px"] == 0 and len(job["qc"]["people"]) == 2 and job["mock"] is True
    out = Image.open(next((opened["tmp"] / "private").glob(f"{job['asset_id']}.*"))).convert("RGB")
    src = couple_photo()
    assert out.size == src.size and list(out.getdata()) != list(src.getdata())


def test_match_same_gives_both_the_first_persons_garments_and_color_shares_one_colour(opened):
    assert couple_jobs.effective_slots({"a": ["top"], "b": ["bottom"]}, "same") == {"a": ["top"], "b": ["top"]}
    assert couple_jobs.effective_slots({"a": ["top"], "b": ["bottom"]}, None) == {"a": ["top"], "b": ["bottom"]}
    aid = upload(couple_photo())
    for match in ("same", "color"):
        r = client.post(BASE, headers=auth("a"), json={"asset_id": aid, "slots": {"a": ["top"], "b": ["top", "bottom"]}, "match": match})
        assert r.status_code == 202 and wait(r.json()["job_id"])["status"] == "succeeded"


def test_two_people_who_overlap_too_much_are_refused_with_a_clear_code(opened):
    aid = upload(couple_photo(gap=-70))
    job = wait(client.post(BASE, headers=auth("a"), json={"asset_id": aid, "slots": {"a": ["top"], "b": ["top"]}}).json()["job_id"])
    assert job["status"] == "failed" and job["error_code"] in ("COUPLE_OVERLAP_TOO_LARGE", "COUPLE_PERSON_NOT_FOUND")


def test_request_checks_roles_and_scope(opened):
    aid = upload(couple_photo())
    ok = {"asset_id": aid, "slots": {"a": ["top"], "b": []}}
    assert client.post(BASE, headers=auth("c"), json=ok).status_code == 403
    assert client.post(BASE, headers=auth("a"), json={**ok, "slots": {"a": [], "b": []}}).json()["detail"]["code"] == "COUPLE_SLOTS_EMPTY"
    assert client.post(BASE, headers=auth("a"), json={**ok, "slots": {"a": ["dress", "top"], "b": []}}).json()["detail"]["code"] == "RENDER3D_GARMENT_CONFLICT"
    assert client.post(BASE, headers=auth("a"), json={**ok, "slots": {"a": ["hat"], "b": []}}).status_code == 422
    assert client.post(BASE, headers=auth("a"), json={**ok, "asset_id": "ast_nope"}).status_code == 404
    jid = client.post(BASE, headers=auth("a"), json=ok).json()["job_id"]
    wait(jid)
    assert client.get(f"{BASE}/{jid}", headers=auth("c")).status_code == 200            # a viewer reads
    assert client.get(f"/v1/workspaces/wb/couple-tryon/{jid}", headers=auth("b")).status_code == 404
    assert len(client.get(BASE, headers=auth("a")).json()["items"]) == 1
