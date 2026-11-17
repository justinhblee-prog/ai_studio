"""Lane 2 / E-06 + M1: measurement mannequin and the clothing-size fit reference."""
import math

import pytest
from pydantic import ValidationError

from app.assets.validation import validate_gltf_upload
from app.glb_tools import inspect_glb, parse_glb
from app.mannequin import Measurements, SizeChart, build_mannequin_glb, fit_report, measurement_warnings, profile

M = Measurements(height_cm=170, chest_cm=92, waist_cm=76, hips_cm=98)
CHART = SizeChart(sizes={"S": {"chest": 94, "waist": 80, "hips": 100}, "M": {"chest": 100, "waist": 86, "hips": 106}, "L": {"chest": 108, "waist": 94, "hips": 114}})


def test_the_mannequin_is_a_valid_glb_as_tall_as_the_height_and_marked_approximate():
    glb = build_mannequin_glb(M)
    assert validate_gltf_upload("m.glb", glb).media_type == "model/gltf-binary"
    info = inspect_glb(glb)
    assert info["size"][1] == pytest.approx(1.70, abs=0.001), "the column is as tall as the typed height"
    assert info["triangles"] > 200 and info["meshes"] == 1
    extras = parse_glb(glb)[0]["nodes"][0]["extras"]
    assert extras["approximate"] is True and extras["is_reconstruction"] is False and extras["measurements_cm"]["chest_cm"] == 92
    assert "Approximate" in extras["label"]


def test_the_chest_waist_and_hip_sections_follow_the_circumferences():
    rows = {round(p, 2): (a, b) for p, a, b in [(y / 1.70, a, b) for y, a, b in profile(M)]}
    def perimeter(a, b):                       # ellipse perimeter (Ramanujan), metres -> centimetres
        h = ((a - b) / (a + b)) ** 2
        return math.pi * (a + b) * (1 + 3 * h / (10 + math.sqrt(4 - 3 * h))) * 100
    assert perimeter(*rows[0.72]) == pytest.approx(92, abs=0.3)
    assert perimeter(*rows[0.62]) == pytest.approx(76, abs=0.3)
    assert perimeter(*rows[0.50]) == pytest.approx(98, abs=0.3)


def test_a_bigger_person_makes_a_wider_and_a_taller_mannequin():
    small, big = inspect_glb(build_mannequin_glb(M)), inspect_glb(build_mannequin_glb(Measurements(height_cm=190, chest_cm=110, waist_cm=95, hips_cm=112)))
    assert big["size"][0] > small["size"][0] and big["size"][1] > small["size"][1]
    assert build_mannequin_glb(M) == build_mannequin_glb(M), "deterministic"


@pytest.mark.parametrize("bad", [dict(height_cm=119), dict(height_cm=221), dict(chest_cm=59), dict(waist_cm=151), dict(hips_cm=69), dict(extra=1), dict(height_cm="tall")])
def test_implausible_or_unknown_inputs_are_refused(bad):
    base = dict(height_cm=170, chest_cm=92, waist_cm=76, hips_cm=98)
    base.update(bad)
    with pytest.raises(ValidationError):
        Measurements(**base)


def test_odd_proportions_only_warn():
    assert measurement_warnings(M) == []
    assert measurement_warnings(Measurements(height_cm=170, chest_cm=80, waist_cm=110, hips_cm=85))
    assert measurement_warnings(Measurements(height_cm=170, chest_cm=92, waist_cm=100, hips_cm=70))


def test_the_fit_report_is_always_labelled_reference_and_picks_the_size_with_regular_room():
    report = fit_report(M, CHART)
    assert report["reference_only"] is True and "참고용" in report["label_ko"] and "Approximate" in report["label_en"]
    assert report["recommended_size"] == "M" and [s["size"] for s in report["sizes"]] == ["S", "M", "L"]
    s = next(x for x in report["sizes"] if x["size"] == "S")["dimensions"]
    assert s["chest"]["ease_cm"] == 2.0 and s["chest"]["fit"] == "snug" and s["waist"]["ease_cm"] == 4.0 and s["waist"]["fit"] == "regular"
    m_ = next(x for x in report["sizes"] if x["size"] == "M")["dimensions"]
    assert m_["chest"]["ease_cm"] == 8.0 and m_["chest"]["fit"] == "regular"
    assert "no cloth simulation" in report["method"]


def test_stretch_fabric_changes_the_ease_and_a_too_small_garment_is_flagged():
    stretch = fit_report(M, SizeChart(sizes=CHART.sizes, stretch=0.2))
    assert next(x for x in stretch["sizes"] if x["size"] == "S")["dimensions"]["chest"]["ease_cm"] == 20.8
    tiny = fit_report(M, SizeChart(sizes={"XS": {"chest": 84, "waist": 70, "hips": 90}}))
    dims = tiny["sizes"][0]["dimensions"]
    assert all(d["fit"] == "too_tight" for d in dims.values()) and tiny["recommended_size"] == "XS", "the closest size is still named, but flagged too tight"


def test_partial_charts_and_bad_charts():
    only_chest = fit_report(M, SizeChart(sizes={"M": {"chest": 100}}))
    assert list(only_chest["sizes"][0]["dimensions"]) == ["chest"]
    assert fit_report(M, SizeChart(sizes={"M": {"sleeve": 60}}))["recommended_size"] is None
    for bad in ({"sizes": {}}, {"sizes": {"M": {"chest": 100}}, "stretch": 0.9}, {"sizes": {"M": {"chest": 100}}, "extra": 1}):
        with pytest.raises(ValidationError):
            SizeChart(**bad)
