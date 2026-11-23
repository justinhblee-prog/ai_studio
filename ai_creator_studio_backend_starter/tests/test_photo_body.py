"""D-2: photo -> body measurements on SYNTHETIC photos (rendered own3d mannequins: a closed loop) + refusals. Real photos are not tested."""
import io

import pytest
from PIL import Image, ImageDraw

from app import base_models, photo_body, render3d_scene, render3d_soft

CASES = [("female", {"height_cm": 166, "chest_cm": 88, "waist_cm": 70, "hips_cm": 96}), ("female", {"height_cm": 158, "chest_cm": 80, "waist_cm": 64, "hips_cm": 90}),
         ("female", {"height_cm": 175, "chest_cm": 100, "waist_cm": 84, "hips_cm": 108}), ("male", {"height_cm": 178, "chest_cm": 98, "waist_cm": 84, "hips_cm": 100}),
         ("male", {"height_cm": 185, "chest_cm": 108, "waist_cm": 96, "hips_cm": 106})]


def photo(sex, measurements, size=(360, 640)):
    body, _, _ = render3d_scene.build_layers(sex, measurements, [])
    h = render3d_soft.height_of(body)
    return render3d_soft.render(body, 0, size, background=(214, 224, 236), height_m=h)


@pytest.mark.parametrize("sex, m", CASES)
def test_the_mannequin_photo_gives_back_its_measurements_within_a_few_centimetres(sex, m):
    r = photo_body.estimate(photo(sex, m), sex=sex, height_cm=m["height_cm"])
    assert r["estimated"] is True and "ESTIMATED" in r["label"]
    for k in ("chest_cm", "waist_cm", "hips_cm"):
        tol = 9.0 if k == "chest_cm" else 3.5           # the chest comes from a PRIOR when the arms hang against it: pinned, see docs
        assert abs(r["measurements"][k] - m[k]) <= tol, (k, r["measurements"], m)


def test_the_estimate_is_ordered_like_the_person_and_fits_the_mannequin_limits():
    thin = photo_body.estimate(photo(*CASES[1]), sex="female", height_cm=158)["measurements"]
    wide = photo_body.estimate(photo(*CASES[2]), sex="female", height_cm=175)["measurements"]
    assert wide["chest_cm"] > thin["chest_cm"] and wide["hips_cm"] > thin["hips_cm"]
    base_models.build_base_model("female", measurements=wide)        # the measurements are accepted by the body builder


def test_a_missing_height_uses_the_default_and_says_so():
    r = photo_body.estimate(photo(*CASES[0]), sex="female")
    assert r["measurements"]["height_cm"] == 166.0 and any("height_cm was not given" in w for w in r["warnings"])


def test_refusals_have_catalogued_codes():
    blank = Image.new("RGB", (200, 300), (230, 230, 230))
    edge = blank.copy()
    ImageDraw.Draw(edge).rectangle([0, 20, 100, 299], fill=(20, 20, 20))
    wide = blank.copy()
    ImageDraw.Draw(wide).rectangle([20, 100, 180, 200], fill=(20, 20, 20))
    for img, code in ((blank, "PHOTO_BODY_NOT_FOUND"), (edge, "PHOTO_BODY_CLIPPED"), (wide, "PHOTO_BODY_POSE")):
        with pytest.raises(photo_body.PhotoBodyError) as e:
            photo_body.estimate(img)
        assert e.value.code == code
    with pytest.raises(photo_body.PhotoBodyError) as e:
        photo_body.estimate(b"not a picture")
    assert e.value.code == "PHOTO_BODY_UNREADABLE"
    for kw, code in (({"sex": "x"}, "PHOTO_BODY_SEX"), ({"height_cm": 20}, "PHOTO_BODY_HEIGHT")):
        with pytest.raises(photo_body.PhotoBodyError) as e:
            photo_body.estimate(photo(*CASES[0]), **kw)
        assert e.value.code == code


def test_arms_hanging_against_the_chest_are_flagged_and_the_chest_comes_from_the_waist():
    img = Image.new("RGB", (300, 640), (230, 230, 230))
    d = ImageDraw.Draw(img)
    d.ellipse([125, 20, 175, 80], fill=(30, 30, 30))                                   # head
    d.polygon([(95, 90), (205, 90), (205, 215), (170, 270), (170, 330), (130, 330), (130, 270), (95, 215)], fill=(30, 30, 30))      # shoulders + arms fused with the chest, a narrow waist
    d.rectangle([115, 330, 185, 620], fill=(30, 30, 30))
    r = photo_body.estimate(img, sex="female", height_cm=166)
    assert r["chest_from_prior"] is True and any("arms hang against the chest" in w for w in r["warnings"])
    assert r["measurements"]["chest_cm"] < 100, "not the inflated silhouette width"


# ---- API
from fastapi.testclient import TestClient  # noqa: E402

from app import config  # noqa: E402
from app.main import app  # noqa: E402
from tests.test_photo_steps_api import auth, env  # noqa: E402,F401

client = TestClient(app)
URL = "/v1/workspaces/wa/photo-body"


def upload_png(img, name="p.png", who="a"):
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    r = client.post("/v1/assets/images", headers=auth(who), data={"workspace_id": "wa", "rights_confirmed": "true"}, files={"file": (name, buf.getvalue(), "image/png")})
    assert r.status_code == 201, r.text
    return r.json()["asset_id"]


def test_api_is_closed_by_default_then_estimates_a_stored_photo(env, monkeypatch):
    aid = upload_png(photo(*CASES[0]))
    assert client.post(URL, headers=auth("a"), json={"asset_id": aid, "sex": "female"}).json()["detail"]["code"] == "RENDER3D_CLOSED"
    monkeypatch.setattr(config, "RENDER3D_ENABLED", True)
    r = client.post(URL, headers=auth("a"), json={"asset_id": aid, "sex": "female", "height_cm": 166})
    assert r.status_code == 200, r.text
    m = r.json()["measurements"]
    assert abs(m["waist_cm"] - 70) <= 3.5 and r.json()["estimated"] is True


def test_api_roles_scope_and_refusals(env, monkeypatch):
    monkeypatch.setattr(config, "RENDER3D_ENABLED", True)
    aid = upload_png(photo(*CASES[0]))
    assert client.post(URL, headers=auth("c"), json={"asset_id": aid, "sex": "female"}).status_code == 403
    assert client.post(URL, headers=auth("a"), json={"asset_id": "ast_nope", "sex": "female"}).status_code == 404
    assert client.post("/v1/workspaces/wb/photo-body", headers=auth("b"), json={"asset_id": aid, "sex": "female"}).status_code == 404
    blank = upload_png(Image.new("RGB", (200, 300), (230, 230, 230)), "blank.png")
    r = client.post(URL, headers=auth("a"), json={"asset_id": blank, "sex": "male"})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "PHOTO_BODY_NOT_FOUND"
    assert client.post(URL, headers=auth("a"), json={"asset_id": aid, "sex": "x"}).status_code == 422
