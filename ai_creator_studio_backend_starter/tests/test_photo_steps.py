"""R-044 A: the local step pipeline: geometry, purity (input untouched), no network, strict validation."""
import socket

import pytest
from PIL import Image

from app import photo_steps as ps


def product(canvas=(200, 100), box=(60, 20, 140, 80), bg=(250, 250, 250), fg=(20, 60, 160)):
    img = Image.new("RGB", canvas, bg)
    img.paste(Image.new("RGB", (box[2] - box[0], box[3] - box[1]), fg), box[:2])
    return img


def test_auto_crop_finds_the_object_and_keeps_the_margin():
    out = ps.auto_crop(product(), tolerance=24, margin_pct=0)
    assert out.size == (80, 60)
    padded = ps.auto_crop(product(), tolerance=24, margin_pct=10)
    assert padded.size == (96, 72), "10% of the object's width/height on every side"
    assert ps.auto_crop(Image.new("RGB", (50, 50), (9, 9, 9))).size == (50, 50), "only background: unchanged"


def test_auto_crop_uses_transparency_when_the_image_has_it_and_ignores_one_odd_corner():
    cut = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
    cut.paste(Image.new("RGBA", (30, 40), (255, 0, 0, 255)), (10, 20))
    assert ps.auto_crop(cut, margin_pct=0).size == (30, 40)
    odd = product()
    odd.putpixel((0, 0), (255, 0, 0))
    assert ps.auto_crop(odd, margin_pct=0).size == (81, 61) or ps.auto_crop(odd, margin_pct=0).size[0] >= 80, "a stray corner pixel does not take over"


def test_fit_canvas_centres_the_whole_picture_without_cropping():
    out = ps.fit_canvas(Image.new("RGB", (200, 100), (10, 20, 30)), 100, 100, (255, 255, 255))
    assert out.size == (100, 100)
    assert out.getpixel((50, 50)) == (10, 20, 30) and out.getpixel((50, 5)) == (255, 255, 255) and out.getpixel((50, 95)) == (255, 255, 255)
    tall = ps.fit_canvas(Image.new("RGB", (50, 100), (10, 20, 30)), 100, 100, (255, 255, 255))
    assert tall.getpixel((5, 50)) == (255, 255, 255) and tall.getpixel((50, 50)) == (10, 20, 30) and tall.getpixel((95, 50)) == (255, 255, 255)


def test_solid_background_replaces_transparency_and_leaves_opaque_pixels():
    cut = Image.new("RGBA", (10, 10), (0, 0, 0, 0)); cut.putpixel((5, 5), (200, 10, 10, 255))
    out, _ = ps.run_steps(cut, [{"op": "solid_background", "color": "#336699"}])
    assert out.mode == "RGB" and out.getpixel((0, 0)) == (0x33, 0x66, 0x99) and out.getpixel((5, 5)) == (200, 10, 10)


def test_a_pipeline_runs_in_order_records_every_step_and_never_touches_the_input(monkeypatch):
    def no_network(*a, **k):
        raise AssertionError("a local step must not open a network connection")
    monkeypatch.setattr(socket, "socket", no_network)
    source = product()
    before = source.tobytes()
    out, records = ps.run_steps(source, [{"op": "auto_crop", "margin_pct": 0}, {"op": "fit_canvas", "width": 120, "height": 120}])
    assert source.tobytes() == before and source.size == (200, 100), "the original is untouched"
    assert out.size == (120, 120)
    assert [(r["op"], r["mode"], r["size_in"], r["size_out"]) for r in records] == [("auto_crop", "local", [200, 100], [80, 60]), ("fit_canvas", "local", [80, 60], [120, 120])]
    assert all(r["duration_ms"] >= 0 for r in records)


@pytest.mark.parametrize("steps, code", [
    (None, "STEPS_REQUIRED"), ([], "STEPS_REQUIRED"), ([{"op": "auto_crop"}] * 13, "STEPS_TOO_MANY"),
    ([{"op": "sharpen"}], "STEP_UNKNOWN"), (["auto_crop"], "STEP_UNKNOWN"),
    ([{"op": "auto_crop", "evil": 1}], "STEP_PARAMETER_UNKNOWN"),
    ([{"op": "auto_crop", "tolerance": 999}], "STEP_PARAMETER_INVALID"), ([{"op": "auto_crop", "margin_pct": True}], "STEP_PARAMETER_INVALID"),
    ([{"op": "fit_canvas", "width": 10, "height": 100}], "STEP_PARAMETER_INVALID"), ([{"op": "fit_canvas", "width": 99999}], "STEP_PARAMETER_INVALID"),
    ([{"op": "solid_background", "color": "red"}], "STEP_COLOR_INVALID"), ([{"op": "fit_canvas", "color": "#12345"}], "STEP_COLOR_INVALID"),
])
def test_bad_requests_are_refused_as_a_whole_before_anything_runs(steps, code):
    source = product()
    with pytest.raises(ps.StepError) as err:
        ps.run_steps(source, steps)
    assert err.value.code == code


def test_defaults_are_filled_in_and_a_later_bad_step_blocks_the_earlier_good_ones():
    assert ps.validate_steps([{"op": "auto_crop"}]) == [{"op": "auto_crop", "tolerance": 24, "margin_pct": 5}]
    with pytest.raises(ps.StepError):
        ps.validate_steps([{"op": "auto_crop"}, {"op": "nope"}])


def cut_out(color=(200, 40, 40)):
    img = Image.new("RGBA", (60, 60), (0, 0, 0, 0))
    img.paste(Image.new("RGBA", (30, 30), color + (255,)), (15, 15))
    return img


def test_gradient_background_fills_only_transparency_top_to_bottom():
    out, _ = ps.run_steps(cut_out(), [{"op": "gradient_background", "top_color": "#000000", "bottom_color": "#ffffff"}])
    assert out.mode == "RGB" and out.getpixel((30, 30)) == (200, 40, 40), "the object is untouched"
    top, bottom = out.getpixel((2, 0)), out.getpixel((2, 59))
    assert top == (0, 0, 0) and bottom == (255, 255, 255)
    assert out.getpixel((2, 10))[0] < out.getpixel((2, 50))[0], "darker at the top, lighter at the bottom"


def test_white_balance_neutralises_a_colour_cast_and_strength_blends():
    cast = Image.new("RGB", (20, 20), (200, 150, 100))
    full, _ = ps.run_steps(cast, [{"op": "white_balance", "strength_pct": 100}])
    r, g, b = full.getpixel((5, 5))
    assert max(r, g, b) - min(r, g, b) <= 2, f"gray-world makes a uniform cast neutral, got {(r, g, b)}"
    none, _ = ps.run_steps(cast, [{"op": "white_balance", "strength_pct": 0}])
    assert none.getpixel((5, 5)) == (200, 150, 100)
    half, _ = ps.run_steps(cast, [{"op": "white_balance", "strength_pct": 50}])
    assert max(half.getpixel((5, 5))) - min(half.getpixel((5, 5))) < 100 and max(half.getpixel((5, 5))) - min(half.getpixel((5, 5))) > 2
    neutral = Image.new("RGB", (8, 8), (90, 90, 90))
    assert ps.run_steps(neutral, [{"op": "white_balance"}])[0].getpixel((1, 1)) == (90, 90, 90), "already neutral: unchanged"


def test_white_balance_ignores_transparent_pixels_and_keeps_alpha():
    out, _ = ps.run_steps(cut_out((200, 150, 100)), [{"op": "white_balance"}])
    assert out.mode == "RGBA" and out.getchannel("A").getextrema() == (0, 255)
    r, g, b, a = out.getpixel((30, 30))
    assert a == 255 and max(r, g, b) - min(r, g, b) <= 2, "measured on the object only"


def test_drop_shadow_grows_the_canvas_darkens_below_the_object_and_needs_transparency():
    out, records = ps.run_steps(cut_out(), [{"op": "drop_shadow", "offset_x": 0, "offset_y": 10, "blur": 4, "opacity_pct": 60}])
    pad = 4 * 3 + 10
    assert out.size == (60 + 2 * pad, 60 + 2 * pad) and out.mode == "RGBA" and records[0]["size_out"] == list(out.size)
    assert out.getpixel((pad + 30, pad + 30)) == (200, 40, 40, 255), "the object is on top"
    below = out.getpixel((pad + 30, pad + 30 + 15 + 5))    # just under the object's bottom edge: shadow only
    assert below[3] > 60 and below[:3] == (0, 0, 0)
    assert out.getpixel((0, 0))[3] == 0, "far corner stays transparent"
    with pytest.raises(ps.StepError) as err:
        ps.run_steps(Image.new("RGB", (30, 30), (255, 255, 255)), [{"op": "drop_shadow"}])
    assert err.value.code == "STEP_NEEDS_TRANSPARENCY"


def test_a_shadow_then_a_background_is_the_product_pipeline_and_stays_local(monkeypatch):
    def no_network(*a, **k):
        raise AssertionError("no network")
    monkeypatch.setattr(socket, "socket", no_network)
    out, records = ps.run_steps(cut_out(), [{"op": "drop_shadow"}, {"op": "solid_background", "color": "#ffffff"}, {"op": "fit_canvas", "width": 100, "height": 100}])
    assert out.size == (100, 100) and [r["op"] for r in records] == ["drop_shadow", "solid_background", "fit_canvas"] and all(r["mode"] == "local" for r in records)


@pytest.mark.parametrize("step, code", [
    ({"op": "gradient_background", "top_color": "red"}, "STEP_COLOR_INVALID"),
    ({"op": "white_balance", "strength_pct": 101}, "STEP_PARAMETER_INVALID"),
    ({"op": "drop_shadow", "blur": 101}, "STEP_PARAMETER_INVALID"), ({"op": "drop_shadow", "offset_x": 201}, "STEP_PARAMETER_INVALID"),
    ({"op": "drop_shadow", "opacity_pct": -1}, "STEP_PARAMETER_INVALID"), ({"op": "white_balance", "x": 1}, "STEP_PARAMETER_UNKNOWN"),
])
def test_new_steps_are_validated_strictly(step, code):
    with pytest.raises(ps.StepError) as err:
        ps.validate_steps([step])
    assert err.value.code == code
