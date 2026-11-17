"""Lane 2 / E-06 + M1: a measurement-driven mannequin silhouette and a clothing-size fit REFERENCE (pure Python, no new dependency).

What this is: a simplified body COLUMN (feet to head, one lofted tube whose chest/waist/hip cross-sections follow the given circumferences) written as a valid .glb with
``extras.approximate=true``, and a size-chart comparison that says per size how much room a garment leaves at chest/waist/hips.
What this is NOT: a body scan, a cloth simulation, or a promise that a garment fits. Every fit result carries ``reference_only=True`` and the label below: the service must show it as
"approximate / reference" (reply 51). Nothing here reads a photo or identifies anyone: the only input is numbers typed by the user.
"""
from __future__ import annotations

import math
import struct
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.glb_tools import build_glb

REFERENCE_LABEL_KO = "참고용(근사치) — 실제 착용감과 다를 수 있습니다"
REFERENCE_LABEL_EN = "Approximate reference only — actual fit may differ"
SEGMENTS = 20
DEPTH_RATIO = 0.72          # front-to-back depth as a share of width, for a typical torso cross-section


class Measurements(BaseModel):
    """Centimetres. Ranges are plausibility limits that keep the geometry sane; they are not medical or sizing standards."""
    model_config = ConfigDict(extra="forbid")
    height_cm: float = Field(ge=120, le=220)
    chest_cm: float = Field(ge=60, le=160)
    waist_cm: float = Field(ge=50, le=150)
    hips_cm: float = Field(ge=70, le=170)


def measurement_warnings(m: Measurements) -> list[str]:
    notes = []
    if m.waist_cm > m.chest_cm * 1.25 or m.waist_cm > m.hips_cm * 1.25:
        notes.append("waist is much larger than chest/hips: check the numbers")
    if m.hips_cm < m.waist_cm * 0.8:
        notes.append("hips are much smaller than the waist: check the numbers")
    if m.chest_cm / m.height_cm > 0.8:
        notes.append("chest is very large for this height: check the numbers")
    return notes


def _semi_axes(circumference: float) -> tuple[float, float]:
    """Width/depth semi-axes (metres) of an ellipse with the given perimeter (cm) and the fixed depth ratio (Ramanujan perimeter)."""
    b_over_a = DEPTH_RATIO
    h = ((1 - b_over_a) / (1 + b_over_a)) ** 2
    per_unit = math.pi * (1 + b_over_a) * (1 + 3 * h / (10 + math.sqrt(4 - 3 * h)))     # perimeter when a = 1
    a = (circumference / 100.0) / per_unit
    return a, a * b_over_a


def profile(m: Measurements) -> list[tuple[float, float, float]]:
    """(height_m, semi_width_m, semi_depth_m) from feet to head. Heights are proportions of the body height."""
    height = m.height_cm / 100.0
    chest, waist, hips = _semi_axes(m.chest_cm), _semi_axes(m.waist_cm), _semi_axes(m.hips_cm)
    ankle, knee, neck = _semi_axes(m.hips_cm * 0.30), _semi_axes(m.hips_cm * 0.38), _semi_axes(m.chest_cm * 0.40)
    head = _semi_axes(m.height_cm * 0.30)
    stops = [(0.00, ankle), (0.28, knee), (0.50, hips), (0.62, waist), (0.72, chest), (0.82, chest), (0.855, neck), (0.88, neck), (0.93, head), (1.00, (head[0] * 0.2, head[1] * 0.2))]
    return [(p * height, a, b) for p, (a, b) in stops]


def build_mannequin_glb(m: Measurements) -> bytes:
    rows = profile(m)
    verts: list[float] = []
    for y, a, b in rows:
        for i in range(SEGMENTS):
            t = 2 * math.pi * i / SEGMENTS
            verts += [a * math.cos(t), y, b * math.sin(t)]
    indices: list[int] = []
    for r in range(len(rows) - 1):
        for i in range(SEGMENTS):
            j = (i + 1) % SEGMENTS
            p0, p1, q0, q1 = r * SEGMENTS + i, r * SEGMENTS + j, (r + 1) * SEGMENTS + i, (r + 1) * SEGMENTS + j
            indices += [p0, q0, p1, p1, q0, q1]
    top = (len(rows) - 1) * SEGMENTS                      # close the head with a fan around a centre point
    centre = len(verts) // 3
    verts += [0.0, rows[-1][0], 0.0]
    for i in range(SEGMENTS):
        indices += [top + i, centre, top + (i + 1) % SEGMENTS]
    pos = struct.pack(f"<{len(verts)}f", *verts)
    idx = struct.pack(f"<{len(indices)}H", *indices)
    xs, ys, zs = verts[0::3], verts[1::3], verts[2::3]
    binary = pos + b"\x00" * (-len(pos) % 4) + idx
    doc = {"asset": {"version": "2.0", "generator": "ai-creator-studio mannequin"}, "scene": 0, "scenes": [{"nodes": [0]}],
           "nodes": [{"mesh": 0, "name": "mannequin", "extras": {"approximate": True, "is_reconstruction": False, "label": REFERENCE_LABEL_EN,
                                                                  "measurements_cm": m.model_dump()}}],
           "meshes": [{"primitives": [{"attributes": {"POSITION": 0}, "indices": 1}]}],
           "accessors": [{"bufferView": 0, "componentType": 5126, "count": len(verts) // 3, "type": "VEC3", "min": [min(xs), min(ys), min(zs)], "max": [max(xs), max(ys), max(zs)]},
                         {"bufferView": 1, "componentType": 5123, "count": len(indices), "type": "SCALAR"}],
           "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": len(pos)}, {"buffer": 0, "byteOffset": len(pos) + (-len(pos) % 4), "byteLength": len(idx)}],
           "buffers": [{"byteLength": len(binary)}]}
    return build_glb(doc, binary)


# --- size fit (M1) -----------------------------------------------------------------------------------------------------------------------
class SizeChart(BaseModel):
    """Finished GARMENT circumferences per size, in cm (as printed by the maker), plus how stretchy the fabric is."""
    model_config = ConfigDict(extra="forbid")
    sizes: dict[str, dict[str, float]] = Field(min_length=1, max_length=12)
    stretch: float = Field(default=0.0, ge=0.0, le=0.5)        # share the fabric can extend (0 = woven, 0.2 = knit)


DIMENSIONS = ("chest", "waist", "hips")
EASE_BANDS = [(-1e9, 0.0, "too_tight", "작을 수 있음"), (0.0, 4.0, "snug", "몸에 딱 맞음"), (4.0, 14.0, "regular", "보통 여유"), (14.0, 1e9, "loose", "넉넉함")]


def _band(ease: float) -> tuple[str, str]:
    for lo, hi, key, ko in EASE_BANDS:
        if lo <= ease < hi:
            return key, ko
    return "loose", "넉넉함"


def fit_report(m: Measurements, chart: SizeChart) -> dict[str, Any]:
    body = {"chest": m.chest_cm, "waist": m.waist_cm, "hips": m.hips_cm}
    per_size, scored = [], []
    for size, dims in chart.sizes.items():
        row, penalty = {}, 0.0
        for d in DIMENSIONS:
            if d not in dims:
                continue
            ease = round(dims[d] * (1 + chart.stretch) - body[d], 1)
            key, ko = _band(ease)
            row[d] = {"garment_cm": dims[d], "body_cm": body[d], "ease_cm": ease, "fit": key, "fit_ko": ko}
            penalty += abs(ease - 8.0)                         # 8 cm of room is the reference "regular" target
        if row:
            per_size.append({"size": size, "dimensions": row, "penalty": round(penalty, 1)})
            scored.append((penalty, size))
    scored.sort()
    return {"reference_only": True, "label_ko": REFERENCE_LABEL_KO, "label_en": REFERENCE_LABEL_EN, "warnings": measurement_warnings(m),
            "recommended_size": scored[0][1] if scored else None, "sizes": per_size,
            "method": "garment circumference (x stretch) minus body circumference; the closest to 8 cm of room wins; no cloth simulation"}
