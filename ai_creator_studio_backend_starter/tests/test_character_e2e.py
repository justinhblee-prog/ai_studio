"""R-074: brand model end to end with the mock provider: values + instruction -> 6 ranked candidates -> choose -> the same person (one character id) -> reused in a try-on; real-person requests are refused."""
import pytest
from fastapi.testclient import TestClient

from app import model_drafts
from app.main import app
from tests.test_model_drafts import V, draft, refs  # noqa: F401
from tests.test_photo_steps_api import auth, env  # noqa: F401

client = TestClient(app)


def choose(draft_id, rank=1, name="브랜드 모델 하늘", who="a", reference_asset_ids=None):
    return client.post(f"/v1/workspaces/wa/model-drafts/{draft_id}/select", headers=auth(who), json={"rank": rank, "name": name, "reference_asset_ids": reference_asset_ids or []})


def test_the_whole_chain_values_to_candidates_to_one_person_to_a_try_on(env):
    d = draft().json()
    assert len(d["candidates"]) == 6 and [c["rank"] for c in d["candidates"]] == [1, 2, 3, 4, 5, 6] and d["status"] == "ready"
    scores = [c["score"] for c in d["candidates"]]
    assert scores == sorted(scores, reverse=True), "ranked best first"
    picked = choose(d["draft_id"], rank=3)
    assert picked.status_code == 200, picked.text
    out = picked.json()
    character_id, item_id = out["character_id"], out["library_item_id"]
    assert character_id and item_id and out["draft"]["status"] == "selected" and out["draft"]["character_id"] == character_id
    # one person: the character, the library item and the picked candidate agree
    ch = client.get(f"/v1/workspaces/wa/characters/{character_id}", headers=auth("a")).json()
    assert ch["identity"]["name"] == "브랜드 모델 하늘" and ch["identity"]["design"]["skin"] == 3
    item = client.get(f"/v1/workspaces/wa/library/{item_id}", headers=auth("a")).json()
    assert item["kind"] == "model" and item["asset_id"] == d["candidates"][2]["asset_id"] and item["asset_id"] in ch["asset_ids"]
    # the second choice of the same draft is refused: the person is fixed
    again = choose(d["draft_id"], rank=1, name="다른 사람")
    assert again.status_code == 409 and again.json()["detail"]["code"] == "MODEL_DRAFT_ALREADY_CHOSEN"
    assert len(client.get("/v1/workspaces/wa/characters", headers=auth("a")).json()["items" if "items" in client.get("/v1/workspaces/wa/characters", headers=auth("a")).json() else "data"]) == 1 if isinstance(client.get("/v1/workspaces/wa/characters", headers=auth("a")).json(), dict) else True
    # reuse in a scene: the library item feeds a try-on job as the model
    shirt = client.post("/v1/workspaces/wa/library", headers=auth("a"), data={"kind": "garment", "name": "셔츠", "rights_confirmed": "true"}, files={"file": ("g.png", __import__("tests.test_workspace_library", fromlist=["png"]).png((10, 120, 30)), "image/png")}).json()
    job = client.post("/v1/generation-jobs", headers=auth("a"), json={"workspace_id": "wa", "model_item_id": item_id, "garment_item_id": shirt["item_id"]})
    assert job.status_code == 202, job.text


def test_the_same_values_give_the_same_candidates_and_other_values_do_not(env):
    a, b, c = draft().json(), draft().json(), draft(v={**V, "skin": 5}).json()
    assert [x["score"] for x in a["candidates"]] == [x["score"] for x in b["candidates"]]
    assert [x["score"] for x in a["candidates"]] != [x["score"] for x in c["candidates"]]


@pytest.mark.parametrize("text", [
    "배우 OOO처럼 생긴 모델", "연예인 닮은 얼굴", "유명인과 똑같이 만들어 줘", "아이돌 얼굴 복제", "대통령 얼굴로", "실존 인물 기반", "딥페이크로",
    "make her look like a celebrity", "looks like Taylor", "A lookalike of an actress", "resembling a famous singer", "use the likeness of a real person",
    "modeled after my neighbour", "deepfake of him", "clone of a real-person face",
])
def test_requests_for_a_real_persons_likeness_are_refused_in_the_instruction_and_in_the_values(env, text):
    r = draft(prompt=text)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "MODEL_REAL_PERSON_BLOCKED", r.text
    r2 = draft(v={**V, "mood": ["calm", text]}, prompt="봄 화보")
    assert r2.status_code == 422 and r2.json()["detail"]["code"] == "MODEL_REAL_PERSON_BLOCKED"
    assert client.get("/v1/workspaces/wa/model-drafts", headers=auth("a")).json()["items"] == [], "nothing was created"


@pytest.mark.parametrize("text", ["봄 화보", "밝고 깨끗한 분위기", "a calm model with a soft smile", "the face of a young woman", "looks great in daylight", "스튜디오 조명, 30대 여성"])
def test_ordinary_wording_is_not_blocked(env, text):
    assert draft(prompt=text).status_code == 201


def test_the_rule_is_a_plain_function_and_says_what_it_catches():
    assert model_drafts.likeness_requested("닮은 사람") and model_drafts.likeness_requested("LOOKS LIKE him")
    assert not model_drafts.likeness_requested("") and not model_drafts.likeness_requested(None)


def test_the_real_person_code_is_in_the_text_table():
    from app import error_catalog
    assert "MODEL_REAL_PERSON_BLOCKED" in error_catalog.CODES and error_catalog.CODES["MODEL_REAL_PERSON_BLOCKED"] is not None


def test_roles_and_isolation_in_the_chain(env):
    d = draft().json()
    assert choose(d["draft_id"], who="c").status_code == 403, "a viewer cannot choose"
    assert client.get(f"/v1/workspaces/wb/model-drafts/{d['draft_id']}", headers=auth("b")).status_code == 404
    assert choose(d["draft_id"]).status_code == 200
