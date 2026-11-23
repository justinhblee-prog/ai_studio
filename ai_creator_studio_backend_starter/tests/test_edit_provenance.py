"""AI-edit provenance: the edit list per asset and the AI-disclosure decision made from it (thresholds are temporary, pending Q11-5/Q11-6)."""
import pytest
from fastapi.testclient import TestClient

from app import ai_marking, edit_provenance as ep
from app.main import app
from tests.test_photo_steps_api import auth, env, run  # noqa: F401  (wa: owner a + viewer c, wb: owner b)

client = TestClient(app)


def edit(op, by="user", provider=None):
    return {"op": op, "by": by, "at": "2026-11-23T00:00:00+00:00", **({"provider": provider} if provider else {})}


@pytest.mark.parametrize("edits, generated, assisted, kind", [
    ([], False, False, None),                                                                       # an untouched upload: nothing to disclose
    ([edit("auto_crop"), edit("fit_canvas")], False, False, None),                                 # the customer's own crop and resize
    ([edit("generate", "ai", "p")], True, False, "generated"),                                     # made by AI
    ([edit("ai_retouch", "ai", "p")], False, True, "edited"),                                      # the customer's picture + an AI step
    ([edit("ai_retouch", "ai"), edit("auto_crop")], False, True, "edited"),                        # a later local crop does not remove it
    ([edit("generate", "ai"), edit("auto_crop")], True, False, "generated"),                       # nor does it turn generated into assisted
])
def test_the_decision_follows_who_made_each_step(edits, generated, assisted, kind):
    d = ep.decide(edits)
    assert (d["is_ai_generated"], d["ai_assisted"], d["mark_kind"]) == (generated, assisted, kind)
    assert d["status"] == "temporary_pending_legal_review" and "Q11-5" in d["rule"]
    assert (d["digital_source_type"] is None) == (kind is None)
    if kind:
        assert d["digital_source_type"].endswith(ai_marking.SOURCE_TYPE[kind])


def test_an_upload_has_no_edits_and_local_photo_steps_are_user_edits_without_a_mark(env):
    r = client.get(f"/v1/assets/{env['asset']}/edits", headers=auth("a"))
    assert r.status_code == 200 and r.json()["edits"] == [] and r.json()["decision"]["mark_kind"] is None
    new_id = run(env).json()["asset"]["asset_id"]
    got = client.get(f"/v1/assets/{new_id}/edits", headers=auth("a")).json()
    assert [(e["op"], e["by"]) for e in got["edits"]] == [("auto_crop", "user"), ("fit_canvas", "user")]
    assert got["decision"]["is_ai_generated"] is False and got["decision"]["ai_assisted"] is False


def test_an_explicit_ai_step_makes_the_asset_and_its_later_copies_ai_assisted(env):
    ep.record_edit("wa", env["asset"], "ai_retouch", "ai", "user-a", provider="some-provider")
    base = client.get(f"/v1/assets/{env['asset']}/edits", headers=auth("a")).json()
    assert base["edits"][0]["provider"] == "some-provider" and base["decision"]["ai_assisted"] is True
    copy_id = run(env).json()["asset"]["asset_id"]                                               # a local crop of the AI-retouched picture
    chain = client.get(f"/v1/assets/{copy_id}/edits", headers=auth("a")).json()
    assert [e["by"] for e in chain["edits"]] == ["ai", "user", "user"] and chain["decision"]["ai_assisted"] is True


def test_roles_scope_and_input_checks(env):
    assert client.get(f"/v1/assets/{env['asset']}/edits", headers=auth("c")).status_code == 200      # a viewer may read
    assert client.get(f"/v1/assets/{env['asset']}/edits", headers=auth("b")).status_code in (403, 404)
    assert client.get(f"/v1/assets/{env['asset']}/edits").status_code in (401, 403)
    assert client.get("/v1/assets/nope/edits", headers=auth("a")).status_code == 404
    for bad in (("", "user"), ("x", "robot"), ("y" * 41, "ai")):
        with pytest.raises(ValueError):
            ep.record_edit("wa", env["asset"], bad[0], bad[1], "user-a")


@pytest.mark.parametrize("kind, op, generated, assisted", [("generated", "generate", True, False), ("unknown", "generate", True, False), ("edited", "ai_edit", False, True)])
def test_an_imported_ai_job_result_is_a_generate_or_ai_edit_step_by_ai(env, monkeypatch, kind, op, generated, assisted):
    import uuid
    from app.assets import store
    with store._connect() as db:
        db.execute("INSERT INTO asset_provenance(provenance_id, workspace_id, asset_id, version_number, event_type, actor_id, details_json, created_at) VALUES (?,?,?,?,?,?,?,?)",
                   ("ap_" + uuid.uuid4().hex, "wa", env["asset"], 1, "asset.generated_output_imported", "worker", '{"provider": "prov-x"}', "2026-11-23T00:00:00+00:00"))
    monkeypatch.setattr(ai_marking, "kind_for_asset", lambda aid: kind)
    got = client.get(f"/v1/assets/{env['asset']}/edits", headers=auth("a")).json()
    assert [(e["op"], e["by"], e.get("provider")) for e in got["edits"]] == [(op, "ai", "prov-x")]
    assert (got["decision"]["is_ai_generated"], got["decision"]["ai_assisted"]) == (generated, assisted)
