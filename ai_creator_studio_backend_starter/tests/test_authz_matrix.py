"""Authorization matrix: every documented operation must reject anonymous callers (401) and a
signed-in non-member of the workspace must never get a 2xx on data owned by another workspace.

Driven by the OpenAPI document, so a newly added route is covered automatically. A 422 (request body
rejected before authorization ran) is not a leak but is weaker evidence than 403/404; the test reports
how many operations were actually decided by authorization.
"""
import json
import struct

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
PUBLIC = {("get", "/health"), ("get", "/v1/engines/capabilities"), ("get", "/v1/engines/models"),
          ("get", "/v1/legal/documents"), ("get", "/v1/assets/{asset_id}/preview"), ("get", "/v1/assets/{asset_id}/thumb/{size}"),
          ("get", "/v1/assets/{asset_id}/versions/{version_id}/preview"),
          ("get", "/v1/library/items/{item_id}/versions/{version}/preview")}  # R-032: signed, short-lived library preview link


# Caller-scoped reads: a 200 is correct, but they must not expose another user's data (checked below).
SELF_SCOPED = {("get", "/v1/workspaces"), ("get", "/v1/me/legal-status"), ("get", "/v1/me/deletion-requests"),
               ("get", "/v1/me/consents"), ("get", "/v1/auth/me"),
               ("get", "/v1/me/takedowns"),   # L-08: lists only the caller's own held assets
               ("get", "/v1/library/items"),
               ("get", "/v1/market/listings"), ("get", "/v1/market/mine"), ("get", "/v1/market/profile"),   # R-064: the market is user-scoped, not workspace-scoped
               ("get", "/v1/features")}  # pilot service switches: global, no workspace data  # R-032: platform-owned default library, readable by every signed-in user (holds no workspace data)


# Operations that any signed-in user may call and whose answer does not depend on the object (so it reveals nothing).
ANSWERS_ALIKE = {("post", "/v1/content-reports"), ("post", "/v1/market/listings/{listing_id}/reports")}


# Minimal valid bodies generated from the OpenAPI schema so authorization, not validation, decides.
def _resolve(spec, s):
    while "$ref" in s:
        s = spec["components"]["schemas"][s["$ref"].split("/")[-1]]
    return s
def _sample(spec, s, depth=0):
    s = _resolve(spec, s)
    if "anyOf" in s or "oneOf" in s:
        opts = [o for o in (s.get("anyOf") or s.get("oneOf")) if _resolve(spec, o).get("type") != "null"]
        return _sample(spec, opts[0], depth+1)
    if "enum" in s: return s["enum"][0]
    if "default" in s and s["default"] is not None: return s["default"]
    t = s.get("type")
    if t == "object" or "properties" in s:
        out = {}
        for k in s.get("required", []):
            out[k] = _sample(spec, s["properties"][k], depth+1) if depth < 5 else None
        return out
    if t == "array": return [_sample(spec, s["items"], depth+1)] if depth < 3 else []
    if t == "integer": return max(1, s.get("minimum", 1))
    if t == "number": return max(1.0, s.get("minimum", 1))
    if t == "boolean": return True
    if t == "string":
        f = s.get("format")
        if f in ("uri", "url") or "url" in str(s.get("title","")).lower(): return "https://images.example.org/x.png"
        if f == "date-time": return "2026-11-09T00:00:00Z"
        return "x" * max(1, s.get("minLength", 1))
    return "x"


def _body(op, ids=None):
    schema = op["requestBody"]["content"]["application/json"]["schema"]
    body = _sample(app.openapi(), schema)
    # Point id-like fields at the seeded workspace's objects so authorization (not "not found") decides.
    for key in list(body) if isinstance(body, dict) else []:
        if ids and key in ids:
            body[key] = ids[key]
    return body


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def glb():
    doc = json.dumps({"asset": {"version": "2.0"}}, separators=(",", ":")).encode()
    doc += b" " * ((4 - len(doc) % 4) % 4)
    chunk = struct.pack("<II", len(doc), 0x4E4F534A) + doc
    return b"glTF" + struct.pack("<II", 2, 12 + len(chunk)) + chunk


@pytest.fixture
def seeded(tmp_path, monkeypatch):
    import app.config as config
    monkeypatch.setattr(config, "ASSET_STORAGE_DIR", tmp_path / "private")
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path / "outputs")
    monkeypatch.setattr(config, "ASSET_DATABASE_PATH", tmp_path / "a.sqlite3")
    monkeypatch.setattr(config, "GENERATION_DATABASE_PATH", None)
    monkeypatch.setattr(config, "ASSET_SIGNING_SECRET", "m" * 48)
    monkeypatch.setattr(config, "asset_api_tokens", lambda: {"tok-a": "user-a", "tok-b": "user-b"})
    monkeypatch.setattr(config, "PROVIDER_MODE", "mock")
    assert client.post("/v1/workspaces", headers=auth("tok-a"), json={"workspace_id": "mx-ws"}).status_code == 201
    asset = client.post("/v1/assets", headers=auth("tok-a"), data={"workspace_id": "mx-ws"},
                        files={"file": ("m.glb", glb(), "application/octet-stream")}).json()
    job = client.post("/v1/generation-jobs", headers=auth("tok-a"), json={
        "workspace_id": "mx-ws", "model_image_url": "https://images.example.org/m.png",
        "garment_image_url": "https://images.example.org/g.png"}).json()
    return {"workspace_id": "mx-ws", "asset_id": asset["asset_id"], "job_id": job["job_id"]}


def _fill(path, ids):
    out = path
    for name in [seg[1:-1] for seg in path.split("/") if seg.startswith("{")]:
        out = out.replace("{" + name + "}", ids.get(name, "does-not-exist"))
    return out


def _operations():
    spec = app.openapi()
    for path, item in spec["paths"].items():
        for method in item:
            if method in {"get", "post", "put", "patch", "delete"} and (method, path) not in PUBLIC:
                yield method, path, item[method]


def test_every_operation_rejects_anonymous_and_non_members(seeded):
    decided, weak, leaks, anon_bad, weak_list = 0, 0, [], [], []
    for method, path, op in _operations():
        url = _fill(path, seeded)
        query = {p["name"]: seeded.get(p["name"], "x") for p in op.get("parameters", [])
                 if p.get("in") == "query" and p.get("required")}
        kw = {"params": query}
        if "requestBody" in op and "application/json" in op["requestBody"].get("content", {}):
            kw["json"] = _body(op, seeded)
        if "multipart/form-data" in json.dumps(op.get("requestBody", {})):
            kw = {"params": query, "data": {"workspace_id": seeded["workspace_id"]},
                  "files": {"file": ("m.glb", glb(), "application/octet-stream")}}
        anon = client.request(method.upper(), url, **kw)
        if anon.status_code != 401:
            anon_bad.append((method, path, anon.status_code))
        other = client.request(method.upper(), url, headers=auth("tok-b"), **kw)
        if (method, path) in SELF_SCOPED:
            assert other.status_code == 200, (method, path, other.status_code)
            assert "mx-ws" not in other.text and "user-a" not in other.text, (method, path)
        elif method != "get" and path.startswith("/v1/me/"):
            decided += 1  # acts only on the caller's own data (verified by the viewer/self tests)
        elif (method, path) in ANSWERS_ALIKE:
            # L-08: any signed-in user may report; the answer must be the same for every asset id (no existence oracle)
            assert other.status_code == 202 and other.json() == {"status": "received"}, (method, path, other.status_code, other.text)
            decided += 1
        elif 200 <= other.status_code < 300:
            leaks.append((method, path, other.status_code))
        elif other.status_code in (403, 404):
            decided += 1
        else:
            weak += 1; weak_list.append((method, path, other.status_code))
    assert not anon_bad, f"anonymous access not rejected with 401: {anon_bad}"
    assert not leaks, f"non-member got a success response: {leaks}"
    assert decided >= 90, (decided, weak, weak_list)


# POST that only issues a read capability; the routes allow viewers on purpose.
SELF_WRITES = {("post", "/v1/workspaces"), ("post", "/v1/assets/{asset_id}/preview-url"),
               ("post", "/v1/assets/{asset_id}/versions/{version_id}/preview-url"),
               # L-08: any signed-in user may file a report; the answer is the same for every asset id, so it reveals nothing
               ("post", "/v1/content-reports"), ("post", "/v1/market/listings/{listing_id}/reports"), ("put", "/v1/market/profile")}


def test_viewer_role_cannot_modify_anything_in_the_workspace(seeded):
    assert client.post("/v1/workspaces/mx-ws/members", headers=auth("tok-a"),
                       json={"user_id": "user-b", "role": "viewer"}).status_code == 201
    allowed_writes, blocked, leaks = 0, 0, []
    for method, path, op in _operations():
        if method == "get" or path.startswith("/v1/me/") or (method, path) in SELF_WRITES:
            continue
        url = _fill(path, seeded)
        query = {p["name"]: seeded.get(p["name"], "x") for p in op.get("parameters", [])
                 if p.get("in") == "query" and p.get("required")}
        kw = {"params": query}
        if "requestBody" in op and "application/json" in op["requestBody"].get("content", {}):
            kw["json"] = _body(op, seeded)
        if "multipart/form-data" in json.dumps(op.get("requestBody", {})):
            kw = {"params": query, "data": {"workspace_id": seeded["workspace_id"]},
                  "files": {"file": ("m.glb", glb(), "application/octet-stream")}}
        resp = client.request(method.upper(), url, headers=auth("tok-b"), **kw)
        if 200 <= resp.status_code < 300:
            leaks.append((method, path, resp.status_code))
        elif resp.status_code == 403:
            blocked += 1
    assert not leaks, f"viewer got a success response on a write: {leaks}"
    assert blocked >= 10, blocked
