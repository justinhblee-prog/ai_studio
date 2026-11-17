"""Lane 4 / E-08c: burned-in subtitles for the MP4 videos (app/video_mp4.py).

The text is drawn with Pillow into the picture frames BEFORE they reach ffmpeg: the text never goes to a shell, a filter string or a file name. The font is an
open font (SIL Open Font License; Noto Sans CJK, which has Hangul): it is looked up on the machine -- ``SUBTITLE_FONT_PATH`` (optionally ``SUBTITLE_FONT_INDEX``
for a .ttc collection) or the usual place of the Debian/Ubuntu package ``fonts-noto-cjk`` -- and is NOT stored in this repository (docs/THIRD_PARTY_FONTS.md).
No font -> ``SUBTITLE_FONT_MISSING`` (no fallback to a font that cannot draw Korean). A character the font cannot draw -> ``SUBTITLE_GLYPH_MISSING`` (never a box).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Iterable, Iterator

from PIL import Image, ImageDraw, ImageFont

from app.video_mp4 import FPS, VideoEncodeError

MAX_CUES, MAX_CUE_CHARS, MAX_LINES = 20, 120, 2
FONT_CANDIDATES = ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
                   "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc", "/usr/share/fonts/opentype/noto/NotoSansKR-Regular.otf",
                   "C:/Windows/Fonts/malgun.ttf")          # the last one only lets a Windows developer see the layout; it is not an open font and is not used by CI
KOREAN_INDEX = 1                                           # in NotoSansCJK-Regular.ttc: 0 JP, 1 KR, 2 SC, 3 TC, 4 HK
_PROBE = "\ue000"                                          # a private-use code point: no font maps it, so its picture is the font's "missing glyph" box


def find_subtitle_font() -> tuple[str, int] | None:
    """(path, collection index) of the font to use, or None."""
    configured = os.environ.get("SUBTITLE_FONT_PATH", "").strip()
    if configured:
        index = int(os.environ.get("SUBTITLE_FONT_INDEX", "0") or 0)
        return (configured, index) if Path(configured).is_file() else None
    for path in FONT_CANDIDATES:
        if Path(path).is_file():
            return path, (KOREAN_INDEX if path.endswith(".ttc") else 0)
    return None


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    found = find_subtitle_font()
    if found is None:
        raise VideoEncodeError("SUBTITLE_FONT_MISSING", "no subtitle font is installed on this machine")
    try:
        return ImageFont.truetype(found[0], size, index=found[1])
    except OSError as exc:
        raise VideoEncodeError("SUBTITLE_FONT_MISSING", "the subtitle font could not be opened") from exc


def parse_cues(raw: Any, seconds: float) -> list[dict[str, Any]]:
    """Checked, sorted cues ``{"text", "start", "end"}`` (seconds). Unknown keys, bad types, empty or control-character text, times outside the video and
    overlapping cues are refused (nothing is drawn if anything is wrong)."""
    if not isinstance(raw, list) or not (1 <= len(raw) <= MAX_CUES):
        raise VideoEncodeError("SUBTITLE_INVALID", f"give 1..{MAX_CUES} subtitle cues")
    cues = []
    for cue in raw:
        if not isinstance(cue, dict) or set(cue) != {"text", "start", "end"}:
            raise VideoEncodeError("SUBTITLE_INVALID", "each cue is {text, start, end}")
        text, start, end = cue["text"], cue["start"], cue["end"]
        if not isinstance(text, str) or not text.strip() or len(text) > MAX_CUE_CHARS or any((ord(c) < 32 and c != "\n") or ord(c) == 127 for c in text):
            raise VideoEncodeError("SUBTITLE_INVALID", f"cue text must be 1..{MAX_CUE_CHARS} characters without control characters")
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in (start, end)) or not (0 <= start < end <= seconds):
            raise VideoEncodeError("SUBTITLE_INVALID", f"cue times must satisfy 0 <= start < end <= {seconds}")
        cues.append({"text": text.strip(), "start": float(start), "end": float(end)})
    cues.sort(key=lambda c: c["start"])
    if any(b["start"] < a["end"] for a, b in zip(cues, cues[1:])):
        raise VideoEncodeError("SUBTITLE_OVERLAP", "subtitle cues may not overlap")
    return cues


def unsupported_characters(text: str, font: ImageFont.FreeTypeFont) -> list[str]:
    """Characters the font cannot draw (its picture equals the picture of an unmapped code point)."""
    missing_box = font.getmask(_PROBE).tobytes()
    return sorted({c for c in text if c not in " \n" and font.getmask(c).tobytes() == missing_box})


def _wrap(text: str, font: ImageFont.FreeTypeFont, max_width: float) -> list[str]:
    lines: list[str] = []
    for paragraph in text.split("\n"):
        current = ""
        for ch in paragraph:                                   # character by character: Korean has no spaces everywhere
            if current and font.getlength(current + ch) > max_width:
                lines.append(current.rstrip())
                current = ch.lstrip()
            else:
                current += ch
        lines.append(current.rstrip())
    return [line for line in lines if line] or [""]


def build_overlays(cues: list[dict[str, Any]], size: tuple[int, int]) -> list[dict[str, Any]]:
    """One transparent picture per cue (dark box + white text near the bottom), made once and laid over every frame of the cue."""
    width, height = size
    font = _load_font(max(18, round(width / 20)))
    overlays = []
    for cue in cues:
        bad = unsupported_characters(cue["text"], font)
        if bad:
            raise VideoEncodeError("SUBTITLE_GLYPH_MISSING", f"the subtitle font cannot draw: {' '.join(bad)}")
        lines = _wrap(cue["text"], font, width * 0.86)
        if len(lines) > MAX_LINES:
            raise VideoEncodeError("SUBTITLE_TOO_LONG", f"a cue may take at most {MAX_LINES} lines at this video size")
        line_h = round(font.size * 1.35)
        box_w = round(max(font.getlength(line) for line in lines)) + font.size
        box_h = line_h * len(lines) + round(font.size * 0.5)
        left, top = (width - box_w) // 2, height - box_h - round(height * 0.08)
        layer = Image.new("RGBA", size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        draw.rounded_rectangle((left, top, left + box_w, top + box_h), radius=round(font.size * 0.3), fill=(0, 0, 0, 150))
        for n, line in enumerate(lines):
            draw.text((width // 2, top + round(font.size * 0.25) + n * line_h), line, font=font, fill=(255, 255, 255, 255), anchor="ma")
        overlays.append({"start": cue["start"], "end": cue["end"], "layer": layer, "lines": len(lines), "box": (left, top, left + box_w, top + box_h)})
    return overlays


def overlay_frames(frames: Iterable[Image.Image], overlays: list[dict[str, Any]], fps: int = FPS) -> Iterator[Image.Image]:
    """The same frames, with each cue's picture laid on the frames whose time is in [start, end). Frame i is at time i / fps."""
    for index, frame in enumerate(frames):
        moment = index / fps
        active = next((o for o in overlays if o["start"] <= moment < o["end"]), None)
        if active is None:
            yield frame
        else:
            out = frame.convert("RGBA")
            out.alpha_composite(active["layer"])
            yield out.convert("RGB")
