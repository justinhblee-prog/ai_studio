"""Opt-in, cost-gated live FASHN sandbox smoke test.

This bypasses the production Provider registry gate intentionally and tests only
FASHN API start/status plus output download/format validation. It does NOT enable
production dispatch, validate commercial rights, or persist a Generation Job.

Required environment:
  FASHN_API_KEY
  FASHN_LIVE_TEST_MODEL_IMAGE_URL (authorized HTTPS image URL)
  FASHN_LIVE_TEST_GARMENT_IMAGE_URL (authorized HTTPS image URL)
  FASHN_LIVE_TEST_CONFIRM_COST=I_UNDERSTAND_PROVIDER_MAY_CHARGE
Optional:
  FASHN_LIVE_TEST_MODEL=tryon-v1.6|tryon-max
  FASHN_LIVE_TEST_TIMEOUT_SECONDS=600
  FASHN_LIVE_TEST_POLL_SECONDS=3
"""
from __future__ import annotations

import asyncio
import ipaddress
import json
import os
import sys
import tempfile
import time
from urllib.parse import urlparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import config
from app.output_store import save_provider_output_artifact
from app.providers.fashn import FashnProvider

COST_CONFIRMATION = "I_UNDERSTAND_PROVIDER_MAY_CHARGE"


def _required_url(name: str) -> str:
    value = os.getenv(name, "").strip()
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError(f"{name} must be a credential-free HTTPS URL.")
    host = parsed.hostname.rstrip(".").lower()
    if host in {"localhost", "localhost.localdomain"}:
        raise ValueError(f"{name} must not target localhost.")
    try:
        if not ipaddress.ip_address(host).is_global:
            raise ValueError(f"{name} must not target a non-public IP address.")
    except ValueError as exc:
        if str(exc).startswith(name):
            raise
    return value


def preflight() -> tuple[str, str, str]:
    if os.getenv("FASHN_LIVE_TEST_CONFIRM_COST") != COST_CONFIRMATION:
        raise RuntimeError("Live generation is disabled: explicit cost confirmation is required.")
    if not config.FASHN_API_KEY:
        raise RuntimeError("Live generation is disabled: FASHN_API_KEY is not configured.")
    model = os.getenv("FASHN_LIVE_TEST_MODEL", config.FASHN_MODEL).strip().lower()
    if model not in {"tryon-v1.6", "tryon-max"}:
        raise ValueError("FASHN_LIVE_TEST_MODEL must be tryon-v1.6 or tryon-max.")
    return model, _required_url("FASHN_LIVE_TEST_MODEL_IMAGE_URL"), _required_url("FASHN_LIVE_TEST_GARMENT_IMAGE_URL")


async def run_live_smoke() -> dict:
    model, model_url, garment_url = preflight()
    timeout_seconds = max(30, min(1800, int(os.getenv("FASHN_LIVE_TEST_TIMEOUT_SECONDS", "600"))))
    poll_seconds = max(1, min(30, float(os.getenv("FASHN_LIVE_TEST_POLL_SECONDS", "3"))))
    provider = FashnProvider(model_id=model)
    payload = {
        "model_image_url": model_url,
        "garment_image_url": garment_url,
        "category": os.getenv("FASHN_LIVE_TEST_CATEGORY", "auto"),
        "mode": os.getenv("FASHN_LIVE_TEST_MODE", "balanced"),
        "resolution": os.getenv("FASHN_LIVE_TEST_RESOLUTION", "2k"),
        "output_format": os.getenv("FASHN_LIVE_TEST_OUTPUT_FORMAT", "png"),
    }
    if os.getenv("FASHN_LIVE_TEST_PROMPT"):
        payload["prompt"] = os.environ["FASHN_LIVE_TEST_PROMPT"][:500]
    provider.validate_request(payload)

    started_at = time.monotonic()
    started = await provider.start(payload)
    request_id = started["request_id"]
    deadline = started_at + timeout_seconds
    status = None
    while time.monotonic() < deadline:
        status = await provider.status(request_id)
        if status.get("status") in {"succeeded", "failed"}:
            break
        await asyncio.sleep(poll_seconds)
    else:
        raise TimeoutError(
            "FASHN live test timed out. The remote request may still be running; "
            f"do not resubmit blindly. Provider request id: {request_id}"
        )

    if status.get("status") != "succeeded" or not status.get("output_url"):
        raise RuntimeError(f"FASHN live generation failed (request_id={request_id}).")

    # Download to an ephemeral directory and validate real image bytes. The test
    # output is deleted on exit; it is not attached to a Job or user workspace.
    original_output_dir = config.OUTPUT_DIR
    with tempfile.TemporaryDirectory(prefix="fashn-live-smoke-") as tmp:
        config.OUTPUT_DIR = Path(tmp)
        try:
            _route, storage_key = await save_provider_output_artifact(
                status["output_url"], "live-smoke", request_id
            )
            output_path = config.OUTPUT_DIR / storage_key
            result = {
                "result": "LIVE_PROVIDER_AND_OUTPUT_DOWNLOAD_VERIFIED",
                "provider": "fashn",
                "model": model,
                "request_id": request_id,
                "elapsed_seconds": round(time.monotonic() - started_at, 2),
                "output_bytes": output_path.stat().st_size,
                "output_format": output_path.suffix.lstrip("."),
                "output_url_logged": False,
                "job_persisted": False,
                "production_eligibility_changed": False,
            }
        finally:
            config.OUTPUT_DIR = original_output_dir
    return result


def main() -> int:
    try:
        result = asyncio.run(run_live_smoke())
    except Exception as exc:
        # Never print API credentials, signed input URLs, or the signed output URL.
        print(json.dumps({"result": "FAILED_OR_BLOCKED", "error_type": type(exc).__name__,
                          "message": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
