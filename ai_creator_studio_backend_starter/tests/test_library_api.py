"""R-032: the platform-owned default asset library. Read-only API, copy-on-use, no way to change an item through the API."""
import hashlib
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import library
from app.main import app
from scripts import purge_requests as purge

client = TestClient(app)


def auth(t):
    return {"Authorization": f"Bearer token-{t}"}


def png(color=(10, 20, 30), size=(24, 32)):
    buf = BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


MODEL_ATTRS = {"skin_tone": "3", "hair": "wavy", "body_type": "regular", "age_range": "30s", "region_style": "europe"}


def fields(item_id="top-01", category="top", **over):
    base = {"item_id": item_id, "category": category, "name_ko": "베이지 셔츠", "tags": ["셔츠", "베이지"], "source": "ai_generated",
            "tool_and_date": "ChatGPT 이미지 생성, 2026-11-20", "rights_confirmed": True, "status": "published"}
    if category == "model":
        base["attributes"] = dict(MODEL_ATTRS)
    base.update(over)
    return base


@pytest.fixture
def env(tmp_path, monkeypatch):
    import app.config as config
    monkeypatch.setattr(config, "ASSET_STORAGE_DIR", tmp_path / "private")
    monkeypatch.setattr(config, "LIBRARY_STORAGE_DIR", tmp_path / "library")
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path / "outputs")
    monkeypatch.setattr(config, "ASSET_DATABASE_PATH", tmp_path / "a.sqlite3")
    monkeypatch.setattr(config, "GENERATION_DATABASE_PATH", None)
    monkeypatch.setattr(config, "ASSET_SIGNING_SECRET", "s" * 48)
    monkeypatch.setattr(config, "asset_api_tokens", lambda: {"token-a": "user-a", "token-b": "user-b", "token-c": "user-c"})
    monkeypatch.setattr(config, "PROVIDER_MODE", "mock")
    for ws, u in (("wa", "a"), ("wb", "b")):
        assert client.post("/v1/workspaces", headers=auth(u), json={"workspace_id": ws}).status_code == 201
    assert client.post("/v1/workspaces/wa/members", headers=auth("a"), json={"user_id": "user-c", "role": "viewer"}).status_code == 201
    (tmp_path / "outputs").mkdir(exist_ok=True)
    return tmp_path


def db_of(tmp_path):
    db = sqlite3.connect(tmp_path / "a.sqlite3", isolation_level=None)
    db.row_factory = sqlite3.Row
    return db


def add(tmp, item_id="top-01", category="top", content=None, **over):
    return library.upsert_item(fields(item_id, category, **over), content or png(), f"{item_id}.png")


def library_state(tmp):
    db = db_of(tmp)
    rows = [dict(r) for r in db.execute("SELECT * FROM library_items ORDER BY item_id")]
    versions = [dict(r) for r in db.execute("SELECT * FROM library_item_versions ORDER BY item_id, version")]
    blobs = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((tmp / "library").glob("*"))}
    return rows, versions, blobs


# ------------------------------------------------------------------------------------------------ reading
def test_every_signed_in_user_reads_published_items_even_without_a_workspace_in_common(env):
    add(env)
    assert client.get("/v1/library/items").status_code == 401
    for user in ("a", "b", "c"):  # c is only a viewer of wa, b is not in wa at all
        listing = client.get("/v1/library/items", headers=auth(user)).json()
        assert [i["item_id"] for i in listing["items"]] == ["top-01"]
        item = listing["items"][0]
        assert item["is_ai_generated"] is True and item["category"] == "top" and item["width"] == 24 and item["height"] == 32
        assert client.get("/v1/library/items/top-01", headers=auth(user)).status_code == 200


def test_readers_never_see_storage_or_rights_internals(env):
    add(env)
    text = client.get("/v1/library/items/top-01", headers=auth("b")).text
    for secret in ("storage_key", "checksum", "tool_and_date", "ChatGPT", "rights_confirmed", ".v1.png"):
        assert secret not in text, secret


def test_draft_and_retired_items_do_not_exist_for_readers(env):
    add(env, "top-draft", status="draft")
    add(env, "top-live")
    add(env, "top-old")
    library.set_status("top-old", "retired")
    ids = [i["item_id"] for i in client.get("/v1/library/items", headers=auth("b")).json()["items"]]
    assert ids == ["top-live"]
    for hidden in ("top-draft", "top-old"):
        assert client.get(f"/v1/library/items/{hidden}", headers=auth("b")).status_code == 404
        assert client.get(f"/v1/library/items/{hidden}/preview-url", headers=auth("b")).status_code == 404
        assert client.post(f"/v1/library/items/{hidden}/import", headers=auth("a"), json={"workspace_id": "wa"}).status_code == 404


def test_the_api_has_no_way_to_change_or_remove_an_item(env):
    add(env)
    before = library_state(env)
    for method, path in (("post", "/v1/library/items"), ("put", "/v1/library/items/top-01"), ("patch", "/v1/library/items/top-01"),
                         ("delete", "/v1/library/items/top-01"), ("post", "/v1/library/items/top-01")):
        assert client.request(method.upper(), path, headers=auth("a"), json={"status": "retired"}).status_code == 405, (method, path)
    assert library_state(env) == before


def test_filters_search_and_paging(env):
    for i, (hair, skin) in enumerate((("wavy", "3"), ("curly", "5"), ("wavy", "5"))):
        add(env, f"model-0{i + 1}", "model", name_ko=f"모델 {i + 1}", tags=["여성"], attributes={**MODEL_ATTRS, "hair": hair, "skin_tone": skin})
    add(env, "bag-01", "bag", name_ko="검정 토트백", tags=["가방"])
    get = lambda **q: client.get("/v1/library/items", headers=auth("b"), params=q).json()
    assert [i["item_id"] for i in get(category="model")["items"]] == ["model-01", "model-02", "model-03"]
    assert [i["item_id"] for i in get(category="model", hair="wavy")["items"]] == ["model-01", "model-03"]
    assert [i["item_id"] for i in get(category="model", hair="wavy", skin_tone="5")["items"]] == ["model-03"]
    assert [i["item_id"] for i in get(q="토트")["items"]] == ["bag-01"]
    assert [i["item_id"] for i in get(q="여성", category="model")["items"]] == ["model-01", "model-02", "model-03"]
    page1 = get(limit=2)
    assert [i["item_id"] for i in page1["items"]] == ["bag-01", "model-01"] and page1["next_cursor"] == "model-01"
    page2 = get(limit=2, cursor=page1["next_cursor"])
    assert [i["item_id"] for i in page2["items"]] == ["model-02", "model-03"] and page2["next_cursor"] is None
    assert client.get("/v1/library/items", headers=auth("b"), params={"category": "nonsense"}).status_code == 422


def test_signed_preview_works_without_a_token_and_only_for_the_current_published_version(env):
    add(env, content=png((1, 2, 3)))
    url = client.get("/v1/library/items/top-01/preview-url", headers=auth("b")).json()["url"]
    ok = client.get(url)  # an <img> tag sends no Authorization header
    assert ok.status_code == 200 and ok.headers["content-type"] == "image/png"
    with Image.open(BytesIO(ok.content)) as shown:  # R-035: a screen copy re-encoded from the pixels, not the stored file's bytes
        assert shown.size == (24, 32) and shown.convert("RGB").getpixel((0, 0)) == (1, 2, 3)
    assert client.get(url.replace("signature=", "signature=0")).status_code == 403
    assert client.get(url.replace("expires=", "expires=1")).status_code == 403
    add(env, content=png((9, 9, 9)))  # a new version: the old link must stop working
    assert client.get(url).status_code == 404
    fresh = client.get("/v1/library/items/top-01/preview-url", headers=auth("b")).json()["url"]
    assert client.get(fresh).status_code == 200
    library.set_status("top-01", "retired")
    assert client.get(fresh).status_code == 404, "a link to a retired item stops working"


# ------------------------------------------------------------------------------------------------ import (copy on use)
def test_import_copies_the_item_into_the_workspace_and_leaves_the_original_untouched(env):
    add(env, content=png((5, 6, 7)))
    before = library_state(env)
    r = client.post("/v1/library/items/top-01/import", headers=auth("a"), json={"workspace_id": "wa"})
    assert r.status_code == 201, r.text
    asset = r.json()
    assert asset["workspace_id"] == "wa" and asset["owner_id"] == "user-a" and asset["media_type"] == "image/png"
    assert asset["checksum_sha256"] == hashlib.sha256(png((5, 6, 7))).hexdigest()
    assert library_state(env) == before, "importing must only READ the library"
    db = db_of(env)
    prov = db.execute("SELECT event_type, details_json FROM asset_provenance WHERE asset_id=?", (asset["asset_id"],)).fetchone()
    assert prov["event_type"] == "asset.imported_from_library"
    details = json.loads(prov["details_json"])
    assert details["library_item_id"] == "top-01" and details["library_item_version"] == 1 and details["source"] == "library"
    assert details["library_source"] == "ai_generated" and details["is_ai_generated"] is True
    listed = client.get("/v1/assets?workspace_id=wa&kind=image", headers=auth("a")).json()["items"]
    assert [a["asset_id"] for a in listed] == [asset["asset_id"]]
    # the copy is an ordinary asset: it has its own file in the workspace storage, not the library's
    assert (env / "private" / f"{asset['asset_id']}.png").is_file()


def test_a_later_change_or_retirement_never_breaks_an_existing_copy(env):
    add(env, content=png((5, 6, 7)))
    asset = client.post("/v1/library/items/top-01/import", headers=auth("a"), json={"workspace_id": "wa"}).json()
    add(env, content=png((200, 200, 200)))
    library.set_status("top-01", "retired")
    again = client.get(f"/v1/assets/{asset['asset_id']}", headers=auth("a"))
    assert again.status_code == 200 and again.json()["checksum_sha256"] == hashlib.sha256(png((5, 6, 7))).hexdigest()
    versions = client.get(f"/v1/assets/{asset['asset_id']}/versions", headers=auth("a")).json()["items"]
    assert len(versions) == 1


def test_only_editors_and_above_may_import_and_a_stranger_sees_nothing(env):
    add(env)
    assert client.post("/v1/library/items/top-01/import", json={"workspace_id": "wa"}).status_code == 401
    assert client.post("/v1/library/items/top-01/import", headers=auth("c"), json={"workspace_id": "wa"}).status_code == 403  # viewer
    assert client.post("/v1/library/items/top-01/import", headers=auth("b"), json={"workspace_id": "wa"}).status_code == 404  # not a member
    assert client.get("/v1/assets?workspace_id=wa&kind=image", headers=auth("a")).json()["items"] == []
    assert client.post("/v1/library/items/missing/import", headers=auth("a"), json={"workspace_id": "wa"}).status_code == 404
    assert client.post("/v1/library/items/top-01/import", headers=auth("a"), json={"workspace_id": "wa", "extra": 1}).status_code == 422


def test_import_is_rate_limited_per_workspace_with_the_numbers_in_the_429(env, monkeypatch):
    import app.config as config
    monkeypatch.setattr(config, "LIBRARY_IMPORT_DAILY_LIMIT", 2)
    add(env)
    for _ in range(2):
        assert client.post("/v1/library/items/top-01/import", headers=auth("a"), json={"workspace_id": "wa"}).status_code == 201
    limited = client.post("/v1/library/items/top-01/import", headers=auth("a"), json={"workspace_id": "wa"})
    assert limited.status_code == 429
    assert limited.json()["detail"] == {"code": "LIBRARY_IMPORT_LIMIT", "message": "Daily library import limit reached for this workspace.", "limit": 2, "used": 2}
    assert client.post("/v1/library/items/top-01/import", headers=auth("b"), json={"workspace_id": "wb"}).status_code == 201  # another workspace is unaffected
    assert len(client.get("/v1/assets?workspace_id=wa&kind=image", headers=auth("a")).json()["items"]) == 2


def test_purging_a_workspace_never_touches_the_library(env):
    add(env, content=png((1, 1, 1)))
    asset = client.post("/v1/library/items/top-01/import", headers=auth("b"), json={"workspace_id": "wb"})
    assert asset.status_code == 201
    state = library_state(env)
    client.get("/v1/me/legal-status", headers=auth("b"))  # creates the legal / deletion tables
    db = db_of(env)
    at = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    db.execute("INSERT INTO deletion_requests(request_id,user_id,scope,workspace_id,status,reason,requested_at) VALUES(?,?,?,?,?,?,?)",
               ("del_b", "user-b", "workspace_content", "wb", "pending", "why", at))
    code = purge.main(["--db", str(env / "a.sqlite3"), "--assets-dir", str(env / "private"), "--outputs-dir", str(env / "outputs"),
                       "--apply", "--confirm", "del_b"])
    assert code == 0, "the library tables must not block (or be part of) a purge"
    assert db.execute("SELECT COUNT(*) FROM assets WHERE workspace_id='wb'").fetchone()[0] == 0, "the copy is purged like any asset"
    assert library_state(env) == state, "the library item and its file survive"


def test_the_library_tables_are_declared_global_for_the_purge_script():
    assert {"library_items", "library_item_versions"} <= purge.GLOBAL_TABLES


# ------------------------------------------------------------------------------------------------ the import rules (used by the R-034 tool)
@pytest.mark.parametrize("over, code", [
    ({"rights_confirmed": False}, "LIBRARY_RIGHTS_NOT_CONFIRMED"), ({"rights_confirmed": "yes"}, "LIBRARY_RIGHTS_NOT_CONFIRMED"),
    ({"category": "pants"}, "LIBRARY_CATEGORY_INVALID"), ({"source": "found_online"}, "LIBRARY_SOURCE_INVALID"),
    ({"tool_and_date": ""}, "LIBRARY_FIELD_REQUIRED"), ({"name_ko": " "}, "LIBRARY_FIELD_REQUIRED"),
    ({"item_id": "Top 01"}, "LIBRARY_ID_INVALID"), ({"attributes": {"hair": "wavy"}}, "LIBRARY_ATTRIBUTE_NOT_ALLOWED"),
    ({"status": "deleted"}, "LIBRARY_STATUS_INVALID"),
])
def test_items_without_proof_or_with_unknown_values_are_refused_and_nothing_is_written(env, over, code):
    with pytest.raises(library.LibraryError) as err:
        library.upsert_item(fields(**over), png(), "top-01.png")
    assert err.value.code == code
    assert library_state(env) == ([], [], {})


def test_model_items_need_every_attribute_with_an_allowed_value(env):
    for bad in ({**MODEL_ATTRS, "hair": "bald"}, {**MODEL_ATTRS, "skin_tone": "7"}, {k: v for k, v in MODEL_ATTRS.items() if k != "region_style"}):
        with pytest.raises(library.LibraryError):
            library.upsert_item(fields("model-01", "model", attributes=bad), png(), "model-01.png")
    assert library_state(env) == ([], [], {})
    assert add(env, "model-01", "model")["action"] == "created"


def test_a_file_that_is_not_a_real_image_is_refused(env):
    with pytest.raises(library.LibraryError):
        library.upsert_item(fields(), b"not an image", "top-01.png")
    with pytest.raises(library.LibraryError):
        library.upsert_item(fields(), png(), "top-01.gif")  # extension does not match the PNG content
    assert library_state(env) == ([], [], {})


def test_same_file_is_idempotent_metadata_updates_in_place_and_a_changed_file_is_a_new_version_that_keeps_the_old_one(env):
    assert add(env, content=png((1, 1, 1))) == {"item_id": "top-01", "version": 1, "action": "created"}
    first = library_state(env)
    assert add(env, content=png((1, 1, 1))) == {"item_id": "top-01", "version": 1, "action": "unchanged"}
    assert library_state(env)[1:] == first[1:], "same bytes: no new version, no new file"
    assert add(env, content=png((1, 1, 1)), name_ko="새 이름") == {"item_id": "top-01", "version": 1, "action": "updated"}
    assert client.get("/v1/library/items/top-01", headers=auth("b")).json()["name_ko"] == "새 이름"
    assert add(env, content=png((2, 2, 2))) == {"item_id": "top-01", "version": 2, "action": "new_version"}
    rows, versions, blobs = library_state(env)
    assert [v["version"] for v in versions] == [1, 2] and len(blobs) == 2, "the previous version's file is kept"
    assert rows[0]["version"] == 2
    assert blobs[versions[0]["storage_key"]] == hashlib.sha256(png((1, 1, 1))).hexdigest()
    assert client.get("/v1/library/items/top-01", headers=auth("b")).json()["version"] == 2
