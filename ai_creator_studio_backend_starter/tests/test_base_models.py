"""Lane 2/5: the two generated base human models (stylised, low-poly, three recolourable materials)."""
import pytest

from app.assets.validation import validate_gltf_upload
from app.base_models import BOTTOM_STYLES, SEXES, TOP_STYLES, build_base_model
from app.glb_tools import inspect_glb, parse_glb


def materials(glb):
    doc, _ = parse_glb(glb)
    return {m["name"]: m for m in doc["materials"]}, doc


def triangles_of(glb, material):
    doc, _ = parse_glb(glb)
    index = next(i for i, m in enumerate(doc["materials"]) if m["name"] == material)
    prim = next(p for p in doc["meshes"][0]["primitives"] if p["material"] == index)
    return doc["accessors"][prim["indices"]]["count"] // 3


@pytest.mark.parametrize("sex", SEXES)
def test_each_model_is_a_valid_low_poly_glb_with_the_right_height_and_no_external_files(sex):
    glb = build_base_model(sex)
    assert validate_gltf_upload("m.glb", glb).media_type == "model/gltf-binary"
    info = inspect_glb(glb)
    assert info["has_external_uri"] is False and info["images"] == 0 and info["textures"] == 0
    assert 800 < info["triangles"] < 5000, info["triangles"]
    assert info["size"][1] == pytest.approx({"male": 1.78, "female": 1.66}[sex] + 0.0, abs=0.12), "about the preset height (head sphere included)"
    assert build_base_model(sex) == glb, "deterministic"


def test_the_three_materials_carry_the_requested_colours_so_clothes_can_be_recoloured():
    mats, doc = materials(build_base_model("female", skin=(10, 20, 30), top=(255, 0, 0), bottom=(0, 255, 0)))
    assert set(mats) == {"skin", "top", "bottom"}
    assert mats["top"]["pbrMetallicRoughness"]["baseColorFactor"] == [1.0, 0.0, 0.0, 1.0]
    assert mats["bottom"]["pbrMetallicRoughness"]["baseColorFactor"] == [0.0, 1.0, 0.0, 1.0]
    assert mats["skin"]["pbrMetallicRoughness"]["baseColorFactor"][:3] == [10 / 255, 20 / 255, 30 / 255]
    assert len(doc["meshes"][0]["primitives"]) == 3


def test_style_switches_change_what_each_material_covers():
    tank, tee, long_ = (build_base_model("male", top_style=s) for s in ("tank", "tshirt", "longsleeve"))
    assert triangles_of(tank, "top") < triangles_of(tee, "top") < triangles_of(long_, "top")
    assert triangles_of(tank, "skin") > triangles_of(tee, "skin") > triangles_of(long_, "skin"), "the skin shows where the clothes stop"
    shorts, pants = build_base_model("male", bottom_style="shorts"), build_base_model("male", bottom_style="pants")
    assert triangles_of(shorts, "bottom") < triangles_of(pants, "bottom") and triangles_of(shorts, "skin") > triangles_of(pants, "skin")
    assert len({build_base_model("male", top_style=t, bottom_style=b) for t in TOP_STYLES for b in BOTTOM_STYLES}) == 6, "every style pair is a different file"


def test_the_two_presets_differ_in_height_and_in_the_shoulder_to_hip_proportion():
    male, female = inspect_glb(build_base_model("male")), inspect_glb(build_base_model("female"))
    assert male["size"][1] > female["size"][1]
    assert male["size"][0] > female["size"][0], "the figure with the wider shoulder preset is wider overall (arms hang at the shoulder)"
    assert build_base_model("male") != build_base_model("female")


def test_the_file_says_it_is_generated_and_not_a_person():
    doc, _ = parse_glb(build_base_model("male"))
    extras = doc["nodes"][0]["extras"]
    assert extras["generated_by_code"] is True and extras["is_scan"] is False and extras["is_a_real_person"] is False and extras["has_face_detail"] is False
    assert "no third-party asset" in extras["licence"]


@pytest.mark.parametrize("bad", [dict(sex="robot"), dict(top_style="cape"), dict(bottom_style="skirt"), dict(top=(1, 2)), dict(top=(1, 2, 300)), dict(skin=(1, 2, True)), dict(bottom="red")])
def test_bad_input_is_refused(bad):
    with pytest.raises(ValueError):
        build_base_model(**bad)
