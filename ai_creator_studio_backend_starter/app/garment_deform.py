"""R-ENGINE-03b (track A of the own 3D try-on engine): deform a garment (garment.v1) to a body with typed measurements by MESH DEFORMATION ("profile-ratio.v1").

Method (deliberately simple, deterministic, CPU only, no GPU, no model weights): the garment is made around a REFERENCE body (the unmeasured preset of ``spec['fit']['reference_sex']``).
Every vertex is moved by the ratio between the TARGET body and the REFERENCE body at the vertex's own height:
  * torso part: x and z are scaled by (target half-width / reference half-width) at that height; the height is scaled by the height ratio;
  * a leg part: the vertex keeps its offset from the leg's centre line, scaled by the radius ratio, and the centre line moves to the target leg position;
  * an arm part (jacket sleeves, R-ENGINE-09): the same as a leg, with the arm's centre line and radius (``garments.arm_stops``);
  * a skirt part (skirt, dress; R-ENGINE-09): like the torso, but the profile is the ENVELOPE of waist, hips and both thighs (``garments.skirt_stops``) so the skirt follows the legs too.
Because the garment's EASE (its gap to the body) is scaled by the same ratio, a garment that stood outside the reference body stands outside the target body: the result is checked
for vertices that fall INSIDE the target body and the fit is refused if there are any (``penetrations`` is always 0 on a successful return).

What it is NOT: no cloth simulation (no folds, no gravity, no stretch), no pose, no collision with arms, no real garment patterns. The body is the stylised placeholder of
``app/base_models.py``; the result is a "garment tube that follows the typed measurements", good for previews and for tests of the data flow, not a realistic try-on.
"""
from __future__ import annotations

import struct
from typing import Any

from app import base_models, garments
from app.glb_tools import GlbError, build_glb, parse_glb

EPS = 1e-6


def _lerp_profile(stops: list[tuple[float, ...]], y: float) -> tuple[float, ...]:
    """Piecewise-linear value list at height y (clamped at both ends); stops are (y, v1, v2, ...) in ascending y."""
    if y <= stops[0][0]:
        return stops[0][1:]
    if y >= stops[-1][0]:
        return stops[-1][1:]
    for lo, hi in zip(stops, stops[1:]):
        if lo[0] <= y <= hi[0]:
            t = (y - lo[0]) / (hi[0] - lo[0]) if hi[0] > lo[0] else 0.0
            return tuple(a + (b - a) * t for a, b in zip(lo[1:], hi[1:]))
    return stops[-1][1:]


def _torso_stops(p: dict[str, Any]) -> list[tuple[float, ...]]:
    h = p["height"]
    return [(0.52 * h, *p["hip"]), (0.60 * h, *p["waist"]), (0.70 * h, *p["chest"]), (0.81 * h, p["shoulder"] * 0.72, p["chest"][1] * 0.92)]


def _arm_stops(p: dict[str, Any]) -> list[tuple[float, ...]]:
    return garments.arm_stops(p)


def _skirt_stops(p: dict[str, Any]) -> list[tuple[float, ...]]:
    return garments.skirt_stops(p)


def _leg_stops(p: dict[str, Any]) -> list[tuple[float, ...]]:
    h = p["height"]
    leg_x = p["hip"][0] * 0.55
    return [(0.04 * h, leg_x * 0.9, p["calf"] * 0.65), (0.28 * h, leg_x * 0.95, p["thigh"] * 0.72), (0.52 * h, leg_x, p["thigh"])]


def _read_positions(doc: dict[str, Any], binary: bytes | bytearray, primitive: dict[str, Any]) -> tuple[dict[str, Any], int, list[float]]:
    accessor = doc["accessors"][primitive["attributes"]["POSITION"]]
    view = doc["bufferViews"][accessor["bufferView"]]
    if accessor.get("componentType") != 5126 or accessor.get("type") != "VEC3" or view.get("byteStride") not in (None, 12):
        raise garments.GarmentError(["fit needs float32 tightly packed POSITION data"])
    start = view.get("byteOffset", 0) + accessor.get("byteOffset", 0)
    n = accessor["count"] * 3
    return accessor, start, list(struct.unpack_from(f"<{n}f", binary, start))


def _body(sex: str, measurements: dict[str, float] | None) -> dict[str, Any]:
    reference = base_models.PRESETS[sex]
    return base_models._fit_measurements(reference, measurements) if measurements else reference


def _inside(x: float, z: float, a: float, b: float) -> bool:
    return b > 0 and a > 0 and (x / a) ** 2 + (z / b) ** 2 < 1.0 - 1e-6


def deform_garment(glb: bytes, spec: dict[str, Any], measurements: dict[str, float] | None = None) -> tuple[bytes, dict[str, Any]]:
    """Return (fitted .glb, report). ``measurements`` uses the base-model names (height_cm, chest_cm, waist_cm, hips_cm; any subset; None = the reference body, which changes nothing)."""
    garments.validate_garment(glb, spec)
    fit = spec.get("fit")
    if not fit:
        raise garments.GarmentError(["this garment is not fit-ready: the spec has no 'fit' block"])
    sex = fit["reference_sex"]
    ref, tgt = _body(sex, None), _body(sex, measurements)       # _body raises ValueError for bad measurements
    doc, binary = parse_glb(glb)
    binary = bytearray(binary)
    ratio_h = tgt["height"] / ref["height"]
    ref_torso, tgt_torso, ref_leg, tgt_leg = _torso_stops(ref), _torso_stops(tgt), _leg_stops(ref), _leg_stops(tgt)
    ref_arm, tgt_arm, ref_skirt, tgt_skirt = _arm_stops(ref), _arm_stops(tgt), _skirt_stops(ref), _skirt_stops(tgt)
    penetrations = vertices = 0
    y_lo, y_hi = float("inf"), float("-inf")
    for primitive in doc["meshes"][0]["primitives"]:
        part = (primitive.get("extras") or {}).get("part")
        if part not in garments.PARTS:
            raise garments.GarmentError([f"every primitive needs extras.part in {list(garments.PARTS)}"])
        accessor, start, pos = _read_positions(doc, binary, primitive)
        side = -1 if part in ("leg_l", "arm_l") else 1
        out = list(pos)
        for i in range(0, len(pos), 3):
            x, y, z = pos[i:i + 3]
            y_t = y * ratio_h
            if part in ("torso", "skirt"):
                (ar, br), (at, bt) = (_lerp_profile(ref_torso, y), _lerp_profile(tgt_torso, y_t)) if part == "torso" else (_lerp_profile(ref_skirt, y), _lerp_profile(tgt_skirt, y_t))
                nx, nz = x * at / ar, z * bt / br
                penetrations += _inside(nx, nz, at, bt)
            else:
                ref_c, tgt_c = (ref_arm, tgt_arm) if part in ("arm_l", "arm_r") else (ref_leg, tgt_leg)
                (cxr, rr), (cxt, rt) = _lerp_profile(ref_c, y), _lerp_profile(tgt_c, y_t)
                nx, nz = side * cxt + (x - side * cxr) * rt / rr, z * rt / rr
                penetrations += _inside(nx - side * cxt, nz, rt, rt)
            out[i:i + 3] = [nx, y_t, nz]
            y_lo, y_hi = min(y_lo, y_t), max(y_hi, y_t)
        vertices += len(pos) // 3
        struct.pack_into(f"<{len(out)}f", binary, start, *out)
        xs, ys, zs = out[0::3], out[1::3], out[2::3]
        accessor["min"], accessor["max"] = [min(xs), min(ys), min(zs)], [max(xs), max(ys), max(zs)]
    if penetrations:
        raise garments.GarmentError([f"the fitted garment would pass through the body at {penetrations} vertices"])
    node = doc["nodes"][0]
    node["extras"] = dict(node.get("extras", {}), fitted_to=dict(measurements or {}), fit_method=garments.FIT_METHOD)
    try:
        fitted = build_glb(doc, bytes(binary))
    except GlbError as exc:                                      # pragma: no cover - the structure was valid on the way in
        raise garments.GarmentError([f"glb: {exc}"]) from exc
    return fitted, {"method": garments.FIT_METHOD, "vertices": vertices, "penetrations": 0, "height_cm": round((y_hi - y_lo) * 100, 1), "measurements": dict(measurements or {}),
                    "note": "mesh deformation on the stylised base body: no cloth simulation, folds or pose"}
