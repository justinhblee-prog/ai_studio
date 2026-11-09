"""L-04: rights / likeness declaration on image upload, recorded in asset provenance."""
import io
import json
import struct

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def auth(token="token-user-a"):
    return {"Authorization": f"Bearer {token}"}


def png():
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (24, 16), (10, 120, 200)).save(buf, format="PNG")
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
    monkeypatch.setattr(config, "ASSET_DATABASE_PATH", tmp_path / "rights.sqlite3")
    monkeypatch.setattr(config, "ASSET_SIGNING_SECRET", "s" * 48)
    monkeypatch.setattr(config, "asset_api_tokens", lambda: {"token-user-a": "user-a"})
    assert client.post("/v1/workspaces", headers=auth(), json={"workspace_id": "rights-ws"}).status_code == 201
    return tmp_path


def upload_image(**fields):
    data = {"workspace_id": "rights-ws", **{k: str(v).lower() for k, v in fields.items()}}
    return client.post("/v1/assets/images", headers=auth(), data=data, files={"file": ("a.png", png(), "image/png")})


def uploaded_details(asset_id):
    items = client.get(f"/v1/assets/{asset_id}/provenance", headers=auth()).json()["items"]
    return [i["details"] for i in items if i["event_type"] == "asset.uploaded"]


def stored_files(env):
    root = env / "private"
    return sorted(p.name for p in root.iterdir()) if root.exists() else []


def test_legacy_mode_keeps_old_clients_working_and_the_old_provenance_format(env):
    res = upload_image()
    assert res.status_code == 201, res.text
    assert uploaded_details(res.json()["asset_id"]) == [{"source": "upload"}]


def test_declaration_is_recorded_in_provenance_even_when_not_enforced(env):
    res = upload_image(rights_confirmed=True, depicts_person=True, likeness_consent=True)
    assert res.status_code == 201, res.text
    assert uploaded_details(res.json()["asset_id"]) == [
        {"source": "upload", "rights": {"rights_confirmed": True, "depicts_person": True, "likeness_consent": True}}]
    res = upload_image(rights_confirmed=True)
    assert uploaded_details(res.json()["asset_id"]) == [
        {"source": "upload", "rights": {"rights_confirmed": True, "depicts_person": False, "likeness_consent": False}}]


def test_enforcement_rejects_uploads_without_a_rights_declaration_and_stores_nothing(env, monkeypatch):
    import app.config as config
    monkeypatch.setattr(config, "ASSET_REQUIRE_RIGHTS_CONFIRMATION", True)
    for fields in ({}, {"rights_confirmed": False}, {"depicts_person": False}):
        res = upload_image(**fields)
        assert res.status_code == 422 and res.json()["detail"]["code"] == "RIGHTS_CONFIRMATION_REQUIRED", (fields, res.text)
    assert stored_files(env) == [], "a rejected upload must not leave a file behind"
    assert client.get("/v1/assets?workspace_id=rights-ws", headers=auth()).json()["items"] == []


def test_enforcement_requires_likeness_consent_only_when_a_person_is_shown(env, monkeypatch):
    import app.config as config
    monkeypatch.setattr(config, "ASSET_REQUIRE_RIGHTS_CONFIRMATION", True)
    res = upload_image(rights_confirmed=True, depicts_person=True)
    assert res.status_code == 422 and res.json()["detail"]["code"] == "LIKENESS_CONSENT_REQUIRED", res.text
    res = upload_image(rights_confirmed=True, depicts_person=True, likeness_consent=True)
    assert res.status_code == 201, res.text
    assert uploaded_details(res.json()["asset_id"])[0]["rights"] == {"rights_confirmed": True, "depicts_person": True, "likeness_consent": True}
    res = upload_image(rights_confirmed=True, depicts_person=False)  # product-only image: no likeness consent needed
    assert res.status_code == 201, res.text


def test_enforcement_applies_to_images_only(env, monkeypatch):
    import app.config as config
    monkeypatch.setattr(config, "ASSET_REQUIRE_RIGHTS_CONFIRMATION", True)
    res = client.post("/v1/assets", headers=auth(), data={"workspace_id": "rights-ws"},
                      files={"file": ("m.glb", glb(), "application/octet-stream")})
    assert res.status_code == 201, res.text
    assert uploaded_details(res.json()["asset_id"]) == [{"source": "upload"}]


def test_rights_flag_is_off_unless_explicitly_enabled():
    import app.config as config
    for value, expected in ((None, False), ("", False), ("false", False), ("0", False), ("no", False), ("maybe", False),
                            ("true", True), ("1", True), ("YES", True), (" on ", True)):
        assert config.env_flag(value) is expected, value


def test_rights_flag_is_wired_to_its_environment_variable():
    import os
    import subprocess
    import sys

    def read(value):
        env = {k: v for k, v in os.environ.items() if k != "ASSET_REQUIRE_RIGHTS_CONFIRMATION"}
        if value is not None:
            env["ASSET_REQUIRE_RIGHTS_CONFIRMATION"] = value
        out = subprocess.run([sys.executable, "-I", "-c", "import sys; sys.path.insert(0, '.'); import app.config as c; print(c.ASSET_REQUIRE_RIGHTS_CONFIRMATION)"],
                             capture_output=True, text=True, env=env, check=True)
        return out.stdout.strip()
    assert read(None) == "True" and read("true") == "True"  # required unless explicitly switched off (D2)
    assert read("0") == "False" and read("false") == "False" and read("off") == "False"
    assert read("garbage") == "True" and read("") == "True"  # anything but an explicit off keeps it required


def test_assets_uploaded_before_enforcement_are_not_blocked_retroactively(env, monkeypatch):
    """Enforcement applies to new uploads only; an existing asset without a declaration stays usable and listable."""
    import app.config as config
    old = upload_image()  # uploaded while enforcement was off, no declaration
    assert old.status_code == 201
    asset_id = old.json()["asset_id"]
    monkeypatch.setattr(config, "ASSET_REQUIRE_RIGHTS_CONFIRMATION", True)
    assert upload_image().status_code == 422  # a new upload is now refused...
    listed = client.get("/v1/assets?workspace_id=rights-ws&kind=image", headers=auth()).json()["items"]
    assert [a["asset_id"] for a in listed] == [asset_id]  # ...but the old asset is untouched
    assert client.get(f"/v1/assets/{asset_id}", headers=auth()).status_code == 200
    draft = client.post("/v1/photo-drafts", headers=auth(), json={
        "workspace_id": "rights-ws", "source_asset_id": asset_id, "operation": "ENHANCE", "preserve_identity": True,
        "preserve_product_geometry": True, "preserve_text_and_logo": True, "output_format": "PNG", "output_count": 1})
    assert draft.status_code == 201, draft.text  # usable as a source without any declaration on record
    assert uploaded_details(asset_id) == [{"source": "upload"}]


def test_declaration_record_survives_deleting_the_asset(env):
    """The declaration lives in asset_provenance, which keeps its rows when the asset is soft-deleted."""
    import sqlite3

    import app.config as config
    res = upload_image(rights_confirmed=True, depicts_person=True, likeness_consent=True)
    asset_id = res.json()["asset_id"]
    assert client.delete(f"/v1/assets/{asset_id}", headers=auth()).status_code == 204
    db = sqlite3.connect(config.ASSET_DATABASE_PATH)
    rows = db.execute("SELECT event_type, details_json FROM asset_provenance WHERE asset_id=? ORDER BY created_at, provenance_id", (asset_id,)).fetchall()
    kinds = [r[0] for r in rows]
    assert kinds == ["asset.uploaded", "asset.deleted"], kinds
    assert json.loads(rows[0][1])["rights"] == {"rights_confirmed": True, "depicts_person": True, "likeness_consent": True}
    assert db.execute("SELECT deleted_at IS NOT NULL FROM assets WHERE asset_id=?", (asset_id,)).fetchone()[0] == 1
