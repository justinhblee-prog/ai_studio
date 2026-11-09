"""D2 acceptance: image uploads require a rights confirmation, which is recorded in upload_rights_confirmations."""
import io
import sqlite3

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


@pytest.fixture
def env(tmp_path, monkeypatch):
    import app.config as config
    monkeypatch.setattr(config, "ASSET_STORAGE_DIR", tmp_path / "private")
    monkeypatch.setattr(config, "ASSET_DATABASE_PATH", tmp_path / "d2.sqlite3")
    monkeypatch.setattr(config, "ASSET_SIGNING_SECRET", "s" * 48)
    monkeypatch.setattr(config, "asset_api_tokens", lambda: {"token-user-a": "user-a", "token-user-b": "user-b", "token-user-c": "user-c"})
    monkeypatch.delenv("LEGAL_DOCUMENT_VERSIONS", raising=False)
    assert client.post("/v1/workspaces", headers=auth(), json={"workspace_id": "d2-ws"}).status_code == 201
    assert client.post("/v1/workspaces/d2-ws/members", headers=auth(), json={"user_id": "user-b", "role": "viewer"}).status_code == 201
    legacy_asset = upload(enforce=False)  # exists before enforcement, with no declaration
    monkeypatch.setattr(config, "ASSET_REQUIRE_RIGHTS_CONFIRMATION", True)  # the real default; conftest switches it off for older tests
    return {"tmp": tmp_path, "legacy": legacy_asset}


def upload(enforce=True, **fields):
    data = {"workspace_id": "d2-ws", **{k: str(v).lower() for k, v in fields.items()}}
    if not enforce:
        import app.config as config
        assert config.ASSET_REQUIRE_RIGHTS_CONFIRMATION is False
    res = client.post("/v1/assets/images", headers=auth(), data=data, files={"file": ("a.png", png(), "image/png")})
    return res


def rows(env):
    db = sqlite3.connect(env["tmp"] / "d2.sqlite3"); db.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in db.execute("SELECT * FROM upload_rights_confirmations ORDER BY confirmed_at")]
    finally:
        db.close()


def test_the_default_is_required_in_a_fresh_interpreter():
    import os, subprocess, sys
    env = {k: v for k, v in os.environ.items() if k != "ASSET_REQUIRE_RIGHTS_CONFIRMATION"}
    out = subprocess.run([sys.executable, "-I", "-c", "import sys; sys.path.insert(0, '.'); import app.config as c; print(c.ASSET_REQUIRE_RIGHTS_CONFIRMATION)"],
                         capture_output=True, text=True, env=env, check=True)
    assert out.stdout.strip() == "True"


def test_an_upload_without_confirmation_is_refused_with_422_and_stores_nothing(env):
    before = len(client.get("/v1/assets?workspace_id=d2-ws&kind=image", headers=auth()).json()["items"])
    for fields in ({}, {"rights_confirmed": False}):
        res = upload(**fields)
        assert res.status_code == 422, res.text
        assert res.json()["detail"]["code"] == "RIGHTS_CONFIRMATION_REQUIRED"
    assert len(client.get("/v1/assets?workspace_id=d2-ws&kind=image", headers=auth()).json()["items"]) == before
    assert rows(env) == []


def test_a_confirmed_upload_records_exactly_one_row(env):
    res = upload(rights_confirmed=True)
    assert res.status_code == 201, res.text
    asset_id = res.json()["asset_id"]
    recorded = rows(env)
    assert len(recorded) == 1
    r = recorded[0]
    assert (r["asset_id"], r["workspace_id"], r["user_id"]) == (asset_id, "d2-ws", "user-a")
    assert (r["depicts_person"], r["likeness_consent"]) == (0, 0)
    assert r["policy_version"] and r["confirmed_at"]


def test_a_person_in_the_image_needs_the_consent_too_and_it_is_recorded(env):
    refused = upload(rights_confirmed=True, depicts_person=True)
    assert refused.status_code == 422 and refused.json()["detail"]["code"] == "LIKENESS_CONSENT_REQUIRED"
    assert rows(env) == []
    ok = upload(rights_confirmed=True, depicts_person=True, likeness_consent=True)
    assert ok.status_code == 201
    assert [(r["depicts_person"], r["likeness_consent"]) for r in rows(env)] == [(1, 1)]


def test_the_same_asset_cannot_be_recorded_twice(env):
    asset_id = upload(rights_confirmed=True).json()["asset_id"]
    from app.assets.store import _connect
    with _connect() as db:
        db.execute("""INSERT OR IGNORE INTO upload_rights_confirmations(asset_id, workspace_id, user_id, depicts_person, likeness_consent, policy_version, confirmed_at)
            VALUES(?,?,?,?,?,?,?)""", (asset_id, "d2-ws", "user-a", 0, 0, "x", "2026-01-01T00:00:00+00:00"))
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("""INSERT INTO upload_rights_confirmations(asset_id, workspace_id, user_id, depicts_person, likeness_consent, policy_version, confirmed_at)
                VALUES(?,?,?,?,?,?,?)""", (asset_id, "d2-ws", "user-a", 0, 0, "x", "2026-01-01T00:00:00+00:00"))
    assert len(rows(env)) == 1


def test_assets_uploaded_before_enforcement_stay_usable_and_read_as_unconfirmed(env):
    legacy = env["legacy"].json()["asset_id"]
    assert client.get(f"/v1/assets/{legacy}", headers=auth()).status_code == 200
    read = client.get(f"/v1/assets/{legacy}/rights-confirmation", headers=auth())
    assert read.status_code == 200 and read.json() == {"asset_id": legacy, "status": "unconfirmed"}
    fresh = upload(rights_confirmed=True).json()["asset_id"]
    got = client.get(f"/v1/assets/{fresh}/rights-confirmation", headers=auth()).json()
    assert got["status"] == "confirmed" and got["policy_version"] and got["confirmed_at"] and got["depicts_person"] is False


def test_the_rights_record_follows_workspace_membership(env):
    fresh = upload(rights_confirmed=True).json()["asset_id"]
    assert client.get(f"/v1/assets/{fresh}/rights-confirmation").status_code == 401
    assert client.get(f"/v1/assets/{fresh}/rights-confirmation", headers=auth("token-user-b")).status_code == 200   # viewer may read
    assert client.get(f"/v1/assets/{fresh}/rights-confirmation", headers=auth("token-user-c")).status_code == 404   # outsider
    assert client.get("/v1/assets/ast_missing/rights-confirmation", headers=auth()).status_code == 404


def test_deleting_the_asset_keeps_the_record_without_naming_the_uploader(env):
    asset_id = upload(rights_confirmed=True).json()["asset_id"]
    assert client.delete(f"/v1/assets/{asset_id}", headers=auth()).status_code == 204
    left = rows(env)
    assert len(left) == 1 and left[0]["asset_id"] == asset_id
    assert left[0]["user_id"] == "deleted-user"
    assert client.get(f"/v1/assets/{asset_id}/rights-confirmation", headers=auth()).status_code == 404   # the asset itself is gone


def test_account_purge_anonymises_the_record_in_a_shared_workspace_and_does_not_stop(env):
    """The retention decision: a shared workspace survives the member's purge, so the member's id must leave the record."""
    import importlib.util
    from pathlib import Path
    from datetime import datetime, timedelta, timezone
    spec = importlib.util.spec_from_file_location("purge_requests", Path(__file__).resolve().parents[1] / "scripts" / "purge_requests.py")
    purge = importlib.util.module_from_spec(spec); import sys as _s; _s.modules["purge_requests"] = purge; spec.loader.exec_module(purge)
    assert client.post("/v1/workspaces/d2-ws/members", headers=auth(), json={"user_id": "user-c", "role": "editor"}).status_code == 201
    res = client.post("/v1/assets/images", headers=auth("token-user-c"), data={"workspace_id": "d2-ws", "rights_confirmed": "true"}, files={"file": ("c.png", png(30), "image/png")})
    assert res.status_code == 201, res.text
    assert "user-c" in {r["user_id"] for r in rows(env)}
    made = client.post("/v1/me/deletion-requests", headers=auth("token-user-c"), json={"scope": "account"})
    assert made.status_code == 201, made.text
    db = sqlite3.connect(env["tmp"] / "d2.sqlite3", isolation_level=None)
    at = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    db.execute("UPDATE deletion_requests SET requested_at=? WHERE request_id=?", (at, made.json()["request_id"]))  # past the 7-day grace
    db.close()
    code = purge.main(["--db", str(env["tmp"] / "d2.sqlite3"), "--assets-dir", str(env["tmp"] / "private"), "--outputs-dir", str(env["tmp"] / "outputs"), "--apply", "--confirm", made.json()["request_id"]])
    assert code == 0
    after = rows(env)
    assert "user-c" not in {r["user_id"] for r in after}, after
    assert any(r["user_id"] == "deleted-user" for r in after)           # the record stayed, anonymised


def test_an_unconfirmed_declaration_in_legacy_mode_creates_no_record(env, monkeypatch):
    import app.config as config
    monkeypatch.setattr(config, "ASSET_REQUIRE_RIGHTS_CONFIRMATION", False)   # old clients explicitly allowed
    res = upload(enforce=False, rights_confirmed=False)
    assert res.status_code == 201
    assert rows(env) == []
    got = client.get(f"/v1/assets/{res.json()['asset_id']}/rights-confirmation", headers=auth()).json()
    assert got["status"] == "unconfirmed"
