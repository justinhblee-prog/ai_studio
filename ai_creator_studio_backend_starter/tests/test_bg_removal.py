"""Lane 3 / E-09a: background-removal candidates, measured on the synthetic evaluation set (numbers recorded in docs/BG_REMOVAL_EVAL.md)."""
import pytest
from PIL import Image

from app import bg_removal as bg


def case(name):
    return next(c for c in bg.evaluation_set() if c["name"].startswith(name))


def test_the_evaluation_set_is_deterministic_and_has_a_deliberately_hard_case():
    a, b = bg.evaluation_set(), bg.evaluation_set()
    assert [c["name"] for c in a] == [c["name"] for c in b] and len(a) == 10
    assert all(x["image"].tobytes() == y["image"].tobytes() for x, y in zip(a, b))
    assert [c["name"] for c in a if c["hard"]] == ["white-ellipse-246x246x246"]


def test_every_candidate_cuts_the_easy_cases_well_and_the_numbers_are_recorded():
    result = bg.evaluate()
    for method in bg.METHODS:
        summary = result["summary"][method]
        assert summary["mean_iou_easy"] >= 0.95, (method, summary)
        assert summary["min_iou_easy"] >= 0.80, (method, summary)
    for name in ("white-ellipse-200x40x40", "gray-ellipse-40x120x60", "strong-ellipse-200x40x40"):
        for method in bg.METHODS:
            assert result["iou"][method][name] >= 0.99, (method, name)
    for method in bg.METHODS:
        assert result["iou"][method]["noisy-ellipse-60x60x60"] >= 0.98, method
    hard = {m: result["iou"][m]["white-ellipse-246x246x246"] for m in bg.METHODS}
    assert hard["gradient"] < 0.1 and 0.5 < hard["flood"] < 0.8 and hard["auto"] == hard["flood"], hard      # the hard case is NOT solved by any candidate
    assert result["selected"] in bg.METHODS and result["selected"] == "auto"
    assert result["summary"]["auto"]["mean_iou_all"] >= max(result["summary"][m]["mean_iou_all"] for m in bg.CANDIDATES) - 1e-9


def test_a_strong_shading_needs_the_gradient_model_and_auto_chooses_it():
    img = case("strong-rect")["image"]
    assert bg.corner_spread(img) > bg.SPREAD_LIMIT
    assert bg.corner_spread(case("white-rect")["image"]) <= bg.SPREAD_LIMIT
    assert bg.iou(bg.foreground_mask(img, "auto"), case("strong-rect")["truth"]) >= 0.99


def test_remove_background_returns_rgba_with_transparent_corners_and_an_opaque_product():
    c = case("white-ellipse-200")
    out = bg.remove_background(c["image"])
    assert out.mode == "RGBA" and out.size == c["image"].size
    assert out.getpixel((2, 2))[3] == 0 and out.getpixel((80, 80))[3] == 255
    assert out.getpixel((80, 80))[:3] == c["image"].convert("RGB").getpixel((80, 80)), "the product's own colours are untouched"
    sharp = bg.remove_background(c["image"], feather=0)
    assert set(sharp.getchannel("A").getdata()) <= {0, 255}


def test_known_limit_enclosed_background_such_as_a_donut_hole_stays_opaque():
    c = case("white-donut")
    for method in bg.CANDIDATES:
        mask = bg.foreground_mask(c["image"], method)
        assert mask.getpixel((80, 80)) == 255, "the hole in the middle is kept as product"
        assert 0.80 <= bg.iou(mask, c["truth"]) < 0.95, "so the IoU is the known 0.87-ish, not a pass"


def test_the_confidence_check_is_honest_about_a_white_product_on_a_white_background():
    easy = bg.removal_confidence(case("white-ellipse-200")["image"], "auto")
    hard = bg.removal_confidence(case("white-ellipse-246")["image"], "auto")
    assert easy["reliable"] is True and easy["warnings"] == [] and 0.2 < easy["foreground_share"] < 0.6
    assert hard["reliable"] is False and hard["warnings"] and hard["colour_contrast"] < 25
    plain = bg.removal_confidence(Image.new("RGB", (64, 64), (240, 240, 240)), "auto")
    assert plain["reliable"] is False and plain["foreground_share"] < 0.02


def test_a_busy_background_is_flagged_not_silently_cut():
    noisy = Image.effect_noise((96, 96), 90).convert("RGB")
    report = bg.removal_confidence(noisy, "flood")
    assert report["reliable"] is False


def test_unknown_methods_are_refused_and_tolerance_matters():
    with pytest.raises(ValueError):
        bg.foreground_mask(Image.new("RGB", (8, 8)), "magic")
    c = case("white-ellipse-246")
    strict, loose = bg.foreground_mask(c["image"], "gradient", 2), bg.foreground_mask(c["image"], "gradient", 60)
    assert sum(strict.histogram()[128:]) > sum(loose.histogram()[128:]), "a tighter tolerance keeps more"
