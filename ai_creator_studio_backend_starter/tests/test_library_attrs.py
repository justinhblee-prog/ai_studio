"""R-058: free key/value attributes on library items: stored, validated (R-055 value rule), replaced by PATCH, filtered in the list, summarised as facets."""
import json
import sqlite3

import pytest

from tests.test_workspace_library import client, db, glb, lib, png, upload  # noqa: F401
from tests.test_photo_steps_api import auth, env  # noqa: F401


def attrs_json(d):
    return json.dumps(d, ensure_ascii=False)


def make(kind="garment", name="x", rgb=(1, 2, 3), **attrs):
    r = upload(kind=kind, name=name, file=("a.png", png(rgb), "image/png"), **({"attrs": attrs_json(attrs)} if attrs else {}))
    assert r.status_code == 201, r.text
    return r.json()


def test_upload_stores_attributes_and_defaults_to_empty(env):
    plain = make(name="plain", rgb=(9, 9, 9))
    assert plain["attrs"] == {}
    item = make(name="셔츠", category="top", season="여름", fit="오버", color="아이보리", material="린넨", brand="아무개", size_no=95, colors=["white", "beige"])
    assert item["attrs"] == {"category": "top", "season": "여름", "fit": "오버", "color": "아이보리", "material": "린넨", "brand": "아무개", "size_no": 95, "colors": ["white", "beige"]}
    got = client.get(f"/v1/workspaces/wa/library/{item['item_id']}", headers=auth("a")).json()
    assert got["attrs"] == item["attrs"]
    assert [i["attrs"] for i in lib().json()["items"] if i["name"] == "plain"] == [{}]


def test_attach_and_patch_set_and_replace_the_whole_set(env):
    up = client.post("/v1/assets/images", headers=auth("a"), data={"workspace_id": "wa", "rights_confirmed": "true"}, files={"file": ("b.png", png((5, 5, 5)), "image/png")})
    assert up.status_code == 201, up.text
    r = client.post("/v1/workspaces/wa/library/attach", headers=auth("a"), json={"asset_id": up.json()["asset_id"], "kind": "bg", "attrs": {"place": "indoor", "mood": "warm"}})
    assert r.status_code == 201 and r.json()["attrs"] == {"place": "indoor", "mood": "warm"}
    iid = r.json()["item_id"]
    p = client.patch(f"/v1/workspaces/wa/library/{iid}", headers=auth("a"), json={"attrs": {"place": "outdoor"}})
    assert p.json()["attrs"] == {"place": "outdoor"}, "PATCH replaces the set"
    assert client.patch(f"/v1/workspaces/wa/library/{iid}", headers=auth("a"), json={"name": "새 이름"}).json()["attrs"] == {"place": "outdoor"}, "other edits keep it"
    assert client.patch(f"/v1/workspaces/wa/library/{iid}", headers=auth("a"), json={"attrs": {}}).json()["attrs"] == {}, "an empty object clears"
    assert client.patch(f"/v1/workspaces/wa/library/{iid}", headers=auth("a"), json={}).status_code == 422


@pytest.mark.parametrize("attrs", [
    {"Bad": "x"}, {"1x": "x"}, {"a-b": "x"}, {"k": "x" * 61}, {"k": 10000}, {"k": -1}, {"k": 1.5}, {"k": True}, {"k": None}, {"k": ""}, {"k": "  "}, {"k": {"n": 1}},
    {"k": []}, {"k": ["a"] * 11}, {"k": [["a"]]}, {f"k{i}": "v" for i in range(21)}, {"k" * 32: "v"},
])
def test_bad_attributes_are_refused_and_nothing_is_created(env, attrs):
    before = lib().json()["total"]
    r = upload(kind="garment", attrs=attrs_json(attrs))
    assert r.status_code == 422, (attrs, r.text)
    assert lib().json()["total"] == before
    it = make(name="ok")
    assert client.patch(f"/v1/workspaces/wa/library/{it['item_id']}", headers=auth("a"), json={"attrs": attrs}).status_code == 422
    assert client.patch(f"/v1/workspaces/wa/library/{it['item_id']}", headers=auth("a"), json={"attrs": "x"}).status_code == 422


def test_upload_attrs_must_be_a_json_object(env):
    assert upload(kind="garment", attrs="not json").status_code == 422
    assert upload(kind="garment", attrs="[1,2]").status_code == 422


def test_edge_values_are_accepted(env):
    item = make(name="edge", zero=0, top=9999, long="가" * 60, **{"k" * 31: "v"})
    assert item["attrs"]["zero"] == 0 and item["attrs"]["top"] == 9999 and len(item["attrs"]["long"]) == 60


def test_list_filter_by_attributes_with_and_semantics(env):
    a = make(name="a", rgb=(11, 0, 0), category="top", season="summer", colors=["white", "beige"], size_no=95)
    b = make(name="b", rgb=(12, 0, 0), category="top", season="winter")
    c = make(name="c", rgb=(13, 0, 0), category="pants", season="summer")
    d = make(name="d", rgb=(14, 0, 0))
    def names(*filters, **params):
        r = client.get("/v1/workspaces/wa/library", headers=auth("a"), params={"attr": list(filters), **params})
        assert r.status_code == 200, r.text
        return sorted(i["name"] for i in r.json()["items"]), r.json()["total"]
    assert names("category:top") == (["a", "b"], 2)
    assert names("category:top", "season:summer") == (["a"], 1), "all filters must match"
    assert names("season:summer") == (["a", "c"], 2)
    assert names("colors:beige") == (["a"], 1), "a list matches when it contains the value"
    assert names("size_no:95") == (["a"], 1), "numbers compare as text"
    assert names("category:top", "season:summer", "colors:black") == ([], 0)
    assert names("category:Top") == ([], 0), "exact, case-sensitive"
    assert names("nothere:x") == ([], 0)
    assert names("category:top", kind="garment") == (["a", "b"], 2) and names("category:top", kind="model") == ([], 0)
    assert names() == (["a", "b", "c", "d"], 4)
    for bad in ("novalue", "k:", ":v", "k:" + "x" * 100):
        assert client.get("/v1/workspaces/wa/library", headers=auth("a"), params={"attr": bad}).status_code == 422, bad
    assert client.get("/v1/workspaces/wa/library", headers=auth("a"), params={"attr": [f"k{i}:v" for i in range(11)]}).status_code == 422, "at most 10 filters"
    # the filter works together with the existing text search and paging
    assert names("season:summer", q="a") == (["a"], 1)
    page = client.get("/v1/workspaces/wa/library", headers=auth("a"), params={"attr": "season:summer", "limit": 1, "offset": 1}).json()
    assert page["total"] == 2 and len(page["items"]) == 1


def test_facets_list_keys_values_and_counts_and_respect_kind_and_roles(env):
    make(name="a", rgb=(21, 0, 0), category="top", season="summer", colors=["white", "beige"])
    make(name="b", rgb=(22, 0, 0), category="top", season="winter")
    upload(kind="model", name="m", file=("m.png", png((23, 0, 0)), "image/png"), attrs=attrs_json({"gender": "female", "age": 25}))
    all_ = client.get("/v1/workspaces/wa/library/facets", headers=auth("a")).json()
    f = {x["key"]: {v["value"]: v["count"] for v in x["values"]} for x in all_["facets"]}
    assert f["category"] == {"top": 2} and f["season"] == {"summer": 1, "winter": 1} and f["colors"] == {"white": 1, "beige": 1} and f["gender"] == {"female": 1} and f["age"] == {"25": 1}
    only = client.get("/v1/workspaces/wa/library/facets", headers=auth("a"), params={"kind": "model"}).json()
    assert [x["key"] for x in only["facets"]] == ["age", "gender"] and only["kind"] == "model"
    assert client.get("/v1/workspaces/wa/library/facets", headers=auth("c")).status_code == 200, "a viewer may read"
    assert client.get("/v1/workspaces/wa/library/facets", headers=auth("b")).status_code in (403, 404)
    assert client.get("/v1/workspaces/wa/library/facets").status_code == 401


def test_roles_viewers_cannot_write_attributes(env):
    it = make(name="r", rgb=(31, 0, 0), category="top")
    assert client.patch(f"/v1/workspaces/wa/library/{it['item_id']}", headers=auth("c"), json={"attrs": {"category": "x"}}).status_code == 403
    assert upload(kind="garment", who="c", attrs=attrs_json({"a": "b"})).status_code == 403
    seen = client.get(f"/v1/workspaces/wa/library/{it['item_id']}", headers=auth("c")).json()
    assert seen["attrs"] == {"category": "top"}, "a viewer reads them"


def test_an_existing_database_without_the_column_is_migrated(env):
    with db(env) as c:
        c.execute("DROP TABLE IF EXISTS workspace_library_items")
        c.execute("""CREATE TABLE workspace_library_items (item_id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, asset_id TEXT NOT NULL, kind TEXT NOT NULL,
            origin TEXT NOT NULL, name TEXT NOT NULL, tags_json TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            UNIQUE(workspace_id, asset_id))""")
    item = make(name="after", rgb=(41, 0, 0), category="top")
    assert item["attrs"] == {"category": "top"}
    with db(env) as c:
        assert any(r[1] == "attrs_json" for r in c.execute("PRAGMA table_info(workspace_library_items)").fetchall())
