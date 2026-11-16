"""R-065: the workspace / account export ZIP: contents, scope, limits, expiry, roles, audit."""
import hashlib
import io
import json
import sqlite3
import zipfile
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import config
from app.main import app
from tests.test_photo_steps_api import auth, env  # noqa: F401  (wa: owner a + viewer c, wb: owner b)

client = TestClient(app)


@pytest.fixture
def team(env, monkeypatch):
    """wa: owner a, viewer c, editor d, admin e; wb: owner b."""
    monkeypatch.setattr(config, "asset_api_tokens", lambda: {"token-a": "user-a", "token-b": "user-b", "token-c": "user-c", "token-d": "user-d", "token-e": "user-e"})
    assert client.post("/v1/workspaces/wa/members", headers=auth("a"), json={"user_id": "user-d", "role": "editor"}).status_code == 201
    assert client.post("/v1/workspaces/wa/members", headers=auth("a"), json={"user_id": "user-e", "role": "admin"}).status_code == 201
    return env


def gps_jpeg():
    ex = Image.Exif(); ex[0x010F] = "Cam"
    ifd = ex.get_ifd(0x8825); ifd[1] = "N"; ifd[2] = (37.0, 33.0, 59.0); ex[0x8825] = ifd
    buf = io.BytesIO(); Image.new("RGB", (16, 16), (200, 10, 10)).save(buf, format="JPEG", exif=ex.tobytes()); return buf.getvalue()


def make_export(who="a", ws="wa"):
    return client.post(f"/v1/workspaces/{ws}/exports", headers=auth(who))


def zip_of(response):
    return zipfile.ZipFile(io.BytesIO(response.content))


def audit(env_):
    with sqlite3.connect(config.ASSET_DATABASE_PATH) as c:
        return c.execute("SELECT event, scope, request_id, subject_hash, size_bytes FROM data_lifecycle_audit ORDER BY event_id").fetchall()


def test_a_workspace_export_holds_the_manifest_the_tables_and_every_original_file(team):
    original = gps_jpeg()
    up = client.post("/v1/workspaces/wa/library", headers=auth("a"), data={"kind": "model", "name": "내 모델", "rights_confirmed": "true", "attrs": json.dumps({"category": "top"})},
                     files={"file": ("m.jpg", original, "image/jpeg")}).json()
    r = make_export()
    assert r.status_code == 201, r.text
    ex = r.json()
    assert ex["scope"] == "workspace" and ex["workspace_id"] == "wa" and ex["status"] == "ready" and ex["download_path"] == f"/v1/exports/{ex['export_id']}/download"
    assert ex["summary"]["assets_included"] >= 2 and "workspace_library_items" in ex["summary"]["tables_included"]
    dl = client.get(ex["download_path"], headers=auth("a"))
    assert dl.status_code == 200 and dl.headers["content-type"] == "application/zip" and "attachment" in dl.headers["content-disposition"]
    assert hashlib.sha256(dl.content).hexdigest() == ex["checksum_sha256"] and len(dl.content) == ex["size_bytes"]
    z = zip_of(dl)
    assert z.testzip() is None
    manifest = json.loads(z.read("manifest.json"))
    assert manifest["workspace_id"] == "wa" and manifest["scope"] == "workspace" and manifest["format"] == 1
    entry = next(a for a in manifest["assets"] if a["asset_id"] == up["asset_id"])
    assert entry["original_filename"] == "m.jpg" and entry["path"] == f"assets/{up['asset_id']}.jpg"
    stored = z.read(entry["path"])
    assert stored == original and hashlib.sha256(stored).hexdigest() == entry["sha256"], "the stored original, byte for byte (the GPS position is still in it)"
    items = json.loads(z.read("data/workspace_library_items.json"))
    assert items[0]["name"] == "내 모델" and json.loads(items[0]["attrs_json"]) == {"category": "top"}
    assert "storage_key" not in json.dumps(json.loads(z.read("data/assets.json")))
    assert {m["user_id"] for m in json.loads(z.read("data/workspace_members.json"))} == {"user-a", "user-c", "user-d", "user-e"}
    assert any("workspace_id column" in n for n in manifest["notes"]) and isinstance(manifest["not_included_tables"], list)
    assert all("wb" not in n for n in z.namelist())


def test_nothing_of_another_workspace_or_another_account_is_included(team):
    client.post("/v1/workspaces/wb/library", headers=auth("b"), data={"kind": "model", "name": "OTHER-WS-ITEM", "rights_confirmed": "true"},
                files={"file": ("o.png", gps_jpeg(), "image/jpeg")})
    client.put("/v1/me/consents/ai_training", headers=auth("b"), json={"granted": True})
    z = zip_of(client.get(make_export().json()["download_path"], headers=auth("a")))
    blob = b"".join(z.read(n) for n in z.namelist() if not n.startswith("assets/"))
    assert b"OTHER-WS-ITEM" not in blob and b"user-b" not in blob and "data/consents.json" not in z.namelist()


def test_roles_and_scopes(team):
    assert make_export("e").status_code == 201, "an admin may"
    for who in "cd":
        assert make_export(who).status_code == 403, "viewer / editor"
    assert make_export("b").status_code in (403, 404) and client.post("/v1/workspaces/wa/exports").status_code == 401
    ex = make_export("a").json()
    path = ex["download_path"]
    assert client.get(path, headers=auth("e")).status_code == 200, "an admin can download the owner's export"
    for who in "bcd":
        assert client.get(path, headers=auth(who)).status_code == 404, "not yours looks like not there"
    assert client.get(path).status_code == 401
    assert client.get(f"/v1/workspaces/wa/exports", headers=auth("c")).status_code == 403
    assert [e["export_id"] for e in client.get("/v1/workspaces/wa/exports", headers=auth("e")).json()][0] == ex["export_id"]
    assert client.delete(f"/v1/exports/{ex['export_id']}", headers=auth("d")).status_code == 404
    assert client.get("/v1/exports/exp_nope/download", headers=auth("a")).status_code == 404


def test_the_daily_limit_and_the_size_cap(team, monkeypatch):
    for _ in range(config.EXPORT_DAILY_LIMIT_PER_WORKSPACE):
        assert make_export().status_code == 201
    over = make_export()
    assert over.status_code == 429 and over.json()["detail"]["code"] == "EXPORT_LIMIT" and over.headers["retry-after"]
    assert make_export("b", "wb").status_code == 201, "another workspace has its own allowance"


def test_too_large_is_refused_and_leaves_no_file(team, monkeypatch):
    monkeypatch.setattr(config, "EXPORT_MAX_BYTES", 10)
    r = make_export()
    assert r.status_code == 413 and r.json()["detail"]["code"] == "EXPORT_TOO_LARGE"
    assert not list((config.ASSET_STORAGE_DIR / "exports").glob("*"))


def test_held_assets_are_listed_not_included(team):
    up = client.post("/v1/workspaces/wa/library", headers=auth("a"), data={"kind": "model", "name": "held", "rights_confirmed": "true"}, files={"file": ("h.jpg", gps_jpeg(), "image/jpeg")}).json()
    with sqlite3.connect(config.ASSET_DATABASE_PATH) as c:
        c.execute("INSERT INTO asset_takedowns(asset_id, workspace_id, state, since, updated_at) VALUES (?,?,?,?,?)", (up["asset_id"], "wa", "under_review", "2026-01-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00"))
    ex = make_export().json()
    assert ex["summary"]["assets_held"] == 1
    z = zip_of(client.get(ex["download_path"], headers=auth("a")))
    manifest = json.loads(z.read("manifest.json"))
    assert manifest["held_assets_not_included"] == [up["asset_id"]] and f"assets/{up['asset_id']}.jpg" not in z.namelist()


def test_expiry_removes_the_file_and_the_link_stops(team):
    ex = make_export().json()
    key = f"exports/{ex['export_id']}.zip"
    assert (config.ASSET_STORAGE_DIR / key).is_file()
    with sqlite3.connect(config.ASSET_DATABASE_PATH) as c:
        c.execute("UPDATE data_exports SET expires_at=? WHERE export_id=?", ((datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(), ex["export_id"]))
    gone = client.get(ex["download_path"], headers=auth("a"))
    assert gone.status_code == 410 and gone.json()["detail"]["code"] == "EXPORT_GONE"
    assert not (config.ASSET_STORAGE_DIR / key).exists()
    listed = client.get("/v1/workspaces/wa/exports", headers=auth("a")).json()
    assert listed[0]["status"] == "expired" and listed[0]["download_path"] is None
    assert [a[0] for a in audit(team)] == ["export.created", "export.expired"]


def test_delete_removes_the_file_and_is_audited(team):
    ex = make_export().json()
    assert client.delete(f"/v1/exports/{ex['export_id']}", headers=auth("a")).status_code == 204
    assert not (config.ASSET_STORAGE_DIR / f"exports/{ex['export_id']}.zip").exists()
    assert client.get(ex["download_path"], headers=auth("a")).status_code == 410
    assert client.delete(f"/v1/exports/{ex['export_id']}", headers=auth("a")).status_code == 204, "deleting twice is harmless"
    assert [a[0] for a in audit(team)] == ["export.created", "export.deleted"]


def test_a_changed_file_fails_the_integrity_check(team):
    ex = make_export().json()
    path = config.ASSET_STORAGE_DIR / f"exports/{ex['export_id']}.zip"
    path.write_bytes(path.read_bytes() + b"x")
    assert client.get(ex["download_path"], headers=auth("a")).status_code == 409


def test_every_event_is_audited_with_hashes_only(team):
    ex = make_export().json()
    client.get(ex["download_path"], headers=auth("a"))
    client.get(ex["download_path"], headers=auth("e"))
    rows = audit(team)
    assert [r[0] for r in rows] == ["export.created", "export.downloaded", "export.downloaded"]
    assert all(r[1] == "workspace" and r[2] == ex["export_id"] and len(r[3]) == 20 for r in rows)
    text = json.dumps(rows)
    assert "user-a" not in text and "wa" not in text.replace("data_", "")
    assert client.get("/v1/workspaces/wa/exports", headers=auth("a")).json()[0]["downloaded_count"] == 2


def test_an_account_export_holds_only_the_callers_own_records(team):
    client.put("/v1/me/consents/ai_training", headers=auth("a"), json={"granted": True})
    client.put("/v1/me/consents/ai_training", headers=auth("c"), json={"granted": True})
    client.put("/v1/market/profile", headers=auth("a"), json={"display_name": "A Studio", "bio": "hello"})
    ex = client.post("/v1/me/exports", headers=auth("a"))
    assert ex.status_code == 201, ex.text
    body = ex.json()
    assert body["scope"] == "account" and body["workspace_id"] is None
    z = zip_of(client.get(body["download_path"], headers=auth("a")))
    manifest = json.loads(z.read("manifest.json"))
    assert manifest["scope"] == "account" and manifest["workspaces_you_own"] == ["wa"] and any("CONTENT" in n for n in manifest["notes"])
    assert {m["workspace_id"] for m in json.loads(z.read("data/memberships.json"))} == {"wa"}
    consents = json.loads(z.read("data/consents.json"))
    assert consents and all(c["user_id"] == "user-a" for c in consents)
    assert json.loads(z.read("data/market_profile.json"))[0]["display_name"] == "A Studio"
    assert b"user-c" not in b"".join(z.read(n) for n in z.namelist())
    assert not [n for n in z.namelist() if n.startswith("assets/")], "content is exported per workspace"
    assert client.get(body["download_path"], headers=auth("c")).status_code == 404 and client.get(body["download_path"], headers=auth("b")).status_code == 404
    mine = client.get("/v1/me/exports", headers=auth("a")).json()
    assert [e["export_id"] for e in mine] == [body["export_id"]] and client.get("/v1/me/exports", headers=auth("c")).json() == []
    assert client.post("/v1/me/exports").status_code == 401
    assert client.delete(f"/v1/exports/{body['export_id']}", headers=auth("a")).status_code == 204


def test_the_real_defaults(team):
    import os, subprocess, sys
    from pathlib import Path
    clean = {k: v for k, v in os.environ.items() if not k.startswith("EXPORT_")}
    out = subprocess.run([sys.executable, "-c", "import app.config as c; print(c.EXPORT_TTL_HOURS, c.EXPORT_MAX_BYTES, c.EXPORT_DAILY_LIMIT_PER_WORKSPACE)"],
                         cwd=Path(__file__).resolve().parents[1], env=clean, capture_output=True, text=True, check=True).stdout.strip()
    assert out == f"24 {200 * 1024 * 1024} 3"
