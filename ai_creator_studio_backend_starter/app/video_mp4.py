"""Lane 4 / E-08a: real MP4 files from still pictures with a local camera move (zoom, pan, rotate) and an optional crossfade between pictures.

No AI and no network: the frames are drawn with Pillow and encoded by an ``ffmpeg`` executable that must already be installed on the machine
(H.264 / yuv420p / faststart, no audio). If ffmpeg is missing the call FAILS (``FFMPEG_MISSING``): there is no silent fallback to another format.
The result is checked two ways: ``probe_mp4`` reads the MP4 structure in pure Python (codec, size, frame count, duration, faststart) and
``qc_mp4`` decodes the file again with ffmpeg and looks at every frame (count, blank frames, brightness jumps, a picture that does not move).

This module is NOT yet connected to the video job route (app/video_jobs.py still delivers the animated WebP of the mock): see docs/VIDEO_MP4.md.
"""
from __future__ import annotations

import math
import os
import shutil
import struct
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Iterable, Iterator

from PIL import Image, ImageChops, ImageStat

SIZES = {"9:16": (720, 1280), "4:5": (864, 1080), "16:9": (1280, 720)}     # even sides (yuv420p needs them)
DURATIONS = (5, 10, 15)
FPS = 24
MOTIONS = ("zoom", "pan", "rotate")
TRANSITIONS = ("cut", "crossfade")
MAX_INPUTS = 8
FADE_SECONDS = 0.5
HEADROOM = 1.3              # every picture is prepared 1.3x larger than the frame: the room the camera moves in
ROTATE_DEGREES = 4.0        # rotate: from -4 to +4 degrees
ENCODE_TIMEOUT = 300
BLANK_STDDEV, FLICKER_JUMP, STATIC_DIFF, STATIC_RATIO = 1.5, 25.0, 0.02, 0.6
QC_SCALE = 4                # the QC decodes at a quarter of the size


class VideoEncodeError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def find_ffmpeg() -> str | None:
    """Path of the ffmpeg executable: ``FFMPEG_BINARY`` if set, else the one on PATH. None if there is none."""
    configured = os.environ.get("FFMPEG_BINARY", "").strip()
    if configured:
        return configured if Path(configured).is_file() else None
    return shutil.which("ffmpeg")


def _require_ffmpeg() -> str:
    path = find_ffmpeg()
    if not path:
        raise VideoEncodeError("FFMPEG_MISSING", "ffmpeg is not installed on this machine; MP4 output is not available")
    return path


# ---------------------------------------------------------------------------------------------------------------- frames
def _base(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    w, h = size
    scale = max(w / image.width, h / image.height) * HEADROOM
    return image.convert("RGB").resize((math.ceil(image.width * scale), math.ceil(image.height * scale)), Image.LANCZOS)


def _window(base: Image.Image, size: tuple[int, int], win_w: float, win_h: float, left: float | None = None, top: float | None = None) -> Image.Image:
    left = (base.width - win_w) / 2 if left is None else left
    top = (base.height - win_h) / 2 if top is None else top
    left, top = max(0.0, min(left, base.width - win_w)), max(0.0, min(top, base.height - win_h))
    return base.resize(size, Image.BILINEAR, box=(left, top, left + win_w, top + win_h))


def _frame(base: Image.Image, size: tuple[int, int], motion: str, t: float) -> Image.Image:
    """One frame of one picture; ``t`` runs 0..1 over the time this picture is shown."""
    w, h = size
    if motion == "zoom":                      # from the wide view to 15% closer
        closer = 1.0 + 0.15 * t
        return _window(base, size, w * HEADROOM / closer, h * HEADROOM / closer)
    if motion == "pan":                       # a frame-sized window slides along the side that has more room
        spare_x, spare_y = base.width - w, base.height - h
        if spare_x >= spare_y:
            return _window(base, size, w, h, left=spare_x * t)
        return _window(base, size, w, h, top=spare_y * t)
    # rotate: one affine pass straight to the frame (a window 1.1x the frame, turned about the picture's centre; it stays inside the picture)
    angle = math.radians(-ROTATE_DEGREES + 2 * ROTATE_DEGREES * t)
    a, b = 1.1 * math.cos(angle), -1.1 * math.sin(angle)
    return base.transform(size, Image.AFFINE, (a, b, base.width / 2 - a * w / 2 - b * h / 2, -b, a, base.height / 2 + b * w / 2 - a * h / 2),
                          resample=Image.BILINEAR)


def check_request(image_count: int, aspect: str, seconds: int, motion: str, transition: str) -> None:
    if aspect not in SIZES:
        raise VideoEncodeError("VIDEO_ASPECT_INVALID", "aspect must be 9:16, 4:5 or 16:9")
    if isinstance(seconds, bool) or seconds not in DURATIONS:
        raise VideoEncodeError("VIDEO_DURATION_INVALID", "duration must be 5, 10 or 15 seconds")
    if motion not in MOTIONS:
        raise VideoEncodeError("VIDEO_MOTION_INVALID", "motion must be zoom, pan or rotate")
    if transition not in TRANSITIONS:
        raise VideoEncodeError("VIDEO_TRANSITION_INVALID", "transition must be cut or crossfade")
    if not (1 <= image_count <= MAX_INPUTS):
        raise VideoEncodeError("VIDEO_INPUT_COUNT", f"give 1..{MAX_INPUTS} pictures")


def render_frames(images: list[Image.Image], aspect: str, seconds: int, motion: str = "zoom", transition: str = "cut") -> Iterator[Image.Image]:
    """The frames one after another (a generator: a 15 second video is 360 frames, they are not all kept in memory). Inputs are not changed."""
    check_request(len(images), aspect, seconds, motion, transition)
    size, total, n = SIZES[aspect], seconds * FPS, len(images)
    bases = [_base(image, size) for image in images]
    per, fade = total / n, FADE_SECONDS * FPS

    def generate() -> Iterator[Image.Image]:
        for index in range(total):
            seg = min(int(index / per), n - 1)
            t = min(1.0, (index - seg * per) / max(1.0, per - 1))
            frame = _frame(bases[seg], size, motion, t)
            remaining = (seg + 1) * per - index
            if transition == "crossfade" and seg + 1 < n and remaining <= fade:
                frame = Image.blend(frame, _frame(bases[seg + 1], size, motion, 0.0), 1.0 - remaining / fade)
            yield frame
    return generate()


# ---------------------------------------------------------------------------------------------------------------- encode
def encode_mp4(frames: Iterable[Image.Image], size: tuple[int, int], fps: int = FPS) -> bytes:
    """Encode RGB frames of exactly ``size`` as H.264 MP4 (yuv420p, faststart, no audio). Raises VideoEncodeError if ffmpeg is missing or fails."""
    ffmpeg = _require_ffmpeg()
    if size[0] % 2 or size[1] % 2 or min(size) < 16:
        raise VideoEncodeError("VIDEO_SIZE_INVALID", "width and height must be even and at least 16")
    with tempfile.TemporaryDirectory(prefix="acs_mp4_") as folder:
        out_path, log_path = Path(folder) / "out.mp4", Path(folder) / "ffmpeg.log"
        command = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{size[0]}x{size[1]}",
                   "-r", str(fps), "-i", "-", "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
                   "-movflags", "+faststart", str(out_path)]
        with open(log_path, "wb") as log:
            process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=log)
            written = 0
            try:
                for frame in frames:
                    if frame.size != size:
                        raise VideoEncodeError("VIDEO_FRAME_SIZE", f"frame {written} is {frame.size[0]}x{frame.size[1]}, expected {size[0]}x{size[1]}")
                    process.stdin.write(frame.convert("RGB").tobytes())
                    written += 1
                process.stdin.close()
                code = process.wait(timeout=ENCODE_TIMEOUT)
            except (BrokenPipeError, OSError):
                process.kill()
                process.wait()
                code = -1
            except BaseException:
                process.kill()
                process.wait()
                raise
        if code != 0 or written == 0 or not out_path.is_file() or out_path.stat().st_size == 0:
            detail = log_path.read_text(errors="replace")[-300:].strip()
            raise VideoEncodeError("FFMPEG_FAILED", f"ffmpeg could not encode the video ({written} frames sent): {detail}")
        return out_path.read_bytes()


def make_mp4(images: list[Image.Image], aspect: str, seconds: int, motion: str = "zoom", transition: str = "cut") -> tuple[bytes, dict[str, Any]]:
    """Pictures -> MP4 bytes and a record of what was made. Local only (no AI model, no provider)."""
    _require_ffmpeg()
    started = time.perf_counter()
    content = encode_mp4(render_frames(images, aspect, seconds, motion, transition), SIZES[aspect], FPS)
    return content, {"aspect": aspect, "size": list(SIZES[aspect]), "seconds": seconds, "fps": FPS, "frames": seconds * FPS, "motion": motion,
                     "transition": transition, "inputs": len(images), "mode": "local", "ai": False, "encoder": "ffmpeg libx264",
                     "bytes": len(content), "encode_ms": round((time.perf_counter() - started) * 1000)}


# ---------------------------------------------------------------------------------------------------------------- read the MP4 structure
def _boxes(data: bytes, start: int, end: int) -> Iterator[tuple[str, int, int]]:
    position = start
    while position + 8 <= end:
        size, kind = struct.unpack(">I4s", data[position:position + 8])
        header = 8
        if size == 1:
            if position + 16 > end:
                raise VideoEncodeError("MP4_INVALID", "truncated MP4 box header")
            size, header = struct.unpack(">Q", data[position + 8:position + 16])[0], 16
        elif size == 0:
            size = end - position
        if size < header or position + size > end:
            raise VideoEncodeError("MP4_INVALID", "an MP4 box runs past the end of the file")
        yield kind.decode("latin-1"), position + header, position + size
        position += size


def _find(data: bytes, start: int, end: int, path: tuple[str, ...]) -> tuple[int, int] | None:
    for kind, body, stop in _boxes(data, start, end):
        if kind == path[0]:
            return (body, stop) if len(path) == 1 else _find(data, body, stop, path[1:])
    return None


def _handler(data: bytes, start: int, end: int) -> bytes:
    """The handler type of a track: b'vide' for video, b'soun' for audio."""
    box = _find(data, start, end, ("mdia", "hdlr"))
    return b"" if box is None else data[box[0] + 8:box[0] + 12]


def probe_mp4(content: bytes) -> dict[str, Any]:
    """What the file says about itself (pure Python, no ffmpeg): brand, video codec, picture size, frame count, duration, faststart."""
    top = list(_boxes(content, 0, len(content)))
    names = [kind for kind, _, _ in top]
    if not names or names[0] != "ftyp" or "moov" not in names or "mdat" not in names:
        raise VideoEncodeError("MP4_INVALID", "not a complete MP4 file (ftyp, moov and mdat are required)")
    brand = content[top[0][1]:top[0][1] + 4].decode("latin-1")
    moov_start, moov_end = next((body, stop) for kind, body, stop in top if kind == "moov")
    mvhd = _find(content, moov_start, moov_end, ("mvhd",))
    if mvhd is None:
        raise VideoEncodeError("MP4_INVALID", "the MP4 has no movie header")
    if content[mvhd[0]] == 1:
        timescale, duration = struct.unpack(">IQ", content[mvhd[0] + 20:mvhd[0] + 32])
    else:
        timescale, duration = struct.unpack(">II", content[mvhd[0] + 12:mvhd[0] + 20])
    video = None
    for kind, body, stop in _boxes(content, moov_start, moov_end):
        if kind != "trak":
            continue
        if _handler(content, body, stop) != b"vide":
            continue
        tkhd = _find(content, body, stop, ("tkhd",))
        stsd = _find(content, body, stop, ("mdia", "minf", "stbl", "stsd"))
        stsz = _find(content, body, stop, ("mdia", "minf", "stbl", "stsz"))
        if tkhd is None or stsd is None or stsz is None:
            raise VideoEncodeError("MP4_INVALID", "the video track is incomplete")
        width, height = struct.unpack(">II", content[tkhd[1] - 8:tkhd[1]])
        video = {"codec": content[stsd[0] + 12:stsd[0] + 16].decode("latin-1"), "width": width >> 16, "height": height >> 16,
                 "frames": struct.unpack(">I", content[stsz[0] + 8:stsz[0] + 12])[0]}
        break
    if video is None:
        raise VideoEncodeError("MP4_INVALID", "the MP4 has no video track")
    audio_tracks = sum(1 for kind, body, stop in _boxes(content, moov_start, moov_end) if kind == "trak" and _handler(content, body, stop) == b"soun")
    return {"brand": brand, **video, "duration_seconds": round(duration / timescale, 3) if timescale else 0.0, "audio_tracks": audio_tracks,
            "faststart": names.index("moov") < names.index("mdat"), "bytes": len(content)}


# ---------------------------------------------------------------------------------------------------------------- QC by decoding
def qc_mp4(content: bytes, size: tuple[int, int], seconds: int, fps: int = FPS) -> dict[str, Any]:
    """Decode the file again and judge it. FAIL: not an MP4, wrong codec/size/frame count/duration, cannot be decoded, blank frames.
    WARN only: no faststart, brightness jumps (a cut between two pictures also jumps), a picture that does not move."""
    ffmpeg = _require_ffmpeg()
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: str, level: str = "fail") -> None:
        checks.append({"check": name, "level": "ok" if ok else level, "detail": detail})

    expected = seconds * fps
    try:
        probe = probe_mp4(content)
    except VideoEncodeError as error:
        add("container", False, str(error))
        return {"passed": False, "probe": None, "decoded_frames": 0, "blank_frames": 0, "max_brightness_jump": 0.0, "static_ratio": 0.0, "checks": checks}
    add("container", True, f"brand {probe['brand']}")
    add("codec", probe["codec"] == "avc1", probe["codec"])
    add("size", (probe["width"], probe["height"]) == tuple(size), f"{probe['width']}x{probe['height']} (expected {size[0]}x{size[1]})")
    add("frame_count", probe["frames"] == expected, f"{probe['frames']}/{expected}")
    add("duration", abs(probe["duration_seconds"] - seconds) <= 0.1, f"{probe['duration_seconds']} s (expected {seconds})")
    add("faststart", probe["faststart"], "moov before mdat" if probe["faststart"] else "moov after mdat", level="warn")

    small = (max(2, probe["width"] // QC_SCALE), max(2, probe["height"] // QC_SCALE))
    frame_bytes = small[0] * small[1] * 3
    decoded, blank, jumps, still = 0, 0, [], 0
    with tempfile.TemporaryDirectory(prefix="acs_mp4qc_") as folder:
        in_path, log_path = Path(folder) / "in.mp4", Path(folder) / "ffmpeg.log"
        in_path.write_bytes(content)
        command = [ffmpeg, "-hide_banner", "-loglevel", "error", "-i", str(in_path), "-vf", f"scale={small[0]}:{small[1]}", "-f", "rawvideo",
                   "-pix_fmt", "rgb24", "-"]
        with open(log_path, "wb") as log:
            process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=log)
            previous, previous_mean = None, None
            try:
                while True:
                    chunk = process.stdout.read(frame_bytes)
                    if len(chunk) < frame_bytes:
                        break
                    gray = Image.frombytes("RGB", small, chunk).convert("L")
                    stat = ImageStat.Stat(gray)
                    blank += 1 if stat.stddev[0] < BLANK_STDDEV else 0
                    if previous is not None:
                        jumps.append(abs(stat.mean[0] - previous_mean))
                        still += 1 if ImageStat.Stat(ImageChops.difference(gray, previous)).mean[0] < STATIC_DIFF else 0
                    previous, previous_mean = gray, stat.mean[0]
                    decoded += 1
                code = process.wait(timeout=ENCODE_TIMEOUT)
            except BaseException:
                process.kill()
                process.wait()
                raise
        errors = log_path.read_text(errors="replace").strip()
    max_jump = round(max(jumps), 2) if jumps else 0.0
    static_ratio = round(still / max(1, decoded - 1), 3)
    add("decodable", code == 0 and not errors, "decoded without errors" if code == 0 and not errors else f"ffmpeg: {errors[-200:] or 'exit ' + str(code)}")
    add("decoded_frame_count", decoded == expected, f"{decoded}/{expected}")
    add("blank_frames", blank == 0, f"{blank} blank frame(s)")
    add("brightness_flicker", max_jump <= FLICKER_JUMP, f"largest jump {max_jump}", level="warn")
    add("static_picture", static_ratio <= STATIC_RATIO, f"{static_ratio} of frames repeat the previous one", level="warn")
    return {"passed": not any(c["level"] == "fail" for c in checks), "probe": probe, "decoded_frames": decoded, "blank_frames": blank,
            "max_brightness_jump": max_jump, "static_ratio": static_ratio, "checks": checks}
