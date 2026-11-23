"""M3 stage 1: a minimal XPBD (extended position based dynamics) cloth demo for ONE sleeveless top on the own3d torso - gravity drape + collision - in pure Python (no numpy, CPU).

Scope (honest): a research-grade demo, NOT a product feature and not wired to any API. One tube of cloth hangs from a pinned shoulder ring over an analytic torso (the same ellipse stack the body mesh
is built from, ``base_models.body_profiles``), falls under gravity and is pushed out of the body. No arms/sleeves, no self-collision, no friction model beyond a velocity damping at contact,
no seams or fabric anisotropy. See docs/CLOTH_XPBD.md for the memo and what a stage 2 needs.
"""
from __future__ import annotations

import math
import time
from typing import Any

from app import base_models
from app.render3d_soft import Triangle

Vec = list[float]
GRAVITY = -9.81
SKIN_MARGIN = 0.004            # metres kept between cloth and body surface


def torso_stack(sex: str, measurements: dict[str, float] | None = None) -> tuple[list[tuple[float, ...]], float]:
    """(torso rows (y, half-width, half-depth, z offset) ascending y, shoulder top y) of the body mesh's own profiles."""
    p = base_models._fit_measurements(base_models.PRESETS[sex], measurements) if measurements else dict(base_models.PRESETS[sex])
    rows = base_models.body_profiles(p, sex == "female")["torso"]
    return rows, 0.81 * p["height"]


def _at(rows: list[tuple[float, ...]], y: float) -> tuple[float, float, float]:
    """(half-width, half-depth, z offset) of the torso at height y (linear between rows, clamped)."""
    if y <= rows[0][0]:
        return rows[0][1], rows[0][2], rows[0][3]
    for a, b in zip(rows, rows[1:]):
        if y <= b[0]:
            t = (y - a[0]) / ((b[0] - a[0]) or 1.0)
            return tuple(a[k] + (b[k] - a[k]) * t for k in (1, 2, 3))     # type: ignore[return-value]
    return rows[-1][1], rows[-1][2], rows[-1][3]


class Cloth:
    def __init__(self, sex: str = "female", measurements: dict[str, float] | None = None, columns: int = 24, rows: int = 20, hem_y_share: float = 0.52, ease: float = 1.12,
                 stretch_compliance: float = 1e-7, bend_compliance: float = 5e-4, mass_per_m2: float = 0.18) -> None:
        self.torso, top_y = torso_stack(sex, measurements)
        self.columns, self.rows = columns, rows
        hem_y = hem_y_share * self.torso[-1][0] / 0.81 if False else self.torso[0][0] + 0.02
        top_y -= 0.015
        self.pos: list[Vec] = []
        for r in range(rows):
            y = top_y + (hem_y - top_y) * r / (rows - 1)
            a, b, zo = _at(self.torso, y)
            flare = 1.0 + 0.10 * (r / (rows - 1))                       # starts slightly A-line so there is something to drape
            for c in range(columns):
                t = 2 * math.pi * c / columns
                self.pos.append([a * ease * flare * math.sin(t), y, zo + b * ease * flare * math.cos(t)])
        self.prev = [p[:] for p in self.pos]
        self.vel = [[0.0, 0.0, 0.0] for _ in self.pos]
        area = 2 * math.pi * self.torso[len(self.torso) // 2][1] * (top_y - hem_y)
        particle_mass = mass_per_m2 * area / len(self.pos)
        self.inv_mass = [0.0 if i < columns else 1.0 / particle_mass for i in range(len(self.pos))]      # the top ring is pinned
        self.constraints: list[tuple[int, int, float, float]] = []   # (i, j, rest length, compliance)
        def idx(r: int, c: int) -> int:
            return r * columns + c % columns
        for r in range(rows):
            for c in range(columns):
                pairs = [(idx(r, c), idx(r, c + 1), stretch_compliance), (idx(r, c), idx(r, c + 2), bend_compliance)]
                if r + 1 < rows:
                    pairs += [(idx(r, c), idx(r + 1, c), stretch_compliance), (idx(r, c), idx(r + 1, c + 1), stretch_compliance * 4), (idx(r, c + 1), idx(r + 1, c), stretch_compliance * 4)]
                if r + 2 < rows:
                    pairs.append((idx(r, c), idx(r + 2, c), bend_compliance))
                for i, j, comp in pairs:
                    self.constraints.append((i, j, math.dist(self.pos[i], self.pos[j]), comp))
        self.triangles_idx = [(idx(r, c), idx(r + 1, c), idx(r, c + 1)) for r in range(rows - 1) for c in range(columns)] + \
                             [(idx(r, c + 1), idx(r + 1, c), idx(r + 1, c + 1)) for r in range(rows - 1) for c in range(columns)]

    def inside_body(self, p: Vec) -> tuple[bool, float]:
        """(is the point inside the (margin-grown) torso ellipse, normalised radius) at its height."""
        a, b, zo = _at(self.torso, p[1])
        a, b = a + SKIN_MARGIN, b + SKIN_MARGIN
        u, v = p[0] / a, (p[2] - zo) / b
        r = math.hypot(u, v)
        return r < 1.0, r

    def collide(self) -> int:
        """Push every particle out of the torso along the radial direction; returns how many had to move."""
        moved = 0
        for k, p in enumerate(self.pos):
            if self.inv_mass[k] == 0.0 or p[1] > self.torso[-1][0] or p[1] < self.torso[0][0] - 0.02:
                continue
            inside, r = self.inside_body(p)
            if inside:
                a, b, zo = _at(self.torso, p[1])
                a, b = a + SKIN_MARGIN, b + SKIN_MARGIN
                if r < 1e-6:
                    p[2] = zo + b
                else:
                    p[0] /= r
                    p[2] = zo + (p[2] - zo) / r
                moved += 1
        return moved

    def step(self, dt: float = 1 / 60, iterations: int = 6, damping: float = 0.985) -> None:
        for k, p in enumerate(self.pos):
            if self.inv_mass[k] == 0.0:
                continue
            self.vel[k][1] += GRAVITY * dt
            self.prev[k] = p[:]
            for a in range(3):
                p[a] += self.vel[k][a] * dt
        lambdas = [0.0] * len(self.constraints)
        for _ in range(iterations):
            for n, (i, j, rest, comp) in enumerate(self.constraints):
                wi, wj = self.inv_mass[i], self.inv_mass[j]
                if wi + wj == 0.0:
                    continue
                pi, pj = self.pos[i], self.pos[j]
                dx, dy, dz = pi[0] - pj[0], pi[1] - pj[1], pi[2] - pj[2]
                length = math.sqrt(dx * dx + dy * dy + dz * dz) or 1e-9
                alpha = comp / (dt * dt)
                dl = (-(length - rest) - alpha * lambdas[n]) / (wi + wj + alpha)
                lambdas[n] += dl
                s = dl / length
                for a, d in enumerate((dx, dy, dz)):
                    pi[a] += wi * s * d
                    pj[a] -= wj * s * d
            self.collide()
        for k, p in enumerate(self.pos):
            if self.inv_mass[k] == 0.0:
                continue
            self.vel[k] = [(p[a] - self.prev[k][a]) / dt * damping for a in range(3)]

    def run(self, steps: int = 240, **kw: Any) -> dict[str, Any]:
        t0 = time.time()
        for _ in range(steps):
            self.step(**kw)
        wall = time.time() - t0
        return {"steps": steps, "seconds": wall, "ms_per_step": 1000 * wall / steps, "particles": len(self.pos), "constraints": len(self.constraints), **self.measure()}

    def measure(self) -> dict[str, Any]:
        strains = [abs(math.dist(self.pos[i], self.pos[j]) - rest) / rest for i, j, rest, c in self.constraints if c <= 1e-6 and rest > 0]
        inside = sum(1 for k, p in enumerate(self.pos) if self.inv_mass[k] and self.torso[0][0] - 0.02 <= p[1] <= self.torso[-1][0] and self.inside_body(p)[0])
        speed = max(math.sqrt(sum(a * a for a in v)) for v in self.vel)
        hem = [self.pos[(self.rows - 1) * self.columns + c][1] for c in range(self.columns)]
        return {"max_stretch_strain": max(strains), "mean_stretch_strain": sum(strains) / len(strains), "particles_inside_body": inside, "max_speed_m_s": speed,
                "hem_y_mean": sum(hem) / len(hem), "hem_y_min": min(hem), "hem_y_max": max(hem)}

    def triangles(self, colour: tuple[int, int, int] = (60, 90, 160)) -> list[Triangle]:
        normals = [[0.0, 0.0, 0.0] for _ in self.pos]
        faces = []
        for i, j, k in self.triangles_idx:
            a, b, c = self.pos[i], self.pos[j], self.pos[k]
            u = [b[x] - a[x] for x in range(3)]
            w = [c[x] - a[x] for x in range(3)]
            n = [u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0]]
            for v in (i, j, k):
                for x in range(3):
                    normals[v][x] += n[x]
            faces.append((i, j, k))
        out = []
        for m in normals:
            length = math.sqrt(sum(x * x for x in m)) or 1.0
            m[:] = [x / length for x in m]
        for i, j, k in faces:
            corners = tuple(tuple(self.pos[v]) for v in (i, j, k))
            # the tube's outside faces away from its own axis: flip so shading and back-face culling see the outside
            ns = tuple(tuple(normals[v]) for v in (i, j, k))
            cx = sum(c[0] for c in corners) / 3
            cz = sum(c[2] for c in corners) / 3
            if sum(n[0] * cx + n[2] * cz for n in ns) < 0:
                ns = tuple(tuple(-x for x in n) for n in ns)
            out.append((corners, ns, colour))
        return out       # type: ignore[return-value]


__all__ = ["Cloth", "torso_stack"]
