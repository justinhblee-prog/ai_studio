"""Image protection helpers (R-035): who may fetch a signed image link, and how images are labelled for the browser.

This blocks the EASY ways to take an image (opening the address directly, embedding it in another site, caching it). It cannot stop
someone from photographing or capturing what the browser shows, and a determined script can send forged Origin/Referer headers; the
real protection is the short-lived signed link plus authentication and role checks on everything that hands out a file.
"""
from __future__ import annotations

from urllib.parse import urlsplit

from fastapi import HTTPException, Request

from app import config

# Every image response: never stored by browsers or proxies, shown in the page (not offered as a file), no type sniffing.
IMAGE_HEADERS = {"Cache-Control": "private, no-store", "Content-Disposition": "inline", "X-Content-Type-Options": "nosniff"}


def _origin_of(value: str | None) -> str | None:
    if not value:
        return None
    parts = urlsplit(value.strip())
    return f"{parts.scheme}://{parts.netloc}" if parts.scheme and parts.netloc else None


def check_embed_origin(request: Request) -> None:
    """403 unless the request comes from an allowed page. Applies only when allowed origins are configured (APP_CORS_ORIGINS) and
    PREVIEW_REQUIRE_ORIGIN is on. A request with neither Origin nor Referer (an address typed into the browser, a script, a page
    that sends no referrer) is refused as well as one from another site."""
    allowed = config.PREVIEW_ALLOWED_ORIGINS
    if not allowed or not config.PREVIEW_REQUIRE_ORIGIN:
        return
    candidate = _origin_of(request.headers.get("origin")) or _origin_of(request.headers.get("referer"))
    if candidate is None or candidate.rstrip("/") not in allowed:
        raise HTTPException(status_code=403, detail="Images can only be loaded from this application")
