"""R-046: try-on inputs from "my library": ids at creation, short-lived signed addresses only at dispatch, approval-gated delivery, provider chain."""
import asyncio
import json
import sqlite3
from urllib.parse import urlparse

import pytest
from fastapi.testclient import TestClient

from app import config, provider_chain, tryon_inputs
from app.main import app
from tests.test_photo_steps_api import auth, env  # noqa: F401  (wa: owner a + viewer c, wb: owner b; env["asset"] is an image in wa)
from tests.test_workspace_library import glb, png

client = TestClient(app)


def item(kind, color, name="x", ws="wa", who="a"):
    r = client.post(f"/v1/workspaces/{ws}/library", headers=auth(who), data={"kind": kind, "name": name, "rights_confirmed": "true"},
                    files={"file": (f"{name}.png", png(color), "image/png")})
    assert r.status_code == 201, r.text
    return r.json()


def job(body, who="a"):
    return client.post("/v1/generation-jobs", headers=auth(who), json={"workspace_id": "wa", **body})


def test_a_job_can_be_made_from_two_library_items_and_stores_only_ids(env):
    m, g = item("model", (10, 20, 30), "model"), item("garment", (200, 10, 10), "garment")
    r = job({"model_item_id": m["item_id"], "garment_item_id": g["item_id"]})
    assert r.status_code == 202, r.text
    raw = sqlite3.connect(env["tmp"] / "a.sqlite3").execute("SELECT payload_json FROM generation_jobs WHERE job_id=?", (r.json()["job_id"],)).fetchone()[0]
    payload = json.loads(raw)
    assert payload["model_item_id"] == m["item_id"] and payload["garment_item_id"] == g["item_id"]
    assert not payload.get("model_image_url") and not payload.get("garment_image_url")
    assert "signature=" not in raw and "expires=" not in raw, "no signed address is ever stored with a job"


def test_urls_still_work_and_a_mixed_pick_is_allowed(env):
    g = item("garment", (200, 10, 10), "garment")
    assert job({"model_image_url": "https://example.com/m.jpg", "garment_image_url": "https://example.com/g.jpg"}).status_code == 202
    assert job({"model_image_url": "https://example.com/m.jpg", "garment_item_id": g["item_id"]}).status_code == 202


@pytest.mark.parametrize("body", [
    {},                                                               # nothing at all
    {"model_image_url": "https://example.com/m.jpg"},                 # garment side missing
    {"model_item_id": "wli_x", "model_image_url": "https://example.com/m.jpg", "garment_image_url": "https://example.com/g.jpg"},   # two sources for one side
    {"model_item_id": "ab", "garment_image_url": "https://example.com/g.jpg"},   # too short to be an id
])
def test_exactly_one_source_per_side(env, body):
    assert job(body).status_code == 422


def test_bad_picks_are_refused_at_once(env):
    m, g = item("model", (1, 2, 3), "m"), item("garment", (4, 5, 6), "g")
    wrong = job({"model_item_id": g["item_id"], "garment_item_id": g["item_id"]})
    assert wrong.status_code == 422 and wrong.json()["detail"]["code"] == "TRYON_INPUT_KIND", "a garment cannot be the model"
    wrong2 = job({"model_item_id": m["item_id"], "garment_item_id": m["item_id"]})
    assert wrong2.status_code == 422 and wrong2.json()["detail"]["code"] == "TRYON_INPUT_KIND"
    missing = job({"model_item_id": "wli_doesnotexist", "garment_item_id": g["item_id"]})
    assert missing.status_code == 404 and missing.json()["detail"]["code"] == "TRYON_INPUT_NOT_FOUND"
    other = item("model", (9, 9, 9), "other", ws="wb", who="b")
    foreign = job({"model_item_id": other["item_id"], "garment_item_id": g["item_id"]})
    assert foreign.status_code == 404, "another workspace's item id does not exist for this workspace"
    three_d = client.post("/v1/workspaces/wa/library", headers=auth("a"), data={"kind": "3d", "name": "chair"}, files={"file": ("c.glb", glb(), "model/gltf-binary")}).json()
    assert job({"model_item_id": three_d["item_id"], "garment_item_id": g["item_id"]}).status_code == 422, "a 3D item is not an image input"


def test_roles_and_holds(env):
    m, g = item("model", (1, 2, 3), "m"), item("garment", (4, 5, 6), "g")
    assert job({"model_item_id": m["item_id"], "garment_item_id": g["item_id"]}, who="c").status_code == 403, "a viewer cannot start jobs"
    with sqlite3.connect(env["tmp"] / "a.sqlite3") as c:
        c.execute("INSERT INTO asset_takedowns(asset_id, workspace_id, state, since, updated_at) VALUES (?,?,?,?,?)",
                  (m["asset_id"], "wa", "under_review", "2026-11-16T00:00:00+00:00", "2026-11-16T00:00:00+00:00"))
    assert job({"model_item_id": m["item_id"], "garment_item_id": g["item_id"]}).status_code in (202, 404), "its owner (a) may still use it"
    # user-b is not a member, and user-c is a viewer: neither can start a job from the held item
    assert job({"model_item_id": m["item_id"], "garment_item_id": g["item_id"]}, who="b").status_code in (403, 404)


def test_the_address_is_made_at_dispatch_short_lived_and_really_serves_the_image(env, monkeypatch):
    m, g = item("model", (10, 20, 30), "m"), item("garment", (200, 10, 10), "g")
    payload = {"workspace_id": "wa", "model_item_id": m["item_id"], "garment_item_id": g["item_id"]}
    monkeypatch.setattr(config, "PUBLIC_API_BASE_URL", "https://api.example.org")
    out = tryon_inputs.resolve_payload(payload, for_provider=True)
    assert out["model_item_id"] == m["item_id"], "the original is kept, only a copy gets addresses"
    assert "model_image_url" not in payload
    for key in ("model_image_url", "garment_image_url"):
        u = urlparse(out[key])
        assert u.scheme == "https" and u.netloc == "api.example.org" and "/versions/" in u.path
        r = client.get(f"{u.path}?{u.query}")
        assert r.status_code == 200 and r.headers["content-type"].startswith("image/"), "the signed address serves the picture without a login"
        q = dict(p.split("=") for p in u.query.split("&"))
        assert int(q["expires"]) - __import__("time").time() <= config.TRYON_INPUT_URL_TTL_SECONDS + 2
    tampered = urlparse(out["model_image_url"])
    assert client.get(f"{tampered.path}?{tampered.query[:-3]}000").status_code == 403, "a changed signature is refused"


def test_the_lifetime_is_capped_and_a_real_provider_needs_a_public_https_base(env, monkeypatch):
    m = item("model", (1, 2, 3), "m"); g = item("garment", (4, 5, 6), "g")
    payload = {"workspace_id": "wa", "model_item_id": m["item_id"], "garment_item_id": g["item_id"]}
    monkeypatch.setattr(config, "PUBLIC_API_BASE_URL", "https://api.example.org")
    monkeypatch.setattr(config, "TRYON_INPUT_URL_TTL_SECONDS", 100000)
    q = dict(p.split("=") for p in urlparse(tryon_inputs.resolve_payload(payload, for_provider=True)["model_image_url"]).query.split("&"))
    assert int(q["expires"]) - __import__("time").time() <= 902, "never longer than 15 minutes"
    for bad in ("", "http://api.example.org"):
        monkeypatch.setattr(config, "PUBLIC_API_BASE_URL", bad)
        with pytest.raises(tryon_inputs.TryOnInputError) as err:
            tryon_inputs.resolve_payload(payload, for_provider=True)
        assert err.value.code == "TRYON_PUBLIC_URL_MISSING"
    assert tryon_inputs.resolve_payload(payload, for_provider=False)["model_image_url"].startswith("https://mock.invalid/"), "mock needs no public address"


def test_an_item_that_disappears_before_dispatch_fails_cleanly(env, monkeypatch):
    m, g = item("model", (1, 2, 3), "m"), item("garment", (4, 5, 6), "g")
    payload = {"workspace_id": "wa", "model_item_id": m["item_id"], "garment_item_id": g["item_id"]}
    assert client.delete(f"/v1/workspaces/wa/library/{m['item_id']}", headers=auth("a")).status_code == 204
    with pytest.raises(tryon_inputs.TryOnInputError) as err:
        tryon_inputs.resolve_payload(payload, for_provider=False)
    assert err.value.code == "TRYON_INPUT_NOT_FOUND"


def test_the_worker_hands_the_provider_fresh_addresses_not_ids(env, monkeypatch):
    import app.main as main
    from app import worker
    m, g = item("model", (10, 20, 30), "m"), item("garment", (200, 10, 10), "g")
    created = job({"model_item_id": m["item_id"], "garment_item_id": g["item_id"]})
    assert created.status_code == 202, created.text
    seen = {}

    class Recorder:
        name = "mock"; model = "mock-tryon"
        async def start(self, payload):
            seen.update(payload); return {"request_id": "mock_r1", "status": "running"}
    monkeypatch.setattr(main, "get_provider_for_job", lambda j: Recorder())
    assert asyncio.run(worker.process_one()) is True
    assert seen["model_image_url"].startswith("https://") and seen["garment_image_url"].startswith("https://")
    assert "/versions/" in seen["model_image_url"] and "signature=" in seen["garment_image_url"]


def test_disclosure_traces_library_picks_to_their_origin(env):
    from app.ai_disclosure import input_source_of_job
    m, g = item("model", (1, 2, 3), "m"), item("garment", (4, 5, 6), "g")
    pay = {"workspace_id": "wa", "model_item_id": m["item_id"], "garment_item_id": g["item_id"]}
    assert input_source_of_job({"payload": pay}) == "uploaded"
    assert input_source_of_job({"payload": {**pay, "model_item_id": "wli_gone"}}) == "unknown"


def test_provider_chain_never_replays_an_unknown_outcome():
    chain = provider_chain.parse_chain("FASHN", " second ,third")
    assert chain.order == ("fashn", "second", "third")
    assert chain.next_after(["fashn"], provider_chain.NOT_ACCEPTED) == "second"
    assert chain.next_after(["fashn", "second"], provider_chain.NOT_ACCEPTED) == "third"
    assert chain.next_after(["fashn", "second", "third"], provider_chain.NOT_ACCEPTED) is None, "the end of the chain"
    assert chain.next_after(["fashn"], provider_chain.UNKNOWN) is None, "a timeout may mean the first provider is already working and billing"
    assert chain.next_after(["fashn"], provider_chain.ACCEPTED) is None
    assert provider_chain.parse_chain("mock", None).order == ("mock",)
    for bad in (("a", "a"), ("", "b")):
        with pytest.raises(ValueError):
            provider_chain.ProviderChain(bad[0], (bad[1],))
    with pytest.raises(ValueError):
        provider_chain.parse_chain("a", "b,,a")
