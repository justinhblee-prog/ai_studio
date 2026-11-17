"""R-ENGINE-06 (track A): a LOCAL checker for a fitted-garment .glb (mannequin + garment shell, see app/garment_fit.py). Pure Python, no model, no network, no photo.

It reads the two meshes inside the finished file and answers four questions with numbers, so a regression in the fitting is caught without looking at pictures and without sending anything
to an AI reviewer:
  * penetration - does any sampled point of the garment fall INSIDE the body cross-section?
  * clearance   - the smallest gap (cm) between the garment and the body (negative = cutting in);
  * length      - how much of the body height the garment covers (a share), against an expected range;
  * colour      - is the garment's base colour the one that was asked for?
What it is NOT: the later "5-item review" of the design (logo, text, pattern, hands, length) of a photo-real result. Those need a picture and a reviewer; this only judges the 3D geometry and
colour that the engine itself produced, where the right answer is KNOWN. A pass means "geometry and colour are as specified", never "the garment looks good" or "fits this person".
"""
from __future__ import annotations

import math
import struct
from typing import Any

from app.glb_tools import parse_glb

MIN_CLEARANCE_CM = 0.2          # a pass needs the garment to stay at least this far from the skin
DEFAULT_LENGTH_SHARE = (0.25, 0.45)
COLOUR_TOLERANCE = 0.05         # per channel, on the 0..1 scale of glTF baseColorFactor
EDGE_SAMPLES = 10


class FitCheckError(ValueError):
    pass


def _mesh(doc: dict[str, Any], binary: bytes, node_name: str) -> tuple[list[tuple[float, float, float]], list[tuple[int, int, int]], int | None]:
    node = next((n for n in doc.get("nodes", []) if n.get("name") == node_name), None)
    if node is None or "mesh" not in node:
        raise FitCheckError(f"no node named {node_name!r} with a mesh")
    prim = doc["meshes"][node["mesh"]]["primitives"][0]
    pos, idx = doc["accessors"][prim["attributes"]["POSITION"]], doc["accessors"][prim["indices"]]
    pv, iv = doc["bufferViews"][pos["bufferView"]], doc["bufferViews"][idx["bufferView"]]
    flat = struct.unpack_from(f"<{pos['count'] * 3}f", binary, pv.get("byteOffset", 0))
    ids = struct.unpack_from(f"<{idx['count']}H", binary, iv.get("byteOffset", 0))
    return [flat[i:i + 3] for i in range(0, len(flat), 3)], [ids[i:i + 3] for i in range(0, len(ids), 3)], prim.get("material")


def _rings(verts: list[tuple[float, float, float]]) -> list[tuple[float, list[tuple[float, float]]]]:
    """Group the mannequin's vertices into horizontal rings: [(height, [(x, z), ...]), ...] from the feet up. Only rings with the same number of points as the first are kept (the head cap's centre point is skipped)."""
    by_height: dict[float, list[tuple[float, float]]] = {}
    for x, y, z in verts:
        by_height.setdefault(round(y, 5), []).append((x, z))
    rows = sorted(by_height.items())
    size = len(rows[0][1])
    rings = [(y, pts) for y, pts in rows if len(pts) == size]
    if size < 3 or len(rings) < 2:
        raise FitCheckError("the body mesh does not look like stacked rings")
    return rings


def _body_polygon(rings: list[tuple[float, list[tuple[float, float]]]], y: float) -> list[tuple[float, float]] | None:
    for (y0, p0), (y1, p1) in zip(rings, rings[1:]):
        if y0 - 1e-9 <= y <= y1 + 1e-9:
            t = 0.0 if y1 == y0 else (y - y0) / (y1 - y0)
            return [((1 - t) * a[0] + t * b[0], (1 - t) * a[1] + t * b[1]) for a, b in zip(p0, p1)]
    return None


def _signed_distance(poly: list[tuple[float, float]], x: float, z: float) -> float:
    """Distance from (x, z) to a convex polygon: positive outside, negative inside."""
    best, signs = math.inf, []
    for i in range(len(poly)):
        (x0, z0), (x1, z1) = poly[i], poly[(i + 1) % len(poly)]
        ex, ez = x1 - x0, z1 - z0
        length2 = ex * ex + ez * ez
        t = 0.0 if length2 == 0 else max(0.0, min(1.0, ((x - x0) * ex + (z - z0) * ez) / length2))
        best = min(best, math.hypot(x - (x0 + t * ex), z - (z0 + t * ez)))
        signs.append(ex * (z - z0) - ez * (x - x0))
    inside = all(s > 0 for s in signs) or all(s < 0 for s in signs)
    return -best if inside else best


def _samples(verts: list[tuple[float, float, float]], tris: list[tuple[int, int, int]]):
    for a, b, c in tris:
        pts = (verts[a], verts[b], verts[c])
        for p, q in ((pts[0], pts[1]), (pts[1], pts[2]), (pts[2], pts[0])):
            for k in range(EDGE_SAMPLES + 1):
                t = k / EDGE_SAMPLES
                yield tuple((1 - t) * p[j] + t * q[j] for j in range(3))


def check_fit(glb: bytes, *, expected_colour: tuple[float, float, float, float] | None = None, length_share: tuple[float, float] = DEFAULT_LENGTH_SHARE,
              body_node: str = "mannequin", garment_node: str = "garment_top") -> dict[str, Any]:
    """The four checks on a fitted .glb. ``passed`` is true only when every check passes; every check also carries its measured number."""
    doc, binary = parse_glb(glb)
    body, _, _ = _mesh(doc, binary, body_node)
    shell, tris, material = _mesh(doc, binary, garment_node)
    rings = _rings(body)
    body_height = max(v[1] for v in body) - min(v[1] for v in body)
    if body_height <= 0:
        raise FitCheckError("the body has no height")
    inside, total, smallest = 0, 0, math.inf
    for x, y, z in _samples(shell, tris):
        poly = _body_polygon(rings, y)
        if poly is None:
            continue                                            # above or below the body: nothing to cut into
        distance_cm = _signed_distance(poly, x, z) * 100.0
        total += 1
        smallest = min(smallest, distance_cm)
        if distance_cm < 0:
            inside += 1
    if total == 0:
        raise FitCheckError("the garment is not beside the body at any height")
    top, bottom = max(v[1] for v in shell), min(v[1] for v in shell)
    share = (top - bottom) / body_height
    colour = None
    if material is not None and "materials" in doc:
        colour = doc["materials"][material].get("pbrMetallicRoughness", {}).get("baseColorFactor")
    colour_ok, colour_error = None, None
    if expected_colour is not None:
        if colour is None:
            colour_ok, colour_error = False, None
        else:
            colour_error = max(abs(a - b) for a, b in zip(colour[:3], expected_colour[:3]))
            colour_ok = colour_error <= COLOUR_TOLERANCE
    checks = {
        "penetration": {"passed": inside == 0, "points_inside": inside, "points_checked": total},
        "clearance": {"passed": smallest >= MIN_CLEARANCE_CM, "min_clearance_cm": round(smallest, 3), "required_cm": MIN_CLEARANCE_CM},
        "length": {"passed": length_share[0] <= share <= length_share[1], "share_of_body_height": round(share, 3), "expected": list(length_share)},
        "colour": {"passed": colour_ok, "max_channel_error": None if colour_error is None else round(colour_error, 3), "checked": expected_colour is not None},
    }
    passed = all(c["passed"] is not False for c in checks.values())
    return {"passed": passed, "checks": checks, "scope": "geometry and colour as specified; not a review of how the garment looks or whether it fits a real person"}
