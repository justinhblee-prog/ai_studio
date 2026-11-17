"""Lane 4 / E-08b: turn the server-side render's 360-degree set (turn_000.png ...) into a rotating-object MP4.

    python scripts/turntable_mp4.py <folder with turn_*.png> out.mp4 [aspect=9:16] [seconds=5] [turns=1]

Needs the ffmpeg executable. Prints the file's own description and its QC result; exits 1 if the QC fails, 2 on wrong usage or no pictures.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PIL import Image  # noqa: E402

from app import video_mp4  # noqa: E402


def main(argv: list[str]) -> int:
    if not (2 <= len(argv) <= 5):
        print("usage: python scripts/turntable_mp4.py <folder with turn_*.png> out.mp4 [aspect] [seconds] [turns]")
        return 2
    files = sorted(Path(argv[0]).glob("turn_*.png"))
    if not files:
        print(f"no turn_*.png in {argv[0]}")
        return 2
    aspect = argv[2] if len(argv) > 2 else "9:16"
    seconds = int(argv[3]) if len(argv) > 3 else 5
    turns = int(argv[4]) if len(argv) > 4 else 1
    cuts = []
    for file in files:
        with Image.open(file) as opened:
            cuts.append(opened.convert("RGB"))
    content, info = video_mp4.make_turntable_mp4(cuts, aspect, seconds, turns, comment="source=3d_rotation_cuts; server-side render; no AI")
    qc = video_mp4.qc_mp4(content, video_mp4.SIZES[aspect], seconds)
    Path(argv[1]).write_bytes(content)
    print(json.dumps({"cuts": len(cuts), "cut_size": list(cuts[0].size), "bytes": len(content), "encode_ms": info["encode_ms"], "blended_frames": info["blended_frames"], "probe": qc["probe"],
                      "qc_passed": qc["passed"], "warnings": [c for c in qc["checks"] if c["level"] == "warn"]}, ensure_ascii=False))
    return 0 if qc["passed"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
