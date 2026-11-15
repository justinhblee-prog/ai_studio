"""Pilot service switches (Virtual Try-on, Character, 3D, Video, Marketplace). Global, read-only, for signed-in users."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app import config
from app.assets.routes import current_user

router = APIRouter(prefix="/v1/features", tags=["features"])


class FeatureState(BaseModel):
    enabled: bool
    status: str  # "available" or "pilot_preview" (off: shown as a preview, an administrator can turn it on)


class FeaturesResponse(BaseModel):
    features: dict[str, FeatureState]


@router.get("", response_model=FeaturesResponse, operation_id="getFeatures")
async def get_features(user_id: str = Depends(current_user)):
    return {"features": {name: {"enabled": on, "status": "available" if on else "pilot_preview"}
                         for name in config.FEATURE_FLAGS for on in [config.feature_enabled(name)]}}
