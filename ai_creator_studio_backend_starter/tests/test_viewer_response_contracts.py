from app.main import app, GeneratedOutputItemResponse, GeneratedOutputReviewResponse


def _success_schema(path: str, method: str = "get"):
    operation = app.openapi()["paths"][path][method]
    return operation["responses"]["200"]["content"]["application/json"]["schema"]


def test_generation_output_list_has_explicit_success_response_contract():
    schema = _success_schema("/v1/generation-jobs/{job_id}/outputs")
    assert schema["$ref"].endswith("/GeneratedOutputListResponse")
    item = GeneratedOutputItemResponse.model_validate({
        "id": "out_1", "job_id": "job_1", "mime_type": "image/png",
        "size_bytes": 12, "created_at": "2026-11-03T00:00:00Z",
        "asset_link_status": "linked", "asset_id": None,
        "asset_version_id": None, "provenance_record_id": None,
    })
    assert item.id == "out_1"


def test_generation_output_review_has_explicit_nested_nullable_contract():
    path = "/v1/generation-jobs/{job_id}/outputs/{output_id}/review"
    schema = _success_schema(path)
    assert schema["$ref"].endswith("/GeneratedOutputReviewResponse")
    review = GeneratedOutputReviewResponse.model_validate({
        "output": {
            "output_id": "out_1", "job_id": "job_1", "media_type": "image/png",
            "size_bytes": 12, "created_at": "2026-11-03T00:00:00Z",
            "provider": None, "model": None, "asset_link_status": "not_queued",
            "asset_id": None, "asset_version_id": None,
            "provenance_id": None, "checksum_sha256": None,
        },
        "status": "pending_review", "latest_decision": None,
        "events": [], "job_status": "succeeded",
    })
    assert review.output.asset_id is None


def test_asset_preview_url_success_responses_are_documented():
    spec = app.openapi()
    for path in ("/v1/assets/{asset_id}/preview-url",
                 "/v1/assets/{asset_id}/versions/{version_id}/preview-url"):
        schema = spec["paths"][path]["post"]["responses"]["200"]["content"]["application/json"]["schema"]
        assert schema["$ref"].endswith("/AssetPreviewUrlResponse")


def test_viewer_output_review_types_cover_backend_contract_fields():
    from pathlib import Path
    viewer_file = Path(__file__).resolve().parents[2] / "ai_creator_studio_3d_viewer" / "src" / "OutputReviewWorkspace.tsx"
    source = viewer_file.read_text(encoding="utf-8")
    required_fragments = (
        "job_id: string;", "mime_type: string;", "size_bytes: number;",
        "asset_link_status: string;", "provenance_record_id?: string | null;",
        "latest_decision?: ReviewEvent | null;", "job_status: string;",
    )
    for fragment in required_fragments:
        assert fragment in source
