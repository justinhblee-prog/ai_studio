"""E-03: a more PHOTO-LIKE picture of the own3d scene, still pure Python + Pillow (no GPU, no model, no new dependency), next to ``render3d_soft`` (which stays the fast mock).

What it adds over ``render3d_soft`` (each one is a switch, see ``render_photo``):
  * three-point lighting (warm key, cool fill, rim from behind) plus a hemispheric ambient term, computed in LINEAR light and encoded with a 2.2 gamma;
  * two materials: ``skin`` (wrap-around diffuse, a faint warm tint at the light's edge, a small highlight) and ``cloth`` (rougher, a soft sheen at grazing angles, no highlight);
  * screen-space ambient occlusion (SSAO) from the depth buffer: creases, armpits, the garment edge over the body get darker;
  * a floor: a soft shadow cast by the key light plus a tighter contact shadow under the feet, fading out into the background (a "studio sweep");
  * anti-aliased edges by 2x2 supersampling.
What it is NOT: not ray traced, no self-shadowing from the key light on the figure, no textures, no real subsurface scattering, orthographic camera. It looks better than the mock, not like a photograph.
Slow on purpose (about 4x the pixels of the mock, plus SSAO): the job path keeps using ``render3d_soft``; this module is for stills and comparisons (``scripts/render_photo_compare.py``).
"""
from __future__ import annotations

import math
from array import array

from PIL import Image, ImageDraw, ImageFilter

from app import render3d_scene, render3d_soft
from app.render3d_soft import Triangle

GAMMA = 2.2
FLOOR_RADIUS_M = 1.0                 # the floor patch fades out between 45 % and 100 % of this
MAX_SAMPLES = 4_000_000              # final pixels x supersampling^2
MATERIALS = {
    "skin": {"wrap": 0.35, "spec": 0.10, "shin": 28.0, "sss": 0.20, "sheen": 0.0},
    "cloth": {"wrap": 0.12, "spec": 0.0, "shin": 8.0, "sss": 0.0, "sheen": 0.20},
}
MAT_ID = {"skin": 1, "cloth": 2}


def _unit(v: tuple[float, float, float]) -> tuple[float, float, float]:
    n = math.sqrt(sum(c * c for c in v)) or 1.0
    return v[0] / n, v[1] / n, v[2] / n


# lights in CAMERA space (x right, y up, z towards the viewer): a turntable turns the object under fixed studio lights
KEY = (_unit((-0.55, 0.65, 0.55)), (1.00, 0.96, 0.90), 1.00)
FILL = (_unit((0.70, 0.15, 0.65)), (0.80, 0.88, 1.00), 0.32)
RIM = (_unit((0.10, 0.45, -0.80)), (1.00, 1.00, 1.00), 0.55)
SKY, GROUND = (0.40, 0.44, 0.50), (0.26, 0.24, 0.22)
AMBIENT = 0.55


def _lin(c: int) -> float:
    return (c / 255.0) ** GAMMA


def _enc(v: float) -> int:
    return 255 if v >= 1.0 else int(255.0 * (v if v > 0.0 else 0.0) ** (1.0 / GAMMA) + 0.5)


def render_photo(layers: list[tuple[list[Triangle], str]], angle_deg: float, size: tuple[int, int] = (360, 640), elevation_deg: float = 10.0, background: tuple[int, int, int] = (226, 228, 234),
                 height_m: float | None = None, ss: int = 2, ao: bool = True, floor: bool = True) -> Image.Image:
    """One picture of ``layers`` = [(triangles, material)] (material ``skin`` or ``cloth``), the scene turned ``angle_deg`` about the vertical axis (0 = from the front).
    ``ss`` is the supersampling factor per axis (1 = no anti-aliasing), ``ao`` switches the occlusion, ``floor`` the floor shadows. Same input -> same pixels."""
    w, h = size
    if ss not in (1, 2, 3) or w < 16 or h < 16 or w * h * ss * ss > MAX_SAMPLES:
        raise ValueError("picture size or supersampling out of range")
    for _, material in layers:
        if material not in MATERIALS:
            raise ValueError(f"unknown material {material!r}")
    sw, sh = w * ss, h * ss
    every = [t for tris, _ in layers for t in tris]
    scale = sh * 0.92 / ((height_m or render3d_soft.height_of(every)) * 1.04)
    cx, cy = sw / 2.0, sh * 0.96
    a, e = math.radians(angle_deg), math.radians(elevation_deg)
    ca, sa, ce, se = math.cos(a), math.sin(a), math.cos(e), math.sin(e)

    def rot(p):
        x, y, z = p
        x2, z2 = x * ca + z * sa, -x * sa + z * ca
        return x2, y * ce - z2 * se, y * se + z2 * ce
    up = (0.0, ce, se)                                                       # the world's up in camera space (the floor's normal)

    # ---- G-buffer: depth, normal, albedo, material per supersampled pixel (nearer = larger z, as in render3d_soft)
    n_px = sw * sh
    zbuf = array("d", [-1e9]) * n_px
    nxs, nys, nzs = array("f", [0.0]) * n_px, array("f", [0.0]) * n_px, array("f", [0.0]) * n_px
    red, grn, blu, mat = bytearray(n_px), bytearray(n_px), bytearray(n_px), bytearray(n_px)
    for tris, material in layers:
        mid = MAT_ID[material]
        for corners, normals, rgb in tris:
            rn = [rot(n) for n in normals]
            if rn[0][2] + rn[1][2] + rn[2][2] <= 0:
                continue                                                      # back faces: never seen, and an open sleeve's inside must not show
            rp = [rot(c) for c in corners]
            sx = [cx + q[0] * scale for q in rp]
            sy = [cy - q[1] * scale for q in rp]
            x0, y0, x1, y1, x2, y2 = sx[0], sy[0], sx[1], sy[1], sx[2], sy[2]
            den = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
            if abs(den) < 1e-9:
                continue
            lo_x, hi_x = max(int(min(x0, x1, x2)), 0), min(int(max(x0, x1, x2)) + 1, sw - 1)
            lo_y, hi_y = max(int(min(y0, y1, y2)), 0), min(int(max(y0, y1, y2)) + 1, sh - 1)
            z0, z1, z2 = rp[0][2], rp[1][2], rp[2][2]
            for y in range(lo_y, hi_y + 1):
                row = y * sw
                for x in range(lo_x, hi_x + 1):
                    w0 = ((y1 - y2) * (x - x2) + (x2 - x1) * (y - y2)) / den
                    w1 = ((y2 - y0) * (x - x2) + (x0 - x2) * (y - y2)) / den
                    w2 = 1.0 - w0 - w1
                    if w0 < -0.001 or w1 < -0.001 or w2 < -0.001:
                        continue
                    z = w0 * z0 + w1 * z1 + w2 * z2
                    i = row + x
                    if z <= zbuf[i]:
                        continue
                    nx = w0 * rn[0][0] + w1 * rn[1][0] + w2 * rn[2][0]
                    ny = w0 * rn[0][1] + w1 * rn[1][1] + w2 * rn[2][1]
                    nz = w0 * rn[0][2] + w1 * rn[1][2] + w2 * rn[2][2]
                    ln = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
                    zbuf[i] = z
                    nxs[i], nys[i], nzs[i] = nx / ln, ny / ln, nz / ln
                    red[i], grn[i], blu[i], mat[i] = rgb[0], rgb[1], rgb[2], mid

    # ---- screen-space ambient occlusion from the depth buffer
    occl = bytearray(n_px)
    if ao:
        radius = max(3, int(0.045 * scale))
        taps = [(radius, 0), (-radius, 0), (0, radius), (0, -radius), (int(radius * 0.7), int(radius * 0.7)), (-int(radius * 0.7), int(radius * 0.7)),
                (int(radius * 0.7), -int(radius * 0.7)), (-int(radius * 0.7), -int(radius * 0.7))]
        for y in range(sh):
            for x in range(sw):
                i = y * sw + x
                if not mat[i]:
                    continue
                z = zbuf[i]
                hit = 0
                for dx, dy in taps:
                    xx, yy = x + dx, y + dy
                    if 0 <= xx < sw and 0 <= yy < sh:
                        d = zbuf[yy * sw + xx] - z
                        if 0.03 < d < 0.15:
                            hit += 1
                occl[i] = hit * 31                                            # 0..248
        blurred = Image.frombytes("L", (sw, sh), bytes(occl)).filter(ImageFilter.GaussianBlur(max(1.0, radius / 3.0)))      # interleaved depth of two layers must not show as moire
        mask_bytes = bytes(1 if m else 0 for m in mat)
        occl = bytearray(b if k else 0 for b, k in zip(blurred.tobytes(), mask_bytes))

    # ---- floor shadows: project every triangle onto the floor plane along the key light (soft) and straight down (contact, only near the floor)
    soft_mask = contact_mask = None
    if floor:
        soft_mask, contact_mask = Image.new("L", (sw, sh), 0), Image.new("L", (sw, sh), 0)
        sd, cd = ImageDraw.Draw(soft_mask), ImageDraw.Draw(contact_mask)
        lk = KEY[0]
        k_den = up[0] * lk[0] + up[1] * lk[1] + up[2] * lk[2]
        for tris, _ in layers:
            for corners, _n, _c in tris:
                rp = [rot(c) for c in corners]
                heights = [c[1] for c in corners]
                if k_den > 0.1:
                    poly = []
                    for p in rp:
                        t = (up[0] * p[0] + up[1] * p[1] + up[2] * p[2]) / k_den
                        poly.append((cx + (p[0] - lk[0] * t) * scale, cy - (p[1] - lk[1] * t) * scale))
                    sd.polygon(poly, fill=255)
                if min(heights) < 0.12:
                    poly = []
                    for p in rp:
                        t = up[0] * p[0] + up[1] * p[1] + up[2] * p[2]
                        poly.append((cx + (p[0] - up[0] * t) * scale, cy - (p[1] - up[1] * t) * scale))
                    cd.polygon(poly, fill=255)
        soft_mask = soft_mask.filter(ImageFilter.GaussianBlur(0.035 * scale))
        contact_mask = contact_mask.filter(ImageFilter.GaussianBlur(0.018 * scale))

    # ---- shade and compose (linear light, then 2.2 gamma)
    bg_lin = [_lin(c) for c in background]
    out = Image.new("RGB", (sw, sh))
    px = out.load()
    soft_px = soft_mask.load() if soft_mask else None
    contact_px = contact_mask.load() if contact_mask else None
    klin, kcol, kint = KEY
    flin, fcol, fint = FILL
    rlin, rcol, rint = RIM
    inv_ce_se = ng_z = up[2]
    for y in range(sh):
        v = y / (sh - 1)
        row_gain = 1.04 - 0.09 * v                                           # a very gentle top-to-bottom falloff of the backdrop
        base = (_enc(bg_lin[0] * row_gain), _enc(bg_lin[1] * row_gain), _enc(bg_lin[2] * row_gain))
        for x in range(sw):
            i = y * sw + x
            m = mat[i]
            if not m:
                colour = base
                if floor and ng_z > 0.05:
                    xc, yc = (x - cx) / scale, (cy - y) / scale
                    zc = -(up[0] * xc + up[1] * yc) / ng_z                   # the floor point seen at this pixel (orthographic camera)
                    yo = yc * ce + zc * se
                    z2 = -yc * se + zc * ce
                    xo, zo = xc * ca - z2 * sa, xc * sa + z2 * ca
                    r = math.sqrt(xo * xo + zo * zo)
                    if r < FLOOR_RADIUS_M:
                        fade = 1.0 if r <= 0.45 * FLOOR_RADIUS_M else (FLOOR_RADIUS_M - r) / (0.55 * FLOOR_RADIUS_M)
                        shadow = 1.0 - 0.62 * soft_px[x, y] / 255.0
                        shadow *= 1.0 - 0.50 * contact_px[x, y] / 255.0
                        gain = 1.0 - (1.0 - shadow) * fade
                        if gain < 1.0:
                            colour = (_enc(bg_lin[0] * row_gain * gain), _enc(bg_lin[1] * row_gain * gain), _enc(bg_lin[2] * row_gain * gain))
                px[x, y] = colour
                continue
            spec_mat = MATERIALS["skin" if m == 1 else "cloth"]
            nx, ny, nz = nxs[i], nys[i], nzs[i]
            alb = (_lin(red[i]), _lin(grn[i]), _lin(blu[i]))
            wrap = spec_mat["wrap"]
            ndl_k = nx * klin[0] + ny * klin[1] + nz * klin[2]
            ndl_f = nx * flin[0] + ny * flin[1] + nz * flin[2]
            ndl_r = nx * rlin[0] + ny * rlin[1] + nz * rlin[2]
            dk, df, dr = (max(0.0, (ndl_k + wrap) / (1 + wrap)), max(0.0, (ndl_f + wrap) / (1 + wrap)), max(0.0, (ndl_r + wrap) / (1 + wrap)))
            hemi = (nx * up[0] + ny * up[1] + nz * up[2]) * 0.5 + 0.5
            occ = occl[i] / 248.0 if ao else 0.0
            amb = [AMBIENT * (GROUND[c] + (SKY[c] - GROUND[c]) * hemi) for c in range(3)]
            lit = []
            for c in range(3):
                soft = (amb[c] + df * fcol[c] * fint) * (1.0 - 0.65 * occ)
                lit.append(alb[c] * (soft + dk * kcol[c] * kint * (1.0 - 0.35 * occ) + dr * rcol[c] * rint))
            if spec_mat["sss"]:
                edge = max(0.0, 1.0 - abs(ndl_k) / 0.5) * (1.0 if ndl_k > -0.3 else 0.0)        # warm tint where the light turns away
                for c, tint in enumerate((1.0, 0.30, 0.20)):
                    lit[c] += alb[c] * spec_mat["sss"] * edge * tint
            if spec_mat["spec"]:
                hx, hy, hz = klin[0], klin[1], klin[2] + 1.0
                hn = math.sqrt(hx * hx + hy * hy + hz * hz)
                nh = max(0.0, (nx * hx + ny * hy + nz * hz) / hn)
                s = spec_mat["spec"] * nh ** spec_mat["shin"] * (1.0 - 0.5 * occ)
                for c in range(3):
                    lit[c] += s * kcol[c] * kint
            if spec_mat["sheen"]:
                fres = (1.0 - max(0.0, nz)) ** 3
                for c in range(3):
                    lit[c] += alb[c] * spec_mat["sheen"] * fres * (1.0 - 0.5 * occ)
            px[x, y] = (_enc(lit[0]), _enc(lit[1]), _enc(lit[2]))
    return out if ss == 1 else out.resize((w, h), Image.BOX)


def render_scene(sex: str, measurements: dict[str, float] | None, garment_kinds: list[str], angle_deg: float, **kwargs) -> Image.Image:
    """Convenience: the plain body (skin) + the fitted sample garments (cloth) of ``render3d_scene.build_layers``."""
    body, layers, _ = render3d_scene.build_layers(sex, measurements, garment_kinds)
    return render_photo([(body, "skin")] + [(tris, "cloth") for _, tris, _ in layers], angle_deg, **kwargs)


__all__ = ["render_photo", "render_scene", "MATERIALS"]
