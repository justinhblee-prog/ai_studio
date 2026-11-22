"""LEGACY since D-66b (R-ENGINE-07): the canonical fitting is the garment.v1 mesh deformation (app/garment_deform.py, R-ENGINE-03b); this ring-shell is kept only for its
checker/CI sample (app/fit_check.py, scripts/make_fitted_glb.py) and is NOT on the own3d path.
R-ENGINE-03a (track A, step 1): a TOP (shirt-like shell) fitted around the measurement mannequin, in pure Python (no new dependency, no photo, no AI, no network).

What this is: for one size of a SizeChart, a closed-ring shell whose chest/waist/hip circumferences are the garment's finished circumferences, pushed OUTWARD where the
body would otherwise poke through it, written next to the mannequin in ONE .glb (two meshes, two materials). Every result is checked numerically: the clearance between the
shell and the body is never negative, and a size that is too small for the body is reported (``cannot_fit``) instead of being silently stretched past what the fabric can do.
What this is NOT: a cloth simulation. The shell does not drape, wrinkle or sag; it is a stiff tube whose size comes from the size chart (it looks like a sleeveless torso
shell, not a real shirt). It is reference geometry for angles/360-degree previews and for the later steps of R-ENGINE, never a promise of how a garment looks or fits.
The mannequin it wraps is the lane-2 column (a body COLUMN, not a person), so the result carries the same "approximate / reference" label.
"""
from __future__ import annotations

import math
import struct
from typing import Any

from app.glb_tools import build_glb, parse_glb
from app.mannequin import REFERENCE_LABEL_EN, REFERENCE_LABEL_KO, SEGMENTS, Measurements, SizeChart, _semi_axes, build_mannequin_glb

MIN_GAP_CM = 0.4                    # clearance the shell keeps from the skin even where it is snug (about the thickness of a thin fabric)
GARMENT_COLOUR = (0.24, 0.35, 0.63, 1.0)
SKIN_COLOUR = (0.88, 0.68, 0.41, 1.0)
# Heights (share of body height) where the shell has a ring, and which size-chart dimension sets its circumference there. They are the SAME heights as the mannequin's
# hip, waist, chest and upper-chest rings, so the shell and the body are compared ring by ring and in between by the same straight-line rule.
RINGS = ((0.50, "hips"), (0.62, "waist"), (0.72, "chest"), (0.82, "chest"))


def _body_perimeter_cm(m: Measurements, dimension: str) -> float:
    return {"hips": m.hips_cm, "waist": m.waist_cm, "chest": m.chest_cm}[dimension]


def ring_plan(m: Measurements, chart: SizeChart, size: str) -> list[dict[str, Any]]:
    """Per ring: what the size chart says, what the body needs, and the circumference the shell really gets (cm), with the reason."""
    if size not in chart.sizes:
        raise ValueError(f"unknown size {size!r}; the chart has {sorted(chart.sizes)}")
    dims = chart.sizes[size]
    rows = []
    for share, dimension in RINGS:
        body = _body_perimeter_cm(m, dimension)
        if dimension not in dims:
            raise ValueError(f"size {size!r} has no {dimension} measurement")
        garment = float(dims[dimension])
        depth_cm = _semi_axes(body)[1] * 100.0              # the body's front-to-back half-depth at this ring: the narrowest direction, where the clearance is smallest
        floor = body * (1.0 + MIN_GAP_CM / depth_cm)        # the smallest shell (scaled evenly) that still clears the skin by at least MIN_GAP_CM in every direction
        stretched = garment * (1.0 + chart.stretch)
        if garment >= floor:
            used, state = garment, "ok"
        elif stretched >= floor:
            used, state = floor, "stretched"               # the fabric can reach the body: it hugs it at the minimum clearance
        else:
            used, state = floor, "cannot_fit"              # too small even stretched: the shell is pushed out so it never cuts into the body, and the size is flagged
        rows.append({"height_share": share, "dimension": dimension, "garment_cm": garment, "body_cm": body, "shell_cm": round(used, 2), "state": state})
    return rows


def _shell_vertices(m: Measurements, plan: list[dict[str, Any]]) -> list[tuple[float, float, float]]:
    height, verts = m.height_cm / 100.0, []
    for row in plan:
        a, b = _semi_axes(row["shell_cm"])
        y = row["height_share"] * height
        for i in range(SEGMENTS):
            t = 2 * math.pi * i / SEGMENTS
            verts.append((a * math.cos(t), y, b * math.sin(t)))
    return verts


def _shell_indices(rings: int) -> list[int]:
    out: list[int] = []
    for r in range(rings - 1):
        for i in range(SEGMENTS):
            j = (i + 1) % SEGMENTS
            p0, p1, q0, q1 = r * SEGMENTS + i, r * SEGMENTS + j, (r + 1) * SEGMENTS + i, (r + 1) * SEGMENTS + j
            out += [p0, q0, p1, p1, q0, q1]
            out += [p0, p1, q0, p1, q1, q0]                 # the same quads facing inward: the shell has a visible inside from both sides (no back-face culling surprises)
    return out


def build_fitted_glb(m: Measurements, chart: SizeChart, size: str) -> tuple[bytes, dict[str, Any]]:
    """(glb bytes, report). The glb holds node 0 = the mannequin and node 1 = the garment shell."""
    plan = ring_plan(m, chart, size)
    doc, binary = parse_glb(build_mannequin_glb(m))
    binary += b"\x00" * (-len(binary) % 4)
    verts = _shell_vertices(m, plan)
    indices = _shell_indices(len(plan))
    flat = [c for v in verts for c in v]
    pos = struct.pack(f"<{len(flat)}f", *flat)
    idx = struct.pack(f"<{len(indices)}H", *indices)
    pos_off = len(binary)
    idx_off = pos_off + len(pos) + (-len(pos) % 4)
    binary = binary + pos + b"\x00" * (-len(pos) % 4) + idx
    xs, ys, zs = flat[0::3], flat[1::3], flat[2::3]
    views, accessors = doc["bufferViews"], doc["accessors"]
    views += [{"buffer": 0, "byteOffset": pos_off, "byteLength": len(pos)}, {"buffer": 0, "byteOffset": idx_off, "byteLength": len(idx)}]
    accessors += [{"bufferView": len(views) - 2, "componentType": 5126, "count": len(verts), "type": "VEC3", "min": [min(xs), min(ys), min(zs)], "max": [max(xs), max(ys), max(zs)]},
                  {"bufferView": len(views) - 1, "componentType": 5123, "count": len(indices), "type": "SCALAR"}]
    doc["materials"] = [{"name": "skin", "pbrMetallicRoughness": {"baseColorFactor": list(SKIN_COLOUR), "metallicFactor": 0.0, "roughnessFactor": 0.9}},
                        {"name": "garment", "pbrMetallicRoughness": {"baseColorFactor": list(GARMENT_COLOUR), "metallicFactor": 0.0, "roughnessFactor": 0.85}, "doubleSided": True}]
    doc["meshes"][0]["primitives"][0]["material"] = 0
    doc["meshes"].append({"primitives": [{"attributes": {"POSITION": len(accessors) - 2}, "indices": len(accessors) - 1, "material": 1}]})
    states = [r["state"] for r in plan]
    doc["nodes"].append({"mesh": 1, "name": "garment_top", "extras": {"approximate": True, "is_reconstruction": False, "size": size, "label": REFERENCE_LABEL_EN,
                                                                     "not_a_simulation": True, "cannot_fit": "cannot_fit" in states}})
    doc["scenes"][0]["nodes"] = [0, 1]
    doc["buffers"][0]["byteLength"] = len(binary) + (-len(binary) % 4)
    report = {"size": size, "rings": plan, "cannot_fit": "cannot_fit" in states, "stretched": "stretched" in states, "reference_only": True,
              "label_ko": REFERENCE_LABEL_KO, "label_en": REFERENCE_LABEL_EN,
              "method": "stiff shell from the size chart, pushed outward to clear the body; no cloth simulation, no drape"}
    return build_glb(doc, binary), report
