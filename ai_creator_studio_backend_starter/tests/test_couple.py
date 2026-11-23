"""R-ENGINE-16 stage 1: couple pipeline on SYNTHETIC two-figure pictures (overlap none / small / large) and the 3D two-person scene from five angles."""
import pytest
from PIL import Image, ImageChops, ImageDraw

from app import couple, render3d_soft


def figure(draw, cx, colour, w=70, top=40, bottom=330):
    draw.ellipse([cx - 28, top, cx + 28, top + 56], fill=colour)                       # head
    draw.rectangle([cx - w // 2, top + 60, cx + w // 2, bottom], fill=colour)           # body + legs as one block


def picture(gap, bridge=0):
    """Two figures; ``gap`` > 0 leaves a clean gap, ``gap`` < 0 makes them overlap by that many pixels."""
    img = Image.new("RGB", (420, 360), (235, 235, 232))
    d = ImageDraw.Draw(img)
    centre = 210
    half = 35 + gap / 2
    figure(d, int(centre - half), (190, 60, 70))
    figure(d, int(centre + half), (50, 90, 170))
    if bridge:                                                                           # a hand reaching across the gap
        d.rectangle([int(centre - half), 200, int(centre + half), 200 + bridge], fill=(190, 60, 70))
    return img


def tint(crop, side):
    out = Image.new("RGBA", crop.size, (20, 160, 80, 255) if side == "left" else (230, 180, 30, 255))
    return out


def test_no_overlap_splits_cleanly_and_each_person_is_found():
    r = couple.split_people(picture(30))
    assert r["overlap_px"] == 0 and 180 < r["cut_x"] < 240
    left, right = r["people"]
    assert left.box[2] <= r["cut_x"] <= right.box[0] and left.area > 5000 and right.area > 5000
    couple.check_overlap(r)


def test_a_small_overlap_is_recorded_and_accepted():
    r = couple.split_people(picture(30, bridge=6))
    assert 0 < r["overlap_px"] and r["overlap_share"] <= couple.MAX_OVERLAP_SHARE          # recorded and under the limit
    out = couple.run_couple(picture(30, bridge=6), tint)
    assert out["overlap_px"] == r["overlap_px"]


def test_a_large_overlap_is_refused_with_the_catalogue_code():
    with pytest.raises(couple.CoupleError) as err:
        couple.run_couple(picture(-40), tint)
    with pytest.raises(couple.CoupleError):
        couple.run_couple(picture(30, bridge=60), tint)
    assert err.value.code == "COUPLE_OVERLAP_TOO_LARGE"


def test_each_person_goes_through_the_runner_alone_and_is_put_back_in_place():
    out = couple.run_couple(picture(30), tint)
    img = out["image"]
    assert img.size == (420, 360)
    assert img.getpixel((int(210 - 65), 200))[:3] == (20, 160, 80) and img.getpixel((int(210 + 65), 200))[:3] == (230, 180, 30)
    assert img.getpixel((5, 5)) == (235, 235, 232), "the background is untouched"
    assert len(out["people"]) == 2


def test_an_empty_side_is_not_a_couple():
    img = Image.new("RGB", (420, 360), (235, 235, 232))
    figure(ImageDraw.Draw(img), 100, (190, 60, 70))
    with pytest.raises(couple.CoupleError) as err:
        couple.split_people(img)
    assert err.value.code == "COUPLE_PERSON_NOT_FOUND"


def test_deterministic():
    a, b = couple.run_couple(picture(30), tint)["image"], couple.run_couple(picture(30), tint)["image"]
    assert ImageChops.difference(a, b).getbbox() is None


def test_two_mannequins_side_by_side_render_from_five_angles_with_their_own_garments():
    tris, reports = couple.scene_two("female", "male", ["top", "bottom"], ["jacket"])
    assert [r["side"] for r in reports] == ["left", "right"] and len(reports[0]["garments"]) == 2 and len(reports[1]["garments"]) == 1
    xs = [c[0] for t in tris for c in t[0]]
    assert min(xs) < -0.3 and max(xs) > 0.3
    h = render3d_soft.height_of(tris)
    shots = [render3d_soft.render(tris, a, (300, 400), height_m=h) for a in (0, 45, 90, 180, 270)]
    assert all(s.getbbox() for s in shots)
    assert ImageChops.difference(shots[0], shots[2]).getbbox() is not None
    bg = shots[0].getpixel((2, 2))
    assert sum(1 for v in shots[0].getdata() if v != bg) > 2000
