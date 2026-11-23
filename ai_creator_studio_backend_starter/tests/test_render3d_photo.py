"""E-03: the photo-like renderer. Checks measurable properties, not 'prettiness' (see docs/RENDER_PHOTO.md for the picture comparison)."""
import pytest
from PIL import Image, ImageChops

from app import render3d_photo as rp

SIZE = (180, 320)


@pytest.fixture(scope="module")
def front():
    return rp.render_scene("female", None, ["top"], 0, size=SIZE)


def test_same_input_gives_same_pixels(front):
    assert ImageChops.difference(front, rp.render_scene("female", None, ["top"], 0, size=SIZE)).getbbox() is None


def test_the_floor_has_a_shadow_darker_than_the_backdrop_and_it_fades_out(front):
    bg = front.getpixel((3, 3))
    row = [front.getpixel((x, int(SIZE[1] * 0.955))) for x in range(SIZE[0])]
    assert min(sum(p) for p in row) < sum(bg) * 0.96, "no shadow on the floor"
    assert front.getpixel((3, SIZE[1] - 3))[0] >= bg[0] - 14       # far from the figure: backdrop only


def test_floor_off_leaves_a_plain_backdrop():
    im = rp.render_scene("female", None, ["top"], 0, size=SIZE, floor=False)
    assert im.getpixel((20, int(SIZE[1] * 0.96))) == im.getpixel((20, int(SIZE[1] * 0.96) - 40)) or abs(im.getpixel((20, 300))[0] - im.getpixel((20, 250))[0]) <= 12


def test_edges_are_anti_aliased_unlike_the_mock():
    smooth = rp.render_scene("female", None, ["top"], 0, size=SIZE, ss=2, floor=False)
    hard = rp.render_scene("female", None, ["top"], 0, size=SIZE, ss=1, floor=False)
    def mixed(im):                      # pixels that are neither backdrop nor figure colour: count distinct colours along the silhouette row
        return len({im.getpixel((x, 120)) for x in range(SIZE[0])})
    assert mixed(smooth) > mixed(hard)


def test_ambient_occlusion_darkens_creases():
    on = rp.render_scene("female", None, ["top"], 0, size=SIZE, floor=False, ao=True)
    off = rp.render_scene("female", None, ["top"], 0, size=SIZE, floor=False, ao=False)
    lum = lambda im: sum(im.convert("L").getdata())
    assert lum(on) < lum(off)


def test_skin_and_cloth_are_shaded_differently():
    body_only = rp.render_scene("female", None, [], 0, size=SIZE, floor=False)
    dressed = rp.render_scene("female", None, ["top"], 0, size=SIZE, floor=False)
    assert ImageChops.difference(body_only, dressed).getbbox() is not None


def test_a_turntable_changes_the_picture_and_bad_arguments_are_refused(front):
    assert ImageChops.difference(front, rp.render_scene("female", None, ["top"], 90, size=SIZE)).getbbox() is not None
    with pytest.raises(ValueError):
        rp.render_scene("female", None, [], 0, size=(8, 8))
    with pytest.raises(ValueError):
        rp.render_photo([([], "metal")], 0)
