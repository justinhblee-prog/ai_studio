"""D-4 (answer 73): the story -> video job route (``app/story_video.py``, R-ENGINE-17), local engine only.

  POST /v1/workspaces/{id}/video/story   {story, length: "auto"|6|10|15|30|60, sources:[asset_id], aspect?, transitions?, captions?: "auto"|[texts]|null, motion?, engine?: "local"|"ai"}
        -> 202 {job_id, status:"queued", plan:{scenes, seconds_per_scene, cuts:[{scene, asset_id, start, end, caption}], cues}}      editor or above
  GET  /v1/workspaces/{id}/video/story/{job_id}  -> {status, asset_id, mp4:{seconds, size, frames, bytes}, cuts, error_code}                    any member
  GET  /v1/workspaces/{id}/video/story                                                                                                           newest first

The story is cut into scenes at request time (a bad story / length is refused AT ONCE with a ``STORY_*`` code, nothing is queued), the MP4 is made in the background by ffmpeg
(H.264, ``video_mp4``) with the captions burned in (open Korean font; ``SUBTITLE_FONT_MISSING`` when the server has none; ``FFMPEG_MISSING`` 503 when it has no ffmpeg - no silent fallback).
``length: "auto"`` = 3 seconds per scene (at most 60). ``engine: "ai"`` is a closed door: 409 ``STORY_ENGINE_CLOSED`` (an AI video provider needs a key and money: the customer's decision).
The sources are the workspace's own image assets; scene j shows ``sources[cut.image_index]``. The same ``cuts`` shape the screen's story step makes (``__caps`` / ``__dur``: caption + seconds per cut)."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field

from app import story_video, video_mp4, video_subtitles
from app.assets import store
from app.assets.routes import current_user, require_role
from app.assets.validation import ValidatedAsset

router = APIRouter(prefix="/v1/workspaces/{workspace_id}/video/story", tags=["story-video"])
EVENT = "asset.story_video"
SECONDS_PER_SCENE_AUTO = 3
LENGTHS = (6, 10, 15, 30, 60)


def _init(db) -> None:
    db.execute("""CREATE TABLE IF NOT EXISTS story_video_jobs (
        job_id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, owner_id TEXT NOT NULL, status TEXT NOT NULL, request_json TEXT NOT NULL, plan_json TEXT NOT NULL, result_json TEXT,
        error_code TEXT, created_at TEXT NOT NULL, finished_at TEXT)""")
    db.execute("CREATE INDEX IF NOT EXISTS idx_story_video_jobs_ws ON story_video_jobs(workspace_id, created_at)")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class StoryIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    story: str = Field(min_length=1, max_length=4000)
    length: int | Literal["auto"] = "auto"
    sources: list[str] = Field(min_length=1, max_length=story_video.MAX_IMAGES)
    aspect: Literal["9:16", "4:5", "16:9"] = "9:16"
    transitions: Literal["cut", "crossfade"] = "crossfade"
    captions: Literal["auto"] | list[str] | None = "auto"
    motion: Literal["zoom", "pan", "rotate"] = "zoom"
    engine: Literal["local", "ai"] = "local"


def _seconds(length: int | str, story: str, captions: Any, n_sources: int) -> int:
    if length == "auto":
        scenes = max(len(story_video.split_story(story)), n_sources, 1)
        return max(story_video.MIN_SECONDS, min(story_video.MAX_SECONDS, scenes * SECONDS_PER_SCENE_AUTO))
    return int(length)


def make_plan(body: StoryIn) -> dict[str, Any]:
    """The plan at request time. Raises ``story_video.StoryError`` for a bad story / length / captions / engine."""
    seconds = _seconds(body.length, body.story, body.captions, len(body.sources))
    plan = story_video.plan(len(body.sources), body.story, seconds, body.captions, body.engine)
    plan["cuts"] = [{"scene": c["scene"], "asset_id": body.sources[c["image_index"]], "image_index": c["image_index"], "start": c["start"], "end": c["end"], "caption": c["caption"]} for c in plan["cuts"]]
    return plan


def _public(row) -> dict[str, Any]:
    plan = json.loads(row["plan_json"])
    result = json.loads(row["result_json"]) if row["result_json"] else {}
    return {"job_id": row["job_id"], "workspace_id": row["workspace_id"], "status": row["status"], "engine": "local", "plan": plan, "asset_id": result.get("asset_id"), "mp4": result.get("mp4"),
            "cuts": plan["cuts"], "error_code": row["error_code"], "created_at": row["created_at"], "finished_at": row["finished_at"]}


def run_job(job_id: str, workspace_id: str, user_id: str, request: dict[str, Any], plan: dict[str, Any]) -> None:
    with store._connect() as db:
        _init(db)
        db.execute("UPDATE story_video_jobs SET status='running' WHERE job_id=?", (job_id,))
    status, result, error = "failed", None, "STORY_VIDEO_FAILED"
    try:
        images = []
        for asset_id in request["sources"]:
            path = store.storage_path(asset_id)
            with Image.open(path) as im:
                im.load()
                images.append(im.convert("RGB"))
        comment = f"job={job_id}; mode=local; engine=story-video; ai_generated=false; made by AI Creator Studio, no AI model"
        data, meta = story_video.make_story_mp4(images, request["story"], plan["total_seconds"], request["aspect"], request["transitions"], request["captions"], request["motion"], "local", comment)
        saved = store.save_asset(owner_id=user_id, workspace_id=workspace_id, filename=f"story-{job_id[-6:]}.mp4", content=data,
                                 validated=ValidatedAsset(media_type="video/mp4", size_bytes=len(data), gltf_version=None, embedded_binary=False), provenance_event=EVENT,
                                 provenance_extra={"job_id": job_id, "mode": "local", "engine": "story-video", "is_ai_generated": False, "sources": request["sources"], "seconds": plan["total_seconds"],
                                                   "scenes": plan["scenes"]})
        result, status, error = {"asset_id": saved["asset_id"], "mp4": {"seconds": plan["total_seconds"], "size": meta["size"], "frames": meta["frames"], "bytes": meta["bytes"]}}, "succeeded", None
    except video_mp4.VideoEncodeError as exc:
        error = exc.code if exc.code in ("FFMPEG_MISSING", "SUBTITLE_FONT_MISSING", "SUBTITLE_GLYPH_MISSING") else "STORY_VIDEO_FAILED"
    except Exception:  # noqa: BLE001 - the job record must end in a state; the cause is not echoed
        error = "STORY_VIDEO_FAILED"
    with store._connect() as db:
        _init(db)
        db.execute("UPDATE story_video_jobs SET status=?, result_json=?, error_code=?, finished_at=? WHERE job_id=?", (status, json.dumps(result) if result else None, error, _now(), job_id))


@router.post("", status_code=202, operation_id="createStoryVideo")
async def create_story_video(workspace_id: str, body: StoryIn, background: BackgroundTasks, user_id: str = Depends(current_user)) -> dict[str, Any]:
    require_role(workspace_id, user_id, {"owner", "admin", "editor"})
    if isinstance(body.length, int) and body.length not in LENGTHS and not (story_video.MIN_SECONDS <= body.length <= story_video.MAX_SECONDS):
        raise HTTPException(status_code=422, detail={"code": "STORY_SECONDS_INVALID", "message": "length is auto or 1..60 seconds"})
    try:
        plan = make_plan(body)
    except story_video.StoryError as exc:
        if exc.code == "STORY_ENGINE_CLOSED":
            raise HTTPException(status_code=409, detail={"code": exc.code, "message": str(exc)}) from exc
        raise HTTPException(status_code=422, detail={"code": exc.code, "message": str(exc)}) from exc
    if len(set(body.sources)) != len(body.sources):
        raise HTTPException(status_code=422, detail={"code": "STORY_IMAGES_INVALID", "message": "each picture may be used once in the source list"})
    for asset_id in body.sources:
        source = store.get_asset(asset_id, workspace_id)
        if source is None or source.get("asset_kind") != "image":
            raise HTTPException(status_code=404, detail="Image asset not found")
    if video_mp4.find_ffmpeg() is None:
        raise HTTPException(status_code=503, detail={"code": "FFMPEG_MISSING", "message": "MP4 output is not available on this server"})
    if plan["cues"] and video_subtitles.find_subtitle_font() is None:
        raise HTTPException(status_code=503, detail={"code": "SUBTITLE_FONT_MISSING", "message": "no subtitle font is installed on this server"})
    from app import rate_limit
    rate_limit.check("generate", user_id, workspace_id)
    job_id, request = "stv_" + uuid.uuid4().hex, body.model_dump()
    with store._connect() as db:
        _init(db)
        db.execute("INSERT INTO story_video_jobs(job_id, workspace_id, owner_id, status, request_json, plan_json, created_at) VALUES (?,?,?,?,?,?,?)",
                   (job_id, workspace_id, user_id, "queued", json.dumps(request, ensure_ascii=False), json.dumps(plan, ensure_ascii=False), _now()))
        out = _public(db.execute("SELECT * FROM story_video_jobs WHERE job_id=?", (job_id,)).fetchone())
    background.add_task(run_job, job_id, workspace_id, user_id, request, plan)
    return out


@router.get("", operation_id="listStoryVideos")
async def list_story_videos(workspace_id: str, user_id: str = Depends(current_user)) -> dict[str, Any]:
    require_role(workspace_id, user_id, {"owner", "admin", "editor", "viewer"})
    with store._connect() as db:
        _init(db)
        rows = db.execute("SELECT * FROM story_video_jobs WHERE workspace_id=? ORDER BY created_at DESC LIMIT 100", (workspace_id,)).fetchall()
    return {"items": [_public(r) for r in rows]}


@router.get("/{job_id}", operation_id="getStoryVideo")
async def get_story_video(workspace_id: str, job_id: str, user_id: str = Depends(current_user)) -> dict[str, Any]:
    require_role(workspace_id, user_id, {"owner", "admin", "editor", "viewer"})
    with store._connect() as db:
        _init(db)
        row = db.execute("SELECT * FROM story_video_jobs WHERE job_id=? AND workspace_id=?", (job_id, workspace_id)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return _public(row)
