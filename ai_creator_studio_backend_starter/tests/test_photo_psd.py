"""R-PSD-01 API: export a layered PSD at the ORIGINAL resolution, import an edited PSD as a new original asset (merged image or layer composite), limits and roles."""
import io
import sqlite3

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import config, psd_io
from app.main import app
from tests.test_photo_steps_api import auth, env  # noqa: F401  (wa: owner a + viewer c, wb: owner b)

client = TestClient(app)
URL = "/v1/workspaces/wa/photo-psd"


def export(env, **body):
    return client.post(URL, headers=auth(body.pop("who", "a")), json={"asset_id": env["asset"], **body})


def test_export_gives_the_layers_of_the_design_at_the_original_resolution(env):
    r = export(env)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("image/vnd.adobe.photoshop") and r.headers["x-content-sha256"] and "attachment" in r.headers["content-disposition"]
    psd = psd_io.read_psd(r.content)
    src = Image.open(next((env["tmp"] / "private").glob(f"{env['asset']}.*")))
    assert (psd.width, psd.height) == src.size, "original resolution, not the work copy"
    assert [l.name for l in psd.layers] == ["원본 (참고)", "배경 (피사체 자리 비움)", "피사체 (누끼)", "최종 결과 (평면, 참고)"]
    assert [l.visible for l in psd.layers] == [False, True, True, False] and psd.icc and psd.merged is not None
    sub, bg = psd.layers[2].image, psd.layers[1].image
    assert sub.getchannel("A").getbbox() is not None and bg.getchannel("A").getextrema()[0] == 0, "the subject's place is empty in the background"


def test_without_a_cutout_there_are_two_layers_and_16_bit_is_possible(env):
    psd = psd_io.read_psd(export(env, cutout=False, depth=16).content)
    assert psd.depth == 16 and [l.name for l in psd.layers] == ["원본 (참고)", "보정 결과"]


def test_export_is_audited_scoped_and_role_checked(env):
    export(env)
    db = sqlite3.connect(config.ASSET_DATABASE_PATH)
    rows = db.execute("SELECT details_json FROM asset_provenance WHERE event_type='asset.psd_exported'").fetchall()
    assert len(rows) == 1 and "sha256" in rows[0][0]
    assert export(env, who="c").status_code == 403
    assert client.post("/v1/workspaces/wb/photo-psd", headers=auth("b"), json={"asset_id": env["asset"]}).status_code == 404
    assert client.post(URL, headers=auth("a"), json={"asset_id": "ast_nope"}).status_code == 404
    assert client.post(URL, headers=auth("a"), json={"asset_id": env["asset"], "depth": 32}).status_code == 422


def edited_psd(white_merged=False):
    base = Image.new("RGBA", (60, 40), (30, 120, 200, 255))
    top = Image.new("RGBA", (20, 10), (250, 200, 0, 255))
    merged = base.convert("RGB")
    merged.paste(top.convert("RGB"), (5, 5))
    layers = [psd_io.Layer("배경", base), psd_io.Layer("텍스트처럼 보이는 레이어", top, x=5, y=5)]
    data = psd_io.write_psd(layers, (60, 40), Image.new("RGB", (60, 40), (255, 255, 255)) if white_merged else merged)
    return data


def upload(data, name="수정본.psd", who="a", ws="wa", **form):
    return client.post(f"{URL}/import" if ws == "wa" else f"/v1/workspaces/{ws}/photo-psd/import", headers=auth(who), data={"rights_confirmed": "true", **form}, files={"file": (name, data, "application/octet-stream")})


def test_import_adds_a_new_original_with_a_version_trail_and_keeps_the_psd(env):
    data = edited_psd()
    r = upload(data)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["source"] == "merged" and body["psd"]["layers"] == 2 and body["psd"]["layer_names"][1] == "텍스트처럼 보이는 레이어"
    new_id = body["asset"]["asset_id"]
    assert new_id != env["asset"]
    stored = Image.open(next((env["tmp"] / "private").glob(f"{new_id}.*")))
    assert stored.size == (60, 40) and stored.convert("RGB").getpixel((10, 8)) == (250, 200, 0)
    db = sqlite3.connect(config.ASSET_DATABASE_PATH)
    row = db.execute("SELECT details_json, actor_id FROM asset_provenance WHERE asset_id=? AND event_type='asset.psd_import'", (new_id,)).fetchone()
    import json
    details = json.loads(row[0])
    assert row[1] == "user-a" and details["layers"] == 2 and details["label"] == "PSD 수정본" and details["psd_sha256"] == body["psd"]["sha256"] and details["rights"]["rights_confirmed"] is True
    assert list((env["tmp"] / "private" / "psd").glob("*.psd")), "the PSD itself is kept"


def test_a_psd_without_a_usable_merged_image_is_read_through_its_layers(env):
    r = upload(edited_psd(white_merged=True))
    assert r.status_code == 201 and r.json()["source"] == "layers"
    stored = Image.open(next((env["tmp"] / "private").glob(f"{r.json()['asset']['asset_id']}.*"))).convert("RGB")
    assert stored.getpixel((10, 8)) == (250, 200, 0) and stored.getpixel((50, 30)) == (30, 120, 200)


def test_big_pictures_are_reduced_for_work_and_the_flag_says_so(env, monkeypatch):
    from app import photo_psd
    monkeypatch.setattr(photo_psd, "WORK_SIDE", 30)
    r = upload(edited_psd())
    assert r.json()["reduced"] is True and max(r.json()["work_size"]) == 30


def test_bad_uploads_have_clear_codes_and_store_nothing(env):
    before = client.get("/v1/assets?workspace_id=wa&kind=image", headers=auth("a")).json()["items"]
    assert upload(b"hello", name="x.psd").json()["detail"]["code"] == "PSD_NOT_PSD"
    assert upload(edited_psd()[:200], name="cut.psd").json()["detail"]["code"] == "PSD_CORRUPT"
    assert upload(edited_psd(), name="x.png").json()["detail"]["code"] == "PSD_NOT_PSD"
    assert upload(edited_psd(), who="c").status_code == 403
    assert client.get("/v1/assets?workspace_id=wa&kind=image", headers=auth("a")).json()["items"] == before


def test_too_large_upload_is_413_and_rights_are_required_when_enforced(env, monkeypatch):
    original = psd_io.MAX_BYTES
    monkeypatch.setattr(psd_io, "MAX_BYTES", 50)
    assert upload(edited_psd()).status_code == 413
    monkeypatch.setattr(psd_io, "MAX_BYTES", original)
    monkeypatch.setattr(config, "ASSET_REQUIRE_RIGHTS_CONFIRMATION", True)
    r = client.post(f"{URL}/import", headers=auth("a"), files={"file": ("a.psd", edited_psd(), "application/octet-stream")})
    assert r.status_code == 422
