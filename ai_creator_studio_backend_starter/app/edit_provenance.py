"""AI-edit provenance (answer 69 C.7): every asset carries an ordered list of EDITS, and the AI disclosure of what leaves the service is DECIDED from that list.

  edits: [{op, by: "user" | "ai", provider?, at}]      GET /v1/assets/{asset_id}/edits  ->  {asset_id, edits, decision}

Where the list comes from (nothing is stored twice; the asset_provenance trail already has it):
  * ``asset.generated_output_imported`` (an AI provider's job result)   -> {op: "generate" | "ai_edit", by: "ai", provider}   (``ai_marking.kind_for_asset`` decides which)
  * ``asset.photo_steps`` (local steps: crop, canvas, shadow, ...)         -> one {op, by: "user"} per step
  * ``asset.edit`` (explicit record, ``record_edit``: for an AI step of the future, e.g. AI retouch) -> as recorded
  * the same rules for the SOURCE asset a processed copy was made from (``source_asset_id``), so a crop of an AI-assisted picture stays AI-assisted (depth <= MAX_DEPTH).
The decision (``decide``): ``is_ai_generated`` when an AI step created the picture, ``ai_assisted`` when the customer's own picture was changed by an AI step, neither when every edit is the
customer's or local processing (crop, resize, colour, classical background removal, ...). It maps onto the IPTC source types already used for the picture mark (``ai_marking.SOURCE_TYPE``).
THRESHOLDS ARE TEMPORARY: where exactly "assisted" begins (any AI step? only a visible one?) and the wording are the open legal questions Q11-5 / Q11-6; ``decision.status`` says so and this
module takes the strictest reading (ANY AI step makes it assisted) until they are answered.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app import ai_marking, takedown
from app.assets import store
from app.assets.routes import current_user, require_role
from app.ports.asset_bytes import get_asset_bytes_port

router = APIRouter(prefix="/v1/assets", tags=["asset-provenance"])
EVENT_EDIT = "asset.edit"
EVENT_STEPS = "asset.photo_steps"
EVENT_IMPORT = "asset.generated_output_imported"
MAX_DEPTH = 10
STATUS = "temporary_pending_legal_review"            # Q11-5 / Q11-6
AI_OPS = {"generate", "ai_edit", "ai_retouch", "ai_inpaint", "ai_background", "ai_upscale"}
By = Literal["user", "ai"]


def record_edit(workspace_id: str, asset_id: str, op: str, by: By, actor_id: str, provider: str | None = None, version_number: int | None = None) -> None:
    """Add one explicit edit to the asset's provenance trail (used by AI steps; local steps are already recorded by ``asset.photo_steps``)."""
    if by not in ("user", "ai") or not op or len(op) > 40:
        raise ValueError("an edit needs op (<= 40 characters) and by 'user' or 'ai'")
    store.initialize()
    with store._connect() as db:
        db.execute("INSERT INTO asset_provenance(provenance_id, workspace_id, asset_id, version_number, event_type, actor_id, details_json, created_at) VALUES (?,?,?,?,?,?,?,?)",
                   ("ap_edit_" + uuid.uuid4().hex, workspace_id, asset_id, version_number, EVENT_EDIT, actor_id,
                    json.dumps({"op": op, "by": by, **({"provider": provider} if provider else {})}), datetime.now(timezone.utc).isoformat()))


def _rows(asset_id: str) -> list[Any]:
    store.initialize()
    with store._connect() as db:
        return db.execute("SELECT event_type, details_json, created_at FROM asset_provenance WHERE asset_id=? ORDER BY created_at, provenance_id", (asset_id,)).fetchall()


def edits_of(asset_id: str, _depth: int = 0, _seen: frozenset[str] = frozenset()) -> list[dict[str, Any]]:
    """The ordered edits of an asset, the source asset's first. Every item: {op, by, provider?, at}."""
    if _depth > MAX_DEPTH or asset_id in _seen:
        return []
    out: list[dict[str, Any]] = []
    for row in _rows(asset_id):
        details = json.loads(row["details_json"] or "{}")
        at = row["created_at"]
        if row["event_type"] == EVENT_IMPORT:
            kind = ai_marking.kind_for_asset(asset_id)
            if kind is not None:
                item: dict[str, Any] = {"op": "ai_edit" if kind == "edited" else "generate", "by": "ai", "at": at}
                if details.get("provider"):
                    item["provider"] = details["provider"]
                out.append(item)
        elif row["event_type"] == EVENT_STEPS:
            if details.get("source_asset_id"):
                out = edits_of(details["source_asset_id"], _depth + 1, _seen | {asset_id}) + out
            out += [{"op": str(s.get("op", "step")), "by": "user", "at": at} for s in details.get("steps", [])]
        elif row["event_type"] == EVENT_EDIT:
            item = {"op": str(details.get("op", "edit")), "by": "ai" if details.get("by") == "ai" else "user", "at": at}
            if details.get("provider"):
                item["provider"] = details["provider"]
            out.append(item)
    return out


def decide(edits: list[dict[str, Any]]) -> dict[str, Any]:
    """Pure decision from an edit list (no I/O). ``generate`` by AI -> AI-generated; any other AI step -> AI-assisted; otherwise nothing to disclose."""
    ai = [e for e in edits if e.get("by") == "ai"]
    generated = any(e.get("op") == "generate" for e in ai)
    assisted = bool(ai) and not generated
    if generated:
        basis, kind = "an AI step created the picture", "generated"
    elif assisted:
        basis, kind = "an AI step changed the customer's own picture", "edited"
    else:
        basis, kind = "no AI step: every edit is the customer's or local processing" if edits else "no edits recorded", None
    return {"is_ai_generated": generated, "ai_assisted": assisted, "ai_steps": len(ai), "mark_kind": kind,
            "digital_source_type": None if kind is None else ai_marking.DST + ai_marking.SOURCE_TYPE[kind], "basis": basis, "status": STATUS,
            "rule": "strictest reading: ANY AI step on a customer picture makes it AI-assisted; where 'assisted' begins is legal question Q11-5 / Q11-6"}


class EditOut(BaseModel):
    op: str
    by: By
    provider: str | None = None
    at: str


class EditsOut(BaseModel):
    asset_id: str
    edits: list[EditOut]
    decision: dict[str, Any]


@router.get("/{asset_id}/edits", response_model=EditsOut, operation_id="getAssetEdits")
async def get_edits(asset_id: str, user_id: str = Depends(current_user)):
    workspace_id = get_asset_bytes_port().workspace_of(asset_id)
    if not workspace_id or not takedown.visible_to(asset_id, user_id):
        raise HTTPException(status_code=404, detail="Asset not found")
    require_role(workspace_id, user_id, {"owner", "admin", "editor", "viewer"})
    edits = edits_of(asset_id)
    return {"asset_id": asset_id, "edits": edits, "decision": decide(edits)}
