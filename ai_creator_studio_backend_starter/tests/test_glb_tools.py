"""Lane 1 / E-01: GLB inspection + normalization on a small regression set built in the test (no binary fixtures in the repo)."""
import json
import struct

import pytest

from app.assets.validation import validate_gltf_upload
from app.glb_tools import GlbError, build_glb, inspect_glb, normalize_glb, parse_glb

PNG = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c6360000002000001e221bc330000000049454e44ae426082")


def box(extra_views=False, duplicate_png=False, padding=0):
    """A unit box: 8 corners, 12 triangles; optional unused views, two identical embedded pictures, loose padding."""
    pos = struct.pack("<24f", *[c for x in (-.5, .5) for y in (-.5, .5) for z in (-.5, .5) for c in (x, y, z)])
    idx = struct.pack("<36H", 0, 1, 3, 0, 3, 2, 4, 6, 7, 4, 7, 5, 0, 4, 5, 0, 5, 1, 2, 3, 7, 2, 7, 6, 0, 2, 6, 0, 6, 4, 1, 5, 7, 1, 7, 3)
    binary, views = b"", []

    def add(blob):
        nonlocal binary
        binary += b"\x00" * (padding + (-len(binary) % 4))
        views.append({"buffer": 0, "byteOffset": len(binary), "byteLength": len(blob)})
        binary += blob
        return len(views) - 1
    if extra_views:
        add(b"JUNKJUNKJUNK")                          # nothing refers to it
    v_pos, v_idx = add(pos), add(idx)
    images, textures = [], []
    for _ in range(2 if duplicate_png else 1):
        images.append({"bufferView": add(PNG), "mimeType": "image/png"})
        textures.append({"source": len(images) - 1})
    doc = {"asset": {"version": "2.0"}, "scene": 0, "scenes": [{"nodes": [0]}], "nodes": [{"mesh": 0}],
           "meshes": [{"primitives": [{"attributes": {"POSITION": 0}, "indices": 1, "material": 0}]}],
           "materials": [{"pbrMetallicRoughness": {"baseColorTexture": {"index": 0}}}], "textures": textures, "images": images,
           "accessors": [{"bufferView": v_pos, "componentType": 5126, "count": 8, "type": "VEC3", "min": [-.5, -.5, -.5], "max": [.5, .5, .5]},
                         {"bufferView": v_idx, "componentType": 5123, "count": 36, "type": "SCALAR"}],
           "bufferViews": views, "buffers": [{"byteLength": len(binary)}]}
    return build_glb(doc, binary)


def test_inspect_reports_the_numbers_of_a_box():
    info = inspect_glb(box())
    assert info["triangles"] == 12 and info["meshes"] == 1 and info["materials"] == 1 and info["textures"] == 1 and info["images"] == 1
    assert info["size"] == [1.0, 1.0, 1.0] and info["bounds_min"] == [-.5, -.5, -.5] and info["image_bytes"] == len(PNG)
    assert info["has_external_uri"] is False and info["file_bytes"] == len(box())


def test_normalize_drops_unused_views_shares_identical_pictures_and_keeps_the_picture_the_same():
    messy = box(extra_views=True, duplicate_png=True, padding=64)
    out, report = normalize_glb(messy)
    assert report["changed"] and report["deduplicated_images"] == 1 and report["dropped_buffer_views"] == 2     # junk view + the duplicate picture's view
    assert len(out) < len(messy) and report["saved_bytes"] == len(messy) - len(out) > 0
    before, after = report["before"], report["after"]
    for key in ("triangles", "meshes", "materials", "textures", "images", "size", "bounds_min", "bounds_max"):
        assert before[key] == after[key], key
    doc, binary = parse_glb(out)
    assert doc["images"][0]["bufferView"] == doc["images"][1]["bufferView"]
    view = doc["bufferViews"][doc["images"][0]["bufferView"]]
    assert binary[view["byteOffset"]: view["byteOffset"] + view["byteLength"]] == PNG
    assert all(v["byteOffset"] % 4 == 0 for v in doc["bufferViews"]) and 0 <= len(binary) - doc["buffers"][0]["byteLength"] < 4
    assert validate_gltf_upload("n.glb", out).media_type == "model/gltf-binary", "the normalized file still passes the upload checks"


def test_normalize_is_idempotent_and_a_clean_file_is_stable():
    once, _ = normalize_glb(box(extra_views=True, duplicate_png=True, padding=16))
    twice, report = normalize_glb(once)
    assert twice == once and report["changed"] is False and report["dropped_buffer_views"] == 0 and report["deduplicated_images"] == 0
    clean, r = normalize_glb(box())
    assert normalize_glb(clean)[0] == clean


def test_the_geometry_bytes_survive_unchanged():
    messy = box(extra_views=True, padding=32)
    out, _ = normalize_glb(messy)
    def geometry(blob):
        d, b = parse_glb(blob)
        return [b[d["bufferViews"][a["bufferView"]]["byteOffset"]:][: d["bufferViews"][a["bufferView"]]["byteLength"]] for a in d["accessors"]]
    assert geometry(out) == geometry(messy)


@pytest.mark.parametrize("mutate,reason", [
    (lambda d: d["buffers"][0].__setitem__("uri", "data:application/octet-stream;base64,AAAA"), "URI"),
    (lambda d: d["bufferViews"][0].__setitem__("extensions", {"EXT_meshopt_compression": {}}), "compressed"),
    (lambda d: d["buffers"].append({"byteLength": 4}), "more than one buffer"),
])
def test_a_file_that_cannot_be_rewritten_safely_comes_back_unchanged_with_a_reason(mutate, reason):
    doc, binary = parse_glb(box())
    mutate(doc)
    raw = build_glb(doc, binary)
    out, report = normalize_glb(raw)
    assert out == raw and report["changed"] is False and reason in report["reason"]


def test_garbage_is_refused():
    for bad in (b"", b"hello", b"glTF" + b"\x00" * 30):
        with pytest.raises(GlbError):
            parse_glb(bad)
    with pytest.raises(GlbError):
        parse_glb(struct.pack("<III", 0x46546C67, 1, 12))


def test_triangle_counts_follow_the_primitive_mode():
    doc, binary = parse_glb(box())
    doc["meshes"][0]["primitives"][0]["mode"] = 5          # strip: 36 indices -> 34
    assert inspect_glb(build_glb(doc, binary))["triangles"] == 34
    del doc["meshes"][0]["primitives"][0]["indices"]       # no indices: 8 vertices -> 2 triangles in mode 4... mode is 5 -> 6
    assert inspect_glb(build_glb(doc, binary))["triangles"] == 6
