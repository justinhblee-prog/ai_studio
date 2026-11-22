"""E-05: the .glb export carries its provenance (hash, ids, AI disclosure) and changes nothing else; roles, integrity, audit trail."""
import hashlib
import json
import sqlite3
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app import ai_marking, model_export
from app.glb_tools import build_glb, parse_glb
from app.main import app
from tests.test_photo_steps_api import auth, env, product_png  # noqa: F401
from tests.test_workspace_library import glb

client = TestClient(app)


def upload_glb(content=None, name="chair.glb", who="a", ws="wa"):
    r = client.post("/v1/assets", headers=auth(who), data={"workspace_id": ws}, files={"file": (name, content or glb(), "model/gltf-binary")})
    assert r.status_code == 201, r.text
    return r.json()["asset_id"]


def version_of(asset_id, who="a"):
    return client.get(f"/v1/assets/{asset_id}/versions", headers=auth(who)).json()["items"][0]


def export(asset_id, version_id, who="a"):
    return client.get(f"/v1/assets/{asset_id}/versions/{version_id}/export", headers=auth(who))


def stored_path(env, asset_id):
    return next((env["tmp"] / "private").glob(f"{asset_id}.*"))


def test_the_export_is_the_stored_model_plus_one_provenance_block(env):
    asset_id = upload_glb()
    version = version_of(asset_id)
    r = export(asset_id, version["version_id"])
    assert r.status_code == 200 and r.headers["content-type"] == "model/gltf-binary" and r.headers["content-disposition"] == 'attachment; filename="chair-export.glb"'
    digest = hashlib.sha256(r.content).hexdigest()
    assert r.headers["x-content-sha256"] == digest and r.headers["etag"] == f'"{digest}"' and "no-store" in r.headers["cache-control"]
    doc, _ = parse_glb(r.content)
    block = doc["asset"]["extras"]["acs_export"]
    assert block["schema"] == "acs-3d-export.v1" and block["asset_id"] == asset_id and block["version_id"] == version["version_id"] and block["version_number"] == version["version_number"]
    assert block["source_sha256"] == version["checksum_sha256"] == hashlib.sha256(stored_path(env, asset_id).read_bytes()).hexdigest()
    assert block["ai_disclosure"] == {"is_ai_generated": False, "digital_source_type": None, "text": None}
    assert datetime.strptime(block["exported_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc) <= datetime.now(timezone.utc)
    original, _ = parse_glb(stored_path(env, asset_id).read_bytes())
    assert {k: v for k, v in doc.items() if k != "asset"} == {k: v for k, v in original.items() if k != "asset"} and doc["asset"]["version"] == "2.0", "nothing but asset.extras changed"


def test_geometry_and_existing_extras_are_preserved_and_the_stored_file_never_changes(env):
    from app import base_models
    model = base_models.build_base_model("female")
    doc, binary = parse_glb(model)
    doc["asset"]["extras"] = {"keep": {"me": 1}}
    original = build_glb(doc, bytes(binary))
    asset_id = upload_glb(original, "figure.glb")
    before = stored_path(env, asset_id).read_bytes()
    out = export(asset_id, version_of(asset_id)["version_id"]).content
    new_doc, new_binary = parse_glb(out)
    assert bytes(new_binary) == bytes(binary), "the geometry bytes are identical"
    assert new_doc["asset"]["extras"]["keep"] == {"me": 1} and "acs_export" in new_doc["asset"]["extras"]
    assert new_doc["meshes"] == doc["meshes"] and new_doc["materials"] == doc["materials"] and new_doc["accessors"] == doc["accessors"]
    assert stored_path(env, asset_id).read_bytes() == before == original


def test_two_exports_differ_only_in_the_time(env):
    asset_id = upload_glb()
    version_id = version_of(asset_id)["version_id"]
    a, b = (json.dumps(parse_glb(export(asset_id, version_id).content)[0], sort_keys=True) for _ in range(2))
    da, db = json.loads(a), json.loads(b)
    da["asset"]["extras"]["acs_export"].pop("exported_at")
    db["asset"]["extras"]["acs_export"].pop("exported_at")
    assert da == db


@pytest.mark.parametrize("kind, source_type", [("generated", "trainedAlgorithmicMedia"), ("edited", "compositeWithTrainedAlgorithmicMedia")])
def test_an_ai_result_is_marked_with_the_iptc_source_type_and_the_configured_wording(env, monkeypatch, kind, source_type):
    asset_id = upload_glb()
    monkeypatch.setattr(ai_marking, "kind_for_asset", lambda aid: kind)
    block = parse_glb(export(asset_id, version_of(asset_id)["version_id"]).content)[0]["asset"]["extras"]["acs_export"]["ai_disclosure"]
    assert block["is_ai_generated"] is True and block["digital_source_type"] == ai_marking.DST + source_type and block["text"] == ai_marking.text_for(kind)


def test_the_export_is_written_to_the_asset_provenance_with_both_hashes(env):
    asset_id = upload_glb()
    version = version_of(asset_id)
    r = export(asset_id, version["version_id"])
    db = sqlite3.connect(env["tmp"] / "a.sqlite3")
    rows = db.execute("SELECT actor_id, version_number, details_json FROM asset_provenance WHERE asset_id=? AND event_type='asset.exported'", (asset_id,)).fetchall()
    assert len(rows) == 1 and rows[0][0] == "user-a" and rows[0][1] == version["version_number"]
    details = json.loads(rows[0][2])
    assert details["export_sha256"] == r.headers["x-content-sha256"] and details["source_sha256"] == version["checksum_sha256"] and details["bytes"] == len(r.content) and details["format"] == "glb"


def test_roles_sign_in_and_other_workspaces(env):
    asset_id = upload_glb()
    version_id = version_of(asset_id)["version_id"]
    assert client.get(f"/v1/assets/{asset_id}/versions/{version_id}/export").status_code == 401
    assert export(asset_id, version_id, who="c").status_code == 403, "a viewer can look at the model but not take it away"
    assert export(asset_id, version_id, who="b").status_code in (403, 404), "another workspace's owner cannot export it"
    assert export("ast_missing", version_id).status_code == 404 and export(asset_id, "av_missing").status_code == 404


def test_only_glb_models_can_be_exported(env):
    r = export(env["asset"], version_of(env["asset"])["version_id"])
    assert r.status_code == 422 and r.json()["detail"]["code"] == "EXPORT_NOT_GLB"


def test_a_stored_file_that_no_longer_matches_its_record_is_refused_and_not_exported(env):
    asset_id = upload_glb()
    version_id = version_of(asset_id)["version_id"]
    path = stored_path(env, asset_id)
    path.write_bytes(path.read_bytes() + b"\x00\x00\x00\x00")
    assert export(asset_id, version_id).status_code == 409
    db = sqlite3.connect(env["tmp"] / "a.sqlite3")
    assert db.execute("SELECT COUNT(*) FROM asset_provenance WHERE asset_id=? AND event_type='asset.exported'", (asset_id,)).fetchone()[0] == 0


def test_build_export_on_a_model_without_asset_extras_and_a_file_that_is_not_a_glb():
    out = model_export.build_export(glb(), asset_id="a", version_id="v", version_number=1, source_sha256="0" * 64, ai_kind=None, now=datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc))
    assert parse_glb(out)[0]["asset"]["extras"]["acs_export"]["exported_at"] == "2026-01-02T03:04:05Z"
    from app.glb_tools import GlbError
    with pytest.raises(GlbError):
        model_export.build_export(b"not a glb at all, really", asset_id="a", version_id="v", version_number=1, source_sha256="0" * 64, ai_kind=None)
