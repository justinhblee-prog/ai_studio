from fastapi.testclient import TestClient

from app import config
from app.main import app


def test_runtime_readiness_is_platform_operator_only_and_redacts_credentials(monkeypatch):
    monkeypatch.setattr(config, "OPS_ADMIN_USER_IDS", ("platform-operator",))
    monkeypatch.setattr(config, "DATABASE_URL", "postgresql://private-user:private-password@db.invalid/app")
    monkeypatch.setattr(config, "FASHN_API_KEY", "provider-secret")

    monkeypatch.setattr(config, "asset_api_tokens", lambda: {"ops-token": "platform-operator", "member-token": "workspace-member"})
    client = TestClient(app)

    assert client.get("/internal/ops/runtime-readiness").status_code == 401
    assert client.get("/internal/ops/runtime-readiness", headers={"Authorization": "Bearer member-token"}).status_code == 403

    response = client.get("/internal/ops/runtime-readiness", headers={"Authorization": "Bearer ops-token"})
    assert response.status_code == 200
    body = response.json()
    assert body["scope"] == "read-only-preflight"
    assert body["database_url_configured"] is True
    assert "private-password" not in response.text
    assert "provider-secret" not in response.text
