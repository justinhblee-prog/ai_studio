"""Versioned, evidence-backed Provider/Model/Capability registry (PoC static registry).

Registry entries are deliberately conservative. FASHN is documented but has not
passed a live/sandbox contract test in this repository, so production dispatch is
blocked. Mock is available only for flow tests and never represents image output.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any

REGISTRY_VERSION = "2026-11-02.1"

@dataclass(frozen=True)
class CapabilityRecord:
    provider_id: str
    model_id: str
    capability_key: str
    input_schema_version: str
    output_schema_version: str
    verification_status: str
    status: str
    supports_async: bool
    supports_status_query: bool
    supports_cancel: bool
    supports_webhook: bool
    idempotency_support: str
    production_eligible: bool
    evidence_ref: tuple[str, ...]
    notes: str

_RECORDS = (
    CapabilityRecord("mock", "mock-tryon", "TRY_ON_IMAGE", "try-on.v1", "image-manifest.v1",
        "CONTRACT_TESTED", "ACTIVE", True, True, False, False, "NONE", False,
        ("repository:tests/test_api.py",), "Flow-only adapter; no image generation."),
    CapabilityRecord("fashn", "tryon-v1.6", "TRY_ON_IMAGE", "try-on.v1", "image-manifest.v1",
        "DOCUMENTED", "PENDING_CONTRACT_TEST", True, True, False, True, "NOT_DOCUMENTED", False,
        ("https://docs.fashn.ai/api-overview/api-fundamentals",),
        "Official API docs reviewed; live/sandbox contract, rights and usage evidence pending."),
    CapabilityRecord("fashn", "tryon-max", "TRY_ON_IMAGE", "try-on.v1", "image-manifest.v1",
        "DOCUMENTED", "PENDING_CONTRACT_TEST", True, True, False, True, "NOT_DOCUMENTED", False,
        ("https://docs.fashn.ai/api-overview/api-fundamentals",),
        "Official API docs reviewed; live/sandbox contract, rights and usage evidence pending."),
)

# What each provider does with the photos we send (R-037 / reply 14). Taken from the provider's public documentation read on 2026-11-15 and NOT
# verified by a live call or by a signed agreement: every entry must keep "terms_check_required" until the provider's terms are reviewed.
PROVIDER_DATA_POLICY = {
    "fashn": {
        "trains_on_customer_content": False,          # documentation: customer content is not used for training unless opted in by separate agreement
        "input_retention": "base64 input is deleted after processing (within a day); URL inputs leave only the URL in the request log",
        "output_retention": "CDN output is deleted after 3 days (return_base64 output expires after 60 minutes): copy the result at once",
        "request_log_deletion": "request records are not deleted automatically and there is no deletion API: ask the provider by e-mail",
        "source": "https://docs.fashn.ai/ (read 2026-11-15)",
        "terms_check_required": True,
    },
}


def data_policy(provider_id: str) -> dict[str, Any]:
    """The provider's data handling facts, or an explicit 'unknown' record (never an empty answer that could read as 'safe')."""
    found = PROVIDER_DATA_POLICY.get(str(provider_id).lower())
    return dict(found) if found else {"trains_on_customer_content": None, "terms_check_required": True,
                                      "note": "No data-handling facts recorded for this provider: do not enable it before they are."}


def list_capabilities() -> list[dict[str, Any]]:
    return [{**asdict(item), "evidence_ref": list(item.evidence_ref)} for item in _RECORDS]

def find_capability(provider_id: str, model_id: str, capability_key: str = "TRY_ON_IMAGE") -> CapabilityRecord | None:
    return next((r for r in _RECORDS if r.provider_id == provider_id and r.model_id == model_id
                 and r.capability_key == capability_key), None)

class ProviderPolicyError(ValueError):
    def __init__(self, code: str, message: str, status_code: int = 503):
        super().__init__(message); self.code = code; self.status_code = status_code

def resolve_manual(provider_id: str, model_id: str, *, purpose: str = "production") -> CapabilityRecord:
    record = find_capability(provider_id, model_id)
    if record is None:
        raise ProviderPolicyError("UNSUPPORTED_CAPABILITY", "Selected provider/model does not support TRY_ON_IMAGE.", 422)
    if record.status == "SUSPENDED":
        raise ProviderPolicyError("PROVIDER_SUSPENDED", "Selected provider/model is suspended.")
    if record.verification_status in {"UNVERIFIED", "SUSPENDED"}:
        raise ProviderPolicyError("CAPABILITY_NOT_VERIFIED", "Selected capability is not verified.")
    if purpose == "production" and not record.production_eligible:
        raise ProviderPolicyError("PROVIDER_NOT_PRODUCTION_READY",
            "Selected provider/model has not completed the required contract, rights and live verification gates.")
    return record

def resolve_routing(mode: str, provider_id: str, model_id: str) -> CapabilityRecord:
    mode = mode.upper()
    if mode == "AUTO":
        # AUTO scoring/fallback weights are explicitly awaiting PO approval.
        raise ProviderPolicyError("AUTO_ROUTING_NOT_APPROVED", "AUTO routing is disabled until its policy and fallback rules are approved.", 409)
    if mode != "MANUAL":
        raise ProviderPolicyError("INVALID_ROUTING_MODE", "Routing mode must be MANUAL or AUTO.", 422)
    return resolve_manual(provider_id, model_id, purpose="production")
