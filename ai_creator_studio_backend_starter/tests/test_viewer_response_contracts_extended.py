from __future__ import annotations

from app.main import app
from app.viewer_responses import (
    AssetListResponse,
    AssetVersionListResponse,
    CharacterListResponse,
    LookbookAssemblyReviewResponse,
    LookbookDraftListResponse,
    LookbookOutputListResponse,
    LookbookPackageExportListResponse,
    LookbookPackageExportResponse,
    PhotoDraftListResponse,
    PhotoOutputReviewResponse,
    PhotoRunListResponse,
    ProductListResponse,
    ProductVariantListResponse,
    ProjectListResponse,
)


def _response_schema(path: str, method: str = "get", status: str = "200") -> dict:
    return app.openapi()["paths"][path][method]["responses"][status]["content"]["application/json"]["schema"]


def test_viewer_consumed_catalog_and_workspace_endpoints_publish_response_models():
    expected = {
        ("/v1/assets", "get", "200", "AssetListResponse"),
        ("/v1/assets", "post", "201", "AssetRecordResponse"),
        ("/v1/assets/images", "post", "201", "AssetRecordResponse"),
        ("/v1/assets/{asset_id}/versions", "post", "201", "AssetVersionMutationResponse"),
        ("/v1/assets/{asset_id}/versions/{version_id}/restore", "post", "201", "AssetVersionMutationResponse"),
        ("/v1/assets/{asset_id}/versions", "get", "200", "AssetVersionListResponse"),
        ("/v1/projects", "get", "200", "ProjectListResponse"),
        ("/v1/workspaces/{workspace_id}/characters", "get", "200", "CharacterListResponse"),
        ("/v1/products", "get", "200", "ProductListResponse"),
        ("/v1/products/{product_id}/variants", "get", "200", "ProductVariantListResponse"),
        ("/v1/photo-drafts", "get", "200", "PhotoDraftListResponse"),
        ("/v1/photo-drafts", "post", "201", "PhotoDraftResponse"),
        ("/v1/photo-drafts/{draft_id}/runs", "get", "200", "PhotoRunListResponse"),
        ("/v1/photo-drafts/{draft_id}/runs/{run_id}/review", "get", "200", "PhotoOutputReviewResponse"),
        ("/v1/photo-drafts/{draft_id}/runs/{run_id}/review/approve", "post", "200", "PhotoOutputReviewResponse"),
        ("/v1/photo-drafts/{draft_id}/runs/{run_id}/review/request-changes", "post", "200", "PhotoOutputReviewResponse"),
        ("/v1/photo-drafts/{draft_id}/runs/{run_id}/review/reject", "post", "200", "PhotoOutputReviewResponse"),
        ("/v1/lookbook-drafts", "get", "200", "LookbookDraftListResponse"),
        ("/v1/lookbook-drafts", "post", "201", "LookbookDraftResponse"),
        ("/v1/lookbook-drafts/{draft_id}/outputs", "get", "200", "LookbookOutputListResponse"),
        ("/v1/lookbook-drafts/{draft_id}/outputs", "post", "201", "LookbookOutputResponse"),
        ("/v1/lookbook-drafts/{draft_id}/outputs/manifest", "post", "200", "ManifestExportResponse"),
        ("/v1/lookbook-drafts/{draft_id}/outputs/review", "get", "200", "LookbookAssemblyReviewResponse"),
        ("/v1/lookbook-drafts/{draft_id}/outputs/approve", "post", "200", "LookbookAssemblyReviewResponse"),
        ("/v1/lookbook-drafts/{draft_id}/outputs/reject", "post", "200", "LookbookAssemblyReviewResponse"),
        ("/v1/lookbook-drafts/{draft_id}/outputs/exports", "get", "200", "LookbookPackageExportListResponse"),
        ("/v1/lookbook-drafts/{draft_id}/outputs/package-export", "post", "200", "LookbookPackageExportResponse"),
        ("/v1/lookbook-drafts/{draft_id}/outputs/submit", "post", "200", "LookbookAssemblyReviewResponse"),
        ("/v1/lookbook-drafts/{draft_id}/outputs/approve", "post", "200", "LookbookAssemblyReviewResponse"),
        ("/v1/photo-drafts/{draft_id}/runs/{run_id}/export-manifest", "post", "200", "ManifestExportResponse"),
        ("/v1/photo-drafts/{draft_id}/process-local", "post", "200", "PhotoLocalProcessingResponse"),
        ("/v1/generation-jobs/{job_id}/outputs/export-manifest", "post", "200", "ManifestExportResponse"),
        ("/v1/lookbook-drafts/{draft_id}/manifest", "get", "200", "LookbookPlanManifestResponse"),
    }
    spec = app.openapi()
    for path, method, status, model in expected:
        schema = spec["paths"][path][method]["responses"][status]["content"]["application/json"]["schema"]
        assert schema["$ref"].endswith(f"/{model}"), (path, method, schema)


def test_asset_and_project_list_payload_contracts_accept_realistic_nullable_values():
    asset = {
        "asset_id": "ast_12345678", "owner_id": "usr_1", "workspace_id": "ws_1",
        "original_filename": "model.glb", "media_type": "model/gltf-binary",
        "size_bytes": 12, "checksum_sha256": "a" * 64, "gltf_version": None,
        "embedded_binary": True, "asset_kind": "model", "created_at": "2026-11-03T00:00:00Z",
    }
    assert AssetListResponse.model_validate({"items": [asset]}).items[0].gltf_version is None
    version = {"version_id": "av_1", "asset_id": asset["asset_id"], "workspace_id": "ws_1",
               "version_number": 1, "media_type": "model/gltf-binary", "size_bytes": 12,
               "checksum_sha256": "a" * 64, "created_by": "usr_1",
               "created_at": "2026-11-03T00:00:00Z", "is_current": True}
    assert AssetVersionListResponse.model_validate({"items": [version]}).items[0].is_current
    project = {"project_id": "prj_12345678", "workspace_id": "ws_1", "name": "Catalog",
               "project_type": "APPAREL", "status": "ACTIVE", "description": None,
               "external_reference": None, "created_by": "usr_1",
               "created_at": "2026-11-03T00:00:00Z", "updated_at": "2026-11-03T00:00:00Z"}
    assert ProjectListResponse.model_validate({"items": [project]}).items[0].description is None


def test_product_photo_and_lookbook_response_models_cover_viewer_fields():
    variant = {"variant_id": "var_12345678", "product_id": "prd_12345678", "workspace_id": "ws_1",
               "sku": "SKU-BLK-M", "option_values": {"color": "Black", "size": "M"},
               "image_asset_ids": [], "status": "active", "created_by": "usr_1",
               "created_at": "2026-11-03T00:00:00Z", "updated_at": "2026-11-03T00:00:00Z",
               "archived_at": None}
    product = {"product_id": "prd_12345678", "workspace_id": "ws_1", "sku": "SKU-1", "name": "Jacket",
               "description": None, "category": "outerwear", "status": "active", "created_by": "usr_1",
               "created_at": "2026-11-03T00:00:00Z", "updated_at": "2026-11-03T00:00:00Z",
               "archived_at": None, "image_asset_ids": ["ast_12345678"], "variants": [variant]}
    assert ProductListResponse.model_validate({"items": [product], "total": 1, "limit": 50, "offset": 0}).items[0].variants[0].sku == "SKU-BLK-M"
    assert ProductVariantListResponse.model_validate({"items": [variant]}).items[0].image_asset_ids == []

    photo_draft = {"draft_id": "phd_12345678", "workspace_id": "ws_1", "created_by": "usr_1",
                   "status": "draft", "created_at": "2026-11-03T00:00:00Z", "updated_at": "2026-11-03T00:00:00Z",
                   "input": {"title": "Source", "operation": "ENHANCE", "source_version_id": "av_1"}, "archived_at": None}
    assert PhotoDraftListResponse.model_validate({"items": [photo_draft], "total": 1, "limit": 50, "offset": 0}).items[0].input["operation"] == "ENHANCE"

    photo_run = {"run_id": "phr_12345678", "draft_id": photo_draft["draft_id"], "workspace_id": "ws_1",
                 "created_by": "usr_1", "processor_version": "local-v1", "operation": "ENHANCE",
                 "source_version_id": "av_1", "source_checksum_sha256": "b" * 64, "status": "succeeded",
                 "attempts": 1, "output_asset_id": "ast_out", "output_version_id": "av_out",
                 "output_checksum_sha256": "c" * 64, "quality": {}, "error_message": None,
                 "created_at": "2026-11-03T00:00:00Z", "updated_at": "2026-11-03T00:00:00Z", "review_status": None}
    assert PhotoRunListResponse.model_validate({"items": [photo_run], "total": 1, "limit": 50, "offset": 0}).items[0].review_status is None

    assert LookbookDraftListResponse.model_fields["items"].annotation
    assert LookbookOutputListResponse.model_fields["items"].annotation


def test_review_and_export_response_contracts_keep_explicit_status_and_rights_flags():
    review = {"run_id": "phr_12345678", "status": "pending_review", "output": {
        "asset_id": "ast_1", "asset_version_id": "av_1", "provenance_id": "prov_1",
        "checksum_sha256": "a" * 64, "media_type": "image/png", "size_bytes": 12}, "events": []}
    assert PhotoOutputReviewResponse.model_validate(review).status == "pending_review"
    assembly = {"draft_id": "lbd_12345678", "planning_status": "APPROVED", "status": "approved",
                "output_count": 1, "snapshot_sha256": "b" * 64, "events": []}
    assert LookbookAssemblyReviewResponse.model_validate(assembly).snapshot_sha256
    export = {"export_id": "lbx_12345678", "package_sha256": "a" * 64, "package_size_bytes": 1024,
              "manifest_sha256": "b" * 64, "output_count": 1, "created_at": "2026-11-03T00:00:00Z",
              "expires_at": 1794000000, "download_url": "/v1/lookbook-drafts/exports/lbx_12345678/download",
              "internal_use_only": True, "publication_authorized": False, "commercial_rights_verified": False}
    parsed = LookbookPackageExportResponse.model_validate(export)
    assert parsed.internal_use_only is True and parsed.publication_authorized is False
