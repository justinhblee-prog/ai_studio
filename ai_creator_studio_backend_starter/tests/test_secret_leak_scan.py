"""B-10: configured secrets must not appear in any response (body or headers) or log line. Canary values are put into every secret setting, then every GET operation in the
OpenAPI document is called as a platform operator (the most privileged caller), plus unauthenticated / bad-token / malformed-body calls; the canaries must appear nowhere.
A static scan also checks that no source line sends a secret setting to a logger or print. No real secrets are used or read: only canary strings."""
import logging
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app, raise_server_exceptions=False)
CANARIES = {
    "FASHN_API_KEY": "canary-fashn-key-7f3a91c2",
    "ASSET_SIGNING_SECRET": "canary-signing-secret-0123456789-abcdef-7f3a91c2",
    "SUPABASE_ANON_KEY": "canary-supabase-anon-7f3a91c2",
    "OPS_ALERT_WEBHOOK_TOKEN": "canary-webhook-token-7f3a91c2",
    "DATABASE_URL": "postgresql://canaryuser:canary-db-password-7f3a91c2@127.0.0.1:1/canarydb",
}
SECRET_PARTS = ["canary-fashn-key-7f3a91c2", "canary-signing-secret", "canary-supabase-anon", "canary-webhook-token", "canary-db-password-7f3a91c2", "canaryuser"]
BEARER = "canary-bearer-token-7f3a91c2"


@pytest.fixture
def secrets_env(tmp_path, monkeypatch):
    import app.config as config
    monkeypatch.setattr(config, "ASSET_DATABASE_PATH", tmp_path / "assets.sqlite3")
    monkeypatch.setattr(config, "ASSET_STORAGE_DIR", tmp_path / "assets")
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path / "outputs")
    monkeypatch.setattr(config, "asset_api_tokens", lambda: {BEARER: "user-a"})
    monkeypatch.setattr(config, "OPS_ADMIN_USER_IDS", ("user-a",))
    monkeypatch.setattr(config, "PROVIDER_MODE", "mock")
    for name, value in CANARIES.items():
        monkeypatch.setattr(config, name, value, raising=False)
    from app.assets.store import create_workspace
    create_workspace("ws-leak", "user-a")
    return config


def _seen(response) -> list[str]:
    haystack = response.text + "\n" + "\n".join(f"{k}: {v}" for k, v in response.headers.items())
    return [p for p in SECRET_PARTS if p in haystack]


def _get_operations():
    for path, item in app.openapi()["paths"].items():
        op = item.get("get")
        if op:
            yield path, op


def test_no_get_operation_returns_or_logs_a_secret(secrets_env, caplog):
    caplog.set_level(logging.DEBUG)
    headers = {"Authorization": f"Bearer {BEARER}"}
    leaks, called = [], 0
    for path, op in _get_operations():
        url = re.sub(r"\{[^}]+\}", "x", path)
        query = {p["name"]: ("ws-leak" if p["name"] == "workspace_id" else "x") for p in op.get("parameters", []) if p.get("in") == "query" and p.get("required")}
        for h in (headers, {}):
            r = client.get(url, headers=h, params=query)
            called += 1
            if _seen(r):
                leaks.append((path, bool(h), _seen(r)))
    assert called > 100, called
    assert not leaks, leaks
    logged = [p for p in SECRET_PARTS + [BEARER] if p in caplog.text]
    assert not logged, f"log lines contain: {logged}"


@pytest.mark.parametrize("method,url,kw", [
    ("POST", "/v1/generation-jobs", {"content": b"{not json"}),
    ("POST", "/v1/generation-jobs", {"json": {"workspace_id": "ws-leak"}}),
    ("POST", "/v1/workspaces", {"json": {"workspace_id": 5}}),
    ("GET", "/v1/assets/ast_missing", {}),
    ("GET", "/v1/assets", {}),
    ("DELETE", "/v1/assets/ast_missing", {}),
])
def test_error_responses_do_not_contain_secrets_and_do_not_echo_the_token(secrets_env, caplog, method, url, kw):
    caplog.set_level(logging.DEBUG)
    for token in (BEARER, "canary-wrong-token-7f3a91c2", None):
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"} if token else {}
        r = client.request(method, url, headers=headers, **kw)
        assert not _seen(r), (method, url, r.status_code)
        assert BEARER not in r.text and "canary-wrong-token" not in r.text, "the token a caller sent is never echoed"
    assert "canary-wrong-token-7f3a91c2" not in caplog.text and BEARER not in caplog.text, "tokens are not logged"


SECRET_NAMES = ["FASHN_API_KEY", "ASSET_SIGNING_SECRET", "SUPABASE_ANON_KEY", "OPS_ALERT_WEBHOOK_TOKEN", "DATABASE_URL", "SERVICE_ROLE", "JWT_SECRET", "PASSWORD"]


def test_no_source_line_sends_a_secret_setting_to_a_logger_or_print():
    sink = re.compile(r"\b(print|logger\.\w+|logging\.\w+|log\.\w+|warnings\.warn)\(")
    bad = []
    for path in sorted(Path(__file__).resolve().parents[1].glob("app/**/*.py")):
        for no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if sink.search(line) and any(re.search(rf"\b{n}\b", line) for n in SECRET_NAMES) and "# noqa: secret-ok" not in line:
                bad.append(f"{path.name}:{no}: {line.strip()[:120]}")
    assert not bad, bad
