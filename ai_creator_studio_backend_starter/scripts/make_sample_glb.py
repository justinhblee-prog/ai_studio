"""Writes SYNTHETIC sample .glb files for compression measurements (no real artist models are used).
   python scripts/make_sample_glb.py <out_dir>      -> sphere_lo.glb (~2k tris), sphere_hi.glb (~33k tris, 1024px picture), sphere_hi_untextured.glb"""
import math
import struct
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.glb_tools import build_glb  # noqa: E402


def png(width: int, height: int) -> bytes:
    """A deterministic colourful picture (gradients + a plaid) written without any imaging library."""
    rows = []
    for y in range(height):
        row = bytearray([0])
        for x in range(width):
            plaid = 40 if ((x // 32) + (y // 32)) % 2 else 0
            row += bytes(((x * 255 // width + plaid) % 256, (y * 255 // height) % 256, ((x + y) * 255 // (width + height) + 90) % 256))
        rows.append(bytes(row))
    raw = zlib.compress(b"".join(rows), 6)
    def chunk(tag, data):
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)) + chunk(b"IDAT", raw) + chunk(b"IEND", b"")


def sphere(rings: int, segments: int, picture: bytes | None) -> bytes:
    pos, nrm, uv, idx = [], [], [], []
    for r in range(rings + 1):
        phi = math.pi * r / rings
        for s in range(segments + 1):
            theta = 2 * math.pi * s / segments
            x, y, z = math.sin(phi) * math.cos(theta), math.cos(phi), math.sin(phi) * math.sin(theta)
            pos += [x * 0.5, y * 0.5, z * 0.5]
            nrm += [x, y, z]
            uv += [s / segments, r / rings]
    for r in range(rings):
        for s in range(segments):
            a, b = r * (segments + 1) + s, (r + 1) * (segments + 1) + s
            idx += [a, b, a + 1, a + 1, b, b + 1]
    pb, nb, ub = struct.pack(f"<{len(pos)}f", *pos), struct.pack(f"<{len(nrm)}f", *nrm), struct.pack(f"<{len(uv)}f", *uv)
    ib = struct.pack(f"<{len(idx)}I", *idx)
    binary, views = b"", []
    def add(blob):
        nonlocal binary
        binary += b"\x00" * (-len(binary) % 4)
        views.append({"buffer": 0, "byteOffset": len(binary), "byteLength": len(blob)})
        binary += blob
        return len(views) - 1
    vp, vn, vu, vi = add(pb), add(nb), add(ub), add(ib)
    n = len(pos) // 3
    doc = {"asset": {"version": "2.0"}, "scene": 0, "scenes": [{"nodes": [0]}], "nodes": [{"mesh": 0}],
           "meshes": [{"primitives": [{"attributes": {"POSITION": 0, "NORMAL": 1, "TEXCOORD_0": 2}, "indices": 3, "material": 0}]}],
           "materials": [{"pbrMetallicRoughness": {"metallicFactor": 0.0, "roughnessFactor": 0.8}}],
           "accessors": [{"bufferView": vp, "componentType": 5126, "count": n, "type": "VEC3", "min": [-.5, -.5, -.5], "max": [.5, .5, .5]},
                         {"bufferView": vn, "componentType": 5126, "count": n, "type": "VEC3"}, {"bufferView": vu, "componentType": 5126, "count": n, "type": "VEC2"},
                         {"bufferView": vi, "componentType": 5125, "count": len(idx), "type": "SCALAR"}]}
    if picture:
        doc["images"] = [{"bufferView": add(picture), "mimeType": "image/png"}]
        doc["textures"] = [{"source": 0}]
        doc["materials"][0]["pbrMetallicRoughness"]["baseColorTexture"] = {"index": 0}
    doc["bufferViews"], doc["buffers"] = views, [{"byteLength": len(binary)}]
    return build_glb(doc, binary)


def main(argv=None) -> int:
    out = Path((argv or sys.argv[1:])[0])
    out.mkdir(parents=True, exist_ok=True)
    (out / "sphere_lo.glb").write_bytes(sphere(32, 32, png(256, 256)))
    (out / "sphere_hi.glb").write_bytes(sphere(128, 128, png(1024, 1024)))
    (out / "sphere_hi_untextured.glb").write_bytes(sphere(128, 128, None))
    for p in sorted(out.glob("*.glb")):
        print(p.name, p.stat().st_size)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
