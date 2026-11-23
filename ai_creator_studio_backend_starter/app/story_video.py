"""R-ENGINE-17: a STORY -> a video of a chosen length, local only (no AI, no network): the story is cut into sentences, each sentence becomes a scene over one of the given pictures, the
total length (1..60 s) is shared between the scenes and every sentence becomes a caption. The MP4 is made by ``video_mp4`` (ffmpeg, H.264) - the point of this module is to turn the screen's
WebM-only story video into an MP4 on the server.

Planning (``plan``) is pure and deterministic. Rules (PROPOSALS, the design window may change them):
  * sentences S (split at . ! ? 。 ！ ？ and line breaks), pictures N, scenes = max(S, N);
  * S >= N: scene j shows picture floor(j*N/S) and the caption is sentence j (consecutive scenes may reuse a picture);
  * S <  N: scene j shows picture j; sentence k's caption is shown over the whole group of scenes floor(j*S/N) == k;
  * every scene lasts total_seconds / scenes (a scene may not be shorter than MIN_SCENE_SECONDS), captions are cut to MAX_CAPTION characters with an ellipsis;
  * ``captions``: "auto" (from the story), a list of texts (one per scene, "" = none) or None (no captions).
``engine``: "local" is the only one that runs; "ai" is a closed door (``STORY_ENGINE_CLOSED``, answered 409 by a route): an AI video provider needs a key and money, the customer's decision.
"""
from __future__ import annotations

import re
import time
from typing import Any, Iterator

from PIL import Image

from app import video_mp4, video_subtitles

MIN_SECONDS, MAX_SECONDS = 1, 60
MIN_SCENE_SECONDS = 0.5
MAX_SCENES = 20                      # the caption limit of video_subtitles (MAX_CUES)
MAX_IMAGES = video_mp4.MAX_INPUTS
MAX_CAPTION = 40
ENGINES = ("local", "ai")
SPLIT = re.compile(r"(?<=[.!?。！？])\s+|\n+")


class StoryError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def split_story(story: str) -> list[str]:
    if not isinstance(story, str):
        raise StoryError("STORY_INVALID", "the story must be text")
    parts = [p.strip() for p in SPLIT.split(story.strip()) if p and p.strip()]
    return parts


def shorten(text: str, limit: int = MAX_CAPTION) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "…"


def plan(image_count: int, story: str, total_seconds: float, captions: Any = "auto", engine: str = "local") -> dict[str, Any]:
    if engine not in ENGINES:
        raise StoryError("STORY_ENGINE_INVALID", "engine must be 'local' or 'ai'")
    if engine == "ai":
        raise StoryError("STORY_ENGINE_CLOSED", "AI video generation is not open: it needs a provider key and a cost decision")
    if isinstance(total_seconds, bool) or not isinstance(total_seconds, (int, float)) or not MIN_SECONDS <= total_seconds <= MAX_SECONDS:
        raise StoryError("STORY_SECONDS_INVALID", f"total_seconds must be {MIN_SECONDS}..{MAX_SECONDS}")
    if isinstance(image_count, bool) or not 1 <= image_count <= MAX_IMAGES:
        raise StoryError("STORY_IMAGES_INVALID", f"give 1..{MAX_IMAGES} pictures")
    sentences = split_story(story)
    if not sentences and captions == "auto":
        raise StoryError("STORY_EMPTY", "the story has no sentence")
    s, n = len(sentences), image_count
    scenes = max(s, n)
    if scenes > MAX_SCENES:
        raise StoryError("STORY_TOO_MANY_SCENES", f"at most {MAX_SCENES} scenes (sentences or pictures)")
    each = total_seconds / scenes
    if each < MIN_SCENE_SECONDS:
        raise StoryError("STORY_TOO_MANY_SCENES", f"{scenes} scenes in {total_seconds:g} s would be shorter than {MIN_SCENE_SECONDS} s each")
    out = []
    for j in range(scenes):
        picture = j if s < n else (j * n) // s
        cut: dict[str, Any] = {"scene": j, "image_index": picture, "start": round(j * each, 3), "end": round((j + 1) * each, 3), "caption": None}
        if captions == "auto":
            if s >= n:
                cut["caption"] = shorten(sentences[j])
            else:
                k = (j * s) // n
                first = j == 0 or ((j - 1) * s) // n != k
                cut["caption"] = shorten(sentences[k]) if first else None
                cut["_group"] = k
        elif isinstance(captions, list):
            if len(captions) != scenes or any(not isinstance(c, str) for c in captions):
                raise StoryError("STORY_CAPTIONS_INVALID", f"captions must be a list of {scenes} texts (one per scene, '' for none)")
            cut["caption"] = shorten(captions[j]) or None
        elif captions is not None:
            raise StoryError("STORY_CAPTIONS_INVALID", "captions is 'auto', a list of texts or null")
        out.append(cut)
    cues = _cues(out)
    for c in out:
        c.pop("_group", None)
    return {"engine": engine, "total_seconds": total_seconds, "scenes": scenes, "sentences": s, "images": n, "seconds_per_scene": round(each, 3), "cuts": out, "cues": cues}


def _cues(cuts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Caption cues: a captioned scene lasts to its own end - or, in the S < N case, to the end of its sentence's group of scenes."""
    cues = []
    for i, c in enumerate(cuts):
        if not c["caption"]:
            continue
        end = c["end"]
        group = c.get("_group")
        if group is not None:
            for d in cuts[i + 1:]:
                if d.get("_group") != group:
                    break
                end = d["end"]
        cues.append({"text": c["caption"], "start": c["start"], "end": end})
    return cues


def _frames(images: list[Image.Image], plan_: dict[str, Any], aspect: str, motion: str, transition: str) -> Iterator[Image.Image]:
    size = video_mp4.SIZES[aspect]
    fps, total = video_mp4.FPS, round(plan_["total_seconds"] * video_mp4.FPS)
    bases = [video_mp4._base(im, size) for im in images]
    cuts = plan_["cuts"]
    bounds = [round(c["end"] * fps) for c in cuts]
    bounds[-1] = total
    fade = video_mp4.FADE_SECONDS * fps
    start = 0
    for j, c in enumerate(cuts):
        end = bounds[j]
        length = max(1, end - start)
        for k in range(length):
            t = min(1.0, k / max(1.0, length - 1))
            frame = video_mp4._frame(bases[c["image_index"]], size, motion, t)
            remaining = length - k
            if transition == "crossfade" and j + 1 < len(cuts) and remaining <= min(fade, length / 2):
                frame = Image.blend(frame, video_mp4._frame(bases[cuts[j + 1]["image_index"]], size, motion, 0.0), 1.0 - remaining / min(fade, length / 2))
            yield frame
        start = end


def make_story_mp4(images: list[Image.Image], story: str, total_seconds: float, aspect: str = "9:16", transitions: str = "crossfade", captions: Any = "auto",
                   motion: str = "zoom", engine: str = "local", comment: str | None = None) -> tuple[bytes, dict[str, Any]]:
    """The MP4 bytes and ``{mp4 facts, cuts:[{scene, image_index, start, end, caption}], ...}``. Needs ffmpeg (FFMPEG_MISSING otherwise) and, for captions, the open Korean font."""
    if aspect not in video_mp4.SIZES:
        raise StoryError("VIDEO_ASPECT_INVALID", "aspect must be 9:16, 4:5 or 16:9")
    if transitions not in video_mp4.TRANSITIONS or motion not in video_mp4.MOTIONS:
        raise StoryError("VIDEO_TRANSITION_INVALID", "transitions must be cut or crossfade; motion zoom, pan or rotate")
    p = plan(len(images), story, total_seconds, captions, engine)
    video_mp4._require_ffmpeg()
    started = time.perf_counter()
    frames: Any = _frames(images, p, aspect, motion, transitions)
    if p["cues"]:
        cues = video_subtitles.parse_cues(p["cues"], p["total_seconds"])
        frames = video_subtitles.overlay_frames(frames, video_subtitles.build_overlays(cues, video_mp4.SIZES[aspect]), video_mp4.FPS)
    content = video_mp4.encode_mp4(frames, video_mp4.SIZES[aspect], video_mp4.FPS, comment)
    meta = {**p, "aspect": aspect, "size": list(video_mp4.SIZES[aspect]), "fps": video_mp4.FPS, "frames": round(p["total_seconds"] * video_mp4.FPS), "motion": motion, "transition": transitions,
            "mode": "local", "ai": False, "bytes": len(content), "encode_ms": round((time.perf_counter() - started) * 1000)}
    return content, meta


__all__ = ["plan", "split_story", "shorten", "make_story_mp4", "StoryError"]
