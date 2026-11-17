"""B-07 (second part): the OWNER/ADMIN-only operations outside members / settings / reviews — workspace data exports, job-output review and asset-link tools, provider reconciliation,
poll-task admin. Same rule as test_authz_roles: allowed roles are let through (the answer may be 404/409/422 for the sample ids), editors and viewers get 403, a stranger 403/404, nobody 401.
The job used here is created by the owner in workspace wa (mock provider)."""
import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import app
from tests.test_authz_matrix import _body
from tests.test_authz_roles import ADMINS, WHO, auth
from tests.test_members import team  # noqa: F401
from tests.test_photo_steps_api import env  # noqa: F401

client = TestClient(app)
JOB_BODY = {"workspace_id": "wa", "model_image_url": "https://example.com/model.jpg", "garment_image_url": "https://example.com/garment.jpg"}

TABLE = [
    ("GET", "/v1/workspaces/wa/exports", ADMINS),
    ("GET", "/v1/generation-jobs/{job}/outputs/out_none/asset-link-events", ADMINS),
    ("GET", "/v1/generation-jobs/{job}/outputs/out_none/review", ADMINS),
    ("POST", "/v1/generation-jobs/{job}/outputs/out_none/asset-link-retry", ADMINS),
    ("POST", "/v1/generation-jobs/{job}/reconciliation", ADMINS),
    ("GET", "/internal/ops/poll-tasks?workspace_id=wa", ADMINS),
    ("POST", "/internal/ops/poll-tasks/task_none/retry", ADMINS),
]


def _op(method, url):
    """The OpenAPI operation whose path template matches this concrete URL."""
    import re
    concrete = url.split("?")[0]
    for template, item in app.openapi()["paths"].items():
        if method.lower() in item and re.fullmatch(re.sub(r"\{[^}]+\}", "[^/]+", template), concrete):
            return item[method.lower()]
    raise AssertionError(f"no OpenAPI operation for {method} {concrete}")


@pytest.mark.parametrize("method,template,allowed", TABLE, ids=[f"{m} {t.split('?')[0]}" for m, t, _ in TABLE])
def test_admin_only_operations_are_closed_to_editors_viewers_strangers_and_nobody(team, monkeypatch, method, template, allowed):
    monkeypatch.setattr(config, "PROVIDER_MODE", "mock")
    created = client.post("/v1/generation-jobs", headers=auth("a"), json=JOB_BODY)
    assert created.status_code in (200, 201, 202), created.text[:200]
    url = template.replace("{job}", created.json()["job_id"])
    op = _op(method, url)
    body = None
    if "requestBody" in op:
        body = _body(op, {"workspace_id": "wa"})
        if isinstance(body, dict) and "reason" in body:
            body["reason"] = "authorization table check"

    def call(who):
        kw = {"headers": auth(who)} if who else {}
        if body is not None:
            kw["json"] = body
        return client.request(method, url, **kw).status_code

    for role, who in WHO.items():
        got = call(who)
        if role in allowed:
            assert got not in (401, 403), (role, got)
        else:
            assert got == 403, (role, got)
    assert call("b") in (403, 404), "a stranger"
    assert call(None) == 401, "nobody"
