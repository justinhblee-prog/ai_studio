"""Authorization for operations the generic matrix could not decide.

The generic matrix hits photo/lookbook/variant routes with ids that do not exist, so the
server answers 422/409 before authorization is involved. Here the objects really exist in
a workspace owned by user-a, and we check that a non-member and a viewer cannot reach or
change them.
"""
import io

import pytest
from PIL import Image
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
WS = "az-ws"


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def _png():
    buf = io.BytesIO()
    Image.new("RGB", (32, 32), (20, 80, 140)).save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def env(tmp_path, monkeypatch):
    import app.config as config
    monkeypatch.setattr(config, "ASSET_STORAGE_DIR", tmp_path / "private")
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path / "outputs")
    monkeypatch.setattr(config, "ASSET_DATABASE_PATH", tmp_path / "a.sqlite3")
    monkeypatch.setattr(config, "GENERATION_DATABASE_PATH", None)
    monkeypatch.setattr(config, "ASSET_SIGNING_SECRET", "z" * 48)
    monkeypatch.setattr(config, "asset_api_tokens", lambda: {"tok-a": "user-a", "tok-b": "user-b"})
    monkeypatch.setattr(config, "PROVIDER_MODE", "mock")
    assert client.post("/v1/workspaces", headers=auth("tok-a"), json={"workspace_id": WS}).status_code == 201
    img = client.post("/v1/assets/images", headers=auth("tok-a"), data={"workspace_id": WS},
                      files={"file": ("p.png", _png(), "image/png")})
    assert img.status_code == 201, img.text
    image_id = img.json()["asset_id"]
    product = client.post("/v1/products", headers=auth("tok-a"), json={
        "workspace_id": WS, "sku": "AZ-1", "name": "AZ-1", "category": "apparel", "image_asset_ids": [image_id]})
    assert product.status_code == 201, product.text
    product_id = product.json()["product_id"]
    variant = client.post(f"/v1/products/{product_id}/variants", headers=auth("tok-a"), json={
        "workspace_id": WS, "sku": "AZ-1-S", "option_values": {"size": "S"}, "image_asset_ids": [image_id]})
    assert variant.status_code == 201, variant.text
    photo = client.post("/v1/photo-drafts", headers=auth("tok-a"), json={
        "workspace_id": WS, "source_asset_id": image_id, "operation": "ENHANCE"})
    lookbook = client.post("/v1/lookbook-drafts", headers=auth("tok-a"), json={
        "workspace_id": WS, "title": "AZ", "product_ids": [product_id], "product_asset_ids": [image_id]})
    return {"image": image_id, "product": product_id, "variant": variant.json()["variant_id"],
            "photo": photo, "lookbook": lookbook}


def _requests(env):
    p, v = env["product"], env["variant"]
    reqs = [
        ("post", f"/v1/products/{p}/variants", {"workspace_id": WS, "sku": "AZ-1-M", "option_values": {"size": "M"}}),
        ("put", f"/v1/products/{p}/variants/{v}", {"workspace_id": WS, "sku": "AZ-1-S", "option_values": {"size": "L"}}),
        ("post", "/v1/lookbook-drafts", {"workspace_id": WS, "title": "x", "product_ids": [p]}),
    ]
    if env["photo"].status_code == 201:
        d = env["photo"].json()["draft_id"]
        reqs.append(("post", f"/v1/photo-drafts/{d}/process-local?workspace_id={WS}", None))
    if env["lookbook"].status_code == 201:
        d = env["lookbook"].json()["draft_id"]
        reqs.append(("put", f"/v1/lookbook-drafts/{d}", {"workspace_id": WS, "title": "changed", "product_ids": [p]}))
    return reqs


def _send(method, url, body, token):
    kw = {"headers": {**auth(token), "Idempotency-Key": "az-key-1"}}
    if body is not None:
        kw["json"] = body
    return client.request(method.upper(), url, **kw)


def test_seed_objects_exist(env):
    assert env["photo"].status_code == 201, env["photo"].text
    assert env["lookbook"].status_code == 201, env["lookbook"].text


def test_non_member_is_rejected_on_seeded_objects(env):
    reqs = _requests(env)
    assert len(reqs) == 5
    for method, url, body in reqs:
        resp = _send(method, url, body, "tok-b")
        assert resp.status_code in (403, 404), (method, url, resp.status_code, resp.text)


def test_viewer_cannot_write_seeded_objects(env):
    assert client.post(f"/v1/workspaces/{WS}/members", headers=auth("tok-a"),
                       json={"user_id": "user-b", "role": "viewer"}).status_code == 201
    for method, url, body in _requests(env):
        resp = _send(method, url, body, "tok-b")
        assert resp.status_code == 403, (method, url, resp.status_code, resp.text)
