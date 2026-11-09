"""Which generation outputs must be disclosed as AI generated (L-07).

A job output is AI generated when an external generative provider produced it. The built-in ``mock`` provider
returns a placeholder without any model, so it is not. Unknown or missing providers are treated as AI generated:
when in doubt, disclose. Photo Studio's deterministic local adjustments are a different path and carry
``is_ai_generated: false`` in their own manifests.
"""
from __future__ import annotations

from typing import Any

NON_AI_PROVIDERS = frozenset({"mock"})


def is_ai_generated_provider(provider: str | None) -> bool:
    return str(provider or "").strip().lower() not in NON_AI_PROVIDERS


def disclose_job_outputs(listing: dict[str, Any], job: dict[str, Any]) -> dict[str, Any]:
    """Add the disclosure fields to every item of a job's output listing (the job decides, not the item)."""
    flag = is_ai_generated_provider(job.get("provider"))
    for item in listing.get("data", []):
        item["is_ai_generated"] = flag
        item["provider"] = job.get("provider")
        item["model"] = job.get("model")
    return listing
