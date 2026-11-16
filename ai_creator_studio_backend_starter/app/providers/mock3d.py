"""Flow-only image -> 3D adapter (lane 5). It does NOT reconstruct anything: it returns a tiny valid .glb (glTF 2.0, one named node) that records the SHA-256 of the picture, so the whole
pipeline (job, cost record, storage, validation, library) can be tested without a provider, a key or a GPU."""
from __future__ import annotations

import hashlib
import json
import struct


class MockImageTo3D:
    name = "mock3d"
    model = "mock-image-to-3d"

    async def convert(self, image_bytes: bytes) -> bytes:
        if not image_bytes:
            raise ValueError("empty picture")
        doc = {"asset": {"version": "2.0", "generator": "ai-creator-studio mock3d"}, "scene": 0, "scenes": [{"nodes": [0]}],
               "nodes": [{"name": "mock-placeholder", "extras": {"source_sha256": hashlib.sha256(image_bytes).hexdigest(), "is_reconstruction": False}}]}
        raw = json.dumps(doc, separators=(",", ":")).encode()
        raw += b" " * ((4 - len(raw) % 4) % 4)
        chunk = struct.pack("<II", len(raw), 0x4E4F534A) + raw
        return b"glTF" + struct.pack("<II", 2, 12 + len(chunk)) + chunk
