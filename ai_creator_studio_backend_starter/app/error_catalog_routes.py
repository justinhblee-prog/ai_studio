"""R-072: ``GET /v1/error-catalog?lang=ko|en``: the error-code text table, public (no sign-in: the login screen needs it too)."""
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Response

from app import error_catalog

router = APIRouter(tags=["error-catalog"])


@router.get("/v1/error-catalog", operation_id="getErrorCatalog")
async def get_error_catalog(response: Response, lang: Literal["ko", "en"] = "ko") -> dict[str, Any]:
    """Every error ``code`` with its text in the chosen language. ``needs_decision=true`` entries (legal wording) have ``message: null``: show the generic text of the HTTP status instead."""
    response.headers["Cache-Control"] = "public, max-age=300"
    return error_catalog.catalog(lang)
