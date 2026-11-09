import httpx
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from app import config
from app.providers.base import ProviderAdapterError


def _retry_after_seconds(value: str | None) -> float | None:
    """Parse only the standard Retry-After response header (delta-seconds or HTTP-date)."""
    if not value:
        return None
    try:
        return max(0.0, float(value.strip()))
    except (TypeError, ValueError):
        try:
            target = parsedate_to_datetime(value)
            if target.tzinfo is None:
                target = target.replace(tzinfo=timezone.utc)
            return max(0.0, (target - datetime.now(timezone.utc)).total_seconds())
        except (TypeError, ValueError, OverflowError):
            return None


def _raise_poll_http_error(error: httpx.HTTPStatusError) -> None:
    response = error.response
    status = response.status_code
    retryable = status == 429 or status >= 500
    raise ProviderAdapterError(
        "PROVIDER_RATE_LIMITED" if status == 429 else "PROVIDER_POLL_HTTP_ERROR",
        "Provider status polling was rate limited." if status == 429 else "Provider status polling returned an HTTP error.",
        retryable=retryable,
        retry_after_seconds=_retry_after_seconds(response.headers.get("Retry-After")),
    ) from error

class FashnProvider:
    name = "fashn"
    # Official API docs expose prediction IDs and status polling, but no documented
    # client-supplied idempotency key or lookup by our own correlation key.
    supports_idempotency = False
    supports_lookup_by_client_key = False

    def describe_capabilities(self) -> list[str]:
        return ["TRY_ON_IMAGE"]

    def validate_request(self, payload: dict) -> None:
        if not payload.get("model_image_url") or not payload.get("garment_image_url"):
            raise ValueError("Both input images are required.")

    def __init__(self, model_id: str | None = None):
        if not config.FASHN_API_KEY:
            raise RuntimeError("FASHN API key is not configured on the server.")
        selected_model = (model_id or config.FASHN_MODEL).strip().lower()
        if selected_model not in {"tryon-v1.6", "tryon-max"}:
            raise RuntimeError("FASHN_MODEL must be tryon-v1.6 or tryon-max.")
        self.model = selected_model
        self.base_url = config.FASHN_BASE_URL
        self.headers = {
            "Authorization": f"Bearer {config.FASHN_API_KEY}",
            "Content-Type": "application/json",
        }

    def build_request(self, payload: dict) -> dict:
        if self.model == "tryon-max":
            generation_mode = payload.get("mode", "balanced")
            if generation_mode == "performance":
                generation_mode = "fast"
            inputs = {
                "model_image": str(payload["model_image_url"]),
                "product_image": str(payload["garment_image_url"]),
                "generation_mode": generation_mode,
                "resolution": payload.get("resolution", "2k"),
                "output_format": payload.get("output_format", "png"),
                "num_images": 1,
            }
            if payload.get("prompt"):
                inputs["prompt"] = payload["prompt"]
        else:
            # v1.6 does not accept an explicit resolution; input/output dimensions are model-controlled.
            # Its documented garment categories are tops, bottoms, one-pieces and auto.
            category = payload.get("category", "auto")
            if category == "outerwear":
                category = "auto"
            inputs = {
                "model_image": str(payload["model_image_url"]),
                "garment_image": str(payload["garment_image_url"]),
                "category": category,
                "mode": payload.get("mode", "balanced"),
                "output_format": payload.get("output_format", "png"),
                "num_samples": 1,
            }
        return {"model_name": self.model, "inputs": inputs}

    async def start(self, payload: dict) -> dict:
        body = self.build_request(payload)
        async with httpx.AsyncClient(timeout=config.HTTP_TIMEOUT_SECONDS) as client:
            response = await client.post(f"{self.base_url}/v1/run", headers=self.headers, json=body)
            response.raise_for_status()
            data = response.json()
        if data.get("error"):
            raise RuntimeError("Provider rejected the generation request.")
        request_id = data.get("id") or data.get("request_id")
        if not request_id:
            raise RuntimeError("Provider response did not contain a request id.")
        return {"request_id": request_id, "status": "running"}

    async def status(self, request_id: str) -> dict:
        async with httpx.AsyncClient(timeout=config.HTTP_TIMEOUT_SECONDS) as client:
            response = await client.get(
                f"{self.base_url}/v1/status/{request_id}",
                headers={"Authorization": f"Bearer {config.FASHN_API_KEY}"},
            )
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                _raise_poll_http_error(exc)
            data = response.json()

        raw_status = (data.get("status") or "").lower()
        outputs = data.get("output") or data.get("outputs") or []
        output_url = outputs[0] if isinstance(outputs, list) and outputs else None
        if isinstance(output_url, dict):
            output_url = output_url.get("url")
        if raw_status in {"completed", "succeeded", "success"}:
            mapped = "succeeded" if output_url else "failed"
            message = None if output_url else "Provider reported completion without an output image."
        elif raw_status in {"failed", "error", "canceled", "cancelled"}:
            mapped = "failed"
            message = "The provider could not complete this generation."
        else:
            mapped = "running"
            message = None
        return {"request_id": request_id, "status": mapped, "output_url": output_url,
                "message": message, "raw_status": raw_status,
                "retry_after_seconds": _retry_after_seconds(response.headers.get("Retry-After"))}
