"""R-ENGINE-11: the render-based garment check ("render-cuts.v1") sees what it should see: a clean fit passes, a body poking through fails, a wrong colour fails, and nothing is invented."""
import math

import pytest

from app import render3d_scene, render_qc
from app.render3d_soft import Triangle

GARMENT = (60, 90, 160)
M = {"height_cm": 170, "chest_cm": 92, "waist_cm": 76, "hips_cm": 98}


def cylinder(radius: float, y0: float, y1: float, sides: int = 24) -> list[Triangle]:
    """A closed-looking tube around the vertical axis, outward normals (the renderer's own input type)."""
    tris: list[Triangle] = []
    for i in range(sides):
        a0, a1 = 2 * math.pi * i / sides, 2 * math.pi * (i + 1) / sides
        p = [(radius * math.sin(a), y, radius * math.cos(a)) for a in (a0, a1) for y in (y0, y1)]
        n = [(math.sin(a), 0.0, math.cos(a)) for a in (a0, a1) for _ in (0, 1)]
        tris.append(((p[0], p[1], p[2]), (n[0], n[1], n[2]), GARMENT))
        tris.append(((p[1], p[3], p[2]), (n[1], n[3], n[2]), GARMENT))
    return tris


def scene(body_radius: float, garment_radius: float, garment_colour=GARMENT):
    body = cylinder(body_radius, 0.0, 1.7)
    shell = [(c, n, garment_colour) for c, n, _ in cylinder(garment_radius, 0.6, 1.2)]
    return body, [("top", shell, GARMENT)]


def report(body_radius, garment_radius, garment_colour=GARMENT, angles=(0, 180)):
    body, layers = scene(body_radius, garment_radius, garment_colour)
    layers = [(kind, [(c, n, garment_colour) for c, n, _ in tris], GARMENT) for kind, tris, _ in layers]
    return render_qc.check_cuts(body, layers, angles, penetrations={"top": 0})


def test_a_garment_that_stands_clear_of_the_body_passes_with_full_visibility():
    r = report(0.15, 0.19)
    g = r["garments"][0]
    assert g["visible_share_min"] == 1.0 and g["colour_distance_max"] <= render_qc.MAX_COLOUR_DISTANCE and g["penetration_points"] == 0 and g["passed"] is True and r["passed"] is True
    assert r["method"] == "render-cuts.v1" and r["thresholds"]["source"] == "proposal"


def test_a_body_that_pokes_through_the_garment_is_caught_by_the_silhouette_check():
    g = report(0.22, 0.19)["garments"][0]
    assert g["visible_share_min"] < 0.5 and g["passed"] is False
    middle = report(0.19, 0.19)["garments"][0]["visible_share_min"]
    assert 0.0 <= middle <= 1.0


def test_a_wrong_colour_is_caught_and_the_light_does_not_matter():
    assert report(0.15, 0.19, garment_colour=(200, 60, 80))["garments"][0]["passed"] is False
    assert report(0.15, 0.19, garment_colour=(30, 45, 80))["garments"][0]["colour_distance_max"] <= render_qc.MAX_COLOUR_DISTANCE, "half as bright, same colour"


def test_a_fitting_report_with_penetrations_fails_the_check_even_when_the_picture_looks_fine():
    body, layers = scene(0.15, 0.19)
    r = render_qc.check_cuts(body, layers, (0,), penetrations={"top": 3})
    assert r["garments"][0]["penetration_points"] == 3 and r["garments"][0]["passed"] is False


def test_nothing_is_invented_unknown_stays_none():
    body, layers = scene(0.15, 0.19)
    unknown = render_qc.check_cuts(body, layers, (0, 180))                      # no fitting report given
    assert unknown["garments"][0]["penetration_points"] is None and unknown["garments"][0]["passed"] is True, "the checks that CAN be judged decide"
    assert render_qc.check_cuts(body, [], (0,))["passed"] is None and render_qc.check_cuts(body, [], (0,))["garments"] == []
    assert unknown["not_judged"] == {"logo": None, "text": None, "pattern": None, "hands": None, "length": None}
    side_only = render_qc.check_cuts(*scene(0.22, 0.19), (90, 270), penetrations={"top": 0})
    assert side_only["garments"][0]["visible_share_min"] is None and side_only["garments"][0]["passed"] is True, "side views are recorded, not judged"
    assert all(v["frontal"] is False and v["visible_share"] is not None for v in side_only["garments"][0]["views"])


def test_a_hidden_garment_is_compared_with_the_garments_only_picture_not_counted_against():
    body = cylinder(0.14, 0.0, 1.7)
    inner = [(c, n, GARMENT) for c, n, _ in cylinder(0.17, 0.6, 1.0)]
    outer = [(c, n, (200, 60, 80)) for c, n, _ in cylinder(0.20, 0.5, 1.2)]
    r = render_qc.check_cuts(body, [("top", inner, GARMENT), ("jacket", outer, (200, 60, 80))], (0, 180), penetrations={"top": 0, "jacket": 0})
    by = {g["kind"]: g for g in r["garments"]}
    assert by["jacket"]["visible_share_min"] == 1.0 and by["jacket"]["passed"] is True
    assert all(v["reference_pixels"] == 0 and v["visible_share"] is None for v in by["top"]["views"]), "fully hidden by the jacket: nothing to compare, so no verdict"
    assert by["top"]["visible_share_min"] is None and by["top"]["colour_distance_max"] is None and by["top"]["passed"] is True, "only the fitting report (0 penetrations) could be judged"


def test_the_check_is_deterministic():
    assert report(0.15, 0.19) == report(0.15, 0.19)


@pytest.mark.parametrize("sex", ("male", "female"))
@pytest.mark.parametrize("kind", ("top", "bottom", "skirt", "dress", "jacket"))
def test_the_real_sample_garments_are_measured_and_the_numbers_are_sane(sex, kind):
    """Measured here with the whole body and no relaxation; the pass line for the samples is tests/test_garment_cover.py (R-ENGINE-09b)."""
    body, layers, fits = render3d_scene.build_layers(sex, M, [kind])
    r = render_qc.check_cuts(body, layers, (0, 90, 180, 270), penetrations={f["kind"]: f["penetrations"] for f in fits})
    g = r["garments"][0]
    assert g["kind"] == kind and g["penetration_points"] == 0 and len(g["views"]) == 4
    assert 0.0 < g["visible_share_min"] <= 1.0 and 0.0 <= g["colour_distance_max"] <= render_qc.MAX_COLOUR_DISTANCE
    assert all(v["reference_pixels"] > 0 for v in g["views"]) and [v["frontal"] for v in g["views"]] == [True, False, True, False]
