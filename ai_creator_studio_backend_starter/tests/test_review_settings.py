"""Reply 40: workspace settings require_review_for_export and forbid_self_approval: defaults, who may change them, history, and the gates (job export, market publish;
photo / lookbook exports are checked for the wiring by running their existing flows with a spy)."""
import io
import sqlite3

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import config, reviews
from app.main import app
from app.output_asset_link_worker import process_one
from tests.test_assets_api import asset_env  # noqa: F401
from tests.test_output_asset_link_worker import linked_output_env  # noqa: F401
from tests.test_photo_steps_api import auth, env  # noqa: F401  (wa: owner a + viewer c, wb: owner b)

client = TestClient(app)
A = {"Authorization": "Bearer token-user-a"}
B = {"Authorization": "Bearer token-user-b"}
WS = "ws-output-link"


@pytest.fixture
def team(env, monkeypatch):
    monkeypatch.setattr(config, "asset_api_tokens", lambda: {"token-a": "user-a", "token-b": "user-b", "token-c": "user-c", "token-d": "user-d", "token-e": "user-e"})
    assert client.post("/v1/workspaces/wa/members", headers=auth("a"), json={"user_id": "user-d", "role": "editor"}).status_code == 201
    assert client.post("/v1/workspaces/wa/members", headers=auth("a"), json={"user_id": "user-e", "role": "admin"}).status_code == 201
    return env


def settings(who="a", ws="wa"):
    return client.get(f"/v1/workspaces/{ws}/settings", headers=auth(who))


def patch(who="a", ws="wa", **body):
    return client.patch(f"/v1/workspaces/{ws}/settings", headers=auth(who), json=body)


def test_defaults_are_off_and_everyone_in_the_workspace_can_read_them(team):
    for who in "acde":
        r = settings(who)
        assert r.status_code == 200 and r.json() == {"workspace_id": "wa", "require_review_for_export": False, "forbid_self_approval": False, "updated_at": None, "updated_by": None}
    assert settings("b").status_code in (403, 404) and client.get("/v1/workspaces/wa/settings").status_code == 401


def test_only_owner_and_admin_change_them_and_every_change_is_in_the_history(team):
    for who in "cd":
        assert patch(who, require_review_for_export=True).status_code == 403, "viewer / editor"
    assert patch("b", require_review_for_export=True).status_code in (403, 404)
    assert client.patch("/v1/workspaces/wa/settings", json={"forbid_self_approval": True}).status_code == 401
    r = patch("e", require_review_for_export=True)
    assert r.status_code == 200 and r.json()["require_review_for_export"] is True and r.json()["forbid_self_approval"] is False and r.json()["updated_by"] == "user-e"
    assert patch("a", forbid_self_approval=True, require_review_for_export=True).json() == settings("c").json() | {} and settings("c").json()["forbid_self_approval"] is True
    patch("a", require_review_for_export=False)
    history = client.get("/v1/workspaces/wa/settings/history", headers=auth("a")).json()
    assert [(h["field"], h["old_value"], h["new_value"], h["actor_id"]) for h in history] == [
        ("require_review_for_export", False, True, "user-e"), ("forbid_self_approval", False, True, "user-a"), ("require_review_for_export", True, False, "user-a")], "an unchanged value adds no history"
    assert client.get("/v1/workspaces/wa/settings/history", headers=auth("c")).status_code == 403
    with sqlite3.connect(config.ASSET_DATABASE_PATH) as c:
        for sql in ("UPDATE workspace_settings_history SET actor_id='x'", "DELETE FROM workspace_settings_history"):
            with pytest.raises(sqlite3.DatabaseError, match="append-only"):
                c.execute(sql)


@pytest.mark.parametrize("body", [{}, {"require_review_for_export": None}, {"require_review_for_export": "yes"}, {"forbid_self_approval": 2}, {"other": True}, {"require_review_for_export": []}])
def test_bad_settings_bodies_are_refused(team, body):
    assert patch("a", **body).status_code == 422
    assert settings("a").json()["require_review_for_export"] is False


def test_settings_are_per_workspace(team):
    patch("a", require_review_for_export=True)
    assert settings("b", "wb").json()["require_review_for_export"] is False


# ---- self approval
def asset(who="a", ws="wa", shade=1):
    buf = io.BytesIO(); Image.new("RGB", (12, 12), (shade, shade, shade)).save(buf, format="PNG")
    r = client.post("/v1/assets/images", headers=auth(who), data={"workspace_id": ws, "rights_confirmed": "true"}, files={"file": ("a.png", buf.getvalue(), "image/png")})
    assert r.status_code == 201, r.text
    return r.json()["asset_id"]


def ask(asset_id, who):
    r = client.post("/v1/workspaces/wa/reviews", headers=auth(who), json={"asset_id": asset_id})
    assert r.status_code == 201, r.text
    return r.json()["review_id"]


def act(review_id, action, who, comment=None):
    return client.post(f"/v1/workspaces/wa/reviews/{review_id}/{action}", headers=auth(who), json={"comment": comment} if comment else {})


def test_forbidding_self_approval_blocks_only_the_requesters_own_approval(team):
    a1 = asset()
    rv = ask(a1, "a")
    assert act(rv, "approve", "a").status_code == 200, "off by default: an owner working alone is not stuck"
    patch("a", forbid_self_approval=True)
    rv2 = ask(asset(shade=2), "a")
    blocked = act(rv2, "approve", "a")
    assert blocked.status_code == 403 and blocked.json()["detail"]["code"] == "REVIEW_SELF_APPROVAL_FORBIDDEN"
    assert client.get(f"/v1/workspaces/wa/reviews/{rv2}", headers=auth("a")).json()["status"] == "requested", "nothing changed"
    assert act(rv2, "request-changes", "a", "my own note").status_code == 200, "only APPROVAL by the requester is forbidden"
    rv3 = ask(asset(shade=3), "d")
    assert act(rv3, "approve", "e").status_code == 200, "someone else may approve"
    rv4 = ask(asset(shade=4), "d")
    assert act(rv4, "approve", "a").status_code == 200
    patch("a", forbid_self_approval=False)
    rv5 = ask(asset(shade=5), "e")
    assert act(rv5, "approve", "e").status_code == 200, "off again"


# ---- the export gate: helper
def test_the_gate_helper_is_silent_when_off_and_lists_the_blocked_ids_when_on(team):
    from fastapi import HTTPException
    a1, a2, a3 = asset(shade=1), asset(shade=2), asset(shade=3)
    reviews.require_approved("wa", [a1, a2, None])           # off: nothing happens
    patch("a", require_review_for_export=True)
    reviews.require_approved("wa", [])                        # nothing to export
    with pytest.raises(HTTPException) as e:
        reviews.require_approved("wa", [a1, a2, a3, a1])
    assert e.value.status_code == 409 and e.value.detail["code"] == "REVIEW_NOT_APPROVED" and e.value.detail["asset_ids"] == [a1, a2, a3], "never-reviewed assets are refused too, listed once"
    act(ask(a1, "d"), "approve", "e")
    r2 = ask(a2, "d"); act(r2, "reject", "e", "no")
    r3 = ask(a3, "d")
    with pytest.raises(HTTPException) as e:
        reviews.require_approved("wa", [a1, a2, a3])
    assert e.value.detail["asset_ids"] == [a2, a3], "rejected and still-requested are refused, approved passes"
    act(r3, "approve", "e")
    reviews.require_approved("wa", [a1, a3])
    reviews.require_approved("wb", [a2])                      # another workspace has its own setting (off)
    r2b = ask(a2, "d"); act(r2b, "approve", "e")
    reviews.require_approved("wa", [a1, a2, a3])


# ---- the export gate: a try-on job's manifest
def finish(env_):
    job_id = env_["job_id"]
    out = client.get(f"/v1/generation-jobs/{job_id}/outputs", headers=A).json()["data"][0]
    assert process_one(worker_id="delivery-worker") is True
    return job_id, out["id"]


def test_the_job_manifest_follows_the_setting(linked_output_env):
    job_id, output_id = finish(linked_output_env)
    assert client.post(f"/v1/generation-jobs/{job_id}/outputs/{output_id}/review/approve", headers=A, json={"comment": "ok"}).status_code == 200
    manifest = lambda: client.post(f"/v1/generation-jobs/{job_id}/outputs/export-manifest", headers=A)
    assert manifest().status_code == 200, "setting off: exactly the old behaviour"
    assert client.patch(f"/v1/workspaces/{WS}/settings", headers=A, json={"require_review_for_export": True}).status_code == 200
    out = client.get(f"/v1/generation-jobs/{job_id}/outputs", headers=A).json()["data"][0]
    blocked = manifest()
    assert blocked.status_code == 409 and blocked.json()["detail"]["code"] == "REVIEW_NOT_APPROVED" and blocked.json()["detail"]["asset_ids"] == [out["asset_id"]]
    rv = client.post(f"/v1/workspaces/{WS}/reviews", headers=A, json={"asset_id": out["asset_id"]}).json()["review_id"]
    assert manifest().status_code == 409, "requested is not approved"
    assert client.post(f"/v1/workspaces/{WS}/reviews/{rv}/approve", headers=A, json={}).status_code == 200
    assert manifest().status_code == 200
    assert client.patch(f"/v1/workspaces/{WS}/settings", headers=A, json={"require_review_for_export": False}).status_code == 200
    assert manifest().status_code == 200


# ---- the market publish gate (cover picture)
def test_a_market_listing_with_a_cover_needs_its_review_when_the_setting_is_on(team):
    cover = asset(shade=9)
    body = {"workspace_id": "wa", "kind": "preset", "title": "t", "license_scope": "personal", "is_ai_generated": False, "rights_confirmed": True, "cover_asset_id": cover}
    item = client.post("/v1/market/listings", headers=auth("a"), json=body).json()
    plain = client.post("/v1/market/listings", headers=auth("a"), json={k: v for k, v in body.items() if k != "cover_asset_id"}).json()
    pub = lambda i: client.post(f"/v1/market/listings/{i['listing_id']}/publish", headers=auth("a"), json={"rights_confirmed": True})
    assert pub(item).status_code == 200, "off: unchanged"
    client.post(f"/v1/market/listings/{item['listing_id']}/unpublish", headers=auth("a"))
    patch("a", require_review_for_export=True)
    blocked = pub(item)
    assert blocked.status_code == 409 and blocked.json()["detail"]["asset_ids"] == [cover]
    assert pub(plain).status_code == 200, "a listing without a cover has nothing to review"
    act(ask(cover, "d"), "approve", "e")
    assert pub(item).status_code == 200


# ---- the wiring of the photo and lookbook exports (their existing flows run with a spy on the gate)
def spy(monkeypatch):
    calls = []
    real = reviews.require_approved
    monkeypatch.setattr(reviews, "require_approved", lambda ws, ids: (calls.append((ws, [i for i in ids if i])), real(ws, ids))[1])
    return calls


def test_the_photo_run_export_asks_the_gate_with_the_runs_result_asset(asset_env, monkeypatch):
    from tests import test_assets_api as ta
    calls = spy(monkeypatch)
    ta.test_photo_output_review_approval_and_internal_manifest_gate(asset_env)
    assert calls and all(ws == "ws-a" for ws, _ in calls) and any(len(ids) == 1 for _, ids in calls), calls


def test_the_lookbook_manifest_and_package_ask_the_gate_with_every_output_asset(asset_env, monkeypatch):
    from tests import test_assets_api as ta
    calls = spy(monkeypatch)
    ta.test_lookbook_assembles_only_approved_photo_outputs_with_product_variant_snapshot(asset_env)
    assert calls and all(ws == "ws-a" for ws, _ in calls) and any(len(ids) >= 1 for _, ids in calls), calls
