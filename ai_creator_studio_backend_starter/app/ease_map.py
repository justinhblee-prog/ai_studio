"""Lane 2 / M4: EASE and PRESSURE maps - how does a garment of size S, M or L sit on a body with typed measurements?

The sizes are ABSOLUTE garments: M is the sample garment made for a NOMINAL body (``nominal``, default the preset) with 4 cm of ease, S and L are made for a body 4 cm smaller / larger round the chest,
waist and hips (the chart's S / M / L = M -4 / 0 / +4 cm). The body being checked is the typed one, so a small garment on a big body comes out TIGHT instead of being stretched to fit
(``garment_deform`` scales a garment to the body, which hides exactly this).
  * zone ease (the standard sizing logic): garment circumference - body circumference at the chest / waist / hips, in cm, classed ``tight`` (< 0: it does not close), ``fitted`` (0-4),
    ``regular`` (4-10), ``loose`` (> 10). The class limits are PROPOSALS (the design window decides);
  * vertex clearance: for every vertex of the garment, how far it stands from the body's own cross-section at that height (cm, negative = the vertex is INSIDE the body = pressure), drawn as
    a colour map (red tight -> green fitted -> blue loose) on a side-by-side S / M / L render with the software renderer.
  * a recommendation: the smallest size whose every zone has at least ``MIN_EASE_CM`` of room (you cannot move in a garment with none) and where at most ``MAX_PRESSURE_SHARE`` of its vertices are inside the
    body; if no size qualifies, none ("between sizes" or bigger than the largest).  Both limits are PROPOSALS.
What it is NOT: no cloth physics and no fabric stretch (a knit forgives what a woven does not), the clearance is measured against the stylised body of ``base_models`` (not a person), the garments are
the plain sample tubes, and a "tight" verdict is a geometric overlap, not a force. It is a size-guidance aid for the own3d engine, never a promise of how a real garment fits a real person.
"""
from __future__ import annotations

import math
import statistics
from typing import Any

from PIL import Image, ImageChops, ImageDraw

from app import base_models, garments, render3d_soft
from app.garment_deform import _body, _lerp_profile
from app.glb_tools import build_glb, parse_glb

SIZES = ("S", "M", "L")
EASE_CM = 4.0                                              # the ease every size is made with
STEP_CM = {"S": -4.0, "M": 0.0, "L": 4.0}                  # the size ladder: nominal body -4 / 0 / +4 cm round the chest, waist and hips
CIRC_KEYS = ("chest_cm", "waist_cm", "hips_cm")
MIN_EASE_CM = 2.0                                          # PROPOSAL: the least wearing ease a recommended size may have in any zone
MAX_PRESSURE_SHARE = 0.02                                  # PROPOSAL: the share of vertices that may lie inside the body
CLASSES = ((0.0, "tight"), (4.0, "fitted"), (10.0, "regular"))      # PROPOSAL: upper limits in cm; above the last is "loose"
ZONES = {"top": ("chest_cm", "waist_cm"), "jacket": ("chest_cm", "waist_cm"), "bottom": ("waist_cm", "hips_cm"), "skirt": ("waist_cm", "hips_cm"), "dress": ("chest_cm", "waist_cm", "hips_cm")}
BODY_KEY = {"chest_cm": "chest", "waist_cm": "waist", "hips_cm": "hip"}
SPLIT = {"torso": "torso", "skirt": "skirt"}


def classify(ease_cm: float) -> str:
    for limit, name in CLASSES:
        if ease_cm < limit:
            return name
    return "loose"


def body_circumference_cm(body: dict[str, Any], zone: str) -> float:
    a, b = body[BODY_KEY[zone]]
    return base_models._perimeter_cm(a, b)


def ladder(sex: str, nominal: dict[str, float] | None) -> dict[str, dict[str, float]]:
    """The body each size is made for: the nominal body (default: the preset's own circumferences) -4 / 0 / +4 cm round the chest, waist and hips; the height stays the nominal one."""
    base = base_models.preset_circumferences_cm(sex)
    start = {"chest_cm": base["chest"], "waist_cm": base["waist"], "hips_cm": base["hips"], **(nominal or {})}
    out = {}
    for size in SIZES:
        body = dict(start)
        for key in CIRC_KEYS:
            body[key] = round(float(start[key]) + STEP_CM[size], 1)
        out[size] = body
    return out


def zone_table(kind: str, sex: str, measurements: dict[str, float] | None, nominal: dict[str, float] | None = None) -> dict[str, Any]:
    """Per size: the garment's circumference at each zone, the body's, the ease between them and its class."""
    body = _body(sex, measurements)
    sizes = ladder(sex, nominal)
    out: dict[str, Any] = {}
    for size in SIZES:
        chart = garments.build_sample_garment(kind, sex, EASE_CM, measurements=sizes[size])[1]["sizes"]["M"]
        rows = {}
        for zone in ZONES[kind]:
            body_cm = round(body_circumference_cm(body, zone), 1)
            ease = round(chart[zone] - body_cm, 1)
            rows[zone] = {"garment_cm": chart[zone], "body_cm": body_cm, "ease_cm": ease, "class": classify(ease)}
        out[size] = rows
    return out


def vertex_clearance(kind: str, sex: str, size: str, measurements: dict[str, float] | None, nominal: dict[str, float] | None = None) -> tuple[list[tuple[tuple[float, float, float], float]], list[Any]]:
    """([(vertex of the size's garment in place on the target body, clearance cm)], triangles as vertex-index triples per part): negative = inside the body."""
    made_for = ladder(sex, nominal)[size]
    glb = garments.build_sample_garment(kind, sex, EASE_CM, measurements=made_for)[0]
    reference, target = _body(sex, made_for), _body(sex, measurements)
    ratio_h = target["height"] / reference["height"]
    profile = base_models.body_profiles(target, sex == "female")
    profile["skirt"] = garments.skirt_stops(target, sex == "female")
    doc, binary = parse_glb(glb)
    import struct
    points, tris = [], []
    for prim in doc["meshes"][0]["primitives"]:
        part = (prim.get("extras") or {}).get("part")
        acc = doc["accessors"][prim["attributes"]["POSITION"]]
        view = doc["bufferViews"][acc["bufferView"]]
        flat = struct.unpack_from(f"<{acc['count'] * 3}f", binary, view["byteOffset"])
        iacc = doc["accessors"][prim["indices"]]
        iview = doc["bufferViews"][iacc["bufferView"]]
        idx = struct.unpack_from(f"<{iacc['count']}H", binary, iview["byteOffset"])
        base = len(points)
        side = -1 if part in ("leg_l", "arm_l") else 1
        for i in range(0, len(flat), 3):
            x, y, z = flat[i:i + 3]
            y_t = y * ratio_h                                          # the garment is as long as the body is tall; its width is NOT scaled
            if part in ("torso", "skirt"):
                a, b, zc = _lerp_profile(profile[part], y_t)
                px, pz, centre_x = x, z, 0.0
            else:
                key = "arm" if part in ("arm_l", "arm_r") else "leg"
                cx, a, b, zc = _lerp_profile(profile[key], y_t)
                px, pz, centre_x = x - side * cx, z, 0.0
            rho = math.sqrt(((px - centre_x) / a) ** 2 + ((pz - zc) / b) ** 2)
            points.append(((x, y_t, z), (rho - 1.0) * (a + b) / 2 * 100.0))
        tris += [(base + idx[k], base + idx[k + 1], base + idx[k + 2]) for k in range(0, len(idx), 3)]
    return points, tris


def compare(kind: str, sex: str, measurements: dict[str, float] | None = None, nominal: dict[str, float] | None = None) -> dict[str, Any]:
    """The size table, clearance statistics per size and the recommendation."""
    if kind not in ZONES:
        raise ValueError(f"kind must be one of {sorted(ZONES)}")
    zones = zone_table(kind, sex, measurements, nominal)
    report: dict[str, Any] = {"kind": kind, "sex": sex, "measurements": dict(measurements or {}), "nominal": ladder(sex, nominal)["M"], "sizes": {}, "proposal_class_limits_cm": [l for l, _ in CLASSES]}
    for size in SIZES:
        points, _ = vertex_clearance(kind, sex, size, measurements, nominal)
        values = [c for _, c in points]
        ordered = sorted(values)
        report["sizes"][size] = {"zones": zones[size], "tight_zones": [z for z, r in zones[size].items() if r["class"] == "tight"],
                                 "below_min_ease_zones": [z for z, r in zones[size].items() if r["ease_cm"] < MIN_EASE_CM],
                                 "clearance_cm": {"min": round(ordered[0], 1), "median": round(statistics.median(values), 1), "p95": round(ordered[int(0.95 * (len(ordered) - 1))], 1)},
                                 "pressure_share": round(sum(1 for v in values if v < 0) / len(values), 3)}
    fitting = [s for s in SIZES if not report["sizes"][s]["below_min_ease_zones"] and report["sizes"][s]["pressure_share"] <= MAX_PRESSURE_SHARE]
    report["recommended"] = fitting[0] if fitting else None
    report["limits"] = {"min_ease_cm": MIN_EASE_CM, "max_pressure_share": MAX_PRESSURE_SHARE, "source": "proposal"}
    report["note"] = ("smallest size with enough room in every zone and no pressure" if fitting else "no size fits: the body is bigger than the largest size at some zone, or between sizes") + "; geometric guidance on the stylised body, no fabric stretch"
    return report


# ------------------------------------------------------------------------------------------------------------------ colours and the sheet
XRAY_KEY = (255, 0, 254)                                    # background of the overlay layer (a colour the colour map never produces)
STOPS = ((-3.0, (200, 30, 30)), (0.0, (240, 150, 40)), (2.0, (90, 190, 90)), (6.0, (70, 150, 220)), (12.0, (40, 70, 170)))


def colour_for(clearance_cm: float) -> tuple[int, int, int]:
    if clearance_cm <= STOPS[0][0]:
        return STOPS[0][1]
    for (c0, k0), (c1, k1) in zip(STOPS, STOPS[1:]):
        if clearance_cm <= c1:
            t = (clearance_cm - c0) / (c1 - c0)
            return tuple(int(round(a + (b - a) * t)) for a, b in zip(k0, k1))   # type: ignore[return-value]
    return STOPS[-1][1]


def render_sheet(kind: str, sex: str, measurements: dict[str, float] | None = None, angle: int = 0, size: tuple[int, int] = (300, 520), nominal: dict[str, float] | None = None) -> Image.Image:
    """S | M | L side by side on the same body, every triangle coloured by its mean clearance, with the verdicts written under each picture."""
    report = compare(kind, sex, measurements, nominal)
    body = render3d_soft.triangles_of(base_models.build_base_model(sex, top_style="tank", bottom_style="shorts", skin=(214, 168, 128), top=(214, 168, 128), bottom=(214, 168, 128),
                                                                    measurements=measurements or None, arms=True))
    height = render3d_soft.height_of(body)
    sheet = Image.new("RGB", (size[0] * 3, size[1] + 70), (255, 255, 255))
    draw = ImageDraw.Draw(sheet)
    for column, label in enumerate(SIZES):
        points, tris = vertex_clearance(kind, sex, label, measurements, nominal)
        coloured = []
        for a, b, c in tris:
            mean = (points[a][1] + points[b][1] + points[c][1]) / 3
            corners = (points[a][0], points[b][0], points[c][0])
            u = [corners[1][i] - corners[0][i] for i in range(3)]
            w = [corners[2][i] - corners[0][i] for i in range(3)]
            n = [u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0]]
            if n[0] * sum(p[0] for p in corners) + n[2] * sum(p[2] for p in corners) < 0:
                n = [-v for v in n]
            length = math.sqrt(sum(v * v for v in n)) or 1.0
            coloured.append((corners, ((n[0] / length, n[1] / length, n[2] / length),) * 3, colour_for(mean)))
        image = render3d_soft.render(body, angle, size, background=(244, 244, 244), height_m=height)
        # the garment is drawn OVER the body, flat and without light: a tight garment lies INSIDE the body and would be hidden by it, and the flat colours are exactly the legend's
        overlay = render3d_soft.render(coloured, angle, size, background=XRAY_KEY, height_m=height, flat=True, cull_back=True)
        mask = Image.eval(ImageChops.difference(overlay, Image.new("RGB", size, XRAY_KEY)).convert("L"), lambda v: 255 if v else 0)
        image.paste(overlay, (0, 0), mask)
        sheet.paste(image, (column * size[0], 0))
        info = report["sizes"][label]
        verdict = ("TIGHT: " + ", ".join(z.replace("_cm", "") for z in info["tight_zones"])) if info["tight_zones"] else ("little room: " + ", ".join(z.replace("_cm", "") for z in info["below_min_ease_zones"])) if info["below_min_ease_zones"] else "room in every zone"
        mark = "  <- recommended" if report["recommended"] == label else ""
        draw.text((column * size[0] + 8, size[1] + 6), f"{label}{mark}", fill=(0, 0, 0))
        draw.text((column * size[0] + 8, size[1] + 24), verdict, fill=(160, 30, 30) if info["tight_zones"] or info["below_min_ease_zones"] else (30, 110, 30))
        draw.text((column * size[0] + 8, size[1] + 42), "ease " + " ".join(f"{z.replace('_cm', '')} {r['ease_cm']:+.1f}" for z, r in info["zones"].items()) + " cm", fill=(60, 60, 60))
    return sheet


__all__ = ["compare", "zone_table", "vertex_clearance", "render_sheet", "classify", "colour_for", "SIZES"]
