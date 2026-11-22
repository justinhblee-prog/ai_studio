"""R-ENGINE-10: the ``render3d`` job - the in-house engine ``own3d`` (MOCK state) turns typed body measurements + garments into pictures from several angles and a rotating MP4.

  POST /v1/workspaces/{workspace_id}/render3d-jobs   {sex, measurements?, garments:[{kind, id}], bg, angles, mp4}  -> 202 {job_id, status: "queued", ...}
  GET  /v1/workspaces/{workspace_id}/render3d-jobs/{job_id}   (poll)  -> {status, images: [{angle, asset_id}], mp4: {asset_id, ...} | null, qc, error_code}
  GET  /v1/workspaces/{workspace_id}/render3d-jobs            -> the workspace's jobs, newest first

What it does: builds the base body of ``sex`` at the typed measurements (``app/base_models.py``), fits each requested sample garment to it (``app/garment_deform.py``, garment.v1 mesh
deformation), draws the scene with the software renderer (``app/render3d_soft.py``) from each angle, and - if asked - turns 8 cuts (every 45 degrees) into a 5 second rotating
H.264 MP4 with ffmpeg (``app/video_mp4.py``). The pictures and the video are stored as ordinary workspace assets (image/png, video/mp4), so the normal asset routes serve them.
What it is NOT: no AI model, no photo, no GPU, no external service, no paid call. The pictures look like a mock (plain mannequin, flat colours, one light). A garment id is only the
built-in sample (``sample`` or ``sample-<kind>-<sex>``): turning a library garment into garment.v1 is R-ENGINE-12 research, not built.
The whole feature is behind the flag ``RENDER3D_ENABLED`` (default OFF): closed, every route answers 409 ``RENDER3D_CLOSED`` after the usual sign-in and role checks.
A job runs in the background of the request; ``queued`` -> ``running`` -> ``succeeded`` | ``failed``. A job found ``queued``/``running`` after a server restart stays so (no recovery yet).
"""
from __future__ import annotations

import io
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from PIL import Image, ImageChops
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app import base_models, config, garments, render3d_scene, render3d_soft, render_qc, video_mp4
from app.assets import store
from app.assets.routes import current_user, require_role
from app.assets.validation import ValidatedAsset

router = APIRouter(prefix="/v1/workspaces/{workspace_id}/render3d-jobs", tags=["render3d-jobs"])
EVENT = "asset.render3d_output"
STILL_SIZE = (360, 640)
DEFAULT_ANGLES = [0, 45, 90, 180, 270]
CUT_ANGLES = [45 * k for k in range(8)]          # the 8 cuts of the rotating video (a multiple of 45 degrees is reused for a picture)
MP4_SECONDS, MP4_ASPECT = 5, "9:16"
MAX_GARMENTS, MAX_ANGLES = 3, 8
DAILY_LIMIT_DEFAULT = 20
EXCLUDES = {"dress": {"top", "bottom", "skirt"}, "skirt": {"bottom", "dress"}, "top": {"dress"}, "bottom": {"skirt", "dress"}, "jacket": set()}
MIN_PAINTED_SHARE = 0.004                         # a picture where fewer pixels than this differ from the background is blank


def _init(db) -> None:
    db.execute("""CREATE TABLE IF NOT EXISTS render3d_jobs (
        job_id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, owner_id TEXT NOT NULL, status TEXT NOT NULL, engine TEXT NOT NULL, request_json TEXT NOT NULL,
        result_json TEXT, qc_json TEXT, error_code TEXT, created_at TEXT NOT NULL, finished_at TEXT)""")
    db.execute("CREATE INDEX IF NOT EXISTS idx_render3d_jobs_ws ON render3d_jobs(workspace_id, created_at)")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class GarmentRef(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["top", "bottom", "skirt", "dress", "jacket"]
    id: str = Field(default="sample", min_length=1, max_length=48)


class RenderIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sex: Literal["male", "female"]
    measurements: dict[str, float] | None = Field(default=None, max_length=4)
    garments: list[GarmentRef] = Field(default_factory=list, max_length=MAX_GARMENTS)
    bg: Literal["white", "light", "gray", "studio"] = "light"
    angles: list[int] = Field(default_factory=lambda: list(DEFAULT_ANGLES), min_length=1, max_length=MAX_ANGLES)
    mp4: bool = True

    @field_validator("angles")
    @classmethod
    def _angles(cls, value: list[int]) -> list[int]:
        if len(set(value)) != len(value) or any(isinstance(a, bool) or not 0 <= a <= 345 or a % 15 for a in value):
            raise ValueError("angles must be different multiples of 15 from 0 to 345")
        return value


class ImageOut(BaseModel):
    angle: int
    asset_id: str


class Mp4Out(BaseModel):
    model_config = ConfigDict(extra="allow")
    asset_id: str
    seconds: int
    size: list[int]


class RenderOut(BaseModel):
    job_id: str
    workspace_id: str
    owner_id: str
    status: Literal["queued", "running", "succeeded", "failed"]
    engine: str
    request: dict[str, Any]
    images: list[ImageOut]
    mp4: Mp4Out | None
    qc: dict[str, Any] | None
    error_code: str | None
    created_at: str
    finished_at: str | None


class RenderListOut(BaseModel):
    items: list[RenderOut]


def _public(row) -> dict[str, Any]:
    result = json.loads(row["result_json"]) if row["result_json"] else {}
    return {"job_id": row["job_id"], "workspace_id": row["workspace_id"], "owner_id": row["owner_id"], "status": row["status"], "engine": row["engine"],
            "request": json.loads(row["request_json"]), "images": result.get("images", []), "mp4": result.get("mp4"),
            "qc": json.loads(row["qc_json"]) if row["qc_json"] else None, "error_code": row["error_code"], "created_at": row["created_at"], "finished_at": row["finished_at"]}


def _closed() -> None:
    if not getattr(config, "RENDER3D_ENABLED", False):
        raise HTTPException(status_code=409, detail={"code": "RENDER3D_CLOSED", "message": "The 3D render job is not open yet."})


def _check_request(body: RenderIn) -> None:
    if body.measurements:
        try:
            base_models._fit_measurements(base_models.PRESETS[body.sex], body.measurements)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail={"code": "RENDER3D_MEASUREMENT_INVALID", "message": str(exc)}) from exc
    kinds = [g.kind for g in body.garments]
    if len(set(kinds)) != len(kinds):
        raise HTTPException(status_code=422, detail={"code": "RENDER3D_GARMENT_CONFLICT", "message": "each garment kind can be used once"})
    for g in body.garments:
        if g.id not in ("sample", f"sample-{g.kind}-{body.sex}"):
            raise HTTPException(status_code=422, detail={"code": "RENDER3D_GARMENT_UNKNOWN", "message": "only the built-in sample garments can be rendered for now"})
        if EXCLUDES[g.kind] & set(kinds):
            raise HTTPException(status_code=422, detail={"code": "RENDER3D_GARMENT_CONFLICT", "message": f"a {g.kind} cannot be worn with {sorted(EXCLUDES[g.kind] & set(kinds))}"})


def build_scene(sex: str, measurements: dict[str, float] | None, garment_kinds: list[str]):
    """(all triangles, fitting reports, (body, garment layers)). Raises ``garments.GarmentError`` if a garment cannot be fitted."""
    body, layers, reports = render3d_scene.build_layers(sex, measurements, garment_kinds)
    return body + [t for _, tris, _ in layers for t in tris], reports, (body, layers)


def _painted_share(image: Image.Image, background: tuple[int, int, int]) -> float:
    gap = ImageChops.difference(image, Image.new("RGB", image.size, background)).convert("L").point(lambda v: 255 if v > 12 else 0)
    return gap.histogram()[255] / (image.width * image.height)


def run_job(job_id: str, workspace_id: str, user_id: str, request: dict[str, Any]) -> None:
    """Runs in the background of the POST. Everything is made in memory first; assets are stored only if every check passes."""
    with store._connect() as db:
        _init(db)
        db.execute("UPDATE render3d_jobs SET status='running' WHERE job_id=?", (job_id,))
    status, result, qc, error = "failed", None, None, "RENDER_FAILED"
    try:
        tris, fits, (body_tris, layers) = build_scene(request["sex"], request.get("measurements"), [g["kind"] for g in request["garments"]])
        background = render3d_soft.BACKGROUNDS[request["bg"]]
        height = render3d_soft.height_of(tris)
        cache: dict[int, Image.Image] = {}

        def picture(angle: int) -> Image.Image:
            if angle not in cache:
                cache[angle] = render3d_soft.render(tris, angle, STILL_SIZE, background=background, height_m=height)
            return cache[angle]
        stills = {a: picture(a) for a in request["angles"]}
        shares = {a: round(_painted_share(im, background), 4) for a, im in stills.items()}
        qc = {"passed": all(s >= MIN_PAINTED_SHARE for s in shares.values()), "painted_share": {str(a): s for a, s in shares.items()}, "min_share": MIN_PAINTED_SHARE, "fits": fits}
        # R-ENGINE-11: a RECORD of how the garments look in the pictures (the body poking through, colour). It does not decide delivery: ``qc.passed`` stays the blank-picture check.
        qc["render_check"] = render_qc.check_cuts(body_tris, layers, request["angles"], penetrations={f["kind"]: f["penetrations"] for f in fits})
        content_mp4, mp4_info = None, None
        if qc["passed"] and request["mp4"]:
            cuts = [picture(a) for a in CUT_ANGLES]
            comment = f"job={job_id}; mode=mock; engine=own3d-soft; ai_generated=false; made by AI Creator Studio, no AI model"
            content_mp4, mp4_info = video_mp4.make_turntable_mp4(cuts, MP4_ASPECT, MP4_SECONDS, 1, comment)
            mp4_qc = video_mp4.qc_mp4(content_mp4, video_mp4.SIZES[MP4_ASPECT], MP4_SECONDS)
            qc["mp4"] = {"passed": mp4_qc["passed"], "frames": mp4_qc["decoded_frames"], "checks": mp4_qc["checks"]}
            qc["passed"] = qc["passed"] and mp4_qc["passed"]
        if not qc["passed"]:
            error = "QC_FAILED"
        else:
            images = []
            for angle in request["angles"]:
                buf = io.BytesIO()
                stills[angle].save(buf, format="PNG")
                data = buf.getvalue()
                saved = store.save_asset(owner_id=user_id, workspace_id=workspace_id, filename=f"render3d-{job_id[-6:]}-{angle:03d}.png", content=data,
                                         validated=ValidatedAsset(media_type="image/png", size_bytes=len(data), gltf_version=None, embedded_binary=False), provenance_event=EVENT,
                                         provenance_extra={"job_id": job_id, "mode": "mock", "engine": "own3d-soft", "is_ai_generated": False, "angle": angle, "qc_passed": True})
                images.append({"angle": angle, "asset_id": saved["asset_id"]})
            mp4 = None
            if content_mp4 is not None:
                saved = store.save_asset(owner_id=user_id, workspace_id=workspace_id, filename=f"render3d-{job_id[-6:]}.mp4", content=content_mp4,
                                         validated=ValidatedAsset(media_type="video/mp4", size_bytes=len(content_mp4), gltf_version=None, embedded_binary=False), provenance_event=EVENT,
                                         provenance_extra={"job_id": job_id, "mode": "mock", "engine": "own3d-soft", "is_ai_generated": False, "motion": "turntable", "qc_passed": True})
                mp4 = {"asset_id": saved["asset_id"], "seconds": MP4_SECONDS, "size": list(video_mp4.SIZES[MP4_ASPECT]), "cuts": len(CUT_ANGLES),
                       "blended_frames": mp4_info["blended_frames"] if mp4_info else None}
            result, status, error = {"images": images, "mp4": mp4}, "succeeded", None
    except garments.GarmentError:
        error = "FIT_REFUSED"
    except video_mp4.VideoEncodeError as exc:
        error = exc.code if exc.code in ("FFMPEG_MISSING",) else "RENDER_FAILED"
    except Exception:  # noqa: BLE001 - the job record must end in a state; the cause is not echoed to the client
        error = "RENDER_FAILED"
    with store._connect() as db:
        _init(db)
        db.execute("UPDATE render3d_jobs SET status=?, result_json=?, qc_json=?, error_code=?, finished_at=? WHERE job_id=?",
                   (status, json.dumps(result) if result else None, json.dumps(qc) if qc else None, error, _now(), job_id))


@router.post("", status_code=202, response_model=RenderOut, operation_id="createRender3dJob")
async def create_render3d_job(workspace_id: str, body: RenderIn, background: BackgroundTasks, user_id: str = Depends(current_user)):
    require_role(workspace_id, user_id, {"owner", "admin", "editor"})
    _closed()
    from app import rate_limit
    rate_limit.check("generate", user_id, workspace_id)
    _check_request(body)
    if body.mp4 and video_mp4.find_ffmpeg() is None:        # no silent fallback to pictures only
        raise HTTPException(status_code=503, detail={"code": "FFMPEG_MISSING", "message": "MP4 output is not available on this server"})
    since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    with store._connect() as db:
        _init(db)
        used = db.execute("SELECT COUNT(*) AS n FROM render3d_jobs WHERE workspace_id=? AND created_at>=?", (workspace_id, since)).fetchone()["n"]
    limit = int(getattr(config, "RENDER3D_DAILY_LIMIT", DAILY_LIMIT_DEFAULT))
    if used >= limit:
        raise rate_limit.too_many("RENDER3D_DAILY_LIMIT", "today's 3D render limit is used up", 3600, estimated=True, limit=limit, used=used)
    job_id, request = "r3d_" + uuid.uuid4().hex, body.model_dump()
    with store._connect() as db:
        _init(db)
        db.execute("INSERT INTO render3d_jobs(job_id, workspace_id, owner_id, status, engine, request_json, created_at) VALUES (?,?,?,?,?,?,?)",
                   (job_id, workspace_id, user_id, "queued", "own3d-mock", json.dumps(request), _now()))
        row = db.execute("SELECT * FROM render3d_jobs WHERE job_id=?", (job_id,)).fetchone()
        out = _public(row)
    background.add_task(run_job, job_id, workspace_id, user_id, request)
    return out


@router.get("", response_model=RenderListOut, operation_id="listRender3dJobs")
async def list_render3d_jobs(workspace_id: str, user_id: str = Depends(current_user)):
    require_role(workspace_id, user_id, {"owner", "admin", "editor", "viewer"})
    _closed()
    with store._connect() as db:
        _init(db)
        rows = db.execute("SELECT * FROM render3d_jobs WHERE workspace_id=? ORDER BY created_at DESC, job_id LIMIT 100", (workspace_id,)).fetchall()
        return {"items": [_public(r) for r in rows]}


@router.get("/{job_id}", response_model=RenderOut, operation_id="getRender3dJob")
async def get_render3d_job(workspace_id: str, job_id: str, user_id: str = Depends(current_user)):
    require_role(workspace_id, user_id, {"owner", "admin", "editor", "viewer"})
    _closed()
    with store._connect() as db:
        _init(db)
        row = db.execute("SELECT * FROM render3d_jobs WHERE job_id=? AND workspace_id=?", (job_id, workspace_id)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="3D render job not found")
        return _public(row)
