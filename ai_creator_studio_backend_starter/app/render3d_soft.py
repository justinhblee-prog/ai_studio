"""R-ENGINE-10: a small SOFTWARE renderer (pure Python + Pillow, no GPU, no Chromium, no new dependency) that draws the own3d scene (base body + fitted garments) from any angle.

Why it exists: the browser/Chromium renderer of the viewer (``scripts/render_glb.mjs``) needs Node and Playwright, which the API server does not have. This renderer lets the
``render3d`` job make its pictures inside the server process so the whole path (typed measurements -> fitted garments -> pictures -> rotating MP4) runs, and is tested, anywhere.
What it is NOT: not physically based and not pretty: one directional light, per-vertex smooth shading, a plain background, orthographic camera, no shadows, no textures, no anti-aliasing.
Look and speed are those of a mock; the deterministic result (same input -> same pixels) is what the tests rely on.
"""
from __future__ import annotations

import math
import struct
from typing import Any

from PIL import Image

from app.glb_tools import parse_glb

Vec = tuple[float, float, float]
Triangle = tuple[tuple[Vec, Vec, Vec], tuple[Vec, Vec, Vec], tuple[int, int, int]]      # (corner positions, corner normals, colour 0..255)
LIGHT = (0.4, 0.6, 0.7)
BACKGROUNDS = {"white": (255, 255, 255), "light": (242, 242, 242), "gray": (190, 190, 196), "studio": (214, 224, 236)}
MAX_PIXELS = 800 * 1400


def triangles_of(glb: bytes, colour: tuple[int, int, int] | None = None, axis_outward: bool = False) -> list[Triangle]:
    """The triangles of a .glb. A mesh without NORMAL gets face normals; with ``axis_outward`` (garment tubes) they are turned to point away from the vertical axis."""
    doc, binary = parse_glb(glb)
    out: list[Triangle] = []
    for prim in doc["meshes"][0]["primitives"]:
        material = doc["materials"][prim.get("material", 0)]["pbrMetallicRoughness"]["baseColorFactor"][:3]
        rgb = colour or tuple(int(round(c * 255)) for c in material)

        def read(index: int, fmt: str, width: int) -> tuple[Any, ...]:
            accessor = doc["accessors"][index]
            view = doc["bufferViews"][accessor["bufferView"]]
            return struct.unpack_from(f"<{accessor['count'] * width}{fmt}", binary, view["byteOffset"])
        pos = read(prim["attributes"]["POSITION"], "f", 3)
        normals = read(prim["attributes"]["NORMAL"], "f", 3) if "NORMAL" in prim["attributes"] else None
        idx = read(prim["indices"], "H", 1)
        for t in range(0, len(idx), 3):
            corners = tuple(tuple(pos[3 * k:3 * k + 3]) for k in idx[t:t + 3])
            if normals is not None:
                ns = tuple(tuple(normals[3 * k:3 * k + 3]) for k in idx[t:t + 3])
            else:
                u = [corners[1][i] - corners[0][i] for i in range(3)]
                w = [corners[2][i] - corners[0][i] for i in range(3)]
                n = [u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0]]
                if axis_outward and n[0] * sum(c[0] for c in corners) + n[2] * sum(c[2] for c in corners) < 0:
                    n = [-x for x in n]
                length = math.sqrt(sum(x * x for x in n)) or 1.0
                ns = ((n[0] / length, n[1] / length, n[2] / length),) * 3
            out.append((corners, ns, rgb))      # type: ignore[arg-type]
    return out


def height_of(tris: list[Triangle]) -> float:
    return max(c[1] for t in tris for c in t[0])


def render(tris: list[Triangle], angle_deg: float, size: tuple[int, int] = (360, 640), elevation_deg: float = 8.0, background: tuple[int, int, int] = (242, 242, 242),
           height_m: float | None = None) -> Image.Image:
    """One picture: the scene turned ``angle_deg`` about the vertical axis (0 = seen from the front), the camera ``elevation_deg`` above the horizon."""
    width, height = size
    if width * height > MAX_PIXELS or width < 16 or height < 16:
        raise ValueError("picture size out of range")
    a, e = math.radians(angle_deg), math.radians(elevation_deg)
    ca, sa, ce, se = math.cos(a), math.sin(a), math.cos(e), math.sin(e)
    scale = height * 0.92 / ((height_m or height_of(tris)) * 1.04)
    cx, cy = width / 2.0, height * 0.96

    def rot(p: Vec) -> Vec:
        x, y, z = p
        x2, z2 = x * ca + z * sa, -x * sa + z * ca
        return x2, y * ce - z2 * se, y * se + z2 * ce
    image = Image.new("RGB", size, background)
    pixels = image.load()
    zbuf = [-1e9] * (width * height)
    for corners, normals, rgb in tris:
        rp = [rot(c) for c in corners]
        rn = [rot(n) for n in normals]
        sx = [cx + q[0] * scale for q in rp]
        sy = [cy - q[1] * scale for q in rp]
        x0, y0, x1, y1, x2, y2 = sx[0], sy[0], sx[1], sy[1], sx[2], sy[2]
        den = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
        if abs(den) < 1e-9:
            continue
        lo_x, hi_x = max(int(min(x0, x1, x2)), 0), min(int(max(x0, x1, x2)) + 1, width - 1)
        lo_y, hi_y = max(int(min(y0, y1, y2)), 0), min(int(max(y0, y1, y2)) + 1, height - 1)
        z0, z1, z2 = rp[0][2], rp[1][2], rp[2][2]
        for y in range(lo_y, hi_y + 1):
            row = y * width
            for x in range(lo_x, hi_x + 1):
                w0 = ((y1 - y2) * (x - x2) + (x2 - x1) * (y - y2)) / den
                w1 = ((y2 - y0) * (x - x2) + (x0 - x2) * (y - y2)) / den
                w2 = 1.0 - w0 - w1
                if w0 < -0.001 or w1 < -0.001 or w2 < -0.001:
                    continue
                z = w0 * z0 + w1 * z1 + w2 * z2
                if z <= zbuf[row + x]:
                    continue
                nx = w0 * rn[0][0] + w1 * rn[1][0] + w2 * rn[2][0]
                ny = w0 * rn[0][1] + w1 * rn[1][1] + w2 * rn[2][1]
                nz = w0 * rn[0][2] + w1 * rn[1][2] + w2 * rn[2][2]
                length = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
                diffuse = max(0.0, (nx * LIGHT[0] + ny * LIGHT[1] + nz * LIGHT[2]) / length) if nz >= 0 else 0.0
                shade = 0.45 + 0.65 * diffuse
                zbuf[row + x] = z
                pixels[x, y] = (min(255, int(rgb[0] * shade)), min(255, int(rgb[1] * shade)), min(255, int(rgb[2] * shade)))
    return image
