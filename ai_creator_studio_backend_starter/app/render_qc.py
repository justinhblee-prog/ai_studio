"""R-ENGINE-11: a render-based check of a fitted garment ("render-cuts.v1"), the picture-side sibling of the geometry checker ``app/fit_check.py`` (R-ENGINE-06).

For each angle it draws the scene three ways (all with the software renderer, same framing; the label pictures skip back faces, so the inside of a garment's neck or hem opening is not counted): the garments ALONE, body + garments with every object painted in a flat label colour, and the
normal shaded body + garments. From these it measures, per garment and angle:
  * ``visible_share`` - (judged from the FRONT and BACK views only, see ``frontal``; a garment without sleeves is judged against the body without its arms, see ``check_cuts``) silhouette IoU of "the garment's pixels in the full scene" against "the garment's pixels when drawn without the body" (the second contains the first, so the IoU is
    the share of the garment that is still in front of the body). Less than 1 means the BODY pokes through the garment somewhere; garments hidden by another garment on purpose (a jacket over a
    top) are compared with the garments-only picture, so they are not counted against it;
  * ``colour_distance`` - how far the garment's mean colour in the shaded picture is from the colour it was asked to have (chromaticity, so the light does not matter);
and from the fitting report: ``penetration`` (points of the garment found inside the body cross-section, always 0 when a fit was accepted).
Side views are RECORDED but not judged: the sample garments have no sleeves (except the jacket), so the body's own arms legitimately hide part of a torso garment seen from the side.
Nothing is invented: the five items of the design's later photo review (logo, text, pattern, hands, length) are ``None`` here because this geometry-and-colour check cannot judge them, and a
garment with nothing visible to compare gets ``passed: None``. The thresholds are PROPOSALS (the design window decides). A failed check is a finding to record, not a verdict about how the
garment looks or whether it fits a real person.
"""
from __future__ import annotations

import math
from typing import Any, Sequence

from PIL import Image, ImageStat

from app import render3d_soft as soft

METHOD = "render-cuts.v1"
SIZE = (144, 256)
MIN_VISIBLE_SHARE = 0.98        # proposal
MAX_COLOUR_DISTANCE = 0.05      # proposal, on unit-length RGB vectors
NOT_JUDGED = ("logo", "text", "pattern", "hands", "length")
BODY_LABEL = 1
Layer = tuple[str, list[soft.Triangle], tuple[int, int, int]]          # (kind, triangles, the colour the garment was asked to have)


def is_frontal(angle: float) -> bool:
    """True for a view within 30 degrees of the front (0) or the back (180)."""
    return abs(math.sin(math.radians(angle))) <= 0.5


def _label(tris: list[soft.Triangle], number: int) -> list[soft.Triangle]:
    return [(corners, normals, (number, 0, 0)) for corners, normals, _ in tris]


def _counts(image: Image.Image) -> list[int]:
    return image.getchannel("R").histogram()


def _unit(rgb: Sequence[float]) -> tuple[float, float, float]:
    length = math.sqrt(sum(c * c for c in rgb)) or 1.0
    return (rgb[0] / length, rgb[1] / length, rgb[2] / length)


SLEEVED = ("jacket",)           # garment kinds that have sleeves of their own: they are judged against the whole body


def _pass(body: list[soft.Triangle], garments: list[Layer], angles: Sequence[int], size: tuple[int, int], height: float):
    """For every angle: ({garment index: (reference pixels, visible pixels)}, the label picture, the shaded picture)."""
    black = (0, 0, 0)
    labelled = [(kind, _label(tris, BODY_LABEL + 1 + k), colour) for k, (kind, tris, colour) in enumerate(garments)]
    garment_only = [t for _, tris, _ in labelled for t in tris]
    everything = body + [t for _, tris, _ in garments for t in tris]
    out = {}
    for angle in angles:
        alone = _counts(soft.render(garment_only, angle, size, background=black, height_m=height, flat=True, cull_back=True)) if garment_only else [0] * 256
        labels = soft.render(_label(body, BODY_LABEL) + garment_only, angle, size, background=black, height_m=height, flat=True, cull_back=True)
        full = _counts(labels)
        shaded = soft.render(everything, angle, size, background=black, height_m=height)
        out[angle] = ({k: (alone[BODY_LABEL + 1 + k], full[BODY_LABEL + 1 + k]) for k in range(len(garments))}, labels, shaded)
    return out


def check_cuts(body: list[soft.Triangle], garments: list[Layer], angles: Sequence[int], *, penetrations: dict[str, int] | None = None, size: tuple[int, int] = SIZE,
               min_visible_share: float = MIN_VISIBLE_SHARE, max_colour_distance: float = MAX_COLOUR_DISTANCE, body_without_arms: list[soft.Triangle] | None = None) -> dict[str, Any]:
    """The report. ``penetrations`` maps a garment kind to the count the fitting reported (None when unknown).
    ``body_without_arms`` (R-ENGINE-09b): a garment WITHOUT sleeves is judged against the body minus its arms, because in the A-pose the hanging arm overlaps the garment's side edge by about two
    centimetres in front of it - that is the arm in front, not the body poking through the garment. The number against the whole body is kept next to it as ``visible_share_incl_arms``."""
    everything = body + [t for _, tris, _ in garments for t in tris]
    height = soft.height_of(everything)
    whole = _pass(body, garments, angles, size, height)
    bare = _pass(body_without_arms, garments, angles, size, height) if body_without_arms is not None and any(kind not in SLEEVED for kind, _, _ in garments) else None
    reports: list[dict[str, Any]] = [{"kind": kind, "occluder": "body" if (kind in SLEEVED or bare is None) else "body_without_arms", "views": []} for kind, _, _ in garments]
    for angle in angles:
        counts, labels, shaded = whole[angle]
        for k, (kind, tris, colour) in enumerate(garments):
            number = BODY_LABEL + 1 + k
            reference_w, visible_w = counts[k]
            judged_ref, judged_vis = (bare[angle][0][k] if reports[k]["occluder"] == "body_without_arms" else (reference_w, visible_w))
            view: dict[str, Any] = {"angle": angle, "frontal": is_frontal(angle), "reference_pixels": judged_ref, "visible_pixels": judged_vis,
                                    "visible_share": round(judged_vis / judged_ref, 4) if judged_ref else None,
                                    "visible_share_incl_arms": round(visible_w / reference_w, 4) if reference_w else None, "colour_distance": None}
            if visible_w:
                mask = labels.getchannel("R").point(lambda v, n=number: 255 if v == n else 0)
                mean = ImageStat.Stat(shaded, mask).mean
                view["colour_distance"] = round(math.dist(_unit(mean), _unit(colour)), 4)
            reports[k]["views"].append(view)
    for report, (kind, _, _) in zip(reports, garments):
        shares = [v["visible_share"] for v in report["views"] if v["frontal"] and v["visible_share"] is not None]
        distances = [v["colour_distance"] for v in report["views"] if v["colour_distance"] is not None]
        report["visible_share_min"] = min(shares) if shares else None
        report["colour_distance_max"] = max(distances) if distances else None
        report["penetration_points"] = None if penetrations is None else penetrations.get(kind)
        checks = [c for c in (None if report["visible_share_min"] is None else report["visible_share_min"] >= min_visible_share,
                              None if report["colour_distance_max"] is None else report["colour_distance_max"] <= max_colour_distance,
                              None if report["penetration_points"] is None else report["penetration_points"] == 0) if c is not None]
        report["passed"] = all(checks) if checks else None
    judged = [r["passed"] for r in reports if r["passed"] is not None]
    return {"method": METHOD, "passed": (all(judged) if judged else None), "size": list(size), "angles": list(angles), "garments": reports,
            "thresholds": {"min_visible_share": min_visible_share, "max_colour_distance": max_colour_distance, "source": "proposal"},
            "not_judged": {item: None for item in NOT_JUDGED},
            "scope": "silhouette visibility, colour and fitting-penetration of the in-house render; not a review of how the garment looks or whether it fits a real person"}
