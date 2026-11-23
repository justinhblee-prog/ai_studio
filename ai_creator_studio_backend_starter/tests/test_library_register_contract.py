"""D-01 (answer 69 C.6): the server side of the screen's "register your items" dialog (site/assets/lib.js ``L.register``) - the SAME fields, stored per workspace.

The dialog sends per item: kind, name (<= 30), the garment category (``shape``/``type``), the main colour (#rrggbb), the optional selects (season, ...), SKU and collection, the rights
confirmation (the upload checkbox) and gets the origin from the server. These pin that mapping onto the existing library API (R-045/R-058) so a change on either side shows up here."""
import json

from tests.test_workspace_library import client, db, lib, png, upload  # noqa: F401
from tests.test_photo_steps_api import auth, env  # noqa: F401

DIALOG_ATTRS = {"type": "top", "shape": "shirt", "color": "#c8344c", "season": "summer", "sku": "TOP-001", "collection": "26 S/S"}


def register(name="린넨 셔츠", rgb=(200, 52, 76), who="a", ws="wa", **extra):
    return upload(kind="garment", name=name, file=("a.png", png(rgb), "image/png"), who=who, ws=ws, attrs=json.dumps({**DIALOG_ATTRS, **extra}, ensure_ascii=False))


def test_the_dialogs_fields_are_stored_and_the_origin_comes_from_the_server(env):
    r = register()
    assert r.status_code == 201, r.text
    item = r.json()
    assert item["kind"] == "garment" and item["origin"] == "upload" and item["is_ai_generated"] is False and item["name"] == "린넨 셔츠"
    assert item["attrs"] == DIALOG_ATTRS
    rights = client.get(f"/v1/assets/{item['asset_id']}/rights-confirmation", headers=auth("a"))
    assert rights.status_code == 200, "the rights confirmation is recorded like any image upload"


def test_registering_without_the_rights_confirmation_stores_nothing_when_the_server_requires_it(env, monkeypatch):
    from app import config
    monkeypatch.setattr(config, "ASSET_REQUIRE_RIGHTS_CONFIRMATION", True)
    r = client.post("/v1/workspaces/wa/library", headers=auth("a"), data={"kind": "garment", "name": "x", "attrs": json.dumps(DIALOG_ATTRS)}, files={"file": ("a.png", png(), "image/png")})
    assert r.status_code in (400, 422) and lib().json()["total"] == 0


def test_the_list_filters_by_sku_season_and_collection_and_facets_summarise_them(env):
    register(name="a", rgb=(1, 2, 3))
    register(name="b", rgb=(4, 5, 6), sku="TOP-002", season="winter")
    register(name="c", rgb=(7, 8, 9), sku="TOP-003", collection="26 F/W")
    names = lambda q: sorted(i["name"] for i in client.get(f"/v1/workspaces/wa/library?kind=garment&{q}", headers=auth("a")).json()["items"])
    assert names("attr=sku:TOP-002") == ["b"]
    assert names("attr=season:summer&attr=collection:26 S/S") == ["a"]
    facets = client.get("/v1/workspaces/wa/library/facets?kind=garment", headers=auth("a")).json()
    assert "sku" in json.dumps(facets) and "season" in json.dumps(facets)


def test_attributes_can_be_changed_and_an_item_deleted_and_the_scope_is_the_workspace(env):
    item = register().json()
    patched = client.patch(f"/v1/workspaces/wa/library/{item['item_id']}", headers=auth("a"), json={"attrs": {**DIALOG_ATTRS, "season": "winter"}})
    assert patched.status_code == 200 and patched.json()["attrs"]["season"] == "winter"
    assert client.get(f"/v1/workspaces/wb/library/{item['item_id']}", headers=auth("b")).status_code == 404, "another workspace never sees it"
    assert client.get(f"/v1/workspaces/wa/library/{item['item_id']}", headers=auth("b")).status_code in (403, 404)
    assert register(who="c").status_code == 403, "a viewer may read the library but not register"
    assert client.delete(f"/v1/workspaces/wa/library/{item['item_id']}", headers=auth("c")).status_code == 403
    assert client.delete(f"/v1/workspaces/wa/library/{item['item_id']}", headers=auth("a")).status_code == 204
    assert lib().json()["total"] == 0


def test_a_value_longer_than_the_rule_allows_is_refused_with_a_code(env):
    r = register(sku="X" * 61)
    assert r.status_code == 422 and r.json()["detail"]["code"].startswith("ATTR")
