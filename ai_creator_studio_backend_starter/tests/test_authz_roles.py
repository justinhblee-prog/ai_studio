"""B-07: one table of WHO may call each workspace operation: owner, admin, editor, viewer, a stranger (owner of another workspace) and nobody (no login).
Existing tests cover each area on its own; this table keeps the whole picture in one place, so a role gate that is loosened or dropped shows up here.
"allowed" means authorization lets the call through (the answer may still be 404/409/422 because the sample ids do not exist); "denied" must be 403
(a stranger may also get 404, nobody gets 401). Only operations that are harmless to repeat are listed.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.test_asset_reviews import ask, asset
from tests.test_members import team  # noqa: F401  (wa: owner a, viewer c, editor d, admin e, admin f, editor g; wb: owner b)
from tests.test_photo_steps_api import auth, env  # noqa: F401  (the fixture `team` builds on `env`)

client = TestClient(app)
W = "/v1/workspaces/wa"
WHO = {"owner": "a", "admin": "e", "editor": "d", "viewer": "c"}
ALL4 = {"owner", "admin", "editor", "viewer"}
ADMINS = {"owner", "admin"}
WRITERS = {"owner", "admin", "editor"}
# (method, url, json, who may call it)
TABLE = [
    ("GET", f"{W}/members", None, ALL4),
    ("GET", f"{W}/members-history", None, ADMINS),
    ("PATCH", f"{W}/members/user-nobody", {"role": "viewer"}, ADMINS),
    ("GET", f"{W}/settings", None, ALL4),
    ("PATCH", f"{W}/settings", {"forbid_self_approval": False}, ADMINS),
    ("GET", f"{W}/settings/history", None, ADMINS),
    ("GET", f"{W}/reviews", None, ALL4),
    ("GET", f"{W}/reviews/status", None, ALL4),
    ("POST", f"{W}/reviews", {"asset_id": "ast_nobody"}, WRITERS),
    ("POST", f"{W}/reviews/{{rev}}/approve", {}, ADMINS),
    ("POST", f"{W}/reviews/{{rev}}/reject", {"comment": "no"}, ADMINS),
    ("POST", f"{W}/reviews/{{rev}}/request-changes", {"comment": "no"}, ADMINS),
    ("GET", f"{W}/library", None, ALL4),
    ("GET", "/v1/assets?workspace_id=wa", None, ALL4),
]


_n = [0]


def call(method, url, body, who):
    if "{rev}" in url:       # a decision needs a real open review (a missing one answers 404 before the role is looked at): a fresh one per call
        _n[0] += 1
        review_id = ask(asset("a", (1 + _n[0] % 250, 7, 7)), "d").json()["review_id"]
        url = url.replace("{rev}", review_id)
    kw = {"headers": auth(who)} if who else {}
    if body is not None:
        kw["json"] = body
    return client.request(method, url, **kw)


@pytest.mark.parametrize("method,url,body,allowed", TABLE, ids=[f"{m} {u.split('wa', 1)[-1]}" for m, u, _, _ in TABLE])
def test_each_operation_is_open_to_exactly_its_roles(team, method, url, body, allowed):
    for role, who in WHO.items():
        got = call(method, url, body, who).status_code
        if role in allowed:
            assert got not in (401, 403), (role, got)
        else:
            assert got == 403, (role, got)
    assert call(method, url, body, "b").status_code in (403, 404), "a stranger"
    assert call(method, url, body, None).status_code == 401, "nobody"


def test_the_table_covers_every_role_gate_that_matters():
    kinds = {frozenset(a) for *_, a in TABLE}
    assert kinds == {frozenset(ALL4), frozenset(ADMINS), frozenset(WRITERS)}
