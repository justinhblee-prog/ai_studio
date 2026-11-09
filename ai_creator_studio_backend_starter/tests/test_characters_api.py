import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def auth(token="token-user-a"):
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def character_env(tmp_path, monkeypatch):
    import app.config as config
    monkeypatch.setattr(config, "ASSET_STORAGE_DIR", tmp_path / "private")
    monkeypatch.setattr(config, "ASSET_DATABASE_PATH", tmp_path / "characters.sqlite3")
    monkeypatch.setattr(config, "ASSET_SIGNING_SECRET", "s" * 48)
    monkeypatch.setattr(config, "asset_api_tokens", lambda: {"token-user-a":"user-a", "token-user-b":"user-b"})
    assert client.post("/v1/workspaces", headers=auth(), json={"workspace_id":"char-ws"}).status_code == 201
    return tmp_path


def payload(name="Mina"):
    return {"identity":{"name":name,"gender":"female","face_shape":"oval","hairstyle":"long","body_type":"athletic","skin_tone":"medium"},
            "outfits":[{"id":"outfit-1","name":"Casual","category":"casual","top":"white shirt"}],
            "active_outfit_id":"outfit-1","asset_ids":[]}


def test_character_crud_and_persistence(character_env):
    created = client.post("/v1/workspaces/char-ws/characters", headers=auth(), json=payload())
    assert created.status_code == 201, created.text
    item = created.json()
    assert item["identity"]["name"] == "Mina"
    assert item["active_outfit_id"] == "outfit-1"
    listed = client.get("/v1/workspaces/char-ws/characters", headers=auth())
    assert len(listed.json()["items"]) == 1
    updated = payload("Mina 2")
    assert client.put(f"/v1/workspaces/char-ws/characters/{item['character_id']}", headers=auth(), json=updated).json()["identity"]["name"] == "Mina 2"
    assert client.get(f"/v1/workspaces/char-ws/characters/{item['character_id']}", headers=auth()).status_code == 200
    assert client.delete(f"/v1/workspaces/char-ws/characters/{item['character_id']}", headers=auth()).status_code == 204
    assert client.get(f"/v1/workspaces/char-ws/characters/{item['character_id']}", headers=auth()).status_code == 404


def test_character_workspace_isolation(character_env):
    item = client.post("/v1/workspaces/char-ws/characters", headers=auth(), json=payload()).json()
    assert client.get(f"/v1/workspaces/char-ws/characters/{item['character_id']}", headers=auth("token-user-b")).status_code == 404


def test_viewer_can_read_but_cannot_write(character_env):
    item = client.post("/v1/workspaces/char-ws/characters", headers=auth(), json=payload()).json()
    assert client.post("/v1/workspaces/char-ws/members", headers=auth(), json={"user_id":"user-b","role":"viewer"}).status_code == 201
    assert client.get("/v1/workspaces/char-ws/characters", headers=auth("token-user-b")).status_code == 200
    assert client.put(f"/v1/workspaces/char-ws/characters/{item['character_id']}", headers=auth("token-user-b"), json=payload()).status_code == 403


def test_invalid_active_outfit_rejected(character_env):
    body = payload()
    body["active_outfit_id"] = "missing"
    assert client.post("/v1/workspaces/char-ws/characters", headers=auth(), json=body).status_code == 422


def test_character_requires_auth(character_env):
    assert client.get("/v1/workspaces/char-ws/characters").status_code == 401


def _glb_bytes():
    import json
    import struct
    doc = json.dumps({"asset": {"version": "2.0"}}, separators=(",", ":")).encode()
    doc += b" " * ((4 - len(doc) % 4) % 4)
    chunk = struct.pack("<II", len(doc), 0x4E4F534A) + doc
    return b"glTF" + struct.pack("<II", 2, 12 + len(chunk)) + chunk


def test_asset_delete_is_refused_while_an_active_character_links_it(character_env):
    up = client.post("/v1/assets", headers=auth(), data={"workspace_id": "char-ws"},
                     files={"file": ("a.glb", _glb_bytes(), "application/octet-stream")})
    assert up.status_code == 201, up.text
    asset_id = up.json()["asset_id"]
    body = payload()
    body["asset_ids"] = [asset_id]
    created = client.post("/v1/workspaces/char-ws/characters", headers=auth(), json=body)
    assert created.status_code == 201, created.text
    blocked = client.delete(f"/v1/assets/{asset_id}", headers=auth())
    assert blocked.status_code == 409 and "Character" in blocked.text, blocked.text
    assert client.delete(f"/v1/workspaces/char-ws/characters/{created.json()['character_id']}", headers=auth()).status_code == 204
    assert client.delete(f"/v1/assets/{asset_id}", headers=auth()).status_code == 204
