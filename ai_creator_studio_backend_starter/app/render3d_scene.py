"""R-ENGINE-10/11: the own3d scene as LAYERS - the plain body mannequin and every requested sample garment fitted to it - shared by the render job and the own3d mock provider.
Pure Python, no model, no network. ``garments.GarmentError`` is raised when a garment cannot be fitted (the body would poke through)."""
from __future__ import annotations

from typing import Any

from app import base_models, garments, render3d_soft
from app.garment_deform import deform_garment

SKIN = (214, 168, 128)
GARMENT_COLOURS = {"top": (60, 90, 160), "bottom": (70, 70, 90), "skirt": (200, 60, 80), "dress": (60, 140, 90), "jacket": (50, 60, 80)}


def build_layers(sex: str, measurements: dict[str, float] | None, garment_kinds: list[str], ease_cm: float = 4.0, colours: dict[str, tuple[int, int, int]] | None = None
                 ) -> tuple[list[render3d_soft.Triangle], list[tuple[str, list[render3d_soft.Triangle], tuple[int, int, int]]], list[dict[str, Any]]]:
    """(body triangles, [(kind, fitted garment triangles, asked-for colour)], fitting reports)."""
    body = base_models.build_base_model(sex, top_style="tank", bottom_style="shorts", skin=SKIN, top=SKIN, bottom=SKIN, measurements=measurements or None)
    layers, reports = [], []
    for kind in garment_kinds:
        colour = (colours or {}).get(kind, GARMENT_COLOURS[kind])
        glb, spec = garments.build_sample_garment(kind, sex, ease_cm, colour=colour)
        fitted, report = deform_garment(glb, spec, measurements or None)
        layers.append((kind, render3d_soft.triangles_of(fitted, axis_outward=True), colour))
        reports.append({"kind": kind, "penetrations": report["penetrations"], "method": report["method"]})
    return render3d_soft.triangles_of(body), layers, reports


def body_without_arms(sex: str, measurements: dict[str, float] | None) -> list[render3d_soft.Triangle]:
    """The same plain body minus its arms and hands, for judging sleeveless garments against the torso (``app/render_qc.py``)."""
    return render3d_soft.triangles_of(base_models.build_base_model(sex, top_style="tank", bottom_style="shorts", skin=SKIN, top=SKIN, bottom=SKIN, measurements=measurements or None, arms=False))
