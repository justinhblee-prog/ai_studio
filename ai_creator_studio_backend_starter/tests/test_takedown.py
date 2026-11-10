"""L-08: rights-infringement report -> temporary hold -> operator decision (DEV_ACCEPTANCE_PACK)."""
import hashlib
import io
import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
REPORTER_TEXT = "REPORTER-TEXT-the-asset-owner-must-never-see-this-3f9a"


def auth(user):
    return {"Authorization": f"Bearer token-{user}"}


def png(shade=120):
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (24, 16), (10, shade, 200)).save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def env(tmp_path, monkeypatch):
    import app.config as config
    monkeypatch.setattr(config, "ASSET_STORAGE_DIR", tmp_path / "private")
    monkeypatch.setattr(config, "ASSET_DATABASE_PATH", tmp_path / "tk.sqlite3")
    monkeypatch.setattr(config, "ASSET_SIGNING_SECRET", "s" * 48)
    monkeypatch.setattr(config, "OPS_ADMIN_USER_IDS", ("ops",))
    monkeypatch.setattr(config, "asset_api_tokens", lambda: {f"token-{u}": u for u in ("owner", "editor", "viewer", "reporter", "other", "ops")})
    assert client.post("/v1/workspaces", headers=auth("owner"), json={"workspace_id": "tk-ws"}).status_code == 201
    for user, role in (("editor", "editor"), ("viewer", "viewer")):
        assert client.post("/v1/workspaces/tk-ws/members", headers=auth("owner"), json={"user_id": user, "role": role}).status_code == 201
    # the editor uploads a second asset: its owner is the editor, not the workspace owner
    return tmp_path


def upload(user="owner", shade=120):
    res = client.post("/v1/assets/images", headers=auth(user), data={"workspace_id": "tk-ws"}, files={"file": ("a.png", png(shade), "image/png")})
    assert res.status_code == 201, res.text
    return res.json()["asset_id"]


def report(asset_id, user="reporter", category="copyright", details=REPORTER_TEXT):
    return client.post("/v1/content-reports", headers=auth(user), json={"asset_id": asset_id, "category": category, "details": details})


def open_reports():
    return client.get("/internal/moderation/reports", headers=auth("ops")).json()["items"]


def resolve(report_id, decision, note="checked"):
    return client.post(f"/internal/moderation/reports/{report_id}/resolve", headers=auth("ops"), json={"decision": decision, "note": note})


def version_id(asset_id, user="owner"):
    return client.get(f"/v1/assets/{asset_id}/versions", headers=auth(user)).json()["items"][0]["version_id"]


def asset_routes(asset_id, vid):
    return [("get", f"/v1/assets/{asset_id}"), ("get", f"/v1/assets/{asset_id}/versions"), ("get", f"/v1/assets/{asset_id}/provenance"),
            ("get", f"/v1/assets/{asset_id}/relations"), ("get", f"/v1/assets/{asset_id}/rights-confirmation"),
            ("post", f"/v1/assets/{asset_id}/preview-url"), ("post", f"/v1/assets/{asset_id}/versions/{vid}/preview-url"),
            ("get", f"/v1/assets/{asset_id}/versions/{vid}/preview-content")]


def test_a_report_is_accepted_with_the_same_answer_for_any_asset_id_and_puts_the_asset_on_hold(env):
    aid = upload()
    real = report(aid)
    unknown = report("ast_does_not_exist_at_all")
    assert real.status_code == unknown.status_code == 202
    assert real.json() == unknown.json() == {"status": "received"}
    assert [r["asset_id"] for r in open_reports()] == [aid]
    assert client.get(f"/v1/assets/{aid}/takedown", headers=auth("owner")).json()["state"] == "under_review"


def test_while_on_hold_nobody_but_the_owner_can_reach_the_asset(env):
    aid = upload()
    vid = version_id(aid)
    before = {path: client.request(m.upper(), path, headers=auth("editor")).status_code for m, path in asset_routes(aid, vid)}
    assert all(code == 200 or code == 201 for code in before.values()), before
    assert report(aid).status_code == 202
    for user in ("editor", "viewer"):
        for m, path in asset_routes(aid, vid):
            res = client.request(m.upper(), path, headers=auth(user))
            assert res.status_code == 404, (user, m, path, res.status_code)
        assert aid not in [i["asset_id"] for i in client.get("/v1/assets?workspace_id=tk-ws", headers=auth(user)).json()["items"]]
        assert client.get(f"/v1/assets/{aid}/takedown", headers=auth(user)).status_code == 404
    # the owner keeps access and sees the state
    for m, path in asset_routes(aid, vid):
        assert client.request(m.upper(), path, headers=auth("owner")).status_code in (200, 201), (m, path)
    assert aid in [i["asset_id"] for i in client.get("/v1/assets?workspace_id=tk-ws", headers=auth("owner")).json()["items"]]
    assert client.get("/v1/me/takedowns", headers=auth("owner")).json()["items"][0]["state"] == "under_review"


def test_a_signed_link_issued_before_the_hold_stops_working(env):
    aid = upload()
    url = client.post(f"/v1/assets/{aid}/preview-url", headers=auth("editor")).json()["url"]
    path = url.split("://", 1)[-1].split("/", 1)[-1]
    path = "/" + path if not path.startswith("/") else path
    assert client.get(path).status_code == 200            # signed links carry no bearer token
    assert report(aid).status_code == 202
    assert client.get(path).status_code == 404


def test_the_owner_never_learns_who_reported_or_what_they_wrote(env):
    aid = upload()
    vid = version_id(aid)
    assert report(aid, user="reporter").status_code == 202
    seen = []
    for m, path in asset_routes(aid, vid)[:7]:
        seen.append(client.request(m.upper(), path, headers=auth("owner")).text)
    seen.append(client.get(f"/v1/assets/{aid}/takedown", headers=auth("owner")).text)
    seen.append(client.get("/v1/me/takedowns", headers=auth("owner")).text)
    seen.append(client.get("/v1/assets?workspace_id=tk-ws", headers=auth("owner")).text)
    text = "\n".join(seen)
    assert "reporter" not in text and REPORTER_TEXT not in text and "copyright" not in text
    # ... while the operator does see the reporter
    item = open_reports()[0]
    assert item["reporter_id"] == "reporter" and item["details"] == REPORTER_TEXT and item["category"] == "copyright"


def test_a_hold_deletes_nothing_and_the_owner_cannot_erase_the_evidence(env):
    aid = upload()
    stored = sorted(p.name for p in (env / "private").iterdir())
    assert report(aid).status_code == 202
    assert sorted(p.name for p in (env / "private").iterdir()) == stored
    res = client.delete(f"/v1/assets/{aid}", headers=auth("owner"))
    assert res.status_code == 409 and res.json()["detail"]["code"] == "TAKEDOWN_ACTIVE"
    assert sorted(p.name for p in (env / "private").iterdir()) == stored


def test_restore_puts_everything_back_exactly_as_it_was(env):
    aid = upload()
    vid = version_id(aid)
    original = client.get(f"/v1/assets/{aid}/versions/{vid}/preview-content", headers=auth("editor")).content
    meta_before = client.get(f"/v1/assets/{aid}", headers=auth("editor")).json()
    assert report(aid).status_code == 202
    rid = open_reports()[0]["report_id"]
    assert resolve(rid, "restore").status_code == 200
    assert client.get(f"/v1/assets/{aid}", headers=auth("editor")).json() == meta_before
    assert client.get(f"/v1/assets/{aid}/versions/{vid}/preview-content", headers=auth("editor")).content == original
    assert hashlib.sha256(original).hexdigest() == meta_before["checksum_sha256"]
    assert client.get(f"/v1/assets/{aid}/takedown", headers=auth("owner")).json()["state"] == "none"
    assert client.get("/v1/me/takedowns", headers=auth("owner")).json()["items"] == []
    assert client.get("/internal/moderation/reports?status=rejected", headers=auth("ops")).json()["items"][0]["report_id"] == rid
    assert client.delete(f"/v1/assets/{aid}", headers=auth("owner")).status_code == 204   # the owner may delete again


def test_the_hold_lifts_only_when_no_other_report_is_open(env):
    aid = upload()
    report(aid, user="reporter"); report(aid, user="other")
    first, second = [r["report_id"] for r in open_reports()]
    assert resolve(first, "restore").status_code == 200
    assert client.get(f"/v1/assets/{aid}", headers=auth("editor")).status_code == 404   # a second report is still open
    assert resolve(second, "restore").status_code == 200
    assert client.get(f"/v1/assets/{aid}", headers=auth("editor")).status_code == 200


def test_remove_hides_the_asset_from_everyone_keeps_the_file_and_can_be_reinstated(env):
    aid = upload()
    vid = version_id(aid)
    stored = sorted(p.name for p in (env / "private").iterdir())
    report(aid)
    assert resolve(open_reports()[0]["report_id"], "remove").status_code == 200
    for user in ("owner", "editor", "viewer"):
        assert client.get(f"/v1/assets/{aid}", headers=auth(user)).status_code == 404, user
        assert aid not in [i["asset_id"] for i in client.get("/v1/assets?workspace_id=tk-ws", headers=auth(user)).json()["items"]]
    assert client.get(f"/v1/assets/{aid}/takedown", headers=auth("owner")).json()["state"] == "removed"
    assert client.get("/v1/me/takedowns", headers=auth("owner")).json()["items"][0]["state"] == "removed"
    assert sorted(p.name for p in (env / "private").iterdir()) == stored          # nothing erased
    assert client.post(f"/internal/moderation/assets/{aid}/reinstate", headers=auth("ops")).status_code == 200
    assert client.get(f"/v1/assets/{aid}", headers=auth("editor")).status_code == 200
    assert client.get(f"/v1/assets/{aid}/versions/{vid}/preview-content", headers=auth("editor")).status_code == 200


def test_only_platform_operators_reach_the_moderation_endpoints(env):
    aid = upload(); report(aid); rid = open_reports()[0]["report_id"]
    for method, path, body in (("get", "/internal/moderation/reports", None), ("post", f"/internal/moderation/reports/{rid}/resolve", {"decision": "restore"}),
                               ("post", f"/internal/moderation/assets/{aid}/reinstate", None)):
        assert client.request(method.upper(), path, json=body).status_code == 401
        for user in ("owner", "editor", "reporter"):
            assert client.request(method.upper(), path, headers=auth(user), json=body).status_code == 403, (user, path)
    assert resolve(rid, "restore").status_code == 200
    assert resolve(rid, "remove").status_code == 409          # already resolved
    assert resolve("rpt_missing", "restore").status_code == 404


def test_reports_are_idempotent_rate_limited_and_a_self_report_does_nothing(env, monkeypatch):
    import app.config as config
    a = upload()
    report(a); report(a)
    assert len(open_reports()) == 1
    assert report(upload("owner", 50), user="owner").status_code == 202      # the owner reporting their own asset: no effect
    assert len(open_reports()) == 1
    monkeypatch.setattr(config, "CONTENT_REPORT_DAILY_LIMIT", 3)
    ids = [upload("owner", 60 + i) for i in range(4)]
    codes = [report(i, user="other").status_code for i in ids]
    assert codes == [202, 202, 202, 429], codes


def test_a_reporters_account_purge_removes_their_identity_from_the_reports_and_does_not_stop(env):
    import importlib.util
    import sys
    from datetime import datetime, timedelta, timezone
    spec = importlib.util.spec_from_file_location("purge_requests", Path(__file__).resolve().parents[1] / "scripts" / "purge_requests.py")
    purge = importlib.util.module_from_spec(spec); sys.modules["purge_requests"] = purge; spec.loader.exec_module(purge)
    assert client.post("/v1/workspaces/tk-ws/members", headers=auth("owner"), json={"user_id": "reporter", "role": "viewer"}).status_code == 201
    aid = upload(); report(aid, user="reporter")
    made = client.post("/v1/me/deletion-requests", headers=auth("reporter"), json={"scope": "account"})
    assert made.status_code == 201
    db = sqlite3.connect(env / "tk.sqlite3", isolation_level=None)
    db.execute("UPDATE deletion_requests SET requested_at=? WHERE request_id=?", ((datetime.now(timezone.utc) - timedelta(days=10)).isoformat(), made.json()["request_id"]))
    code = purge.main(["--db", str(env / "tk.sqlite3"), "--assets-dir", str(env / "private"), "--outputs-dir", str(env / "outputs"), "--apply", "--confirm", made.json()["request_id"]])
    assert code == 0
    rows = db.execute("SELECT reporter_id FROM content_reports").fetchall()
    db.close()
    assert rows == [("deleted-user",)]
