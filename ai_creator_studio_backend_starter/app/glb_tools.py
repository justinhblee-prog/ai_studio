"""Lane 1 / E-01: GLB inspection and normalization in pure Python (no new dependency).

``inspect_glb`` reports the numbers a human or a gate needs (file size, triangles, meshes, materials, textures, embedded picture bytes, local-space bounds).
``normalize_glb`` rewrites a single-buffer GLB into a canonical, smaller form WITHOUT changing what it draws:
  * compact JSON, 4-byte alignment, one BIN chunk;
  * byte-identical embedded pictures are stored once (images keep their index, they just share one bufferView);
  * bufferViews nothing refers to are dropped and the rest are re-packed;
  * running it again changes nothing (idempotent).
It does NOT re-compress meshes or textures (no Draco/meshopt/KTX2 here: that needs tools that are not approved) and it refuses files it cannot
rewrite safely (external URIs, several buffers, sparse accessors referring to views we would move) by returning them unchanged with a reason.
Bounds are local-space (accessor min/max); node transforms are NOT applied.
"""
from __future__ import annotations

import hashlib
import json
import struct
from typing import Any

MAGIC, JSON_CHUNK, BIN_CHUNK = 0x46546C67, 0x4E4F534A, 0x004E4942


class GlbError(ValueError):
    pass


def parse_glb(data: bytes) -> tuple[dict[str, Any], bytes]:
    if len(data) < 20 or struct.unpack_from("<I", data, 0)[0] != MAGIC:
        raise GlbError("not a binary glTF (.glb)")
    version, total = struct.unpack_from("<II", data, 4)
    if version != 2 or total > len(data):
        raise GlbError("unsupported GLB version or truncated file")
    pos, doc, binary = 12, None, b""
    while pos + 8 <= total:
        length, kind = struct.unpack_from("<II", data, pos)
        body = data[pos + 8: pos + 8 + length]
        if len(body) != length:
            raise GlbError("truncated chunk")
        if kind == JSON_CHUNK and doc is None:
            doc = json.loads(body.decode("utf-8").rstrip(" \x00"))
        elif kind == BIN_CHUNK and not binary:
            binary = bytes(body)
        pos += 8 + length + (-length % 4)
    if not isinstance(doc, dict):
        raise GlbError("GLB has no JSON chunk")
    return doc, binary


def build_glb(doc: dict[str, Any], binary: bytes) -> bytes:
    raw = json.dumps(doc, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    raw += b" " * (-len(raw) % 4)
    chunks = struct.pack("<II", len(raw), JSON_CHUNK) + raw
    if binary:
        padded = binary + b"\x00" * (-len(binary) % 4)
        chunks += struct.pack("<II", len(padded), BIN_CHUNK) + padded
    return struct.pack("<III", MAGIC, 2, 12 + len(chunks)) + chunks


def _accessor_triangles(doc: dict[str, Any], prim: dict[str, Any]) -> int:
    accessors = doc.get("accessors", [])
    mode = prim.get("mode", 4)
    if "indices" in prim:
        count = int(accessors[prim["indices"]].get("count", 0))
    else:
        pos = prim.get("attributes", {}).get("POSITION")
        count = int(accessors[pos].get("count", 0)) if pos is not None else 0
    if mode == 4:
        return count // 3
    if mode in (5, 6):
        return max(count - 2, 0)
    return 0


def inspect_glb(data: bytes) -> dict[str, Any]:
    doc, binary = parse_glb(data)
    views = doc.get("bufferViews", [])
    image_bytes = sum(int(views[i["bufferView"]].get("byteLength", 0)) for i in doc.get("images", []) if "bufferView" in i)
    triangles, lo, hi = 0, None, None
    for mesh in doc.get("meshes", []):
        for prim in mesh.get("primitives", []):
            triangles += _accessor_triangles(doc, prim)
            pos = prim.get("attributes", {}).get("POSITION")
            acc = doc.get("accessors", [])[pos] if pos is not None else None
            if acc and acc.get("min") and acc.get("max") and len(acc["min"]) == 3:
                lo = acc["min"] if lo is None else [min(a, b) for a, b in zip(lo, acc["min"])]
                hi = acc["max"] if hi is None else [max(a, b) for a, b in zip(hi, acc["max"])]
    size = [round(h - l, 6) for l, h in zip(lo, hi)] if lo and hi else None
    return {"file_bytes": len(data), "json_bytes": len(json.dumps(doc, separators=(",", ":")).encode()), "binary_bytes": len(binary), "meshes": len(doc.get("meshes", [])),
            "nodes": len(doc.get("nodes", [])), "triangles": triangles, "materials": len(doc.get("materials", [])), "textures": len(doc.get("textures", [])),
            "images": len(doc.get("images", [])), "image_bytes": image_bytes, "bounds_min": lo, "bounds_max": hi, "size": size,
            "has_external_uri": any("uri" in x and not str(x["uri"]).startswith("data:") for k in ("buffers", "images") for x in doc.get(k, []))}


def _unsafe_reason(doc: dict[str, Any], binary: bytes) -> str | None:
    if any("uri" in b for b in doc.get("buffers", [])):
        return "buffer uses a URI (only a single embedded GLB buffer can be rewritten)"
    if len(doc.get("buffers", [])) > 1:
        return "more than one buffer"
    if any("uri" in i for i in doc.get("images", [])):
        return "image uses a URI"
    if doc.get("buffers") and not binary:
        return "buffer declared but no BIN chunk"
    for key in ("bufferViews",):
        if any(v.get("buffer", 0) != 0 for v in doc.get(key, [])):
            return "bufferView points at another buffer"
    return None


def normalize_glb(data: bytes) -> tuple[bytes, dict[str, Any]]:
    """Returns (bytes, report). If the file cannot be rewritten safely the original bytes come back with ``changed=False`` and a ``reason``."""
    doc, binary = parse_glb(data)
    before = inspect_glb(data)
    reason = _unsafe_reason(doc, binary)
    if reason:
        return data, {"changed": False, "reason": reason, "before": before, "after": before, "deduplicated_images": 0, "dropped_buffer_views": 0}
    views = doc.get("bufferViews", [])
    # 1. share identical pictures
    seen, merged = {}, 0
    for image in doc.get("images", []):
        if "bufferView" not in image:
            continue
        view = views[image["bufferView"]]
        start = int(view.get("byteOffset", 0))
        digest = hashlib.sha256(binary[start:start + int(view["byteLength"])]).hexdigest()
        key = (digest, image.get("mimeType"))
        if key in seen and seen[key] != image["bufferView"]:
            image["bufferView"] = seen[key]
            merged += 1
        else:
            seen.setdefault(key, image["bufferView"])
    # 2. keep only referenced bufferViews, re-pack them 4-byte aligned
    used: set[int] = set()
    for acc in doc.get("accessors", []):
        if "bufferView" in acc:
            used.add(acc["bufferView"])
        sparse = acc.get("sparse")
        if sparse:
            used.add(sparse["indices"]["bufferView"])
            used.add(sparse["values"]["bufferView"])
    for image in doc.get("images", []):
        if "bufferView" in image:
            used.add(image["bufferView"])
    if any(v.get("extensions") for v in views) or any(p.get("extensions") for m in doc.get("meshes", []) for p in m.get("primitives", [])):
        return data, {"changed": False, "reason": "compressed (Draco/meshopt) or extension-bound buffer views are left untouched", "before": before, "after": before,
                      "deduplicated_images": 0, "dropped_buffer_views": 0}
    order = sorted(used)
    remap, new_views, out = {}, [], bytearray()
    for old in order:
        view = dict(views[old])
        start, length = int(view.get("byteOffset", 0)), int(view["byteLength"])
        out += b"\x00" * (-len(out) % 4)
        view["byteOffset"] = len(out)
        view["buffer"] = 0
        out += binary[start:start + length]
        remap[old] = len(new_views)
        new_views.append(view)
    for acc in doc.get("accessors", []):
        if "bufferView" in acc:
            acc["bufferView"] = remap[acc["bufferView"]]
        sparse = acc.get("sparse")
        if sparse:
            sparse["indices"]["bufferView"] = remap[sparse["indices"]["bufferView"]]
            sparse["values"]["bufferView"] = remap[sparse["values"]["bufferView"]]
    for image in doc.get("images", []):
        if "bufferView" in image:
            image["bufferView"] = remap[image["bufferView"]]
    dropped = len(views) - len(new_views)
    if new_views:
        doc["bufferViews"] = new_views
    else:
        doc.pop("bufferViews", None)
    if doc.get("buffers"):
        doc["buffers"][0] = {"byteLength": len(out)}
    result = build_glb(doc, bytes(out))
    after = inspect_glb(result)
    return result, {"changed": result != data, "reason": None, "before": before, "after": after, "deduplicated_images": merged, "dropped_buffer_views": dropped,
                    "saved_bytes": len(data) - len(result)}
