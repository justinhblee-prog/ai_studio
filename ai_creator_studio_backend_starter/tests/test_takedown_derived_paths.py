"""L-08 follow-up: new work is not built on an asset that is under a report (photo drafts, local processing)."""
import io

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def auth(user):
    return {"Authorization": f"Bearer token-{user}"}


def png(shade=120):
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (40, 30), (shade, 60, 120)).save(buf, format="PNG")
    return buf.getvalue()


DRAFT = {"operation": "ENHANCE", "preserve_identity": True, "preserve_product_geometry": True, "preserve_text_and_logo": True,
         "output_format": "PNG", "output_count": 1}


@pytest.fixture
def env(tmp_path, monkeypatch):
    import app.config as config
    monkeypatch.setattr(config, "ASSET_STORAGE_DIR", tmp_path / "private")
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path / "outputs")
    monkeypatch.setattr(config, "ASSET_DATABASE_PATH", tmp_path / "d.sqlite3")
    monkeypatch.setattr(config, "GENERATION_DATABASE_PATH", None)
    monkeypatch.setattr(config, "ASSET_SIGNING_SECRET", "s" * 48)
    monkeypatch.setattr(config, "OPS_ADMIN_USER_IDS", ("ops",))
    monkeypatch.setattr(config, "asset_api_tokens", lambda: {f"token-{u}": u for u in ("owner", "reporter", "ops")})
    assert client.post("/v1/workspaces", headers=auth("owner"), json={"workspace_id": "dp-ws"}).status_code == 201
    assert client.post("/v1/workspaces/dp-ws/members", headers=auth("owner"), json={"user_id": "reporter", "role": "viewer"}).status_code == 201


def new_asset(shade=120):
    r = client.post("/v1/assets/images", headers=auth("owner"), data={"workspace_id": "dp-ws"}, files={"file": ("a.png", png(shade), "image/png")})
    assert r.status_code == 201, r.text
    return r.json()["asset_id"]


def draft_for(asset_id):
    return client.post("/v1/photo-drafts", headers=auth("owner"), json={"workspace_id": "dp-ws", "source_asset_id": asset_id, **DRAFT})


def run_local(draft_id, key):
    return client.post(f"/v1/photo-drafts/{draft_id}/process-local?workspace_id=dp-ws", headers=auth("owner") | {"Idempotency-Key": key}, json={})


def assets_count():
    return len(client.get("/v1/assets?workspace_id=dp-ws&kind=image", headers=auth("owner")).json()["items"])


def report_and_get_id(asset_id):
    assert client.post("/v1/content-reports", headers=auth("reporter"), json={"asset_id": asset_id, "category": "likeness"}).status_code == 202
    return client.get("/internal/moderation/reports", headers=auth("ops")).json()["items"][0]["report_id"]


def test_a_held_source_cannot_start_a_photo_draft_or_be_processed_and_works_again_after_a_restore(env):
    source = new_asset()
    ok = draft_for(source)
    assert ok.status_code == 201, ok.text
    draft_id = ok.json()["draft_id"]                      # saved before the report
    rid = report_and_get_id(source)
    before = assets_count()
    refused = draft_for(source)
    assert refused.status_code == 409 and refused.json()["detail"]["code"] == "ASSET_UNDER_REVIEW", refused.text
    processed = run_local(draft_id, "dp-key-held-01")
    assert processed.status_code == 409 and "under review" in processed.text, processed.text   # the hold is the reason
    assert assets_count() == before                           # and no derived asset was created
    runs = client.get(f"/v1/photo-drafts/{draft_id}/runs?workspace_id=dp-ws", headers=auth("owner")).json()
    assert (runs.get("items") or runs.get("runs") or []) == []   # no failed run was left behind either
    assert client.post(f"/internal/moderation/reports/{rid}/resolve", headers=auth("ops"), json={"decision": "restore"}).status_code == 200
    again = run_local(draft_id, "dp-key-after-02")
    assert again.status_code == 200, again.text
    assert assets_count() == before + 1
    assert draft_for(source).status_code == 201


def test_a_removed_source_stays_unusable(env):
    source = new_asset()
    draft_id = draft_for(source).json()["draft_id"]
    rid = report_and_get_id(source)
    assert client.post(f"/internal/moderation/reports/{rid}/resolve", headers=auth("ops"), json={"decision": "remove"}).status_code == 200
    assert draft_for(source).status_code == 409
    removed_run = run_local(draft_id, "dp-key-removed-03")
    assert removed_run.status_code == 409 and "under review" in removed_run.text, removed_run.text


def test_a_hold_that_arrives_after_the_run_was_claimed_still_stops_the_render(env, monkeypatch):
    import app.photo_engine as engine
    source = new_asset()
    draft_id = draft_for(source).json()["draft_id"]
    real_claim = engine.claim_local_run

    def claim_then_report(*args, **kwargs):
        claim = real_claim(*args, **kwargs)
        assert client.post("/v1/content-reports", headers=auth("reporter"), json={"asset_id": source, "category": "copyright"}).status_code == 202
        return claim
    monkeypatch.setattr(engine, "claim_local_run", claim_then_report)
    before = assets_count()
    res = run_local(draft_id, "dp-key-race-0004")
    assert res.status_code == 422, res.text                  # claimed, then refused at render time
    assert assets_count() == before                          # nothing was derived
