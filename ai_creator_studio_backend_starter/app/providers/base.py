"""Provider-neutral adapter contracts and normalized error types."""
from typing import Protocol, Any

class TryOnProvider(Protocol):
    name: str
    model: str
    async def start(self, payload: dict[str, Any]) -> dict[str, Any]: ...
    async def status(self, request_id: str) -> dict[str, Any]: ...

class ProviderAdapterError(Exception):
    def __init__(self, code: str, message: str, *, retryable: bool = False,
                 outcome_unknown: bool = False, retry_after_seconds: float | None = None):
        super().__init__(message)
        self.code = code
        self.retryable = retryable
        self.outcome_unknown = outcome_unknown
        self.retry_after_seconds = retry_after_seconds

def normalize_provider_error(error: BaseException) -> dict[str, Any]:
    """Return safe domain error metadata; never serialize raw provider response/headers."""
    if isinstance(error, ProviderAdapterError):
        return {"code": error.code, "message": str(error), "retryable": error.retryable,
                "outcome_unknown": error.outcome_unknown,
                "retry_after_seconds": error.retry_after_seconds}
    return {"code": "INTERNAL_ADAPTER_ERROR", "message": "Provider adapter failed.",
            "retryable": False, "outcome_unknown": False, "retry_after_seconds": None}


class ImageTo3DProvider(Protocol):
    """Lane 5 slot: a provider that turns ONE picture into a 3D model (.glb bytes). Nothing real implements it yet; ``MockImageTo3D`` is the flow-only stand-in.
    A real provider must also be registered in provider_registry with a data-handling record and a unit price before it can be enabled (cost cap and external transfer notice apply)."""
    name: str
    model: str

    async def convert(self, image_bytes: bytes) -> bytes: ...
