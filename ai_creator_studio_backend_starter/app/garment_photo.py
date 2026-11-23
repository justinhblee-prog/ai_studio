"""R-ENGINE-15: a flat-lay PHOTO of a garment -> estimated dimensions + colour -> a fit-ready garment.v1 (route A of the R-ENGINE-12 memo).

No model, no network, Pillow only (the backend has no numpy / OpenCV). The photo must follow the capture rules (``CAPTURE_RULES``): a plain background,
the garment laid flat and fully inside the picture, a reference object (a bank card or an A4 sheet) lying NEXT TO it (not under it), camera straight above.
  1. the background is removed with the classical cut-out of ``bg_removal`` (``auto`` = flood / gradient);
  2. the cut-out is split into connected pieces; the garment is the biggest, the reference object is the piece that is a good rectangle of the right aspect;
  3. pixels per cm come from the reference object's AREA (sub-pixel, rotation independent);
  4. the garment's outline is measured row by row (width in cm) and read at fixed heights of the garment per kind (``RULES``);
  5. the colour is a small k-means over the garment's inner pixels.
EVERYTHING is an ESTIMATE and is labelled so: the dimensions are flat widths x 2 (the garment-chart convention), not tape-measure values.
"""
from __future__ import annotations

import functools
import io
import math
import random
from array import array
from typing import Any

from PIL import Image, ImageChops, ImageFilter, ImageOps

from app import base_models, bg_removal, garments

REFERENCES = {"card": (8.560, 5.398, 0.998), "a4": (29.7, 21.0, 1.0)}   # long side cm, short side cm, area factor (a bank card has 3.18 mm round corners: ~0.2 % less area)
KINDS = garments.KINDS
MAX_SIDE = 900                       # the photo is shrunk to this longest side before any pixel work
MAX_BYTES = 12_000_000
MAX_PIXELS = 40_000_000
MIN_PIECE_SHARE = 0.0004             # pieces smaller than this share of the picture are dust
ASPECT_TOLERANCE = 0.12              # the reference piece's long/short ratio may differ from the real object's by this much
MIN_FILL = 0.80                      # share of its own minimal rectangle a piece must fill to count as a rectangle
CONSISTENCY_WARN = 0.06              # the two px/cm values (from the long and the short side) differ by more than this: tilted camera or object
MIN_GARMENT_SHARE = 0.04
LOW_CONTRAST = 45.0                 # the reference piece differs from the flattened background by less than this (max channel): warn
EDGE_OBJECT_DIFF = 45               # a border pixel differing from the border's median colour by more than this is an object, not background
EDGE_OBJECT_SHARE = 0.01            # ... when this share of the border is such
MERGE_DISTANCE = 45.0               # colour clusters closer than this (RGB distance) are one colour
MAX_OTHER_SHARE = 0.15              # other sizeable pieces (not the reference) may add up to this share of the garment's area
DENOISE_RADIUS = 1.5                # the picture is blurred this much before the cut-out (sensor noise must not speckle the background)
FLAT_GRID = (64, 48)                # the lighting model is fitted on a picture this small
FLAT_KEEP = (45.0, 30.0, 20.0, 14.0, 14.0)   # per round: pixels this close to the current background model (max channel) count as background in the next round (wide first: the ring alone extrapolates badly)
FLAT_WARN = 24.0                    # the lighting differs by more than this across the picture: say so
SHADOW_NEUTRAL = 10                 # a shadow darkens all channels alike: per-channel differences up to this count as neutral
SHADOW_DEPTH = (6, 90)              # ... and it is this many levels darker than the flattened background (128)
SHADOW_GIVE_UP = 0.35               # if 'shadow' would remove more than this share of the cut-out, the garment itself is neutral grey: keep everything
EDGE_BIAS_PX = 1.4                   # the classical cut-out grows every edge by about this many pixels (measured on the synthetic set; on real photos: NOT yet measured)
CAPTURE_RULES = ("plain background, no pattern; garment laid flat, fully inside the picture", "a bank card (85.6 x 54 mm) or an A4 sheet lying beside the garment, not under it",
                 "camera straight above, no zoomed wide-angle edge; even light, no strong shadow")
# Where each width is read, as (from, to) shares of the garment's height measured from its top edge. Widths are flat widths; circumference = 2 x width.
RULES = {
    "top": {"chest_cm": (0.45, 0.60), "waist_cm": (0.78, 0.90)},
    "jacket": {"chest_cm": (0.45, 0.60), "waist_cm": (0.78, 0.90)},
    "bottom": {"waist_cm": (0.02, 0.06), "hips_cm": (0.12, 0.22)},
    "skirt": {"waist_cm": (0.02, 0.06), "hips_cm": (0.25, 0.35)},
    "dress": {"chest_cm": (0.15, 0.28), "waist_cm": (0.38, 0.50), "hips_cm": (0.55, 0.68)},
}
SLEEVE_BAND = (0.0, 0.35)            # where a top's sleeves stick out
SLEEVE_MIN_EXCESS = 1.12             # widest row must exceed the chest width by this factor to count as sleeves


class GarmentPhotoError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code, self.message = code, message


# ------------------------------------------------------------------------------------------------------------------ pixels
def _load(data: bytes) -> Image.Image:
    if len(data) > MAX_BYTES:
        raise GarmentPhotoError("PHOTO_TOO_LARGE", "the photo file is too large")
    try:
        img = Image.open(io.BytesIO(data))
        width, height = img.size
    except Exception as exc:                                               # noqa: BLE001 - anything Pillow cannot read
        raise GarmentPhotoError("PHOTO_UNREADABLE", "the file is not a picture this server can read") from exc
    if width * height > MAX_PIXELS:
        raise GarmentPhotoError("PHOTO_TOO_LARGE", "the photo has too many pixels")
    img = ImageOps.exif_transpose(img).convert("RGB")
    longest = max(img.size)
    if longest > MAX_SIDE:
        img = img.resize((max(1, round(img.width * MAX_SIDE / longest)), max(1, round(img.height * MAX_SIDE / longest))), Image.LANCZOS)
    return img


def _solve(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
    """Gauss-Jordan for A x = B (A square, B has one column per channel)."""
    n = len(a)
    m = [row[:] + brow[:] for row, brow in zip(a, b)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(m[r][col]))
        m[col], m[piv] = m[piv], m[col]
        div = m[col][col] or 1e-12
        m[col] = [v / div for v in m[col]]
        for r in range(n):
            if r != col and m[r][col]:
                f = m[r][col]
                m[r] = [v - f * c for v, c in zip(m[r], m[col])]
    return [row[n:] for row in m]


def _flatten(img: Image.Image) -> tuple[Image.Image, float]:
    """Remove smooth lighting (vignette, a lamp on one side) so the classical cut-out sees a flat background: fit a cubic surface per channel to the pixels
    that look like background (start with the outer ring, then keep what stays near the fit while the tolerance narrows), subtract it. Returns (flattened picture, largest lighting difference found)."""
    gw, gh = FLAT_GRID
    small = img.resize((gw, gh), Image.BOX)
    px = list(_values(small))
    basis = []
    for j in range(gh):
        for i in range(gw):
            x, y = 2 * i / (gw - 1) - 1, 2 * j / (gh - 1) - 1
            basis.append((1.0, x, y, x * x, x * y, y * y, x ** 3, x * x * y, x * y * y, y ** 3))
    ring = [k for k, (_, x, y, *_r) in enumerate(basis) if max(abs(x), abs(y)) > 0.78]
    med = [sorted(px[k][c] for k in ring)[len(ring) // 2] for c in range(3)]
    use = [k for k in ring if max(abs(px[k][c] - med[c]) for c in range(3)) < FLAT_KEEP[0]] or ring        # a garment touching the picture edge must not pull the first fit
    coef: list[list[float]] = []
    for tol in (None,) + FLAT_KEEP:
        ata = [[sum(basis[k][i] * basis[k][j] for k in use) for j in range(10)] for i in range(10)]
        atb = [[sum(basis[k][i] * px[k][c] for k in use) for c in range(3)] for i in range(10)]
        coef = _solve(ata, atb)
        fit = [tuple(sum(coef[i][c] * basis[k][i] for i in range(10)) for c in range(3)) for k in range(len(basis))]
        if tol is None:
            continue
        keep = [k for k in range(len(basis)) if max(abs(fit[k][c] - px[k][c]) for c in range(3)) < tol]
        if len(keep) < 60:
            break
        use = keep
    ata = [[sum(basis[k][i] * basis[k][j] for k in use) for j in range(10)] for i in range(10)]          # the last selection gets its own fit
    atb = [[sum(basis[k][i] * px[k][c] for k in use) for c in range(3)] for i in range(10)]
    coef = _solve(ata, atb)
    fit = [tuple(sum(coef[i][c] * basis[k][i] for i in range(10)) for c in range(3)) for k in range(len(basis))]
    model = Image.new("RGB", (gw, gh))
    model.putdata([tuple(int(round(min(255.0, max(0.0, v)))) for v in f) for f in fit])
    spread = max(max(f[c] for f in fit) - min(f[c] for f in fit) for c in range(3))
    model = model.resize(img.size, Image.BICUBIC)
    flat = ImageChops.subtract(img, model, 1.0, 128)                      # (picture - lighting) + 128: a flat grey background, the garment keeps its difference from it
    return flat, spread


def _refuse_if_object_at_the_edge(flat: Image.Image) -> None:
    """The cut-out grows the background from the picture's border, so anything lying ON the border is taken for background. Check the border first."""
    w, h = flat.size
    px = flat.load()
    ring = [px[x, y] for x in range(w) for y in (0, 1, h - 2, h - 1)] + [px[x, y] for y in range(h) for x in (0, 1, w - 2, w - 1)]
    med = [sorted(p[c] for p in ring)[len(ring) // 2] for c in range(3)]
    off = sum(1 for p in ring if max(abs(p[c] - med[c]) for c in range(3)) > EDGE_OBJECT_DIFF)
    if off > EDGE_OBJECT_SHARE * len(ring):
        raise GarmentPhotoError("PHOTO_GARMENT_CLIPPED", "the garment (or the reference object) touches the edge of the picture: move the camera back so everything fits")


def _without_shadow(flat: Image.Image, mask: Image.Image) -> tuple[Image.Image, float]:
    """Take soft, neutral-coloured darkening out of the cut-out. Returns (mask, share of the cut-out removed). A neutral grey garment looks like a shadow:
    when more than ``SHADOW_GIVE_UP`` of the cut-out would go, nothing is removed (share is returned as -1)."""
    r, g, b = flat.split()
    neutral = ImageChops.multiply(ImageChops.difference(r, g).point(lambda v: 255 if v <= SHADOW_NEUTRAL else 0), ImageChops.difference(g, b).point(lambda v: 255 if v <= SHADOW_NEUTRAL else 0))
    lo, hi = SHADOW_DEPTH
    dark = flat.convert("L").point(lambda v: 255 if 128 - hi <= v <= 128 - lo else 0)
    shadow = ImageChops.multiply(neutral, dark)
    solid = mask.filter(ImageFilter.MedianFilter(5))                        # the share is judged on the solid part, not on stray noise specks
    removed = ImageChops.multiply(shadow, solid)
    before = sum(1 for v in _values(solid) if v >= 128) or 1
    share = sum(1 for v in _values(removed) if v >= 128) / before
    if share > SHADOW_GIVE_UP:
        return mask, -1.0
    return ImageChops.subtract(mask, shadow), share


def _pieces(mask: Image.Image) -> tuple[list[dict[str, Any]], int, int]:
    """4-connected pieces of the cut-out: [{area, bbox, pixels}], biggest first."""
    w, h = mask.size
    m = bytearray(1 if v >= 128 else 0 for v in _values(mask))
    out: list[dict[str, Any]] = []
    for start in range(w * h):
        if not m[start]:
            continue
        stack, pixels = [start], array("i")
        m[start] = 0
        x0 = x1 = start % w
        y0 = y1 = start // w
        while stack:
            p = stack.pop()
            pixels.append(p)
            y, x = divmod(p, w)
            if x < x0: x0 = x
            if x > x1: x1 = x
            if y < y0: y0 = y
            if y > y1: y1 = y
            if x > 0 and m[p - 1]: m[p - 1] = 0; stack.append(p - 1)
            if x < w - 1 and m[p + 1]: m[p + 1] = 0; stack.append(p + 1)
            if y > 0 and m[p - w]: m[p - w] = 0; stack.append(p - w)
            if y < h - 1 and m[p + w]: m[p + w] = 0; stack.append(p + w)
        out.append({"area": len(pixels), "bbox": (x0, y0, x1, y1), "pixels": pixels})
    out.sort(key=lambda piece: -piece["area"])
    return out, w, h


def _values(img: Image.Image):
    """Flat pixel values (Pillow 13 deprecates ``getdata``)."""
    return img.get_flattened_data() if hasattr(img, "get_flattened_data") else img.getdata()


def _span(values: list[float]) -> float:
    """Length of the range, ignoring the extreme 0.4 % at each end (a few stray noise pixels must not stretch it) and scaled back up."""
    ordered = sorted(values)
    k = int(0.004 * len(ordered))
    return (ordered[len(ordered) - 1 - k] - ordered[k]) / 0.992 + 1


def _rectangle(piece: dict[str, Any], w: int) -> dict[str, float]:
    """Principal-axis rectangle of a piece: its sides in px and how much of that rectangle the piece fills."""
    pix = piece["pixels"]
    n = len(pix)
    xs = [p % w for p in pix]
    ys = [p // w for p in pix]
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs) / n
    syy = sum((y - my) ** 2 for y in ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / n
    theta = 0.5 * math.atan2(2 * sxy, sxx - syy)
    c, s = math.cos(theta), math.sin(theta)
    us = [(x - mx) * c + (y - my) * s for x, y in zip(xs, ys)]
    vs = [-(x - mx) * s + (y - my) * c for x, y in zip(xs, ys)]
    lu, lv = _span(us), _span(vs)
    long_side, short_side = max(lu, lv), min(lu, lv)
    return {"long_px": long_side, "short_px": short_side, "fill": n / (lu * lv), "area_px": float(n), "angle_deg": round(math.degrees(theta), 1)}


def _scale_from_area(area_px: float, long_cm: float, short_cm: float, factor: float) -> float:
    """px per cm from the reference piece's pixel count. The cut-out grew the object's edge by ``EDGE_BIAS_PX`` on every side, so
    area = f*L*S*s^2 + perimeter*d*s... (perimeter = 2(L+S)s) + pi*d^2; solve that quadratic for s."""
    d = EDGE_BIAS_PX
    a, b, c = factor * long_cm * short_cm, 2 * (long_cm + short_cm) * d, math.pi * d * d - area_px
    return (-b + math.sqrt(b * b - 4 * a * c)) / (2 * a)


def _reference(pieces: list[dict[str, Any]], w: int, name: str, garment: dict[str, Any], total: int, flat: Image.Image) -> dict[str, Any]:
    long_cm, short_cm, area_factor = REFERENCES[name]
    want = long_cm / short_cm
    best = None
    for piece in pieces:
        if piece is garment or piece["area"] < MIN_PIECE_SHARE * total or piece["area"] >= garment["area"]:
            continue
        rect = _rectangle(piece, w)
        aspect = rect["long_px"] / rect["short_px"]
        if rect["fill"] < MIN_FILL or abs(aspect / want - 1) > ASPECT_TOLERANCE:
            continue
        score = abs(aspect / want - 1) + (1 - rect["fill"])
        if best is None or score < best[0]:
            best = (score, rect, piece)
    if best is None:
        raise GarmentPhotoError("PHOTO_REFERENCE_NOT_FOUND", f"no {name} was found beside the garment: lay it flat next to the garment, not under it, with a clear gap")
    _, rect, piece = best
    by_area = _scale_from_area(rect["area_px"], long_cm, short_cm, area_factor)
    by_sides = (rect["long_px"] / long_cm + rect["short_px"] / short_cm) / 2
    spread = abs(rect["long_px"] / long_cm - rect["short_px"] / short_cm) / by_sides
    by_difference = (rect["long_px"] - rect["short_px"]) / (long_cm - short_cm)       # independent of how far the cut-out grew the edge; only accurate when long - short is large (A4)
    pix = flat.load()
    contrast = sum(max(abs(c - 128) for c in pix[p % w, p // w]) for p in piece["pixels"][::7]) / max(1, len(piece["pixels"][::7]))
    scale = by_difference if name == "a4" else by_area
    return {"name": name, "size_cm": [long_cm, short_cm], "px_per_cm": scale, "px_per_cm_from_area": round(by_area, 3), "px_per_cm_from_difference": round(by_difference, 3), "contrast": round(contrast, 1), "px_per_cm_from_sides": round(by_sides, 3), "side_disagreement": round(spread, 3), "fill": round(rect["fill"], 3),
            "tilt_deg": rect["angle_deg"], "piece_area_px": piece["area"]}


def _rows(garment: dict[str, Any], w: int) -> dict[int, list[int]]:
    rows: dict[int, list[int]] = {}
    for p in garment["pixels"]:
        y, x = divmod(p, w)
        rows.setdefault(y, []).append(x)
    return rows


def _band(widths: list[float], lo: float, hi: float) -> float:
    n = len(widths)
    part = sorted(widths[min(n - 1, int(lo * n)):max(int(lo * n) + 1, int(hi * n))])
    return part[len(part) // 2]


def _classify(widths: list[float], gaps: list[bool], height_cm: float) -> str:
    """A rough guess of the kind from the outline alone (used only when the caller gives no kind). Jacket cannot be told from a top."""
    n = len(widths)
    lower = gaps[int(0.65 * n):int(0.95 * n)]
    if lower and sum(lower) / len(lower) > 0.6:
        return "bottom"
    if height_cm > 0 and max(widths) > 0:
        ratio = height_cm / max(widths)
        top_w, hem_w = _band(widths, 0.02, 0.08), _band(widths, 0.9, 0.99)
        if hem_w > top_w * 1.25:
            return "dress" if ratio > 1.3 else "skirt"
        if ratio > 1.5 and hem_w < 0.75 * _band(widths, 0.15, 0.40):            # long and narrowing towards the hem: two trouser legs, even when they touch
            return "bottom"
    return "top"


# ------------------------------------------------------------------------------------------------------------------ colour
def _kmeans(samples: list[tuple[int, int, int]], k: int = 4, rounds: int = 12) -> list[tuple[tuple[int, int, int], float]]:
    """Plain k-means in RGB with a deterministic start (luminance quantiles), then clusters closer than ``MERGE_DISTANCE`` merged. [(centre, share)] biggest first."""
    pts = sorted(samples, key=lambda c: 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2])
    k = max(1, min(k, len(pts)))
    centres = [pts[int((i + 0.5) * len(pts) / k)] for i in range(k)]
    sizes = [0] * k
    for _ in range(rounds):
        sums = [[0, 0, 0] for _ in range(k)]
        sizes = [0] * k
        for c in pts:
            j = min(range(k), key=lambda i: (c[0] - centres[i][0]) ** 2 + (c[1] - centres[i][1]) ** 2 + (c[2] - centres[i][2]) ** 2)
            sizes[j] += 1
            for ch in range(3):
                sums[j][ch] += c[ch]
        new = [tuple(round(sums[i][ch] / sizes[i]) for ch in range(3)) if sizes[i] else centres[i] for i in range(k)]
        if new == centres:
            break
        centres = new
    total = sum(sizes) or 1
    groups = [([float(v) for v in centres[i]], float(sizes[i])) for i in range(k) if sizes[i]]
    merged = True
    while merged and len(groups) > 1:                                         # one colour lit unevenly splits in two: merge clusters closer than MERGE_DISTANCE
        merged = False
        for i in range(len(groups)):
            for j in range(i + 1, len(groups)):
                if math.dist(groups[i][0], groups[j][0]) < MERGE_DISTANCE:
                    (a, na), (b, nb) = groups[i], groups[j]
                    groups[i] = ([(x * na + y * nb) / (na + nb) for x, y in zip(a, b)], na + nb)
                    del groups[j]
                    merged = True
                    break
            if merged:
                break
    return sorted(((tuple(int(round(v)) for v in c), n / total) for c, n in groups), key=lambda t: -t[1])  # type: ignore[arg-type]


def _colour(img: Image.Image, garment: dict[str, Any], mask: Image.Image) -> dict[str, Any]:
    w = img.width
    inner = Image.new("L", img.size, 0)
    inner.putdata([255 if v >= 128 else 0 for v in _values(mask)])
    inner = inner.filter(ImageFilter.MinFilter(5))                           # drop the blended rim
    inside = inner.load()
    rgb = img.load()
    pix = [p for p in garment["pixels"] if inside[p % w, p // w] >= 128] or list(garment["pixels"])
    random.Random(15).shuffle(pix)
    samples = [rgb[p % w, p // w] for p in pix[:4000]]
    clusters = _kmeans(samples)
    base = clusters[0][0]
    palette = [{"rgb": list(c), "hex": "#%02x%02x%02x" % c, "share": round(s, 3)} for c, s in clusters]
    return {"base": list(base), "hex": "#%02x%02x%02x" % base, "palette": palette}


# ------------------------------------------------------------------------------------------------------------------ analysis
def analyze(data: bytes, *, reference: str, kind: str | None = None) -> dict[str, Any]:
    """The estimate for one photo. Raises ``GarmentPhotoError`` (code PHOTO_*) when the photo cannot be used; every number is an ESTIMATE."""
    if reference not in REFERENCES:
        raise GarmentPhotoError("PHOTO_REFERENCE_UNKNOWN", f"reference must be one of {sorted(REFERENCES)}")
    if kind is not None and kind not in KINDS:
        raise GarmentPhotoError("PHOTO_KIND", f"kind must be one of {sorted(KINDS)}")
    img = _load(data)
    flat, lighting = _flatten(img)
    flat = flat.filter(ImageFilter.GaussianBlur(DENOISE_RADIUS))
    _refuse_if_object_at_the_edge(flat)
    mask = bg_removal.foreground_mask(flat, "auto")
    mask, shadow_share = _without_shadow(flat, mask)
    mask = mask.filter(ImageFilter.MedianFilter(3))
    pieces, w, h = _pieces(mask)
    total = w * h
    if not pieces or pieces[0]["area"] < MIN_GARMENT_SHARE * total:
        raise GarmentPhotoError("PHOTO_GARMENT_NOT_FOUND", "no garment could be told from the background: use a plain background with more contrast")
    garment = pieces[0]
    x0, y0, x1, y1 = garment["bbox"]
    if x0 <= 1 or y0 <= 1 or x1 >= w - 2 or y1 >= h - 2:
        raise GarmentPhotoError("PHOTO_GARMENT_CLIPPED", "the garment touches the edge of the picture: move the camera back so the whole garment fits")
    ref = _reference(pieces, w, reference, garment, total, flat)
    others = sum(piece["area"] for piece in pieces if piece is not garment and piece["area"] != ref["piece_area_px"] and piece["area"] >= 0.002 * total)
    if others > MAX_OTHER_SHARE * garment["area"]:
        raise GarmentPhotoError("PHOTO_GARMENT_FRAGMENTED", "the garment came out in several pieces, or something else lies in the picture: a pattern close to the background colour? use a background that contrasts with the whole garment")
    scale = ref["px_per_cm"]
    rows = _rows(garment, w)
    ys = list(range(y0, y1 + 1))
    widths = [((max(rows[y]) - min(rows[y]) + 1 - 2 * EDGE_BIAS_PX) / scale) if y in rows else 0.0 for y in ys]      # pixel count minus the 2 x EDGE_BIAS_PX the cut-out added
    gaps = []
    for y in ys:
        xs = sorted(rows.get(y, []))
        span = (xs[-1] - xs[0] + 1) if xs else 0
        gaps.append(bool(xs) and span > 0 and (len(xs) / span) < 0.85)       # a row with a hole in it: two trouser legs
    length_cm = (y1 - y0 + 1 - 2 * EDGE_BIAS_PX) / scale
    warnings: list[str] = []
    guessed = kind is None
    if guessed:
        kind = _classify(widths, gaps, length_cm)
        warnings.append(f"the kind was GUESSED from the outline ({kind}); give the kind yourself, and a jacket cannot be told from a top")
    measures: dict[str, float] = {}
    for key, (lo, hi) in RULES[kind].items():
        measures[key] = round(2 * _band(widths, lo, hi), 1)                  # flat width x 2
    measures["length_cm"] = round(length_cm, 1)
    if kind in ("top", "jacket"):
        reach = max(widths[int(SLEEVE_BAND[0] * len(widths)):max(1, int(SLEEVE_BAND[1] * len(widths)))])
        flat_chest = measures["chest_cm"] / 2
        if reach > flat_chest * SLEEVE_MIN_EXCESS:
            measures["sleeve_cm"] = round((reach - flat_chest) / 2, 1)
    if ref["side_disagreement"] > CONSISTENCY_WARN:
        warnings.append(f"the reference's two sides disagree by {ref['side_disagreement'] * 100:.0f} % (tilted camera or object): the cm values carry that much extra uncertainty")
    if shadow_share < 0:
        warnings.append("the garment is neutral grey: a shadow cannot be told from it, so no shadow was removed; avoid shadows next to the garment")
    elif shadow_share > 0.01:
        warnings.append(f"{shadow_share * 100:.0f} % of the cut-out looked like a soft shadow and was removed")
    if ref["contrast"] < LOW_CONTRAST:
        warnings.append(f"the reference object has little contrast with the background ({ref['contrast']:.0f} levels): its edge is less certain, so the cm scale is too (a few percent)")
    if lighting > FLAT_WARN:
        warnings.append(f"the lighting differs by {lighting:.0f} levels across the picture (it was levelled out): even light gives a better estimate")
    if garment["area"] < 0.10 * total:
        warnings.append("the garment is small in the picture: move closer for a better estimate")
    return {"estimated": True, "label": "ESTIMATED dimensions from a photo (flat width x 2), not tape-measure values", "kind": kind, "kind_source": "guess" if guessed else "hint",
            "reference": ref, "image": {"size_px": [w, h], "garment_share": round(garment["area"] / total, 3), "pieces": len(pieces)},
            "measurements_cm": measures, "colour": _colour(img, garment, mask), "lighting_spread": round(lighting, 1), "shadow_removed_share": round(max(shadow_share, 0.0), 3), "warnings": warnings, "capture_rules": list(CAPTURE_RULES)}


# ------------------------------------------------------------------------------------------------------------------ garment.v1
@functools.lru_cache(maxsize=None)
def _length_ratio(kind: str, sex: str) -> float:
    """The template's garment length divided by the preset body height (the sample garments scale with the body)."""
    _, spec = garments.build_sample_garment(kind, sex, 4.0)
    return spec["sizes"]["M"]["length_cm"] / (base_models.PRESETS[sex]["height"] * 100)


def to_garment(analysis: dict[str, Any], *, garment_id: str, sex: str, provenance: str, rights_confirmed: bool, ease_cm: float = 4.0) -> tuple[bytes, dict[str, Any], dict[str, Any]]:
    """(.glb, garment.v1 spec with a ``fit`` block, report). The sample template of the kind is built around a body whose measurements are the photo's garment circumferences minus ``ease_cm``
    and whose height makes the template's length equal to the photo's length (when that is possible); the person must still confirm the sizes."""
    kind, measures = analysis["kind"], analysis["measurements_cm"]
    if sex not in base_models.SEXES:
        raise GarmentPhotoError("PHOTO_KIND", f"sex must be one of {sorted(base_models.SEXES)}")
    body: dict[str, float] = {}
    for key in RULES[kind]:
        value = measures[key] - ease_cm
        lo, hi = base_models.LIMITS[key]
        if not lo <= value <= hi:
            raise GarmentPhotoError("PHOTO_SIZE_IMPLAUSIBLE", f"{key} = {measures[key]} cm is outside what a garment of this kind can be here ({lo + ease_cm:.0f}-{hi + ease_cm:.0f} cm)")
        body[key] = round(value, 1)
    notes: list[str] = []
    lo_h, hi_h = base_models.LIMITS["height_cm"]
    wanted = measures["length_cm"] / _length_ratio(kind, sex)
    body["height_cm"] = round(min(hi_h, max(lo_h, wanted)), 1)
    if abs(body["height_cm"] - wanted) > 0.5:
        notes.append(f"the template cannot be as {'long' if wanted > hi_h else 'short'} as the photo's garment ({measures['length_cm']} cm): its length was limited by the body proportions")
    colour = tuple(int(c) for c in analysis["colour"]["base"])
    glb, spec = garments.build_sample_garment(kind, sex, ease_cm, colour, body)
    spec["id"] = garment_id
    spec["source"] = {"provenance": provenance + " | sizes are ESTIMATES from a photo (app/garment_photo.py), the person must confirm them", "third_party_asset": True, "rights_confirmed": bool(rights_confirmed)}
    garments.validate_garment(glb, spec)
    report = {"estimated": True, "kind": kind, "measured_cm": measures, "garment_cm": spec["sizes"][spec["reference_size"]], "body_used_cm": body, "ease_cm": ease_cm, "fit_ready": "fit" in spec,
              "notes": notes}
    return glb, spec, report


__all__ = ["analyze", "to_garment", "GarmentPhotoError", "REFERENCES", "RULES", "CAPTURE_RULES"]
