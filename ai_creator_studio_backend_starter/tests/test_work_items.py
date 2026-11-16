"""R-069: work items: a general store for the homepage's "my work" entries: shapes, roles, filters, asset links with their review status, archive instead of delete, immutable history."""
import io
import json
import sqlite3

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import config
from app.main import app
from tests.test_photo_steps_api import auth, env  # noqa: F401  (wa: owner a + viewer c, wb: owner b)

client = TestClient(app)
BASE = "/v1/workspaces/wa/work-items"


@pytest.fixture
def team(env, monkeypatch):
    """wa: owner a, viewer c, editor d, admin e; wb: owner b."""
    monkeypatch.setattr(config, "asset_api_tokens", lambda: {"token-a": "user-a", "token-b": "user-b", "token-c": "user-c", "token-d": "user-d", "token-e": "user-e"})
    assert client.post("/v1/workspaces/wa/members", headers=auth("a"), json={"user_id": "user-d", "role": "editor"}).status_code == 201
    assert client.post("/v1/workspaces/wa/members", headers=auth("a"), json={"user_id": "user-e", "role": "admin"}).status_code == 201
    return env


def make(who="d", ws="wa", **over):
    body = {"kind": "tryon", "title": "  봄 룩 시착  ", **over}
    return client.post(f"/v1/workspaces/{ws}/work-items", headers=auth(who), json=body)


def made(**over):
    r = make(**over)
    assert r.status_code == 201, r.text
    return r.json()


def asset(who="a", ws="wa", shade=1):
    buf = io.BytesIO(); Image.new("RGB", (12, 12), (shade, shade, shade)).save(buf, format="PNG")
    r = client.post("/v1/assets/images", headers=auth(who), data={"workspace_id": ws, "rights_confirmed": "true"}, files={"file": ("a.png", buf.getvalue(), "image/png")})
    assert r.status_code == 201, r.text
    return r.json()["asset_id"]


def patch(item_id, who="d", **body):
    return client.patch(f"{BASE}/{item_id}", headers=auth(who), json=body)


def events(item_id, who="c"):
    return client.get(f"{BASE}/{item_id}/events", headers=auth(who)).json()


def test_create_defaults_trim_and_record_the_creator(team):
    item = made()
    assert (item["kind"], item["title"], item["status"], item["attrs"], item["asset_ids"], item["assets"], item["asset_review_summary"]) == ("tryon", "봄 룩 시착", "draft", {}, [], [], None)
    assert item["item_id"].startswith("wk_") and item["created_by"] == "user-d" and item["version"] == 1 and item["archived_at"] is None
    assert [(e["event"], e["actor_id"], e["to_status"]) for e in events(item["item_id"])] == [("created", "user-d", "draft")]


@pytest.mark.parametrize("status", ["draft", "req", "ok", "chg", "rej", "done", "in-review", "later_2", "a" + "b" * 15])
def test_any_status_word_of_the_right_shape_is_accepted_the_server_has_no_state_machine(team, status):
    assert made(status=status)["status"] == status


@pytest.mark.parametrize("over", [
    {"status": "Draft"}, {"status": "1st"}, {"status": "a" + "b" * 16}, {"status": ""}, {"status": "two words"}, {"status": "한글"},
    {"kind": "Tryon"}, {"kind": "x" * 21}, {"kind": ""}, {"kind": "a b"}, {"title": "   "}, {"title": "x" * 121}, {"title": ""},
    {"attrs": {"Bad": 1}}, {"attrs": {"k": "x" * 61}}, {"attrs": {"k": 10000}}, {"attrs": [1]}, {"attrs": {f"k{i}": "v" for i in range(21)}},
    {"asset_ids": ["ast_nope"]}, {"asset_ids": [1]}, {"asset_ids": ["a"] * 101}, {"unknown": 1}, {"data": "data:image/png;base64,AAAA"},
])
def test_bad_values_are_refused_and_nothing_is_stored(team, over):
    r = make(**over)
    assert r.status_code == 422, (over, r.status_code, r.text)
    assert client.get(BASE, headers=auth("a")).json()["total"] == 0


def test_the_homepages_heavy_data_field_is_not_accepted_assets_carry_pictures(team):
    r = make(data={"img": "data:image/png;base64," + "A" * 100})
    assert r.status_code == 422, "free `data` is refused: pictures are assets, the item links to them"


def test_roles_and_isolation(team):
    assert make("c").status_code == 403, "a viewer cannot create"
    assert make("b").status_code in (403, 404) and client.post(BASE, json={"kind": "x", "title": "t"}).status_code == 401
    item = made()
    assert client.get(f"{BASE}/{item['item_id']}", headers=auth("c")).status_code == 200, "a viewer reads"
    assert client.get(BASE, headers=auth("c")).json()["total"] == 1
    for who in "c":
        assert patch(item["item_id"], who, title="x").status_code == 403
        assert client.delete(f"{BASE}/{item['item_id']}", headers=auth(who)).status_code == 403
        assert client.post(f"{BASE}/{item['item_id']}/restore", headers=auth(who)).status_code == 403
    assert client.get(f"{BASE}/{item['item_id']}", headers=auth("b")).status_code in (403, 404)
    assert client.get(f"/v1/workspaces/wb/work-items/{item['item_id']}", headers=auth("b")).status_code == 404, "another workspace does not see it even by id"
    assert patch(item["item_id"], "e", title="admin edit").status_code == 200, "an admin may; any editor may edit any item (library semantics)"
    other = made("a", title="owner's")
    assert patch(other["item_id"], "d", title="editor edit").status_code == 200


def test_attrs_follow_the_library_rule_and_are_replaced_as_a_whole(team):
    item = made(attrs={"sku": "A-1", "size_no": 95, "colors": ["white", "beige"]})
    assert item["attrs"] == {"sku": "A-1", "size_no": 95, "colors": ["white", "beige"]}
    assert patch(item["item_id"], attrs={"sku": "B"}).json()["attrs"] == {"sku": "B"}
    assert patch(item["item_id"], attrs={}).json()["attrs"] == {}
    assert patch(item["item_id"], attrs=None).status_code == 422


def test_assets_must_be_live_and_of_this_workspace_and_duplicates_collapse(team):
    a1, a2 = asset(shade=1), asset(shade=2)
    foreign = asset("b", "wb", 3)
    item = made(asset_ids=[a1, a2, a1])
    assert item["asset_ids"] == [a1, a2] and [s["asset_id"] for s in item["assets"]] == [a1, a2]
    assert make(asset_ids=[foreign]).status_code == 422, "an asset of another workspace"
    assert patch(item["item_id"], asset_ids=[a2]).json()["asset_ids"] == [a2]
    assert patch(item["item_id"], asset_ids=[]).json()["asset_ids"] == []
    assert patch(item["item_id"], asset_ids=[foreign]).status_code == 422
    assert patch(item["item_id"], asset_ids=None).status_code == 422
    assert make(asset_ids=[asset(shade=i + 10) for i in range(20)]).status_code == 201
    assert make(asset_ids=[asset(shade=i + 40) for i in range(21)]).status_code == 422, "at most 20"


def test_the_response_shows_each_assets_review_status_and_one_summary_with_the_screen_words(team):
    a1, a2, a3, a4 = (asset(shade=i) for i in (1, 2, 3, 4))
    item = made(asset_ids=[a1, a2, a3, a4], status="req")
    states = lambda: {s["asset_id"]: (s["review_status"], s["screen_status"], s["exportable"]) for s in client.get(f"{BASE}/{item['item_id']}", headers=auth("c")).json()["assets"]}
    summary = lambda: client.get(f"{BASE}/{item['item_id']}", headers=auth("c")).json()["asset_review_summary"]
    assert set(states().values()) == {("none", "draft", False)} and summary() == "draft"
    ask = lambda aid, who="d": client.post("/v1/workspaces/wa/reviews", headers=auth("a" if who == "a" else who), json={"asset_id": aid}).json()["review_id"]
    act = lambda rid, action, comment=None: client.post(f"/v1/workspaces/wa/reviews/{rid}/{action}", headers=auth("e"), json={"comment": comment} if comment else {})
    r1 = ask(a1); assert summary() == "req"
    act(r1, "approve")
    assert states()[a1] == ("approved", "ok", True) and summary() == "draft", "one approved and the rest unreviewed is not yet 'ok'"
    r2 = ask(a2); act(r2, "request-changes", "fix")
    assert states()[a2] == ("changes_requested", "chg", False)
    r3 = ask(a3); act(r3, "reject", "no")
    assert states()[a3] == ("rejected", "rej", False) and summary() == "rej", "any rejected wins"
    r3b = ask(a3); client.post(f"/v1/workspaces/wa/reviews/{r3b}/withdraw", headers=auth("e"), json={})
    assert states()[a3] == ("withdrawn", "draft", False)
    assert summary() == "chg", "then changes requested"
    only_ok = made(asset_ids=[a1])
    assert client.get(f"{BASE}/{only_ok['item_id']}", headers=auth("c")).json()["asset_review_summary"] == "ok", "all approved -> ok"
    assert item["status"] == "req" and client.get(f"{BASE}/{item['item_id']}", headers=auth("c")).json()["status"] == "req", "the item's own status is a separate label, untouched by reviews"


def test_a_deleted_asset_is_shown_as_gone_and_ignored_by_the_summary(team):
    a1 = asset(shade=1); a2 = asset(shade=2)
    item = made(asset_ids=[a1, a2])
    rv = client.post("/v1/workspaces/wa/reviews", headers=auth("d"), json={"asset_id": a1}).json()["review_id"]
    client.post(f"/v1/workspaces/wa/reviews/{rv}/approve", headers=auth("e"), json={})
    with sqlite3.connect(config.ASSET_DATABASE_PATH) as c:
        c.execute("UPDATE assets SET deleted_at='2026-01-01T00:00:00+00:00' WHERE asset_id=?", (a2,))
    got = client.get(f"{BASE}/{item['item_id']}", headers=auth("c")).json()
    assert {s["asset_id"]: s["state"] for s in got["assets"]} == {a1: "live", a2: "gone"} and got["asset_ids"] == [a1, a2]
    assert got["asset_review_summary"] == "ok"


def test_patch_is_partial_counts_versions_and_detects_a_concurrent_change(team):
    item = made()
    iid = item["item_id"]
    r = patch(iid, title="새 제목", kind="character")
    assert (r.json()["title"], r.json()["kind"], r.json()["status"], r.json()["version"]) == ("새 제목", "character", "draft", 2)
    same = patch(iid, title="새 제목")
    assert same.status_code == 200 and same.json()["version"] == 2 and len(events(iid)) == 2, "a call that changes nothing adds no version and no history"
    assert patch(iid, expected_version=1, title="stale").status_code == 409
    d = patch(iid, expected_version=1, title="stale").json()["detail"]
    assert d["code"] == "WORK_ITEM_CHANGED" and d["version"] == 2
    assert patch(iid, expected_version=2, title="fresh").json()["version"] == 3
    assert patch(iid).status_code == 422 and patch(iid, expected_version=3).status_code == 422
    for bad in ({"title": ""}, {"kind": "BAD"}, {"status": "BAD"}, {"nonsense": 1}):
        assert patch(iid, **bad).status_code == 422, bad


def test_every_change_is_in_the_history_with_who_and_the_status_move(team):
    item = made(status="draft")
    iid = item["item_id"]
    patch(iid, "d", status="req")
    patch(iid, "e", title="edited", attrs={"k": 1})
    patch(iid, "e", status="ok", title="edited again")
    client.delete(f"{BASE}/{iid}", headers=auth("e"))
    client.post(f"{BASE}/{iid}/restore", headers=auth("a"))
    rows = [(e["event"], e["actor_id"], e["from_status"], e["to_status"], e["changed"]) for e in events(iid)]
    assert rows == [("created", "user-d", None, "draft", []), ("status", "user-d", "draft", "req", []), ("updated", "user-e", "req", "req", ["title", "attrs"]),
                    ("status", "user-e", "req", "ok", ["title"]), ("archived", "user-e", "ok", "ok", []), ("restored", "user-a", "ok", "ok", [])]
    with sqlite3.connect(config.ASSET_DATABASE_PATH) as c:
        for sql in ("UPDATE work_item_events SET actor_id='x'", "DELETE FROM work_item_events"):
            with pytest.raises(sqlite3.DatabaseError, match="append-only"):
                c.execute(sql)


def test_archive_hides_nothing_is_deleted_and_restore_brings_it_back(team):
    item = made(); iid = item["item_id"]
    assert client.delete(f"{BASE}/{iid}", headers=auth("d")).status_code == 204
    assert client.delete(f"{BASE}/{iid}", headers=auth("d")).status_code == 204, "archiving twice is harmless"
    assert client.get(BASE, headers=auth("c")).json()["total"] == 0
    assert client.get(BASE, headers=auth("c"), params={"archived": "true"}).json()["items"][0]["item_id"] == iid
    got = client.get(f"{BASE}/{iid}", headers=auth("c")).json()
    assert got["archived_at"] and got["title"] == item["title"], "still readable by id"
    r = patch(iid, title="x")
    assert r.status_code == 409 and r.json()["detail"]["code"] == "WORK_ITEM_ARCHIVED"
    back = client.post(f"{BASE}/{iid}/restore", headers=auth("d"))
    assert back.status_code == 200 and back.json()["archived_at"] is None and client.get(BASE, headers=auth("c")).json()["total"] == 1
    with sqlite3.connect(config.ASSET_DATABASE_PATH) as c:
        assert c.execute("SELECT COUNT(*) FROM work_items").fetchone()[0] == 1
    assert client.delete(f"{BASE}/wk_nope", headers=auth("d")).status_code == 404 and client.post(f"{BASE}/wk_nope/restore", headers=auth("d")).status_code == 404


def test_list_filters_order_and_paging(team):
    a1 = asset(shade=1)
    i1 = made(kind="tryon", title="Spring look", status="req", asset_ids=[a1])
    i2 = made(kind="character", title="Winter 50%_off", status="ok")
    i3 = made(kind="tryon", title="Summer", status="draft")
    patch(i1["item_id"], title="Spring look v2")             # newest change first
    titles = lambda **p: [i["title"] for i in client.get(BASE, headers=auth("c"), params=p).json()["items"]]
    assert titles() == ["Spring look v2", "Summer", "Winter 50%_off"]
    assert set(titles(kind="tryon")) == {"Spring look v2", "Summer"} and titles(status="ok") == ["Winter 50%_off"]
    assert titles(q="spring") == ["Spring look v2"] and titles(q="50%_") == ["Winter 50%_off"], "% and _ are literal"
    assert titles(asset_id=a1) == ["Spring look v2"] and titles(asset_id="ast_none") == []
    assert titles(kind="tryon", status="draft") == ["Summer"]
    page = client.get(BASE, headers=auth("c"), params={"limit": 2, "offset": 2}).json()
    assert page["total"] == 3 and len(page["items"]) == 1
    for bad in ({"limit": 0}, {"limit": 201}, {"offset": -1}):
        assert client.get(BASE, headers=auth("c"), params=bad).status_code == 422


def test_the_workspace_cap_counts_archived_items_too(team, monkeypatch):
    monkeypatch.setattr(config, "WORK_ITEMS_MAX", 2)
    a = made(); made()
    full = make()
    assert full.status_code == 409 and full.json()["detail"]["code"] == "WORK_ITEMS_FULL"
    client.delete(f"{BASE}/{a['item_id']}", headers=auth("d"))
    assert make().status_code == 409, "archived items still count"
    assert make("b", "wb").status_code in (201, 403, 404), "another workspace has its own count"


def test_the_screen_status_table_is_complete():
    from app import work_items
    assert work_items.REVIEW_TO_SCREEN == {"none": "draft", "requested": "req", "approved": "ok", "changes_requested": "chg", "rejected": "rej", "withdrawn": "draft"}
