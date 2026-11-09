import pytest

from app.repositories.postgres_output import PostgreSQLOutputRepository


def test_postgres_output_adapter_is_explicit_and_does_not_connect_on_construction():
    repository = PostgreSQLOutputRepository()
    assert repository.backend == "postgresql"


@pytest.mark.parametrize("media_type,key", [
    ("image/png", "result.png"),
    ("image/jpeg", "result.jpg"),
    ("image/webp", "result.webp"),
])
def test_final_output_validation_accepts_private_route_and_matching_media(media_type, key):
    PostgreSQLOutputRepository._validate_final_output(
        "job_123", storage_key=key, media_type=media_type, size_bytes=10,
        output_url="/v1/generation-jobs/job_123/output",
    )


@pytest.mark.parametrize("kwargs", [
    {"storage_key": "../escape.png", "media_type": "image/png", "size_bytes": 10,
     "output_url": "/v1/generation-jobs/job_123/output"},
    {"storage_key": "result.jpg", "media_type": "image/png", "size_bytes": 10,
     "output_url": "/v1/generation-jobs/job_123/output"},
    {"storage_key": "result.png", "media_type": "image/png", "size_bytes": 0,
     "output_url": "/v1/generation-jobs/job_123/output"},
    {"storage_key": "result.png", "media_type": "image/png", "size_bytes": True,
     "output_url": "/v1/generation-jobs/job_123/output"},
    {"storage_key": "result.png", "media_type": "image/png", "size_bytes": 10,
     "output_url": "https://public.example/result.png"},
])
def test_final_output_validation_rejects_unsafe_or_inconsistent_metadata(kwargs):
    with pytest.raises(ValueError):
        PostgreSQLOutputRepository._validate_final_output("job_123", **kwargs)


def test_final_output_validation_rejects_oversized_output():
    from app import config
    with pytest.raises(ValueError, match="size"):
        PostgreSQLOutputRepository._validate_final_output(
            "job_123", storage_key="result.png", media_type="image/png",
            size_bytes=config.MAX_OUTPUT_BYTES + 1,
            output_url="/v1/generation-jobs/job_123/output",
        )
