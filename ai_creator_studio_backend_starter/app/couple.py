"""R-ENGINE-16 stage 1: a COUPLE (two people standing side by side) outfit pipeline, own code first.

Image side (``split_people`` -> per-person runner -> ``composite``):
  1. foreground mask (classical, ``bg_removal``), then a vertical split at the emptiest column near the foreground's centre of mass; ``overlap_px`` = (rows where the foreground runs
     unbroken across a band around the split) x (band width): arms around each other, hands - where one person's pixels cannot be told from the other's;
  2. each person is cut out as an RGBA crop (the other person's pixels removed) and handed to a ``runner`` (own3d mock or an approved evaluation model; injected, never called here);
  3. ``composite`` puts the results back at their original place with a feathered edge;
  4. QC: ``overlap_px`` is recorded and ``COUPLE_OVERLAP_TOO_LARGE`` refuses a picture whose overlap exceeds ``MAX_OVERLAP_SHARE`` of the smaller person (PROPOSAL, not tuned on real photos).
3D side (``scene_two``): two base models placed side by side, one fitted garment set each (``render3d_scene.build_layers``), renderable from any angle.
Honest limits: side-by-side couples only (stage 1); people who touch strongly are refused, not separated; the split is a straight vertical line, so crossed limbs, one person partly behind the
other, children held in arms, or a very different height are NOT handled; tested on SYNTHETIC two-figure images and the mannequin scene, not on real couple photos (미실행).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from PIL import Image, ImageFilter

from app import bg_removal, render3d_scene
from app.render3d_soft import Triangle

MAX_OVERLAP_SHARE = 0.04          # PROPOSAL: overlap pixels / the smaller person's pixels above which the picture is refused
BAND_SHARE = 0.04                 # half-width of the overlap band, as a share of the picture width
MIN_PERSON_SHARE = 0.03           # a side with less foreground than this share of the picture is "no person"
FEATHER = 2.0
GAP_X = 0.62                      # metres between the two mannequins' centres in the 3D scene


class CoupleError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass
class Person:
    side: str
    box: tuple[int, int, int, int]
    mask: Image.Image           # L, full picture size, this person only
    area: int


def split_people(img: Image.Image) -> dict:
    rgb = img.convert("RGB")
    w, h = rgb.size
    mask = bg_removal.foreground_mask(rgb, "auto").convert("L").point(lambda v: 255 if v > 127 else 0)
    px = mask.load()
    cols = [sum(1 for y in range(h) if px[x, y]) for x in range(w)]
    total, run, half = sum(cols), 0, 0
    for x, c in enumerate(cols):                      # the split is searched around the foreground's centre of mass: two people of similar size balance there
        run += c
        if run >= total / 2:
            half = x
            break
    lo, hi = max(1, half - int(w * 0.08)), min(w - 1, half + int(w * 0.08))
    cut = min(range(lo, hi), key=lambda x: (cols[x], abs(x - w // 2)))
    band = max(2, int(w * BAND_SHARE))
    x0, x1 = max(0, cut - band), min(w - 1, cut + band)
    contact_rows = sum(1 for y in range(h) if all(px[x, y] for x in range(x0, x1 + 1)))     # rows where the foreground runs unbroken across the split band: the people touch there
    overlap = contact_rows * (x1 - x0 + 1)
    people = []
    for side, (a, b) in (("left", (0, cut)), ("right", (cut, w))):
        m = Image.new("L", (w, h), 0)
        m.paste(mask.crop((a, 0, b, h)), (a, 0))
        box = m.getbbox()
        area = sum(1 for v in m.getdata() if v)
        people.append(Person(side, box or (a, 0, a, 0), m, area))
    smaller = min(p.area for p in people) or 1
    share = overlap / smaller
    if share <= MAX_OVERLAP_SHARE and min(p.area for p in people) < MIN_PERSON_SHARE * w * h:
        raise CoupleError("COUPLE_PERSON_NOT_FOUND", "two people were not found: one side of the picture is (almost) empty")
    return {"cut_x": cut, "people": people, "overlap_px": overlap, "overlap_share": share, "picture": (w, h)}


def check_overlap(result: dict) -> None:
    if result["overlap_share"] > MAX_OVERLAP_SHARE:
        raise CoupleError("COUPLE_OVERLAP_TOO_LARGE", f"the two people overlap too much ({result['overlap_px']} px, {result['overlap_share']:.1%} of the smaller person)")


def cut_out(img: Image.Image, person: Person, margin: int = 4) -> tuple[Image.Image, tuple[int, int]]:
    """RGBA crop of one person (the other side's pixels transparent) and its top-left corner in the picture."""
    x0, y0, x1, y1 = person.box
    x0, y0, x1, y1 = max(0, x0 - margin), max(0, y0 - margin), min(img.width, x1 + margin), min(img.height, y1 + margin)
    out = img.convert("RGBA").crop((x0, y0, x1, y1))
    out.putalpha(person.mask.crop((x0, y0, x1, y1)).filter(ImageFilter.GaussianBlur(FEATHER)))
    return out, (x0, y0)


Runner = Callable[[Image.Image, str], Image.Image]


def run_couple(img: Image.Image, runner: Runner, *, enforce_overlap: bool = True) -> dict:
    """Split, refuse a too-large overlap, run ``runner(person_rgba_crop, side)`` for each person (same size back) and composite. Returns the picture and the QC numbers."""
    split = split_people(img)
    if enforce_overlap:
        check_overlap(split)
    out = img.convert("RGB").copy()
    for p in split["people"]:
        crop, (x0, y0) = cut_out(img, p)
        done = runner(crop, p.side).convert("RGBA")
        if done.size != crop.size:
            raise CoupleError("COUPLE_RUNNER_SIZE", "the per-person runner must return a picture of the same size")
        done.putalpha(crop.getchannel("A"))
        out.paste(done.convert("RGB"), (x0, y0), done.getchannel("A"))
    return {"image": out, "cut_x": split["cut_x"], "overlap_px": split["overlap_px"], "overlap_share": split["overlap_share"],
            "people": [{"side": p.side, "box": list(p.box), "area_px": p.area} for p in split["people"]]}


def scene_two(sex_left: str, sex_right: str, kinds_left: list[str], kinds_right: list[str], measurements_left: dict[str, float] | None = None,
              measurements_right: dict[str, float] | None = None) -> tuple[list[Triangle], list[dict]]:
    """(all triangles, fitting reports per person) of two mannequins side by side, each with its own garments; the left one stands at x = -GAP_X/2, the right one at +GAP_X/2."""
    triangles, reports = [], []
    for sex, kinds, meas, dx in ((sex_left, kinds_left, measurements_left, -GAP_X / 2), (sex_right, kinds_right, measurements_right, GAP_X / 2)):
        body, layers, rep = render3d_scene.build_layers(sex, meas, kinds)
        tris = body + [t for _, g, _ in layers for t in g]
        triangles += [(tuple((c[0] + dx, c[1], c[2]) for c in t[0]), t[1], t[2]) for t in tris]      # type: ignore[misc]
        reports.append({"side": "left" if dx < 0 else "right", "garments": rep})
    return triangles, reports


__all__ = ["split_people", "run_couple", "scene_two", "CoupleError", "check_overlap", "cut_out"]
