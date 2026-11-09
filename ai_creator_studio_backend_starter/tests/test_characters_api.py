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
