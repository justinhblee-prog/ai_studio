"""R-ENGINE-09b: the sample garments COVER the body they are made for. The pass line is the render check of R-ENGINE-11: front and back ``visible_share_min >= 0.98``
(before this step it was 0.46-0.95 for all ten samples: the body's bust, thighs and arms showed through)."""
import pytest

from app import base_models, garments, render3d_scene, render3d_soft, render_qc
from app.garment_deform import deform_garment
from app.glb_tools import build_glb, parse_glb

SIZES = {"small": {"height_cm": 155, "chest_cm": 80, "waist_cm": 64, "hips_cm": 88},
         "medium": {"height_cm": 170, "chest_cm": 92, "waist_cm": 76, "hips_cm": 98},
         "large": {"height_cm": 185, "chest_cm": 108, "waist_cm": 92, "hips_cm": 112}}


@pytest.mark.parametrize("size", SIZES)
@pytest.mark.parametrize("sex", base_models.SEXES)
@pytest.mark.parametrize("kind", garments.KINDS)
def test_every_sample_covers_the_body_at_three_body_sizes(kind, sex, size):
    measurements = SIZES[size]
    body, layers, fits = render3d_scene.build_layers(sex, measurements, [kind])
    report = render_qc.check_cuts(body, layers, (0, 180), penetrations={f["kind"]: f["penetrations"] for f in fits}, body_without_arms=render3d_scene.body_without_arms(sex, measurements))
    garment = report["garments"][0]
    assert garment["visible_share_min"] >= render_qc.MIN_VISIBLE_SHARE, garment
    assert garment["passed"] is True and garment["penetration_points"] == 0 and garment["colour_distance_max"] <= render_qc.MAX_COLOUR_DISTANCE


@pytest.mark.parametrize("sex", base_models.SEXES)
def test_the_arms_are_left_out_only_for_garments_without_sleeves_and_the_number_with_arms_is_kept(sex):
    measurements = SIZES["medium"]
    body, top_layers, _ = render3d_scene.build_layers(sex, measurements, ["top"])
    _, jacket_layers, _ = render3d_scene.build_layers(sex, measurements, ["jacket"])
    bare = render3d_scene.body_without_arms(sex, measurements)
    top = render_qc.check_cuts(body, top_layers, (0,), body_without_arms=bare)["garments"][0]
    jacket = render_qc.check_cuts(body, jacket_layers, (0,), body_without_arms=bare)["garments"][0]
    assert top["occluder"] == "body_without_arms" and jacket["occluder"] == "body", "a jacket has its own sleeves, so it is judged against the whole body"
    view = top["views"][0]
    assert view["visible_share"] > view["visible_share_incl_arms"], "the hanging arm overlaps the garment's side edge in front view"
    assert 0.9 < view["visible_share_incl_arms"] < 1.0
    assert render_qc.check_cuts(body, top_layers, (0,))["garments"][0]["occluder"] == "body", "without an arm-less body given, nothing is relaxed"


@pytest.mark.parametrize("kind", garments.KINDS)
def test_garment_faces_point_away_from_their_own_axis_including_a_sleeves_inner_side(kind):
    """The normals decide which faces are back faces. A sleeve's inner side faces the body, so 'away from the body's axis' was wrong for it and the faces were dropped."""
    glb, _ = garments.build_sample_garment(kind, "female")
    doc, binary = parse_glb(glb)
    for primitive in doc["meshes"][0]["primitives"]:
        single = dict(doc, meshes=[{"primitives": [primitive], "name": "p"}])
        tris = render3d_soft.triangles_of(build_glb(single, bytes(binary)), axis_outward=True)
        cx = sum(c[0] for t in tris for c in t[0]) / (3 * len(tris))
        cz = sum(c[2] for t in tris for c in t[0]) / (3 * len(tris))
        outward = sum(1 for t in tris if t[1][0][0] * (sum(c[0] for c in t[0]) / 3 - cx) + t[1][0][2] * (sum(c[2] for c in t[0]) / 3 - cz) >= 0)
        # measured against the tube's MEAN axis, so a slanted sleeve scores a little under 1 (its ends sit off that axis); the old rule (away from the BODY's axis) left about 75 per cent here
        assert outward / len(tris) > 0.9, (kind, primitive["extras"]["part"], outward / len(tris))


def test_the_garment_is_made_from_the_bodys_own_sections():
    """Same numbers, so they cannot drift apart: a top's ring at the chest is the body's chest section plus ease."""
    p = base_models.PRESETS["female"]
    rows = base_models.body_profiles(p, True)["torso"]
    chest_y = 0.70 * p["height"]
    _, a, b, z = min(rows, key=lambda r: abs(r[0] - chest_y))
    glb, spec = garments.build_sample_garment("top", "female", ease_cm=4.0)
    assert spec["sizes"]["M"]["chest_cm"] == garments._ring_cm(a + 0.04 / (2 * 3.141592653589793), b + 0.04 / (2 * 3.141592653589793))
    assert abs(z) > 0.005, "and that section carries the bust's forward offset, which a centred ring could not"
