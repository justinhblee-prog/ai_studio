"""Lane 3 / E-09b: background + shadow + reflection compositing on a cut-out product."""
import pytest
from PIL import Image, ImageDraw

from app import bg_compose as bc
from app import bg_removal as bg

RED = (200, 40, 40)


def product(w=160, h=160, box=(40, 30, 120, 110)):
    """An opaque red block on a transparent canvas (a perfect cut-out)."""
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(img).rectangle(box, fill=RED + (255,))
    return img


def near(a, b, tol=3):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def test_white_solid_and_gradient_backgrounds_have_the_right_colours_and_the_product_is_untouched():
    p = product()
    white = bc.compose(p, "white", shadow="none")
    assert white.getpixel((3, 3)) == (255, 255, 255) and white.getpixel((80, 70)) == RED
    solid = bc.compose(p, "solid", color=(10, 120, 200), shadow="none")
    assert near(solid.getpixel((3, 3)), (10, 120, 200), 0) and near(solid.getpixel((156, 156)), (10, 120, 200), 0) and solid.getpixel((80, 70)) == RED
    grad = bc.compose(p, "gradient", color=(250, 250, 250), color2=(40, 60, 90), shadow="none")
    assert near(grad.getpixel((3, 1)), (250, 250, 250), 8) and near(grad.getpixel((3, 158)), (40, 60, 90), 8)
    assert grad.getpixel((3, 80))[0] < grad.getpixel((3, 20))[0], "it darkens towards the bottom"
    assert grad.getpixel((80, 70)) == RED


def test_a_scene_background_is_cover_fitted_and_needs_a_picture():
    scene = Image.new("RGB", (400, 100), (30, 140, 60))
    out = bc.compose(product(), "scene", scene=scene, shadow="none")
    assert out.size == (160, 160) and near(out.getpixel((2, 2)), (30, 140, 60), 1) and near(out.getpixel((157, 157)), (30, 140, 60), 1)
    with pytest.raises(ValueError):
        bc.compose(product(), "scene")


def test_a_drop_shadow_darkens_beside_and_below_the_product_but_not_far_away_and_none_adds_nothing():
    p = product()
    plain = bc.compose(p, "white", shadow="none")
    shadowed = bc.compose(p, "white", shadow="drop")
    below = (80, 118)          # just under the block (block bottom edge is y=110), inside the offset shadow
    assert plain.getpixel(below) == (255, 255, 255)
    assert sum(shadowed.getpixel(below)) < 3 * 235, shadowed.getpixel(below)
    assert shadowed.getpixel((5, 5)) == (255, 255, 255), "far from the product nothing changes"
    assert shadowed.getpixel((80, 70)) == RED


def test_a_ground_shadow_sits_under_the_product_not_above_it():
    p = product()
    out = bc.compose(p, "white", shadow="ground", shadow_offset=(0, 12), shadow_blur=3)
    assert sum(out.getpixel((80, 114))) < 3 * 240, "a contact shadow just under the bottom edge"
    assert out.getpixel((80, 10)) == (255, 255, 255), "nothing above the product"


def test_a_reflection_appears_under_the_product_only_when_asked_and_fades_out():
    p = product()
    off = bc.compose(p, "white", shadow="none")
    on = bc.compose(p, "white", shadow="none", reflection=True, reflection_strength=0.5)
    assert off.getpixel((80, 114)) == (255, 255, 255)
    assert on.getpixel((80, 114)) != (255, 255, 255) and on.getpixel((80, 114))[1] < 245
    assert sum(on.getpixel((80, 114))) < sum(on.getpixel((80, 134))) <= 3 * 255, "stronger near the product, fading away"
    assert on.getpixel((80, 70)) == RED


def test_the_output_size_can_change_and_the_product_is_scaled_to_fit_and_centred():
    out = bc.compose(product(), "white", size=(400, 200), shadow="none")
    assert out.size == (400, 200)
    assert out.getpixel((200, 100)) == RED, "centred"
    assert out.getpixel((10, 100)) == (255, 255, 255)


def test_bad_input_is_refused():
    p = product()
    with pytest.raises(ValueError):
        bc.compose(p.convert("RGB"))
    for bad in (dict(background="neon"), dict(shadow="glow"), dict(shadow_opacity=1.5), dict(size=(0, 10)), dict(size=(5000, 10)), dict(background="solid", color=(1, 2)),
                dict(background="solid", color=(1, 2, 300)), dict(background="solid", color=(1, 2, True))):
        with pytest.raises(ValueError):
            bc.compose(p, **bad)


def test_a_fully_transparent_product_gives_just_the_background_without_crashing():
    empty = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    out = bc.compose(empty, "solid", color=(9, 9, 9), shadow="drop", reflection=True)
    assert out.getpixel((10, 10)) == (9, 9, 9) and set(out.getdata()) == {(9, 9, 9)}


def test_the_whole_pipeline_cut_out_then_compose_replaces_the_background():
    case = next(c for c in bg.evaluation_set() if c["name"].startswith("gray-ellipse"))
    cut = bg.remove_background(case["image"], "auto", feather=0)
    out = bc.compose(cut, "white", shadow="none")
    assert out.getpixel((3, 3)) == (255, 255, 255), "the grey backdrop became white"
    assert out.getpixel((80, 80)) == case["image"].convert("RGB").getpixel((80, 80)), "the product kept its own colours"
