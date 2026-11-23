"""API contract for the S/M/L fit comparison (``app/ease_map.py``, lane 2 / M4):

  POST /v1/workspaces/{workspace_id}/fit-check   {sex, kind, measurements?, nominal?}  ->  200 {kind, sex, measurements, nominal, sizes:{S,M,L}, recommended, limits, note, engine}

Pure, deterministic geometry on the STYLISED own3d body (no fabric stretch, no AI, no network, nothing stored): for each size the wearing ease per zone (cm, class tight/fitted/regular/loose),
the clearance statistics between garment and body, the share of vertices that would press on the body, and the smallest size with enough room (``recommended``, null when none fits).
The thresholds are PROPOSALS (``limits.source = "proposal"``), not a sizing standard. Behind the same own3d flag as the render job (``RENDER3D_ENABLED``, default OFF -> 409 ``RENDER3D_CLOSED``).
Viewer or above (it reads nothing from the workspace and writes nothing). Counted by the generation rate limit scope ``fit_check`` is NOT used: the call is cheap (about 0.2 s)."""
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app import base_models, config, ease_map
from app.assets.routes import current_user, require_role

router = APIRouter(prefix="/v1/workspaces/{workspace_id}/fit-check", tags=["fit-check"])
ENGINE = "own3d"


class FitCheckIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sex: Literal["male", "female"]
    kind: Literal["top", "bottom", "skirt", "dress", "jacket"]
    measurements: dict[str, float] | None = Field(default=None, max_length=4)
    nominal: dict[str, float] | None = Field(default=None, max_length=3)       # the body size M is made for; default = the preset's own circumferences


@router.post("", response_model=None, operation_id="createFitCheck")
async def fit_check(workspace_id: str, body: FitCheckIn, user_id: str = Depends(current_user)) -> dict[str, Any]:
    require_role(workspace_id, user_id, {"owner", "admin", "editor", "viewer"})
    if not getattr(config, "RENDER3D_ENABLED", False):
        raise HTTPException(status_code=409, detail={"code": "RENDER3D_CLOSED", "message": "The 3D render job is not open yet."})
    try:
        if body.measurements:
            base_models._fit_measurements(base_models.PRESETS[body.sex], body.measurements)
        if body.nominal:
            unknown = set(body.nominal) - set(ease_map.CIRC_KEYS)
            low, high = 40.0, 200.0
            if unknown or any(not low <= v <= high for v in body.nominal.values()):
                raise ValueError(f"nominal takes only {', '.join(ease_map.CIRC_KEYS)} between {low:g} and {high:g} cm")
        report = ease_map.compare(body.kind, body.sex, body.measurements, body.nominal)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"code": "FIT_CHECK_INVALID", "message": str(exc)}) from exc
    return {**report, "engine": ENGINE}
