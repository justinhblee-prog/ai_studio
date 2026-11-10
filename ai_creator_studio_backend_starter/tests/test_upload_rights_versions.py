"""D2 checklist item 1 and 4: a new version of an image asset is a new photo (needs the declaration), and the upload
writes the asset and its rights record in one transaction."""
import io
import json
import struct

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def auth(token="token-user-a"):
    return {"Authorization": f"Bearer {token}"}


def png(shade=120):
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (24, 16), (10, shade, 200)).save(buf, format="PNG")
    return buf.getvalue()


def glb():
    doc = json.dumps({"asset": {"version": "2.0"}}, separators=(",", ":")).encode()
    doc += b" " * ((4 - len(doc) % 4) % 4)
    chunk = struct.pack("<II", len(doc), 0x4E4F534A) + doc
    return b"glTF" + struct.pack("<II", 2, 12 + len(chunk)) + chunk


@pytest.fixture
def env(tmp_path, monkeypatch):
    import app.config as config
    monkeypatch.setattr(config, "ASSET_STORAGE_DIR", tmp_path / "private")
    monkeypatch.setattr(config, "ASSET_DATABASE_PATH", tmp_path / "ver.sqlite3")
    monkeypatch.setattr(config, "ASSET_SIGNING_SECRET", "s" * 48)
    monkeypatch.setattr(config, "asset_api_tokens", lambda: {"token-user-a": "user-a"})
    assert client.post("/v1/workspaces", headers=auth(), json={"workspace_id": "ver-ws"}).status_code == 201
    monkeypatch.setattr(config, "ASSET_REQUIRE_RIGHTS_CONFIRMATION", True)
    return tmp_path


def new_image(**fields):
    data = {"workspace_id": "ver-ws", **{k: str(v).lower() for k, v in fields.items()}}
    return client.post("/v1/assets/images", headers=auth(), data=data, files={"file": ("a.png", png(), "image/png")})


def add_version(asset_id, shade=200, **fields):
    data = {k: str(v).lower() for k, v in fields.items()}
    return client.post(f"/v1/assets/{asset_id}/versions", headers=auth(), data=data, files={"file": ("b.png", png(shade), "image/png")})


def versions(asset_id):
    return client.get(f"/v1/assets/{asset_id}/versions", headers=auth()).json()["items"]


def test_a_new_image_version_without_the_declaration_is_refused_and_creates_no_version(env):
    aid = new_image(rights_confirmed=True).json()["asset_id"]
    before = len(versions(aid))
    for fields in ({}, {"rights_confirmed": False}):
        res = add_version(aid, **fields)
        assert res.status_code == 422, res.text
        assert res.json()["detail"]["code"] == "RIGHTS_CONFIRMATION_REQUIRED"
    assert len(versions(aid)) == before


def test_a_person_in_a_new_version_needs_the_consent_too(env):
    aid = new_image(rights_confirmed=True).json()["asset_id"]
    res = add_version(aid, rights_confirmed=True, depicts_person=True)
    assert res.status_code == 422 and res.json()["detail"]["code"] == "LIKENESS_CONSENT_REQUIRED"


def test_a_declared_new_version_is_stored_and_the_declaration_is_in_its_provenance(env):
    aid = new_image(rights_confirmed=True).json()["asset_id"]
    res = add_version(aid, rights_confirmed=True)
    assert res.status_code == 201, res.text
    assert len(versions(aid)) == 2
    events = client.get(f"/v1/assets/{aid}/provenance", headers=auth()).json()["items"]
    created = [e for e in events if e["event_type"] == "asset.version_created"]
    assert len(created) == 1 and created[0]["details"]["rights"] == {"rights_confirmed": True, "depicts_person": False, "likeness_consent": False}


def test_legacy_mode_still_accepts_an_undeclared_image_version(env, monkeypatch):
    import app.config as config
    aid = new_image(rights_confirmed=True).json()["asset_id"]
    monkeypatch.setattr(config, "ASSET_REQUIRE_RIGHTS_CONFIRMATION", False)
    assert add_version(aid).status_code == 201


def test_a_3d_model_version_needs_no_declaration(env):
    res = client.post("/v1/assets", headers=auth(), data={"workspace_id": "ver-ws"}, files={"file": ("m.glb", glb(), "model/gltf-binary")})
    assert res.status_code == 201, res.text
    mid = res.json()["asset_id"]
    v = client.post(f"/v1/assets/{mid}/versions", headers=auth(), files={"file": ("m2.glb", glb(), "model/gltf-binary")})
    assert v.status_code == 201, v.text


def test_the_asset_and_its_rights_record_are_written_in_one_transaction(env, monkeypatch):
    """If the record cannot be written, the upload fails as a whole: no asset row and no stored file."""
    import sqlite3
    import app.legal as legal

    def boom():
        raise RuntimeError("injected failure while writing the rights record")
    monkeypatch.setattr(legal, "current_versions", boom)
    res = new_image(rights_confirmed=True)
    assert res.status_code >= 500, res.text
    db = sqlite3.connect(env / "ver.sqlite3")
    try:
        assert db.execute("SELECT COUNT(*) FROM assets").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM upload_rights_confirmations").fetchone()[0] == 0
    finally:
        db.close()
    root = env / "private"
    assert not root.exists() or list(root.iterdir()) == []
