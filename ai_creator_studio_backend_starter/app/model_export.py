"""E-05: export a stored 3D model (.glb) as a download that carries its own provenance.

  GET /v1/assets/{asset_id}/versions/{version_id}/export      editor or above; the immutable version, checked against its recorded size and SHA-256 before anything is sent

The file that is sent is the stored GLB with ONE addition: ``asset.extras.acs_export`` (glTF's own place for application data, ignored by every viewer that does not know it). It records
``source_sha256`` (the SHA-256 of the stored file this was made from), the asset and version ids, the export time, and an ``ai_disclosure`` block derived from the asset's provenance (an AI
provider's result is marked, an upload, local processing and the built-in mock are not; the wording comes from the same settings as the picture mark, the final legal wording is pending).
Geometry, materials, textures and every other part of the file are left exactly as they were. The stored file never changes. The response carries the SHA-256 of the file that is SENT
(``ETag`` / ``X-Content-SHA256``) and the export is written to the asset's provenance (``asset.exported``: who, which version, both hashes). Nothing leaves the server by any other route.
USDZ is not produced (it needs a converter that is not approved); only .glb binaries are exported.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response

from app import config, takedown
from app.assets import store
from app.assets.routes import _verified_version_path, current_user, require_role
from app.assets.validation import AssetValidationError, validate_gltf_upload
from app.glb_tools import GlbError, build_glb, parse_glb
from app.ports.asset_bytes import get_asset_bytes_port

router = APIRouter(prefix="/v1/assets", tags=["asset-export"])
SCHEMA = "acs-3d-export.v1"
EVENT = "asset.exported"
GLB = "model/gltf-binary"


def _disclosure(kind: str | None) -> dict[str, Any]:
    if kind is None:
        return {"is_ai_generated": False, "digital_source_type": None, "text": None}
    from app import ai_marking
    return {"is_ai_generated": True, "digital_source_type": ai_marking.DST + ai_marking.SOURCE_TYPE.get(kind, ai_marking.SOURCE_TYPE["unknown"]), "text": ai_marking.text_for(kind)}


def build_export(glb: bytes, *, asset_id: str, version_id: str, version_number: int | None, source_sha256: str, ai_kind: str | None, now: datetime | None = None) -> bytes:
    """The stored GLB plus the ``acs_export`` block. Raises GlbError for a file that cannot be rewritten (external buffers are already refused at upload)."""
    doc, binary = parse_glb(glb)
    asset = dict(doc.get("asset") or {"version": "2.0"})
    extras = dict(asset.get("extras") or {})
    extras["acs_export"] = {"schema": SCHEMA, "generator": "AI Creator Studio", "asset_id": asset_id, "version_id": version_id, "version_number": version_number,
                            "source_sha256": source_sha256, "exported_at": (now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                            "ai_disclosure": _disclosure(ai_kind),
                            "note": "This file equals the stored file except for this block. source_sha256 is the SHA-256 of the stored file."}
    asset["extras"] = extras
    return build_glb({**doc, "asset": asset}, bytes(binary))


def _record(workspace_id: str, asset_id: str, version_number: int | None, user_id: str, details: dict[str, Any]) -> None:
    store.initialize()
    with store._connect() as db:
        db.execute("""INSERT INTO asset_provenance(provenance_id, workspace_id, asset_id, version_number, event_type, actor_id, details_json, created_at) VALUES (?,?,?,?,?,?,?,?)""",
                   ("ap_exp_" + uuid.uuid4().hex, workspace_id, asset_id, version_number, EVENT, user_id, json.dumps(details, ensure_ascii=False), datetime.now(timezone.utc).isoformat()))


@router.get("/{asset_id}/versions/{version_id}/export", response_class=Response, operation_id="exportAssetVersionGlb",
            responses={200: {"description": "The stored .glb with its provenance block", "content": {GLB: {}}}})
async def export_asset_version(asset_id: str, version_id: str, user_id: str = Depends(current_user)):
    workspace_id = get_asset_bytes_port().workspace_of(asset_id)
    if not workspace_id or not takedown.visible_to(asset_id, user_id):
        raise HTTPException(status_code=404, detail="Asset not found")
    require_role(workspace_id, user_id, {"owner", "admin", "editor"})
    from app import rate_limit    # R-067
    rate_limit.check("download", user_id, workspace_id)
    version, path = _verified_version_path(asset_id, workspace_id, version_id)
    if version.get("media_type") != GLB:
        raise HTTPException(status_code=422, detail={"code": "EXPORT_NOT_GLB", "message": "Only .glb 3D models can be exported."})
    source = path.read_bytes()
    from app import ai_marking
    try:
        out = build_export(source, asset_id=asset_id, version_id=version_id, version_number=version.get("version_number"), source_sha256=version["checksum_sha256"],
                           ai_kind=ai_marking.kind_for_asset(asset_id))
        validate_gltf_upload("export.glb", out, max_bytes=config.ASSET_MAX_UPLOAD_BYTES * 2)
    except (GlbError, AssetValidationError) as exc:
        raise HTTPException(status_code=422, detail={"code": "EXPORT_FAILED", "message": "The model could not be prepared for export."}) from exc
    digest = hashlib.sha256(out).hexdigest()
    _record(workspace_id, asset_id, version.get("version_number"), user_id, {"format": "glb", "version_id": version_id, "source_sha256": version["checksum_sha256"], "export_sha256": digest,
                                                                          "bytes": len(out), "schema": SCHEMA})
    stem = str(store.get_asset(asset_id, workspace_id).get("original_filename") or "model").rsplit(".", 1)[0]
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in stem)[:80] or "model"
    return Response(content=out, media_type=GLB, headers={"Content-Disposition": f'attachment; filename="{safe}-export.glb"', "ETag": f'"{digest}"', "X-Content-SHA256": digest,
                                                          "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})
