import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def auth(token="token-user-a"):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def legal_env(tmp_path, monkeypatch):
    import app.config as config
    monkeypatch.setattr(config, "ASSET_STORAGE_DIR", tmp_path / "private")
    monkeypatch.setattr(config, "ASSET_DATABASE_PATH", tmp_path / "legal.sqlite3")
    monkeypatch.setattr(config, "ASSET_SIGNING_SECRET", "s" * 48)
    monkeypatch.setattr(config, "asset_api_tokens", lambda: {"token-user-a": "user-a", "token-user-b": "user-b"})
    monkeypatch.delenv("LEGAL_DOCUMENT_VERSIONS", raising=False)
    assert client.post("/v1/workspaces", headers=auth(), json={"workspace_id": "legal-ws"}).status_code == 201
    return tmp_path


def _all_current():
    docs = client.get("/v1/legal/documents").json()["documents"]
    return [{"document": d["document"], "version": d["version"]} for d in docs]


def test_documents_are_public_and_marked_draft(legal_env):
    body = client.get("/v1/legal/documents").json()
    assert body["status"] == "draft"
    assert {d["document"] for d in body["documents"]} == {"terms", "privacy", "content_policy"}


def test_status_requires_authentication(legal_env):
    assert client.get("/v1/me/legal-status").status_code == 401
    assert client.post("/v1/me/legal-acceptances", json={"documents": _all_current()}).status_code == 401


def test_new_user_is_missing_every_document_then_accepts(legal_env):
    status = client.get("/v1/me/legal-status", headers=auth()).json()
    assert status["accepted"] is False and len(status["missing"]) == 3 and status["history"] == []
    accepted = client.post("/v1/me/legal-acceptances", headers=auth(), json={"documents": _all_current()})
    assert accepted.status_code == 200, accepted.text
    body = accepted.json()
    assert body["accepted"] is True and body["missing"] == [] and len(body["history"]) == 3


def test_partial_acceptance_leaves_the_rest_missing(legal_env):
    only_terms = [d for d in _all_current() if d["document"] == "terms"]
    body = client.post("/v1/me/legal-acceptances", headers=auth(), json={"documents": only_terms}).json()
    assert body["accepted"] is False
    assert [m["document"] for m in body["missing"]] == ["privacy", "content_policy"]


def test_acceptance_is_idempotent_and_isolated_per_user(legal_env):
    for _ in range(2):
        assert client.post("/v1/me/legal-acceptances", headers=auth(), json={"documents": _all_current()}).status_code == 200
    assert len(client.get("/v1/me/legal-status", headers=auth()).json()["history"]) == 3
    other = client.get("/v1/me/legal-status", headers=auth("token-user-b")).json()
    assert other["accepted"] is False and other["history"] == []


def test_stale_unknown_and_duplicate_documents_are_rejected(legal_env):
    stale = client.post("/v1/me/legal-acceptances", headers=auth(), json={"documents": [{"document": "terms", "version": "old"}]})
    assert stale.status_code == 409
    unknown = client.post("/v1/me/legal-acceptances", headers=auth(), json={"documents": [{"document": "cookies", "version": "x"}]})
    assert unknown.status_code == 422
    current = _all_current()[0]
    dup = client.post("/v1/me/legal-acceptances", headers=auth(), json={"documents": [current, current]})
    assert dup.status_code == 422
    assert client.get("/v1/me/legal-status", headers=auth()).json()["history"] == []


def test_version_bump_invalidates_previous_acceptance(legal_env, monkeypatch):
    client.post("/v1/me/legal-acceptances", headers=auth(), json={"documents": _all_current()})
    monkeypatch.setenv("LEGAL_DOCUMENT_VERSIONS", "terms=2026-12-01")
    status = client.get("/v1/me/legal-status", headers=auth()).json()
    assert status["accepted"] is False
    assert status["missing"] == [{"document": "terms", "version": "2026-12-01"}]


def test_account_deletion_request_is_recorded_idempotent_and_cancellable(legal_env):
    first = client.post("/v1/me/deletion-requests", headers=auth(), json={"scope": "account", "reason": "closing"})
    assert first.status_code == 201, first.text
    item = first.json()
    assert item["status"] == "pending" and item["workspace_id"] is None
    again = client.post("/v1/me/deletion-requests", headers=auth(), json={"scope": "account"})
    assert again.status_code == 200 and again.json()["request_id"] == item["request_id"]
    assert len(client.get("/v1/me/deletion-requests", headers=auth()).json()["items"]) == 1
    assert client.delete(f"/v1/me/deletion-requests/{item['request_id']}", headers=auth()).status_code == 204
    assert client.delete(f"/v1/me/deletion-requests/{item['request_id']}", headers=auth()).status_code == 409
    assert client.get("/v1/me/deletion-requests", headers=auth()).json()["items"][0]["status"] == "cancelled"
    reopened = client.post("/v1/me/deletion-requests", headers=auth(), json={"scope": "account"})
    assert reopened.status_code == 201 and reopened.json()["request_id"] != item["request_id"]


def test_deletion_request_does_not_delete_anything(legal_env):
    char = client.post("/v1/workspaces/legal-ws/characters", headers=auth(), json={
        "identity": {"name": "Mina", "gender": "female", "face_shape": "oval", "hairstyle": "long", "body_type": "athletic", "skin_tone": "medium"},
        "outfits": [{"id": "o1", "name": "Casual", "category": "casual", "top": "shirt"}], "active_outfit_id": "o1", "asset_ids": []})
    assert char.status_code == 201, char.text
    assert client.post("/v1/me/deletion-requests", headers=auth(), json={"scope": "account"}).status_code == 201
    assert client.get(f"/v1/workspaces/legal-ws/characters/{char.json()['character_id']}", headers=auth()).status_code == 200


def test_workspace_content_request_needs_owner_and_a_workspace(legal_env):
    ok = client.post("/v1/me/deletion-requests", headers=auth(), json={"scope": "workspace_content", "workspace_id": "legal-ws"})
    assert ok.status_code == 201 and ok.json()["workspace_id"] == "legal-ws"
    assert client.post("/v1/me/deletion-requests", headers=auth(), json={"scope": "workspace_content"}).status_code == 422
    assert client.post("/v1/me/deletion-requests", headers=auth(), json={"scope": "account", "workspace_id": "legal-ws"}).status_code == 422
    # a non-member sees the workspace as missing; a non-owner member is forbidden
    assert client.post("/v1/me/deletion-requests", headers=auth("token-user-b"), json={"scope": "workspace_content", "workspace_id": "legal-ws"}).status_code == 404
    assert client.post("/v1/workspaces/legal-ws/members", headers=auth(), json={"user_id": "user-b", "role": "editor"}).status_code == 201
    assert client.post("/v1/me/deletion-requests", headers=auth("token-user-b"), json={"scope": "workspace_content", "workspace_id": "legal-ws"}).status_code == 403


def test_other_users_cannot_see_or_cancel_a_deletion_request(legal_env):
    item = client.post("/v1/me/deletion-requests", headers=auth(), json={"scope": "account"}).json()
    assert client.get("/v1/me/deletion-requests", headers=auth("token-user-b")).json()["items"] == []
    assert client.delete(f"/v1/me/deletion-requests/{item['request_id']}", headers=auth("token-user-b")).status_code == 404
    assert client.get("/v1/me/deletion-requests", headers=auth()).json()["items"][0]["status"] == "pending"


def test_concurrent_identical_deletion_requests_create_one_pending_row(legal_env):
    import threading
    client.get("/v1/me/legal-status", headers=auth())  # create tables before the threads start
    barrier, codes = threading.Barrier(8), []

    def post():
        barrier.wait()
        codes.append(client.post("/v1/me/deletion-requests", headers=auth(), json={"scope": "account"}).status_code)

    threads = [threading.Thread(target=post) for _ in range(8)]
    [t.start() for t in threads]; [t.join() for t in threads]
    assert sorted(set(codes)) in ([200, 201], [201]), codes
    assert codes.count(201) == 1, codes
    items = client.get("/v1/me/deletion-requests", headers=auth()).json()["items"]
    assert len(items) == 1 and items[0]["status"] == "pending"


def _consent(token="token-user-a"):
    items = client.get("/v1/me/consents", headers=auth(token)).json()["items"]
    return {i["purpose"]: i["granted"] for i in items}


def test_ai_training_consent_defaults_to_refused_and_needs_auth(legal_env):
    assert client.get("/v1/me/consents").status_code == 401
    assert client.put("/v1/me/consents/ai_training", json={"granted": True}).status_code == 401
    assert _consent() == {"ai_training": False}


def test_consent_grant_withdraw_regrant_keeps_history_and_latest_wins(legal_env):
    from app.assets.store import _connect
    for granted in (True, False, True):
        assert client.put("/v1/me/consents/ai_training", headers=auth(), json={"granted": granted}).status_code == 200
    assert _consent() == {"ai_training": True}
    client.put("/v1/me/consents/ai_training", headers=auth(), json={"granted": False})
    assert _consent() == {"ai_training": False}
    with _connect() as db:
        assert db.execute("SELECT COUNT(*) AS n FROM consents WHERE user_id='user-a'").fetchone()["n"] == 4


def test_consent_is_isolated_per_user_and_rejects_unknown_purpose(legal_env):
    client.put("/v1/me/consents/ai_training", headers=auth(), json={"granted": True})
    assert _consent("token-user-b") == {"ai_training": False}
    assert client.put("/v1/me/consents/marketing", headers=auth(), json={"granted": True}).status_code == 404
    assert client.put("/v1/me/consents/ai_training", headers=auth(), json={"granted": "yes please", "x": 1}).status_code == 422


def test_consent_is_not_part_of_required_document_acceptance(legal_env):
    client.post("/v1/me/legal-acceptances", headers=auth(), json={"documents": _all_current()})
    assert client.get("/v1/me/legal-status", headers=auth()).json()["accepted"] is True
    assert _consent() == {"ai_training": False}


def test_a_consent_row_records_the_privacy_policy_version_it_was_given_under(legal_env, monkeypatch):
    """The version is the evidence of which text the user agreed to, so it must be stored, and the right one."""
    from app.assets.store import _connect
    client.put("/v1/me/consents/ai_training", headers=auth(), json={"granted": True})
    monkeypatch.setenv("LEGAL_DOCUMENT_VERSIONS", "privacy=2027-01-01")
    client.put("/v1/me/consents/ai_training", headers=auth(), json={"granted": False})
    with _connect() as db:
        rows = db.execute("SELECT granted, version FROM consents WHERE user_id='user-a' ORDER BY seq").fetchall()
    assert [(r["granted"], r["version"]) for r in rows] == [(1, "draft-2026-11-09"), (0, "2027-01-01")]
    assert _consent()["ai_training"] is False
