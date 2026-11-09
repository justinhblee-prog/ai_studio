import io

import pytest
from PIL import Image
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def auth(token="token-user-a"):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def assignment_env(tmp_path, monkeypatch):
    import app.config as config
    monkeypatch.setattr(config, "ASSET_STORAGE_DIR", tmp_path / "private")
    monkeypatch.setattr(config, "ASSET_DATABASE_PATH", tmp_path / "assignments.sqlite3")
    monkeypatch.setattr(config, "ASSET_SIGNING_SECRET", "p" * 48)
    monkeypatch.setattr(config, "asset_api_tokens", lambda: {"token-user-a": "user-a", "token-user-b": "user-b"})
    assert client.post("/v1/workspaces", headers=auth(), json={"workspace_id": "assign-ws"}).status_code == 201
    project = client.post("/v1/projects", headers=auth(), json={"workspace_id": "assign-ws", "name": "Spring Lookbook"})
    assert project.status_code == 201, project.text
    buffer = io.BytesIO()
    Image.new("RGB", (32, 32), (20, 80, 140)).save(buffer, format="PNG")
    image = client.post("/v1/assets/images", headers=auth(), data={"workspace_id": "assign-ws"},
                        files={"file": ("product.png", buffer.getvalue(), "image/png")})
    assert image.status_code == 201, image.text
    return {"project": project.json(), "image": image.json()}


def create_product(image_id, sku):
    response = client.post("/v1/products", headers=auth(), json={
        "workspace_id": "assign-ws", "sku": sku, "name": sku,
        "category": "apparel", "image_asset_ids": [image_id],
    })
    assert response.status_code == 201, response.text
    return response.json()


def test_project_product_assignment_replace_history_and_archive_guard(assignment_env):
    project = assignment_env["project"]
    image_id = assignment_env["image"]["asset_id"]
    first = create_product(image_id, "ASSIGN-001")
    second = create_product(image_id, "ASSIGN-002")

    assigned = client.put(f"/v1/projects/{project['project_id']}/products", headers=auth(),
                          json={"product_ids": [first["product_id"], second["product_id"]]})
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()["total"] == 2
    read = client.get(f"/v1/projects/{project['project_id']}/products", headers=auth()).json()
    assert [item["product_id"] for item in read["items"]] == [first["product_id"], second["product_id"]]
    reordered = client.put(f"/v1/projects/{project['project_id']}/products", headers=auth(),
                           json={"product_ids": [second["product_id"], first["product_id"]]})
    assert [item["product_id"] for item in reordered.json()["items"]] == [second["product_id"], first["product_id"]]
    blocked = client.post(f"/v1/products/{first['product_id']}/archive?workspace_id=assign-ws", headers=auth())
    assert blocked.status_code == 409

    replaced = client.put(f"/v1/projects/{project['project_id']}/products", headers=auth(),
                          json={"product_ids": [second["product_id"]]})
    assert replaced.status_code == 200 and replaced.json()["total"] == 1
    events = client.get(f"/v1/projects/{project['project_id']}/product-events", headers=auth()).json()
    assert events["total"] == 3
    assert events["items"][0]["details"]["removed"] == [first["product_id"]]
    assert events["items"][1]["details"]["reordered"] is True
    assert client.post(f"/v1/products/{first['product_id']}/archive?workspace_id=assign-ws", headers=auth()).status_code == 200

    cleared = client.put(f"/v1/projects/{project['project_id']}/products", headers=auth(), json={"product_ids": []})
    assert cleared.status_code == 200 and cleared.json()["total"] == 0


def test_project_product_assignment_workspace_and_role_guards(assignment_env):
    project = assignment_env["project"]
    image_id = assignment_env["image"]["asset_id"]
    product = create_product(image_id, "ASSIGN-003")
    invalid = client.put(f"/v1/projects/{project['project_id']}/products", headers=auth(),
                         json={"product_ids": ["prd_not_in_workspace"]})
    assert invalid.status_code == 422
    assert client.post("/v1/workspaces/assign-ws/members", headers=auth(),
                       json={"user_id": "user-b", "role": "viewer"}).status_code == 201
    denied = client.put(f"/v1/projects/{project['project_id']}/products", headers=auth("token-user-b"),
                        json={"product_ids": [product["product_id"]]})
    assert denied.status_code == 403
    readable = client.get(f"/v1/projects/{project['project_id']}/products", headers=auth("token-user-b"))
    assert readable.status_code == 200


def test_archived_project_releases_product_archive_guard(assignment_env):
    project = assignment_env["project"]
    product = create_product(assignment_env["image"]["asset_id"], "ASSIGN-004")
    assert client.put(f"/v1/projects/{project['project_id']}/products", headers=auth(),
                      json={"product_ids": [product["product_id"]]}).status_code == 200
    archived_project = client.put(f"/v1/projects/{project['project_id']}", headers=auth(), json={
        "name": "Spring Lookbook", "project_type": "general", "status": "ARCHIVED"
    })
    assert archived_project.status_code == 200
    archived_product = client.post(f"/v1/products/{product['product_id']}/archive?workspace_id=assign-ws", headers=auth())
    assert archived_product.status_code == 200
    assert client.get(f"/v1/projects/{project['project_id']}/products", headers=auth()).json()["total"] == 0
