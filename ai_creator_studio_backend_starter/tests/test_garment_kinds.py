"""R-ENGINE-09: skirt, dress and jacket samples next to top and bottom (= trousers), each fitted to three body sizes with no vertex inside the body."""
import itertools
import struct

import pytest

from app import base_models, garment_deform, garments
from app.assets.validation import validate_gltf_upload
from app.garment_deform import deform_garment
from app.garments import GarmentError, build_sample_garment, validate_garment
from app.glb_tools import inspect_glb, parse_glb

NEW_KINDS = ("skirt", "dress", "jacket")
EXPECTED_PARTS = {"top": ["torso"], "bottom": ["leg_l", "leg_r", "torso"], "skirt": ["skirt"], "dress": ["skirt", "torso"], "jacket": ["arm_l", "arm_r", "torso"]}
# three body sizes: small / medium / large (typed measurements, all four given)
SIZES = {"small": {"height_cm": 155, "chest_cm": 80, "waist_cm": 64, "hips_cm": 88},
         "medium": {"height_cm": 170, "chest_cm": 92, "waist_cm": 76, "hips_cm": 98},
         "large": {"height_cm": 185, "chest_cm": 108, "waist_cm": 92, "hips_cm": 112}}


def _parts(glb: bytes) -> dict[str, list[tuple[float, float, float]]]:
    doc, binary = parse_glb(glb)
    out: dict[str, list[tuple[float, float, float]]] = {}
    for prim in doc["meshes"][0]["primitives"]:
        acc = doc["accessors"][prim["attributes"]["POSITION"]]
        view = doc["bufferViews"][acc["bufferView"]]
        flat = struct.unpack_from(f"<{acc['count'] * 3}f", binary, view["byteOffset"])
        out[prim["extras"]["part"]] = [tuple(flat[i:i + 3]) for i in range(0, len(flat), 3)]
    return out


def test_the_kinds_are_the_five_and_trousers_are_the_existing_bottom():
    assert garments.KINDS == ("top", "bottom", "skirt", "dress", "jacket")


@pytest.mark.parametrize("kind", garments.KINDS)
@pytest.mark.parametrize("sex", base_models.SEXES)
def test_each_sample_is_a_valid_garment_with_its_parts_and_a_size_table_that_grows(kind, sex):
    glb, spec = build_sample_garment(kind, sex)
    assert validate_gltf_upload(f"{kind}.glb", glb).media_type == "model/gltf-binary"
    validate_garment(glb, spec)
    assert sorted(_parts(glb)) == EXPECTED_PARTS[kind]
    assert set(spec["sizes"]) == {"S", "M", "L"} and spec["kind"] == kind
    for key in garments.REQUIRED_MEASURES[kind]:
        if key != "length_cm":
            assert spec["sizes"]["S"][key] < spec["sizes"]["M"][key] < spec["sizes"]["L"][key], key
    assert inspect_glb(glb)["triangles"] > 0 and build_sample_garment(kind, sex)[0] == glb, "deterministic"


@pytest.mark.parametrize("kind", NEW_KINDS)
@pytest.mark.parametrize("sex", base_models.SEXES)
def test_each_new_kind_fits_three_body_sizes_with_nothing_inside_the_body(kind, sex):
    glb, spec = build_sample_garment(kind, sex)
    widths = []
    for name, measurements in SIZES.items():
        fitted, report = deform_garment(glb, spec, measurements)
        assert report["penetrations"] == 0 and report["vertices"] > 0, name
        widths.append((inspect_glb(fitted)["size"][0], inspect_glb(fitted)["size"][1]))
    assert widths[0][1] < widths[1][1] < widths[2][1], "a taller body gets a longer garment"
    assert widths[0][0] < widths[1][0] < widths[2][0], "a bigger body gets a wider garment"


@pytest.mark.parametrize("kind", ("skirt", "dress"))
@pytest.mark.parametrize("sex", base_models.SEXES)
def test_a_skirt_never_cuts_through_the_legs_over_a_grid_of_bodies(kind, sex):
    glb, spec = build_sample_garment(kind, sex)
    grid = itertools.product((None, 140, 170, 215), (None, 70, 130), (None, 60, 120), (None, 75, 100, 165))
    for h, c, w, hp in grid:
        m = {k: v for k, v in (("height_cm", h), ("chest_cm", c), ("waist_cm", w), ("hips_cm", hp)) if v is not None}
        fitted, _ = deform_garment(glb, spec, m or None)
        body = garment_deform._body(sex, m or None)
        legs = base_models.body_profiles(body, sex == "female")["leg"]          # (y, centre x, half-width, half-depth, z offset): the body mesh's own leg sections
        for x, y, z in _parts(fitted)["skirt"]:
            if y > 0.52 * body["height"]:
                continue
            cx, a, b, zc = garment_deform._lerp_profile(legs, y)
            for side in (-1, 1):
                assert ((x - side * cx) / a) ** 2 + ((z - zc) / b) ** 2 >= 0.999, (m, y)


@pytest.mark.parametrize("sex", base_models.SEXES)
def test_the_dress_top_and_skirt_meet_at_the_waist_after_every_fit(sex):
    glb, spec = build_sample_garment("dress", sex)
    for m in (None, SIZES["small"], SIZES["large"], {"waist_cm": 55}, {"hips_cm": 160}):
        parts = _parts(deform_garment(glb, spec, m)[0])
        waist_y = max(v[1] for v in parts["skirt"])
        top = sorted(v for v in parts["torso"] if abs(v[1] - waist_y) < 1e-4)
        low = sorted(v for v in parts["skirt"] if abs(v[1] - waist_y) < 1e-4)
        assert top and len(top) == len(low) and all(abs(a - b) < 1e-4 for p, q in zip(top, low) for a, b in zip(p, q)), "no gap or step at the waist seam"


@pytest.mark.parametrize("sex", base_models.SEXES)
def test_the_jacket_has_two_sleeves_that_follow_the_arms(sex):
    glb, spec = build_sample_garment("jacket", sex)
    plain = _parts(glb)
    assert all(v[0] < 0 for v in plain["arm_l"]) and all(v[0] > 0 for v in plain["arm_r"]), "one sleeve per side"
    assert spec["sizes"]["M"]["sleeve_cm"] > 40
    narrow = _parts(deform_garment(glb, spec, {"height_cm": 150})[0])["arm_r"]
    tall = _parts(deform_garment(glb, spec, {"height_cm": 200})[0])["arm_r"]
    assert max(v[0] for v in tall) > max(v[0] for v in narrow), "the sleeve moves out with the shoulder width of a taller body"
    assert min(v[1] for v in tall) > min(v[1] for v in narrow), "and its cuff sits higher in absolute terms because the whole body is taller"
    wide = inspect_glb(deform_garment(glb, spec, SIZES["large"])[0])["size"][0]
    assert wide > inspect_glb(build_sample_garment("top", sex)[0])["size"][0], "with its sleeves the jacket is wider than a t-shirt"


def test_a_jacket_chart_without_a_sleeve_length_and_a_skirt_without_hips_are_refused():
    glb, spec = build_sample_garment("jacket", "male")
    del spec["sizes"]["M"]["sleeve_cm"]
    with pytest.raises(GarmentError):
        validate_garment(glb, spec)
    glb, spec = build_sample_garment("skirt", "male")
    del spec["sizes"]["S"]["hips_cm"]
    with pytest.raises(GarmentError):
        validate_garment(glb, spec)


@pytest.mark.parametrize("kind", NEW_KINDS)
def test_the_own3d_mock_accepts_every_new_kind(kind):
    import asyncio
    from app.providers.own_mock import OwnMockProvider
    provider = OwnMockProvider()
    loop = asyncio.new_event_loop()
    started = loop.run_until_complete(provider.start({"sex": "female", "garment_kind": kind, "measurements": SIZES["large"]}))
    done = loop.run_until_complete(provider.status(started["request_id"]))
    assert done["status"] == "succeeded" and done["output"]["fit"]["penetrations"] == 0 and provider.result_glb(started["request_id"])
