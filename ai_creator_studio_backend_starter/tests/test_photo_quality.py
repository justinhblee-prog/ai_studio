"""Lane 3 / E-10: the finished-picture quality check, on synthetic pictures (thresholds are provisional, see the module)."""
import pytest
from PIL import Image, ImageDraw, ImageFilter

from app import channel_export as ce
from app import photo_quality as pq


def textured(w=120, h=120, colour=(200, 40, 40)):
    """A product with a checker pattern (so it has edges to be sharp or soft)."""
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, w - 1, h - 1), fill=colour + (255,))
    for x in range(0, w, 12):
        for y in range(0, h, 12):
            if (x // 12 + y // 12) % 2:
                d.rectangle((x, y, x + 11, y + 11), fill=(40, 40, 40, 255))
    return img


def on_white(product, size=(800, 800), at=None):
    pic = Image.new("RGB", size, (255, 255, 255))
    x, y = at or ((size[0] - product.width) // 2, (size[1] - product.height) // 2)
    pic.paste(product, (x, y), product)
    return pic


def names(report, key):
    return set(report[key])


def test_a_clean_centred_sharp_picture_passes_every_rule():
    report = pq.check_image(on_white(textured(300, 300)), background="white")
    assert report["status"] == "pass", report
    assert report["failed"] == [] and report["warnings"] == [] and report["provisional_thresholds"] is True
    assert {c["name"] for c in report["checks"]} >= {"size", "blank", "product_found", "edges", "centred", "coverage", "sharpness", "highlights", "background"}


def test_a_blank_picture_fails_and_stops_early():
    report = pq.check_image(Image.new("RGB", (800, 800), (255, 255, 255)))
    assert report["status"] == "fail" and report["failed"] == ["blank"]


def test_a_product_cut_off_by_the_edge_fails():
    report = pq.check_image(on_white(textured(300, 300), at=(-100, 250)), background="white")
    assert report["status"] == "fail" and "edges" in report["failed"]
    assert "left" in next(c for c in report["checks"] if c["name"] == "edges")["value"]


def test_an_off_centre_product_only_warns():
    report = pq.check_image(on_white(textured(200, 200), at=(520, 100)), background="white")
    assert "centred" in report["warnings"] and report["failed"] == []


def test_a_tiny_product_warns_about_coverage():
    report = pq.check_image(on_white(textured(60, 60)), background="white")
    assert "coverage" in report["warnings"]


def test_a_blurred_product_warns_about_sharpness_but_the_sharp_one_does_not():
    sharp = on_white(textured(300, 300))
    blurry = sharp.filter(ImageFilter.GaussianBlur(9))
    assert "sharpness" not in pq.check_image(sharp, background="white")["warnings"]
    assert "sharpness" in pq.check_image(blurry, background="white")["warnings"]


def test_a_dirty_white_background_warns_only_when_white_is_required():
    pic = on_white(textured(300, 300))
    d = ImageDraw.Draw(pic)
    for i in range(0, 800, 40):
        d.rectangle((i, 20, i + 14, 60), fill=(215, 220, 205))      # smudges on the "white" background
    dirty = pq.check_image(pic, background="white")
    assert "background" in dirty["warnings"] or "product_found" in dirty["failed"] or dirty["status"] != "pass", dirty
    assert next((c for c in pq.check_image(pic)["checks"] if c["name"] == "background"), None) is None, "not asked for, not checked"


def test_the_size_rules_depend_on_whether_a_channel_size_is_given():
    pic = on_white(textured(300, 300), size=(700, 700))
    assert next(c for c in pq.check_image(pic)["checks"] if c["name"] == "size")["status"] == "warn", "short side under 800"
    wrong = pq.check_image(pic, target_size=(1000, 1000))
    assert wrong["status"] == "fail" and "size" in wrong["failed"]
    assert next(c for c in pq.check_image(pic, target_size=(700, 700))["checks"] if c["name"] == "size")["status"] == "pass"


def test_blown_highlights_are_reported_for_a_pure_white_product_on_a_grey_background():
    pic = Image.new("RGB", (800, 800), (140, 140, 140))
    ImageDraw.Draw(pic).ellipse((200, 200, 600, 600), fill=(255, 255, 255))
    report = pq.check_image(pic)
    assert "highlights" in report["warnings"]


def test_check_files_checks_an_exported_set_against_its_channel_sizes():
    product = textured(160, 160)
    files = ce.export_set(product, ["marketplace_square", "thumbnail"], "SKU-1", shadow="none")
    reports = pq.check_files(files, ce.CHANNELS)
    assert [r["filename"] for r in reports] == [f["filename"] for f in files]
    assert all("size" not in r["failed"] for r in reports), reports
    files[0]["bytes"] = ce.encode(Image.new("RGB", (500, 500), (255, 255, 255)), "jpeg", 90)[0]
    assert "size" in pq.check_files(files, ce.CHANNELS)[0]["failed"]


@pytest.mark.parametrize("mode", ["RGBA", "L", "P"])
def test_other_picture_modes_are_accepted(mode):
    base = on_white(textured(300, 300))
    pic = base.convert(mode)
    assert pq.check_image(pic)["status"] in ("pass", "warn", "fail")
