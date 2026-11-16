"""R-065: data export (workspace / account ZIP), deletion coverage of the newer tables, derived files removed with their asset, and the audit record that survives."""
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
from scripts import purge_requests as purge
from tests.test_purge_requests import auth, env, files, orphans, request, run, ws_rows  # noqa: F401  (pa: owner a, pb: owner b, sh: owner a + editor b)

client = TestClient(app)


def png(shade=1, size=(20, 20)):
    buf = io.BytesIO(); Image.new("RGB", size, (shade, shade, shade)).save(buf, format="PNG"); return buf.getvalue()


def jpeg_gps():
    ex = Image.Exif(); ex[0x010F] = "Cam"
    ifd = ex.get_ifd(0x8825); ifd[1] = "N"; ifd[2] = (37.0, 33.0, 59.0); ex[0x8825] = ifd
    buf = io.BytesIO(); Image.new("RGB", (16, 16), (200, 10, 10)).save(buf, format="JPEG", exif=ex.tobytes()); return buf.getvalue()


def lib_upload(who, ws, content, name="x.png", kind="model", **fields):
    mime = "image/jpeg" if name.endswith("jpg") else "image/png"
    r = client.post(f"/v1/workspaces/{ws}/library", headers=auth(who), data={"kind": kind, "name": "n", "rights_confirmed": "true", **fields}, files={"file": (name, content, mime)})
    assert r.status_code == 201, r.text
    return r.json()


def db_of(tmp):
    c = sqlite3.connect(tmp / "a.sqlite3", isolation_level=None)
    c.execute("PRAGMA foreign_keys=ON")
    return c


def busy_workspace(tmp):
    """Rows in every newer table for workspace pb (owner b), plus cross-workspace references."""
    item = lib_upload("b", "pb", png(5, (700, 500)), attrs=json.dumps({"category": "top"}))
    assert (tmp / "private" / "thumbs").is_dir() and list((tmp / "private" / "thumbs").glob(f"{item['asset_id']}.*.webp")), "display pictures exist"
    assert client.put("/v1/market/profile", headers=auth("b"), json={"display_name": "B Studio", "bio": "hi"}).status_code == 200
    body = {"workspace_id": "pb", "kind": "preset", "title": "t", "license_scope": "personal", "is_ai_generated": False, "rights_confirmed": True, "payload": {"x": 1}}
    listing = client.post("/v1/market/listings", headers=auth("b"), json=body).json()
    assert client.post(f"/v1/market/listings/{listing['listing_id']}/publish", headers=auth("b"), json={"rights_confirmed": True}).status_code == 200
    assert client.post(f"/v1/market/listings/{listing['listing_id']}/reports", headers=auth("a"), json={"reason": "other", "details": "x"}).status_code == 202
    rv = client.post("/v1/workspaces/pb/reviews", headers=auth("b"), json={"asset_id": item["asset_id"]}).json()
    assert client.post(f"/v1/workspaces/pb/reviews/{rv['review_id']}/approve", headers=auth("b"), json={}).status_code == 200
    assert client.patch("/v1/workspaces/pb/settings", headers=auth("b"), json={"require_review_for_export": True}).status_code == 200
    assert client.post("/v1/workspaces/pb/exports", headers=auth("b")).status_code in (201, 409), "an export exists too (it needs no review to be created)"
    assert client.post("/v1/me/exports", headers=auth("b")).status_code == 201
    return item


def test_every_table_the_newer_features_create_is_mapped_and_a_workspace_purge_removes_it_all(env):
    tmp, db, out = env
    item = busy_workspace(tmp)
    # the other workspace has the same kinds of rows, which must survive
    other = lib_upload("a", "pa", png(9, (700, 500)))
    client.post("/v1/workspaces/pa/reviews", headers=auth("a"), json={"asset_id": other["asset_id"]})
    rid = request(db, "user-b", "workspace_content", "pb")
    assert run(tmp) == 0
    plan = purge.build_plan([db], {"request_id": rid, "scope": "workspace_content", "user_id": "user-b", "workspace_id": "pb"}, tmp / "private", tmp / "outputs")
    assert plan.blocked == [], f"a table of the newer features is not mapped: {plan.blocked}"
    for table in ("workspace_library_items", "asset_reviews", "asset_review_events", "workspace_settings", "workspace_settings_history", "market_listings", "market_reports", "data_exports"):
        assert plan.rows.get(table, 0) >= 1, (table, plan.rows)
    assert any("thumbs" in str(f) for f in plan.files) and any("exports" in str(f) for f in plan.files)
    assert run(tmp, "--apply", "--confirm", rid) == 0
    assert orphans(db) == []
    for table in ("workspace_library_items", "asset_reviews", "asset_review_events", "workspace_settings", "workspace_settings_history", "market_listings", "data_exports"):
        assert db.execute(f'SELECT COUNT(*) FROM "{table}" WHERE workspace_id=?', ("pb",)).fetchone()[0] == 0, table
    assert db.execute("SELECT COUNT(*) FROM market_reports").fetchone()[0] == 0, "reports on the purged listings went with them"
    assert not list((tmp / "private" / "thumbs").glob(f"{item['asset_id']}.*.webp")), "the display pictures are removed with their asset"
    assert not [p for p in (tmp / "private" / "exports").glob("exp_*.zip")], "the workspace export file is removed"
    assert list((tmp / "private" / "thumbs").glob(f"{other['asset_id']}.*.webp")), "another workspace's display pictures stay"
    assert db.execute("SELECT COUNT(*) FROM asset_reviews WHERE workspace_id='pa'").fetchone()[0] == 1


def test_an_account_purge_removes_the_profile_the_exports_and_anonymizes_the_people_columns(env):
    tmp, db, out = env
    busy_workspace(tmp)
    shared = lib_upload("a", "sh", png(7, (300, 300)))
    rv = client.post("/v1/workspaces/sh/reviews", headers=auth("b"), json={"asset_id": shared["asset_id"]}).json()
    client.post(f"/v1/workspaces/sh/reviews/{rv['review_id']}/approve", headers=auth("a"), json={})
    db.execute("UPDATE workspace_members SET role='owner' WHERE workspace_id='sh' AND user_id='user-b'")
    client.patch("/v1/workspaces/sh/settings", headers=auth("b"), json={"forbid_self_approval": True})
    assert client.post("/v1/me/exports", headers=auth("b")).status_code in (201, 429)
    account_files = list((tmp / "private" / "exports").glob("acx_*.zip"))
    assert account_files
    rid = request(db, "user-b", "account")
    assert run(tmp, "--apply", "--confirm", rid) == 0
    assert orphans(db) == []
    assert db.execute("SELECT COUNT(*) FROM market_profiles WHERE user_id='user-b'").fetchone()[0] == 0, "the seller profile goes with the account"
    assert db.execute("SELECT COUNT(*) FROM account_exports WHERE user_id='user-b'").fetchone()[0] == 0
    assert not list((tmp / "private" / "exports").glob("acx_*.zip")), "the account export files are removed"
    assert db.execute("SELECT COUNT(*) FROM asset_reviews WHERE requested_by='user-b' OR handled_by='user-b'").fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM asset_reviews WHERE requested_by='deleted-user'").fetchone()[0] >= 1, "the review stays for the workspace, without the person"
    assert db.execute("SELECT COUNT(*) FROM workspace_settings WHERE updated_by='user-b'").fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM market_reports WHERE reporter_id='user-b'").fetchone()[0] == 0
    leftover = []
    for (t,) in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name!='data_lifecycle_audit'").fetchall():
        for (c,) in [(r[1],) for r in db.execute(f'PRAGMA table_info("{t}")')]:
            if t in ("deletion_requests",):
                continue
            if db.execute(f'SELECT COUNT(*) FROM "{t}" WHERE "{c}"=?', ("user-b",)).fetchone()[0]:
                leftover.append(f"{t}.{c}")
    assert leftover == [], f"user-b is still named in: {leftover}"


def test_the_audit_survives_the_deletion_and_names_nobody(env):
    tmp, db, _ = env
    client.post("/v1/workspaces/pb/exports", headers=auth("b"))
    r = client.post("/v1/me/deletion-requests", headers=auth("b"), json={"scope": "workspace_content", "workspace_id": "pb", "reason": "SECRET-REASON"})
    assert r.status_code == 201, r.text
    rid = r.json()["request_id"]
    db.execute("UPDATE deletion_requests SET requested_at=? WHERE request_id=?", ((datetime.now(timezone.utc) - timedelta(days=10)).isoformat(), rid))
    assert run(tmp, "--apply", "--confirm", rid) == 0
    rows = db.execute("SELECT * FROM data_lifecycle_audit ORDER BY event_id").fetchall()
    events = [r[2] for r in rows]
    assert "export.created" in events and "deletion.requested" in events and events[-1] == "deletion.completed", events
    done = rows[-1]
    text = json.dumps([list(r) for r in rows])
    for secret in ("user-b", "pb", "SECRET-REASON", "ws"):
        assert secret not in text.replace("deletion.", "").replace("workspace", ""), secret
    assert done[3] == "workspace_content" and done[4] == rid and done[5] and len(done[5]) == 20, "scope, request id and a hash of the subject"
    assert done[6] >= 1 and done[8] >= 0, "counts"
    assert db.execute("SELECT COUNT(*) FROM data_lifecycle_audit").fetchone()[0] == len(rows), "the purge did not remove audit rows"
    for sql in ("UPDATE data_lifecycle_audit SET event='x'", "DELETE FROM data_lifecycle_audit"):
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            db.execute(sql)


def test_a_request_can_be_cancelled_during_the_grace_period_and_then_nothing_is_deleted(env):
    tmp, db, out = env
    r = client.post("/v1/me/deletion-requests", headers=auth("b"), json={"scope": "workspace_content", "workspace_id": "pb"})
    rid = r.json()["request_id"]
    db.execute("UPDATE deletion_requests SET requested_at=? WHERE request_id=?", ((datetime.now(timezone.utc) - timedelta(days=10)).isoformat(), rid))
    before = ws_rows(db, "pb")
    assert client.delete(f"/v1/me/deletion-requests/{rid}", headers=auth("b")).status_code == 204
    assert run(tmp, "--apply", "--confirm", rid) == 2, "a cancelled request is not processed even after the grace period"
    assert ws_rows(db, "pb") == before and out["pb"]["asset"] in " ".join(files(tmp))
    events = [r[0] for r in db.execute("SELECT event FROM data_lifecycle_audit ORDER BY event_id")]
    assert events == ["deletion.requested", "deletion.cancelled"]


def test_after_the_purge_the_data_is_gone_for_the_api_too(env):
    tmp, db, out = env
    item = lib_upload("b", "pb", png(3))
    rid = request(db, "user-b", "workspace_content", "pb")
    assert run(tmp, "--apply", "--confirm", rid) == 0
    assert client.get(f"/v1/assets/{item['asset_id']}/provenance", headers=auth("b")).status_code == 404
    assert client.get("/v1/workspaces/pb/library", headers=auth("b")).json()["total"] == 0
    assert client.get(item["thumbs"]["480"]).status_code == 404 if item.get("thumbs") else True
    assert client.get("/v1/workspaces/pb/reviews", headers=auth("b")).json()["total"] == 0
