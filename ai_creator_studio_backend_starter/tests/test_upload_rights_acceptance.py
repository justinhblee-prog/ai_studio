"""Acceptance tests for D2 / L-04 (upload rights confirmation). Written BEFORE the implementation, from
DESIGN_PACK D2; they must fail on a tree without the feature and pass on a correct implementation.

Contract assumed (from the design): POST /v1/assets/images requires form field rights_confirmed=true (422
otherwise); a successful upload writes exactly one row to table upload_rights_confirmations(asset_id, user_id,
confirmed_at, policy_version). If the implementation chose different names, adjust the constants below, not the checks.
"""
import io
import sqlite3

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app

TABLE = "upload_rights_confirmations"
ENFORCE_ATTR = "ASSET_REQUIRE_RIGHTS_CONFIRMATION"  # this tree's name for the switch (the reference used UPLOAD_RIGHTS_REQUIRED); only this constant was changed
client = TestClient(app)


def auth(t):
    return {"Authorization": f"Bearer {t}"}


def png():
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), (200, 10, 10)).save(buf, "PNG")
    return buf.getvalue()


@pytest.fixture
def env(tmp_path, monkeypatch):
    import app.config as config
    monkeypatch.setattr(config, "ASSET_STORAGE_DIR", tmp_path / "private")
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path / "outputs")
    monkeypatch.setattr(config, "ASSET_DATABASE_PATH", tmp_path / "a.sqlite3")
    monkeypatch.setattr(config, "GENERATION_DATABASE_PATH", None)
    monkeypatch.setattr(config, "ASSET_SIGNING_SECRET", "r" * 48)
    monkeypatch.setattr(config, "asset_api_tokens", lambda: {"tok-a": "user-a"})
    monkeypatch.setattr(config, ENFORCE_ATTR, True, raising=False)
    assert client.post("/v1/workspaces", headers=auth("tok-a"), json={"workspace_id": "rt-ws"}).status_code == 201
    return tmp_path / "a.sqlite3"


def upload(data_extra=None):
    data = {"workspace_id": "rt-ws"}
    data.update(data_extra or {})
    return client.post("/v1/assets/images", headers=auth("tok-a"), data=data,
                       files={"file": ("p.png", png(), "image/png")})


def rows(db):
    conn = sqlite3.connect(db)
    try:
        return conn.execute(f"SELECT * FROM {TABLE}").fetchall()
    except sqlite3.OperationalError:
        return None
    finally:
        conn.close()


def count_assets():
    r = client.get("/v1/assets", headers=auth("tok-a"), params={"workspace_id": "rt-ws"})
    assert r.status_code == 200
    return len(r.json()["items"])


def test_upload_without_confirmation_is_rejected_and_stores_nothing(env):
    assert upload().status_code == 422
    assert count_assets() == 0


def test_upload_with_confirmation_false_is_rejected(env):
    assert upload({"rights_confirmed": "false"}).status_code == 422
    assert count_assets() == 0


def test_confirmed_upload_records_exactly_one_row(env):
    r = upload({"rights_confirmed": "true"})
    assert r.status_code == 201, r.text
    got = rows(env)
    assert got is not None and len(got) == 1
    conn = sqlite3.connect(env); conn.row_factory = sqlite3.Row
    row = conn.execute(f"SELECT * FROM {TABLE}").fetchone()
    assert row["asset_id"] == r.json()["asset_id"] and row["user_id"] == "user-a"
    assert row["confirmed_at"] and row["policy_version"]
    # listing the asset again must not add a second confirmation record
    count_assets()
    assert len(rows(env)) == 1


def test_confirmation_rows_are_not_shared_between_assets(env):
    a = upload({"rights_confirmed": "true"}).json()["asset_id"]
    b = upload({"rights_confirmed": "true"}).json()["asset_id"]
    assert a != b and len(rows(env)) == 2
