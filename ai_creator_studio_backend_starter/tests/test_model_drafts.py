"""R-047 (mock): design values -> 6 ranked candidates -> choose -> brand model (Character) + library item; references; limits; roles."""
import pytest
from fastapi.testclient import TestClient

from app import config, model_drafts
from app.main import app
from tests.test_photo_steps_api import auth, env  # noqa: F401  (wa: owner a + viewer c, wb: owner b; env["asset"] = an image in wa)
from tests.test_workspace_library import png

client = TestClient(app)
V = {"skin_tone": "3", "hair": "wavy", "body_type": "regular", "age_range": "30s", "expression": ["calm", "smile"], "light": "soft"}


def draft(v=None, prompt="봄 화보", who="a", ws="wa"):
    return client.post(f"/v1/workspaces/{ws}/model-drafts", headers=auth(who), json={"v": V if v is None else v, "prompt": prompt})


def refs(n, who="a"):
    out = []
    for i in range(n):
        r = client.post("/v1/assets/images", headers=auth(who), data={"workspace_id": "wa", "rights_confirmed": "true"},
                        files={"file": (f"ref{i}.png", png((i * 7 % 250, 40, 90)), "image/png")})
        assert r.status_code == 201, r.text
        out.append(r.json()["asset_id"])
    return out


def test_six_ranked_candidates_are_made_and_the_same_input_gives_the_same_result(env):
    d = draft().json()
    assert len(d["candidates"]) == 6 and [c["rank"] for c in d["candidates"]] == [1, 2, 3, 4, 5, 6]
    scores = [c["score"] for c in d["candidates"]]
    assert scores == sorted(scores, reverse=True) and all(60 <= s <= 99 for s in scores), "best fit first"
    assert len({c["asset_id"] for c in d["candidates"]}) == 6 and d["status"] == "ready" and d["provider"] == "mock"
    again = draft().json()
    assert [c["score"] for c in again["candidates"]] == scores, "deterministic"
    a = model_drafts.mock_candidate(V, "봄 화보", 1)[0]
    assert a == model_drafts.mock_candidate(V, "봄 화보", 1)[0] and a != model_drafts.mock_candidate(V, "봄 화보", 2)[0]
    assert a != model_drafts.mock_candidate({**V, "hair": "straight"}, "봄 화보", 1)[0]


def test_candidates_are_marked_as_mock_not_ai_and_are_readable_images(env):
    d = draft().json()
    asset = d["candidates"][0]["asset_id"]
    prov = client.get(f"/v1/assets/{asset}/provenance", headers=auth("a")).json()
    event = next(p for p in (prov["items"] if isinstance(prov, dict) else prov) if p["event_type"] == "asset.model_candidate")
    details = event["details"] if "details" in event else __import__("json").loads(event["details_json"])
    assert details["mode"] == "mock" and details["is_ai_generated"] is False
    versions = client.get(f"/v1/assets/{asset}/versions", headers=auth("a")).json()["items"]
    assert client.post(f"/v1/assets/{asset}/versions/{versions[0]['version_id']}/preview-url", headers=auth("a")).status_code == 200


@pytest.mark.parametrize("v, code", [
    ({}, "DESIGN_REQUIRED"), ([], "DESIGN_REQUIRED"), ({"Bad-Key": "x"}, "DESIGN_KEY_INVALID"), ({"hair": {"nested": "x"}}, "DESIGN_VALUE_INVALID"),
    ({"hair": ""}, "DESIGN_VALUE_INVALID"), ({"hair": "x" * 61}, "DESIGN_VALUE_INVALID"), ({"hair": []}, "DESIGN_VALUE_INVALID"),
    ({"hair": ["a"] * 11}, "DESIGN_VALUE_INVALID"), ({f"k{i}": "x" for i in range(41)}, "DESIGN_TOO_MANY"), ({"hair": 5}, "DESIGN_VALUE_INVALID"),
])
def test_bad_designs_are_refused_before_anything_is_made(env, v, code):
    r = client.post("/v1/workspaces/wa/model-drafts", headers=auth("a"), json={"v": v})
    assert r.status_code in (422,) and (r.json()["detail"]["code"] if isinstance(r.json()["detail"], dict) else "") in (code, "")
    assert client.get("/v1/workspaces/wa/model-drafts", headers=auth("a")).json()["items"] == []
    assert len(client.get("/v1/assets?workspace_id=wa&kind=image", headers=auth("a")).json()["items"]) == 1, "no candidate pictures were saved"


def test_roles_and_isolation(env):
    d = draft().json()
    assert draft(who="c").status_code == 403, "a viewer cannot create"
    assert client.get("/v1/workspaces/wa/model-drafts", headers=auth("c")).status_code == 200
    assert client.get(f"/v1/workspaces/wa/model-drafts/{d['draft_id']}", headers=auth("c")).status_code == 200
    assert client.post("/v1/workspaces/wa/model-drafts").status_code in (401, 422)
    assert client.get("/v1/workspaces/wa/model-drafts").status_code == 401
    assert client.get(f"/v1/workspaces/wb/model-drafts/{d['draft_id']}", headers=auth("b")).status_code == 404
    sel = {"rank": 1, "name": "x"}
    assert client.post(f"/v1/workspaces/wa/model-drafts/{d['draft_id']}/select", headers=auth("c"), json=sel).status_code == 403
    assert client.post(f"/v1/workspaces/wb/model-drafts/{d['draft_id']}/select", headers=auth("b"), json=sel).status_code == 404
    assert client.delete(f"/v1/workspaces/wa/model-drafts/{d['draft_id']}", headers=auth("c")).status_code == 403


def test_choosing_creates_the_brand_model_with_identity_references_and_a_library_item(env):
    d = draft().json()
    pick = d["candidates"][2]
    reference_ids = refs(3)
    r = client.post(f"/v1/workspaces/wa/model-drafts/{d['draft_id']}/select", headers=auth("a"), json={"rank": 3, "name": " 브랜드 모델 A ", "reference_asset_ids": reference_ids})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["draft"]["status"] == "selected" and body["draft"]["selected_rank"] == 3 and body["draft"]["character_id"] == body["character_id"]
    assert body["references"] == 3 and body["consistency_ready"] is False and body["recommended_min_references"] == 15 and body["max_references"] == 30
    ch = client.get(f"/v1/workspaces/wa/characters/{body['character_id']}", headers=auth("a")).json()
    ident = ch["identity"]
    assert ident["name"] == "브랜드 모델 A" and ident["skin_tone"] == "3" and ident["hairstyle"] == "wavy" and ident["body_type"] == "regular" and ident["age_range"] == "30s"
    assert ident["design"] == {**V}, "nothing the designer chose is lost"
    assert ch["asset_ids"][0] == pick["asset_id"] and set(ch["asset_ids"][1:]) == set(reference_ids)
    item = client.get(f"/v1/workspaces/wa/library/{body['library_item_id']}", headers=auth("a")).json()
    assert item["kind"] == "model" and item["asset_id"] == pick["asset_id"] and item["origin"] == "work" and item["name"] == "브랜드 모델 A"
    # the other five candidates are gone, the chosen one stays
    for c in d["candidates"]:
        status = client.get(f"/v1/assets/{c['asset_id']}", headers=auth("a")).status_code
        assert status == (200 if c["asset_id"] == pick["asset_id"] else 404), c


def test_choosing_twice_and_bad_choices_are_refused(env):
    d = draft().json()
    base = f"/v1/workspaces/wa/model-drafts/{d['draft_id']}/select"
    assert client.post(base, headers=auth("a"), json={"rank": 7, "name": "x"}).status_code == 422
    assert client.post(base, headers=auth("a"), json={"rank": 0, "name": "x"}).status_code == 422
    assert client.post(base, headers=auth("a"), json={"rank": 1, "name": " "}).status_code == 422
    assert client.post(base, headers=auth("a"), json={"rank": 1, "name": "x", "reference_asset_ids": ["ast_missing"]}).status_code == 422
    assert client.post(base, headers=auth("a"), json={"rank": 1, "name": "x", "reference_asset_ids": [env["asset"], env["asset"]]}).status_code == 422
    assert client.post(base, headers=auth("a"), json={"rank": 1, "name": "x", "reference_asset_ids": [d["candidates"][0]["asset_id"]]}).status_code == 422, "the pick is not its own reference"
    assert client.post(base, headers=auth("a"), json={"rank": 1, "name": "x", "reference_asset_ids": ["a"] * 31}).status_code == 422, "at most 30"
    assert client.get("/v1/workspaces/wa/characters", headers=auth("a")).json()["items"] == [], "refusals created nothing"
    ok = client.post(base, headers=auth("a"), json={"rank": 1, "name": "첫째"})
    assert ok.status_code == 200
    again = client.post(base, headers=auth("a"), json={"rank": 2, "name": "둘째"})
    assert again.status_code == 409 and again.json()["detail"]["code"] == "MODEL_DRAFT_ALREADY_CHOSEN"
    assert len(client.get("/v1/workspaces/wa/characters", headers=auth("a")).json()["items"]) == 1


def test_fifteen_or_more_references_mark_consistency_ready(env):
    d = draft().json()
    r = client.post(f"/v1/workspaces/wa/model-drafts/{d['draft_id']}/select", headers=auth("a"), json={"rank": 1, "name": "일관성", "reference_asset_ids": refs(15)})
    assert r.status_code == 200 and r.json()["consistency_ready"] is True and r.json()["references"] == 15


def test_deleting_an_unchosen_draft_removes_every_candidate_and_a_chosen_one_keeps_its_picture(env):
    d = draft().json()
    assert client.delete(f"/v1/workspaces/wa/model-drafts/{d['draft_id']}", headers=auth("a")).status_code == 204
    assert client.get(f"/v1/workspaces/wa/model-drafts/{d['draft_id']}", headers=auth("a")).status_code == 404
    assert all(client.get(f"/v1/assets/{c['asset_id']}", headers=auth("a")).status_code == 404 for c in d["candidates"])
    e = draft(prompt="다른").json()
    client.post(f"/v1/workspaces/wa/model-drafts/{e['draft_id']}/select", headers=auth("a"), json={"rank": 2, "name": "남김"})
    assert client.delete(f"/v1/workspaces/wa/model-drafts/{e['draft_id']}", headers=auth("a")).status_code == 204
    assert client.get(f"/v1/assets/{e['candidates'][1]['asset_id']}", headers=auth("a")).status_code == 200, "it belongs to the brand model now"
    assert client.delete(f"/v1/workspaces/wa/model-drafts/{e['draft_id']}", headers=auth("a")).status_code == 404


def test_open_drafts_are_capped_and_a_real_provider_is_not_connected(env, monkeypatch):
    monkeypatch.setattr(model_drafts, "MAX_OPEN_DRAFTS", 2)
    assert draft(prompt="1").status_code == 201 and draft(prompt="2").status_code == 201
    full = draft(prompt="3")
    assert full.status_code == 409 and full.json()["detail"]["code"] == "MODEL_DRAFT_LIMIT"
    monkeypatch.setattr(config, "PROVIDER_MODE", "fashn")
    blocked = draft(prompt="4")
    assert blocked.status_code == 409 and blocked.json()["detail"]["code"] == "MODEL_PROVIDER_NOT_CONNECTED", "fails closed: nothing is sent anywhere"


def test_identity_mapping_prefers_the_explicit_key_and_keeps_unknown_keys_only_under_design():
    ident = model_drafts.identity_from_design(" A ", {"hair": "bob", "hairstyle": "ignored-second", "camera": "wide", "tags": ["x", "y"], "face_shape": ["oval", "soft"]})
    assert ident["name"] == "A" and ident["hairstyle"] == "ignored-second" and ident["face_shape"] == "oval, soft"
    assert "camera" not in ident and ident["design"]["camera"] == "wide" and ident["design"]["tags"] == ["x", "y"]
