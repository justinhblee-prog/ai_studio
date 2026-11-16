"""R-063: review / approval records: the full transition table, roles, required comments, immutable history, status / export check."""
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import app
from tests.test_photo_steps_api import auth, env  # noqa: F401  (wa: owner a + viewer c, wb: owner b)

client = TestClient(app)
WS = "wa"


@pytest.fixture
def team(env, monkeypatch):
    """wa: owner a, viewer c, editor d, admin e; wb: owner b."""
    monkeypatch.setattr(config, "asset_api_tokens", lambda: {"token-a": "user-a", "token-b": "user-b", "token-c": "user-c", "token-d": "user-d", "token-e": "user-e"})
    assert client.post("/v1/workspaces/wa/members", headers=auth("a"), json={"user_id": "user-d", "role": "editor"}).status_code == 201
    assert client.post("/v1/workspaces/wa/members", headers=auth("a"), json={"user_id": "user-e", "role": "admin"}).status_code == 201
    return env


def asset(who="a", color=(1, 1, 1)):
    import io
    from PIL import Image
    buf = io.BytesIO(); Image.new("RGB", (16, 16), color).save(buf, format="PNG")
    r = client.post("/v1/assets/images", headers=auth(who), data={"workspace_id": WS, "rights_confirmed": "true"}, files={"file": ("a.png", buf.getvalue(), "image/png")})
    assert r.status_code == 201, r.text
    return r.json()["asset_id"]


def ask(asset_id, who="d", comment=None, ws=WS):
    body = {"asset_id": asset_id, **({"comment": comment} if comment else {})}
    return client.post(f"/v1/workspaces/{ws}/reviews", headers=auth(who), json=body)


def act(review_id, action, who="e", comment=None, ws=WS):
    return client.post(f"/v1/workspaces/{ws}/reviews/{review_id}/{action}", headers=auth(who), json={"comment": comment} if comment is not None else {})


def get(review_id, who="c"):
    return client.get(f"/v1/workspaces/{WS}/reviews/{review_id}", headers=auth(who))


def test_request_then_approve_records_who_when_and_the_history(team):
    r = ask(team["asset"], "d", "봄 룩북 최종본입니다")
    assert r.status_code == 201, r.text
    rv = r.json()
    assert (rv["status"], rv["requested_by"], rv["handled_by"], rv["comment"], rv["version"], rv["asset_id"]) == ("requested", "user-d", None, "봄 룩북 최종본입니다", 1, team["asset"])
    ok = act(rv["review_id"], "approve", "e", "좋습니다")
    assert ok.status_code == 200, ok.text
    done = ok.json()
    assert (done["status"], done["handled_by"], done["comment"], done["version"]) == ("approved", "user-e", "좋습니다", 2) and done["handled_at"]
    events = client.get(f"/v1/workspaces/{WS}/reviews/{rv['review_id']}/events", headers=auth("c")).json()
    assert [(e["action"], e["from_status"], e["to_status"], e["actor_id"], e["actor_role"]) for e in events] == [
        ("request", None, "requested", "user-d", "editor"), ("approve", "requested", "approved", "user-e", "admin")]
    assert events[0]["comment"] == "봄 룩북 최종본입니다" and events[1]["comment"] == "좋습니다"


# the whole transition table: (state reached by these actions) x (action) -> allowed or not
PATHS = {"requested": [], "changes_requested": [("request-changes", "e", "x")], "approved": [("approve", "e", None)],
         "rejected": [("reject", "e", "x")], "withdrawn": [("withdraw", "d", None)]}
ACTIONS = ["approve", "request-changes", "reject", "resubmit", "withdraw"]
VALID = {("requested", "approve"), ("requested", "request-changes"), ("requested", "reject"), ("requested", "withdraw"), ("changes_requested", "resubmit"), ("changes_requested", "withdraw")}


@pytest.mark.parametrize("state", list(PATHS))
@pytest.mark.parametrize("action", ACTIONS)
def test_the_whole_transition_table(team, state, action):
    rv = ask(team["asset"], "d").json()
    for step, who, comment in PATHS[state]:
        assert act(rv["review_id"], step, who, comment).status_code == 200
    assert get(rv["review_id"]).json()["status"] == state
    before = client.get(f"/v1/workspaces/{WS}/reviews/{rv['review_id']}/events", headers=auth("c")).json()
    who = "d" if action in ("resubmit", "withdraw") else "e"
    r = act(rv["review_id"], action, who, "reason")
    if (state, action) in VALID:
        assert r.status_code == 200, (state, action, r.text)
        assert r.json()["status"] == {"approve": "approved", "request-changes": "changes_requested", "reject": "rejected", "resubmit": "requested", "withdraw": "withdrawn"}[action]
    else:
        assert r.status_code == 409 and r.json()["detail"]["code"] == "REVIEW_TRANSITION_INVALID", (state, action, r.text)
        assert get(rv["review_id"]).json()["status"] == state, "a refused move changes nothing"
        assert client.get(f"/v1/workspaces/{WS}/reviews/{rv['review_id']}/events", headers=auth("c")).json() == before, "and writes no history"


def test_a_comment_is_required_for_changes_and_rejection_only(team):
    for action in ("request-changes", "reject"):
        rv = ask(team["asset"], "d").json()
        for empty in (None, "", "   ", "\x00\x01"):
            r = act(rv["review_id"], action, "e", empty)
            assert r.status_code == 422 and r.json()["detail"]["code"] == "REVIEW_COMMENT_REQUIRED", (action, repr(empty))
        assert get(rv["review_id"]).json()["status"] == "requested"
        assert act(rv["review_id"], action, "e", "  이유  ").json()["comment"] == "이유"
        client.post(f"/v1/workspaces/{WS}/reviews/{rv['review_id']}/withdraw", headers=auth("e"), json={})
    rv = ask(team["asset"], "d").json()
    assert act(rv["review_id"], "approve", "e").status_code == 200, "approval needs no comment"
    assert act(rv["review_id"], "approve", "e", "x" * 1001).status_code == 422, "at most 1000 characters"


def test_roles_viewers_cannot_write_editors_cannot_decide(team):
    assert ask(team["asset"], "c").status_code == 403, "a viewer cannot request"
    rv = ask(team["asset"], "d").json()
    for action in ("approve", "request-changes", "reject"):
        assert act(rv["review_id"], action, "d", "x").status_code == 403, f"an editor cannot {action}"
        assert act(rv["review_id"], action, "c", "x").status_code == 403, f"a viewer cannot {action}"
    assert act(rv["review_id"], "withdraw", "c").status_code == 403
    other_editor_ok = act(rv["review_id"], "approve", "a", "owner may approve")
    assert other_editor_ok.status_code == 200 and other_editor_ok.json()["handled_by"] == "user-a"


def test_only_the_requester_or_an_admin_can_withdraw_and_only_writers_resubmit(team):
    first = ask(team["asset"], "d").json()
    assert act(first["review_id"], "request-changes", "e", "fix").status_code == 200
    assert act(first["review_id"], "resubmit", "c").status_code == 403, "a viewer cannot resubmit"
    back = act(first["review_id"], "resubmit", "d", "고쳤습니다")
    assert back.status_code == 200 and back.json()["status"] == "requested" and back.json()["handled_by"] is None and back.json()["comment"] == "고쳤습니다"
    assert act(first["review_id"], "withdraw", "e").status_code == 200, "an admin may withdraw someone else's request"
    second = ask(team["asset"], "a").json()      # the owner asks; editor d did not ask it
    assert act(second["review_id"], "withdraw", "d").status_code == 403, "an editor withdraws only their own request"
    assert act(second["review_id"], "withdraw", "a").status_code == 200


def test_one_open_review_per_asset_and_a_new_one_after_it_closes(team):
    rv = ask(team["asset"], "d").json()
    dup = ask(team["asset"], "a")
    assert dup.status_code == 409 and dup.json()["detail"]["code"] == "REVIEW_ALREADY_OPEN"
    assert act(rv["review_id"], "request-changes", "e", "x").status_code == 200
    assert ask(team["asset"], "d").status_code == 409, "changes requested is still open"
    assert act(rv["review_id"], "withdraw", "d").status_code == 200
    assert ask(team["asset"], "d").status_code == 201, "closed: a new review may start"


def test_unknown_assets_other_workspaces_and_anonymous_calls(team):
    assert ask("ast_nope", "d").status_code == 404
    import io
    from PIL import Image
    buf = io.BytesIO(); Image.new("RGB", (8, 8), (9, 9, 9)).save(buf, format="PNG")
    foreign = client.post("/v1/assets/images", headers=auth("b"), data={"workspace_id": "wb", "rights_confirmed": "true"}, files={"file": ("f.png", buf.getvalue(), "image/png")}).json()["asset_id"]
    assert ask(foreign, "d").status_code == 404, "an asset of another workspace cannot be put under review here"
    rv = ask(team["asset"], "d").json()
    assert act(rv["review_id"], "approve", "b", ws="wb").status_code == 404, "the review does not exist in another workspace"
    assert client.get(f"/v1/workspaces/{WS}/reviews/{rv['review_id']}", headers=auth("b")).status_code in (403, 404)
    assert client.get(f"/v1/workspaces/{WS}/reviews").status_code == 401
    assert client.post(f"/v1/workspaces/{WS}/reviews", json={"asset_id": team["asset"]}).status_code == 401
    assert act("rev_nope", "approve", "e").status_code == 404


def test_list_filters_and_the_status_and_export_check(team):
    a2 = asset(color=(2, 2, 2)); a3 = asset(color=(3, 3, 3)); a4 = asset(color=(4, 4, 4))
    r1 = ask(team["asset"], "d").json(); r2 = ask(a2, "d").json(); r3 = ask(a3, "a").json()
    act(r1["review_id"], "approve", "e"); act(r2["review_id"], "reject", "e", "no")
    lst = lambda **p: client.get(f"/v1/workspaces/{WS}/reviews", headers=auth("c"), params=p).json()   # a viewer reads
    assert lst()["total"] == 3
    assert {i["review_id"] for i in lst(status="approved")["items"]} == {r1["review_id"]}
    assert {i["review_id"] for i in lst(status="requested")["items"]} == {r3["review_id"]}
    assert {i["review_id"] for i in lst(asset_id=a2)["items"]} == {r2["review_id"]}
    mine = client.get(f"/v1/workspaces/{WS}/reviews", headers=auth("d"), params={"mine": "true"}).json()
    assert {i["review_id"] for i in mine["items"]} == {r1["review_id"], r2["review_id"]}
    assert len(lst(limit=1)["items"]) == 1 and lst(limit=1, offset=1)["total"] == 3
    st = client.get(f"/v1/workspaces/{WS}/reviews/status", headers=auth("c"), params=[("asset_ids", team["asset"]), ("asset_ids", a2), ("asset_ids", a3), ("asset_ids", a4), ("asset_ids", a4)]).json()["items"]
    assert [(i["status"], i["exportable"]) for i in st] == [("approved", True), ("rejected", False), ("requested", False), ("none", False)], "only an approved latest review exports"
    # a rejected asset reviewed again: the LATEST review decides
    r2b = ask(a2, "d").json(); act(r2b["review_id"], "approve", "e")
    again = client.get(f"/v1/workspaces/{WS}/reviews/status", headers=auth("c"), params=[("asset_ids", a2)]).json()["items"][0]
    assert (again["status"], again["exportable"], again["review_id"]) == ("approved", True, r2b["review_id"])
    assert client.get(f"/v1/workspaces/{WS}/reviews", headers=auth("c"), params={"status": "nonsense"}).status_code == 422


def test_the_history_cannot_be_changed_or_deleted(team):
    rv = ask(team["asset"], "d").json()
    with sqlite3.connect(config.ASSET_DATABASE_PATH) as c:
        for sql in ("UPDATE asset_review_events SET comment='x'", "DELETE FROM asset_review_events"):
            with pytest.raises(sqlite3.DatabaseError, match="append-only"):
                c.execute(sql)
    assert len(client.get(f"/v1/workspaces/{WS}/reviews/{rv['review_id']}/events", headers=auth("c")).json()) == 1


def test_a_stale_decision_is_refused_not_silently_overwritten(team):
    rv = ask(team["asset"], "d").json()
    assert act(rv["review_id"], "approve", "e").status_code == 200
    late = act(rv["review_id"], "reject", "a", "too late")
    assert late.status_code == 409 and get(rv["review_id"]).json()["status"] == "approved"
