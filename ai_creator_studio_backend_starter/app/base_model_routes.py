"""Lane 2/5: public read routes for the generated base human models (``app/base_models.py``).

  GET /v1/base-models                      -> the choices (sex presets, clothing styles, default colours)
  GET /v1/base-models/{sex}/glb?top_style=&bottom_style=&top=rrggbb&bottom=rrggbb&skin=rrggbb   -> the .glb (model/gltf-binary)

No sign-in: the file is generated from the query alone, holds no user data and no third-party asset, and is deterministic (so it carries an ETag and caches for a day).
Colours are six hex digits WITHOUT '#'. Nothing is stored or logged beyond the normal access log.
"""
from __future__ import annotations

import hashlib
from functools import lru_cache
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Header, Query, Response

from app import base_models

router = APIRouter(tags=["base-models"])
HEX = r"^[0-9a-fA-F]{6}$"
DEFAULTS = {"skin": "e0ac69", "top": "3c5aa0", "bottom": "32323c"}


def _rgb(value: str) -> tuple[int, int, int]:
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


@lru_cache(maxsize=128)
def _build(sex: str, top_style: str, bottom_style: str, skin: str, top: str, bottom: str) -> tuple[bytes, str]:
    data = base_models.build_base_model(sex, top_style, bottom_style, _rgb(skin), _rgb(top), _rgb(bottom))
    return data, '"' + hashlib.sha256(data).hexdigest()[:32] + '"'


@router.get("/v1/base-models", operation_id="listBaseModels")
async def list_base_models(response: Response) -> dict[str, Any]:
    response.headers["Cache-Control"] = "public, max-age=3600"
    return {"sexes": list(base_models.SEXES), "top_styles": list(base_models.TOP_STYLES), "bottom_styles": list(base_models.BOTTOM_STYLES), "default_colors": DEFAULTS,
            "color_format": "six hex digits without '#'", "materials": ["skin", "top", "bottom"],
            "note": "generated stylised placeholder figures: low-poly, no face, no scan, no third-party asset (see each file's node extras)"}


@router.get("/v1/base-models/{sex}/glb", operation_id="getBaseModelGlb", response_class=Response, responses={200: {"content": {"model/gltf-binary": {}}}, 304: {"description": "unchanged"}})
async def get_base_model_glb(sex: Literal["male", "female"], top_style: Literal["tank", "tshirt", "longsleeve"] = "tshirt", bottom_style: Literal["shorts", "pants"] = "pants",
                             skin: Annotated[str, Query(pattern=HEX)] = DEFAULTS["skin"], top: Annotated[str, Query(pattern=HEX)] = DEFAULTS["top"],
                             bottom: Annotated[str, Query(pattern=HEX)] = DEFAULTS["bottom"], if_none_match: Annotated[str | None, Header()] = None) -> Response:
    data, etag = _build(sex, top_style, bottom_style, skin.lower(), top.lower(), bottom.lower())
    headers = {"ETag": etag, "Cache-Control": "public, max-age=86400"}
    if if_none_match == etag:
        return Response(status_code=304, headers=headers)
    return Response(content=data, media_type="model/gltf-binary", headers={**headers, "Content-Disposition": f'inline; filename="base_{sex}.glb"'})
