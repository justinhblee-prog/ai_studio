"""R-050: image -> short video jobs (MOCK ONLY). Inputs are the workspace's own library images (including the 3D viewer's rotation cuts, which
are ordinary 'render' images); the mock provider makes an ANIMATED WebP with a local camera move (no AI, no network, no new dependency) and every
result goes through a frame QC before it is delivered. A real provider is NOT connected (``PROVIDER_MODE`` other than mock fails closed; real MP4
output also needs a new media type and video tooling, which is the R-041 dependency approval).

The mock runs inside the request (it is instant), but the contract is the job contract a real provider needs: ``status`` queued/running/succeeded/failed,
read through GET. A result that fails the QC is NOT delivered (status ``failed``, error ``QC_FAILED``, the findings in ``qc``).
"""
from __future__ import annotations

import asyncio
import io
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from PIL import Image, ImageChops, ImageStat
from pydantic import BaseModel, ConfigDict, Field

from app.schema_util import add_column
from app import config, takedown, video_mp4, video_subtitles
from app.assets import store
from app.assets.routes import current_user, require_role
from app.assets.validation import ValidatedAsset

router = APIRouter(prefix="/v1/workspaces/{workspace_id}/video-jobs", tags=["video-jobs"])
EVENT = "asset.video_output"
FPS = 8
SIZES = {"9:16": (270, 480), "4:5": (320, 400), "16:9": (480, 270)}   # mock sizes: small on purpose
MIN_SECONDS, MAX_SECONDS, DEFAULT_SECONDS = 3, 15, 6     # R-073: 5, 10 and 15 second videos
MAX_INPUTS = 8
DAILY_LIMIT_DEFAULT = 20
MOTIONS = ("slow_zoom", "pan", "crossfade")
# frame QC thresholds (proposals; the design window decides): a frame whose pixels barely vary is blank; steady brightness jumps are flicker
BLANK_STDDEV, FLICKER_JUMP, STATIC_DUPLICATE_RATIO = 1.5, 25.0, 0.6


def _init(db) -> None:
    db.execute("""CREATE TABLE IF NOT EXISTS video_jobs (
        job_id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, owner_id TEXT NOT NULL, status TEXT NOT NULL, provider TEXT NOT NULL,
        aspect TEXT NOT NULL, duration_seconds INTEGER NOT NULL, motion TEXT NOT NULL, instruction TEXT, input_item_ids_json TEXT NOT NULL,
        output_asset_id TEXT, qc_json TEXT, error_code TEXT, created_at TEXT NOT NULL, finished_at TEXT)""")
    # B-11: listing one workspace's rows must not scan the whole table
    db.execute("CREATE INDEX IF NOT EXISTS idx_video_jobs_ws ON video_jobs(workspace_id, created_at)")
    if "output_format" not in {r[1] for r in db.execute("PRAGMA table_info(video_jobs)").fetchall()}:     # a database made before MP4 output existed
        add_column(db, "ALTER TABLE video_jobs ADD COLUMN output_format TEXT NOT NULL DEFAULT 'webp'")
    if "subtitles_json" not in {r[1] for r in db.execute("PRAGMA table_info(video_jobs)").fetchall()}:
        add_column(db, "ALTER TABLE video_jobs ADD COLUMN subtitles_json TEXT")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------------------------------------------- frames
def _cover(image: Image.Image, size: tuple[int, int], zoom: float, along: float) -> Image.Image:
    """Scale to cover the canvas, zoom in, then take the window; ``along`` 0..1 slides the window across the spare width/height."""
    w, h = size
    scale = max(w / image.width, h / image.height) * zoom
    big = image.resize((max(w, round(image.width * scale)), max(h, round(image.height * scale))), Image.LANCZOS)
    spare_x, spare_y = big.width - w, big.height - h
    left = round(spare_x * (along if spare_x >= spare_y else 0.5))
    top = round(spare_y * (along if spare_y > spare_x else 0.5))
    return big.crop((left, top, left + w, top + h))


def make_frames(images: list[Image.Image], aspect: str, seconds: int, motion: str) -> list[Image.Image]:
    size, total, n = SIZES[aspect], seconds * FPS, len(images)
    per = max(1, total // n)
    frames: list[Image.Image] = []
    for index in range(total):
        seg = min(index // per, n - 1)
        t = (index - seg * per) / max(1, per - 1)                      # 0..1 inside the segment
        if motion == "slow_zoom":
            frame = _cover(images[seg], size, 1.0 + 0.12 * t, 0.5)
        elif motion == "pan":
            frame = _cover(images[seg], size, 1.25, t)
        else:                                                           # crossfade: the last quarter of a segment blends into the next picture
            frame = _cover(images[seg], size, 1.0 + 0.05 * t, 0.5)
            if seg + 1 < n and t > 0.75:
                nxt = _cover(images[seg + 1], size, 1.0, 0.5)
                frame = Image.blend(frame, nxt, (t - 0.75) / 0.25)
        frames.append(frame.convert("RGB"))
    return frames


def qc_frames(frames: list[Image.Image], aspect: str, expected_count: int) -> dict[str, Any]:
    """Findings that decide delivery: wrong size/count and blank frames FAIL the job; a static picture or brightness flicker only WARN."""
    expected = SIZES[aspect]
    checks: list[dict[str, Any]] = []
    size_ok = all(f.size == expected for f in frames)
    count_ok = len(frames) == expected_count
    blank = [i for i, f in enumerate(frames) if max(ImageStat.Stat(f.convert("L")).stddev) < BLANK_STDDEV]
    lum = [ImageStat.Stat(f.convert("L")).mean[0] for f in frames]
    jumps = [abs(b - a) for a, b in zip(lum, lum[1:])]
    max_jump = round(max(jumps), 2) if jumps else 0.0
    duplicates = sum(1 for a, b in zip(frames, frames[1:]) if ImageChops.difference(a, b).getbbox() is None)
    dup_ratio = round(duplicates / max(1, len(frames) - 1), 3)
    checks.append({"check": "size", "level": "ok" if size_ok else "fail", "detail": f"{expected[0]}x{expected[1]}"})
    checks.append({"check": "frame_count", "level": "ok" if count_ok else "fail", "detail": f"{len(frames)}/{expected_count}"})
    checks.append({"check": "blank_frames", "level": "fail" if blank else "ok", "detail": f"{len(blank)} blank frame(s)"})
    checks.append({"check": "brightness_flicker", "level": "warn" if max_jump > FLICKER_JUMP else "ok", "detail": f"largest jump {max_jump}"})
    checks.append({"check": "static_picture", "level": "warn" if dup_ratio > STATIC_DUPLICATE_RATIO else "ok", "detail": f"{dup_ratio} of frames repeat the previous one"})
    return {"passed": not any(c["level"] == "fail" for c in checks), "frames": len(frames), "max_brightness_jump": max_jump,
            "duplicate_ratio": dup_ratio, "blank_frames": len(blank), "checks": checks}


# ------------------------------------------------------------------------------------------------------------------ API
class CueIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=120)
    start: float = Field(ge=0, le=MAX_SECONDS)       # seconds from the start of the video
    end: float = Field(gt=0, le=MAX_SECONDS)


class VideoIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    input_item_ids: list[str] = Field(min_length=1, max_length=MAX_INPUTS)
    aspect: Literal["9:16", "4:5", "16:9"] = "9:16"
    duration_seconds: int = Field(default=DEFAULT_SECONDS, ge=MIN_SECONDS, le=MAX_SECONDS)
    motion: Literal["slow_zoom", "pan", "crossfade"] = "slow_zoom"
    prompt: str | None = Field(default=None, max_length=500)
    subtitles: list[CueIn] | None = Field(default=None, max_length=20)     # mp4 only: burned into the picture (app/video_subtitles.py)
    output_format: Literal["webp", "mp4"] = "webp"      # mp4 = a real H.264 file (needs ffmpeg on the server; 5, 10 or 15 seconds; 720x1280, 864x1080 or 1280x720)


class QcOut(BaseModel):
    model_config = ConfigDict(extra="allow")
    passed: bool
    frames: int
    checks: list[dict[str, Any]]


class VideoOut(BaseModel):
    job_id: str
    workspace_id: str
    owner_id: str
    status: Literal["queued", "running", "succeeded", "failed"]
    provider: str
    aspect: str
    duration_seconds: int
    motion: str
    output_format: str = "webp"
    subtitles: list[CueIn] | None = None
    prompt: str | None
    input_item_ids: list[str]
    output_asset_id: str | None
    qc: QcOut | None
    error_code: str | None
    created_at: str
    finished_at: str | None


class VideoListOut(BaseModel):
    items: list[VideoOut]


def _public(row) -> dict[str, Any]:
    return {"job_id": row["job_id"], "workspace_id": row["workspace_id"], "owner_id": row["owner_id"], "status": row["status"], "provider": row["provider"],
            "aspect": row["aspect"], "duration_seconds": row["duration_seconds"], "motion": row["motion"], "output_format": row["output_format"], "subtitles": json.loads(row["subtitles_json"]) if row["subtitles_json"] else None, "prompt": row["instruction"],
            "input_item_ids": json.loads(row["input_item_ids_json"]), "output_asset_id": row["output_asset_id"],
            "qc": json.loads(row["qc_json"]) if row["qc_json"] else None, "error_code": row["error_code"],
            "created_at": row["created_at"], "finished_at": row["finished_at"]}


def _load_inputs(workspace_id: str, user_id: str, item_ids: list[str]) -> list[Image.Image]:
    from app.tryon_inputs import _item
    images = []
    for item_id in item_ids:
        row = _item(workspace_id, item_id)
        if row is None or not takedown.visible_to(row["asset_id"], user_id):
            raise HTTPException(status_code=404, detail={"code": "VIDEO_INPUT_NOT_FOUND", "message": "library item not found"})
        if row["kind"] == "3d" or not str(row["media_type"]).startswith("image/"):
            raise HTTPException(status_code=422, detail={"code": "VIDEO_INPUT_KIND", "message": "video inputs must be images (a 3D item needs its rotation cuts)"})
        path = store.storage_path(row["asset_id"])
        if path is None:
            raise HTTPException(status_code=409, detail={"code": "VIDEO_INPUT_GONE", "message": "the item's file is missing"})
        with Image.open(path) as opened:
            opened.seek(0)
            images.append(opened.convert("RGB"))
    return images


@router.post("", status_code=201, response_model=VideoOut, operation_id="createVideoJob")
async def create_video_job(workspace_id: str, body: VideoIn, user_id: str = Depends(current_user)):
    require_role(workspace_id, user_id, {"owner", "admin", "editor"})
    from app import rate_limit    # R-067
    rate_limit.check("generate", user_id, workspace_id)
    if config.PROVIDER_MODE != "mock":
        raise HTTPException(status_code=409, detail={"code": "VIDEO_PROVIDER_NOT_CONNECTED", "message": "Video generation by an external AI service is not connected yet."})
    if len(set(body.input_item_ids)) != len(body.input_item_ids):
        raise HTTPException(status_code=422, detail={"code": "VIDEO_INPUT_DUPLICATE", "message": "each picture may be used once"})
    since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    with store._connect() as db:
        _init(db)
        used = db.execute("SELECT COUNT(*) AS n FROM video_jobs WHERE workspace_id=? AND created_at>=?", (workspace_id, since)).fetchone()["n"]
    limit = int(getattr(config, "VIDEO_DAILY_LIMIT", DAILY_LIMIT_DEFAULT))
    if used >= limit:
        from app import rate_limit
        raise rate_limit.too_many("VIDEO_DAILY_LIMIT", "today's video limit is used up", 3600, estimated=True, limit=limit, used=used)
    if body.subtitles is not None and body.output_format != "mp4":
        raise HTTPException(status_code=422, detail={"code": "SUBTITLE_INVALID", "message": "subtitles need output_format mp4"})
    if body.output_format == "mp4":
        if body.subtitles is not None:          # the cue checks and the font run before anything is made or stored
            try:
                video_subtitles.parse_cues([c.model_dump() for c in body.subtitles], body.duration_seconds)
            except video_mp4.VideoEncodeError as exc:
                raise HTTPException(status_code=422, detail={"code": exc.code, "message": str(exc)}) from exc
            if video_subtitles.find_subtitle_font() is None:
                raise HTTPException(status_code=503, detail={"code": "SUBTITLE_FONT_MISSING", "message": "subtitles are not available on this server"})
        if body.duration_seconds not in video_mp4.DURATIONS:
            raise HTTPException(status_code=422, detail={"code": "VIDEO_DURATION_INVALID", "message": "an MP4 video is 5, 10 or 15 seconds long"})
        if video_mp4.find_ffmpeg() is None:     # no silent fallback to another format
            raise HTTPException(status_code=503, detail={"code": "FFMPEG_MISSING", "message": "MP4 output is not available on this server"})
    images = _load_inputs(workspace_id, user_id, body.input_item_ids)
    job_id, now = "vid_" + uuid.uuid4().hex, _now()
    if body.output_format == "mp4":
        return await _create_mp4(workspace_id, user_id, body, job_id, now, images)
    frames = make_frames(images, body.aspect, body.duration_seconds, body.motion)
    qc = qc_frames(frames, body.aspect, body.duration_seconds * FPS)
    output_asset_id, status, error = None, "failed", "QC_FAILED"
    if qc["passed"]:
        buf = io.BytesIO()
        frames[0].save(buf, format="WEBP", save_all=True, append_images=frames[1:], duration=1000 // FPS, loop=0, quality=70)
        content = buf.getvalue()
        saved = store.save_asset(owner_id=user_id, workspace_id=workspace_id, filename=f"video-{job_id[-6:]}.webp", content=content,
                                 validated=ValidatedAsset(media_type="image/webp", size_bytes=len(content), gltf_version=None, embedded_binary=False),
                                 provenance_event=EVENT,
                                 provenance_extra={"job_id": job_id, "mode": "mock", "is_ai_generated": False, "aspect": body.aspect,
                                                   "duration_seconds": body.duration_seconds, "motion": body.motion, "qc_passed": True})
        output_asset_id, status, error = saved["asset_id"], "succeeded", None
    with store._connect() as db:
        _init(db)
        _insert_job(db, job_id, workspace_id, user_id, body, status, output_asset_id, qc, error, now)
        return _public(db.execute("SELECT * FROM video_jobs WHERE job_id=?", (job_id,)).fetchone())


def _insert_job(db, job_id, workspace_id, user_id, body, status, output_asset_id, qc, error, now) -> None:
    cues = json.dumps([c.model_dump() for c in body.subtitles], ensure_ascii=False) if body.subtitles else None
    db.execute("""INSERT INTO video_jobs(job_id, workspace_id, owner_id, status, provider, aspect, duration_seconds, motion, output_format, instruction, input_item_ids_json,
        output_asset_id, qc_json, error_code, created_at, finished_at, subtitles_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
               (job_id, workspace_id, user_id, status, "mock", body.aspect, body.duration_seconds, body.motion, body.output_format, (body.prompt or "").strip() or None,
                json.dumps(body.input_item_ids), output_asset_id, json.dumps(qc), error, now, _now(), cues))


# the three mock motions of this API -> the motion and transition of the MP4 module
MP4_MOTION = {"slow_zoom": ("zoom", "cut"), "pan": ("pan", "cut"), "crossfade": ("zoom", "crossfade")}


async def _create_mp4(workspace_id, user_id, body, job_id, now, images):
    """A real MP4 (H.264) made locally by ffmpeg, checked by decoding it again; saved as a ``video`` asset. The picture work runs in a worker thread so the
    server keeps answering while a 15 second video is encoded. A file that fails the QC is NOT delivered (``QC_FAILED``), like the picture version."""
    motion, transition = MP4_MOTION[body.motion]
    source_assets = []
    for item_id in body.input_item_ids:
        from app.tryon_inputs import _item
        row = _item(workspace_id, item_id)
        source_assets.append(row["asset_id"])
    comment = f"job={job_id}; mode=mock; ai_generated=false; made by AI Creator Studio from {len(images)} picture(s); no AI model"
    try:
        cues = [c.model_dump() for c in body.subtitles] if body.subtitles else None
        content, info = await asyncio.to_thread(video_mp4.make_mp4, images, body.aspect, body.duration_seconds, motion, transition, comment, cues)
        qc = await asyncio.to_thread(video_mp4.qc_mp4, content, video_mp4.SIZES[body.aspect], body.duration_seconds)
    except video_mp4.VideoEncodeError as exc:
        status_code = 503 if exc.code in ("FFMPEG_MISSING", "SUBTITLE_FONT_MISSING") else 422 if exc.code.startswith("SUBTITLE_") else 500
        raise HTTPException(status_code=status_code, detail={"code": exc.code, "message": str(exc) if status_code == 422 else "the video could not be made"}) from exc
    qc_out = {"passed": qc["passed"], "frames": qc["decoded_frames"], "checks": qc["checks"], "max_brightness_jump": qc["max_brightness_jump"],
              "static_ratio": qc["static_ratio"], "blank_frames": qc["blank_frames"]}
    output_asset_id, status, error = None, "failed", "QC_FAILED"
    if qc["passed"]:
        saved = store.save_asset(owner_id=user_id, workspace_id=workspace_id, filename=f"video-{job_id[-6:]}.mp4", content=content,
                                 validated=ValidatedAsset(media_type="video/mp4", size_bytes=len(content), gltf_version=None, embedded_binary=False),
                                 provenance_event=EVENT,
                                 provenance_extra={"job_id": job_id, "mode": "mock", "is_ai_generated": False, "aspect": body.aspect, "duration_seconds": body.duration_seconds,
                                                   "motion": body.motion, "output_format": "mp4", "fps": video_mp4.FPS, "frames": info["frames"], "size": info["size"],
                                                   "source_asset_ids": source_assets, "subtitle_cues": len(body.subtitles or []), "qc_passed": True})
        output_asset_id, status, error = saved["asset_id"], "succeeded", None
    with store._connect() as db:
        _init(db)
        _insert_job(db, job_id, workspace_id, user_id, body, status, output_asset_id, qc_out, error, now)
        return _public(db.execute("SELECT * FROM video_jobs WHERE job_id=?", (job_id,)).fetchone())


@router.get("", response_model=VideoListOut, operation_id="listVideoJobs")
async def list_video_jobs(workspace_id: str, user_id: str = Depends(current_user)):
    require_role(workspace_id, user_id, {"owner", "admin", "editor", "viewer"})
    with store._connect() as db:
        _init(db)
        rows = db.execute("SELECT * FROM video_jobs WHERE workspace_id=? ORDER BY created_at DESC, job_id LIMIT 100", (workspace_id,)).fetchall()
        return {"items": [_public(r) for r in rows]}


def _row(db, workspace_id: str, job_id: str):
    row = db.execute("SELECT * FROM video_jobs WHERE job_id=? AND workspace_id=?", (job_id, workspace_id)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Video job not found")
    return row


@router.get("/{job_id}", response_model=VideoOut, operation_id="getVideoJob")
async def get_video_job(workspace_id: str, job_id: str, user_id: str = Depends(current_user)):
    require_role(workspace_id, user_id, {"owner", "admin", "editor", "viewer"})
    with store._connect() as db:
        _init(db)
        return _public(_row(db, workspace_id, job_id))


@router.get("/{job_id}/poster", operation_id="getVideoJobPoster", response_class=Response, responses={200: {"content": {"image/png": {}}, "description": "A frame of the MP4 as a PNG (the cover)."}})
async def video_job_poster(workspace_id: str, job_id: str, at: float = Query(default=0.0, ge=0.0, le=1.0), max_side: int = Query(default=480, ge=16, le=1280),
                           user_id: str = Depends(current_user)):
    """The cover picture of a finished MP4 video: one frame at position ``at`` (0..1), shrunk so its longer side is at most ``max_side``. Pictures (WebP) need no cover."""
    require_role(workspace_id, user_id, {"owner", "admin", "editor", "viewer"})
    with store._connect() as db:
        _init(db)
        row = _row(db, workspace_id, job_id)
    if row["output_format"] != "mp4" or not row["output_asset_id"] or not takedown.visible_to(row["output_asset_id"], user_id):
        raise HTTPException(status_code=404, detail={"code": "VIDEO_POSTER_NOT_AVAILABLE", "message": "this job has no MP4 video to take a cover from"})
    path = store.storage_path(row["output_asset_id"])
    if path is None:
        raise HTTPException(status_code=409, detail={"code": "VIDEO_INPUT_GONE", "message": "the video file is missing"})
    try:
        picture = await asyncio.to_thread(lambda: video_mp4.poster_image(path.read_bytes(), at, max_side))
    except video_mp4.VideoEncodeError as exc:
        raise HTTPException(status_code=503 if exc.code == "FFMPEG_MISSING" else 500, detail={"code": exc.code, "message": "the cover could not be made"}) from exc
    buf = io.BytesIO()
    picture.save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png", headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})


@router.post("/{job_id}/cancel", operation_id="cancelVideoJob")
async def cancel_video_job(workspace_id: str, job_id: str, user_id: str = Depends(current_user)):
    """The built-in mock makes a video inside the request, so a job is never waiting or running: it is always finished (succeeded or failed) and there is nothing to cancel.
    The answer says so (409); a real provider's queued job will become cancellable when one is connected."""
    require_role(workspace_id, user_id, {"owner", "admin", "editor"})
    with store._connect() as db:
        _init(db)
        row = _row(db, workspace_id, job_id)
    raise HTTPException(status_code=409, detail={"code": "VIDEO_NOT_CANCELLABLE", "message": f"the job is already {row['status']}; there is nothing to cancel"})


@router.post("/{job_id}/retry", status_code=201, response_model=VideoOut, operation_id="retryVideoJob")
async def retry_video_job(workspace_id: str, job_id: str, user_id: str = Depends(current_user)):
    """Runs a FAILED job again with the same pictures and settings as a NEW job (the failed one stays as a record). Counts toward the same limits as any new video."""
    require_role(workspace_id, user_id, {"owner", "admin", "editor"})
    with store._connect() as db:
        _init(db)
        row = _row(db, workspace_id, job_id)
    if row["status"] != "failed":
        raise HTTPException(status_code=409, detail={"code": "VIDEO_RETRY_NOT_FAILED", "message": "only a failed video can be retried"})
    body = VideoIn(input_item_ids=json.loads(row["input_item_ids_json"]), aspect=row["aspect"], duration_seconds=row["duration_seconds"], motion=row["motion"],
                   output_format=row["output_format"], subtitles=json.loads(row["subtitles_json"]) if row["subtitles_json"] else None, prompt=row["instruction"])
    return await create_video_job(workspace_id, body, user_id)


@router.delete("/{job_id}", status_code=204, operation_id="deleteVideoJob")
async def delete_video_job(workspace_id: str, job_id: str, user_id: str = Depends(current_user)):
    """Removes the job record and its output picture file (deletion keeps the normal asset rules, so a still-referenced output stays)."""
    require_role(workspace_id, user_id, {"owner", "admin", "editor"})
    with store._connect() as db:
        _init(db)
        row = _row(db, workspace_id, job_id)
        db.execute("DELETE FROM video_jobs WHERE job_id=?", (job_id,))
    if row["output_asset_id"]:
        try:
            store.delete_asset(row["output_asset_id"], workspace_id, user_id)
        except Exception:  # noqa: BLE001
            pass
    return None
