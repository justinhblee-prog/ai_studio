import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def auth(token="token-user-a"):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def env(tmp_path, monkeypatch):
    import app.config as config
    monkeypatch.setattr(config, "ASSET_STORAGE_DIR", tmp_path / "private")
    monkeypatch.setattr(config, "ASSET_DATABASE_PATH", tmp_path / "enforce.sqlite3")
    monkeypatch.setattr(config, "GENERATION_DATABASE_PATH", tmp_path / "generation.sqlite3")
    monkeypatch.setattr(config, "ASSET_SIGNING_SECRET", "s" * 48)
    monkeypatch.setattr(config, "asset_api_tokens", lambda: {"token-user-a": "user-a", "token-user-b": "user-b"})
    monkeypatch.delenv("LEGAL_DOCUMENT_VERSIONS", raising=False)
    # Workspaces are created while enforcement is still off, the way pre-existing users would have them.
    assert client.post("/v1/workspaces", headers=auth(), json={"workspace_id": "enf-ws"}).status_code == 201
    monkeypatch.setattr(config, "LEGAL_REQUIRE_ACCEPTANCE", True)
    return monkeypatch


def accept(token="token-user-a"):
    docs = client.get("/v1/legal/documents").json()["documents"]
    res = client.post("/v1/me/legal-acceptances", headers=auth(token), json={"documents": [{"document": d["document"], "version": d["version"]} for d in docs]})
    assert res.status_code == 200, res.text


def test_a_user_who_has_not_accepted_is_refused_everywhere_except_the_accept_paths(env):
    for method, path in (("get", "/v1/workspaces"), ("get", "/v1/assets?workspace_id=enf-ws"), ("get", "/v1/generation-jobs?workspace_id=enf-ws"),
                         ("get", "/v1/workspaces/enf-ws/characters")):
        res = getattr(client, method)(path, headers=auth())
        assert res.status_code == 403, (path, res.status_code, res.text)
        assert res.json()["detail"]["code"] == "LEGAL_ACCEPTANCE_REQUIRED"
    assert client.post("/v1/generation-jobs", headers=auth(), json={"workspace_id": "enf-ws", "model_image_url": "https://example.com/m.jpg", "garment_image_url": "https://example.com/g.jpg"}).status_code == 403


def test_the_paths_needed_to_accept_withdraw_or_delete_stay_open(env):
    assert client.get("/v1/auth/me", headers=auth()).status_code == 200
    assert client.get("/v1/me/legal-status", headers=auth()).status_code == 200
    assert client.get("/v1/me/consents", headers=auth()).status_code == 200
    assert client.put("/v1/me/consents/ai_training", headers=auth(), json={"granted": False}).status_code == 200
    assert client.post("/v1/me/deletion-requests", headers=auth(), json={"scope": "account"}).status_code == 201
    assert client.get("/v1/me/deletion-requests", headers=auth()).status_code == 200
    assert client.get("/v1/legal/documents").status_code == 200


def test_accepting_opens_the_rest_and_only_for_that_user(env):
    accept()
    assert client.get("/v1/workspaces", headers=auth()).status_code == 200
    assert client.get("/v1/workspaces", headers=auth("token-user-b")).status_code == 403


def test_a_new_document_version_closes_the_gate_again_until_re_accepted(env):
    accept()
    assert client.get("/v1/workspaces", headers=auth()).status_code == 200
    env.setenv("LEGAL_DOCUMENT_VERSIONS", "terms=2027-01-01")
    assert client.get("/v1/workspaces", headers=auth()).status_code == 403
    accept()
    assert client.get("/v1/workspaces", headers=auth()).status_code == 200


def test_with_the_flag_off_nothing_changes(env):
    import app.config as config
    env.setattr(config, "LEGAL_REQUIRE_ACCEPTANCE", False)
    assert client.get("/v1/workspaces", headers=auth("token-user-b")).status_code == 200


def test_authentication_is_still_checked_first(env):
    assert client.get("/v1/workspaces").status_code == 401
    assert client.get("/v1/workspaces", headers=auth("wrong-token")).status_code == 401
