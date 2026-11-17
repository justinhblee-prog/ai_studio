"""R-ENGINE-06: the local fit checker passes a correct fitted .glb and FAILS the right check for deliberately damaged ones (so a pass means something)."""
import struct

import pytest

from app.fit_check import FitCheckError, check_fit
from app.garment_fit import GARMENT_COLOUR, build_fitted_glb
from app.glb_tools import build_glb, parse_glb
from app.mannequin import Measurements, SizeChart

M = Measurements(height_cm=170, chest_cm=92, waist_cm=76, hips_cm=98)
CHART = SizeChart(sizes={"S": {"chest": 94, "waist": 80, "hips": 100}, "M": {"chest": 100, "waist": 86, "hips": 106}, "L": {"chest": 108, "waist": 94, "hips": 114}})


def good(size="M"):
    return build_fitted_glb(M, CHART, size)[0]


def edit_shell(glb, move):
    """The same file with every garment vertex passed through move((x, y, z)) -> (x, y, z): a way to make a known-bad result."""
    doc, binary = parse_glb(glb)
    prim = doc["meshes"][1]["primitives"][0]
    acc = doc["accessors"][prim["attributes"]["POSITION"]]
    view = doc["bufferViews"][acc["bufferView"]]
    start = view.get("byteOffset", 0)
    flat = list(struct.unpack_from(f"<{acc['count'] * 3}f", binary, start))
    for i in range(0, len(flat), 3):
        flat[i:i + 3] = move(tuple(flat[i:i + 3]))
    data = bytearray(binary)
    struct.pack_into(f"<{len(flat)}f", data, start, *flat)
    return build_glb(doc, bytes(data))


def with_colour(glb, rgba):
    doc, binary = parse_glb(glb)
    doc["materials"][1]["pbrMetallicRoughness"]["baseColorFactor"] = list(rgba)
    return build_glb(doc, binary)


def test_every_size_of_a_correct_fit_passes_all_four_checks_with_numbers():
    for size in CHART.sizes:                                    # S is "cannot_fit" in the engine's own report but its geometry is still pushed clear of the body
        report = check_fit(good(size), expected_colour=GARMENT_COLOUR)
        assert report["passed"] is True, (size, report)
        checks = report["checks"]
        assert checks["penetration"]["points_inside"] == 0 and checks["penetration"]["points_checked"] > 1000
        assert checks["clearance"]["min_clearance_cm"] >= 0.2
        assert 0.25 <= checks["length"]["share_of_body_height"] <= 0.45
        assert checks["colour"]["checked"] is True and checks["colour"]["max_channel_error"] == pytest.approx(0, abs=0.01)
    assert "not a review" in report["scope"]


def test_a_garment_shrunk_into_the_body_fails_penetration_and_clearance():
    report = check_fit(edit_shell(good(), lambda p: (p[0] * 0.8, p[1], p[2] * 0.8)))
    assert report["passed"] is False
    assert report["checks"]["penetration"]["passed"] is False and report["checks"]["penetration"]["points_inside"] > 100
    assert report["checks"]["clearance"]["passed"] is False and report["checks"]["clearance"]["min_clearance_cm"] < 0
    assert report["checks"]["length"]["passed"] is True, "only the damaged things fail"


def test_a_garment_that_nearly_touches_the_skin_fails_only_the_clearance():
    report = check_fit(edit_shell(good("S"), lambda p: (p[0] * 0.98, p[1], p[2] * 0.98)))      # S is the snug size: its shell sits at the minimum gap (about 0.4 cm), so a 2% shrink leaves about 0.13 cm
    assert report["checks"]["penetration"]["passed"] is True, "still outside the body"
    assert report["checks"]["clearance"]["passed"] is False and 0 < report["checks"]["clearance"]["min_clearance_cm"] < 0.2
    assert report["passed"] is False


def test_a_garment_that_is_too_short_or_too_long_fails_the_length_check_only():
    short = check_fit(edit_shell(good(), lambda p: (p[0], 0.5 * 1.70 + (p[1] - 0.5 * 1.70) * 0.4, p[2])))
    assert short["checks"]["length"]["passed"] is False and short["checks"]["length"]["share_of_body_height"] < 0.25
    long = check_fit(edit_shell(good(), lambda p: (p[0], 0.5 * 1.70 + (p[1] - 0.5 * 1.70) * 2.0, p[2])))
    assert long["checks"]["length"]["passed"] is False and long["checks"]["length"]["share_of_body_height"] > 0.45
    assert short["checks"]["colour"]["passed"] is None and long["checks"]["colour"]["checked"] is False, "an unrequested colour is not judged"


def test_the_wrong_colour_fails_only_when_a_colour_was_asked_for():
    wrong = with_colour(good(), (0.9, 0.1, 0.1, 1.0))
    asked = check_fit(wrong, expected_colour=GARMENT_COLOUR)
    assert asked["passed"] is False and asked["checks"]["colour"]["passed"] is False and asked["checks"]["colour"]["max_channel_error"] > 0.5
    assert asked["checks"]["penetration"]["passed"] is True and asked["checks"]["clearance"]["passed"] is True
    assert check_fit(wrong)["passed"] is True, "geometry is fine and no colour was asked for"


def test_files_that_are_not_a_fitted_pair_are_refused_with_a_clear_error():
    doc, binary = parse_glb(good())
    doc["nodes"][1]["name"] = "something_else"
    with pytest.raises(FitCheckError):
        check_fit(build_glb(doc, binary))
    with pytest.raises(Exception):
        check_fit(b"not a glb")
