"""Lane 1 / E-04: a STATIC performance budget for a .glb: how heavy is it for a phone, a laptop, a desktop?

What it measures (pure Python + Pillow, no GPU, no browser, no network): triangles, vertices, draw calls (one per mesh primitive: the cost a renderer pays per object), the file size, and the
TEXTURE MEMORY the GPU would hold (each embedded picture decoded to RGBA = width x height x 4 bytes, plus a third more for its mip levels, each picture counted once however many
materials use it). It compares them with a budget per device class and, when a number is over, says by how much the model has to shrink (the "LOD hint": the ratio a simplified copy must reach).
What it does NOT do: it does not measure FPS (headless CI has no GPU, a software-GL frame time says nothing about a phone), does not simplify a mesh or build LOD levels (that needs a mesh
simplifier that is not approved), and cannot read compressed textures (KTX2/Basis, WebP): such a model gets ``texture_bytes: None`` and a warning, never a guessed number.
The budget numbers are PROPOSALS (the design window decides); they are rules of thumb for interactive WebGL viewers, not measurements of this product.
"""
from __future__ import annotations

import io
from typing import Any

from PIL import Image

from app.glb_tools import GlbError, inspect_glb, parse_glb

MIP_FACTOR = 4 / 3
PROFILES: dict[str, dict[str, float]] = {            # PROPOSALS
    "mobile":  {"triangles": 100_000, "draw_calls": 50, "texture_mb": 64, "file_mb": 20, "max_texture_side": 2048},
    "laptop":  {"triangles": 500_000, "draw_calls": 200, "texture_mb": 256, "file_mb": 60, "max_texture_side": 4096},
    "desktop": {"triangles": 2_000_000, "draw_calls": 500, "texture_mb": 1024, "file_mb": 150, "max_texture_side": 8192},
}
Image.MAX_IMAGE_PIXELS = 200_000_000                  # a bomb is refused by Pillow, not decoded


def _vertices_and_calls(doc: dict[str, Any]) -> tuple[int, int]:
    vertices = calls = 0
    for mesh in doc.get("meshes", []):
        for prim in mesh.get("primitives", []):
            calls += 1
            index = prim.get("attributes", {}).get("POSITION")
            if index is not None and index < len(doc.get("accessors", [])):
                vertices += int(doc["accessors"][index].get("count", 0))
    return vertices, calls


def _textures(doc: dict[str, Any], binary: bytes) -> tuple[int | None, int, list[dict[str, Any]], list[str]]:
    """(texture bytes on the GPU or None when something cannot be read, largest side, per-picture records, warnings)."""
    views, total, widest, records, warnings, unknown, seen = doc.get("bufferViews", []), 0, 0, [], [], False, set()
    for number, image in enumerate(doc.get("images", [])):
        view = image.get("bufferView")
        if view is None:
            warnings.append(f"image {number}: stored by address, its size cannot be read here")
            unknown = True
            continue
        if view in seen:                                   # byte-identical pictures that share one view are one GPU texture
            continue
        seen.add(view)
        start, length = int(views[view].get("byteOffset", 0)), int(views[view]["byteLength"])
        try:
            with Image.open(io.BytesIO(binary[start:start + length])) as opened:
                width, height = opened.size
        except Exception:  # noqa: BLE001 - an unreadable or compressed picture is reported, not guessed
            warnings.append(f"image {number}: {image.get('mimeType', 'unknown type')} cannot be measured (compressed or unreadable)")
            unknown = True
            continue
        gpu = int(width * height * 4 * MIP_FACTOR)
        total += gpu
        widest = max(widest, width, height)
        records.append({"image": number, "width": width, "height": height, "gpu_bytes": gpu, "power_of_two": width & (width - 1) == 0 and height & (height - 1) == 0})
    return (None if unknown else total), widest, records, warnings


def analyze(glb: bytes) -> dict[str, Any]:
    """The numbers of one model. Raises GlbError for a file that is not a .glb."""
    doc, binary = parse_glb(glb)
    base = inspect_glb(glb)
    vertices, calls = _vertices_and_calls(doc)
    texture_bytes, widest, records, warnings = _textures(doc, bytes(binary))
    if any(not r["power_of_two"] for r in records):
        warnings.append("some pictures are not a power of two: older GPUs/WebGL1 pad or refuse them")
    return {"file_bytes": base["file_bytes"], "triangles": base["triangles"], "vertices": vertices, "draw_calls": calls, "meshes": base["meshes"], "materials": base["materials"],
            "textures": len(doc.get("textures", [])), "texture_bytes": texture_bytes, "max_texture_side": widest, "pictures": records, "warnings": warnings}


def check(info: dict[str, Any], profile: str) -> dict[str, Any]:
    """Compare ``analyze`` output with a device class. ``passed`` is True only when every KNOWN number is within the budget; an unknown number is listed under ``unknown``, not passed silently."""
    if profile not in PROFILES:
        raise ValueError(f"profile must be one of {sorted(PROFILES)}")
    limits = PROFILES[profile]
    values = {"triangles": info["triangles"], "draw_calls": info["draw_calls"], "texture_mb": None if info["texture_bytes"] is None else info["texture_bytes"] / 1_048_576,
              "file_mb": info["file_bytes"] / 1_048_576, "max_texture_side": info["max_texture_side"]}
    rows, over, unknown = {}, [], []
    for name, limit in limits.items():
        value = values[name]
        if value is None:
            unknown.append(name)
            rows[name] = {"value": None, "limit": limit, "ok": None, "share_of_limit": None}
            continue
        ok = value <= limit
        rows[name] = {"value": round(value, 3), "limit": limit, "ok": ok, "share_of_limit": round(value / limit, 3)}
        if not ok:
            over.append(name)
    hints = []
    if "triangles" in over:
        hints.append(f"simplify the mesh to {limits['triangles'] / values['triangles']:.0%} of its triangles or less (a LOD copy; no simplifier is built in)")
    if "draw_calls" in over:
        hints.append(f"merge meshes that share a material: {info['draw_calls']} draw calls, budget {int(limits['draw_calls'])}")
    if "texture_mb" in over:
        side = max(16, int(info['max_texture_side'] * (limits['texture_mb'] / values['texture_mb']) ** 0.5))
        hints.append(f"shrink the pictures: about {side} px on the longest side would fit the texture budget")
    if "max_texture_side" in over:
        hints.append(f"no picture may be larger than {int(limits['max_texture_side'])} px on a side")
    if "file_mb" in over:
        hints.append(f"the file is {values['file_mb']:.1f} MB, budget {int(limits['file_mb'])} MB")
    return {"profile": profile, "passed": not over and not unknown, "over": over, "unknown": unknown, "rows": rows, "hints": hints, "proposal": True}


def report(glb: bytes) -> dict[str, Any]:
    info = analyze(glb)
    return {"info": info, "profiles": {name: check(info, name) for name in PROFILES}}


__all__ = ["PROFILES", "analyze", "check", "report", "GlbError"]
