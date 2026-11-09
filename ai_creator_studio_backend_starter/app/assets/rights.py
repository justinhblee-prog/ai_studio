"""Rights / likeness confirmation recorded when an image is uploaded (L-04).

Nothing here is legal wording. The API only records what the uploader declared and, when
``ASSET_REQUIRE_RIGHTS_CONFIRMATION`` is on (the default), refuses uploads that lack the declaration (D2).
Setting it to 0 keeps old clients working; assets uploaded earlier are never blocked retroactively.
"""
from __future__ import annotations

from typing import Any

from app import config
from app.assets.validation import AssetValidationError

RIGHTS_REQUIRED = "RIGHTS_CONFIRMATION_REQUIRED"
LIKENESS_REQUIRED = "LIKENESS_CONSENT_REQUIRED"


def build_upload_confirmation(rights_confirmed: bool | None, depicts_person: bool | None,
                              likeness_consent: bool | None) -> dict[str, bool] | None:
    """Return the declaration to store, or None when the client sent none of the fields.

    Raises AssetValidationError when enforcement is on and the declaration is missing or incomplete.
    """
    provided = any(v is not None for v in (rights_confirmed, depicts_person, likeness_consent))
    declaration = {
        "rights_confirmed": bool(rights_confirmed),
        "depicts_person": bool(depicts_person),
        "likeness_consent": bool(likeness_consent),
    }
    if config.ASSET_REQUIRE_RIGHTS_CONFIRMATION:
        if not declaration["rights_confirmed"]:
            raise AssetValidationError(RIGHTS_REQUIRED, "Confirm that you hold the rights to use this image before uploading it.")
        if declaration["depicts_person"] and not declaration["likeness_consent"]:
            raise AssetValidationError(LIKENESS_REQUIRED, "Confirm consent of the person shown before uploading this image.")
    return declaration if provided else None


def upload_details(confirmation: dict[str, Any] | None) -> dict[str, Any]:
    """Provenance details of an upload; unchanged from the previous format when nothing was declared."""
    details: dict[str, Any] = {"source": "upload"}
    if confirmation is not None:
        details["rights"] = dict(confirmation)
    return details
