"""Lane 3 / E-09c: crop, centre, channel sizes, file names, AI mark inside the exported files, ZIP."""
import io
import zipfile

import pytest
from PIL import Image, ImageDraw

from app import ai_marking
from app import channel_export as ce

RED = (200, 40, 40)


def product(w=400, h=300, box=(220, 150, 300, 250)):
    """A small red block sitting off-centre in a big transparent canvas."""
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(img).rectangle(box, fill=RED + (255,))
    return img


def bbox_of(img):
    return img.convert("RGB").point(lambda v: 0 if v >= 250 else 255).convert("L").getbbox()


def test_crop_to_product_removes_the_empty_border_and_refuses_an_empty_picture():
    cropped = ce.crop_to_product(product())
    assert cropped.size == (81, 101) and cropped.getpixel((40, 50)) == RED + (255,)
    assert ce.crop_to_product(product(), pad_ratio=0.1).size[0] > 81
    with pytest.raises(ValueError):
        ce.crop_to_product(Image.new("RGBA", (10, 10), (0, 0, 0, 0)))
    with pytest.raises(ValueError):
        ce.crop_to_product(Image.new("RGB", (10, 10)))


@pytest.mark.parametrize("channel", ["marketplace_square", "feed_4_5", "story_9_16", "banner_16_9", "thumbnail"])
def test_each_channel_gives_its_size_with_the_product_centred_inside_its_margin(channel):
    spec = ce.CHANNELS[channel]
    img = ce.render(product(), channel, shadow="none")
    assert img.size == spec["size"] and img.getpixel((2, 2)) == (255, 255, 255)
    x0, y0, x1, y1 = bbox_of(img)
    w, h = spec["size"]
    assert abs((x0 + x1) / 2 - w / 2) <= 3 and abs((y0 + y1) / 2 - h / 2) <= 3, "centred"
    assert x0 >= spec["margin"] * w - 3 and y0 >= spec["margin"] * h - 3 and x1 <= w - spec["margin"] * w + 3 and y1 <= h - spec["margin"] * h + 3, "inside the margin"
    assert (x1 - x0) >= (1 - 2 * spec["margin"]) * w - 4 or (y1 - y0) >= (1 - 2 * spec["margin"]) * h - 4, "and as large as the margin allows"


def test_the_transparent_channel_keeps_an_alpha_channel_and_a_clear_border():
    img = ce.render(product(), "transparent_png")
    assert img.mode == "RGBA" and img.size == (1200, 1200) and img.getpixel((3, 3))[3] == 0 and img.getpixel((600, 600))[3] == 255


def test_the_shadow_and_background_options_pass_through():
    plain = ce.render(product(), "marketplace_square", shadow="none")
    shadowed = ce.render(product(), "marketplace_square", shadow="drop")
    assert plain != shadowed
    gray = ce.render(product(), "marketplace_square", background="solid", color=(200, 200, 200), shadow="none")
    assert gray.getpixel((2, 2)) == (200, 200, 200)


@pytest.mark.parametrize("sku,ok", [("SKU-001", True), ("a", True), ("A_b-9", True), ("x" * 40, True), ("x" * 41, False), ("", False), ("-bad", False), ("a b", False), ("../x", False), ("한글", False), ("a/b", False)])
def test_file_names_follow_one_rule_and_unsafe_codes_are_refused(sku, ok):
    if ok:
        assert ce.filename(sku, "feed_4_5", 3, "jpg") == f"{sku}_feed_4_5_03.jpg"
    else:
        with pytest.raises(ValueError):
            ce.filename(sku, "feed_4_5", 3, "jpg")


def test_file_name_arguments_are_checked():
    for args in (("S1", "nope", 1, "jpg"), ("S1", "feed_4_5", 0, "jpg"), ("S1", "feed_4_5", 100, "jpg"), ("S1", "feed_4_5", True, "jpg")):
        with pytest.raises(ValueError):
            ce.filename(*args)


def test_encoded_files_have_the_right_format_and_ai_marking_is_added_only_when_asked_without_touching_pixels():
    img = ce.render(product(), "marketplace_square", shadow="none")
    plain, media = ce.encode(img, "jpeg", 90)
    assert plain[:2] == b"\xff\xd8" and media == "image/jpeg" and not ai_marking.already_marked(plain)
    marked, _ = ce.encode(img, "jpeg", 90, ai_kind="generated")
    assert ai_marking.already_marked(marked) and len(marked) > len(plain)
    assert Image.open(io.BytesIO(marked)).tobytes() == Image.open(io.BytesIO(plain)).tobytes(), "the pixels are identical"
    png, m = ce.encode(img, "png", 100, ai_kind="edited")
    assert png[:4] == b"\x89PNG" and m == "image/png" and ai_marking.already_marked(png)
    webp, m = ce.encode(img, "webp", 85, ai_kind="generated")
    assert webp[:4] == b"RIFF" and m == "image/webp" and ai_marking.already_marked(webp)
    with pytest.raises(ValueError):
        ce.encode(img, "gif", 90)


def test_an_export_set_names_sizes_and_marks_every_file_and_zips_them():
    files = ce.export_set(product(), ["marketplace_square", "story_9_16", "thumbnail"], "SKU-7", index=2, ai_kind="generated", shadow="none")
    assert [f["filename"] for f in files] == ["SKU-7_marketplace_square_02.jpg", "SKU-7_story_9_16_02.jpg", "SKU-7_thumbnail_02.webp"]
    assert [(f["width"], f["height"]) for f in files] == [(1000, 1000), (1080, 1920), (600, 600)] and all(f["ai_marked"] and ai_marking.already_marked(f["bytes"]) for f in files)
    blob = ce.zip_bytes(files)
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        assert z.namelist() == [f["filename"] for f in files] and z.read(files[0]["filename"]) == files[0]["bytes"]
    unmarked = ce.export_set(product(), ["thumbnail"], "SKU-7", shadow="none")
    assert unmarked[0]["ai_marked"] is False and not ai_marking.already_marked(unmarked[0]["bytes"])


def test_bad_export_requests_are_refused():
    for channels in ([], ["feed_4_5", "feed_4_5"], ["nope"]):
        with pytest.raises(ValueError):
            ce.export_set(product(), channels, "S1")
    with pytest.raises(ValueError):
        ce.export_set(product(), ["feed_4_5"], "bad sku")
    with pytest.raises(ValueError):
        ce.export_set(Image.new("RGBA", (9, 9), (0, 0, 0, 0)), ["feed_4_5"], "S1")


def test_the_channel_table_is_complete_and_marked_provisional():
    for name, spec in ce.CHANNELS.items():
        assert set(spec) == {"size", "margin", "format", "quality", "background", "label"} and spec["format"] in ce.MEDIA and 0 < spec["margin"] < 0.3, name
    assert "PROVISIONAL" in ce.__doc__
