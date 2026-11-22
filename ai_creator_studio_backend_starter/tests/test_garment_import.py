"""E-15 (own-code part): a user-uploaded garment .glb -> a garment.v1 candidate: transforms baked in, scale estimated (and never silently chosen when ambiguous), size estimated, rights enforced."""
import copy
import math

import pytest

from app import garment_deform, garment_import as gi, garments
from app.assets.validation import validate_gltf_upload
from app.glb_tools import build_glb, parse_glb


def tube(radius=0.15, height=0.6, levels=11, sides=24):
    vertices = [(radius * math.cos(2 * math.pi * s / sides), y * height / (levels - 1), radius * math.sin(2 * math.pi * s / sides)) for y in range(levels) for s in range(sides)]
    triangles = []
    for y in range(levels - 1):
        for s in range(sides):
            a, b, c, d = y * sides + s, y * sides + (s + 1) % sides, (y + 1) * sides + s, (y + 1) * sides + (s + 1) % sides
            triangles += [(a, c, b), (b, c, d)]
    return vertices, triangles


def user_glb(vertices=None, triangles=None, edit=None, colour=(0.2, 0.4, 0.8)):
    v, t = tube() if vertices is None else (vertices, triangles)
    doc, binary = parse_glb(gi._write(v, t, colour, {}))
    if edit:
        edit(doc)
    return build_glb(doc, bytes(binary))


def scaled(factor):
    return user_glb(edit=lambda d: d["nodes"][0].update({"scale": [factor] * 3}))


def convert(glb, **over):
    args = dict(garment_id="my-top", kind="top", provenance="user upload ast_1", rights_confirmed=True)
    args.update(over)
    return gi.to_garment(glb, **args)


def test_a_clean_metre_model_is_analysed_and_converted_with_a_good_size_estimate():
    glb = user_glb()
    info = gi.analyze(glb)
    assert info["triangles"] == 10 * 24 * 2 and info["size_units"][1] == pytest.approx(0.6, abs=1e-4) and info["ambiguous"] is False
    assert [c["unit"] for c in info["scale_candidates"]] == ["metres"] and "top" in info["plausible_kinds"] and info["base_colour"] == [0.2, 0.4, 0.8]
    clean, spec, report = convert(glb)
    assert spec["sizes"]["M"]["chest_cm"] == pytest.approx(2 * math.pi * 15, rel=0.01), "a round tube of radius 15 cm is 94.2 cm round"
    assert spec["sizes"]["M"]["length_cm"] == pytest.approx(60.0, abs=0.2) and report["estimated"] is True and report["fit_ready"] is False
    assert spec["schema"] == "garment.v1" and "fit" not in spec and spec["source"] == {"provenance": "user upload ast_1", "third_party_asset": True, "rights_confirmed": True}


def test_node_transforms_are_baked_in_so_a_hundred_times_scaled_node_is_measured_in_its_real_size():
    glb = scaled(100.0)
    info = gi.analyze(glb)
    assert info["size_units"][1] == pytest.approx(60.0, abs=0.01), "the node's scale of 100 is part of the size"
    assert {c["unit"] for c in info["scale_candidates"]} == {"centimetres", "inches"} and info["ambiguous"] is True and any("ambiguous" in w for w in info["warnings"])
    clean, spec, _ = convert(glb, scale=0.01)
    assert spec["sizes"]["M"]["chest_cm"] == pytest.approx(2 * math.pi * 15, rel=0.01)
    doc, _ = parse_glb(clean)
    assert doc["nodes"][0].get("scale") is None and doc["nodes"][0].get("translation") is None, "the result has no transform left: the vertices are in place"


def test_an_ambiguous_or_implausible_scale_is_refused_not_guessed():
    with pytest.raises(gi.GarmentImportError) as ambiguous:
        convert(scaled(100.0))
    assert ambiguous.value.code == "IMPORT_SCALE_AMBIGUOUS"
    with pytest.raises(gi.GarmentImportError) as implausible:
        convert(scaled(1000000.0))
    assert implausible.value.code == "IMPORT_SCALE_IMPLAUSIBLE"
    for bad in (0, -1, True, "0.01", 1000):
        with pytest.raises(gi.GarmentImportError) as exc:
            convert(user_glb(), scale=bad)
        assert exc.value.code == "IMPORT_SCALE_INVALID"


def test_a_hierarchy_with_a_translation_and_a_rotation_is_baked_and_a_flat_model_is_warned_about():
    def lie_down(doc):                                              # parent moves it, child turns it 90 degrees about Z: the tube now lies along X
        s = math.sqrt(0.5)
        doc["nodes"] = [{"name": "root", "translation": [5.0, 2.0, -3.0], "children": [1]}, {**doc["nodes"][0], "rotation": [0, 0, s, s]}]
        doc["scenes"] = [{"nodes": [0]}]
    glb = user_glb(*tube(height=0.9), edit=lie_down)
    info = gi.analyze(glb)
    assert info["size_units"][0] == pytest.approx(0.9, abs=1e-3) and info["size_units"][1] == pytest.approx(0.3, abs=1e-3)
    assert info["bounds_min"][0] == pytest.approx(5.0 - 0.9, abs=1e-3) and info["bounds_max"][0] == pytest.approx(5.0, abs=1e-3), "the parent translation and the child rotation are both in the numbers"
    assert any("lying flat" in w for w in info["warnings"])


def test_the_hem_is_put_on_the_floor_and_the_output_is_a_valid_garment_and_upload():
    clean, spec, _ = convert(user_glb(edit=lambda d: d["nodes"][0].update({"translation": [3.0, 7.0, 1.0]})))
    assert validate_gltf_upload("g.glb", clean).media_type == "model/gltf-binary"
    info = gi.analyze(clean)
    assert info["bounds_min"][1] == pytest.approx(0.0, abs=1e-5) and info["size_units"][1] == pytest.approx(0.6, abs=1e-3)
    doc, _ = parse_glb(clean)
    assert [m["name"] for m in doc["materials"]] == ["base"] and len(doc["meshes"]) == 1 and doc["nodes"][0]["extras"]["imported_garment"] is True
    assert garments.validate_garment(clean, spec)["kind"] == "top"


def test_the_estimate_follows_the_shape_at_the_heights_of_the_kind_of_garment_even_with_few_rings():
    # a bell with only 8 rings (no ring near the measuring heights): narrow at the top, wide at the hem; the whole nearest ring is used, not a few of its points
    vertices = [(r * math.cos(2 * math.pi * s / 24), y * 0.1, r * math.sin(2 * math.pi * s / 24)) for y in range(8) for s in range(24) for r in [0.12 + (7 - y) * 0.02]]
    triangles = []
    for y in range(7):
        for s in range(24):
            a, b, c, d = y * 24 + s, y * 24 + (s + 1) % 24, (y + 1) * 24 + s, (y + 1) * 24 + (s + 1) % 24
            triangles += [(a, c, b), (b, c, d)]
    measures = gi.estimate_measurements(vertices, "skirt")
    assert measures["waist_cm"] < measures["hips_cm"] and measures["waist_cm"] == pytest.approx(2 * math.pi * 13.2, rel=0.12) and measures["hips_cm"] == pytest.approx(2 * math.pi * 17.2, rel=0.12)


def test_a_third_party_garment_without_confirmed_rights_is_refused_and_a_confirmed_one_is_not():
    with pytest.raises(garments.GarmentError, match="rights_confirmed"):
        convert(user_glb(), rights_confirmed=False)
    assert convert(user_glb(), rights_confirmed=True)[1]["source"]["rights_confirmed"] is True
    assert convert(user_glb(), rights_confirmed=False, third_party_asset=False)[1]["source"]["third_party_asset"] is False, "the person says it is their own design; the caller records who decided"


def test_the_result_cannot_be_fitted_to_a_body_and_says_so():
    clean, spec, report = convert(user_glb())
    with pytest.raises(garments.GarmentError, match="fit-ready"):
        garment_deform.deform_garment(clean, spec, {"height_cm": 170})
    assert "reference-size" in report["note"]


def test_a_jacket_needs_its_sleeve_length_and_an_unknown_kind_is_refused():
    with pytest.raises(gi.GarmentImportError) as exc:
        convert(user_glb(), kind="jacket")
    assert exc.value.code == "IMPORT_SLEEVE_REQUIRED"
    assert convert(user_glb(), kind="jacket", sleeve_cm=60)[1]["sizes"]["M"]["sleeve_cm"] == 60.0
    with pytest.raises(gi.GarmentImportError) as kind:
        convert(user_glb(), kind="hat")
    assert kind.value.code == "IMPORT_KIND"


@pytest.mark.parametrize("edit, code", [
    (lambda d: d["nodes"][0].update({"skin": 0}), "IMPORT_SKINNED"),
    (lambda d: d["meshes"][0]["primitives"][0].update({"targets": [{"POSITION": 0}]}), "IMPORT_SKINNED"),
    (lambda d: d["meshes"][0]["primitives"][0].update({"mode": 5}), "IMPORT_UNSUPPORTED"),
    (lambda d: d["accessors"][0].update({"normalized": True}), "IMPORT_UNSUPPORTED"),
    (lambda d: d["accessors"][0].update({"sparse": {}}), "IMPORT_UNSUPPORTED"),
    (lambda d: d["meshes"][0].update({"primitives": []}), "IMPORT_EMPTY")])
def test_what_cannot_be_imported_is_refused_with_a_reason(edit, code):
    with pytest.raises(gi.GarmentImportError) as exc:
        gi.analyze(user_glb(edit=edit))
    assert exc.value.code == code


def test_textures_are_dropped_and_said_so_and_a_huge_mesh_is_refused():
    def textured(doc):
        doc["images"] = [{"uri": "data:image/png;base64,AAAA"}]
        doc["textures"] = [{"source": 0}]
    assert gi.analyze(user_glb(edit=textured))["texture_dropped"] is True
    assert convert(user_glb(edit=textured))[2]["texture_dropped"] is True
    v, t = tube(levels=2, sides=3)
    big = user_glb(v, t * 1)
    doc, binary = parse_glb(big)
    doc["accessors"][1]["count"] = 3 * (gi.MAX_TRIANGLES + 1)
    doc["bufferViews"][1]["byteLength"] = 0
    with pytest.raises(Exception):
        gi.analyze(build_glb(doc, bytes(binary)))


def test_the_conversion_is_deterministic():
    a, b = convert(user_glb()), convert(user_glb())
    assert a[0] == b[0] and a[1] == b[1]
