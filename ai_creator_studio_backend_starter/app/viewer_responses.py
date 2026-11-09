"""Explicit success response contracts for Viewer-consumed APIs.

These models describe the current runtime payloads; they do not change endpoint
semantics. Extra fields are intentionally allowed during the compatibility
migration so adding server metadata does not silently strip it from responses.
"""
from __future__ import annotations

from typing import Any
from pydantic import BaseModel, ConfigDict


class ViewerResponse(BaseModel):
    model_config = ConfigDict(extra="allow")


class AssetRecordResponse(ViewerResponse):
    asset_id: str
    owner_id: str
    workspace_id: str
    original_filename: str
    media_type: str
    size_bytes: int
    checksum_sha256: str
    gltf_version: str | None
    embedded_binary: bool
    asset_kind: str
    created_at: str


class AssetListResponse(ViewerResponse):
    items: list[AssetRecordResponse]


class AssetVersionResponse(ViewerResponse):
    version_id: str
    asset_id: str
    workspace_id: str
    version_number: int
    media_type: str
    size_bytes: int
    checksum_sha256: str
    created_by: str
    created_at: str
    is_current: bool


class AssetVersionListResponse(ViewerResponse):
    items: list[AssetVersionResponse]


class ProjectResponse(ViewerResponse):
    project_id: str
    workspace_id: str
    name: str
    project_type: str
    status: str
    description: str | None
    external_reference: str | None
    created_by: str
    created_at: str
    updated_at: str


class ProjectListResponse(ViewerResponse):
    items: list[ProjectResponse]


class ProductVariantResponse(ViewerResponse):
    variant_id: str
    product_id: str
    workspace_id: str
    sku: str
    option_values: dict[str, str]
    image_asset_ids: list[str]
    status: str
    created_by: str
    created_at: str
    updated_at: str
    archived_at: str | None = None


class ProductResponse(ViewerResponse):
    product_id: str
    workspace_id: str
    sku: str
    name: str
    description: str | None
    category: str
    status: str
    created_by: str
    created_at: str
    updated_at: str
    archived_at: str | None = None
    image_asset_ids: list[str]
    variants: list[ProductVariantResponse]


class ProductListResponse(ViewerResponse):
    items: list[ProductResponse]
    total: int
    limit: int
    offset: int


class ProductVariantListResponse(ViewerResponse):
    items: list[ProductVariantResponse]


class ProjectProductListResponse(ViewerResponse):
    project_id: str
    workspace_id: str
    items: list[ProductResponse]
    total: int


class PhotoDraftResponse(ViewerResponse):
    draft_id: str
    workspace_id: str
    created_by: str
    status: str
    created_at: str
    updated_at: str
    input: dict[str, Any]
    archived_at: str | None = None


class PhotoDraftListResponse(ViewerResponse):
    items: list[PhotoDraftResponse]
    total: int
    limit: int
    offset: int


class PhotoRunResponse(ViewerResponse):
    run_id: str
    draft_id: str
    workspace_id: str
    created_by: str
    processor_version: str
    operation: str
    source_version_id: str | None
    source_checksum_sha256: str | None
    status: str
    attempts: int
    output_asset_id: str | None
    output_version_id: str | None
    output_checksum_sha256: str | None
    quality: dict[str, Any]
    error_message: str | None
    created_at: str
    updated_at: str
    review_status: str | None = None


class PhotoRunListResponse(ViewerResponse):
    items: list[PhotoRunResponse]
    total: int
    limit: int
    offset: int


class LookbookDraftResponse(ViewerResponse):
    draft_id: str
    workspace_id: str
    created_by: str
    status: str
    workflow_status: str
    created_at: str
    updated_at: str
    input: dict[str, Any]
    archived_at: str | None = None


class LookbookDraftListResponse(ViewerResponse):
    items: list[LookbookDraftResponse]
    total: int
    limit: int
    offset: int


class LookbookOutputResponse(ViewerResponse):
    output_item_id: str
    draft_id: str
    workspace_id: str
    photo_run_id: str
    asset_id: str
    asset_version_id: str
    provenance_id: str
    checksum_sha256: str
    product_id: str | None
    product_sku: str | None
    product_variant_id: str | None
    variant_sku: str | None
    variant_options: dict[str, str]
    page_order: int
    caption: str | None
    created_by: str
    created_at: str


class LookbookOutputListResponse(ViewerResponse):
    items: list[LookbookOutputResponse]
    total: int


class LookbookAssemblyReviewResponse(ViewerResponse):
    draft_id: str
    planning_status: str
    status: str
    output_count: int
    snapshot_sha256: str | None
    events: list[dict[str, Any]]


class LookbookPackageExportResponse(ViewerResponse):
    export_id: str
    package_sha256: str
    package_size_bytes: int
    manifest_sha256: str
    output_count: int
    created_at: str
    expires_at: int
    download_url: str
    internal_use_only: bool
    publication_authorized: bool
    commercial_rights_verified: bool


class LookbookPackageExportItemResponse(ViewerResponse):
    export_id: str
    package_sha256: str
    package_size_bytes: int
    manifest_sha256: str
    snapshot_sha256: str
    output_count: int
    created_at: str
    expires_at: int
    status: str


class LookbookPackageExportListResponse(ViewerResponse):
    items: list[LookbookPackageExportItemResponse]
    total: int


class ManifestExportResponse(ViewerResponse):
    manifest: dict[str, Any]
    manifest_sha256: str
    exported_at: str

class CharacterResponse(ViewerResponse):
    character_id: str
    workspace_id: str
    owner_id: str
    identity: dict[str, Any]
    outfits: list[dict[str, Any]]
    active_outfit_id: str | None
    asset_ids: list[str]
    created_at: str
    updated_at: str


class CharacterListResponse(ViewerResponse):
    items: list[CharacterResponse]


class EventItemResponse(ViewerResponse):
    event_id: str
    actor_id: str | None = None
    event_type: str
    created_at: str
    details: dict[str, Any]


class EventListResponse(ViewerResponse):
    items: list[EventItemResponse]
    total: int
    limit: int | None = None
    offset: int | None = None


class PhotoOutputReviewEventResponse(ViewerResponse):
    event_id: str
    run_id: str
    draft_id: str
    actor_id: str
    decision: str
    comment: str
    asset_id: str
    asset_version_id: str
    provenance_id: str
    checksum_sha256: str
    created_at: str


class PhotoOutputReviewResponse(ViewerResponse):
    run_id: str
    status: str
    output: dict[str, Any]
    events: list[PhotoOutputReviewEventResponse]

class AssetVersionMutationResponse(AssetRecordResponse):
    version_id: str
    version_number: int


class PhotoLocalProcessingResponse(ViewerResponse):
    run: PhotoRunResponse
    output_asset: AssetRecordResponse

class LookbookPlanManifestResponse(ViewerResponse):
    manifest_type: str
    generated_outputs_included: bool
    draft_id: str
    workspace_id: str
    workflow_status: str
    approved_at: str | None
    approved_by: str | None
    input: dict[str, Any]
    referenced_assets: list[dict[str, Any]]
