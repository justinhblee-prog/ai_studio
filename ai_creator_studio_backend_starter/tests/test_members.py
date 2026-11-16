"""Lane 6: member list / role change / removal / leaving, GET /v1/me, immutable history."""
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import app
from tests.test_photo_steps_api import auth, env  # noqa: F401  (wa: owner a + viewer c, wb: owner b)

client = TestClient(app)
M = "/v1/workspaces/wa/members"


@pytest.fixture
def team(env, monkeypatch):
    """wa: owner a, viewer c, editor d, admin e, admin f, editor g; wb: owner b."""
    monkeypatch.setattr(config, "asset_api_tokens", lambda: {f"token-{n}": f"user-{n}" for n in "abcdefg"})
    for u, r in (("d", "editor"), ("e", "admin"), ("f", "admin"), ("g", "editor")):
        assert client.post(M, headers=auth("a"), json={"user_id": f"user-{u}", "role": r}).status_code == 201
    return env


def roles():
    return {m["user_id"]: m["role"] for m in client.get(M, headers=auth("a")).json()["items"]}


def test_everyone_in_the_workspace_reads_the_list_ordered_by_role_nobody_else_does(team):
    r = client.get(M, headers=auth("c"))
    assert r.status_code == 200
    items = r.json()["items"]
    assert [m["role"] for m in items] == ["owner", "admin", "admin", "editor", "editor", "viewer"] and items[0]["user_id"] == "user-a"
    assert all(set(m) == {"user_id", "role", "created_at"} for m in items)
    assert client.get(M, headers=auth("b")).status_code in (403, 404) and client.get(M).status_code == 401


def test_the_owner_changes_any_non_owner_and_the_history_records_it(team):
    for who, role in (("c", "editor"), ("d", "viewer"), ("e", "editor"), ("g", "admin")):
        r = client.patch(f"{M}/user-{who}", headers=auth("a"), json={"role": role})
        assert r.status_code == 200 and r.json()["role"] == role
    assert roles()["user-g"] == "admin" and roles()["user-e"] == "editor"
    same = client.patch(f"{M}/user-g", headers=auth("a"), json={"role": "admin"})
    assert same.status_code == 200
    ev = client.get("/v1/workspaces/wa/members-history", headers=auth("a")).json()
    assert [(e["member_id"], e["from_role"], e["to_role"], e["actor_id"]) for e in ev] == [("user-c", "viewer", "editor", "user-a"), ("user-d", "editor", "viewer", "user-a"),
                                                                                         ("user-e", "admin", "editor", "user-a"), ("user-g", "editor", "admin", "user-a")], "an unchanged role adds nothing"
    assert client.get("/v1/workspaces/wa/members-history", headers=auth("c")).status_code == 403


def test_an_admin_moves_editors_and_viewers_but_never_makes_or_unmakes_an_admin(team):
    assert client.patch(f"{M}/user-c", headers=auth("e"), json={"role": "editor"}).status_code == 200
    assert client.patch(f"{M}/user-d", headers=auth("e"), json={"role": "viewer"}).status_code == 200
    for target, role in (("g", "admin"), ("f", "editor"), ("e", "viewer")):
        r = client.patch(f"{M}/user-{target}", headers=auth("e"), json={"role": role})
        assert r.status_code == 403 and r.json()["detail"]["code"] == "MEMBER_ROLE_FORBIDDEN", (target, role)


def test_the_owner_role_is_never_changed_or_removed_here(team):
    for who in "ae":
        assert client.patch(f"{M}/user-a", headers=auth(who), json={"role": "viewer"}).status_code in (409, 403)
    r = client.patch(f"{M}/user-a", headers=auth("a"), json={"role": "admin"})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "MEMBER_OWNER_PROTECTED"
    for who in "ae":
        d = client.delete(f"{M}/user-a", headers=auth(who))
        assert d.status_code == 409 and d.json()["detail"]["code"] == "MEMBER_OWNER_PROTECTED"
    assert roles()["user-a"] == "owner"
    assert client.patch(f"{M}/user-d", headers=auth("a"), json={"role": "owner"}).status_code == 422, "nobody can be made owner here"


@pytest.mark.parametrize("body", [{}, {"role": "boss"}, {"role": None}, {"role": "admin", "x": 1}])
def test_bad_role_bodies_are_refused(team, body):
    assert client.patch(f"{M}/user-d", headers=auth("a"), json=body).status_code == 422


def test_viewers_editors_and_strangers_cannot_change_roles(team):
    for who in "cdgb":
        assert client.patch(f"{M}/user-c", headers=auth(who), json={"role": "editor"}).status_code in (403, 404)
    assert client.patch(f"{M}/user-nobody", headers=auth("a"), json={"role": "editor"}).status_code == 404
    assert client.patch(f"{M}/user-c", json={"role": "editor"}).status_code == 401
    assert roles()["user-c"] == "viewer"


def test_removing_and_leaving(team):
    assert client.delete(f"{M}/user-c", headers=auth("d")).status_code == 403, "an editor cannot remove another member"
    assert client.delete(f"{M}/user-g", headers=auth("e")).status_code == 204, "an admin removes an editor"
    assert client.delete(f"{M}/user-f", headers=auth("e")).status_code == 403, "an admin cannot remove another admin"
    assert client.delete(f"{M}/user-f", headers=auth("a")).status_code == 204, "the owner removes an admin"
    assert client.delete(f"{M}/user-d", headers=auth("d")).status_code == 204, "anyone may leave"
    assert client.get("/v1/workspaces/wa/library", headers=auth("d")).status_code in (403, 404), "a member who left has no access"
    assert client.delete(f"{M}/user-g", headers=auth("a")).status_code == 404, "already gone"
    assert client.delete(f"{M}/user-c", headers=auth("c")).status_code == 204
    ev = client.get("/v1/workspaces/wa/members-history", headers=auth("a")).json()
    assert [(e["member_id"], e["event"], e["actor_id"]) for e in ev] == [("user-g", "removed", "user-e"), ("user-f", "removed", "user-a"), ("user-d", "left", "user-d"), ("user-c", "left", "user-c")]
    assert set(roles()) == {"user-a", "user-e"}


def test_the_history_cannot_be_changed(team):
    client.patch(f"{M}/user-d", headers=auth("a"), json={"role": "viewer"})
    with sqlite3.connect(config.ASSET_DATABASE_PATH) as c:
        for sql in ("UPDATE workspace_member_events SET actor_id='x'", "DELETE FROM workspace_member_events"):
            with pytest.raises(sqlite3.DatabaseError, match="append-only"):
                c.execute(sql)


def test_me_gives_the_id_and_the_workspaces_with_roles_and_nothing_personal(team):
    r = client.get("/v1/me", headers=auth("d"))
    assert r.status_code == 200 and r.json() == {"user_id": "user-d", "workspaces": [{"workspace_id": "wa", "role": "editor"}]}
    assert client.get("/v1/me", headers=auth("b")).json()["workspaces"] == [{"workspace_id": "wb", "role": "owner"}]
    assert client.get("/v1/me").status_code == 401
    assert client.get("/v1/auth/me", headers=auth("d")).json() == {"user_id": "user-d"}, "the old route is unchanged"


def test_adding_a_member_is_in_the_history_too_and_a_refused_add_is_not(team):
    ev = client.get("/v1/workspaces/wa/members-history", headers=auth("a")).json()
    assert [(e["event"], e["member_id"], e["to_role"], e["actor_id"]) for e in ev][:4] == [("added", "user-d", "editor", "user-a"), ("added", "user-e", "admin", "user-a"),
                                                                                         ("added", "user-f", "admin", "user-a"), ("added", "user-g", "editor", "user-a")]
    assert all(e["from_role"] is None for e in ev)
    n = len(ev)
    assert client.post(M, headers=auth("d"), json={"user_id": "user-x", "role": "viewer"}).status_code == 403, "an editor cannot add"
    assert client.post(M, headers=auth("a"), json={"user_id": "user-d", "role": "viewer"}).status_code in (409, 422), "already a member"
    assert len(client.get("/v1/workspaces/wa/members-history", headers=auth("a")).json()) == n, "nothing was added, so nothing is recorded"
