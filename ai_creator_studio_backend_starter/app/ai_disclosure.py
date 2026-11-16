"""Which generation outputs must be disclosed as AI generated (L-07).

A job output is AI generated when an external generative provider produced it. The built-in ``mock`` provider
returns a placeholder without any model, so it is not. Unknown or missing providers are treated as AI generated:
when in doubt, disclose. Photo Studio's deterministic local adjustments are a different path and carry
``is_ai_generated: false`` in their own manifests.
"""
from __future__ import annotations

import json
import re
from typing import Any

NON_AI_PROVIDERS = frozenset({"mock"})


def is_ai_generated_provider(provider: str | None) -> bool:
    return str(provider or "").strip().lower() not in NON_AI_PROVIDERS


ASSET_IN_URL = re.compile(r"/v1/assets/([A-Za-z0-9_-]+)/")


def input_source_of_job(job: dict[str, Any]) -> str:
    """Where the pictures a job was made from came from (reply 11 A): ``uploaded`` (the customer's own photos), ``platform_library_ai`` (copies of
    the platform library's AI-made models / clothes, or a mix that includes one) or ``unknown`` (an input is not one of our assets, or cannot
    be traced). The result of a job is always AI-edited; this only decides the wording: AI-edited (own photos) vs AI-generated (library AI)."""
    payload = job.get("payload") or {}
    urls = [payload.get("model_image_url"), payload.get("garment_image_url")]
    ids = [m.group(1) for u in urls if isinstance(u, str) for m in [ASSET_IN_URL.search(u)] if m]
    try:   # R-046: sides picked from "my library" are traced through their item
        from app import tryon_inputs
        ids += tryon_inputs.asset_ids_of(payload)
        picked = sum(1 for k in ("model_item_id", "garment_item_id") if payload.get(k))
    except Exception:  # noqa: BLE001
        return "unknown"
    if not ids or len(ids) < sum(1 for u in urls if u) + picked:
        return "unknown"
    try:
        from app.assets import store
        store.initialize()
        kinds = []
        with store._connect() as db:
            for asset_id in ids:
                row = db.execute("SELECT details_json FROM asset_provenance WHERE asset_id=? AND version_number=1 ORDER BY created_at LIMIT 1",
                                 (asset_id,)).fetchone()
                if row is None:
                    return "unknown"
                details = json.loads(row["details_json"] or "{}")
                kinds.append("platform_library_ai" if details.get("source") == "library" and details.get("is_ai_generated") else "uploaded")
    except Exception:  # noqa: BLE001 - disclosure wording must never break the output listing
        return "unknown"
    return "uploaded" if all(k == "uploaded" for k in kinds) else "platform_library_ai"


def disclose_job_outputs(listing: dict[str, Any], job: dict[str, Any]) -> dict[str, Any]:
    """Add the disclosure fields to every item of a job's output listing (the job decides, not the item)."""
    flag = is_ai_generated_provider(job.get("provider"))
    source = input_source_of_job(job)
    for item in listing.get("data", []):
        item["input_source"] = source
        item["is_ai_generated"] = flag
        item["provider"] = job.get("provider")
        item["model"] = job.get("model")
    return listing
