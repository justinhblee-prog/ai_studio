"""D-3 (answer 73): the COUPLE try-on job - ``app/couple.py`` (R-ENGINE-16) behind a job route, own3d MOCK state.

  POST /v1/workspaces/{id}/couple-tryon   {asset_id, slots:{a:[kind..], b:[kind..]}, match?: "same"|"color"|null, sexes?:{a,b}}   -> 202 {job_id, status:"queued", ...}   editor or above
  GET  /v1/workspaces/{id}/couple-tryon/{job_id}   -> {status, asset_id, qc:{overlap_px, overlap_share, people[]}, error_code}                                           any member
  GET  /v1/workspaces/{id}/couple-tryon                                                                                                                              newest first

The photo of TWO people standing side by side is split (``couple.split_people``: slot ``a`` = the LEFT person, ``b`` = the RIGHT one), a too-large overlap is refused
(``COUPLE_OVERLAP_TOO_LARGE``), each person goes through the runner alone and the results are put back in place. The runner of this stage is the own3d MOCK: the person's area is
replaced by the 3D mannequin of the slot's sex wearing the slot's garments (fitted sample garments, ``render3d_scene``), drawn at the size of the person's box - a placeholder that shows
the pipeline and the garments, NOT a real try-on (no AI model, no photo of the garment on the person). ``match``: ``same`` = the second person gets the first person's garments, ``color`` = the kinds as asked, but a kind both people wear has ONE shared colour (the first person's). Behind the own3d flag ``RENDER3D_ENABLED`` (default OFF: 409 ``RENDER3D_CLOSED``).
Not done: a real per-person try-on model (needs the evaluation models, NEED_USER), people touching strongly, real couple photos (not tested: 미실행)."""
from __future__ import annotations

import io
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field

from app import config, couple, garments, render3d_scene, render3d_soft
from app.assets import store
from app.assets.routes import current_user, require_role
from app.assets.validation import ValidatedAsset

router = APIRouter(prefix="/v1/workspaces/{workspace_id}/couple-tryon", tags=["couple-tryon"])
EVENT = "asset.couple_tryon"
Kind = Literal["top", "bottom", "skirt", "dress", "jacket"]
EXCLUDES = {"dress": {"top", "bottom", "skirt"}, "skirt": {"bottom", "dress"}, "top": {"dress"}, "bottom": {"skirt", "dress"}, "jacket": set()}
BACKDROP = (226, 228, 234)
KEY = (255, 0, 254)
MAX_PIXELS = 12_000_000


def _init(db) -> None:
    db.execute("""CREATE TABLE IF NOT EXISTS couple_jobs (
        job_id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, owner_id TEXT NOT NULL, status TEXT NOT NULL, request_json TEXT NOT NULL, result_json TEXT, qc_json TEXT,
        error_code TEXT, created_at TEXT NOT NULL, finished_at TEXT)""")
    db.execute("CREATE INDEX IF NOT EXISTS idx_couple_jobs_ws ON couple_jobs(workspace_id, created_at)")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Slots(BaseModel):
    model_config = ConfigDict(extra="forbid")
    a: list[Kind] = Field(default_factory=list, max_length=3)
    b: list[Kind] = Field(default_factory=list, max_length=3)


class Sexes(BaseModel):
    model_config = ConfigDict(extra="forbid")
    a: Literal["male", "female"] = "female"
    b: Literal["male", "female"] = "male"


class CoupleIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    asset_id: str = Field(min_length=3, max_length=80)
    slots: Slots
    match: Literal["same", "color"] | None = None
    sexes: Sexes = Field(default_factory=Sexes)


def _closed() -> None:
    if not getattr(config, "RENDER3D_ENABLED", False):
        raise HTTPException(status_code=409, detail={"code": "RENDER3D_CLOSED", "message": "The 3D render job is not open yet."})


def effective_slots(slots: dict[str, list[str]], match: str | None) -> dict[str, list[str]]:
    """``same``: both wear the first person's garments; otherwise as given."""
    a, b = list(slots.get("a", [])), list(slots.get("b", []))
    return {"a": a, "b": a if match == "same" else b}


def _check(slots: dict[str, list[str]]) -> None:
    for side, kinds in slots.items():
        if len(set(kinds)) != len(kinds) or any(set(kinds) & EXCLUDES[k] for k in kinds):
            raise HTTPException(status_code=422, detail={"code": "RENDER3D_GARMENT_CONFLICT", "message": f"garments of slot {side} cannot be worn together"})


def mannequin_runner(sex_by_side: dict[str, str], kinds_by_side: dict[str, list[str]], match: str | None):
    """The own3d MOCK runner: the person's area becomes the dressed mannequin of the slot (same size as the crop)."""
    shared = dict(zip(kinds_by_side["a"], [render3d_scene.GARMENT_COLOURS[k] for k in kinds_by_side["a"]]))

    def run(crop: Image.Image, side: str) -> Image.Image:
        side = {"left": "a", "right": "b"}[side]                                # couple.split_people names the people left / right = slot a / b
        w, h = crop.size
        colours = {k: shared.get(k, render3d_scene.GARMENT_COLOURS[k]) for k in kinds_by_side[side]} if match == "color" else None
        body, layers, _ = render3d_scene.build_layers(sex_by_side[side], None, kinds_by_side[side], colours=colours)
        tris = body + [t for _, g, _ in layers for t in g]
        pic = render3d_soft.render(tris, 0, (max(16, w), max(16, h)), background=KEY, height_m=render3d_soft.height_of(tris))
        out = Image.new("RGB", pic.size, BACKDROP)
        out.paste(pic, mask=_silhouette(pic))
        return out.resize((w, h)).convert("RGBA")
    return run


def _silhouette(pic: Image.Image) -> Image.Image:
    px = pic.load()
    m = Image.new("L", pic.size, 0)
    mp = m.load()
    for y in range(pic.height):
        for x in range(pic.width):
            if px[x, y] != KEY:
                mp[x, y] = 255
    return m


def _public(row) -> dict[str, Any]:
    result = json.loads(row["result_json"]) if row["result_json"] else {}
    return {"job_id": row["job_id"], "workspace_id": row["workspace_id"], "status": row["status"], "engine": "own3d-mock", "request": json.loads(row["request_json"]),
            "asset_id": result.get("asset_id"), "qc": json.loads(row["qc_json"]) if row["qc_json"] else None, "error_code": row["error_code"], "created_at": row["created_at"],
            "finished_at": row["finished_at"], "mock": True, "note": "own3d mock: each person's area is replaced by the dressed 3D mannequin; not a real try-on"}


def run_job(job_id: str, workspace_id: str, user_id: str, request: dict[str, Any]) -> None:
    with store._connect() as db:
        _init(db)
        db.execute("UPDATE couple_jobs SET status='running' WHERE job_id=?", (job_id,))
    status, result, qc, error = "failed", None, None, "COUPLE_FAILED"
    try:
        path = store.storage_path(request["asset_id"])
        with Image.open(path) as im:
            im.load()
            photo = im.convert("RGB")
        slots = effective_slots(request["slots"], request.get("match"))
        runner = mannequin_runner({"a": request["sexes"]["a"], "b": request["sexes"]["b"]}, slots, request.get("match"))
        out = couple.run_couple(photo, runner)
        qc = {"overlap_px": out["overlap_px"], "overlap_share": round(out["overlap_share"], 4), "max_overlap_share": couple.MAX_OVERLAP_SHARE, "cut_x": out["cut_x"], "people": out["people"]}
        buf = io.BytesIO()
        out["image"].save(buf, format="PNG")
        data = buf.getvalue()
        saved = store.save_asset(owner_id=user_id, workspace_id=workspace_id, filename=f"couple-{job_id[-6:]}.png", content=data,
                                 validated=ValidatedAsset(media_type="image/png", size_bytes=len(data), gltf_version=None, embedded_binary=False), provenance_event=EVENT,
                                 provenance_extra={"job_id": job_id, "mode": "mock", "engine": "own3d-mock", "is_ai_generated": False, "source_asset_id": request["asset_id"], "slots": slots,
                                                   "overlap_px": out["overlap_px"]})
        result, status, error = {"asset_id": saved["asset_id"]}, "succeeded", None
    except couple.CoupleError as exc:
        error = exc.code if exc.code in ("COUPLE_OVERLAP_TOO_LARGE", "COUPLE_PERSON_NOT_FOUND") else "COUPLE_FAILED"
    except garments.GarmentError:
        error = "FIT_REFUSED"
    except Exception:  # noqa: BLE001 - the job record must end in a state
        error = "COUPLE_FAILED"
    with store._connect() as db:
        _init(db)
        db.execute("UPDATE couple_jobs SET status=?, result_json=?, qc_json=?, error_code=?, finished_at=? WHERE job_id=?",
                   (status, json.dumps(result) if result else None, json.dumps(qc) if qc else None, error, _now(), job_id))


@router.post("", status_code=202, operation_id="createCoupleTryon")
async def create_job(workspace_id: str, body: CoupleIn, background: BackgroundTasks, user_id: str = Depends(current_user)) -> dict[str, Any]:
    require_role(workspace_id, user_id, {"owner", "admin", "editor"})
    _closed()
    from app import rate_limit
    rate_limit.check("generate", user_id, workspace_id)
    source = store.get_asset(body.asset_id, workspace_id)
    if source is None or source.get("asset_kind") != "image":
        raise HTTPException(status_code=404, detail="Image asset not found")
    if not body.slots.a and not body.slots.b:
        raise HTTPException(status_code=422, detail={"code": "COUPLE_SLOTS_EMPTY", "message": "choose garments for at least one person"})
    _check(effective_slots(body.slots.model_dump(), body.match))
    job_id, request = "cpl_" + uuid.uuid4().hex, body.model_dump()
    with store._connect() as db:
        _init(db)
        db.execute("INSERT INTO couple_jobs(job_id, workspace_id, owner_id, status, request_json, created_at) VALUES (?,?,?,?,?,?)", (job_id, workspace_id, user_id, "queued", json.dumps(request), _now()))
        out = _public(db.execute("SELECT * FROM couple_jobs WHERE job_id=?", (job_id,)).fetchone())
    background.add_task(run_job, job_id, workspace_id, user_id, request)
    return out


@router.get("", operation_id="listCoupleTryons")
async def list_jobs(workspace_id: str, user_id: str = Depends(current_user)) -> dict[str, Any]:
    require_role(workspace_id, user_id, {"owner", "admin", "editor", "viewer"})
    _closed()
    with store._connect() as db:
        _init(db)
        rows = db.execute("SELECT * FROM couple_jobs WHERE workspace_id=? ORDER BY created_at DESC LIMIT 100", (workspace_id,)).fetchall()
    return {"items": [_public(r) for r in rows]}


@router.get("/{job_id}", operation_id="getCoupleTryon")
async def get_job(workspace_id: str, job_id: str, user_id: str = Depends(current_user)) -> dict[str, Any]:
    require_role(workspace_id, user_id, {"owner", "admin", "editor", "viewer"})
    _closed()
    with store._connect() as db:
        _init(db)
        row = db.execute("SELECT * FROM couple_jobs WHERE job_id=? AND workspace_id=?", (job_id, workspace_id)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return _public(row)
