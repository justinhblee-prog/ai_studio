import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def auth(token="token-user-a"):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def project_env(tmp_path, monkeypatch):
    import app.config as config
    monkeypatch.setattr(config, "ASSET_STORAGE_DIR", tmp_path / "private")
    monkeypatch.setattr(config, "ASSET_DATABASE_PATH", tmp_path / "projects.sqlite3")
    monkeypatch.setattr(config, "ASSET_SIGNING_SECRET", "s" * 48)
    monkeypatch.setattr(config, "asset_api_tokens", lambda: {
        "token-user-a": "user-a", "token-user-b": "user-b"
    })
    created = client.post("/v1/workspaces", headers=auth(), json={"workspace_id": "project-ws"})
    assert created.status_code == 201, created.text
    return tmp_path


def create_project():
    return client.post("/v1/projects", headers=auth(), json={
        "workspace_id": "project-ws", "name": "Summer Campaign",
        "project_type": "campaign", "description": "SS campaign",
        "external_reference": "ERP-123",
    })


def test_project_crud_and_status_filter(project_env):
    created = create_project()
    assert created.status_code == 201, created.text
    item = created.json()
    assert item["project_id"].startswith("prj_")
    assert item["status"] == "ACTIVE"
    assert item["created_by"] == "user-a"
    assert item["external_reference"] == "ERP-123"

    listed = client.get("/v1/projects?workspace_id=project-ws", headers=auth())
    assert listed.status_code == 200 and len(listed.json()["items"]) == 1
    updated = client.put(f"/v1/projects/{item['project_id']}", headers=auth(), json={
        "name": "Summer Campaign Final", "project_type": "campaign",
        "status": "ARCHIVED", "description": "Approved archive"
    })
    assert updated.status_code == 200
    assert updated.json()["status"] == "ARCHIVED"
    assert client.get("/v1/projects?workspace_id=project-ws&status=ACTIVE", headers=auth()).json()["items"] == []
    assert len(client.get("/v1/projects?workspace_id=project-ws&status=ARCHIVED", headers=auth()).json()["items"]) == 1


def test_project_is_workspace_scoped(project_env):
    item = create_project().json()
    assert client.get(f"/v1/projects/{item['project_id']}", headers=auth("token-user-b")).status_code == 404
    assert client.get("/v1/projects?workspace_id=missing-ws", headers=auth()).status_code == 404


def test_viewer_can_read_but_cannot_create_or_update_project(project_env):
    item = create_project().json()
    assert client.post("/v1/workspaces/project-ws/members", headers=auth(), json={
        "user_id": "user-b", "role": "viewer"
    }).status_code == 201
    assert client.get(f"/v1/projects/{item['project_id']}", headers=auth("token-user-b")).status_code == 200
    assert client.post("/v1/projects", headers=auth("token-user-b"), json={
        "workspace_id": "project-ws", "name": "No write", "project_type": "general"
    }).status_code == 403
    assert client.put(f"/v1/projects/{item['project_id']}", headers=auth("token-user-b"), json={
        "name": "No write", "project_type": "general", "status": "ACTIVE"
    }).status_code == 403


def test_project_requires_authentication(project_env):
    assert client.get("/v1/projects?workspace_id=project-ws").status_code == 401


def test_project_rejects_invalid_status_and_extra_fields(project_env):
    item = create_project().json()
    bad_status = client.put(f"/v1/projects/{item['project_id']}", headers=auth(), json={
        "name": "X", "project_type": "campaign", "status": "DELETED"
    })
    assert bad_status.status_code == 422
    bad_extra = client.post("/v1/projects", headers=auth(), json={
        "workspace_id": "project-ws", "name": "X", "unexpected": True
    })
    assert bad_extra.status_code == 422
