import json
import struct
import time
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

@pytest.fixture
def asset_env(tmp_path, monkeypatch):
    import app.config as config
    monkeypatch.setattr(config, "ASSET_STORAGE_DIR", tmp_path / "private")
    monkeypatch.setattr(config, "ASSET_DATABASE_PATH", tmp_path / "assets.sqlite3")
    monkeypatch.setattr(config, "ASSET_MAX_UPLOAD_BYTES", 1024 * 1024)
    monkeypatch.setattr(config, "ASSET_PREVIEW_TTL_SECONDS", 120)
    monkeypatch.setattr(config, "ASSET_SIGNING_SECRET", "s" * 48)
    monkeypatch.setattr(config, "asset_api_tokens", lambda: {"token-user-a": "user-a", "token-user-b": "user-b"})
    created = client.post("/v1/workspaces", headers=auth(), json={"workspace_id": "ws-a"})
    assert created.status_code == 201, created.text
    return tmp_path

def auth(token="token-user-a"):
    return {"Authorization": f"Bearer {token}"}

def glb_bytes():
    doc = json.dumps({"asset": {"version": "2.0"}}, separators=(",", ":")).encode()
    doc += b" " * ((4 - len(doc) % 4) % 4)
    chunk = struct.pack("<II", len(doc), 0x4E4F534A) + doc
    return b"glTF" + struct.pack("<II", 2, 12 + len(chunk)) + chunk

def upload(headers=None, name="model.glb", data=None):
    return client.post("/v1/assets", headers=auth() if headers is None else headers, data={"workspace_id":"ws-a"}, files={"file":(name, data or glb_bytes(), "application/octet-stream")})

def test_asset_upload_requires_auth(asset_env):
    assert upload(headers={}).status_code == 401

def test_upload_metadata_preview_and_delete(asset_env):
    created = upload()
    assert created.status_code == 201, created.text
    asset = created.json()
    assert asset["media_type"] == "model/gltf-binary"
    assert asset["size_bytes"] == len(glb_bytes())
    assert asset["owner_id"] == "user-a"
    assert "storage_key" not in asset
    assert (asset_env / "private" / f"{asset['asset_id']}.glb").exists()

    listed = client.get("/v1/assets?workspace_id=ws-a", headers=auth())
    assert listed.status_code == 200 and len(listed.json()["items"]) == 1
    assert client.get(f"/v1/assets/{asset['asset_id']}", headers=auth("token-user-b")).status_code == 404

    link = client.post(f"/v1/assets/{asset['asset_id']}/preview-url", headers=auth()).json()
    from urllib.parse import urlsplit
    path = urlsplit(link["url"])
    preview = client.get(path.path + "?" + path.query)
    assert preview.status_code == 200
    assert preview.content == glb_bytes()
    assert preview.headers["cache-control"] == "private, no-store"

    assert client.delete(f"/v1/assets/{asset['asset_id']}", headers=auth()).status_code == 204
    assert client.get(f"/v1/assets/{asset['asset_id']}", headers=auth()).status_code == 404
    assert not (asset_env / "private" / f"{asset['asset_id']}.glb").exists()

def test_asset_validation_rejects_bad_glb(asset_env):
    response = upload(data=b"not a glb")
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "ASSET_SIGNATURE_INVALID"

def test_workspace_list_isolation(asset_env):
    upload()
    created = client.post("/v1/workspaces", headers=auth(), json={"workspace_id": "ws-b"})
    assert created.status_code == 201
    response = client.get("/v1/assets?workspace_id=ws-b", headers=auth())
    assert response.status_code == 200 and response.json()["items"] == []

def test_preview_signature_tamper_rejected(asset_env):
    asset = upload().json()
    link = client.post(f"/v1/assets/{asset['asset_id']}/preview-url", headers=auth()).json()["url"]
    from urllib.parse import urlsplit, parse_qs
    parts = urlsplit(link); q = parse_qs(parts.query)
    response = client.get(f"{parts.path}?expires={q['expires'][0]}&signature={'0'*64}")
    assert response.status_code == 403


def test_invalid_bearer_token_rejected(asset_env):
    assert upload(headers=auth("unknown-token")).status_code == 401

def test_upload_size_limit_enforced(asset_env, monkeypatch):
    import app.config as config
    monkeypatch.setattr(config, "ASSET_MAX_UPLOAD_BYTES", 16)
    response = upload()
    assert response.status_code == 413

def test_expired_preview_url_rejected(asset_env):
    asset = upload().json()
    link = client.post(f"/v1/assets/{asset['asset_id']}/preview-url", headers=auth()).json()["url"]
    from urllib.parse import urlsplit
    from app.assets.routes import _signature
    parts = urlsplit(link)
    expired = int(time.time()) - 10
    response = client.get(f"{parts.path}?expires={expired}&signature={_signature(asset['asset_id'], expired)}")
    assert response.status_code == 403


def test_workspace_member_roles_control_asset_access(asset_env):
    created = upload().json()
    asset_id = created["asset_id"]
    add = client.post("/v1/workspaces/ws-a/members", headers=auth(), json={"user_id":"user-b", "role":"viewer"})
    assert add.status_code == 201
    assert client.get("/v1/assets?workspace_id=ws-a", headers=auth("token-user-b")).json()["items"]
    assert client.delete(f"/v1/assets/{asset_id}", headers=auth("token-user-b")).status_code == 403
    assert upload(headers=auth("token-user-b")).status_code == 403

def test_workspace_admin_can_add_editor(asset_env):
    assert client.post("/v1/workspaces/ws-a/members", headers=auth(), json={"user_id":"user-b", "role":"admin"}).status_code == 201
    assert client.post("/v1/workspaces/ws-a/members", headers=auth("token-user-b"), json={"user_id":"user-c", "role":"editor"}).status_code == 201

def test_workspace_non_admin_cannot_add_members(asset_env):
    assert client.post("/v1/workspaces/ws-a/members", headers=auth(), json={"user_id":"user-b", "role":"viewer"}).status_code == 201
    response = client.post("/v1/workspaces/ws-a/members", headers=auth("token-user-b"), json={"user_id":"user-c", "role":"editor"})
    assert response.status_code == 403

def test_workspace_id_conflict_and_listing(asset_env):
    assert client.post("/v1/workspaces", headers=auth(), json={"workspace_id":"ws-a"}).status_code == 409
    listed = client.get("/v1/workspaces", headers=auth())
    assert listed.status_code == 200 and listed.json()["items"][0]["role"] == "owner"


def test_legacy_assets_are_bootstrapped_into_workspace_membership(tmp_path, monkeypatch):
    import sqlite3
    import app.config as config
    from app.assets.store import initialize, workspace_role
    db_path = tmp_path / "legacy.sqlite3"
    monkeypatch.setattr(config, "ASSET_DATABASE_PATH", db_path)
    with sqlite3.connect(db_path) as db:
        db.execute("""CREATE TABLE assets (
            asset_id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
            original_filename TEXT NOT NULL, storage_key TEXT NOT NULL UNIQUE,
            media_type TEXT NOT NULL, size_bytes INTEGER NOT NULL, checksum_sha256 TEXT NOT NULL,
            gltf_version TEXT NOT NULL, embedded_binary INTEGER NOT NULL, created_at TEXT NOT NULL,
            deleted_at TEXT)""")
        db.execute("INSERT INTO assets VALUES(?,?,?,?,?,?,?,?,?,?,?,NULL)", ("a1","owner-a","legacy-ws","a.glb","a.glb","model/gltf-binary",20,"sum","2.0",1,"2026-11-01T00:00:00+00:00"))
        db.execute("INSERT INTO assets VALUES(?,?,?,?,?,?,?,?,?,?,?,NULL)", ("a2","editor-b","legacy-ws","b.glb","b.glb","model/gltf-binary",20,"sum2","2.0",1,"2026-11-01T00:01:00+00:00"))
    initialize()
    assert workspace_role("legacy-ws", "owner-a") == "owner"
    assert workspace_role("legacy-ws", "editor-b") == "editor"
    with sqlite3.connect(db_path) as db:
        asset_columns = {row[1] for row in db.execute("PRAGMA table_info(assets)")}
        version_columns = {row[1] for row in db.execute("PRAGMA table_info(asset_versions)")}
        assert {"storage_backend", "storage_bucket"} <= asset_columns
        assert {"storage_backend", "storage_bucket"} <= version_columns
        legacy_locator = db.execute("SELECT storage_backend,storage_bucket FROM assets WHERE asset_id='a1'").fetchone()
        assert legacy_locator == ("local", "private_assets")


def test_viewer_can_request_signed_preview(asset_env):
    asset = upload().json()
    assert client.post("/v1/workspaces/ws-a/members", headers=auth(), json={"user_id":"user-b", "role":"viewer"}).status_code == 201
    response = client.post(f"/v1/assets/{asset['asset_id']}/preview-url", headers=auth("token-user-b"))
    assert response.status_code == 200


def test_workspace_asset_integrity_audit_detects_corruption_and_missing_files(asset_env):
    first = upload().json()
    second = upload().json()
    root = asset_env / "private"
    (root / f"{first['asset_id']}.glb").write_bytes(b"corrupted")
    (root / f"{second['asset_id']}.glb").unlink()
    response = client.get("/v1/assets/integrity?workspace_id=ws-a", headers=auth())
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["total"] == 2 and result["checked"] == 2
    assert result["counts"]["missing"] == 1
    assert result["counts"]["size_mismatch"] == 1
    assert all(set(item) == {"asset_id", "status"} for item in result["items"])
    assert "storage_key" not in response.text and str(root) not in response.text


def test_workspace_asset_integrity_audit_is_workspace_scoped_and_paginated(asset_env):
    upload()
    upload()
    assert client.post("/v1/workspaces/ws-a/members", headers=auth(), json={"user_id":"user-b", "role":"viewer"}).status_code == 201
    page = client.get("/v1/assets/integrity?workspace_id=ws-a&limit=1&offset=1", headers=auth("token-user-b"))
    assert page.status_code == 200
    assert page.json()["total"] == 2 and page.json()["checked"] == 1
    assert page.json()["counts"]["ok"] == 1
    assert client.get("/v1/assets/integrity?workspace_id=ws-missing", headers=auth()).status_code == 404


def test_workspace_asset_integrity_audit_detects_same_size_checksum_mismatch(asset_env):
    asset = upload().json()
    path = asset_env / "private" / f"{asset['asset_id']}.glb"
    original = path.read_bytes()
    path.write_bytes(bytes([original[0] ^ 1]) + original[1:])
    response = client.get("/v1/assets/integrity?workspace_id=ws-a", headers=auth())
    assert response.status_code == 200
    assert response.json()["counts"]["checksum_mismatch"] == 1


def test_asset_version_baseline_and_provenance_are_created_on_upload(asset_env):
    asset = upload().json()
    versions = client.get(f"/v1/assets/{asset['asset_id']}/versions", headers=auth())
    assert versions.status_code == 200
    assert len(versions.json()["items"]) == 1
    version = versions.json()["items"][0]
    assert version["version_number"] == 1
    assert version["checksum_sha256"] == asset["checksum_sha256"]
    assert "storage_key" not in version
    history = client.get(f"/v1/assets/{asset['asset_id']}/provenance", headers=auth())
    assert history.status_code == 200
    assert history.json()["items"][0]["event_type"] == "asset.uploaded"
    assert history.json()["items"][0]["details"] == {"source": "upload"}


def test_asset_relations_are_workspace_scoped_and_audited(asset_env):
    first = upload().json()
    second = upload().json()
    response = client.post(f"/v1/assets/{first['asset_id']}/relations", headers=auth(),
                           json={"target_asset_id": second["asset_id"], "relation_type": "variant_of"})
    assert response.status_code == 201, response.text
    relation = response.json()
    assert relation["source_asset_id"] == first["asset_id"]
    assert relation["target_asset_id"] == second["asset_id"]
    listed = client.get(f"/v1/assets/{second['asset_id']}/relations", headers=auth())
    assert listed.status_code == 200 and listed.json()["items"][0]["relation_id"] == relation["relation_id"]
    provenance = client.get(f"/v1/assets/{first['asset_id']}/provenance", headers=auth())
    assert provenance.json()["items"][0]["event_type"] == "asset.relation_created"
    target_history = client.get(f"/v1/assets/{second['asset_id']}/provenance", headers=auth())
    assert target_history.json()["items"][0]["event_type"] == "asset.relation_received"
    duplicate = client.post(f"/v1/assets/{first['asset_id']}/relations", headers=auth(),
                            json={"target_asset_id": second["asset_id"], "relation_type": "variant_of"})
    assert duplicate.status_code == 409


def test_asset_relation_rejects_self_unknown_type_and_cross_workspace(asset_env):
    asset = upload().json()
    self_link = client.post(f"/v1/assets/{asset['asset_id']}/relations", headers=auth(),
                            json={"target_asset_id": asset["asset_id"], "relation_type": "variant_of"})
    assert self_link.status_code == 422
    bad_type = client.post(f"/v1/assets/{asset['asset_id']}/relations", headers=auth(),
                           json={"target_asset_id": "ast_missing", "relation_type": "made_up"})
    assert bad_type.status_code == 422
    client.post("/v1/workspaces", headers=auth(), json={"workspace_id": "ws-other"})
    other = client.post("/v1/assets", headers=auth(), data={"workspace_id": "ws-other"},
                        files={"file": ("other.glb", glb_bytes(), "application/octet-stream")}).json()
    cross = client.post(f"/v1/assets/{asset['asset_id']}/relations", headers=auth(),
                        json={"target_asset_id": other["asset_id"], "relation_type": "paired_with"})
    assert cross.status_code == 404


def test_asset_version_and_provenance_reads_enforce_workspace_membership(asset_env):
    asset = upload().json()
    assert client.get(f"/v1/assets/{asset['asset_id']}/versions", headers=auth("token-user-b")).status_code == 404
    assert client.get(f"/v1/assets/{asset['asset_id']}/provenance", headers=auth("token-user-b")).status_code == 404


def test_asset_version_upload_promotes_current_and_preserves_immutable_history(asset_env):
    import hashlib
    asset = upload().json()
    original_path = asset_env / "private" / f"{asset['asset_id']}.glb"
    original_bytes = original_path.read_bytes()
    doc = json.dumps({"asset": {"version": "2.0"}, "extras": {"revision": 2}}, separators=(",", ":")).encode()
    doc += b" " * ((4 - len(doc) % 4) % 4)
    chunk = struct.pack("<II", len(doc), 0x4E4F534A) + doc
    replacement = b"glTF" + struct.pack("<II", 2, 12 + len(chunk)) + chunk
    response = client.post(f"/v1/assets/{asset['asset_id']}/versions", headers=auth(),
                           files={"file": ("revision-2.glb", replacement, "application/octet-stream")})
    assert response.status_code == 201, response.text
    promoted = response.json()
    assert promoted["version_number"] == 2
    assert promoted["checksum_sha256"] == hashlib.sha256(replacement).hexdigest()
    assert original_path.exists() and original_path.read_bytes() == original_bytes
    versions = client.get(f"/v1/assets/{asset['asset_id']}/versions", headers=auth()).json()["items"]
    assert [item["version_number"] for item in versions] == [2, 1]
    assert all("storage_key" not in item for item in versions)
    events = client.get(f"/v1/assets/{asset['asset_id']}/provenance", headers=auth()).json()["items"]
    assert events[0]["event_type"] == "asset.version_created"
    assert events[0]["details"]["previous_version"] == 1
    assert client.delete(f"/v1/assets/{asset['asset_id']}", headers=auth()).status_code == 204
    assert not original_path.exists()
    assert not (asset_env / "private" / f"{asset['asset_id']}_{promoted['version_id']}.glb").exists()


def test_asset_version_upload_requires_editor_role_and_valid_glb(asset_env):
    asset = upload().json()
    client.post("/v1/workspaces/ws-a/members", headers=auth(), json={"user_id": "user-b", "role": "viewer"})
    denied = client.post(f"/v1/assets/{asset['asset_id']}/versions", headers=auth("token-user-b"),
                         files={"file": ("new.glb", glb_bytes(), "application/octet-stream")})
    assert denied.status_code == 403
    invalid = client.post(f"/v1/assets/{asset['asset_id']}/versions", headers=auth(),
                          files={"file": ("new.glb", b"bad", "application/octet-stream")})
    assert invalid.status_code == 422
    versions = client.get(f"/v1/assets/{asset['asset_id']}/versions", headers=auth()).json()["items"]
    assert len(versions) == 1


def test_asset_version_restore_creates_new_verified_immutable_version(asset_env):
    import hashlib
    asset = upload().json()
    original = glb_bytes()
    replacement_doc = json.dumps({"asset": {"version": "2.0"}, "extras": {"revision": 2}}, separators=(",", ":")).encode()
    replacement_doc += b" " * ((4 - len(replacement_doc) % 4) % 4)
    chunk = struct.pack("<II", len(replacement_doc), 0x4E4F534A) + replacement_doc
    replacement = b"glTF" + struct.pack("<II", 2, 12 + len(chunk)) + chunk
    created = client.post(f"/v1/assets/{asset['asset_id']}/versions", headers=auth(),
                          files={"file": ("revision-2.glb", replacement, "application/octet-stream")})
    assert created.status_code == 201, created.text
    v2 = created.json()
    old_v1_path = asset_env / "private" / f"{asset['asset_id']}.glb"
    v1_history = client.get(f"/v1/assets/{asset['asset_id']}/versions", headers=auth()).json()["items"][-1]
    restored = client.post(f"/v1/assets/{asset['asset_id']}/versions/{v1_history['version_id']}/restore",
                           headers=auth())
    assert restored.status_code == 201, restored.text
    result = restored.json()
    assert result["version_number"] == 3
    assert result["restored_from_version_id"] == v1_history["version_id"]
    assert result["checksum_sha256"] == hashlib.sha256(original).hexdigest()
    assert old_v1_path.exists() and old_v1_path.read_bytes() == original
    assert (asset_env / "private" / f"{asset['asset_id']}_{v2['version_id']}.glb").read_bytes() == replacement
    current = client.get(f"/v1/assets/{asset['asset_id']}", headers=auth()).json()
    assert current["checksum_sha256"] == result["checksum_sha256"]
    versions = client.get(f"/v1/assets/{asset['asset_id']}/versions", headers=auth()).json()["items"]
    assert [item["version_number"] for item in versions] == [3, 2, 1]
    assert [item["is_current"] for item in versions] == [True, False, False]
    history = client.get(f"/v1/assets/{asset['asset_id']}/provenance", headers=auth()).json()["items"]
    assert history[0]["event_type"] == "asset.version_restored"
    assert history[0]["details"]["restored_from_version_number"] == 1


def test_asset_version_restore_rejects_missing_or_corrupt_history_without_mutation(asset_env):
    asset = upload().json()
    versions = client.get(f"/v1/assets/{asset['asset_id']}/versions", headers=auth()).json()["items"]
    source = versions[0]
    source_path = asset_env / "private" / f"{asset['asset_id']}.glb"
    source_path.write_bytes(b"tampered")
    response = client.post(f"/v1/assets/{asset['asset_id']}/versions/{source['version_id']}/restore", headers=auth())
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "ASSET_VERSION_INTEGRITY_FAILED"
    assert len(client.get(f"/v1/assets/{asset['asset_id']}/versions", headers=auth()).json()["items"]) == 1
    current = client.get(f"/v1/assets/{asset['asset_id']}", headers=auth()).json()
    assert current["checksum_sha256"] == source["checksum_sha256"]
    assert current["size_bytes"] == source["size_bytes"]
    source_path.write_bytes(glb_bytes())
    source_path.unlink()
    missing = client.post(f"/v1/assets/{asset['asset_id']}/versions/{source['version_id']}/restore", headers=auth())
    assert missing.status_code == 409
    assert len(client.get(f"/v1/assets/{asset['asset_id']}/versions", headers=auth()).json()["items"]) == 1


def test_asset_version_restore_enforces_editor_role_and_hides_unknown_versions(asset_env):
    asset = upload().json()
    version = client.get(f"/v1/assets/{asset['asset_id']}/versions", headers=auth()).json()["items"][0]
    assert client.post(f"/v1/workspaces/ws-a/members", headers=auth(),
                       json={"user_id": "user-b", "role": "viewer"}).status_code == 201
    denied = client.post(f"/v1/assets/{asset['asset_id']}/versions/{version['version_id']}/restore",
                         headers=auth("token-user-b"))
    assert denied.status_code == 403
    missing = client.post(f"/v1/assets/{asset['asset_id']}/versions/av_unknown/restore", headers=auth())
    assert missing.status_code == 404


def image_bytes(color=(20, 80, 140), image_format="PNG"):
    from io import BytesIO
    from PIL import Image
    output = BytesIO()
    Image.new("RGB", (32, 24), color).save(output, format=image_format)
    return output.getvalue()


def upload_image(name="source.png", data=None, headers=None):
    return client.post("/v1/assets/images", headers=auth() if headers is None else headers,
                       data={"workspace_id": "ws-a"},
                       files={"file": (name, data or image_bytes(), "application/octet-stream")})


def test_image_asset_upload_private_preview_and_kind_filtered_listing(asset_env):
    created = upload_image()
    assert created.status_code == 201, created.text
    asset = created.json()
    assert asset["asset_kind"] == "image"
    assert asset["media_type"] == "image/png"
    assert asset["gltf_version"] is None
    assert asset["embedded_binary"] is False
    assert (asset_env / "private" / f"{asset['asset_id']}.png").read_bytes() == image_bytes()
    assert client.get("/v1/assets?workspace_id=ws-a&kind=image", headers=auth()).json()["items"][0]["asset_id"] == asset["asset_id"]
    assert client.get("/v1/assets?workspace_id=ws-a&kind=model", headers=auth()).json()["items"] == []
    link = client.post(f"/v1/assets/{asset['asset_id']}/preview-url", headers=auth()).json()["url"]
    from urllib.parse import urlsplit
    parts = urlsplit(link)
    preview = client.get(parts.path + "?" + parts.query)
    assert preview.status_code == 200
    assert preview.headers["content-type"] == "image/png"
    assert preview.content == image_bytes()


def test_image_asset_validation_rejects_extension_spoof_and_malformed_content(asset_env):
    spoofed = upload_image(name="spoof.png", data=image_bytes(image_format="JPEG"))
    assert spoofed.status_code == 422
    assert spoofed.json()["detail"]["code"] == "IMAGE_EXTENSION_MISMATCH"
    invalid = upload_image(data=b"not really a png")
    assert invalid.status_code == 422
    assert invalid.json()["detail"]["code"] == "IMAGE_DECODE_FAILED"
    assert client.get("/v1/assets?workspace_id=ws-a&kind=image", headers=auth()).json()["items"] == []


def test_image_asset_versions_require_same_kind_and_support_verified_restore(asset_env):
    first_bytes = image_bytes((200, 20, 40))
    asset = upload_image(data=first_bytes).json()
    second_bytes = image_bytes((10, 180, 70))
    updated = client.post(f"/v1/assets/{asset['asset_id']}/versions", headers=auth(),
                          files={"file": ("second.png", second_bytes, "application/octet-stream")})
    assert updated.status_code == 201, updated.text
    v2 = updated.json()
    wrong_kind = client.post(f"/v1/assets/{asset['asset_id']}/versions", headers=auth(),
                             files={"file": ("model.glb", glb_bytes(), "application/octet-stream")})
    assert wrong_kind.status_code == 422
    versions = client.get(f"/v1/assets/{asset['asset_id']}/versions", headers=auth()).json()["items"]
    v1 = versions[-1]
    restored = client.post(f"/v1/assets/{asset['asset_id']}/versions/{v1['version_id']}/restore", headers=auth())
    assert restored.status_code == 201, restored.text
    assert restored.json()["asset_kind"] == "image"
    assert restored.json()["media_type"] == "image/png"
    assert restored.json()["version_number"] == 3
    assert restored.json()["checksum_sha256"] == __import__("hashlib").sha256(first_bytes).hexdigest()
    assert (asset_env / "private" / f"{asset['asset_id']}.png").read_bytes() == first_bytes
    assert (asset_env / "private" / f"{asset['asset_id']}_{v2['version_id']}.png").read_bytes() == second_bytes
    assert client.delete(f"/v1/assets/{asset['asset_id']}", headers=auth()).status_code == 204
    assert not (asset_env / "private" / f"{asset['asset_id']}.png").exists()
    assert not (asset_env / "private" / f"{asset['asset_id']}_{v2['version_id']}.png").exists()


def test_image_upload_requires_editor_role(asset_env):
    client.post("/v1/workspaces/ws-a/members", headers=auth(),
                json={"user_id": "user-b", "role": "viewer"})
    denied = upload_image(headers=auth("token-user-b"))
    assert denied.status_code == 403


@pytest.mark.parametrize(("filename", "image_format", "media_type"), [
    ("source.jpg", "JPEG", "image/jpeg"),
    ("source.webp", "WEBP", "image/webp"),
])
def test_image_upload_accepts_supported_jpeg_and_webp(filename, image_format, media_type, asset_env):
    response = upload_image(name=filename, data=image_bytes(image_format=image_format))
    assert response.status_code == 201, response.text
    assert response.json()["media_type"] == media_type
    assert response.json()["asset_kind"] == "image"


def test_image_upload_rejects_animated_gif(asset_env):
    from io import BytesIO
    from PIL import Image
    output = BytesIO()
    first = Image.new("RGB", (8, 8), (255, 0, 0))
    second = Image.new("RGB", (8, 8), (0, 0, 255))
    first.save(output, format="GIF", save_all=True, append_images=[second], duration=100, loop=0)
    response = upload_image(name="animated.gif", data=output.getvalue())
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "IMAGE_FORMAT_UNSUPPORTED"


def photo_draft_payload(source_asset_id, **overrides):
    payload = {
        "workspace_id": "ws-a",
        "source_asset_id": source_asset_id,
        "operation": "ENHANCE",
        "preserve_identity": True,
        "preserve_product_geometry": True,
        "preserve_text_and_logo": True,
        "output_format": "PNG",
        "output_count": 1,
    }
    payload.update(overrides)
    return payload


def test_photo_draft_create_update_archive_and_append_only_events(asset_env):
    source = upload_image(name="source.png").json()
    mask = upload_image(name="mask.png", data=image_bytes((0, 0, 0))).json()
    reference = upload_image(name="reference.webp", data=image_bytes(image_format="WEBP")).json()
    created = client.post("/v1/photo-drafts", headers=auth(),
                          json=photo_draft_payload(source["asset_id"], mask_asset_id=mask["asset_id"],
                                                   reference_asset_ids=[reference["asset_id"]],
                                                   operation="BACKGROUND", output_count=3))
    assert created.status_code == 201, created.text
    draft = created.json()
    assert draft["status"] == "draft"
    assert draft["input"]["operation"] == "BACKGROUND"
    assert draft["input"]["reference_asset_ids"] == [reference["asset_id"]]
    assert "job_id" not in draft and "output_url" not in draft and "quote_id" not in draft
    listed = client.get("/v1/photo-drafts?workspace_id=ws-a", headers=auth())
    assert listed.status_code == 200 and len(listed.json()["items"]) == 1
    updated_payload = photo_draft_payload(source["asset_id"], operation="LIGHTING", output_format="WEBP",
                                          target_style="soft studio", output_count=2)
    updated = client.put(f"/v1/photo-drafts/{draft['draft_id']}", headers=auth(), json=updated_payload)
    assert updated.status_code == 200, updated.text
    assert updated.json()["input"]["operation"] == "LIGHTING"
    events = client.get(f"/v1/photo-drafts/{draft['draft_id']}/events?workspace_id=ws-a", headers=auth())
    assert [item["event_type"] for item in events.json()["items"]] == ["photo.draft_updated", "photo.draft_created"]
    archived = client.post(f"/v1/photo-drafts/{draft['draft_id']}/archive?workspace_id=ws-a", headers=auth())
    assert archived.status_code == 200 and archived.json()["status"] == "archived"
    assert client.get("/v1/photo-drafts?workspace_id=ws-a", headers=auth()).json()["items"] == []
    archived_list = client.get("/v1/photo-drafts?workspace_id=ws-a&include_archived=true", headers=auth())
    assert len(archived_list.json()["items"]) == 1


def test_photo_draft_requires_active_same_workspace_image_assets(asset_env):
    model = upload().json()
    image = upload_image().json()
    model_source = client.post("/v1/photo-drafts", headers=auth(), json=photo_draft_payload(model["asset_id"]))
    assert model_source.status_code == 422
    assert model_source.json()["detail"]["code"] == "PHOTO_IMAGE_ASSET_REQUIRED"
    client.post("/v1/workspaces", headers=auth(), json={"workspace_id": "ws-other"})
    other_image = client.post("/v1/assets/images", headers=auth(), data={"workspace_id": "ws-other"},
                              files={"file": ("other.png", image_bytes(), "application/octet-stream")}).json()
    cross_workspace = client.post("/v1/photo-drafts", headers=auth(),
                                  json=photo_draft_payload(image["asset_id"], reference_asset_ids=[other_image["asset_id"]]))
    assert cross_workspace.status_code == 422
    duplicate = client.post("/v1/photo-drafts", headers=auth(),
                            json=photo_draft_payload(image["asset_id"], reference_asset_ids=[image["asset_id"]]))
    assert duplicate.status_code == 422


def test_active_photo_draft_protects_referenced_image_until_archived(asset_env):
    source = upload_image().json()
    draft = client.post("/v1/photo-drafts", headers=auth(), json=photo_draft_payload(source["asset_id"])).json()
    blocked = client.delete(f"/v1/assets/{source['asset_id']}", headers=auth())
    assert blocked.status_code == 409
    assert client.get(f"/v1/assets/{source['asset_id']}", headers=auth()).status_code == 200
    archived = client.post(f"/v1/photo-drafts/{draft['draft_id']}/archive?workspace_id=ws-a", headers=auth())
    assert archived.status_code == 200
    assert client.delete(f"/v1/assets/{source['asset_id']}", headers=auth()).status_code == 204


def test_photo_draft_viewer_can_read_but_cannot_create_or_archive(asset_env):
    source = upload_image().json()
    draft = client.post("/v1/photo-drafts", headers=auth(), json=photo_draft_payload(source["asset_id"])).json()
    client.post("/v1/workspaces/ws-a/members", headers=auth(),
                json={"user_id": "user-b", "role": "viewer"})
    read = client.get(f"/v1/photo-drafts/{draft['draft_id']}?workspace_id=ws-a", headers=auth("token-user-b"))
    assert read.status_code == 200
    create = client.post("/v1/photo-drafts", headers=auth("token-user-b"), json=photo_draft_payload(source["asset_id"]))
    assert create.status_code == 403
    archive = client.post(f"/v1/photo-drafts/{draft['draft_id']}/archive?workspace_id=ws-a", headers=auth("token-user-b"))
    assert archive.status_code == 403


def test_photo_draft_rejects_unknown_fields_and_invalid_operation(asset_env):
    source = upload_image().json()
    extra = client.post("/v1/photo-drafts", headers=auth(),
                        json=photo_draft_payload(source["asset_id"], provider="mock"))
    assert extra.status_code == 422
    invalid = client.post("/v1/photo-drafts", headers=auth(),
                          json=photo_draft_payload(source["asset_id"], operation="TRY_ON"))
    assert invalid.status_code == 422


def lookbook_payload(product_asset_ids, **overrides):
    payload = {
        "workspace_id": "ws-a",
        "title": "Spring campaign",
        "product_asset_ids": product_asset_ids,
        "scene_preset": "minimal studio",
        "output_count": 4,
    }
    payload.update(overrides)
    return payload


def test_lookbook_draft_create_update_archive_and_events(asset_env):
    product_a = upload_image(name="product-a.png").json()
    product_b = upload_image(name="product-b.png", data=image_bytes((30, 90, 140))).json()
    person = upload_image(name="person.png", data=image_bytes((120, 90, 40))).json()
    project = client.post("/v1/projects", headers=auth(), json={"workspace_id": "ws-a", "name": "Spring 2027", "project_type": "campaign"})
    assert project.status_code == 201, project.text
    character = client.post("/v1/workspaces/ws-a/characters", headers=auth(),
                            json={"identity": {"name": "Studio Model"}, "outfits": [], "asset_ids": []})
    assert character.status_code == 201, character.text
    created = client.post("/v1/lookbook-drafts", headers=auth(),
                          json=lookbook_payload([product_a["asset_id"]], person_asset_id=person["asset_id"],
                                                project_id=project.json()["project_id"],
                                                character_id=character.json()["character_id"]))
    assert created.status_code == 201, created.text
    draft = created.json()
    assert draft["status"] == "draft"
    assert draft["input"]["product_asset_ids"] == [product_a["asset_id"]]
    assert "job_id" not in draft and "output_url" not in draft and "quote_id" not in draft
    updated = client.put(f"/v1/lookbook-drafts/{draft['draft_id']}", headers=auth(),
                         json=lookbook_payload([product_a["asset_id"], product_b["asset_id"]],
                                               title="Spring campaign revised", output_count=8))
    assert updated.status_code == 200, updated.text
    assert updated.json()["input"]["product_asset_ids"] == [product_a["asset_id"], product_b["asset_id"]]
    events = client.get(f"/v1/lookbook-drafts/{draft['draft_id']}/events?workspace_id=ws-a", headers=auth())
    assert [item["event_type"] for item in events.json()["items"]] == ["lookbook.draft_updated", "lookbook.draft_created"]
    archived = client.post(f"/v1/lookbook-drafts/{draft['draft_id']}/archive?workspace_id=ws-a", headers=auth())
    assert archived.status_code == 200 and archived.json()["status"] == "archived"
    assert client.get("/v1/lookbook-drafts?workspace_id=ws-a", headers=auth()).json()["items"] == []
    assert len(client.get("/v1/lookbook-drafts?workspace_id=ws-a&include_archived=true", headers=auth()).json()["items"]) == 1


def test_lookbook_draft_validates_images_project_character_and_uniqueness(asset_env):
    product = upload_image().json()
    model = upload().json()
    wrong_media = client.post("/v1/lookbook-drafts", headers=auth(), json=lookbook_payload([model["asset_id"]]))
    assert wrong_media.status_code == 422
    duplicate = client.post("/v1/lookbook-drafts", headers=auth(),
                            json=lookbook_payload([product["asset_id"]], person_asset_id=product["asset_id"]))
    assert duplicate.status_code == 422
    client.post("/v1/workspaces", headers=auth(), json={"workspace_id": "ws-other"})
    other_image = client.post("/v1/assets/images", headers=auth(), data={"workspace_id": "ws-other"},
                              files={"file": ("other.png", image_bytes(), "application/octet-stream")}).json()
    cross_workspace = client.post("/v1/lookbook-drafts", headers=auth(), json=lookbook_payload([other_image["asset_id"]]))
    assert cross_workspace.status_code == 422
    project = client.post("/v1/projects", headers=auth(), json={"workspace_id": "ws-a", "name": "Archived project"}).json()
    archived_project = client.put(f"/v1/projects/{project['project_id']}", headers=auth(),
                                  json={"name": "Archived project", "project_type": "general", "status": "ARCHIVED"})
    assert archived_project.status_code == 200
    inactive_project = client.post("/v1/lookbook-drafts", headers=auth(),
                                    json=lookbook_payload([product["asset_id"]], project_id=project["project_id"]))
    assert inactive_project.status_code == 409


def test_active_lookbook_draft_protects_referenced_images_until_archived(asset_env):
    product = upload_image().json()
    draft = client.post("/v1/lookbook-drafts", headers=auth(), json=lookbook_payload([product["asset_id"]])).json()
    blocked = client.delete(f"/v1/assets/{product['asset_id']}", headers=auth())
    assert blocked.status_code == 409
    archived = client.post(f"/v1/lookbook-drafts/{draft['draft_id']}/archive?workspace_id=ws-a", headers=auth())
    assert archived.status_code == 200
    assert client.delete(f"/v1/assets/{product['asset_id']}", headers=auth()).status_code == 204


def test_lookbook_draft_viewer_read_only_access(asset_env):
    product = upload_image().json()
    draft = client.post("/v1/lookbook-drafts", headers=auth(), json=lookbook_payload([product["asset_id"]])).json()
    client.post("/v1/workspaces/ws-a/members", headers=auth(), json={"user_id": "user-b", "role": "viewer"})
    read = client.get(f"/v1/lookbook-drafts/{draft['draft_id']}?workspace_id=ws-a", headers=auth("token-user-b"))
    assert read.status_code == 200
    create = client.post("/v1/lookbook-drafts", headers=auth("token-user-b"), json=lookbook_payload([product["asset_id"]]))
    assert create.status_code == 403


def test_active_lookbook_draft_protects_project_and_character_references(asset_env):
    product = upload_image().json()
    project = client.post("/v1/projects", headers=auth(), json={"workspace_id": "ws-a", "name": "Campaign"}).json()
    character = client.post("/v1/workspaces/ws-a/characters", headers=auth(),
                            json={"identity": {"name": "Catalog Model"}, "outfits": [], "asset_ids": []}).json()
    draft = client.post("/v1/lookbook-drafts", headers=auth(),
                        json=lookbook_payload([product["asset_id"]], project_id=project["project_id"],
                                              character_id=character["character_id"])).json()
    archive_project = client.put(f"/v1/projects/{project['project_id']}", headers=auth(),
                                 json={"name": "Campaign", "project_type": "general", "status": "ARCHIVED"})
    delete_character = client.delete(f"/v1/workspaces/ws-a/characters/{character['character_id']}", headers=auth())
    assert archive_project.status_code == 409
    assert delete_character.status_code == 409
    assert client.post(f"/v1/lookbook-drafts/{draft['draft_id']}/archive?workspace_id=ws-a", headers=auth()).status_code == 200
    assert client.put(f"/v1/projects/{project['project_id']}", headers=auth(),
                      json={"name": "Campaign", "project_type": "general", "status": "ARCHIVED"}).status_code == 200
    assert client.delete(f"/v1/workspaces/ws-a/characters/{character['character_id']}", headers=auth()).status_code == 204


def test_photo_and_lookbook_draft_lists_and_events_are_paginated(asset_env):
    image = upload_image().json()
    photo_ids = []
    lookbook_ids = []
    for index in range(3):
        photo = client.post("/v1/photo-drafts", headers=auth(),
                            json=photo_draft_payload(image["asset_id"], prompt=f"photo-{index}")).json()
        photo_ids.append(photo["draft_id"])
        lookbook = client.post("/v1/lookbook-drafts", headers=auth(),
                               json=lookbook_payload([image["asset_id"]], title=f"lookbook-{index}")).json()
        lookbook_ids.append(lookbook["draft_id"])
    photo_page = client.get("/v1/photo-drafts?workspace_id=ws-a&limit=1&offset=1", headers=auth()).json()
    lookbook_page = client.get("/v1/lookbook-drafts?workspace_id=ws-a&limit=1&offset=1", headers=auth()).json()
    assert photo_page["total"] == 3 and photo_page["limit"] == 1 and photo_page["offset"] == 1
    assert lookbook_page["total"] == 3 and lookbook_page["limit"] == 1 and lookbook_page["offset"] == 1
    for draft_id, update_body, url in (
        (photo_ids[0], photo_draft_payload(image["asset_id"], prompt="updated-1"), "/v1/photo-drafts/"),
        (lookbook_ids[0], lookbook_payload([image["asset_id"]], title="updated-1"), "/v1/lookbook-drafts/"),
    ):
        assert client.put(url + draft_id, headers=auth(), json=update_body).status_code == 200
        if "photo" in url:
            assert client.put(url + draft_id, headers=auth(), json=photo_draft_payload(image["asset_id"], prompt="updated-2")).status_code == 200
        else:
            assert client.put(url + draft_id, headers=auth(), json=lookbook_payload([image["asset_id"]], title="updated-2")).status_code == 200
    photo_events = client.get(f"/v1/photo-drafts/{photo_ids[0]}/events?workspace_id=ws-a&limit=1&offset=1", headers=auth()).json()
    lookbook_events = client.get(f"/v1/lookbook-drafts/{lookbook_ids[0]}/events?workspace_id=ws-a&limit=1&offset=1", headers=auth()).json()
    assert photo_events["total"] == 3 and len(photo_events["items"]) == 1
    assert lookbook_events["total"] == 3 and len(lookbook_events["items"]) == 1
    assert client.get("/v1/photo-drafts?workspace_id=ws-a&limit=101", headers=auth()).status_code == 422
    assert client.get("/v1/lookbook-drafts?workspace_id=ws-a&offset=-1", headers=auth()).status_code == 422


def test_derived_from_asset_relations_reject_cycles(asset_env):
    first = upload().json()
    second = upload().json()
    third = upload().json()
    assert client.post(f"/v1/assets/{first['asset_id']}/relations", headers=auth(),
                       json={"target_asset_id": second["asset_id"], "relation_type": "derived_from"}).status_code == 201
    assert client.post(f"/v1/assets/{second['asset_id']}/relations", headers=auth(),
                       json={"target_asset_id": third["asset_id"], "relation_type": "derived_from"}).status_code == 201
    cycle = client.post(f"/v1/assets/{third['asset_id']}/relations", headers=auth(),
                        json={"target_asset_id": first["asset_id"], "relation_type": "derived_from"})
    assert cycle.status_code == 422
    assert "cycle" in cycle.text
    relations = client.get(f"/v1/assets/{third['asset_id']}/relations", headers=auth()).json()["items"]
    assert len(relations) == 1


def product_payload(workspace_id, sku, name, image_asset_ids):
    return {"workspace_id": workspace_id, "sku": sku, "name": name,
            "category": "apparel", "description": "Catalog test product",
            "image_asset_ids": image_asset_ids}


def test_product_catalog_sku_crud_pagination_and_archive(asset_env):
    image_a = upload_image(name="product-a.png").json()
    image_b = upload_image(name="product-b.png", data=image_bytes((80, 40, 20))).json()
    created = client.post("/v1/products", headers=auth(),
                          json=product_payload("ws-a", "sku-001", "Jacket", [image_a["asset_id"], image_b["asset_id"]]))
    assert created.status_code == 201, created.text
    product = created.json()
    assert product["sku"] == "SKU-001"
    assert product["status"] == "active"
    assert product["image_asset_ids"] == [image_a["asset_id"], image_b["asset_id"]]
    duplicate = client.post("/v1/products", headers=auth(),
                            json=product_payload("ws-a", "Sku-001", "Duplicate", [image_a["asset_id"]]))
    assert duplicate.status_code == 409
    updated = client.put(f"/v1/products/{product['product_id']}", headers=auth(),
                         json=product_payload("ws-a", "sku-002", "Jacket revised", [image_b["asset_id"]]))
    assert updated.status_code == 200
    assert updated.json()["sku"] == "SKU-002"
    assert updated.json()["image_asset_ids"] == [image_b["asset_id"]]
    events = client.get(f"/v1/products/{product['product_id']}/events?workspace_id=ws-a", headers=auth()).json()
    assert [item["event_type"] for item in events["items"]] == ["product.updated", "product.created"]
    page = client.get("/v1/products?workspace_id=ws-a&limit=1&offset=0", headers=auth()).json()
    assert page["total"] == 1 and len(page["items"]) == 1
    archived = client.post(f"/v1/products/{product['product_id']}/archive?workspace_id=ws-a", headers=auth())
    assert archived.status_code == 200 and archived.json()["status"] == "archived"
    assert client.get("/v1/products?workspace_id=ws-a", headers=auth()).json()["items"] == []
    assert len(client.get("/v1/products?workspace_id=ws-a&include_archived=true", headers=auth()).json()["items"]) == 1


def test_product_catalog_validates_workspace_image_assets_and_viewer_permissions(asset_env):
    model = upload().json()
    wrong_media = client.post("/v1/products", headers=auth(), json=product_payload("ws-a", "SKU-MODEL", "Model", [model["asset_id"]]))
    assert wrong_media.status_code == 422
    image = upload_image().json()
    client.post("/v1/workspaces", headers=auth(), json={"workspace_id": "ws-other"})
    other_image = client.post("/v1/assets/images", headers=auth(), data={"workspace_id": "ws-other"},
                              files={"file": ("other.png", image_bytes(), "application/octet-stream")}).json()
    cross_workspace = client.post("/v1/products", headers=auth(),
                                  json=product_payload("ws-a", "SKU-OTHER", "Other", [other_image["asset_id"]]))
    assert cross_workspace.status_code == 422
    invalid_sku = client.post("/v1/products", headers=auth(),
                              json=product_payload("ws-a", "bad sku", "Invalid", [image["asset_id"]]))
    assert invalid_sku.status_code == 422
    product = client.post("/v1/products", headers=auth(),
                          json=product_payload("ws-a", "SKU-READ", "Read", [image["asset_id"]])).json()
    client.post("/v1/workspaces/ws-a/members", headers=auth(), json={"user_id": "user-b", "role": "viewer"})
    read = client.get(f"/v1/products/{product['product_id']}?workspace_id=ws-a", headers=auth("token-user-b"))
    assert read.status_code == 200
    denied = client.post("/v1/products", headers=auth("token-user-b"),
                         json=product_payload("ws-a", "SKU-DENIED", "Denied", [image["asset_id"]]))
    assert denied.status_code == 403


def test_active_product_and_lookbook_references_protect_product_and_image_assets(asset_env):
    product_image = upload_image().json()
    product = client.post("/v1/products", headers=auth(),
                           json=product_payload("ws-a", "SKU-LB-01", "Lookbook Product", [product_image["asset_id"]])).json()
    blocked_asset = client.delete(f"/v1/assets/{product_image['asset_id']}", headers=auth())
    assert blocked_asset.status_code == 409
    lookbook = client.post("/v1/lookbook-drafts", headers=auth(),
                           json=lookbook_payload([], product_ids=[product["product_id"]])).json()
    blocked_archive = client.post(f"/v1/products/{product['product_id']}/archive?workspace_id=ws-a", headers=auth())
    assert blocked_archive.status_code == 409
    blocked_asset_again = client.delete(f"/v1/assets/{product_image['asset_id']}", headers=auth())
    assert blocked_asset_again.status_code == 409
    assert client.post(f"/v1/lookbook-drafts/{lookbook['draft_id']}/archive?workspace_id=ws-a", headers=auth()).status_code == 200
    assert client.post(f"/v1/products/{product['product_id']}/archive?workspace_id=ws-a", headers=auth()).status_code == 200
    assert client.delete(f"/v1/assets/{product_image['asset_id']}", headers=auth()).status_code == 204


def test_lookbook_draft_can_resolve_catalog_product_images(asset_env):
    image_a = upload_image(name="catalog-a.png").json()
    image_b = upload_image(name="catalog-b.png", data=image_bytes((70, 100, 140))).json()
    product = client.post("/v1/products", headers=auth(),
                          json=product_payload("ws-a", "SKU-LB-02", "Catalog Item", [image_a["asset_id"], image_b["asset_id"]])).json()
    draft = client.post("/v1/lookbook-drafts", headers=auth(),
                        json=lookbook_payload([], product_ids=[product["product_id"]])).json()
    assert draft["input"]["product_ids"] == [product["product_id"]]
    assert draft["input"]["product_asset_ids"] == []
    assert client.get(f"/v1/assets/{image_a['asset_id']}/provenance", headers=auth()).status_code == 200


def test_lookbook_entity_reference_migration_preserves_legacy_rows_and_adds_product_type(asset_env):
    from app.assets.store import _connect
    from app.lookbook import initialize as initialize_lookbook
    image = upload_image().json()
    project = client.post("/v1/projects", headers=auth(), json={"workspace_id": "ws-a", "name": "Legacy Project"}).json()
    character = client.post("/v1/workspaces/ws-a/characters", headers=auth(),
                            json={"identity": {"name": "Legacy Character"}, "outfits": [], "asset_ids": []}).json()
    legacy_draft = client.post("/v1/lookbook-drafts", headers=auth(),
                               json=lookbook_payload([image["asset_id"]], project_id=project["project_id"],
                                                     character_id=character["character_id"])).json()
    initialize_lookbook()
    with _connect() as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute("DROP INDEX IF EXISTS idx_lookbook_draft_entities_ref")
        db.execute("ALTER TABLE lookbook_draft_entities RENAME TO lookbook_draft_entities_current")
        db.execute("""CREATE TABLE lookbook_draft_entities (
            draft_id TEXT NOT NULL REFERENCES lookbook_drafts(draft_id) ON DELETE CASCADE,
            entity_type TEXT NOT NULL CHECK(entity_type IN ('project','character')),
            entity_id TEXT NOT NULL,
            PRIMARY KEY(draft_id, entity_type, entity_id)
        )""")
        db.execute("INSERT INTO lookbook_draft_entities SELECT * FROM lookbook_draft_entities_current")
        db.execute("DROP TABLE lookbook_draft_entities_current")
    initialize_lookbook()
    with _connect() as db:
        schema = db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='lookbook_draft_entities'").fetchone()["sql"]
        legacy_refs = db.execute("SELECT entity_type,entity_id FROM lookbook_draft_entities WHERE draft_id=? ORDER BY entity_type",
                                 (legacy_draft["draft_id"],)).fetchall()
    assert "'product'" in schema
    assert {(row["entity_type"], row["entity_id"]) for row in legacy_refs} == {
        ("project", project["project_id"]), ("character", character["character_id"])
    }
    product = client.post("/v1/products", headers=auth(),
                          json=product_payload("ws-a", "SKU-MIGRATION", "Migration Product", [image["asset_id"]])).json()
    product_draft = client.post("/v1/lookbook-drafts", headers=auth(),
                                json=lookbook_payload([], product_ids=[product["product_id"]]))
    assert product_draft.status_code == 201, product_draft.text


def test_product_variants_support_size_color_sku_uniqueness_and_lifecycle(asset_env):
    image = upload_image(name="variant-base.png").json()
    alternate = upload_image(name="variant-red.png", data=image_bytes((180, 20, 20))).json()
    product = client.post("/v1/products", headers=auth(),
                          json=product_payload("ws-a", "STYLE-100", "Classic Shirt", [image["asset_id"]])).json()
    variant_payload = {"workspace_id": "ws-a", "sku": "STYLE-100-BLK-M",
                       "option_values": {"Color": "Black", "Size": "M"},
                       "image_asset_ids": [alternate["asset_id"]]}
    created = client.post(f"/v1/products/{product['product_id']}/variants", headers=auth(), json=variant_payload)
    assert created.status_code == 201, created.text
    variant = created.json()
    assert variant["sku"] == "STYLE-100-BLK-M"
    assert variant["option_values"] == {"color": "Black", "size": "M"}
    assert variant["image_asset_ids"] == [alternate["asset_id"]]

    # Master SKU and variant SKU share one workspace namespace.
    duplicate_variant = client.post(f"/v1/products/{product['product_id']}/variants", headers=auth(),
                                    json={**variant_payload, "sku": "style-100"})
    assert duplicate_variant.status_code == 409
    duplicate_master = client.post("/v1/products", headers=auth(),
                                   json=product_payload("ws-a", "STYLE-100-BLK-M", "Duplicate", [image["asset_id"]]))
    assert duplicate_master.status_code == 409

    assert client.delete(f"/v1/assets/{alternate['asset_id']}", headers=auth()).status_code == 409
    updated = client.put(f"/v1/products/{product['product_id']}/variants/{variant['variant_id']}", headers=auth(),
                         json={**variant_payload, "sku": "STYLE-100-BLK-L", "option_values": {"color": "Black", "size": "L"}})
    assert updated.status_code == 200 and updated.json()["option_values"]["size"] == "L"
    listed = client.get(f"/v1/products/{product['product_id']}/variants?workspace_id=ws-a", headers=auth()).json()
    assert len(listed["items"]) == 1
    archived = client.post(f"/v1/products/{product['product_id']}/variants/{variant['variant_id']}/archive?workspace_id=ws-a", headers=auth())
    assert archived.status_code == 200 and archived.json()["status"] == "archived"
    assert client.delete(f"/v1/assets/{alternate['asset_id']}", headers=auth()).status_code == 204


def test_product_variant_validation_workspace_and_parent_archive(asset_env):
    image = upload_image().json()
    product = client.post("/v1/products", headers=auth(),
                          json=product_payload("ws-a", "STYLE-200", "Trouser", [image["asset_id"]])).json()
    invalid = client.post(f"/v1/products/{product['product_id']}/variants", headers=auth(), json={
        "workspace_id": "ws-a", "sku": "STYLE-200-S", "option_values": {"size": " "},
        "image_asset_ids": []})
    assert invalid.status_code == 422
    variant = client.post(f"/v1/products/{product['product_id']}/variants", headers=auth(), json={
        "workspace_id": "ws-a", "sku": "STYLE-200-S", "option_values": {"size": "S"},
        "image_asset_ids": []}).json()
    archived = client.post(f"/v1/products/{product['product_id']}/archive?workspace_id=ws-a", headers=auth())
    assert archived.status_code == 200
    assert archived.json()["variants"][0]["status"] == "archived"
    assert client.get(f"/v1/products/{product['product_id']}/variants?workspace_id=ws-a", headers=auth()).status_code == 404


def test_product_and_variant_sku_namespace_is_shared_on_updates(asset_env):
    image = upload_image().json()
    first = client.post("/v1/products", headers=auth(),
                        json=product_payload("ws-a", "STYLE-300", "First", [image["asset_id"]])).json()
    second = client.post("/v1/products", headers=auth(),
                         json=product_payload("ws-a", "STYLE-301", "Second", [image["asset_id"]])).json()
    variant = client.post(f"/v1/products/{first['product_id']}/variants", headers=auth(), json={
        "workspace_id": "ws-a", "sku": "STYLE-300-RED-S", "option_values": {"color": "Red", "size": "S"}
    }).json()
    collision = client.put(f"/v1/products/{second['product_id']}", headers=auth(), json=
                           product_payload("ws-a", variant["sku"], "Second renamed", [image["asset_id"]]))
    assert collision.status_code == 409
    variant_collision = client.put(f"/v1/products/{first['product_id']}/variants/{variant['variant_id']}", headers=auth(), json={
        "workspace_id": "ws-a", "sku": "STYLE-301", "option_values": {"color": "Red", "size": "S"}
    })
    assert variant_collision.status_code == 409


def test_lookbook_draft_can_select_variant_and_resolves_variant_images(asset_env):
    parent_image = upload_image(name="variant-parent.png").json()
    variant_image = upload_image(name="variant-specific.png", data=image_bytes((200, 30, 30))).json()
    product = client.post("/v1/products", headers=auth(), json=
                          product_payload("ws-a", "LOOK-STYLE-01", "Lookbook Jacket", [parent_image["asset_id"]])).json()
    variant = client.post(f"/v1/products/{product['product_id']}/variants", headers=auth(), json={
        "workspace_id": "ws-a", "sku": "LOOK-STYLE-01-RED-M",
        "option_values": {"color": "Red", "size": "M"},
        "image_asset_ids": [variant_image["asset_id"]],
    }).json()
    draft = client.post("/v1/lookbook-drafts", headers=auth(), json=lookbook_payload(
        [], product_variant_ids=[variant["variant_id"]]))
    assert draft.status_code == 201, draft.text
    assert draft.json()["input"]["product_variant_ids"] == [variant["variant_id"]]
    assert client.delete(f"/v1/assets/{variant_image['asset_id']}", headers=auth()).status_code == 409
    assert client.post(f"/v1/products/{product['product_id']}/archive?workspace_id=ws-a", headers=auth()).status_code == 409
    assert client.post(f"/v1/products/{product['product_id']}/variants/{variant['variant_id']}/archive?workspace_id=ws-a", headers=auth()).status_code == 409
    edited = client.put(f"/v1/products/{product['product_id']}/variants/{variant['variant_id']}", headers=auth(), json={
        "workspace_id": "ws-a", "sku": "LOOK-STYLE-01-RED-L", "option_values": {"color": "Red", "size": "L"},
        "image_asset_ids": [variant_image["asset_id"]],
    })
    assert edited.status_code == 409
    from app.products import _connect
    with _connect() as db:
        roles = db.execute("SELECT asset_id,role FROM lookbook_draft_assets WHERE draft_id=?", (draft.json()["draft_id"],)).fetchall()
        entity_types = db.execute("SELECT entity_type,entity_id FROM lookbook_draft_entities WHERE draft_id=?", (draft.json()["draft_id"],)).fetchall()
        schema = db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='lookbook_draft_entities'").fetchone()["sql"]
    assert [(row["asset_id"], row["role"]) for row in roles] == [(variant_image["asset_id"], "product")]
    assert {row["entity_type"] for row in entity_types} == {"product", "product_variant"}
    assert "product_variant" in schema
    assert client.post(f"/v1/lookbook-drafts/{draft.json()['draft_id']}/archive?workspace_id=ws-a", headers=auth()).status_code == 200
    assert client.post(f"/v1/products/{product['product_id']}/variants/{variant['variant_id']}/archive?workspace_id=ws-a", headers=auth()).status_code == 200
    assert client.delete(f"/v1/assets/{variant_image['asset_id']}", headers=auth()).status_code == 204


def test_lookbook_variant_falls_back_to_parent_product_images_and_rejects_invalid_variant(asset_env):
    parent_image = upload_image(name="variant-fallback.png").json()
    product = client.post("/v1/products", headers=auth(), json=
                          product_payload("ws-a", "LOOK-STYLE-02", "Fallback Shirt", [parent_image["asset_id"]])).json()
    variant = client.post(f"/v1/products/{product['product_id']}/variants", headers=auth(), json={
        "workspace_id": "ws-a", "sku": "LOOK-STYLE-02-BLUE-S", "option_values": {"color": "Blue", "size": "S"},
        "image_asset_ids": [],
    }).json()
    draft = client.post("/v1/lookbook-drafts", headers=auth(), json=lookbook_payload(
        [], product_variant_ids=[variant["variant_id"]]))
    assert draft.status_code == 201, draft.text
    invalid = client.post("/v1/lookbook-drafts", headers=auth(), json=lookbook_payload(
        [], product_variant_ids=["pvr_not_found"]))
    assert invalid.status_code == 422
    assert client.post(f"/v1/lookbook-drafts/{draft.json()['draft_id']}/archive?workspace_id=ws-a", headers=auth()).status_code == 200


def test_lookbook_review_workflow_approval_manifest_and_edit_lock(asset_env):
    product_image = upload_image(name="review-plan.png").json()
    draft = client.post("/v1/lookbook-drafts", headers=auth(), json=lookbook_payload([product_image["asset_id"]]))
    assert draft.status_code == 201, draft.text
    draft_id = draft.json()["draft_id"]
    assert draft.json()["workflow_status"] == "draft"
    client.post("/v1/workspaces/ws-a/members", headers=auth(), json={"user_id": "user-b", "role": "viewer"})
    viewer_submit = client.post(f"/v1/lookbook-drafts/{draft_id}/submit?workspace_id=ws-a", headers=auth("token-user-b"))
    assert viewer_submit.status_code == 403

    submitted = client.post(f"/v1/lookbook-drafts/{draft_id}/submit?workspace_id=ws-a", headers=auth())
    assert submitted.status_code == 200 and submitted.json()["workflow_status"] == "in_review"
    locked = client.put(f"/v1/lookbook-drafts/{draft_id}", headers=auth(), json=lookbook_payload(
        [product_image["asset_id"]], title="Changed while reviewing"))
    assert locked.status_code == 409
    viewer_approve = client.post(f"/v1/lookbook-drafts/{draft_id}/approve?workspace_id=ws-a", headers=auth("token-user-b"), json={})
    assert viewer_approve.status_code == 403
    approved = client.post(f"/v1/lookbook-drafts/{draft_id}/approve?workspace_id=ws-a", headers=auth(), json={"comment": "Approved planning brief"})
    assert approved.status_code == 200 and approved.json()["workflow_status"] == "approved"
    locked_after_approval = client.put(f"/v1/lookbook-drafts/{draft_id}", headers=auth(), json=lookbook_payload(
        [product_image["asset_id"]], title="Changed after approval"))
    assert locked_after_approval.status_code == 409
    manifest = client.get(f"/v1/lookbook-drafts/{draft_id}/manifest?workspace_id=ws-a", headers=auth())
    assert manifest.status_code == 200
    assert manifest.json()["manifest_type"] == "LOOKBOOK_PLAN_ONLY"
    assert manifest.json()["generated_outputs_included"] is False
    assert manifest.json()["referenced_assets"] == [{"asset_id": product_image["asset_id"], "role": "product"}]
    events = client.get(f"/v1/lookbook-drafts/{draft_id}/events?workspace_id=ws-a", headers=auth()).json()
    assert {item["event_type"] for item in events["items"]} >= {"lookbook.submitted_for_review", "lookbook.approved"}


def test_lookbook_request_changes_requires_comment_and_allows_revision_resubmission(asset_env):
    image = upload_image(name="revision-plan.png").json()
    draft = client.post("/v1/lookbook-drafts", headers=auth(), json=lookbook_payload([image["asset_id"]])).json()
    draft_id = draft["draft_id"]
    assert client.post(f"/v1/lookbook-drafts/{draft_id}/submit?workspace_id=ws-a", headers=auth()).status_code == 200
    missing_comment = client.post(f"/v1/lookbook-drafts/{draft_id}/request-changes?workspace_id=ws-a", headers=auth(), json={})
    assert missing_comment.status_code == 422
    returned = client.post(f"/v1/lookbook-drafts/{draft_id}/request-changes?workspace_id=ws-a", headers=auth(), json={"comment": "Please adjust the scene"})
    assert returned.status_code == 200 and returned.json()["workflow_status"] == "changes_requested"
    revised = client.put(f"/v1/lookbook-drafts/{draft_id}", headers=auth(), json=lookbook_payload(
        [image["asset_id"]], title="Spring campaign revised"))
    assert revised.status_code == 200 and revised.json()["workflow_status"] == "changes_requested"
    resubmitted = client.post(f"/v1/lookbook-drafts/{draft_id}/submit?workspace_id=ws-a", headers=auth())
    assert resubmitted.status_code == 200 and resubmitted.json()["workflow_status"] == "in_review"
    approved = client.post(f"/v1/lookbook-drafts/{draft_id}/approve?workspace_id=ws-a", headers=auth(), json={})
    assert approved.status_code == 200 and approved.json()["workflow_status"] == "approved"


def test_photo_local_enhance_creates_derived_immutable_asset_and_is_idempotent(asset_env):
    source_bytes = image_bytes((35, 90, 150))
    source = upload_image(name="local-source.png", data=source_bytes).json()
    draft = client.post("/v1/photo-drafts", headers=auth(),
                        json=photo_draft_payload(source["asset_id"], operation="ENHANCE")).json()
    url = f"/v1/photo-drafts/{draft['draft_id']}/process-local?workspace_id=ws-a"
    response = client.post(url, headers={**auth(), "Idempotency-Key": "photo-enhance-001"})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["run"]["status"] == "succeeded"
    assert result["run"]["operation"] == "ENHANCE"
    output = result["output_asset"]
    assert output["asset_kind"] == "image"
    assert output["asset_id"] != source["asset_id"]
    assert output["version_id"] and output["checksum_sha256"]
    assert "storage_key" not in output
    from PIL import Image
    from app.assets.store import storage_path
    with Image.open(storage_path(output["asset_id"])) as processed_image:
        assert processed_image.size == (32, 24)
    assert result["run"]["quality"]["spatial_geometry_preserved"] is True
    assert result["run"]["quality"]["semantic_identity_preservation_verified"] is False
    assert result["run"]["quality"]["is_ai_generated"] is False
    assert result["run"]["quality"]["provider_dispatched"] is False
    assert result["run"]["quality"]["credit_charged"] is False

    from app.assets.store import list_asset_versions, list_asset_provenance, list_asset_relations
    versions = list_asset_versions(output["asset_id"], "ws-a")
    assert len(versions) == 1 and versions[0]["version_id"] == output["version_id"]
    provenance = list_asset_provenance(output["asset_id"], "ws-a")
    assert any(item["event_type"] == "asset.photo_processed" for item in provenance)
    relations = list_asset_relations(output["asset_id"], "ws-a")
    assert any(item["relation_type"] == "derived_from" and item["target_asset_id"] == source["asset_id"] for item in relations)
    assert client.delete(f"/v1/assets/{output['asset_id']}", headers=auth()).status_code == 409

    repeated = client.post(url, headers={**auth(), "Idempotency-Key": "photo-enhance-001"})
    assert repeated.status_code == 200
    assert repeated.json()["run"]["run_id"] == result["run"]["run_id"]
    assert repeated.json()["output_asset"]["asset_id"] == output["asset_id"]
    other_draft = client.post("/v1/photo-drafts", headers=auth(),
                              json=photo_draft_payload(source["asset_id"], operation="LIGHTING")).json()
    key_conflict = client.post(f"/v1/photo-drafts/{other_draft['draft_id']}/process-local?workspace_id=ws-a",
                               headers={**auth(), "Idempotency-Key": "photo-enhance-001"})
    assert key_conflict.status_code == 409
    runs = client.get(f"/v1/photo-drafts/{draft['draft_id']}/runs?workspace_id=ws-a", headers=auth())
    assert runs.status_code == 200 and runs.json()["total"] == 1
    events = client.get(f"/v1/photo-drafts/{draft['draft_id']}/runs/{result['run']['run_id']}/events?workspace_id=ws-a", headers=auth())
    assert [item["event_type"] for item in events.json()["items"]] == ["photo.local_run_succeeded", "photo.local_run_started"]
    import sqlite3
    with sqlite3.connect(asset_env / "assets.sqlite3") as db:
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("UPDATE photo_processing_events SET event_type='tampered' WHERE run_id=?", (result["run"]["run_id"],))


def test_photo_local_lighting_support_and_ai_only_operations_fail_closed(asset_env):
    source = upload_image().json()
    supported = client.post("/v1/photo-drafts", headers=auth(),
                            json=photo_draft_payload(source["asset_id"], operation="LIGHTING", output_format="WEBP")).json()
    response = client.post(f"/v1/photo-drafts/{supported['draft_id']}/process-local?workspace_id=ws-a",
                           headers={**auth(), "Idempotency-Key": "photo-lighting-01"})
    assert response.status_code == 200, response.text
    assert response.json()["output_asset"]["media_type"] == "image/webp"

    for operation in ("BACKGROUND", "RETOUCH", "COMPOSE"):
        draft = client.post("/v1/photo-drafts", headers=auth(),
                            json=photo_draft_payload(source["asset_id"], operation=operation)).json()
        blocked = client.post(f"/v1/photo-drafts/{draft['draft_id']}/process-local?workspace_id=ws-a",
                              headers={**auth(), "Idempotency-Key": f"photo-{operation.lower()}-01"})
        assert blocked.status_code == 409
        assert "requires an AI Photo Engine" in blocked.json()["detail"]
        runs = client.get(f"/v1/photo-drafts/{draft['draft_id']}/runs?workspace_id=ws-a", headers=auth()).json()
        assert runs["total"] == 0

    multiple = client.post("/v1/photo-drafts", headers=auth(),
                           json=photo_draft_payload(source["asset_id"], output_count=2)).json()
    rejected = client.post(f"/v1/photo-drafts/{multiple['draft_id']}/process-local?workspace_id=ws-a",
                           headers={**auth(), "Idempotency-Key": "photo-multi-001"})
    assert rejected.status_code == 409


def test_photo_local_processing_failed_run_can_retry_after_source_repair(asset_env):
    from app.assets.store import storage_path
    source_bytes = image_bytes((70, 120, 180))
    source = upload_image(name="retry-source.png", data=source_bytes).json()
    draft = client.post("/v1/photo-drafts", headers=auth(),
                        json=photo_draft_payload(source["asset_id"], operation="LIGHTING")).json()
    source_path = storage_path(source["asset_id"])
    source_path.write_bytes(b"corrupted")
    url = f"/v1/photo-drafts/{draft['draft_id']}/process-local?workspace_id=ws-a"
    headers = {**auth(), "Idempotency-Key": "photo-retry-0001"}
    failed = client.post(url, headers=headers)
    assert failed.status_code == 422
    runs = client.get(f"/v1/photo-drafts/{draft['draft_id']}/runs?workspace_id=ws-a", headers=auth()).json()
    assert runs["total"] == 1 and runs["items"][0]["status"] == "failed"
    source_path.write_bytes(source_bytes)
    retried = client.post(url, headers=headers)
    assert retried.status_code == 200, retried.text
    assert retried.json()["run"]["attempts"] == 2
    events = client.get(f"/v1/photo-drafts/{draft['draft_id']}/runs/{retried.json()['run']['run_id']}/events?workspace_id=ws-a", headers=auth()).json()
    assert [item["event_type"] for item in events["items"]] == [
        "photo.local_run_succeeded", "photo.local_run_retried", "photo.local_run_failed", "photo.local_run_started"]


def test_photo_local_processing_requires_idempotency_and_respects_workspace_roles(asset_env):
    source = upload_image().json()
    draft = client.post("/v1/photo-drafts", headers=auth(),
                        json=photo_draft_payload(source["asset_id"])).json()
    url = f"/v1/photo-drafts/{draft['draft_id']}/process-local?workspace_id=ws-a"
    missing = client.post(url, headers=auth())
    assert missing.status_code == 422
    client.post("/v1/workspaces/ws-a/members", headers=auth(), json={"user_id": "user-b", "role": "viewer"})
    viewer = client.post(url, headers={"Authorization": "Bearer token-user-b", "Idempotency-Key": "photo-viewer-01"})
    assert viewer.status_code == 403
    readable = client.get(f"/v1/photo-drafts/{draft['draft_id']}/runs?workspace_id=ws-a",
                          headers={"Authorization": "Bearer token-user-b"})
    assert readable.status_code == 200


def test_photo_output_review_approval_and_internal_manifest_gate(asset_env):
    source = upload_image().json()
    draft = client.post("/v1/photo-drafts", headers=auth(),
                        json=photo_draft_payload(source["asset_id"], operation="ENHANCE")).json()
    processed = client.post(f"/v1/photo-drafts/{draft['draft_id']}/process-local?workspace_id=ws-a",
                            headers={**auth(), "Idempotency-Key": "photo-review-001"})
    assert processed.status_code == 200, processed.text
    run = processed.json()["run"]
    run_id = run["run_id"]
    base = f"/v1/photo-drafts/{draft['draft_id']}/runs/{run_id}"
    review = client.get(f"{base}/review?workspace_id=ws-a", headers=auth())
    assert review.status_code == 200 and review.json()["status"] == "pending_review"
    output = review.json()["output"]
    assert output["asset_id"] == processed.json()["output_asset"]["asset_id"]
    assert output["asset_version_id"] == processed.json()["output_asset"]["version_id"]
    assert output["provenance_id"] and output["checksum_sha256"]

    client.post("/v1/workspaces/ws-a/members", headers=auth(), json={"user_id": "user-b", "role": "viewer"})
    viewer_read = client.get(f"{base}/review?workspace_id=ws-a", headers=auth("token-user-b"))
    assert viewer_read.status_code == 200
    viewer_approve = client.post(f"{base}/review/approve?workspace_id=ws-a",
                                 headers=auth("token-user-b"), json={})
    assert viewer_approve.status_code == 403
    missing_comment = client.post(f"{base}/review/request-changes?workspace_id=ws-a", headers=auth(), json={})
    assert missing_comment.status_code == 409
    requested = client.post(f"{base}/review/request-changes?workspace_id=ws-a", headers=auth(),
                             json={"comment": "Check the product logo edge."})
    assert requested.status_code == 200 and requested.json()["status"] == "changes_requested"
    blocked_export = client.post(f"{base}/export-manifest?workspace_id=ws-a", headers=auth())
    assert blocked_export.status_code == 409
    approved = client.post(f"{base}/review/approve?workspace_id=ws-a", headers=auth(),
                           json={"comment": "Reviewed against the original source."})
    assert approved.status_code == 200 and approved.json()["status"] == "approved"
    approval_event = approved.json()["events"][0]
    assert approval_event["asset_id"] == output["asset_id"]
    assert approval_event["asset_version_id"] == output["asset_version_id"]
    assert approval_event["provenance_id"] == output["provenance_id"]
    assert approval_event["checksum_sha256"] == output["checksum_sha256"]
    # Review approval is bound to immutable v1, not the mutable current-version pointer.
    output_asset_id = output["asset_id"]
    version_two = client.post(f"/v1/assets/{output_asset_id}/versions", headers=auth(),
                              files={"file": ("replacement.png", image_bytes((200, 30, 40)), "image/png")})
    assert version_two.status_code == 201, version_two.text
    assert version_two.json()["version_number"] == 2
    still_approved = client.get(f"{base}/review?workspace_id=ws-a", headers=auth())
    assert still_approved.status_code == 200 and still_approved.json()["status"] == "approved"
    import sqlite3
    with sqlite3.connect(asset_env / "assets.sqlite3") as db:
        storage_key = db.execute("SELECT storage_key FROM asset_versions WHERE version_id=?", (output["asset_version_id"],)).fetchone()[0]
    reviewed_version_path = asset_env / "private" / storage_key
    reviewed_version_bytes = reviewed_version_path.read_bytes()
    damaged = bytearray(reviewed_version_bytes); damaged[-1] ^= 0x01; reviewed_version_path.write_bytes(damaged)
    integrity_error = client.get(f"{base}/review?workspace_id=ws-a", headers=auth())
    assert integrity_error.status_code == 200 and integrity_error.json()["status"] == "output_integrity_error"
    corrupt_export = client.post(f"{base}/export-manifest?workspace_id=ws-a", headers=auth())
    assert corrupt_export.status_code == 409
    reviewed_version_path.write_bytes(reviewed_version_bytes)
    restored_review = client.get(f"{base}/review?workspace_id=ws-a", headers=auth())
    assert restored_review.status_code == 200 and restored_review.json()["status"] == "approved"
    viewer_export = client.post(f"{base}/export-manifest?workspace_id=ws-a", headers=auth("token-user-b"))
    assert viewer_export.status_code == 403
    exported = client.post(f"{base}/export-manifest?workspace_id=ws-a", headers=auth())
    assert exported.status_code == 200
    manifest = exported.json()["manifest"]
    assert manifest["is_ai_generated"] is False
    assert manifest["publication_authorized"] is False
    assert manifest["commercial_rights_verified"] is False
    assert manifest["binary_files_included"] is False
    assert manifest["output"]["asset_version_id"] == output["asset_version_id"]
    assert manifest["output"]["checksum_sha256"] == output["checksum_sha256"]
    assert exported.json()["manifest_sha256"]
    terminal = client.post(f"{base}/review/reject?workspace_id=ws-a", headers=auth(),
                           json={"comment": "Change"})
    assert terminal.status_code == 409
    listed = client.get(f"/v1/photo-drafts/{draft['draft_id']}/runs?workspace_id=ws-a", headers=auth()).json()
    assert listed["items"][0]["review_status"] == "approved"

    import sqlite3
    with sqlite3.connect(asset_env / "assets.sqlite3") as db:
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("UPDATE photo_output_review_events SET comment='tampered' WHERE run_id=?", (run_id,))
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("DELETE FROM photo_output_export_events WHERE run_id=?", (run_id,))


def test_signed_asset_version_preview_remains_bound_to_historical_bytes(asset_env):
    from urllib.parse import urlsplit, parse_qs
    from app.assets.routes import _version_signature
    source_v1 = image_bytes((220, 30, 40))
    asset = upload_image(name="versioned-preview.png", data=source_v1).json()
    version_one = client.get(f"/v1/assets/{asset['asset_id']}/versions", headers=auth()).json()["items"][0]
    signed = client.post(f"/v1/assets/{asset['asset_id']}/versions/{version_one['version_id']}/preview-url", headers=auth())
    assert signed.status_code == 200, signed.text
    parts = urlsplit(signed.json()["url"])
    preview_v1 = client.get(f"{parts.path}?{parts.query}")
    assert preview_v1.status_code == 200 and preview_v1.content == source_v1
    assert preview_v1.headers["cache-control"] == "private, no-store"

    source_v2 = image_bytes((30, 210, 60))
    uploaded_v2 = client.post(f"/v1/assets/{asset['asset_id']}/versions", headers=auth(),
                              files={"file": ("versioned-preview-v2.png", source_v2, "image/png")})
    assert uploaded_v2.status_code == 201 and uploaded_v2.json()["version_number"] == 2
    old_signed = client.get(f"{parts.path}?{parts.query}")
    assert old_signed.status_code == 200 and old_signed.content == source_v1
    current = client.post(f"/v1/assets/{asset['asset_id']}/preview-url", headers=auth()).json()
    current_parts = urlsplit(current["url"])
    current_preview = client.get(f"{current_parts.path}?{current_parts.query}")
    assert current_preview.status_code == 200 and current_preview.content == source_v2

    query = parse_qs(parts.query)
    tampered = client.get(f"{parts.path}?expires={query['expires'][0]}&signature={'0' * 64}")
    assert tampered.status_code == 403
    expired = int(time.time()) - 10
    expired_signature = _version_signature(asset["asset_id"], version_one["version_id"], expired)
    expired_response = client.get(f"{parts.path}?expires={expired}&signature={expired_signature}")
    assert expired_response.status_code == 403


def test_photo_draft_pins_source_asset_version_for_processing_and_idempotency(asset_env):
    from app.assets.store import list_asset_versions, list_asset_provenance
    source_v1 = image_bytes((180, 40, 50))
    source = upload_image(name="photo-source-v1.png", data=source_v1).json()
    draft = client.post("/v1/photo-drafts", headers=auth(),
                        json=photo_draft_payload(source["asset_id"], operation="LIGHTING")).json()
    v1 = list_asset_versions(source["asset_id"], "ws-a")[0]
    assert draft["input"]["source_version_id"] == v1["version_id"]
    assert draft["input"]["source_checksum_sha256"] == v1["checksum_sha256"]

    source_v2 = image_bytes((20, 40, 220))
    uploaded = client.post(f"/v1/assets/{source['asset_id']}/versions", headers=auth(),
                           files={"file": ("photo-source-v2.png", source_v2, "image/png")})
    assert uploaded.status_code == 201 and uploaded.json()["version_number"] == 2
    url = f"/v1/photo-drafts/{draft['draft_id']}/process-local?workspace_id=ws-a"
    headers = {**auth(), "Idempotency-Key": "photo-pinned-source-001"}
    processed = client.post(url, headers=headers)
    assert processed.status_code == 200, processed.text
    run = processed.json()["run"]
    assert run["source_version_id"] == v1["version_id"]
    assert run["source_checksum_sha256"] == v1["checksum_sha256"]
    output_provenance = list_asset_provenance(processed.json()["output_asset"]["asset_id"], "ws-a")
    event = next(item for item in output_provenance if item["event_type"] == "asset.photo_processed")
    assert event["details"]["source_version_id"] == v1["version_id"]
    assert event["details"]["source_checksum_sha256"] == v1["checksum_sha256"]
    replay = client.post(url, headers=headers)
    assert replay.status_code == 200 and replay.json()["run"]["run_id"] == run["run_id"]
    assert replay.json()["output_asset"]["asset_id"] == processed.json()["output_asset"]["asset_id"]


def test_lookbook_assembles_only_approved_photo_outputs_with_product_variant_snapshot(asset_env):
    product_image = upload_image(name="assembly-product.png").json()
    photo_source = upload_image(name="assembly-source.png", data=image_bytes((80, 100, 160))).json()
    product = client.post("/v1/products", headers=auth(), json=
                          product_payload("ws-a", "ASSEMBLY-100", "Studio Jacket", [product_image["asset_id"]])).json()
    variant = client.post(f"/v1/products/{product['product_id']}/variants", headers=auth(), json={
        "workspace_id": "ws-a", "sku": "ASSEMBLY-100-NAVY-M",
        "option_values": {"color": "Navy", "size": "M"}, "image_asset_ids": [],
    }).json()
    lookbook = client.post("/v1/lookbook-drafts", headers=auth(), json=lookbook_payload(
        [], product_ids=[product["product_id"]], product_variant_ids=[variant["variant_id"]])).json()
    draft_id = lookbook["draft_id"]
    before_approval = client.post(f"/v1/lookbook-drafts/{draft_id}/outputs?workspace_id=ws-a", headers=auth(),
                                  json={"photo_run_id": "phr_notready", "page_order": 1})
    assert before_approval.status_code == 409
    assert client.post(f"/v1/lookbook-drafts/{draft_id}/submit?workspace_id=ws-a", headers=auth()).status_code == 200
    approved_plan = client.post(f"/v1/lookbook-drafts/{draft_id}/approve?workspace_id=ws-a", headers=auth(), json={})
    assert approved_plan.status_code == 200 and approved_plan.json()["workflow_status"] == "approved"

    photo_draft = client.post("/v1/photo-drafts", headers=auth(),
                              json=photo_draft_payload(photo_source["asset_id"], operation="ENHANCE")).json()
    processed = client.post(f"/v1/photo-drafts/{photo_draft['draft_id']}/process-local?workspace_id=ws-a",
                            headers={**auth(), "Idempotency-Key": "lookbook-assembly-run-01"})
    assert processed.status_code == 200, processed.text
    run_id = processed.json()["run"]["run_id"]
    photo_review = client.post(f"/v1/photo-drafts/{photo_draft['draft_id']}/runs/{run_id}/review/approve?workspace_id=ws-a",
                               headers=auth(), json={})
    assert photo_review.status_code == 200 and photo_review.json()["status"] == "approved"

    attach = client.post(f"/v1/lookbook-drafts/{draft_id}/outputs?workspace_id=ws-a", headers=auth(), json={
        "photo_run_id": run_id, "product_variant_id": variant["variant_id"],
        "page_order": 1, "caption": "Navy jacket front view",
    })
    assert attach.status_code == 201, attach.text
    item = attach.json()
    assert item["asset_id"] == processed.json()["output_asset"]["asset_id"]
    assert item["asset_version_id"] == processed.json()["output_asset"]["version_id"]
    assert item["product_id"] == product["product_id"]
    assert item["product_sku"] == "ASSEMBLY-100"
    assert item["product_variant_id"] == variant["variant_id"]
    assert item["variant_sku"] == "ASSEMBLY-100-NAVY-M"
    assert item["variant_options"] == {"color": "Navy", "size": "M"}

    # Preview URL refresh is presentation-only and remains bound to the attached immutable version.
    preview_refresh = client.post(
        f"/v1/assets/{item['asset_id']}/versions/{item['asset_version_id']}/preview-url", headers=auth()
    )
    assert preview_refresh.status_code == 200
    assert preview_refresh.json()["url"] and preview_refresh.json()["expires_at"] > 0
    outputs_after_preview = client.get(f"/v1/lookbook-drafts/{draft_id}/outputs?workspace_id=ws-a", headers=auth())
    preview_item = outputs_after_preview.json()["items"][0]
    assert (preview_item["asset_id"], preview_item["asset_version_id"], preview_item["checksum_sha256"]) == (
        item["asset_id"], item["asset_version_id"], item["checksum_sha256"]
    )

    duplicate = client.post(f"/v1/lookbook-drafts/{draft_id}/outputs?workspace_id=ws-a", headers=auth(), json={
        "photo_run_id": run_id, "page_order": 2,
    })
    assert duplicate.status_code == 409

    # A successful but unapproved Photo run cannot be assembled.
    pending_photo_draft = client.post("/v1/photo-drafts", headers=auth(),
                                      json=photo_draft_payload(photo_source["asset_id"], operation="LIGHTING")).json()
    pending = client.post(f"/v1/photo-drafts/{pending_photo_draft['draft_id']}/process-local?workspace_id=ws-a",
                          headers={**auth(), "Idempotency-Key": "lookbook-assembly-pending-02"}).json()
    unapproved = client.post(f"/v1/lookbook-drafts/{draft_id}/outputs?workspace_id=ws-a", headers=auth(), json={
        "photo_run_id": pending["run"]["run_id"], "page_order": 2,
    })
    assert unapproved.status_code == 409
    approved_pending = client.post(f"/v1/photo-drafts/{pending_photo_draft['draft_id']}/runs/{pending['run']['run_id']}/review/approve?workspace_id=ws-a",
                                   headers=auth(), json={})
    assert approved_pending.status_code == 200
    other_product = client.post("/v1/products", headers=auth(), json=
                                product_payload("ws-a", "ASSEMBLY-OTHER", "Other Coat", [product_image["asset_id"]])).json()
    other_variant = client.post(f"/v1/products/{other_product['product_id']}/variants", headers=auth(), json={
        "workspace_id": "ws-a", "sku": "ASSEMBLY-OTHER-BLACK-L",
        "option_values": {"color": "Black", "size": "L"}, "image_asset_ids": [],
    }).json()
    wrong_variant = client.post(f"/v1/lookbook-drafts/{draft_id}/outputs?workspace_id=ws-a", headers=auth(), json={
        "photo_run_id": pending["run"]["run_id"], "product_variant_id": other_variant["variant_id"], "page_order": 2,
    })
    assert wrong_variant.status_code == 409

    outputs = client.get(f"/v1/lookbook-drafts/{draft_id}/outputs?workspace_id=ws-a", headers=auth())
    assert outputs.status_code == 200 and outputs.json()["total"] == 1
    manifest_response = client.post(f"/v1/lookbook-drafts/{draft_id}/outputs/manifest?workspace_id=ws-a", headers=auth())
    assert manifest_response.status_code == 409
    package_before_review = client.post(f"/v1/lookbook-drafts/{draft_id}/outputs/package-export?workspace_id=ws-a", headers=auth())
    assert package_before_review.status_code == 409
    review_url = f"/v1/lookbook-drafts/{draft_id}/outputs/review?workspace_id=ws-a"
    pending_review = client.get(review_url, headers=auth())
    assert pending_review.status_code == 200 and pending_review.json()["status"] == "pending_review"
    client.post("/v1/workspaces/ws-a/members", headers=auth(), json={"user_id": "user-b", "role": "viewer"})
    viewer_review = client.get(review_url, headers=auth("token-user-b"))
    assert viewer_review.status_code == 200
    submitted = client.post(f"/v1/lookbook-drafts/{draft_id}/outputs/submit?workspace_id=ws-a", headers=auth())
    assert submitted.status_code == 200 and submitted.json()["status"] == "in_review"
    # Simulate out-of-band page-order corruption: the submitted snapshot must bind order,
    # not merely output count and immutable AssetVersion identity.
    import sqlite3
    with sqlite3.connect(asset_env / "assets.sqlite3") as db:
        db.execute("DROP TRIGGER trg_lookbook_outputs_no_update")
        db.execute("UPDATE lookbook_output_assets SET page_order=2 WHERE output_item_id=?", (item["output_item_id"],))
        db.commit()
    reordered_snapshot = client.get(review_url, headers=auth())
    assert reordered_snapshot.status_code == 200 and reordered_snapshot.json()["status"] == "integrity_error"
    with sqlite3.connect(asset_env / "assets.sqlite3") as db:
        db.execute("DROP TRIGGER trg_lookbook_outputs_no_update")
        db.execute("UPDATE lookbook_output_assets SET page_order=1 WHERE output_item_id=?", (item["output_item_id"],))
        db.execute("""CREATE TRIGGER trg_lookbook_outputs_no_update BEFORE UPDATE ON lookbook_output_assets
            BEGIN SELECT RAISE(ABORT, 'lookbook output items are immutable; create a new draft to change assembly'); END""")
        db.commit()
    restored_order_snapshot = client.get(review_url, headers=auth())
    assert restored_order_snapshot.status_code == 200 and restored_order_snapshot.json()["status"] == "in_review"
    frozen_attach = client.post(f"/v1/lookbook-drafts/{draft_id}/outputs?workspace_id=ws-a", headers=auth(), json={
        "photo_run_id": pending["run"]["run_id"], "page_order": 2,
    })
    assert frozen_attach.status_code == 409 and "frozen after review submission" in frozen_attach.json()["detail"]
    import sqlite3
    with sqlite3.connect(asset_env / "assets.sqlite3") as db:
        storage_key = db.execute("SELECT storage_key FROM asset_versions WHERE version_id=?", (item["asset_version_id"],)).fetchone()[0]
    assembly_version_path = asset_env / "private" / storage_key
    assembly_version_bytes = assembly_version_path.read_bytes()
    damaged_assembly = bytearray(assembly_version_bytes); damaged_assembly[-1] ^= 0x01; assembly_version_path.write_bytes(damaged_assembly)
    integrity_review = client.get(review_url, headers=auth())
    assert integrity_review.status_code == 200 and integrity_review.json()["status"] == "integrity_error"
    integrity_approve = client.post(f"/v1/lookbook-drafts/{draft_id}/outputs/approve?workspace_id=ws-a",
                                    headers=auth(), json={})
    assert integrity_approve.status_code == 409
    assembly_version_path.write_bytes(assembly_version_bytes)
    restored_assembly_review = client.get(review_url, headers=auth())
    assert restored_assembly_review.status_code == 200 and restored_assembly_review.json()["status"] == "in_review"
    viewer_approve = client.post(f"/v1/lookbook-drafts/{draft_id}/outputs/approve?workspace_id=ws-a",
                                 headers=auth("token-user-b"), json={})
    assert viewer_approve.status_code == 403
    missing_reject_comment = client.post(f"/v1/lookbook-drafts/{draft_id}/outputs/reject?workspace_id=ws-a",
                                         headers=auth(), json={})
    assert missing_reject_comment.status_code == 409
    assembly_approved = client.post(f"/v1/lookbook-drafts/{draft_id}/outputs/approve?workspace_id=ws-a",
                                    headers=auth(), json={"comment": "Sequence checked against the approved brief."})
    assert assembly_approved.status_code == 200 and assembly_approved.json()["status"] == "approved"
    manifest_response = client.post(f"/v1/lookbook-drafts/{draft_id}/outputs/manifest?workspace_id=ws-a", headers=auth())
    assert manifest_response.status_code == 200, manifest_response.text
    manifest = manifest_response.json()["manifest"]
    assert manifest["manifest_type"] == "LOOKBOOK_APPROVED_PLAN_WITH_APPROVED_PHOTO_OUTPUTS"
    assert manifest["photo_outputs_individually_approved"] is True
    # L-07: every output in the export manifest says it is not AI generated (local photo processing, no provider)
    assert manifest["outputs"] and all(o["is_ai_generated"] is False and o["provider_dispatched"] is False for o in manifest["outputs"])
    assert manifest["output_assembly_approved"] is True
    assert manifest["output_assembly_approved_by"] == "user-a"
    assert manifest["publication_authorized"] is False
    assert manifest["commercial_rights_verified"] is False
    assert manifest["binary_files_included"] is False
    assert manifest["outputs"][0]["variant_sku"] == "ASSEMBLY-100-NAVY-M"
    assert manifest["manifest_version"] == 1
    assert manifest_response.json()["manifest_sha256"]
    viewer_package = client.post(f"/v1/lookbook-drafts/{draft_id}/outputs/package-export?workspace_id=ws-a", headers=auth("token-user-b"))
    assert viewer_package.status_code == 403
    package_response = client.post(f"/v1/lookbook-drafts/{draft_id}/outputs/package-export?workspace_id=ws-a", headers=auth())
    assert package_response.status_code == 200
    package_result = package_response.json()
    assert package_result["internal_use_only"] is True
    assert package_result["publication_authorized"] is False
    assert package_result["commercial_rights_verified"] is False
    from urllib.parse import urlsplit, parse_qs
    import io, zipfile
    package_parts = urlsplit(package_result["download_url"])
    package_download = client.get(f"{package_parts.path}?{package_parts.query}", headers=auth())
    assert package_download.status_code == 200
    assert package_download.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(package_download.content)) as archive:
        names = archive.namelist()
        assert "manifest.json" in names
        assert any(name.startswith("pages/page_001_") for name in names)
        private_manifest = json.loads(archive.read("manifest.json"))
        assert private_manifest["internal_use_only"] is True
        assert private_manifest["binary_files_included"] is True
        # L-07: the downloadable package carries the disclosure at the top and on every output
        assert private_manifest["is_ai_generated"] is False and private_manifest["provider_dispatched"] is False
        assert private_manifest["outputs"] and all(o["is_ai_generated"] is False for o in private_manifest["outputs"])
        assert private_manifest["publication_authorized"] is False
        assert private_manifest["commercial_rights_verified"] is False
        assert private_manifest["public_distribution_authorized"] is False
        assert private_manifest["outputs"][0]["checksum_sha256"] == item["checksum_sha256"]
        assert private_manifest["outputs"][0]["asset_id"] == item["asset_id"]
        assert private_manifest["outputs"][0]["asset_version_id"] == item["asset_version_id"]
        assert any(item["asset_version_id"] in name for name in names if name.startswith("pages/"))
    query = parse_qs(package_parts.query)
    tampered_download = client.get(f"{package_parts.path}?expires={query['expires'][0]}&signature={'0' * 64}", headers=auth())
    assert tampered_download.status_code == 403
    expired_download = client.get(f"{package_parts.path}?expires=1&signature={'0' * 64}", headers=auth())
    assert expired_download.status_code == 403
    package_history = client.get(f"/v1/lookbook-drafts/{draft_id}/outputs/exports?workspace_id=ws-a", headers=auth("token-user-b"))
    assert package_history.status_code == 200 and package_history.json()["total"] == 1
    # Signed URL use still requires current workspace membership; a revoked member
    # cannot reuse a previously issued link.
    unauthenticated_download = client.get(f"{package_parts.path}?{package_parts.query}")
    assert unauthenticated_download.status_code == 401
    viewer_download = client.get(f"{package_parts.path}?{package_parts.query}", headers=auth("token-user-b"))
    assert viewer_download.status_code == 200
    with sqlite3.connect(asset_env / "assets.sqlite3") as db:
        db.execute("DELETE FROM workspace_members WHERE workspace_id='ws-a' AND user_id='user-b'")
        db.commit()
    revoked_member_download = client.get(f"{package_parts.path}?{package_parts.query}", headers=auth("token-user-b"))
    assert revoked_member_download.status_code == 404
    with sqlite3.connect(asset_env / "assets.sqlite3") as db:
        db.execute("INSERT INTO workspace_members(workspace_id,user_id,role,created_at) VALUES('ws-a','user-b','viewer','test')")
        db.commit()
    with sqlite3.connect(asset_env / "assets.sqlite3") as db:
        package_key = db.execute("SELECT storage_key FROM lookbook_output_package_exports WHERE export_id=?", (package_result["export_id"],)).fetchone()[0]
    package_path = asset_env / "private" / "lookbook_exports" / package_key
    # Missing binary is surfaced independently from the retained immutable audit row.
    parked_package = package_path.with_suffix(".parked")
    package_path.rename(parked_package)
    missing_history = client.get(f"/v1/lookbook-drafts/{draft_id}/outputs/exports?workspace_id=ws-a", headers=auth())
    assert missing_history.status_code == 200 and missing_history.json()["items"][0]["status"] == "missing"
    parked_package.rename(package_path)
    available_history = client.get(f"/v1/lookbook-drafts/{draft_id}/outputs/exports?workspace_id=ws-a", headers=auth())
    assert available_history.status_code == 200 and available_history.json()["items"][0]["status"] == "available"
    package_bytes = package_path.read_bytes()
    package_path.write_bytes(package_bytes + b"tamper")
    tampered_file_download = client.get(f"{package_parts.path}?{package_parts.query}", headers=auth())
    assert tampered_file_download.status_code == 409
    package_path.write_bytes(package_bytes)
    # A symlink entry is rejected even if its target has identical bytes.
    outside_package = asset_env / "private" / "outside-lookbook.zip"
    outside_package.write_bytes(package_bytes)
    package_path.unlink()
    package_path.symlink_to(outside_package)
    symlink_download = client.get(f"{package_parts.path}?{package_parts.query}", headers=auth())
    assert symlink_download.status_code == 409
    package_path.unlink()
    outside_package.replace(package_path)
    terminal_reject = client.post(f"/v1/lookbook-drafts/{draft_id}/outputs/reject?workspace_id=ws-a",
                                  headers=auth(), json={"comment": "No"})
    assert terminal_reject.status_code == 409

    # L-08: an output under a rights report is neither exported nor packaged until an operator restores it.
    import app.config as _config
    export_urls = (f"/v1/lookbook-drafts/{draft_id}/outputs/package-export?workspace_id=ws-a",
                   f"/v1/lookbook-drafts/{draft_id}/outputs/manifest?workspace_id=ws-a")
    assert all(client.post(url, headers=auth()).status_code in (200, 201) for url in export_urls)      # fine before the report
    reported = client.post("/v1/content-reports", headers=auth("token-user-b"), json={"asset_id": item["asset_id"], "category": "copyright"})
    assert reported.status_code == 202
    for url in export_urls:
        held = client.post(url, headers=auth())
        assert held.status_code == 409 and "under review" in held.text, (url, held.status_code, held.text)
    attach_held = client.post(f"/v1/lookbook-drafts/{draft_id}/outputs?workspace_id=ws-a", headers=auth(), json={
        "photo_run_id": run_id, "product_variant_id": variant["variant_id"], "page_order": 2, "caption": "again"})
    assert attach_held.status_code == 409 and "under review" in attach_held.text, attach_held.text   # the hold, not the frozen assembly, is the reason
    original_ops = _config.OPS_ADMIN_USER_IDS
    _config.OPS_ADMIN_USER_IDS = ("user-a",)
    try:
        report_id = client.get("/internal/moderation/reports", headers=auth()).json()["items"][0]["report_id"]
        assert client.post(f"/internal/moderation/reports/{report_id}/resolve", headers=auth(), json={"decision": "restore"}).status_code == 200
    finally:
        _config.OPS_ADMIN_USER_IDS = original_ops
    assert all(client.post(url, headers=auth()).status_code in (200, 201) for url in export_urls)      # exportable again after the restore

    with sqlite3.connect(asset_env / "assets.sqlite3") as db:
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("UPDATE lookbook_output_assets SET caption='tampered' WHERE output_item_id=?", (item["output_item_id"],))
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("DELETE FROM lookbook_output_export_events WHERE draft_id=?", (draft_id,))
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("UPDATE lookbook_output_assembly_review_events SET comment='tampered' WHERE draft_id=?", (draft_id,))
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("UPDATE lookbook_output_package_exports SET package_sha256='tampered' WHERE export_id=?", (package_result["export_id"],))


def test_photo_output_review_reject_returns_the_documented_success_payload(asset_env):
    source = upload_image(name="photo-reject-source.png").json()
    draft = client.post(
        "/v1/photo-drafts", headers=auth(),
        json=photo_draft_payload(source["asset_id"], operation="ENHANCE"),
    ).json()
    processed = client.post(
        f"/v1/photo-drafts/{draft['draft_id']}/process-local?workspace_id=ws-a",
        headers={**auth(), "Idempotency-Key": "photo-reject-contract-01"},
    )
    assert processed.status_code == 200, processed.text
    run_id = processed.json()["run"]["run_id"]

    rejected = client.post(
        f"/v1/photo-drafts/{draft['draft_id']}/runs/{run_id}/review/reject?workspace_id=ws-a",
        headers=auth(), json={"comment": "The output does not meet the brief."},
    )
    assert rejected.status_code == 200, rejected.text
    payload = rejected.json()
    assert payload["run_id"] == run_id
    assert payload["status"] == "rejected"
    assert payload["output"]["asset_id"] == processed.json()["output_asset"]["asset_id"]
    assert payload["events"][0]["decision"] == "rejected"
    assert payload["events"][0]["comment"] == "The output does not meet the brief."


def test_lookbook_output_assembly_reject_returns_the_documented_success_payload(asset_env):
    source = upload_image(name="lookbook-reject-source.png").json()
    lookbook = client.post(
        "/v1/lookbook-drafts", headers=auth(),
        json=lookbook_payload([source["asset_id"]]),
    )
    assert lookbook.status_code == 201, lookbook.text
    draft_id = lookbook.json()["draft_id"]

    submitted_plan = client.post(
        f"/v1/lookbook-drafts/{draft_id}/submit?workspace_id=ws-a", headers=auth(),
    )
    assert submitted_plan.status_code == 200, submitted_plan.text
    approved_plan = client.post(
        f"/v1/lookbook-drafts/{draft_id}/approve?workspace_id=ws-a",
        headers=auth(), json={},
    )
    assert approved_plan.status_code == 200, approved_plan.text

    photo_draft = client.post(
        "/v1/photo-drafts", headers=auth(),
        json=photo_draft_payload(source["asset_id"], operation="ENHANCE"),
    ).json()
    processed = client.post(
        f"/v1/photo-drafts/{photo_draft['draft_id']}/process-local?workspace_id=ws-a",
        headers={**auth(), "Idempotency-Key": "lookbook-reject-contract-01"},
    )
    assert processed.status_code == 200, processed.text
    run_id = processed.json()["run"]["run_id"]
    approved_photo = client.post(
        f"/v1/photo-drafts/{photo_draft['draft_id']}/runs/{run_id}/review/approve?workspace_id=ws-a",
        headers=auth(), json={},
    )
    assert approved_photo.status_code == 200, approved_photo.text

    attached = client.post(
        f"/v1/lookbook-drafts/{draft_id}/outputs?workspace_id=ws-a",
        headers=auth(), json={"photo_run_id": run_id, "page_order": 1},
    )
    assert attached.status_code == 201, attached.text
    submitted = client.post(
        f"/v1/lookbook-drafts/{draft_id}/outputs/submit?workspace_id=ws-a", headers=auth(),
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["status"] == "in_review"

    rejected = client.post(
        f"/v1/lookbook-drafts/{draft_id}/outputs/reject?workspace_id=ws-a",
        headers=auth(), json={"comment": "The assembled sequence needs a new direction."},
    )
    assert rejected.status_code == 200, rejected.text
    payload = rejected.json()
    assert payload["draft_id"] == draft_id
    assert payload["status"] == "rejected"
    assert payload["output_count"] == 1
    assert payload["events"][0]["decision"] == "rejected"
    assert payload["events"][0]["comment"] == "The assembled sequence needs a new direction."


def test_authenticated_asset_version_preview_content_rechecks_membership(asset_env, monkeypatch):
    """Fetch-to-blob endpoint requires live Bearer membership, not a reusable signed URL."""
    source = image_bytes()
    asset = upload_image(name="authenticated-preview.png", data=source).json()
    versions = client.get(f"/v1/assets/{asset['asset_id']}/versions", headers=auth()).json()["items"]
    version_id = versions[0]["version_id"]
    path = f"/v1/assets/{asset['asset_id']}/versions/{version_id}/preview-content"

    assert client.get(path).status_code == 401
    allowed = client.get(path, headers=auth())
    assert allowed.status_code == 200
    assert allowed.content == source
    assert allowed.headers["cache-control"] == "private, no-store"

    from app.ports.workspace import SQLiteWorkspacePort
    monkeypatch.setattr(SQLiteWorkspacePort, "role", lambda self, workspace_id, user_id: None)  # membership revoked
    revoked = client.get(path, headers=auth())
    assert revoked.status_code == 404


def test_viewer_role_can_fetch_authenticated_asset_version_content(asset_env):
    asset = upload_image(name="viewer-preview.png", data=image_bytes()).json()
    added = client.post("/v1/workspaces/ws-a/members", headers=auth(),
                        json={"user_id": "user-b", "role": "viewer"})
    assert added.status_code == 201
    versions = client.get(f"/v1/assets/{asset['asset_id']}/versions", headers=auth()).json()["items"]
    version_id = versions[0]["version_id"]
    response = client.get(
        f"/v1/assets/{asset['asset_id']}/versions/{version_id}/preview-content",
        headers=auth("token-user-b"),
    )
    assert response.status_code == 200
    assert response.content == image_bytes()


def test_active_lookbook_product_reference_freezes_catalog_mutation_until_archive(asset_env):
    image_a = upload_image(name="product-snapshot-a.png").json()
    image_b = upload_image(name="product-snapshot-b.png", data=image_bytes((40, 120, 80))).json()
    product = client.post("/v1/products", headers=auth(), json=
                          product_payload("ws-a", "SNAPSHOT-001", "Snapshot Product", [image_a["asset_id"]])).json()
    draft = client.post("/v1/lookbook-drafts", headers=auth(), json=
                        lookbook_payload([], product_ids=[product["product_id"]])).json()

    changed = client.put(f"/v1/products/{product['product_id']}", headers=auth(), json=
                         product_payload("ws-a", "SNAPSHOT-002", "Changed Product", [image_b["asset_id"]]))
    assert changed.status_code == 409
    current = client.get(f"/v1/products/{product['product_id']}?workspace_id=ws-a", headers=auth()).json()
    assert current["sku"] == "SNAPSHOT-001"
    assert current["image_asset_ids"] == [image_a["asset_id"]]

    assert client.post(f"/v1/lookbook-drafts/{draft['draft_id']}/archive?workspace_id=ws-a", headers=auth()).status_code == 200
    resumed = client.put(f"/v1/products/{product['product_id']}", headers=auth(), json=
                         product_payload("ws-a", "SNAPSHOT-002", "Changed Product", [image_b["asset_id"]]))
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["image_asset_ids"] == [image_b["asset_id"]]


def test_active_lookbook_character_reference_freezes_character_mutation_until_archive(asset_env):
    image = upload_image(name="character-reference.png").json()
    product = client.post("/v1/products", headers=auth(), json=
                          product_payload("ws-a", "CHAR-REF-001", "Reference Product", [image["asset_id"]])).json()
    character_payload = {"identity": {"name": "Reference Character", "gender": "unspecified"},
                         "outfits": [], "asset_ids": []}
    character = client.post("/v1/workspaces/ws-a/characters", headers=auth(), json=character_payload).json()
    draft = client.post("/v1/lookbook-drafts", headers=auth(), json=
                        lookbook_payload([], product_ids=[product["product_id"]], character_id=character["character_id"])).json()

    changed = client.put(f"/v1/workspaces/ws-a/characters/{character['character_id']}", headers=auth(), json={
        "identity": {"name": "Mutated Character", "gender": "unspecified"}, "outfits": [], "asset_ids": []})
    assert changed.status_code == 409
    current = client.get(f"/v1/workspaces/ws-a/characters/{character['character_id']}", headers=auth()).json()
    assert current["identity"]["name"] == "Reference Character"

    assert client.post(f"/v1/lookbook-drafts/{draft['draft_id']}/archive?workspace_id=ws-a", headers=auth()).status_code == 200
    resumed = client.put(f"/v1/workspaces/ws-a/characters/{character['character_id']}", headers=auth(), json={
        "identity": {"name": "Mutated Character", "gender": "unspecified"}, "outfits": [], "asset_ids": []})
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["identity"]["name"] == "Mutated Character"


def test_workspace_relation_triggers_reject_cross_workspace_direct_sql_mutations(asset_env):
    import sqlite3
    from app.assets.store import _connect

    assert client.post("/v1/workspaces", headers=auth(), json={"workspace_id": "ws-b"}).status_code == 201
    image_a = upload_image(name="trigger-a.png").json()
    image_b_response = client.post("/v1/assets/images", headers=auth(), data={"workspace_id": "ws-b"},
                                   files={"file": ("trigger-b.png", image_bytes((90, 30, 120)), "application/octet-stream")})
    assert image_b_response.status_code == 201, image_b_response.text
    image_b = image_b_response.json()
    product_a = client.post("/v1/products", headers=auth(), json=
                            product_payload("ws-a", "TRIGGER-A", "A", [image_a["asset_id"]])).json()
    product_b = client.post("/v1/products", headers=auth(), json=
                            product_payload("ws-b", "TRIGGER-B", "B", [image_b["asset_id"]])).json()
    variant_b = client.post(f"/v1/products/{product_b['product_id']}/variants", headers=auth(), json={
        "workspace_id": "ws-b", "sku": "TRIGGER-B-V1", "option_values": {"size": "M"},
        "image_asset_ids": [image_b["asset_id"]]}).json()
    character_b = client.post("/v1/workspaces/ws-b/characters", headers=auth(), json={
        "identity": {"name": "B Character"}, "asset_ids": [image_b["asset_id"]]}).json()
    draft_a = client.post("/v1/lookbook-drafts", headers=auth(), json=
                          lookbook_payload([], product_ids=[product_a["product_id"]])).json()

    with _connect() as db:
        with pytest.raises(sqlite3.IntegrityError, match="product asset workspace mismatch"):
            db.execute("INSERT INTO product_assets(product_id,asset_id,sort_order,role) VALUES(?,?,?,?)",
                       (product_a["product_id"], image_b["asset_id"], 9, "gallery"))
        with pytest.raises(sqlite3.IntegrityError, match="product variant asset workspace mismatch"):
            db.execute("INSERT INTO product_variant_assets(variant_id,asset_id,sort_order) VALUES(?,?,?)",
                       (variant_b["variant_id"], image_a["asset_id"], 9))
        with pytest.raises(sqlite3.IntegrityError, match="character asset workspace mismatch"):
            db.execute("INSERT INTO character_assets(character_id,asset_id,relation,created_at) VALUES(?,?,?,?)",
                       (character_b["character_id"], image_a["asset_id"], "model", "now"))
        with pytest.raises(sqlite3.IntegrityError, match="lookbook asset workspace mismatch"):
            db.execute("INSERT INTO lookbook_draft_assets(draft_id,asset_id,role) VALUES(?,?,?)",
                       (draft_a["draft_id"], image_b["asset_id"], "product"))
        with pytest.raises(sqlite3.IntegrityError, match="lookbook entity workspace mismatch"):
            db.execute("INSERT INTO lookbook_draft_entities(draft_id,entity_type,entity_id) VALUES(?,?,?)",
                       (draft_a["draft_id"], "product", product_b["product_id"]))
