"""R-045: the workspace's own library: attach/upload/list/patch/remove, server-decided origin, roles, isolation, caps, holds, purge."""
import json
import sqlite3
import struct
import uuid
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import config
from app.main import app
from tests.test_photo_steps_api import auth, env  # noqa: F401  (workspaces wa: owner a + viewer c, wb: owner b)

client = TestClient(app)


def png(color=(10, 20, 30)):
    buf = BytesIO(); Image.new("RGB", (24, 24), color).save(buf, format="PNG"); return buf.getvalue()


def glb(extra=None):
    doc = {"asset": {"version": "2.0"}}
    if extra:
        doc.update(extra)
    raw = json.dumps(doc).encode()
    raw += b" " * ((4 - len(raw) % 4) % 4)
    chunk = struct.pack("<II", len(raw), 0x4E4F534A) + raw
    return b"glTF" + struct.pack("<II", 2, 12 + len(chunk)) + chunk


def lib(ws="wa", who="a"):
    return client.get(f"/v1/workspaces/{ws}/library", headers=auth(who))


def upload(kind="model", name="셔츠", file=None, who="a", ws="wa", **fields):
    data = {"kind": kind, "name": name, "rights_confirmed": "true", **fields}
    return client.post(f"/v1/workspaces/{ws}/library", headers=auth(who), data=data,
                       files={"file": file or ("a.png", png(), "image/png")})


def db(env):
    return sqlite3.connect(env["tmp"] / "a.sqlite3")


def test_upload_image_creates_asset_and_item_with_server_origin_and_rights_record(env):
    r = upload(kind="garment", name="  린넨 셔츠 ", tags="여름, 린넨,여름")
    assert r.status_code == 201, r.text
    item = r.json()
    assert (item["kind"], item["origin"], item["is_ai_generated"], item["name"], item["tags"]) == ("garment", "upload", False, "린넨 셔츠", ["여름", "린넨"])
    assert item["created_by"] == "user-a" and item["media_type"] == "image/png" and item["workspace_id"] == "wa"
    assets = client.get("/v1/assets?workspace_id=wa&kind=image", headers=auth("a")).json()["items"]
    assert item["asset_id"] in {a["asset_id"] for a in assets}
    rights = client.get(f"/v1/assets/{item['asset_id']}/rights-confirmation", headers=auth("a"))
    assert rights.status_code == 200 and rights.json()["depicts_person"] is False, "the declaration is recorded like any image upload"


def test_image_upload_needs_the_rights_declaration_and_nothing_is_stored_without_it(env, monkeypatch):
    monkeypatch.setattr(config, "ASSET_REQUIRE_RIGHTS_CONFIRMATION", True)
    r = client.post("/v1/workspaces/wa/library", headers=auth("a"), data={"kind": "model", "name": "x"}, files={"file": ("a.png", png(), "image/png")})
    assert r.status_code == 422
    assert lib().json()["total"] == 0
    assert len(client.get("/v1/assets?workspace_id=wa&kind=image", headers=auth("a")).json()["items"]) == 1, "only the fixture's own image"


def test_3d_items_are_glb_only_with_external_references_refused(env):
    ok = upload(kind="3d", name="의자", file=("chair.glb", glb(), "model/gltf-binary"))
    assert ok.status_code == 201, ok.text
    assert ok.json()["kind"] == "3d" and ok.json()["origin"] == "upload"
    external = upload(kind="3d", file=("ext.glb", glb({"buffers": [{"uri": "http://evil.example/x.bin", "byteLength": 4}]}), "model/gltf-binary"))
    assert external.status_code == 422
    not_a_model = upload(kind="3d", file=("a.png", png(), "image/png"))
    assert not_a_model.status_code == 422
    assert upload(kind="model", file=("c.glb", glb(), "model/gltf-binary")).status_code == 422, "an image kind refuses a 3D file"
    assert lib().json()["total"] == 1


def test_attach_filters_origin_by_provenance_not_by_what_the_client_says(env):
    asset = env["asset"]
    r = client.post("/v1/workspaces/wa/library/attach", headers=auth("a"), json={"asset_id": asset, "kind": "model"})
    assert r.status_code == 201 and r.json()["origin"] == "upload"
    assert client.post("/v1/workspaces/wa/library/attach", headers=auth("a"), json={"asset_id": asset, "kind": "bg"}).status_code == 409
    other = upload(kind="prop").json()["asset_id"]   # an upload, then a generated-output provenance event is recorded for a second asset
    up2 = client.post("/v1/assets/images", headers=auth("a"), data={"workspace_id": "wa", "rights_confirmed": "true"}, files={"file": ("g.png", png((9, 9, 9)), "image/png")}).json()["asset_id"]
    with db(env) as c:
        c.execute("INSERT INTO asset_provenance(provenance_id, workspace_id, asset_id, version_number, event_type, actor_id, details_json, created_at) VALUES (?,?,?,?,?,?,?,?)",
                  ("ap_" + uuid.uuid4().hex, "wa", up2, 1, "asset.generated_output_imported", "worker", "{}", "2026-11-16T00:00:00+00:00"))
    ai = client.post("/v1/workspaces/wa/library/attach", headers=auth("a"), json={"asset_id": up2, "kind": "render", "name": "결과"})
    assert ai.status_code == 201 and ai.json()["origin"] == "ai" and ai.json()["is_ai_generated"] is True
    assert client.post("/v1/workspaces/wa/library/attach", headers=auth("a"), json={"asset_id": up2, "kind": "render", "origin": "upload"}).status_code == 422, "no origin field is accepted"
    assert {i["origin"] for i in lib().json()["items"]} == {"upload", "ai"} and other


def test_work_origin_for_photo_step_results(env):
    done = client.post("/v1/workspaces/wa/photo-steps", headers=auth("a"), json={"asset_id": env["asset"], "steps": [{"op": "auto_crop"}]}).json()["asset"]["asset_id"]
    r = client.post("/v1/workspaces/wa/library/attach", headers=auth("a"), json={"asset_id": done, "kind": "render"})
    assert r.status_code == 201 and r.json()["origin"] == "work" and r.json()["is_ai_generated"] is False


def test_kind_must_match_the_asset_type(env):
    glb_asset = client.post("/v1/assets", headers=auth("a"), data={"workspace_id": "wa"}, files={"file": ("c.glb", glb(), "model/gltf-binary")}).json()["asset_id"]
    assert client.post("/v1/workspaces/wa/library/attach", headers=auth("a"), json={"asset_id": glb_asset, "kind": "model"}).status_code == 422
    assert client.post("/v1/workspaces/wa/library/attach", headers=auth("a"), json={"asset_id": env["asset"], "kind": "3d"}).status_code == 422
    assert client.post("/v1/workspaces/wa/library/attach", headers=auth("a"), json={"asset_id": glb_asset, "kind": "3d"}).status_code == 201
    assert client.post("/v1/workspaces/wa/library/attach", headers=auth("a"), json={"asset_id": "ast_missing", "kind": "model"}).status_code == 404
    assert client.post("/v1/workspaces/wa/library/attach", headers=auth("a"), json={"asset_id": env["asset"], "kind": "sofa"}).status_code == 422


def test_list_filters_search_and_paging(env):
    upload(kind="garment", name="Blue Shirt", tags="summer")
    upload(kind="garment", name="Red Dress", tags="party", file=("b.png", png((200, 0, 0)), "image/png"))
    upload(kind="bg", name="Studio 100%", file=("c.png", png((0, 200, 0)), "image/png"))
    assert lib().json()["total"] == 3
    assert [i["name"] for i in client.get("/v1/workspaces/wa/library?kind=garment", headers=auth("a")).json()["items"]] == ["Red Dress", "Blue Shirt"], "newest first"
    assert [i["name"] for i in client.get("/v1/workspaces/wa/library?q=summer", headers=auth("a")).json()["items"]] == ["Blue Shirt"]
    assert [i["name"] for i in client.get("/v1/workspaces/wa/library?q=100%25", headers=auth("a")).json()["items"]] == ["Studio 100%"], "% is literal"
    assert client.get("/v1/workspaces/wa/library?q=%25", headers=auth("a")).json()["total"] == 1, "a lone % matches only names that contain it"
    page = client.get("/v1/workspaces/wa/library?limit=2&offset=2", headers=auth("a")).json()
    assert page["total"] == 3 and len(page["items"]) == 1
    assert client.get("/v1/workspaces/wa/library?kind=sofa", headers=auth("a")).status_code == 422
    assert client.get("/v1/workspaces/wa/library?limit=0", headers=auth("a")).status_code == 422


def test_roles_and_workspace_isolation(env):
    item = upload().json()
    assert lib(who="c").status_code == 200 and lib(who="c").json()["total"] == 1, "a viewer reads"
    assert client.get(f"/v1/workspaces/wa/library/{item['item_id']}", headers=auth("c")).status_code == 200
    assert upload(who="c").status_code == 403
    assert client.post("/v1/workspaces/wa/library/attach", headers=auth("c"), json={"asset_id": env["asset"], "kind": "model"}).status_code == 403
    assert client.patch(f"/v1/workspaces/wa/library/{item['item_id']}", headers=auth("c"), json={"name": "x"}).status_code == 403
    assert client.delete(f"/v1/workspaces/wa/library/{item['item_id']}", headers=auth("c")).status_code == 403
    assert client.get("/v1/workspaces/wa/library").status_code == 401
    assert lib(who="b").status_code in (403, 404), "not a member"
    assert lib(ws="wb", who="b").json()["total"] == 0, "another workspace's library is empty"
    assert client.get(f"/v1/workspaces/wb/library/{item['item_id']}", headers=auth("b")).status_code == 404
    assert client.patch(f"/v1/workspaces/wb/library/{item['item_id']}", headers=auth("b"), json={"name": "x"}).status_code == 404
    assert client.delete(f"/v1/workspaces/wb/library/{item['item_id']}", headers=auth("b")).status_code == 404
    assert client.post("/v1/workspaces/wb/library/attach", headers=auth("b"), json={"asset_id": env["asset"], "kind": "model"}).status_code == 404, "another workspace's asset id"


def test_patch_changes_only_name_and_tags(env):
    item = upload(tags="a").json()
    r = client.patch(f"/v1/workspaces/wa/library/{item['item_id']}", headers=auth("a"), json={"name": "새 이름", "tags": ["x", " y ", "x"]})
    assert r.status_code == 200 and r.json()["name"] == "새 이름" and r.json()["tags"] == ["x", "y"] and r.json()["kind"] == item["kind"] and r.json()["asset_id"] == item["asset_id"]
    assert client.patch(f"/v1/workspaces/wa/library/{item['item_id']}", headers=auth("a"), json={}).status_code == 422
    assert client.patch(f"/v1/workspaces/wa/library/{item['item_id']}", headers=auth("a"), json={"kind": "bg"}).status_code == 422
    assert client.patch(f"/v1/workspaces/wa/library/{item['item_id']}", headers=auth("a"), json={"name": "  "}).status_code == 422
    assert client.patch(f"/v1/workspaces/wa/library/{item['item_id']}", headers=auth("a"), json={"tags": ["z" * 31]}).status_code == 422
    assert client.patch(f"/v1/workspaces/wa/library/{item['item_id']}", headers=auth("a"), json={"tags": ["t"] * 11}).status_code == 422


def test_remove_keeps_the_asset_unless_asked_and_deletion_guards_still_apply(env):
    item = upload().json()
    assert client.delete(f"/v1/workspaces/wa/library/{item['item_id']}", headers=auth("a")).status_code == 204
    assert lib().json()["total"] == 0
    assert client.get(f"/v1/assets/{item['asset_id']}", headers=auth("a")).status_code == 200, "the asset itself stays"
    assert client.delete(f"/v1/workspaces/wa/library/{item['item_id']}", headers=auth("a")).status_code == 404
    second = upload(file=("b.png", png((1, 2, 3)), "image/png")).json()
    assert client.delete(f"/v1/workspaces/wa/library/{second['item_id']}?delete_asset=true", headers=auth("a")).status_code == 204
    assert client.get(f"/v1/assets/{second['asset_id']}", headers=auth("a")).status_code == 404
    # a generated-output asset cannot be deleted through the library either (output retention workflow)
    third = upload(file=("c.png", png((4, 5, 6)), "image/png")).json()
    with db(env) as c:
        c.execute("INSERT INTO asset_provenance(provenance_id, workspace_id, asset_id, version_number, event_type, actor_id, details_json, created_at) VALUES (?,?,?,?,?,?,?,?)",
                  ("ap_" + uuid.uuid4().hex, "wa", third["asset_id"], 1, "asset.generated_output_imported", "worker", "{}", "2026-11-16T00:00:00+00:00"))
    blocked = client.delete(f"/v1/workspaces/wa/library/{third['item_id']}?delete_asset=true", headers=auth("a"))
    assert blocked.status_code == 409 and blocked.json()["detail"]["code"] == "ASSET_IN_USE"
    assert lib().json()["total"] == 1, "a refused deletion keeps the item"


def test_an_item_whose_asset_was_deleted_elsewhere_disappears(env):
    item = upload().json()
    assert client.delete(f"/v1/assets/{item['asset_id']}", headers=auth("a")).status_code == 204
    assert lib().json()["total"] == 0
    assert client.get(f"/v1/workspaces/wa/library/{item['item_id']}", headers=auth("a")).status_code == 404


def test_caps_refuse_before_storing(env, monkeypatch):
    monkeypatch.setattr(config, "WORKSPACE_LIBRARY_MAX_ITEMS", 2)
    monkeypatch.setattr(config, "WORKSPACE_LIBRARY_MAX_3D", 1)
    assert upload().status_code == 201
    assert upload(kind="3d", file=("c.glb", glb(), "model/gltf-binary")).status_code == 201
    full = upload(file=("z.png", png((7, 7, 7)), "image/png"))
    assert full.status_code == 409 and full.json()["detail"]["code"] == "LIBRARY_FULL"
    assert len(client.get("/v1/assets?workspace_id=wa&kind=image", headers=auth("a")).json()["items"]) == 2, "fixture image + the one upload; the refused file was not stored"
    monkeypatch.setattr(config, "WORKSPACE_LIBRARY_MAX_ITEMS", 10)
    over = upload(kind="3d", file=("d.glb", glb(), "model/gltf-binary"))
    assert over.status_code == 409 and over.json()["detail"]["code"] == "LIBRARY_3D_FULL"
    monkeypatch.setattr(config, "WORKSPACE_LIBRARY_MAX_3D_BYTES", 10)
    monkeypatch.setattr(config, "WORKSPACE_LIBRARY_MAX_3D", 5)
    assert upload(kind="3d", file=("e.glb", glb(), "model/gltf-binary")).status_code == 413


def test_a_held_asset_is_hidden_from_members_but_not_from_its_owner(env):
    item = upload().json()
    with db(env) as c:
        c.execute("INSERT INTO asset_takedowns(asset_id, workspace_id, state, since, updated_at) VALUES (?,?,?,?,?)",
                  (item["asset_id"], "wa", "under_review", "2026-11-16T00:00:00+00:00", "2026-11-16T00:00:00+00:00"))
    assert lib(who="c").json()["total"] == 0, "the viewer no longer sees the held item"
    assert client.get(f"/v1/workspaces/wa/library/{item['item_id']}", headers=auth("c")).status_code == 404
    assert lib(who="a").json()["total"] == 1, "its owner still does"


# ---- R-049: thumbnail of a 3D item (rendered by the browser) and the model information read from the file's own JSON ----
def png_size(w, h, color=(5, 6, 7)):
    buf = BytesIO(); Image.new("RGB", (w, h), color).save(buf, format="PNG"); return buf.getvalue()


def put_thumb(item_id, content=None, who="a", ws="wa", name="thumb.png"):
    return client.put(f"/v1/workspaces/{ws}/library/{item_id}/thumbnail", headers=auth(who), files={"file": (name, content or png_size(64, 64), "image/png")})


def make_3d(extra=None, name="의자"):
    r = upload(kind="3d", name=name, file=("chair.glb", glb(extra), "model/gltf-binary"))
    assert r.status_code == 201, r.text
    return r.json()


def test_a_3d_item_gets_a_browser_rendered_thumbnail_and_replacing_it_removes_the_old_one(env):
    item = make_3d()
    assert item["thumbnail_asset_id"] is None
    first = put_thumb(item["item_id"])
    assert first.status_code == 200, first.text
    t1 = first.json()["thumbnail_asset_id"]
    assert t1 and client.get(f"/v1/assets/{t1}", headers=auth("a")).json()["media_type"] == "image/png"
    prov = client.get(f"/v1/assets/{t1}/provenance", headers=auth("a")).json()
    events = [p["event_type"] for p in (prov["items"] if isinstance(prov, dict) else prov)]
    assert "asset.thumbnail" in events
    second = put_thumb(item["item_id"], png_size(80, 40, (9, 9, 9)))
    t2 = second.json()["thumbnail_asset_id"]
    assert t2 and t2 != t1
    assert client.get(f"/v1/assets/{t1}", headers=auth("a")).status_code == 404, "the replaced thumbnail is gone"
    assert lib().json()["items"][0]["thumbnail_asset_id"] == t2, "the list shows it"
    assert client.get(f"/v1/workspaces/wa/library/{item['item_id']}", headers=auth("a")).json()["thumbnail_asset_id"] == t2
    assert len(client.get("/v1/assets?workspace_id=wa&kind=image", headers=auth("a")).json()["items"]) == 2, "fixture image + one thumbnail"


def test_thumbnail_rules(env):
    item = make_3d()
    image_item = upload(kind="model").json()
    assert put_thumb(image_item["item_id"]).status_code == 422, "only 3D items have one"
    assert put_thumb(item["item_id"], png_size(1025, 10)).status_code == 422, "at most 1024 px"
    assert put_thumb(item["item_id"], b"not an image").status_code == 422
    assert put_thumb(item["item_id"], b"x" * (2 * 1024 * 1024 + 1)).status_code == 413
    assert put_thumb("wli_missing").status_code == 404
    assert put_thumb(item["item_id"], who="c").status_code == 403, "a viewer cannot"
    assert put_thumb(item["item_id"], ws="wb", who="b").status_code == 404, "another workspace"
    assert client.put(f"/v1/workspaces/wa/library/{item['item_id']}/thumbnail", files={"file": ("t.png", png_size(8, 8), "image/png")}).status_code == 401
    assert len(client.get("/v1/assets?workspace_id=wa&kind=image", headers=auth("a")).json()["items"]) == 2, "fixture + the image item; the refused thumbnails stored nothing"


def test_removing_the_item_removes_its_thumbnail(env):
    item = make_3d()
    t = put_thumb(item["item_id"]).json()["thumbnail_asset_id"]
    assert client.delete(f"/v1/workspaces/wa/library/{item['item_id']}", headers=auth("a")).status_code == 204
    assert client.get(f"/v1/assets/{t}", headers=auth("a")).status_code == 404


def test_model_info_comes_from_the_files_own_json(env):
    item = make_3d({"scenes": [{}], "nodes": [{}, {}, {}], "materials": [{}, {}], "extensionsUsed": ["KHR_materials_unlit"]})
    r = client.get(f"/v1/workspaces/wa/library/{item['item_id']}/model-info", headers=auth("c"))
    assert r.status_code == 200, r.text
    info = r.json()
    assert (info["format"], info["gltf_version"], info["scenes"], info["nodes"], info["materials"], info["meshes"], info["animations"]) == ("glb", "2.0", 1, 3, 2, 0, 0)
    assert info["extensions_used"] == ["KHR_materials_unlit"] and info["triangles"] == 0 and info["size_bytes"] == item["size_bytes"]
    assert client.get(f"/v1/workspaces/wa/library/{upload().json()['item_id']}/model-info", headers=auth("a")).status_code == 422, "not a 3D item"
    assert client.get(f"/v1/workspaces/wb/library/{item['item_id']}/model-info", headers=auth("b")).status_code == 404
    assert client.get(f"/v1/workspaces/wa/library/{item['item_id']}/model-info").status_code == 401


def test_gltf_stats_counts_triangles_and_does_not_guess_when_it_cannot():
    from app.workspace_library import gltf_document, gltf_stats
    doc = {"asset": {"version": "2.0", "generator": "x" * 300}, "accessors": [{"count": 8}, {"count": 36}, {"count": 4}],
           "meshes": [{"primitives": [{"attributes": {"POSITION": 0}, "indices": 1}, {"attributes": {"POSITION": 0}}]}],
           "animations": [{}], "skins": [{}], "cameras": [{}], "textures": [{}], "images": [{}]}
    s = gltf_stats(doc)
    assert s["meshes"] == 1 and s["primitives"] == 2 and s["triangles"] == 36 // 3 + 8 // 3 and len(s["generator"]) == 120
    assert (s["animations"], s["skins"], s["cameras"], s["textures"], s["images"]) == (1, 1, 1, 1, 1)
    strip = {"accessors": [{"count": 9}], "meshes": [{"primitives": [{"attributes": {"POSITION": 0}, "mode": 5}]}]}
    assert gltf_stats(strip)["triangles"] is None, "a triangle strip is not counted as if it were a list"
    assert gltf_stats({"meshes": [{"primitives": [{"attributes": {"POSITION": 7}}]}], "accessors": []})["triangles"] is None
    assert gltf_stats({"asset": "bad", "nodes": "bad", "extensionsUsed": [1, "ok"]})["nodes"] == 0
    assert gltf_document(b'{"asset": {"version": "2.0"}}')[0] == "gltf"
    for bad in (b"glTF" + b"\0" * 4, b"\xff\xfe", b"[1, 2"):
        with pytest.raises((ValueError, UnicodeDecodeError)):
            gltf_document(bad)
