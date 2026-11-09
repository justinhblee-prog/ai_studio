import uuid

class MockProvider:
    name = "mock"
    model = "mock-tryon"

    def validate_request(self, payload: dict) -> None:
        if not payload.get("model_image_url") or not payload.get("garment_image_url"):
            raise ValueError("Both input images are required.")

    def describe_capabilities(self) -> list[str]:
        return ["TRY_ON_IMAGE"]

    async def start(self, payload: dict) -> dict:
        # Deliberately does not generate an image; it verifies API flow only.
        return {"request_id": "mock_" + uuid.uuid4().hex, "status": "running"}

    async def status(self, request_id: str) -> dict:
        return {
            "request_id": request_id,
            "status": "running",
            "output_url": None,
            "message": "Mock mode: external image generation is not enabled."
        }
