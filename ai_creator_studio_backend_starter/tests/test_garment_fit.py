"""R-ENGINE-03: fit a garment.v1 to typed body measurements by mesh deformation (profile-ratio.v1)."""
import copy
import itertools
import struct

import pytest

from app import base_models, garment_fit, garments
from app.garment_fit import fit_garment
from app.garments import GarmentError, build_sample_garment, validate_garment
from app.glb_tools import build_glb, inspect_glb, parse_glb


def _positions(glb: bytes) -> list[float]:
    doc, binary = parse_glb(glb)
    out: list[float] = []
    for prim in doc["meshes"][0]["primitives"]:
        acc = doc["accessors"][prim["attributes"]["POSITION"]]
        view = doc["bufferViews"][acc["bufferView"]]
        out += struct.unpack_from(f"<{acc['count'] * 3}f", binary, view["byteOffset"])
    return out


@pytest.mark.parametrize("kind", garments.KINDS)
@pytest.mark.parametrize("sex", base_models.SEXES)
def test_no_measurements_means_no_change(kind, sex):
    glb, spec = build_sample_garment(kind, sex)
    fitted, report = fit_garment(glb, spec)
    assert all(abs(a - b) < 1e-5 for a, b in zip(_positions(glb), _positions(fitted)))
    assert report["penetrations"] == 0 and report["vertices"] > 0 and report["method"] == "profile-ratio.v1"
    assert parse_glb(fitted)[0]["nodes"][0]["extras"]["fit_method"] == "profile-ratio.v1"


def test_a_taller_body_makes_a_taller_garment_in_proportion():
    glb, spec = build_sample_garment("top", "male")
    base_h = inspect_glb(glb)["size"][1]
    fitted, report = fit_garment(glb, spec, {"height_cm": 195})
    ratio = 195 / (base_models.PRESETS["male"]["height"] * 100)
    assert inspect_glb(fitted)["size"][1] == pytest.approx(base_h * ratio, abs=0.002)
    assert report["height_cm"] == pytest.approx(base_h * ratio * 100, abs=0.2)


def test_a_wider_chest_widens_the_garment_and_the_ease_stays():
    glb, spec = build_sample_garment("top", "female")
    narrow, _ = fit_garment(glb, spec, {"chest_cm": 70})
    wide, _ = fit_garment(glb, spec, {"chest_cm": 120})
    assert inspect_glb(wide)["size"][0] > inspect_glb(narrow)["size"][0]
    # the garment is never inside the body: its chest ring is wider than the body's chest ring at the same typed size
    body = base_models._fit_measurements(base_models.PRESETS["female"], {"chest_cm": 120})
    assert inspect_glb(wide)["size"][0] / 2 > body["chest"][0]


@pytest.mark.parametrize("kind", garments.KINDS)
@pytest.mark.parametrize("sex", base_models.SEXES)
def test_no_vertex_ever_ends_up_inside_the_body_over_a_grid_of_measurements(kind, sex):
    glb, spec = build_sample_garment(kind, sex)
    grid = itertools.product((None, 140, 165, 190, 215), (None, 70, 100, 140), (None, 60, 90, 130), (None, 80, 110, 160))
    for h, c, w, hp in grid:
        m = {k: v for k, v in (("height_cm", h), ("chest_cm", c), ("waist_cm", w), ("hips_cm", hp)) if v is not None}
        _, report = fit_garment(glb, spec, m or None)
        assert report["penetrations"] == 0


def test_a_bottom_follows_the_legs_when_the_body_is_taller_and_wider():
    glb, spec = build_sample_garment("bottom", "male")
    fitted, report = fit_garment(glb, spec, {"height_cm": 200, "hips_cm": 120})
    assert inspect_glb(fitted)["size"][1] > inspect_glb(glb)["size"][1] * 1.08
    assert inspect_glb(fitted)["size"][0] > inspect_glb(glb)["size"][0]
    assert report["vertices"] == len(_positions(fitted)) // 3


def test_the_fit_is_deterministic_and_the_output_is_still_a_valid_garment():
    glb, spec = build_sample_garment("top", "male")
    m = {"height_cm": 185, "chest_cm": 105, "waist_cm": 90}
    a, ra = fit_garment(glb, spec, m)
    b, rb = fit_garment(glb, spec, m)
    assert a == b and ra == rb
    fitted_spec = copy.deepcopy(spec)
    fitted_spec["sizes"]["M"]["length_cm"] = ra["height_cm"]
    validate_garment(a, fitted_spec)


def test_bad_measurements_and_unfit_ready_garments_are_refused():
    glb, spec = build_sample_garment("top", "male")
    for bad in ({"height_cm": 100}, {"chest_cm": 300}, {"waist_cm": "wide"}, {"sleeve_cm": 60}, {"hips_cm": True}):
        with pytest.raises(ValueError):
            fit_garment(glb, spec, bad)
    no_fit = copy.deepcopy(spec)
    no_fit.pop("fit")
    with pytest.raises(GarmentError) as exc:
        fit_garment(glb, no_fit)
    assert "not fit-ready" in " ".join(exc.value.problems)
    doc, binary = parse_glb(glb)
    doc["meshes"][0]["primitives"][0].pop("extras")
    with pytest.raises(GarmentError) as exc:
        fit_garment(build_glb(doc, binary), spec)
    assert "extras.part" in " ".join(exc.value.problems)
    broken = copy.deepcopy(spec)
    broken["fit"] = {"method": "other", "reference_sex": "male"}
    with pytest.raises(GarmentError):
        fit_garment(glb, broken)
    with pytest.raises(GarmentError):
        fit_garment(b"junk", spec)


def test_the_helpers_interpolate_and_clamp():
    stops = [(0.0, 1.0, 10.0), (1.0, 3.0, 20.0)]
    assert garment_fit._lerp_profile(stops, -5) == (1.0, 10.0)
    assert garment_fit._lerp_profile(stops, 5) == (3.0, 20.0)
    assert garment_fit._lerp_profile(stops, 0.5) == pytest.approx((2.0, 15.0), abs=1e-9) or garment_fit._lerp_profile(stops, 0.5) == (2.0, 15.0)
    assert garment_fit._inside(0.0, 0.0, 1.0, 1.0) and not garment_fit._inside(1.0, 0.0, 1.0, 1.0) and not garment_fit._inside(2.0, 0.0, 1.0, 1.0)
