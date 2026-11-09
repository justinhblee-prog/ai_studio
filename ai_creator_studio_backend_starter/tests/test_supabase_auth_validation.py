from __future__ import annotations

import httpx
import pytest
from fastapi import HTTPException

from app import config
from app.assets import routes


class FakeResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def test_current_user_validates_supabase_access_token(monkeypatch):
    monkeypatch.setattr(config, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(config, "SUPABASE_ANON_KEY", "public-key")
    seen = {}

    def fake_get(url, *, headers, timeout):
        seen.update(url=url, headers=headers, timeout=timeout)
        return FakeResponse(200, {"id": "auth-user-123", "email": "user@example.com"})

    monkeypatch.setattr(routes.httpx, "get", fake_get)
    assert routes.current_user("Bearer signed-access-token") == "auth-user-123"
    assert seen["url"] == "https://example.supabase.co/auth/v1/user"
    assert seen["headers"] == {"apikey": "public-key", "Authorization": "Bearer signed-access-token"}
    assert seen["timeout"] == 5.0


def test_current_user_rejects_invalid_supabase_token(monkeypatch):
    monkeypatch.setattr(config, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(config, "SUPABASE_ANON_KEY", "public-key")
    monkeypatch.setattr(routes.httpx, "get", lambda *args, **kwargs: FakeResponse(401, {"message": "invalid"}))
    with pytest.raises(HTTPException) as error:
        routes.current_user("Bearer bad-token")
    assert error.value.status_code == 401


def test_current_user_fails_closed_when_supabase_config_is_partial(monkeypatch):
    monkeypatch.setattr(config, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(config, "SUPABASE_ANON_KEY", "")
    with pytest.raises(HTTPException) as error:
        routes.current_user("Bearer token")
    assert error.value.status_code == 503


def test_current_user_maps_supabase_outage_to_service_unavailable(monkeypatch):
    monkeypatch.setattr(config, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(config, "SUPABASE_ANON_KEY", "public-key")

    def fail(*args, **kwargs):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(routes.httpx, "get", fail)
    with pytest.raises(HTTPException) as error:
        routes.current_user("Bearer token")
    assert error.value.status_code == 503


def test_current_user_keeps_static_mapping_for_local_only_mode(monkeypatch):
    monkeypatch.setattr(config, "SUPABASE_URL", "")
    monkeypatch.setattr(config, "SUPABASE_ANON_KEY", "")
    monkeypatch.setattr(config, "asset_api_tokens", lambda: {"local-token": "local-user"})
    assert routes.current_user("Bearer local-token") == "local-user"


def test_current_user_requires_bearer_header():
    with pytest.raises(HTTPException) as error:
        routes.current_user(None)
    assert error.value.status_code == 401


def test_current_user_rejects_supabase_payload_without_identity(monkeypatch):
    monkeypatch.setattr(config, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(config, "SUPABASE_ANON_KEY", "public-key")
    monkeypatch.setattr(routes.httpx, "get", lambda *args, **kwargs: FakeResponse(200, []))
    with pytest.raises(HTTPException) as error:
        routes.current_user("Bearer token")
    assert error.value.status_code == 401
