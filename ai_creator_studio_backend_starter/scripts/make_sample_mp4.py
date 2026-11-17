"""Lane 4: write one sample MP4 (16:9, 5 seconds, pan with a crossfade, drawn pictures only) for the browser playback check.

    python scripts/make_sample_mp4.py out.mp4

Needs the ffmpeg executable (see docs/VIDEO_MP4.md). Prints what the file says about itself and its QC result; exits 1 if the QC fails.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PIL import Image, ImageDraw  # noqa: E402

from app import video_mp4  # noqa: E402


def picture(seed: int, size: tuple[int, int] = (1600, 1000)) -> Image.Image:
    shade = Image.linear_gradient("L").resize(size)
    img = Image.merge("RGB", (shade.point(lambda v: 60 + v // 2), shade.point(lambda v: 200 - v // 3), Image.new("L", size, 40 + 80 * seed)))
    draw = ImageDraw.Draw(img)
    draw.ellipse((300 + 200 * seed, 200, 900 + 200 * seed, 800), fill=(230, 60 + 80 * seed, 40))
    draw.rectangle((100, 820, 1500, 940), fill=(20, 40, 160))
    draw.rectangle((0, 0, 400, 1000), fill=(0, 0, 0))            # a black and a white band: the playback check looks for a wide brightness range
    draw.rectangle((1200, 0, 1600, 1000), fill=(255, 255, 255))
    return img


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: python scripts/make_sample_mp4.py out.mp4")
        return 2
    content, info = video_mp4.make_mp4([picture(0), picture(1)], "16:9", 5, "pan", "crossfade", comment="sample=true; drawn pictures; no AI")
    qc = video_mp4.qc_mp4(content, video_mp4.SIZES["16:9"], 5)
    Path(argv[0]).write_bytes(content)
    print(json.dumps({"bytes": len(content), "encode_ms": info["encode_ms"], "probe": qc["probe"], "qc_passed": qc["passed"]}, ensure_ascii=False))
    return 0 if qc["passed"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
