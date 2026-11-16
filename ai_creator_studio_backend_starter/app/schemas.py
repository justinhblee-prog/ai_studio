from typing import Literal, Optional
from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator

JobStatus = Literal["queued", "running", "post_processing", "succeeded", "failed"]

class CreateTryOnJob(BaseModel):
    workspace_id: str = Field(min_length=2, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]+$")
    # Each side is EITHER an https address (as before) OR a picked "my library" item id (R-046): the server then signs a short-lived
    # address at dispatch time, so no signed address is ever stored with the job and a queue wait cannot let it expire.
    model_image_url: Optional[HttpUrl] = None
    garment_image_url: Optional[HttpUrl] = None
    model_item_id: Optional[str] = Field(default=None, min_length=4, max_length=80)
    garment_item_id: Optional[str] = Field(default=None, min_length=4, max_length=80)
    category: Literal["tops", "bottoms", "one-pieces", "outerwear", "auto"] = "auto"
    mode: Literal["performance", "balanced", "quality"] = "balanced"
    resolution: Literal["1k", "2k", "4k"] = "2k"
    output_format: Literal["png", "jpeg"] = "png"
    prompt: Optional[str] = Field(default=None, max_length=500)

    @field_validator("model_image_url", "garment_image_url")
    @classmethod
    def require_https(cls, value):
        if value is not None and value.scheme != "https":
            raise ValueError("Image URLs must use HTTPS")
        return value

    @model_validator(mode="after")
    def one_source_per_side(self):
        for side in ("model", "garment"):
            url, item = getattr(self, f"{side}_image_url"), getattr(self, f"{side}_item_id")
            if (url is None) == (item is None):
                raise ValueError(f"give exactly one of {side}_image_url or {side}_item_id")
        return self

class JobResponse(BaseModel):
    job_id: str
    status: JobStatus
    provider: str
    model: Optional[str] = None
    provider_request_id: Optional[str] = None
    output_url: Optional[str] = None
    error_code: Optional[str] = None
    message: Optional[str] = None

class EngineInfo(BaseModel):
    provider: str
    model: str
    mode: str
    configured: bool
    note: str


class ReconcileProviderSubmission(BaseModel):
    action: Literal["attach_request_id", "confirm_not_submitted"]
    reason: str = Field(min_length=12, max_length=1000)
    provider_request_id: Optional[str] = Field(default=None, min_length=1, max_length=256)

    @field_validator("provider_request_id")
    @classmethod
    def trim_request_id(cls, value: Optional[str]) -> Optional[str]:
        return value.strip() if value else value


class RetryPollTaskRequest(BaseModel):
    workspace_id: str = Field(min_length=2, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]+$")
    reason: str = Field(min_length=12, max_length=1000)


class CancelGenerationJobRequest(BaseModel):
    model_config = {"extra": "forbid"}
    reason: Optional[str] = Field(default=None, max_length=500)
