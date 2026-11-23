"""D-2 (answer 73): a full-body PHOTO of a person -> body proportions -> own3d mannequin measurements, so a library photo model can become a 3D person. Own code (Pillow only), route (C).

What it does (everything is an ESTIMATE and says so):
  1. cut-out the person (classical ``bg_removal``), take the bounding box -> body height in pixels (head top to feet);
  2. read the silhouette width of the person's CENTRAL run at the chest / waist / hip rows (shares of the height the own3d body is built with: 0.70 / 0.60 / 0.52 of the height from the feet);
  3. the width / height ratio times the HEIGHT YOU GIVE (a photo has no scale: ``height_cm`` or the sex default 166 / 178 cm) is the half-width; the depth is taken from the preset's own
     depth / width ratio (a front photo says nothing about depth); the ellipse perimeter is the circumference -> ``chest_cm, waist_cm, hips_cm`` for ``base_models`` (clamped to its limits);
  4. skin colour and hair are NOT read here: the screen already passes its own ``sk`` / ``hs`` values.
Refused / warned: no person found, the person touches the picture edge (``PHOTO_BODY_CLIPPED``), arms fused with the torso at the chest or waist row (widths are then OVER-estimated: warning), a
picture that is not a standing front view (width/height ratio of the person outside 0.12..0.6: ``PHOTO_BODY_POSE``).
Honest limits: tested only on SYNTHETIC photos (rendered own3d mannequins, a closed loop: the answer is built into the picture); real photos of people - clothes, hair, perspective, poses,
shoes, shadows - are NOT tested (미실행). Loose clothing widens the silhouette: the numbers are of the DRESSED person. No side photo: depth is a preset assumption.
"""
from __future__ import annotations

import io
import math
from typing import Any

from PIL import Image

from app import base_models, bg_removal

ROWS = {"chest_cm": 0.70, "waist_cm": 0.60, "hips_cm": 0.52}          # share of the height above the feet where the own3d body has its chest / waist / widest hip
PRESET_KEY = {"chest_cm": "chest", "waist_cm": "waist", "hips_cm": "hip"}
DEFAULT_HEIGHT_CM = {"male": 178.0, "female": 166.0}
MIN_RATIO, MAX_RATIO = 0.12, 0.60                                      # person width / height of the bounding box
MIN_PERSON_SHARE = 0.02
MAX_SIDE = 1200
FUSED_JUMP = 1.7                                                       # a central run this many times wider than the run 3 % higher/lower on the same side: arms are fused
ARMS_AT_CHEST = 1.22                                                   # chest-row run this many times wider than the waist-row run: the arms hang against the chest (A-pose), so the chest width is NOT the torso's


class PhotoBodyError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _runs(row: list[bool]) -> list[tuple[int, int]]:
    out, start = [], None
    for x, v in enumerate(row):
        if v and start is None:
            start = x
        elif not v and start is not None:
            out.append((start, x - 1))
            start = None
    if start is not None:
        out.append((start, len(row) - 1))
    return out


def estimate(data: bytes | Image.Image, *, sex: str = "female", height_cm: float | None = None) -> dict[str, Any]:
    if sex not in base_models.SEXES:
        raise PhotoBodyError("PHOTO_BODY_SEX", "sex must be male or female")
    if height_cm is not None and not (base_models.LIMITS["height_cm"][0] <= float(height_cm) <= base_models.LIMITS["height_cm"][1]):
        raise PhotoBodyError("PHOTO_BODY_HEIGHT", "height_cm is out of range")
    try:
        img = data if isinstance(data, Image.Image) else Image.open(io.BytesIO(data))
        img = img.convert("RGB")
    except Exception as exc:  # noqa: BLE001
        raise PhotoBodyError("PHOTO_BODY_UNREADABLE", "the picture could not be read") from exc
    if max(img.size) > MAX_SIDE:
        img.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)
    w, h = img.size
    mask = bg_removal.foreground_mask(img, "auto").convert("L").point(lambda v: 255 if v > 127 else 0)
    box = mask.getbbox()
    if box is None or sum(1 for v in mask.getdata() if v) < MIN_PERSON_SHARE * w * h:
        raise PhotoBodyError("PHOTO_BODY_NOT_FOUND", "no person was found in the picture")
    x0, y0, x1, y1 = box
    if x0 <= 1 or y0 <= 1 or x1 >= w - 2 or y1 >= h - 2:
        raise PhotoBodyError("PHOTO_BODY_CLIPPED", "the person touches the edge of the picture: the whole body must be inside")
    height_px, width_px = y1 - y0 + 1, x1 - x0 + 1
    ratio = width_px / height_px
    if not MIN_RATIO <= ratio <= MAX_RATIO:
        raise PhotoBodyError("PHOTO_BODY_POSE", "this does not look like a standing front view of one person")
    px = mask.load()
    # the body axis: the centre of the silhouette at the torso rows (arms hang symmetrically beside it)
    torso_rows = range(int(y1 - 0.75 * height_px), int(y1 - 0.45 * height_px))
    xs = [sum(x * (1 if px[x, y] else 0) for x in range(x0, x1 + 1)) / max(1, sum(1 for x in range(x0, x1 + 1) if px[x, y])) for y in torso_rows if any(px[x, y] for x in range(x0, x1 + 1))]
    cx = sum(xs) / len(xs) if xs else (x0 + x1) / 2
    warnings: list[str] = []
    widths: dict[str, float] = {}
    for key, share in ROWS.items():
        y = int(round(y1 - share * height_px))
        row = [bool(px[x, y]) for x in range(w)]
        run = next((r for r in _runs(row) if r[0] <= cx <= r[1]), None)
        if run is None:
            raise PhotoBodyError("PHOTO_BODY_POSE", "the body axis does not cross the silhouette: not a standing front view")
        width = run[1] - run[0] + 1
        near = [next((r for r in _runs([bool(px[x, yy]) for x in range(w)]) if r[0] <= cx <= r[1]), None) for yy in (int(y - 0.03 * height_px), int(y + 0.03 * height_px))]
        if any(n is not None and (n[1] - n[0] + 1) * FUSED_JUMP < width for n in near):
            warnings.append(f"{key}: the silhouette is much wider here than just above or below it - arms may touch the body, so this width is probably OVER-estimated")
        widths[key] = width
    h_cm = float(height_cm) if height_cm is not None else DEFAULT_HEIGHT_CM[sex]
    preset = base_models._fit_measurements(base_models.PRESETS[sex], {"height_cm": h_cm})
    out: dict[str, float] = {"height_cm": round(h_cm, 1)}
    chest_from_waist = widths["chest_cm"] > ARMS_AT_CHEST * widths["waist_cm"]
    if chest_from_waist:
        base = base_models.preset_circumferences_cm(sex)
        widths = {**widths, "chest_cm": widths["waist_cm"] * base["chest"] / base["waist"]}      # the preset's own chest/waist proportion applied to the waist width
        warnings.append("chest_cm: the arms hang against the chest in this photo, so the chest width cannot be read; it was taken from the waist with the preset's chest/waist proportion (a PRIOR, not a measurement)")
    for key, wpx in widths.items():
        a_m = (wpx / height_px) * (h_cm / 100.0) / 2.0
        a0, b0 = preset[PRESET_KEY[key]]
        b_m = a_m * (b0 / a0)
        lo, hi = base_models.LIMITS[key]
        value = base_models._perimeter_cm(a_m, b_m)
        if not lo <= value <= hi:
            warnings.append(f"{key}: {value:.0f} cm is outside the mannequin's range {lo:g}..{hi:g} and was clamped")
        out[key] = round(min(max(value, lo), hi), 1)
    if height_cm is None:
        warnings.append(f"height_cm was not given: the default {h_cm:g} cm for a {sex} body was used (a photo has no scale)")
    return {"estimated": True, "label": "ESTIMATED from one front photo: dressed silhouette, depth assumed, height " + ("given" if height_cm is not None else "default"),
            "sex": sex, "measurements": out, "silhouette_px": {"height": height_px, "width_at": widths, "axis_x": round(cx, 1)}, "warnings": warnings,
            "chest_from_prior": chest_from_waist, "assumptions": ["standing, facing the camera, whole body inside the picture", "arms away from the torso at chest and waist", "depth = the preset's depth/width ratio", "the numbers are of the DRESSED person"]}


__all__ = ["estimate", "PhotoBodyError"]
