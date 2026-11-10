"""Access log (L-05): useful fields, and nothing sensitive."""
import json
import logging
import logging.handlers

import pytest
from fastapi.testclient import TestClient

from app import access_log
from app.main import app

SECRET_TOKEN = "tok-very-secret-bearer-value"
SIGNATURE = "SIGNATURE-must-never-be-logged-0123456789abcdef"


class Capture(logging.Handler):
    def __init__(self):
        super().__init__(); self.lines = []
    def emit(self, record):
        self.lines.append(record.getMessage())
    def records(self):
        return [json.loads(line) for line in self.lines]


@pytest.fixture
def log(tmp_path, monkeypatch):
    import app.config as config
    from app.assets.store import create_workspace
    monkeypatch.setattr(config, "ASSET_DATABASE_PATH", tmp_path / "log.sqlite3")
    monkeypatch.setattr(config, "ASSET_STORAGE_DIR", tmp_path / "private")
    monkeypatch.setattr(config, "asset_api_tokens", lambda: {SECRET_TOKEN: "user-a"})
    monkeypatch.setattr(config, "ASSET_SIGNING_SECRET", "s" * 48)
    monkeypatch.setattr(config, "ACCESS_LOG_ENABLED", True)
    monkeypatch.setattr(config, "ACCESS_LOG_ACTOR", "hash")
    monkeypatch.setattr(config, "ACCESS_LOG_CLIENT_IP", False)
    create_workspace("ws-log", "user-a")
    capture = Capture()
    logger = logging.getLogger(access_log.LOGGER_NAME)
    logger.addHandler(capture)
    yield capture, TestClient(app, raise_server_exceptions=False), config
    logger.removeHandler(capture)


def auth(token=SECRET_TOKEN):
    return {"Authorization": f"Bearer {token}"}


def test_a_request_is_logged_with_the_route_template_status_and_duration(log):
    capture, client, _ = log
    res = client.get("/v1/workspaces", headers=auth())
    assert res.status_code == 200
    (record,) = capture.records()
    assert record["event"] == "http_request" and record["method"] == "GET" and record["route"] == "/v1/workspaces" and record["status"] == 200
    assert record["duration_ms"] >= 0 and record["ts"].endswith("+00:00") and record["request_id"] == res.headers["X-Request-ID"]
    assert set(record) == {"ts", "event", "request_id", "method", "route", "status", "duration_ms", "workspace_id", "actor"}


def test_secrets_and_query_strings_never_reach_the_log(log):
    capture, client, _ = log
    client.get(f"/v1/assets/ast_x/preview?expires=1&signature={SIGNATURE}")
    client.get("/v1/workspaces", headers=auth())
    client.get("/v1/workspaces", headers=auth("wrong-token-value"))
    text = "\n".join(capture.lines)
    for forbidden in (SIGNATURE, SECRET_TOKEN, "wrong-token-value", "expires=", "signature", "Bearer"):
        assert forbidden not in text, forbidden
    assert any(r["route"] == "/v1/assets/{asset_id}/preview" for r in capture.records()), "the template, not the id, is logged"
    assert "ast_x" not in text


def test_the_route_template_hides_ids_and_unmatched_paths_are_not_echoed(log):
    capture, client, _ = log
    client.get("/v1/workspaces/ws-log/characters", headers=auth())
    client.get("/no/such/path/with-\"quote\"-and-%0Anewline")
    first, second = capture.records()
    assert first["route"] == "/v1/workspaces/{workspace_id}/characters" and first["workspace_id"] == "ws-log"
    assert second["route"] == "unmatched" and second["status"] == 404
    assert "no/such" not in "\n".join(capture.lines) and len(capture.lines) == 2, "one line per request, no injected extra lines"


def test_workspace_id_from_the_query_is_logged_only_when_it_looks_like_an_id(log):
    capture, client, _ = log
    client.get("/v1/assets?workspace_id=ws-log", headers=auth())
    client.get("/v1/assets?workspace_id=" + "x" * 300, headers=auth())
    client.get("/v1/assets?workspace_id=<script>alert(1)</script>", headers=auth())
    ids = [r["workspace_id"] for r in capture.records()]
    assert ids == ["ws-log", None, None]


def test_failed_authentication_is_logged_without_an_actor(log):
    capture, client, _ = log
    assert client.get("/v1/workspaces").status_code == 401
    assert client.get("/v1/workspaces", headers=auth("nope")).status_code == 401
    records = capture.records()
    assert [r["status"] for r in records] == [401, 401] and [r["actor"] for r in records] == [None, None]


def test_a_caller_supplied_request_id_is_used_only_if_it_is_a_plain_token(log):
    capture, client, _ = log
    good = client.get("/health", headers={"X-Request-ID": "client-req-0123456789"})
    assert good.headers["X-Request-ID"] == "client-req-0123456789"
    generated = []
    for bad in ("short", "has space in it 123456", "x" * 65, "new\\nline-forged-12345", "semi;colon;injection1"):
        res = client.get("/health", headers={"X-Request-ID": bad})
        assert res.headers["X-Request-ID"] != bad and len(res.headers["X-Request-ID"]) == 32, bad
        generated.append(res.headers["X-Request-ID"])
    assert "forged" not in "\n".join(capture.lines)
    assert len(set(generated)) == len(generated), "every replaced id must be a fresh unique one"
    assert [r["request_id"] for r in capture.records()][1:] == generated


@pytest.mark.parametrize("mode", ["hash", "plain", "none"])
def test_the_actor_is_pseudonymised_by_default_and_can_be_plain_or_absent(log, mode):
    capture, client, config = log
    config.ACCESS_LOG_ACTOR = mode
    client.get("/v1/workspaces", headers=auth())
    actor = capture.records()[0]["actor"]
    if mode == "plain":
        assert actor == "user-a"
    elif mode == "none":
        assert actor is None
    else:
        assert actor.startswith("h_") and len(actor) == 18 and "user-a" not in actor
        assert access_log.actor_label("user-a") == actor and access_log.actor_label("user-b") != actor


def test_the_client_ip_is_not_logged_unless_enabled(log):
    capture, client, config = log
    client.get("/health")
    assert "client_ip" not in capture.records()[0]
    config.ACCESS_LOG_CLIENT_IP = True
    client.get("/health")
    assert "client_ip" in capture.records()[1]


def test_logging_can_be_switched_off(log):
    capture, client, config = log
    config.ACCESS_LOG_ENABLED = False
    assert client.get("/health").status_code == 200
    assert capture.lines == []


def test_an_unhandled_error_is_logged_as_500_with_the_error_class_only(log, monkeypatch):
    capture, client, _ = log
    def boom(authorization):
        raise RuntimeError("secret internals: " + SECRET_TOKEN)
    monkeypatch.setattr("app.assets.routes._authenticate", boom)
    res = client.get("/v1/auth/me", headers=auth())
    assert res.status_code == 500
    record = capture.records()[-1]
    assert record["status"] == 500 and record["error"] == "RuntimeError"
    assert SECRET_TOKEN not in "\n".join(capture.lines) and "internals" not in "\n".join(capture.lines)


def test_file_logging_rotates_daily_and_keeps_a_bounded_number_of_files(tmp_path, monkeypatch):
    import app.config as config
    monkeypatch.setattr(config, "ACCESS_LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr(config, "ACCESS_LOG_RETENTION_DAYS", 7)
    logger = access_log.configure_access_log()
    try:
        handler = next(h for h in logger.handlers if getattr(h, "_acs_access", False))
        assert isinstance(handler, logging.handlers.TimedRotatingFileHandler)
        assert handler.backupCount == 7 and handler.when == "MIDNIGHT" and handler.utc is True
        logger.info(json.dumps({"event": "probe"}))
        handler.flush()
        assert (tmp_path / "logs" / "access.log").read_text(encoding="utf-8").strip() == '{"event": "probe"}'
        # configuring again replaces the handler instead of stacking duplicates
        access_log.configure_access_log()
        assert len([h for h in logger.handlers if getattr(h, "_acs_access", False)]) == 1
    finally:
        monkeypatch.setattr(config, "ACCESS_LOG_DIR", None)
        access_log.configure_access_log()


def test_log_settings_reject_unsafe_values():
    import os
    import subprocess
    import sys

    def run(**env_values):
        env = {k: v for k, v in os.environ.items() if not k.startswith("ACCESS_LOG_")}
        env.update(env_values)
        return subprocess.run([sys.executable, "-I", "-c", "import sys; sys.path.insert(0, '.'); import app.config as c; print(c.ACCESS_LOG_ACTOR, c.ACCESS_LOG_RETENTION_DAYS, c.ACCESS_LOG_ENABLED)"],
                              capture_output=True, text=True, env=env)
    ok = run()
    assert ok.stdout.split() == ["hash", "30", "True"], ok.stderr[-200:]
    assert run(ACCESS_LOG_ACTOR="everything").returncode != 0
    assert run(ACCESS_LOG_DIR="/tmp/x-logs", ACCESS_LOG_RETENTION_DAYS="0").returncode != 0, "retention 0 would keep files forever"
    assert run(ACCESS_LOG_RETENTION_DAYS="abc").returncode != 0
    assert run(ACCESS_LOG_ENABLED="false").stdout.split()[2] == "False"


# ---- DEV_ACCEPTANCE_PACK L-05: request bodies and signed URLs inside bodies never reach the log; the documented list matches the code ----
BODY_MARKER = "BODY-MARKER-prompt-text-must-not-be-logged-7f3a"
BODY_SIGNATURE = "BODY-SIGNATURE-must-never-be-logged-9c1d4e"


def test_request_bodies_and_signed_urls_inside_bodies_never_reach_the_log(log):
    capture, client, _ = log
    res = client.post("/v1/generation-jobs", headers=auth(), json={
        "workspace_id": "ws-log", "prompt": BODY_MARKER,
        "model_image_url": f"https://images.example.org/m.png?expires=1&signature={BODY_SIGNATURE}",
        "garment_image_url": "https://images.example.org/g.png"})
    assert res.status_code == 202, res.text
    client.post("/v1/workspaces", headers=auth(), json={"workspace_id": "ws-body-marker-" + BODY_MARKER[-4:]})
    text = "\n".join(capture.lines)
    for forbidden in (BODY_MARKER, BODY_SIGNATURE, "images.example.org", "prompt", "model_image_url"):
        assert forbidden not in text, forbidden


def test_a_log_line_has_only_the_documented_keys(log, monkeypatch):
    capture, client, config = log
    client.get("/v1/workspaces", headers=auth())
    client.get("/v1/workspaces", headers=auth("wrong"))
    client.get("/no/such/route")
    for record in capture.records():
        assert set(record) == set(access_log.LOGGED_FIELDS), sorted(record)
    monkeypatch.setattr(config, "ACCESS_LOG_CLIENT_IP", True)
    client.get("/v1/workspaces", headers=auth())
    assert set(capture.records()[-1]) == set(access_log.LOGGED_FIELDS) | {"client_ip"}
    assert set(access_log.OPTIONAL_FIELDS) == {"error", "client_ip"}


def _runbook_section():
    from pathlib import Path
    text = (Path(__file__).resolve().parents[2] / "docs" / "RUNBOOK.md").read_text(encoding="utf-8")
    start = text.index("## 3-1. 접근 로그")
    end = text.index("\n## ", start + 5)
    return text[start:end]


def test_the_runbook_documents_exactly_the_keys_the_code_can_log():
    import re
    section = _runbook_section()
    documented = set(re.findall(r"^\| `([a-z_]+)` \|", section, flags=re.M))
    assert documented == set(access_log.LOGGED_FIELDS) | set(access_log.OPTIONAL_FIELDS), sorted(documented)


def test_the_runbook_says_what_is_never_logged_and_how_expired_logs_go():
    section = _runbook_section()
    for phrase in ("쿼리 문자열", "본문", "토큰", "ACCESS_LOG_RETENTION_DAYS", "만료된 로그"):
        assert phrase in section, phrase
