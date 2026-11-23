"""R-PSD-01: hand a layered PSD to ANY PSD program and take the edited file back (``app/psd_io.py`` does the format).

  POST /v1/workspaces/{id}/photo-psd           {asset_id, final_asset_id?, cutout?: true, depth?: 8|16}   editor or above  ->  the PSD file (download)
  POST /v1/workspaces/{id}/photo-psd/import    multipart: file (.psd/.psb, <= 300 MB), rights_confirmed (+ depicts_person, likeness_consent)  ->  201 {asset, psd, source}

Export keeps the ORIGINAL resolution (up to ``MAX_EXPORT_PIXELS``), writes the layers bottom -> top: original (hidden, reference) / background (the subject's place left empty) / subject (cut-out)
/ final result (flat, hidden, reference); without ``cutout``: original (hidden) / the result. The merged image is the result as it is now. sRGB ICC is embedded; 16 bit on request. A PSD is a
WORKING file: it may be taken before a review, the final PNG/JPEG export keeps its own approval rule. The file is returned directly (nothing is stored); the export is written to the asset's trail.
Import reads the PSD (layers are not interpreted: text layers and smart objects are kept as the pixels they were saved with), takes the merged image - or composites the visible layers when the
file has none - reduces its long side to ``WORK_SIDE`` px as a new ORIGINAL asset, records a version with who/when/layer count/size, keeps the PSD file itself (private, under its SHA-256) and
writes ``asset.psd_import`` to the trail ("PSD 수정본"). The rights confirmation of an image upload applies as it does everywhere.
"""
from __future__ import annotations

import hashlib
import io
import json
from typing import Any, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from PIL import Image, ImageChops
from pydantic import BaseModel, ConfigDict, Field

from app import bg_removal, config, psd_io, takedown
from app.assets import store
from app.assets.rights import build_upload_confirmation
from app.assets.routes import current_user, require_role
from app.assets.validation import AssetValidationError, validate_image_upload

router = APIRouter(prefix="/v1/workspaces/{workspace_id}/photo-psd", tags=["photo-psd"])
EVENT_EXPORT, EVENT_IMPORT = "asset.psd_exported", "asset.psd_import"
MAX_EXPORT_PIXELS = 60_000_000
WORK_SIDE = 3000
PSD_MEDIA = "image/vnd.adobe.photoshop"


class ExportIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    asset_id: str = Field(min_length=3, max_length=80)
    final_asset_id: str | None = Field(default=None, min_length=3, max_length=80)
    cutout: bool = True
    depth: Literal[8, 16] = 8


def _err(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def _open(workspace_id: str, asset_id: str) -> tuple[Image.Image, dict[str, Any]]:
    source = store.get_asset(asset_id, workspace_id)
    path = store.storage_path(asset_id) if source else None
    if source is None or path is None or source.get("asset_kind") != "image" or not takedown.visible_to(asset_id, "") and False:
        raise HTTPException(status_code=404, detail="Image asset not found")
    try:
        with Image.open(path) as im:
            im.load()
            return im.convert("RGBA"), source
    except (OSError, Image.DecompressionBombError) as exc:
        raise _err(422, "IMAGE_UNREADABLE", "The image could not be read.") from exc


def build_layers(original: Image.Image, final: Image.Image | None, cutout: bool) -> tuple[list[psd_io.Layer], Image.Image]:
    """(layers bottom -> top, merged picture). ``final`` = the current result (None = the original itself)."""
    result = (final or original).convert("RGBA")
    if result.size != original.size:
        result = result.resize(original.size)
    if not cutout:
        return [psd_io.Layer("원본 (참고)", original, visible=False), psd_io.Layer("보정 결과", result)], result.convert("RGB")
    mask = bg_removal.foreground_mask(result.convert("RGB"), "auto").convert("L").point(lambda v: 255 if v > 127 else 0)
    subject = result.copy()
    subject.putalpha(ImageChops.multiply(subject.getchannel("A"), mask))
    background = result.copy()
    background.putalpha(ImageChops.multiply(background.getchannel("A"), ImageChops.invert(mask)))       # the subject's place is left empty
    layers = [psd_io.Layer("원본 (참고)", original, visible=False), psd_io.Layer("배경 (피사체 자리 비움)", background), psd_io.Layer("피사체 (누끼)", subject),
              psd_io.Layer("최종 결과 (평면, 참고)", result, visible=False)]
    return layers, result.convert("RGB")


def _record(workspace_id: str, asset_id: str, user_id: str, event: str, details: dict[str, Any]) -> None:
    import uuid
    from datetime import datetime, timezone
    store.initialize()
    with store._connect() as db:
        db.execute("INSERT INTO asset_provenance(provenance_id, workspace_id, asset_id, version_number, event_type, actor_id, details_json, created_at) VALUES (?,?,?,?,?,?,?,?)",
                   ("ap_psd_" + uuid.uuid4().hex, workspace_id, asset_id, None, event, user_id, json.dumps(details, ensure_ascii=False), datetime.now(timezone.utc).isoformat()))


@router.post("", operation_id="exportPhotoPsd", response_class=Response, responses={200: {"content": {PSD_MEDIA: {}}, "description": "The layered PSD"}})
async def export_psd(workspace_id: str, body: ExportIn, user_id: str = Depends(current_user)):
    require_role(workspace_id, user_id, {"owner", "admin", "editor"})
    from app import rate_limit
    rate_limit.check("download", user_id, workspace_id)
    original, source = _open(workspace_id, body.asset_id)
    if original.width * original.height > MAX_EXPORT_PIXELS:
        raise _err(422, "PSD_TOO_LARGE", "The picture is too large for a PSD export.")
    final = _open(workspace_id, body.final_asset_id)[0] if body.final_asset_id else None
    layers, merged = build_layers(original, final, body.cutout)
    try:
        data = psd_io.write_psd(layers, original.size, merged, depth=body.depth, version=1 if max(original.size) <= psd_io.MAX_SIDE[1] else 2)
    except psd_io.PsdError as exc:
        raise _err(422, exc.code, str(exc)) from exc
    sha = hashlib.sha256(data).hexdigest()
    _record(workspace_id, body.asset_id, user_id, EVENT_EXPORT, {"layers": len(layers), "depth": body.depth, "cutout": body.cutout, "bytes": len(data), "sha256": sha})
    name = str(source["original_filename"]).rsplit(".", 1)[0] + ".psd"
    ascii_name = name.encode("ascii", "ignore").decode() or "photo.psd"
    return Response(content=data, media_type=PSD_MEDIA, headers={"Content-Disposition": f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{__import__('urllib.parse').parse.quote(name)}",
                                                                 "ETag": f"\"{sha}\"", "X-Content-SHA256": sha, "Cache-Control": "private, no-store"})


@router.post("/import", status_code=201, operation_id="importPhotoPsd")
async def import_psd(workspace_id: str, file: UploadFile = File(...), rights_confirmed: bool | None = Form(default=None), depicts_person: bool | None = Form(default=None),
                     likeness_consent: bool | None = Form(default=None), user_id: str = Depends(current_user)) -> dict[str, Any]:
    require_role(workspace_id, user_id, {"owner", "admin", "editor"})
    from app import rate_limit
    rate_limit.check("upload", user_id, workspace_id)
    filename = str(file.filename or "edited.psd").replace("\\", "/").rsplit("/", 1)[-1]
    if not filename.lower().endswith((".psd", ".psb")):
        raise _err(422, "PSD_NOT_PSD", "Only .psd and .psb files can be uploaded here.")
    data = await file.read(psd_io.MAX_BYTES + 1)
    await file.close()
    if len(data) > psd_io.MAX_BYTES:
        raise _err(413, "PSD_TOO_LARGE", "The file is larger than 300 MB.")
    try:
        psd = psd_io.read_psd(data)
        image, how = psd_io.to_image(psd)
        confirmation = build_upload_confirmation(rights_confirmed, depicts_person, likeness_consent)
    except psd_io.PsdError as exc:
        raise _err(422, exc.code, str(exc)) from exc
    except AssetValidationError as exc:
        raise _err(422, exc.code, str(exc)) from exc
    long_side = max(image.size)
    reduced = image.copy()
    if long_side > WORK_SIDE:
        reduced.thumbnail((WORK_SIDE, WORK_SIDE), Image.LANCZOS)
    buf = io.BytesIO()
    reduced.convert("RGB").save(buf, format="PNG")
    png_name = filename.rsplit(".", 1)[0] + "-psd.png"
    try:
        validated = validate_image_upload(png_name, buf.getvalue(), max_bytes=config.ASSET_MAX_UPLOAD_BYTES)
    except AssetValidationError as exc:
        raise _err(422, exc.code, str(exc)) from exc
    sha = hashlib.sha256(data).hexdigest()
    keep = config.ASSET_STORAGE_DIR / "psd"
    keep.mkdir(parents=True, exist_ok=True)
    (keep / f"{sha}{'.psb' if psd.version == 2 else '.psd'}").write_bytes(data)
    info = psd_io.describe(psd)
    saved = store.save_asset(owner_id=user_id, workspace_id=workspace_id, filename=png_name, content=buf.getvalue(), validated=validated, upload_confirmation=confirmation,
                             provenance_event=EVENT_IMPORT,
                             provenance_extra={"source": "psd", "psd_sha256": sha, "psd_bytes": len(data), "psd_format": info["format"], "layers": info["layers"], "psd_size": [psd.width, psd.height],
                                               "work_size": list(reduced.size), "image_from": how, "uploaded_by": user_id, "is_ai_generated": False, "label": "PSD 수정본"})
    return {"asset": saved, "psd": {**info, "sha256": sha, "kept": True}, "source": how, "work_size": list(reduced.size), "reduced": long_side > WORK_SIDE}
