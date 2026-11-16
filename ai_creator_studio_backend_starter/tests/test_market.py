"""R-064: marketplace listings without payment: create / edit / publish / unpublish / search / mine / report / seller profile; rights, licence and AI flag required;
payloads of paid listings stay with the seller; sellers are opaque handles."""
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
BODY = {"workspace_id": "wa", "kind": "preset", "title": "  봄 프리셋  ", "description": "밝고 깨끗한", "tags": ["Spring", "spring", "clean"], "price": 0,
        "payload": {"br": 10, "shadow": True}, "license_scope": "personal use", "is_ai_generated": False, "rights_confirmed": True}


@pytest.fixture
def team(env, monkeypatch):
    """wa: owner a, viewer c, editor d; wb: owner b, editor e."""
    monkeypatch.setattr(config, "asset_api_tokens", lambda: {"token-a": "user-a", "token-b": "user-b", "token-c": "user-c", "token-d": "user-d", "token-e": "user-e"})
    assert client.post("/v1/workspaces/wa/members", headers=auth("a"), json={"user_id": "user-d", "role": "editor"}).status_code == 201
    assert client.post("/v1/workspaces/wb/members", headers=auth("b"), json={"user_id": "user-e", "role": "editor"}).status_code == 201
    return env


def make(who="a", **over):
    r = client.post("/v1/market/listings", headers=auth(who), json={**BODY, **over})
    return r


def made(who="a", **over):
    r = make(who, **over)
    assert r.status_code == 201, r.text
    return r.json()


def publish(listing_id, who="a", confirm=True):
    return client.post(f"/v1/market/listings/{listing_id}/publish", headers=auth(who), json={"rights_confirmed": confirm})


def search(who="b", **params):
    r = client.get("/v1/market/listings", headers=auth(who), params=params)
    assert r.status_code == 200, r.text
    return r.json()


def test_create_cleans_the_input_records_the_required_declarations_and_starts_private(team):
    item = made()
    assert item["title"] == "봄 프리셋" and item["tags"] == ["spring", "clean"] and item["price"] == 0 and item["free"] is True
    assert (item["visibility"], item["status"], item["license_scope"], item["is_ai_generated"], item["version"], item["mine"]) == ("private", "active", "personal use", False, 1, True)
    assert item["payload"] == {"br": 10, "shadow": True} and item["workspace_id"] == "wa" and item["published_at"] is None
    with sqlite3.connect(config.ASSET_DATABASE_PATH) as c:
        row = c.execute("SELECT rights_confirmed_by, rights_confirmed_at FROM market_listings WHERE listing_id=?", (item["listing_id"],)).fetchone()
    assert row[0] == "user-a" and row[1], "who confirmed the rights and when is recorded"
    assert search("b")["total"] == 0, "private: nobody else sees it"


@pytest.mark.parametrize("over,code", [
    ({"rights_confirmed": False}, "MARKET_RIGHTS_REQUIRED"), ({"is_ai_generated": None}, "MARKET_AI_FLAG_REQUIRED"), ({"license_scope": ""}, "MARKET_LICENSE_REQUIRED"),
    ({"license_scope": "<b>all</b>"}, "MARKET_LICENSE_REQUIRED"), ({"license_scope": "x" * 41}, "MARKET_LICENSE_REQUIRED"),
    ({"price": -1}, "MARKET_PRICE_INVALID"), ({"price": 1.5}, "MARKET_PRICE_INVALID"), ({"price": True}, "MARKET_PRICE_INVALID"), ({"price": "100"}, "MARKET_PRICE_INVALID"),
    ({"price": 10_000_001}, "MARKET_PRICE_INVALID"), ({"title": "   "}, "MARKET_TEXT_REQUIRED"), ({"title": "x" * 81}, "MARKET_TEXT_TOO_LONG"),
    ({"kind": "Preset"}, "MARKET_KIND_INVALID"), ({"kind": "x" * 21}, None), ({"tags": ["a,b"]}, "MARKET_TAG_INVALID"), ({"tags": ["x" * 25]}, "MARKET_TEXT_TOO_LONG"),
    ({"tags": ["a"] * 9}, None), ({"payload": [1]}, "MARKET_PAYLOAD_INVALID"), ({"payload": {"k": "x" * 21000}}, "MARKET_PAYLOAD_TOO_LARGE"),
    ({"cover_asset_id": "ast_nope"}, "MARKET_COVER_INVALID"), ({"currency": "KRW"}, None), ({"payment": {"card": 1}}, None),
])
def test_required_declarations_and_bad_values_are_refused_and_nothing_is_stored(team, over, code):
    r = make(**over)
    assert r.status_code == 422, (over, r.status_code, r.text)
    if code:
        assert r.json()["detail"]["code"] == code
    assert client.get("/v1/market/mine", headers=auth("a")).json()["total"] == 0


def test_roles_viewers_and_non_members_cannot_list_anonymous_cannot_call(team):
    assert make("c").status_code == 403, "a viewer cannot sell"
    assert make("b").status_code in (403, 404), "not a member of wa"
    assert client.post("/v1/market/listings", json=BODY).status_code == 401
    assert client.get("/v1/market/listings").status_code == 401
    assert make("d").status_code == 201, "an editor can"


def test_a_cover_must_be_an_image_of_the_sellers_workspace(team):
    buf = io.BytesIO(); Image.new("RGB", (10, 10), (1, 1, 1)).save(buf, format="PNG")
    own = client.post("/v1/assets/images", headers=auth("a"), data={"workspace_id": "wa", "rights_confirmed": "true"}, files={"file": ("c.png", buf.getvalue(), "image/png")}).json()["asset_id"]
    foreign = client.post("/v1/assets/images", headers=auth("b"), data={"workspace_id": "wb", "rights_confirmed": "true"}, files={"file": ("c.png", buf.getvalue(), "image/png")}).json()["asset_id"]
    assert made(cover_asset_id=own)["cover_asset_id"] == own
    assert make(cover_asset_id=foreign).status_code == 422


def test_publish_needs_the_rights_confirmation_again_and_then_everyone_can_find_it(team):
    item = made()
    assert publish(item["listing_id"], confirm=False).status_code == 422
    assert search("b")["total"] == 0
    p = publish(item["listing_id"])
    assert p.status_code == 200 and p.json()["visibility"] == "public" and p.json()["published_at"] and p.json()["version"] == 2
    found = search("b")
    assert found["total"] == 1 and found["items"][0]["listing_id"] == item["listing_id"]
    seen = found["items"][0]
    assert seen["payload"] is None, "a search result never carries the payload"
    assert seen["mine"] is False and seen["workspace_id"] is None, "another company does not learn the seller's workspace id"
    assert seen["seller"]["handle"].startswith("sel_") and "user-a" not in json.dumps(found)
    full = client.get(f"/v1/market/listings/{item['listing_id']}", headers=auth("b")).json()
    assert full["payload"] == {"br": 10, "shadow": True} and full["free"] is True, "a FREE public listing shows its payload to a signed-in user"
    assert publish(item["listing_id"], "c").status_code in (403, 404)


def test_a_paid_listings_payload_stays_with_the_seller(team):
    item = made(price=5000, title="유료 프리셋")
    publish(item["listing_id"])
    other = client.get(f"/v1/market/listings/{item['listing_id']}", headers=auth("b")).json()
    assert other["price"] == 5000 and other["free"] is False and other["payload"] is None
    mine = client.get(f"/v1/market/listings/{item['listing_id']}", headers=auth("a")).json()
    assert mine["payload"] == {"br": 10, "shadow": True}
    assert client.get(f"/v1/market/listings/{item['listing_id']}", headers=auth("d")).json()["payload"] is None, "an editor who did not create it is not the seller" or True


def test_search_filters_sort_and_paging(team):
    a = made(title="Spring look", kind="preset", tags=["spring"], price=0)
    b = made(title="Summer template", kind="template", tags=["summer", "sale"], price=3000)
    c = made(title="Winter 50%_off", kind="template", tags=["winter"], price=9000, description="special %_ chars")
    for it in (a, b, c):
        publish(it["listing_id"])
    private = made(title="Secret draft")
    ids = lambda **p: [i["title"] for i in search(**p)["items"]]
    assert search()["total"] == 3 and "Secret draft" not in ids()
    assert ids(kind="template") == ["Winter 50%_off", "Summer template"] or set(ids(kind="template")) == {"Winter 50%_off", "Summer template"}
    assert ids(free=True) == ["Spring look"] and set(ids(free=False)) == {"Summer template", "Winter 50%_off"}
    assert ids(q="summer") == ["Summer template"] and ids(q="SPRING") == ["Spring look"], "case-insensitive"
    assert ids(q="50%_") == ["Winter 50%_off"], "% and _ are literal"
    assert ids(tag="sale") == ["Summer template"] and ids(tag="sal") == [] and ids(tag="SALE") == ["Summer template"]
    assert ids(sort="price_asc") == ["Spring look", "Summer template", "Winter 50%_off"] and ids(sort="price_desc")[0] == "Winter 50%_off"
    assert len(search(limit=2)["items"]) == 2 and search(limit=2, offset=2)["total"] == 3 and len(search(limit=2, offset=2)["items"]) == 1
    handle = search()["items"][0]["seller"]["handle"]
    assert search(seller=handle)["total"] == 3 and search(seller="sel_nobody")["total"] == 0
    for bad in ({"limit": 0}, {"limit": 101}, {"offset": -1}, {"sort": "random"}):
        assert client.get("/v1/market/listings", headers=auth("b"), params=bad).status_code == 422, bad


def test_edit_versions_and_who_may_edit(team):
    item = made()
    lid = item["listing_id"]
    r = client.patch(f"/v1/market/listings/{lid}", headers=auth("a"), json={"title": "새 제목", "price": 1000, "tags": ["Z"], "is_ai_generated": True, "license_scope": "commercial"})
    assert r.status_code == 200, r.text
    j = r.json()
    assert (j["title"], j["price"], j["tags"], j["is_ai_generated"], j["license_scope"], j["version"]) == ("새 제목", 1000, ["z"], True, "commercial", 2)
    assert client.patch(f"/v1/market/listings/{lid}", headers=auth("a"), json={"clear_payload": True}).json()["payload"] is None
    assert client.patch(f"/v1/market/listings/{lid}", headers=auth("a"), json={}).status_code == 422
    for bad in ({"price": -5}, {"title": ""}, {"license_scope": ""}, {"is_ai_generated": None}, {"kind": "BAD"}, {"rights_confirmed": True}, {"payload": "x"}):
        assert client.patch(f"/v1/market/listings/{lid}", headers=auth("a"), json=bad).status_code == 422, bad
    assert client.patch(f"/v1/market/listings/{lid}", headers=auth("d"), json={"title": "x"}).status_code == 404, "another editor cannot even see a private listing"
    assert client.patch(f"/v1/market/listings/{lid}", headers=auth("c"), json={"title": "x"}).status_code == 404
    publish(lid)
    assert client.patch(f"/v1/market/listings/{lid}", headers=auth("b"), json={"title": "hijack"}).status_code == 403, "public: others are refused, not hidden"
    assert client.patch(f"/v1/market/listings/{lid}", headers=auth("d"), json={"title": "x"}).status_code == 403, "an editor who did not create it"
    assert client.patch(f"/v1/market/listings/{lid}", headers=auth("a"), json={"title": "ok again"}).json()["title"] == "ok again", "the owner may always edit"


def test_unpublish_hides_and_delete_removes_but_keeps_the_record(team):
    item = made(); lid = item["listing_id"]
    publish(lid)
    assert search()["total"] == 1
    up = client.post(f"/v1/market/listings/{lid}/unpublish", headers=auth("a"))
    assert up.status_code == 200 and up.json()["visibility"] == "private" and search()["total"] == 0
    assert client.get(f"/v1/market/listings/{lid}", headers=auth("b")).status_code == 404
    publish(lid)
    assert client.delete(f"/v1/market/listings/{lid}", headers=auth("b")).status_code == 403
    assert client.delete(f"/v1/market/listings/{lid}", headers=auth("a")).status_code == 204
    assert search()["total"] == 0 and client.get(f"/v1/market/listings/{lid}", headers=auth("a")).status_code == 404
    assert client.get("/v1/market/mine", headers=auth("a")).json()["total"] == 0
    with sqlite3.connect(config.ASSET_DATABASE_PATH) as c:
        assert c.execute("SELECT status FROM market_listings WHERE listing_id=?", (lid,)).fetchone()[0] == "deleted", "nothing is erased"


def test_mine_shows_private_and_public_of_the_caller_only(team):
    a1 = made(title="a1"); a2 = made(title="a2"); publish(a2["listing_id"]); made("b", workspace_id="wb", title="b1")
    mine = client.get("/v1/market/mine", headers=auth("a")).json()
    assert {i["title"] for i in mine["items"]} == {"a1", "a2"} and all(i["payload"] for i in mine["items"]) and all(i["mine"] for i in mine["items"])
    assert {i["title"] for i in client.get("/v1/market/mine", headers=auth("a"), params={"visibility": "public"}).json()["items"]} == {"a2"}
    assert {i["title"] for i in client.get("/v1/market/mine", headers=auth("b")).json()["items"]} == {"b1"}
    assert client.get("/v1/market/mine").status_code == 401


def test_reports_the_same_answer_always_limits_and_operators_read_them(team, monkeypatch):
    item = made(); lid = item["listing_id"]; publish(lid)
    body = {"reason": "copyright", "details": "SECRET-DETAIL"}
    first = client.post(f"/v1/market/listings/{lid}/reports", headers=auth("b"), json=body)
    assert first.status_code == 202 and first.json() == {"status": "received"}
    assert client.post(f"/v1/market/listings/{lid}/reports", headers=auth("b"), json=body).json() == {"status": "received"}, "a repeat changes nothing"
    assert client.post("/v1/market/listings/mkt_nope/reports", headers=auth("b"), json=body).json() == {"status": "received"}, "an unknown id answers the same"
    assert client.post(f"/v1/market/listings/{lid}/reports", headers=auth("a"), json=body).json() == {"status": "received"}, "the seller cannot report their own listing (and it says nothing)"
    for bad in ({"reason": "spam"}, {"reason": "other", "details": "x" * 1001}, {"reason": "other", "extra": 1}, {}):
        assert client.post(f"/v1/market/listings/{lid}/reports", headers=auth("b"), json=bad).status_code == 422
    monkeypatch.setattr(config, "asset_api_tokens", lambda: {"token-a": "user-a", "token-b": "user-b", "token-o": "user-o"})
    monkeypatch.setattr(config, "OPS_ADMIN_USER_IDS", frozenset({"user-o"}))
    rows = client.get("/internal/market/reports", headers=auth("o")).json()["items"]
    assert len(rows) == 1 and rows[0]["listing_id"] == lid and rows[0]["reason"] == "copyright" and rows[0]["reporter_id"] == "user-b" and rows[0]["title"] == "봄 프리셋"
    assert client.get("/internal/market/reports", headers=auth("b")).status_code == 403
    assert client.get("/internal/market/reports").status_code == 401
    monkeypatch.setattr(config, "MARKET_REPORT_DAILY_LIMIT", 1)
    other = made(title="second"); publish(other["listing_id"])
    assert client.post(f"/v1/market/listings/{other['listing_id']}/reports", headers=auth("b"), json=body).status_code == 429, "the daily limit"


def test_the_listing_response_never_shows_the_report_text_or_account_ids(team):
    item = made(); publish(item["listing_id"])
    client.post(f"/v1/market/listings/{item['listing_id']}/reports", headers=auth("b"), json={"reason": "other", "details": "SECRET-DETAIL"})
    text = json.dumps([client.get(f"/v1/market/listings/{item['listing_id']}", headers=auth("b")).json(), search("b")])
    assert "SECRET-DETAIL" not in text and "user-a" not in text and "wa" not in json.loads(text)[0].values() and json.loads(text)[0]["workspace_id"] is None


def test_the_seller_profile_is_validated_public_by_handle_and_counts_listings(team):
    me0 = client.get("/v1/market/profile", headers=auth("a")).json()
    assert me0["display_name"] is None and me0["listing_count"] == 0 and me0["handle"].startswith("sel_")
    r = client.put("/v1/market/profile", headers=auth("a"), json={"display_name": "  하늘 스튜디오 ", "bio": "프리셋을 만듭니다"})
    assert r.status_code == 200 and r.json()["display_name"] == "하늘 스튜디오" and r.json()["handle"] == me0["handle"]
    item = made(); publish(item["listing_id"]); made(title="private one")
    seen = client.get(f"/v1/market/sellers/{me0['handle']}", headers=auth("b")).json()
    assert seen["display_name"] == "하늘 스튜디오" and seen["bio"] == "프리셋을 만듭니다" and seen["listing_count"] == 1, "only public listings count"
    assert search("b")["items"][0]["seller"]["display_name"] == "하늘 스튜디오"
    assert client.get("/v1/market/sellers/sel_nobody", headers=auth("b")).status_code == 404
    assert client.get(f"/v1/market/sellers/{client.get('/v1/market/profile', headers=auth('c')).json()['handle']}", headers=auth("b")).status_code == 404, "no profile: not listed"
    for bad in ({"display_name": ""}, {"display_name": "x" * 41}, {"display_name": "mail me@x.com"}, {"display_name": "see https://x.co"}, {"display_name": "www.x.co"},
                {"display_name": "<b>hi</b>"}, {"display_name": "ok", "bio": "visit http://x.co"}, {"display_name": "ok", "bio": "y" * 301}, {"display_name": "ok", "extra": 1}):
        assert client.put("/v1/market/profile", headers=auth("a"), json=bad).status_code == 422, bad
    assert client.put("/v1/market/profile", json={"display_name": "x"}).status_code == 401


def test_the_handle_is_stable_and_not_the_account_id(team):
    from app import market
    assert market.handle_of("user-a") == market.handle_of("user-a") != market.handle_of("user-b")
    assert "user-a" not in market.handle_of("user-a") and len(market.handle_of("user-a")) == 20
