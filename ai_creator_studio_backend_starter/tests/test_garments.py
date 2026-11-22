"""R-ENGINE-02: garment data spec (garment.v1), validator and the code-generated sample garments."""
import copy

import pytest

from app import base_models, garments
from app.assets.validation import validate_gltf_upload
from app.garments import GarmentError, build_sample_garment, validate_garment, validate_glb, validate_spec
from app.glb_tools import build_glb, inspect_glb, parse_glb


def _good(kind="top", sex="male"):
    return build_sample_garment(kind, sex)


@pytest.mark.parametrize("kind", garments.KINDS)
@pytest.mark.parametrize("sex", base_models.SEXES)
def test_every_sample_is_a_valid_garment_and_a_valid_upload(kind, sex):
    glb, spec = _good(kind, sex)
    report = validate_garment(glb, spec)
    assert report["kind"] == kind and report["sizes"] == ["L", "M", "S"] and 0 < report["triangles"] < 3000
    assert validate_gltf_upload(f"{kind}.glb", glb).media_type == "model/gltf-binary"
    doc, _ = parse_glb(glb)
    assert [m["name"] for m in doc["materials"]] == ["base"] and doc["nodes"][0]["extras"]["generated_by_code"] is True


def test_the_samples_are_deterministic_and_the_chart_matches_the_mesh():
    a, spec = _good("bottom", "female")
    b, spec2 = _good("bottom", "female")
    assert a == b and spec == spec2
    assert abs(inspect_glb(a)["size"][1] * 100 - spec["sizes"]["M"]["length_cm"]) <= 0.1
    s, m, l = (spec["sizes"][x] for x in "SML")
    assert s["waist_cm"] < m["waist_cm"] < l["waist_cm"] and s["length_cm"] == m["length_cm"] == l["length_cm"]


def test_more_ease_gives_a_wider_garment_and_bad_ease_is_refused():
    tight, _ = build_sample_garment("top", "male", ease_cm=0)
    loose, spec = build_sample_garment("top", "male", ease_cm=12)
    assert inspect_glb(loose)["size"][0] > inspect_glb(tight)["size"][0]
    assert spec["sizes"]["M"]["chest_cm"] > build_sample_garment("top", "male", ease_cm=0)[1]["sizes"]["M"]["chest_cm"]
    for bad in (-1, 21, "4", True, None):
        with pytest.raises(ValueError):
            build_sample_garment("top", "male", ease_cm=bad)
    with pytest.raises(ValueError):
        build_sample_garment("hat", "male")
    with pytest.raises(ValueError):
        build_sample_garment("top", "robot")


def _problems(spec) -> str:
    with pytest.raises(GarmentError) as exc:
        validate_spec(spec)
    return " | ".join(exc.value.problems)


def test_spec_rules_reject_each_kind_of_mistake_and_report_all_of_them_together():
    _, spec = _good("top")
    validate_spec(spec)
    for mutate, expect in [
        (lambda s: s.update(schema="garment.v0"), "schema"),
        (lambda s: s.update(id="Bad Id!"), "id must"),
        (lambda s: s.update(kind="hat"), "kind must"),
        (lambda s: s.update(reference_size="XL"), "reference_size"),
        (lambda s: s["sizes"]["M"].pop("chest_cm"), "missing chest_cm"),
        (lambda s: s["sizes"]["M"].update(chest_cm=5), "chest_cm must be a number"),
        (lambda s: s["sizes"]["M"].update(chest_cm=True), "chest_cm must be a number"),
        (lambda s: s["sizes"]["M"].update(hips_cm=90), "unknown measurement"),
        (lambda s: s["sizes"].update({f"S{i}": dict(s["sizes"]["M"]) for i in range(9)}), "sizes must be"),
        (lambda s: s["sizes"].update({"bad label!!": dict(s["sizes"]["M"])}), "not allowed"),
        (lambda s: s["source"].pop("provenance"), "provenance"),
        (lambda s: s["source"].update(third_party_asset="no"), "true or false"),
    ]:
        broken = copy.deepcopy(spec)
        mutate(broken)
        assert expect in _problems(broken), expect
    many = copy.deepcopy(spec)
    many.update(schema="x", kind="hat")
    assert _problems(many).count("|") >= 1, "several problems come back together"
    assert "object" in _problems([1, 2])


def test_a_third_party_asset_needs_confirmed_rights():
    _, spec = _good("top")
    spec["source"].update(third_party_asset=True, rights_confirmed=False)
    assert "rights_confirmed" in _problems(spec)
    spec["source"]["rights_confirmed"] = True
    validate_spec(spec)
    spec["source"].pop("rights_confirmed")
    assert "rights_confirmed" in _problems(spec)


def _glb_with(materials=None, meshes=1, triangles_extra=0):
    glb, _ = _good("top")
    doc, binary = parse_glb(glb)
    if materials is not None:
        doc["materials"] = [{"name": n, "pbrMetallicRoughness": {"baseColorFactor": [1, 1, 1, 1]}} for n in materials]
    if meshes == 2:
        doc["meshes"].append(copy.deepcopy(doc["meshes"][0]))
    return build_glb(doc, binary)


def test_glb_rules_one_mesh_a_base_material_only_known_names():
    validate_glb(_glb_with())
    for glb, expect in [(_glb_with(materials=["skin"]), "'base'"), (_glb_with(materials=["base", "shiny"]), "unknown material"), (_glb_with(meshes=2), "exactly one mesh")]:
        with pytest.raises(GarmentError) as exc:
            validate_glb(glb)
        assert expect in " ".join(exc.value.problems)
    with pytest.raises(GarmentError):
        validate_glb(b"not a glb at all")


def test_the_garment_check_catches_a_chart_that_disagrees_with_the_mesh_and_reports_glb_and_spec_problems_together():
    glb, spec = _good("top")
    spec["sizes"]["M"]["length_cm"] = 80.0
    with pytest.raises(GarmentError) as exc:
        validate_garment(glb, spec)
    assert "does not match the mesh height" in " ".join(exc.value.problems)
    spec["kind"] = "hat"
    with pytest.raises(GarmentError) as exc:
        validate_garment(b"junk", spec)
    joined = " ".join(exc.value.problems)
    assert "kind must" in joined and "glb:" in joined
