"""Lane 2 / E-15 (own-code part): turn a USER-UPLOADED garment .glb into a ``garment.v1`` candidate - clean it up, estimate its scale and size - without any model, network or new dependency.

What it does
  * reads the scene graph and BAKES every node transform (matrix or translation/rotation/scale) into the vertices, so the result is one mesh in one place;
  * merges all triangle primitives into ONE primitive with one material ``base`` (the first material's colour); textures are dropped (garment.v1 has none: ``texture_dropped`` says so);
  * estimates the SCALE: glTF means metres, but garments are often exported in centimetres or millimetres (or inches). It offers every unit factor that makes the garment a plausible
    0.25 - 1.6 m tall and says when more than one fits (``ambiguous``): the person must confirm, it never silently decides between them;
  * estimates the size chart (chest / waist / hips from the cross-section at typical heights of the kind of garment, as the perimeter of an ellipse through the section's width and depth).
    These numbers are ESTIMATES (``estimated: true``; sleeves and pleats inflate them, a loose garment reads bigger than its body size): the person confirms or corrects them.
What it does NOT do: it cannot segment the garment into torso / legs / sleeves, so the result has no ``fit`` block and CANNOT be fitted to a body by ``garment_deform`` (it is a
reference-size garment); it refuses skinned or morphed models, non-triangle primitives, quantised positions and sparse accessors with a clear reason; it never decides rights.
RIGHTS: the result is only produced when the caller says the upload's rights were confirmed (``rights_confirmed``): a garment from a third party without it is refused by ``garments.validate_spec``.
"""
from __future__ import annotations

import math
import struct
from typing import Any

from app import garments
from app.glb_tools import GlbError, build_glb, parse_glb

COMPONENT = {5120: ("b", 1), 5121: ("B", 1), 5122: ("h", 2), 5123: ("H", 2), 5125: ("I", 4), 5126: ("f", 4)}
WIDTH = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}
UNIT_FACTORS = {"metres": 1.0, "centimetres": 0.01, "millimetres": 0.001, "inches": 0.0254}
PLAUSIBLE_HEIGHT_M = (0.25, 1.6)
MAX_TRIANGLES = 200_000
# heights (share of the garment's height, from the hem up) where each kind of garment is measured
SECTIONS = {"top": {"chest_cm": 0.70, "waist_cm": 0.30}, "jacket": {"chest_cm": 0.70, "waist_cm": 0.30}, "bottom": {"waist_cm": 0.92, "hips_cm": 0.78},
            "skirt": {"waist_cm": 0.92, "hips_cm": 0.75}, "dress": {"chest_cm": 0.78, "waist_cm": 0.58, "hips_cm": 0.35}}
HEIGHT_RANGE_M = {"top": (0.40, 0.90), "jacket": (0.50, 1.10), "bottom": (0.70, 1.30), "skirt": (0.30, 0.90), "dress": (0.80, 1.60)}


class GarmentImportError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


# ------------------------------------------------------------------------------------------------------------------ reading
def _accessor(doc: dict[str, Any], binary: bytes, index: int) -> list[tuple]:
    acc = doc["accessors"][index]
    if "sparse" in acc:
        raise GarmentImportError("IMPORT_UNSUPPORTED", "sparse accessors are not supported")
    fmt, size = COMPONENT[acc["componentType"]]
    width = WIDTH[acc["type"]]
    view = doc["bufferViews"][acc["bufferView"]] if "bufferView" in acc else None
    if view is None:
        return [(0,) * width] * acc["count"]
    stride = view.get("byteStride") or size * width
    base = view.get("byteOffset", 0) + acc.get("byteOffset", 0)
    return [struct.unpack_from("<" + fmt * width, binary, base + i * stride) for i in range(acc["count"])]


def _matrix(node: dict[str, Any]) -> list[float]:
    """Column-major 4x4 of one node (glTF order)."""
    if "matrix" in node:
        return [float(v) for v in node["matrix"]]
    t, (qx, qy, qz, qw), s = node.get("translation", (0, 0, 0)), node.get("rotation", (0, 0, 0, 1)), node.get("scale", (1, 1, 1))
    n = math.sqrt(qx * qx + qy * qy + qz * qz + qw * qw) or 1.0
    qx, qy, qz, qw = qx / n, qy / n, qz / n, qw / n
    r = [1 - 2 * (qy * qy + qz * qz), 2 * (qx * qy + qz * qw), 2 * (qx * qz - qy * qw), 0,
         2 * (qx * qy - qz * qw), 1 - 2 * (qx * qx + qz * qz), 2 * (qy * qz + qx * qw), 0,
         2 * (qx * qz + qy * qw), 2 * (qy * qz - qx * qw), 1 - 2 * (qx * qx + qy * qy), 0, 0, 0, 0, 1]
    return [r[0] * s[0], r[1] * s[0], r[2] * s[0], 0, r[4] * s[1], r[5] * s[1], r[6] * s[1], 0, r[8] * s[2], r[9] * s[2], r[10] * s[2], 0, t[0], t[1], t[2], 1]


def _multiply(a: list[float], b: list[float]) -> list[float]:
    return [sum(a[k * 4 + r] * b[c * 4 + k] for k in range(4)) for c in range(4) for r in range(4)]


def _apply(m: list[float], p: tuple[float, float, float]) -> tuple[float, float, float]:
    x, y, z = p
    return (m[0] * x + m[4] * y + m[8] * z + m[12], m[1] * x + m[5] * y + m[9] * z + m[13], m[2] * x + m[6] * y + m[10] * z + m[14])


def _collect(doc: dict[str, Any], binary: bytes) -> tuple[list[tuple[float, float, float]], list[tuple[int, int, int]], tuple[float, float, float], bool]:
    """(vertices with node transforms baked in, triangles, base colour, textures present)."""
    vertices: list[tuple[float, float, float]] = []
    triangles: list[tuple[int, int, int]] = []
    colour, colour_set, textured = (0.78, 0.78, 0.78), False, bool(doc.get("images") or doc.get("textures"))
    scene = (doc.get("scenes") or [{"nodes": list(range(len(doc.get("nodes", []))))}])[doc.get("scene", 0)]
    stack = [(i, [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]) for i in scene.get("nodes", [])]
    seen = 0
    while stack:
        index, parent = stack.pop()
        seen += 1
        if seen > 10_000:
            raise GarmentImportError("IMPORT_UNSUPPORTED", "the scene has too many nodes")
        node = doc["nodes"][index]
        world = _multiply(parent, _matrix(node))
        stack += [(c, world) for c in node.get("children", [])]
        if "skin" in node:
            raise GarmentImportError("IMPORT_SKINNED", "skinned models are not supported (the garment must be a plain mesh)")
        if "mesh" not in node:
            continue
        for prim in doc["meshes"][node["mesh"]].get("primitives", []):
            if prim.get("targets"):
                raise GarmentImportError("IMPORT_SKINNED", "models with morph targets are not supported")
            if prim.get("mode", 4) != 4:
                raise GarmentImportError("IMPORT_UNSUPPORTED", "only triangle lists are supported")
            pos_index = prim.get("attributes", {}).get("POSITION")
            if pos_index is None:
                continue
            acc = doc["accessors"][pos_index]
            if acc["componentType"] != 5126 or acc.get("normalized"):
                raise GarmentImportError("IMPORT_UNSUPPORTED", "positions must be plain 32-bit floats (quantised positions are not supported)")
            base = len(vertices)
            vertices += [_apply(world, p[:3]) for p in _accessor(doc, binary, pos_index)]
            ids = [v[0] for v in _accessor(doc, binary, prim["indices"])] if "indices" in prim else list(range(len(vertices) - base))
            triangles += [(base + ids[i], base + ids[i + 1], base + ids[i + 2]) for i in range(0, len(ids) - len(ids) % 3, 3)]
            if len(triangles) > MAX_TRIANGLES:
                raise GarmentImportError("IMPORT_TOO_LARGE", f"more than {MAX_TRIANGLES} triangles")
            material = doc.get("materials", [])[prim["material"]] if prim.get("material") is not None else None
            if material and not colour_set:
                colour, colour_set = tuple(material.get("pbrMetallicRoughness", {}).get("baseColorFactor", [0.78, 0.78, 0.78, 1])[:3]), True
    if not triangles:
        raise GarmentImportError("IMPORT_EMPTY", "the model contains no triangles")
    return vertices, triangles, colour, textured


# ------------------------------------------------------------------------------------------------------------------ estimation
def _extent(vertices: list[tuple[float, float, float]]) -> tuple[list[float], list[float]]:
    return [min(v[i] for v in vertices) for i in range(3)], [max(v[i] for v in vertices) for i in range(3)]


def _ellipse_perimeter_cm(a: float, b: float) -> float:
    h = ((a - b) / (a + b)) ** 2 if a + b else 0.0
    return math.pi * (a + b) * (1 + 3 * h / (10 + math.sqrt(4 - 3 * h))) * 100


def scale_candidates(height_units: float, largest_units: float) -> list[dict[str, Any]]:
    """Every unit factor that makes the model's HEIGHT (Y) a plausible garment height; the biggest dimension must stay under 2.5 m too."""
    out = []
    for name, factor in UNIT_FACTORS.items():
        if PLAUSIBLE_HEIGHT_M[0] <= height_units * factor <= PLAUSIBLE_HEIGHT_M[1] and largest_units * factor <= 2.5:
            out.append({"unit": name, "scale": factor, "height_m": round(height_units * factor, 4)})
    return out


def analyze(glb: bytes) -> dict[str, Any]:
    """What the upload looks like and what it would take to use it. Raises GarmentImportError / GlbError for a file that cannot be used."""
    doc, binary = parse_glb(glb)
    vertices, triangles, colour, textured = _collect(doc, bytes(binary))
    lo, hi = _extent(vertices)
    size = [h - l for l, h in zip(lo, hi)]
    candidates = scale_candidates(size[1], max(size))
    warnings = []
    if size[1] < max(size[0], size[2]) * 0.5:
        warnings.append("the model is much wider than tall: it may be lying flat or exported Z-up (garment.v1 expects Y up); rotate it before importing")
    if not candidates:
        warnings.append("no unit (m, cm, mm, inch) makes this a plausible garment height (0.25 - 1.6 m)")
    if len(candidates) > 1:
        warnings.append("more than one unit fits: the scale is ambiguous, confirm it")
    return {"triangles": len(triangles), "vertices": len(vertices), "size_units": [round(s, 5) for s in size], "bounds_min": [round(v, 5) for v in lo], "bounds_max": [round(v, 5) for v in hi],
            "base_colour": [round(c, 4) for c in colour], "texture_dropped": textured, "scale_candidates": candidates, "ambiguous": len(candidates) > 1,
            "plausible_kinds": [k for k, (a, b) in HEIGHT_RANGE_M.items() if candidates and any(a <= c["height_m"] <= b for c in candidates)], "warnings": warnings}


def estimate_measurements(vertices: list[tuple[float, float, float]], kind: str) -> dict[str, float]:
    """Perimeter (cm) of the ellipse through the section's width and depth, at the heights listed in SECTIONS (the vertices are already in metres)."""
    lo, hi = _extent(vertices)
    height = hi[1] - lo[1]
    out = {}
    for key, share in SECTIONS[kind].items():
        y = lo[1] + share * height
        nearest = min(abs(v[1] - y) for v in vertices)
        band = [v for v in vertices if abs(v[1] - y) <= max(0.03 * height, nearest + 0.002 * height)]        # always a whole ring, even when no vertex lies within 3 % of the height
        a, b = (max(v[0] for v in band) - min(v[0] for v in band)) / 2, (max(v[2] for v in band) - min(v[2] for v in band)) / 2
        out[key] = round(_ellipse_perimeter_cm(max(a, 1e-4), max(b, 1e-4)), 1)
    return out


# ------------------------------------------------------------------------------------------------------------------ conversion
def _write(vertices: list[tuple[float, float, float]], triangles: list[tuple[int, int, int]], colour: tuple[float, float, float], note: dict[str, Any]) -> bytes:
    lo, hi = _extent(vertices)
    positions = struct.pack(f"<{len(vertices) * 3}f", *[c for v in vertices for c in v])
    big = len(vertices) > 65535
    indices = struct.pack(f"<{len(triangles) * 3}{'I' if big else 'H'}", *[i for t in triangles for i in t])
    binary = positions + indices + b"\x00" * (-len(indices) % 4)
    doc = {"asset": {"version": "2.0", "generator": "ai-creator-studio garment_import"}, "scene": 0, "scenes": [{"nodes": [0]}],
           "nodes": [{"name": "imported_garment", "mesh": 0, "extras": {"generated_by_code": False, "imported_garment": True, **note}}],
           "meshes": [{"name": "imported_garment", "primitives": [{"attributes": {"POSITION": 0}, "indices": 1, "material": 0}]}],
           "materials": [{"name": "base", "doubleSided": True, "pbrMetallicRoughness": {"baseColorFactor": list(colour) + [1.0], "metallicFactor": 0.0, "roughnessFactor": 0.9}}],
           "accessors": [{"bufferView": 0, "componentType": 5126, "count": len(vertices), "type": "VEC3", "min": lo, "max": hi},
                         {"bufferView": 1, "componentType": 5125 if big else 5123, "count": len(triangles) * 3, "type": "SCALAR"}],
           "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": len(positions)}, {"buffer": 0, "byteOffset": len(positions), "byteLength": len(indices)}],
           "buffers": [{"byteLength": len(binary)}]}
    return build_glb(doc, binary)


def to_garment(glb: bytes, *, garment_id: str, kind: str, scale: float | None = None, provenance: str, rights_confirmed: bool, third_party_asset: bool = True,
               sleeve_cm: float | None = None) -> tuple[bytes, dict[str, Any], dict[str, Any]]:
    """(clean .glb in metres, garment.v1 spec, report). ``scale`` is the unit factor the person CONFIRMED; with none given, the only candidate is used when there is exactly one, else
    the call is refused (``IMPORT_SCALE_AMBIGUOUS``). Refuses with ``garments.GarmentError`` when a third-party garment's rights are not confirmed. The spec has no ``fit`` block."""
    if kind not in SECTIONS:
        raise GarmentImportError("IMPORT_KIND", f"kind must be one of {sorted(SECTIONS)}")
    doc, binary = parse_glb(glb)
    vertices, triangles, colour, textured = _collect(doc, bytes(binary))
    lo, hi = _extent(vertices)
    candidates = scale_candidates(hi[1] - lo[1], max(h - l for l, h in zip(lo, hi)))
    if scale is None:
        if len(candidates) != 1:
            raise GarmentImportError("IMPORT_SCALE_AMBIGUOUS" if candidates else "IMPORT_SCALE_IMPLAUSIBLE", "confirm the unit of the model" if candidates else "no unit makes this a plausible garment height")
        scale = candidates[0]["scale"]
    if isinstance(scale, bool) or not isinstance(scale, (int, float)) or not 1e-4 <= float(scale) <= 100:
        raise GarmentImportError("IMPORT_SCALE_INVALID", "scale must be a number between 0.0001 and 100")
    metres = [(v[0] * scale, v[1] * scale, v[2] * scale) for v in vertices]
    low, _ = _extent(metres)
    metres = [(v[0], v[1] - low[1], v[2]) for v in metres]                    # the hem sits on y = 0
    measures = estimate_measurements(metres, kind)
    if kind == "jacket":
        if sleeve_cm is None:
            raise GarmentImportError("IMPORT_SLEEVE_REQUIRED", "a jacket needs sleeve_cm (it cannot be estimated from the shape)")
        measures["sleeve_cm"] = float(sleeve_cm)
    height_cm = round(max(v[1] for v in metres) * 100, 1)
    measures["length_cm"] = height_cm
    clean = _write(metres, triangles, colour, {"units_scaled_by": scale, "texture_dropped": textured, "source_triangles": len(triangles)})
    spec = {"schema": garments.SCHEMA, "id": garment_id, "kind": kind, "reference_size": "M", "sizes": {"M": measures},
            "source": {"provenance": provenance, "third_party_asset": bool(third_party_asset), "rights_confirmed": bool(rights_confirmed)}}
    garments.validate_garment(clean, spec)                                  # raises GarmentError, e.g. a third-party garment without confirmed rights
    report = {"scale": scale, "estimated": True, "method": "bbox-ellipse at typical heights", "measurements_cm": measures, "texture_dropped": textured, "triangles": len(triangles),
              "fit_ready": False, "note": "no fit block: the garment cannot be fitted to a body, it is a reference-size garment; the measurements are estimates for the person to confirm"}
    return clean, spec, report


__all__ = ["analyze", "to_garment", "estimate_measurements", "scale_candidates", "GarmentImportError", "GlbError"]
