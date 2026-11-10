"""Authenticated, workspace-scoped private 3D asset API."""
from __future__ import annotations

import hashlib
import hmac
import time
from pathlib import Path

from app.viewer_responses import AssetListResponse, AssetVersionListResponse, AssetRecordResponse, AssetVersionResponse, AssetVersionMutationResponse
from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, Request, UploadFile
import httpx
from pydantic import BaseModel, Field
from starlette.responses import StreamingResponse
from app.private_file_response import PrivateFileError, open_private_file_response
from app.ports.asset_bytes import get_asset_bytes_port
from app.ports.assets import get_asset_metadata_port
from app.ports.workspace import get_workspace_port
from app.repo_errors import raise_http

from app import config
from app.assets.store import (AssetVersionIntegrityError, audit_workspace_assets, create_asset_relation, create_asset_version, delete_asset, get_asset, list_asset_provenance, list_asset_relations, list_asset_versions, list_assets, restore_asset_version, save_asset, storage_path, workspace_for_asset, workspace_role, get_asset_version_record)
from app.assets.rights import build_upload_confirmation
from app.assets.validation import AssetValidationError, validate_asset_upload, validate_gltf_upload, validate_image_upload

router = APIRouter(prefix="/v1/assets", tags=["assets"])


# Paths a user may call without having accepted the current legal documents: accepting them, seeing who they are,
# withdrawing consent, requesting deletion, and the operator diagnostics (which are gated by their own operator allow-list).
LEGAL_EXEMPT_PREFIXES = ("/v1/auth/me", "/v1/me/legal-status", "/v1/me/legal-acceptances", "/v1/me/consents",
                         "/v1/me/deletion-requests", "/internal/")


def current_user(authorization: str | None = Header(default=None), request: Request = None) -> str:
    """Authenticate the bearer token; also tells the access log who the actor is (request.state), if a request is given."""
    user_id = _authenticate_once(request, authorization)
    if request is not None:
        request.state.actor = user_id
        if config.LEGAL_REQUIRE_ACCEPTANCE and not request.url.path.startswith(LEGAL_EXEMPT_PREFIXES):
            from app.legal import _initialize, _status_for
            _initialize()
            if not _status_for(user_id)["accepted"]:
                raise HTTPException(status_code=403, detail={"code": "LEGAL_ACCEPTANCE_REQUIRED",
                                                             "message": "Accept the current legal documents to continue."})
    return user_id


def _authenticate_once(request: Request | None, authorization: str | None) -> str:
    """Authenticate once per request (the visibility guard and the route's own current_user both need the identity)."""
    if request is None:
        return _authenticate(authorization)
    cached = getattr(request.state, "_acs_auth", None)
    if cached is not None and cached[0] == authorization:
        return cached[1]
    user_id = _authenticate(authorization)
    request.state._acs_auth = (authorization, user_id)
    return user_id


def asset_visibility(request: Request, authorization: str | None = Header(default=None)) -> None:
    """L-08: an asset on hold is invisible to everyone but its owner (and to the owner too once removed). Applies to every
    route with an asset_id in its path; the status route decides for itself. Signed-URL routes carry no bearer token:
    without an identity a held asset is never shown, so links issued before a hold stop working."""
    asset_id = request.path_params.get("asset_id")
    if asset_id and not request.url.path.endswith("/takedown"):
        from app import takedown
        user_id = _authenticate_once(request, authorization) if authorization else None
        if not takedown.visible_to(asset_id, user_id):
            raise HTTPException(status_code=404, detail="Asset not found")


router.dependencies.append(Depends(asset_visibility))


def _authenticate(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Bearer authentication is required")
    token = authorization[7:].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Bearer authentication is required")

    supabase_url = getattr(config, "SUPABASE_URL", "").strip().rstrip("/")
    supabase_key = getattr(config, "SUPABASE_ANON_KEY", "").strip()
    if supabase_url or supabase_key:
        if not supabase_url or not supabase_key:
            raise HTTPException(status_code=503, detail="Supabase Auth validation is not fully configured")
        try:
            response = httpx.get(
                f"{supabase_url}/auth/v1/user",
                headers={"apikey": supabase_key, "Authorization": f"Bearer {token}"},
                timeout=5.0,
            )
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=503, detail="Supabase Auth validation is temporarily unavailable") from exc
        if response.status_code in {401, 403}:
            raise HTTPException(status_code=401, detail="Invalid or expired bearer token")
        if response.status_code != 200:
            raise HTTPException(status_code=503, detail="Supabase Auth validation failed")
        try:
            payload = response.json()
            user_id = payload.get("id") if isinstance(payload, dict) else None
        except (TypeError, ValueError):
            user_id = None
        if not isinstance(user_id, str) or not user_id:
            raise HTTPException(status_code=401, detail="Supabase Auth returned no user identity")
        return user_id

    # Local-only compatibility mode. Production must configure Supabase Auth;
    # static bearer mappings are intentionally ignored when Supabase is set.
    user_id = config.asset_api_tokens().get(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid bearer token")
    return user_id


def require_role(workspace_id: str, user_id: str, allowed: set[str]) -> str:
    role = get_workspace_port().role(workspace_id, user_id)
    if role is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    if role not in allowed:
        raise HTTPException(status_code=403, detail="Insufficient workspace role")
    return role


def _store_failure(exc: Exception, message: str):
    """Typed repository errors keep their mapped status; anything unexpected keeps the legacy fixed 500 text."""
    from app.repo_errors import map_exception
    if isinstance(exc, HTTPException) or map_exception(exc).status != 500:
        raise_http(exc)
    raise HTTPException(status_code=500, detail=message) from exc


def _signature(asset_id: str, expires: int) -> str:
    secret = config.ASSET_SIGNING_SECRET.encode("utf-8")
    if len(secret) < 32:
        raise HTTPException(status_code=503, detail="Asset preview signing is not configured")
    message = f"{asset_id}:{expires}".encode("utf-8")
    return hmac.new(secret, message, hashlib.sha256).hexdigest()


def _version_signature(asset_id: str, version_id: str, expires: int) -> str:
    secret = config.ASSET_SIGNING_SECRET.encode("utf-8")
    if len(secret) < 32:
        raise HTTPException(status_code=503, detail="Asset version preview signing is not configured")
    message = f"{asset_id}:{version_id}:{expires}".encode("utf-8")
    return hmac.new(secret, message, hashlib.sha256).hexdigest()


def _verified_version_path(asset_id: str, workspace_id: str, version_id: str):
    version = get_asset_bytes_port().version_record(asset_id, workspace_id, version_id)
    if not version:
        raise HTTPException(status_code=404, detail="Asset version not found")
    storage_key = version.get("storage_key")
    if not storage_key or Path(storage_key).name != storage_key:
        raise HTTPException(status_code=409, detail="Asset version storage reference is invalid")
    root = config.ASSET_STORAGE_DIR.resolve()
    path = (root / storage_key).resolve()
    if path.parent != root or not path.is_file():
        raise HTTPException(status_code=409, detail="Asset version file is missing")
    digest = hashlib.sha256()
    size = 0
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                size += len(chunk)
                digest.update(chunk)
    except OSError as exc:
        raise HTTPException(status_code=409, detail="Asset version file cannot be read") from exc
    if size != int(version["size_bytes"]) or not hmac.compare_digest(digest.hexdigest(), version["checksum_sha256"]):
        raise HTTPException(status_code=409, detail="Asset version integrity check failed")
    return version, path


@router.post("", status_code=201, response_model=AssetRecordResponse)
async def upload_asset(workspace_id: str = Form(min_length=2, max_length=64), file: UploadFile = File(...), user_id: str = Depends(current_user)):
    require_role(workspace_id, user_id, {"owner", "admin", "editor"})
    filename = Path(file.filename or "asset").name
    content = await file.read(config.ASSET_MAX_UPLOAD_BYTES + 1)
    await file.close()
    if len(content) > config.ASSET_MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Asset exceeds upload size limit")
    try:
        validated = validate_gltf_upload(filename, content, max_bytes=config.ASSET_MAX_UPLOAD_BYTES)
    except AssetValidationError as exc:
        raise HTTPException(status_code=422, detail={"code": exc.code, "message": str(exc)}) from exc
    try:
        return get_asset_bytes_port().save(workspace_id, user_id, filename, content, validated)
    except Exception as exc:
        _store_failure(exc, "Asset could not be stored")


@router.post("/images", status_code=201, response_model=AssetRecordResponse)
async def upload_image_asset(workspace_id: str = Form(min_length=2, max_length=64),
                             file: UploadFile = File(...), user_id: str = Depends(current_user),
                             rights_confirmed: bool | None = Form(default=None),
                             depicts_person: bool | None = Form(default=None),
                             likeness_consent: bool | None = Form(default=None)):
    """Store a validated source image for the independent Photo Engine workflow.

    The rights fields are recorded in the asset provenance and, when confirmed, in upload_rights_confirmations (D2).
    ``rights_confirmed=true`` is required unless ASSET_REQUIRE_RIGHTS_CONFIRMATION is explicitly switched off (L-04).
    """
    require_role(workspace_id, user_id, {"owner", "admin", "editor"})
    filename = Path(file.filename or "image").name
    content = await file.read(config.ASSET_MAX_UPLOAD_BYTES + 1)
    await file.close()
    if len(content) > config.ASSET_MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Asset exceeds upload size limit")
    try:
        validated = validate_image_upload(filename, content, max_bytes=config.ASSET_MAX_UPLOAD_BYTES)
    except AssetValidationError as exc:
        raise HTTPException(status_code=422, detail={"code": exc.code, "message": str(exc)}) from exc
    try:
        confirmation = build_upload_confirmation(rights_confirmed, depicts_person, likeness_consent)
    except AssetValidationError as exc:
        raise HTTPException(status_code=422, detail={"code": exc.code, "message": str(exc)}) from exc
    try:
        return get_asset_bytes_port().save(workspace_id, user_id, filename, content, validated, upload_confirmation=confirmation)
    except Exception as exc:
        _store_failure(exc, "Image asset could not be stored")


@router.get("", response_model=AssetListResponse)
async def assets(workspace_id: str = Query(min_length=2, max_length=64),
                 kind: str = Query(default="all", pattern="^(all|model|image)$"),
                 user_id: str = Depends(current_user)):
    try:
        listing = get_asset_metadata_port().list(workspace_id, user_id, kind)
    except Exception as exc:
        raise_http(exc)
    from app import takedown
    listing["items"] = takedown.filter_listing(listing["items"], user_id)
    return listing


@router.get("/integrity")
async def asset_integrity_audit(
    workspace_id: str = Query(min_length=2, max_length=64),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user_id: str = Depends(current_user),
):
    """Check private stored bytes against upload-time size and SHA-256 metadata."""
    try:
        return get_asset_bytes_port().audit(workspace_id, user_id, limit, offset)
    except Exception as exc:
        raise_http(exc)


class AssetPreviewUrlResponse(BaseModel):
    url: str
    expires_at: int
    asset_id: str | None = None
    version_id: str | None = None


class AssetRelationRequest(BaseModel):
    target_asset_id: str = Field(min_length=4, max_length=80)
    relation_type: str


@router.post("/{asset_id}/versions", status_code=201, response_model=AssetVersionMutationResponse)
async def upload_asset_version(asset_id: str, file: UploadFile = File(...), user_id: str = Depends(current_user),
                               rights_confirmed: bool | None = Form(default=None), depicts_person: bool | None = Form(default=None),
                               likeness_consent: bool | None = Form(default=None)):
    """New version of an asset. A new version of an IMAGE asset is a new photo, so it needs the same rights declaration as
    POST /v1/assets/images (D2); 3D model versions are unaffected."""
    try:
        port = get_asset_bytes_port()
        workspace_id = port.workspace_of(asset_id)
        if not workspace_id:
            raise HTTPException(status_code=404, detail="Asset not found")
        require_role(workspace_id, user_id, {"owner", "admin", "editor"})
        current_asset = get_asset_metadata_port().get(asset_id, user_id)
    except Exception as exc:
        raise_http(exc)
    filename = Path(file.filename or "asset").name
    content = await file.read(config.ASSET_MAX_UPLOAD_BYTES + 1)
    await file.close()
    if len(content) > config.ASSET_MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Asset exceeds upload size limit")
    try:
        validated = validate_asset_upload(filename, content, max_bytes=config.ASSET_MAX_UPLOAD_BYTES)
        if (validated.media_type.startswith("image/")) != (current_asset["asset_kind"] == "image"):
            raise AssetValidationError("ASSET_KIND_MISMATCH", "A new version must keep the original asset kind.")
        confirmation = (build_upload_confirmation(rights_confirmed, depicts_person, likeness_consent)
                        if validated.media_type.startswith("image/") else None)
    except AssetValidationError as exc:
        raise HTTPException(status_code=422, detail={"code": exc.code, "message": str(exc)}) from exc
    try:
        if confirmation is not None:
            return port.save_version(asset_id, user_id, filename, content, validated, upload_confirmation=confirmation)
        return port.save_version(asset_id, user_id, filename, content, validated)
    except Exception as exc:
        _store_failure(exc, "Asset version could not be stored")


@router.post("/{asset_id}/versions/{version_id}/restore", status_code=201, response_model=AssetVersionMutationResponse)
async def restore_asset_version_route(asset_id: str, version_id: str, user_id: str = Depends(current_user)):
    try:
        return get_asset_bytes_port().restore(asset_id, user_id, version_id)
    except Exception as exc:
        raise_http(exc)


@router.get("/{asset_id}/versions", response_model=AssetVersionListResponse)
async def asset_versions(asset_id: str, user_id: str = Depends(current_user)):
    try:
        return get_asset_metadata_port().versions(asset_id, user_id)
    except Exception as exc:
        raise_http(exc)


@router.get("/{asset_id}/provenance")
async def asset_provenance(
    asset_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user_id: str = Depends(current_user),
):
    try:
        return get_asset_metadata_port().provenance(asset_id, user_id, limit, offset)
    except Exception as exc:
        raise_http(exc)


@router.get("/{asset_id}/rights-confirmation")
async def asset_rights_confirmation(asset_id: str, user_id: str = Depends(current_user)):
    """D2: whether the uploader confirmed the rights to this image. Assets uploaded before enforcement read as unconfirmed."""
    from app.assets.store import get_rights_confirmation
    workspace_id = get_asset_bytes_port().workspace_of(asset_id)
    if not workspace_id:
        raise HTTPException(status_code=404, detail="Asset not found")
    require_role(workspace_id, user_id, {"owner", "admin", "editor", "viewer"})
    try:
        record = get_rights_confirmation(asset_id, workspace_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Asset not found") from None
    return {"asset_id": asset_id, "status": "confirmed" if record else "unconfirmed", **(record or {})}


@router.get("/{asset_id}/relations")
async def asset_relations(asset_id: str, user_id: str = Depends(current_user)):
    try:
        return get_asset_metadata_port().relations(asset_id, user_id)
    except Exception as exc:
        raise_http(exc)


@router.post("/{asset_id}/relations", status_code=201)
async def add_asset_relation(asset_id: str, body: AssetRelationRequest, user_id: str = Depends(current_user)):
    try:
        return get_asset_metadata_port().add_relation(asset_id, user_id, body.target_asset_id, body.relation_type)
    except Exception as exc:
        raise_http(exc)


@router.get("/{asset_id}", response_model=AssetRecordResponse)
async def asset_detail(asset_id: str, user_id: str = Depends(current_user)):
    try:
        return get_asset_metadata_port().get(asset_id, user_id)
    except Exception as exc:
        raise_http(exc)


@router.post("/{asset_id}/preview-url", response_model=AssetPreviewUrlResponse)
async def preview_url(asset_id: str, user_id: str = Depends(current_user)):
    try:
        get_asset_metadata_port().get(asset_id, user_id)  # 404 for unknown asset / non-member
    except Exception as exc:
        raise_http(exc)
    expires = int(time.time()) + max(30, min(config.ASSET_PREVIEW_TTL_SECONDS, 900))
    signature = _signature(asset_id, expires)
    return {"url": f"/v1/assets/{asset_id}/preview?expires={expires}&signature={signature}", "expires_at": expires}


@router.post("/{asset_id}/versions/{version_id}/preview-url", response_model=AssetPreviewUrlResponse)
async def create_asset_version_preview_url(asset_id: str, version_id: str,
                                           user_id: str = Depends(current_user)):
    workspace_id = get_asset_bytes_port().workspace_of(asset_id)
    if not workspace_id:
        raise HTTPException(status_code=404, detail="Asset not found")
    require_role(workspace_id, user_id, {"owner", "admin", "editor", "viewer"})
    _verified_version_path(asset_id, workspace_id, version_id)
    expires = int(time.time()) + max(30, min(config.ASSET_PREVIEW_TTL_SECONDS, 900))
    signature = _version_signature(asset_id, version_id, expires)
    return {"url": f"/v1/assets/{asset_id}/versions/{version_id}/preview?expires={expires}&signature={signature}",
            "expires_at": expires, "asset_id": asset_id, "version_id": version_id}


@router.get("/{asset_id}/versions/{version_id}/preview-content", response_class=StreamingResponse, responses={200: {"description": "Authenticated immutable AssetVersion bytes", "content": {"application/octet-stream": {"schema": {"type": "string", "format": "binary"}}}}})
async def preview_asset_version_content(asset_id: str, version_id: str, user_id: str = Depends(current_user)):
    """Stream an immutable AssetVersion only while the caller remains a workspace member."""
    workspace_id = get_asset_bytes_port().workspace_of(asset_id)
    if not workspace_id:
        raise HTTPException(status_code=404, detail="Asset not found")
    require_role(workspace_id, user_id, {"owner", "admin", "editor", "viewer"})
    version, path = _verified_version_path(asset_id, workspace_id, version_id)
    try:
        return open_private_file_response(path, media_type=version["media_type"],
            expected_size=int(version["size_bytes"]), expected_sha256=version["checksum_sha256"])
    except PrivateFileError as exc:
        raise HTTPException(status_code=409, detail="Asset version file failed descriptor integrity validation") from exc


@router.get("/{asset_id}/versions/{version_id}/preview")
async def preview_asset_version(asset_id: str, version_id: str, expires: int, signature: str):
    now = int(time.time())
    if expires < now or expires > now + 901:
        raise HTTPException(status_code=403, detail="Asset version preview URL expired or invalid")
    expected = _version_signature(asset_id, version_id, expires)
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=403, detail="Invalid asset version preview signature")
    workspace_id = get_asset_bytes_port().workspace_of(asset_id)
    if not workspace_id:
        raise HTTPException(status_code=404, detail="Asset not found")
    version, path = _verified_version_path(asset_id, workspace_id, version_id)
    try:
        return open_private_file_response(path, media_type=version["media_type"],
            expected_size=int(version["size_bytes"]), expected_sha256=version["checksum_sha256"])
    except PrivateFileError as exc:
        raise HTTPException(status_code=409, detail="Asset version file failed descriptor integrity validation") from exc


@router.get("/{asset_id}/preview")
async def preview_asset(asset_id: str, expires: int, signature: str):
    now = int(time.time())
    if expires < now or expires > now + 901:
        raise HTTPException(status_code=403, detail="Preview URL expired or invalid")
    expected = _signature(asset_id, expires)
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=403, detail="Preview URL expired or invalid")
    path = get_asset_bytes_port().current_file(asset_id)
    if not path:
        raise HTTPException(status_code=404, detail="Asset not found")
    media = {".glb": "model/gltf-binary", ".gltf": "model/gltf+json",
             ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
             ".webp": "image/webp"}.get(path.suffix.lower())
    if media is None:
        raise HTTPException(status_code=415, detail="Unsupported stored asset media type")
    try:
        return open_private_file_response(path, media_type=media, filename=path.name)
    except PrivateFileError as exc:
        raise HTTPException(status_code=409, detail="Asset preview file is not safely readable") from exc


@router.delete("/{asset_id}", status_code=204)
async def remove_asset(asset_id: str, user_id: str = Depends(current_user)):
    from app import takedown
    if takedown.state_of(asset_id) is not None:   # L-08: the owner cannot erase content that is under a report
        raise HTTPException(status_code=409, detail={"code": "TAKEDOWN_ACTIVE", "message": "This asset is under review and cannot be deleted."})
    try:
        get_asset_metadata_port().delete(asset_id, user_id)
    except Exception as exc:
        raise_http(exc)
    return None
