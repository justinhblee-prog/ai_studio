"""M4: the ease and pressure maps: the size ladder, zone ease, vertex clearance (negative = inside the body), the recommendation, and the S / M / L sheet."""
import pytest
from PIL import ImageChops

from app import base_models, ease_map as em, garments

NOMINAL = {"height_cm": 170, "chest_cm": 92, "waist_cm": 76, "hips_cm": 98}
SMALL = {"height_cm": 155, "chest_cm": 80, "waist_cm": 64, "hips_cm": 88}
BETWEEN = {"height_cm": 170, "chest_cm": 96, "waist_cm": 80, "hips_cm": 102}
LARGE = {"height_cm": 185, "chest_cm": 108, "waist_cm": 92, "hips_cm": 112}


@pytest.mark.parametrize("ease, name", [(-5, "tight"), (-0.1, "tight"), (0.0, "fitted"), (3.9, "fitted"), (4.0, "regular"), (9.9, "regular"), (10.0, "loose"), (30, "loose")])
def test_the_ease_classes_have_their_boundaries_where_the_proposal_says(ease, name):
    assert em.classify(ease) == name


def test_the_size_ladder_is_the_nominal_body_minus_four_zero_plus_four_round_the_girths_with_the_height_kept():
    ladder = em.ladder("female", NOMINAL)
    assert ladder["M"] == {"height_cm": 170, "chest_cm": 92.0, "waist_cm": 76.0, "hips_cm": 98.0}
    assert (ladder["S"]["chest_cm"], ladder["L"]["waist_cm"], ladder["S"]["hips_cm"], ladder["L"]["height_cm"]) == (88.0, 80.0, 94.0, 170)
    preset = base_models.preset_circumferences_cm("male")
    assert em.ladder("male", None)["M"]["chest_cm"] == preset["chest"]


@pytest.mark.parametrize("sex", base_models.SEXES)
@pytest.mark.parametrize("kind", ("top", "bottom", "skirt", "dress"))
def test_on_the_body_a_size_is_made_for_the_ease_is_four_cm_and_the_ladder_steps_four_cm(kind, sex):
    table = em.zone_table(kind, sex, NOMINAL, NOMINAL)
    for zone in em.ZONES[kind]:
        assert [table[s][zone]["ease_cm"] for s in em.SIZES] == pytest.approx([0.0, 4.0, 8.0], abs=0.25), (kind, sex, zone)
        assert [table[s][zone]["class"] for s in em.SIZES] == ["fitted", "regular", "regular"]


def test_a_jacket_is_cut_roomier_than_a_t_shirt_so_even_its_smallest_size_has_room():
    table = em.zone_table("jacket", "female", NOMINAL, NOMINAL)
    assert table["S"]["chest_cm"]["ease_cm"] == pytest.approx(5.9, abs=0.3) and table["M"]["chest_cm"]["ease_cm"] == pytest.approx(9.9, abs=0.3)
    assert em.compare("jacket", "female", NOMINAL, NOMINAL)["recommended"] == "S"


@pytest.mark.parametrize("body, expected", [(SMALL, "S"), (NOMINAL, "M"), (BETWEEN, "L"), (LARGE, None)])
def test_the_recommendation_is_the_smallest_size_with_room_everywhere_or_none(body, expected):
    report = em.compare("top", "female", body, NOMINAL)
    assert report["recommended"] == expected and report["limits"]["source"] == "proposal"
    if expected is None:
        assert all(report["sizes"][s]["tight_zones"] for s in em.SIZES) and "no size fits" in report["note"]


def test_a_bigger_size_means_more_ease_less_pressure_and_a_higher_minimum_clearance():
    report = em.compare("top", "female", BETWEEN, NOMINAL)
    sizes = [report["sizes"][s] for s in em.SIZES]
    eases = [s["zones"]["chest_cm"]["ease_cm"] for s in sizes]
    assert eases == sorted(eases) and eases[0] < 0 < eases[2]
    assert [s["pressure_share"] for s in sizes] == sorted((s["pressure_share"] for s in sizes), reverse=True) and sizes[2]["pressure_share"] == 0.0
    assert [s["clearance_cm"]["min"] for s in sizes] == sorted(s["clearance_cm"]["min"] for s in sizes)
    assert sizes[0]["tight_zones"] == ["chest_cm", "waist_cm"] and sizes[2]["tight_zones"] == []


def test_vertex_clearance_is_negative_exactly_where_the_garment_is_inside_the_body():
    inside, _ = em.vertex_clearance("top", "female", "S", BETWEEN, NOMINAL)
    outside, _ = em.vertex_clearance("top", "female", "L", BETWEEN, NOMINAL)
    assert min(c for _, c in inside) < -0.5 and min(c for _, c in outside) > 0.0
    assert len(inside) == len(outside) and all(len(p) == 3 for p, _ in inside)
    ys = [p[1] for p, _ in outside]
    assert max(ys) == pytest.approx(0.81 * 1.70, rel=0.01), "the top reaches the shoulder line of a 170 cm body"


def test_a_taller_body_gets_a_longer_garment_but_the_width_is_not_scaled():
    short, _ = em.vertex_clearance("top", "female", "M", {**NOMINAL, "height_cm": 150}, NOMINAL)
    tall, _ = em.vertex_clearance("top", "female", "M", {**NOMINAL, "height_cm": 190}, NOMINAL)
    assert max(p[1] for p, _ in tall) > max(p[1] for p, _ in short) * 1.2
    assert max(p[0] for p, _ in tall) == pytest.approx(max(p[0] for p, _ in short), abs=1e-6), "width is absolute: only the length follows the body"


@pytest.mark.parametrize("sex", base_models.SEXES)
@pytest.mark.parametrize("kind", garments.KINDS)
def test_every_kind_works_for_both_sexes_with_one_clearance_per_vertex(kind, sex):
    report = em.compare(kind, sex, NOMINAL, NOMINAL)
    assert set(report["sizes"]) == {"S", "M", "L"} and report["recommended"] in ("S", "M") and report["nominal"]["chest_cm"] == 92.0
    assert all(report["sizes"][s]["pressure_share"] >= 0 for s in em.SIZES)


def test_unknown_kind_and_bad_measurements_are_refused():
    with pytest.raises(ValueError):
        em.compare("hat", "female")
    with pytest.raises(ValueError):
        em.compare("top", "female", {"chest_cm": 9999})


def test_the_colour_map_is_red_when_tight_green_when_fitted_blue_when_loose_and_continuous():
    assert em.colour_for(-10) == (200, 30, 30) and em.colour_for(2.0) == (90, 190, 90) and em.colour_for(50) == (40, 70, 170)
    red, green, blue = em.colour_for(-3), em.colour_for(2), em.colour_for(12)
    assert red[0] > red[1] and green[1] > green[0] and blue[2] > blue[0]
    previous = em.colour_for(-4)
    for tenth in range(-40, 140):
        now = em.colour_for(tenth / 10)
        assert max(abs(a - b) for a, b in zip(now, previous)) < 40, "no jump between neighbouring values"
        previous = now


def test_the_sheet_shows_three_panels_where_the_tight_size_differs_from_the_roomy_one_and_is_deterministic():
    sheet = em.render_sheet("top", "female", BETWEEN, nominal=NOMINAL, size=(150, 260))
    assert sheet.size == (450, 330) and sheet.tobytes() == em.render_sheet("top", "female", BETWEEN, nominal=NOMINAL, size=(150, 260)).tobytes()
    s_panel, l_panel = sheet.crop((0, 0, 150, 260)), sheet.crop((300, 0, 450, 260))
    assert ImageChops.difference(s_panel, l_panel).getbbox() is not None
    def warm(image):
        raw = image.convert("RGB").tobytes()
        return sum(1 for k in range(0, len(raw), 3) if raw[k] > 200 and raw[k + 1] < 170 and raw[k + 2] < 80)
    assert warm(s_panel) > warm(l_panel), "the tight size is drawn in the warm colours of pressure"
