"""R-046: try-on inputs picked from the workspace's own library ("my library", R-045), turned into short-lived signed addresses.

Why at dispatch time: the job only stores the library ITEM ids. The signed https address is made by the worker right before the provider is
called, lives at most TRYON_INPUT_URL_TTL_SECONDS (hard cap 900) and is never written to the database, a log or a response. A long queue wait
therefore cannot expire it, and a leaked job record does not leak a usable address. Mock jobs never fetch anything, so they use a placeholder
host; a real provider needs PUBLIC_API_BASE_URL (https) and otherwise the dispatch fails closed.
"""
from __future__ import annotations

import time
from typing import Any

from app import config, takedown
from app.assets import store

SIDES = {"model": ("model_image_url", "model_item_id", ("model", "render")),
         "garment": ("garment_image_url", "garment_item_id", ("garment",))}
PLACEHOLDER_BASE = "https://mock.invalid"
MAX_TTL = 900


class TryOnInputError(ValueError):
    def __init__(self, code: str, message: str, status: int = 422):
        super().__init__(message)
        self.code, self.status = code, status


def _item(workspace_id: str, item_id: str):
    from app.workspace_library import _SELECT, _init
    with store._connect() as db:
        store.initialize()
        _init(db)
        return db.execute(_SELECT + " WHERE i.item_id=? AND i.workspace_id=?", (item_id, workspace_id)).fetchone()


def resolve_item(workspace_id: str, item_id: str, allowed_kinds: tuple[str, ...], user_id: str | None = None) -> dict[str, str]:
    """The item's asset and CURRENT version, or TryOnInputError. Checks the workspace, the kind, holds and that the asset still exists."""
    row = _item(workspace_id, item_id)
    if row is None or (user_id is not None and not takedown.visible_to(row["asset_id"], user_id)):
        raise TryOnInputError("TRYON_INPUT_NOT_FOUND", "library item not found", 404)
    if row["kind"] not in allowed_kinds:
        raise TryOnInputError("TRYON_INPUT_KIND", f"this input needs an item of kind {' or '.join(allowed_kinds)}, not {row['kind']}")
    if not str(row["media_type"]).startswith("image/"):
        raise TryOnInputError("TRYON_INPUT_KIND", "try-on inputs must be images")
    versions = store.list_asset_versions(row["asset_id"], workspace_id)
    current = next((v for v in versions if v.get("is_current")), None)
    if current is None:
        raise TryOnInputError("TRYON_INPUT_GONE", "the item's image has no current version", 409)
    return {"asset_id": row["asset_id"], "version_id": current["version_id"], "kind": row["kind"], "origin": row["origin"]}


def sign(asset_id: str, version_id: str, *, base: str) -> tuple[str, int]:
    from app.assets.routes import _version_signature
    ttl = max(30, min(config.TRYON_INPUT_URL_TTL_SECONDS, MAX_TTL))
    expires = int(time.time()) + ttl
    return f"{base}/v1/assets/{asset_id}/versions/{version_id}/preview?expires={expires}&signature={_version_signature(asset_id, version_id, expires)}", expires


def resolve_payload(payload: dict[str, Any], *, for_provider: bool, user_id: str | None = None) -> dict[str, Any]:
    """A COPY of the job payload where every library item id is replaced by a signed address. The stored payload is never changed.
    ``for_provider`` False (validation at creation, mock dispatch) allows the placeholder host; True needs PUBLIC_API_BASE_URL."""
    out = dict(payload)
    workspace_id = payload["workspace_id"]
    for side, (url_key, item_key, kinds) in SIDES.items():
        item_id = payload.get(item_key)
        if not item_id:
            continue
        found = resolve_item(workspace_id, item_id, kinds, user_id)
        base = config.PUBLIC_API_BASE_URL
        if for_provider and not base.startswith("https://"):
            raise TryOnInputError("TRYON_PUBLIC_URL_MISSING", "PUBLIC_API_BASE_URL (https) is not configured", 503)
        out[url_key] = sign(found["asset_id"], found["version_id"], base=base if base.startswith("https://") else PLACEHOLDER_BASE)[0]
    return out


def asset_ids_of(payload: dict[str, Any]) -> list[str]:
    """Asset ids behind the item-picked sides (for the disclosure wording); sides that are plain addresses are not included."""
    ids = []
    for side, (url_key, item_key, kinds) in SIDES.items():
        if payload.get(item_key):
            row = _item(payload.get("workspace_id", ""), payload[item_key])
            if row is not None:
                ids.append(row["asset_id"])
    return ids
