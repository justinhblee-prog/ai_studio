from __future__ import annotations

import sys
from pathlib import Path

from app.main import app

PROJECT_ROOT = Path(__file__).resolve().parents[2]
VIEWER_ROOT = PROJECT_ROOT / "ai_creator_studio_3d_viewer"
sys.path.insert(0, str(VIEWER_ROOT / "scripts"))
from validate_viewer_response_contract import audit_viewer_response_contracts  # noqa: E402


def test_every_viewer_fetch_endpoint_has_a_success_json_schema_or_explicit_no_content():
    report = audit_viewer_response_contracts(VIEWER_ROOT, app.openapi())
    assert report["viewer_source_files"] == 8
    assert report["unique_endpoints"] == 52
    assert report["json_success_response_contracts"] == 50
    assert report["distinct_response_models"] == 28
    assert report["missing_routes"] == []
    assert report["missing_response_schemas"] == []
    assert report["unresolved_dynamic_segments"] == []
    assert {item["path"] for item in report["endpoints"] if item["method"] == "put"} >= {"/v1/products/{param}", "/v1/products/{param}/variants/{param}", "/v1/projects/{param}"}
    assert report["no_json_body_endpoints"] == [
        {"method": "delete", "path": "/v1/assets/{param}", "success_statuses": ["204"]},
        {"method": "get", "path": "/v1/assets/{param}/versions/{param}/preview-content", "success_statuses": ["200"]},
    ]


def test_viewer_response_audit_reports_key_envelopes_and_private_rights_flags():
    report = audit_viewer_response_contracts(VIEWER_ROOT, app.openapi())
    models = set(report["response_models"])
    assert "PhotoLocalProcessingResponse" in models
    assert "LookbookPackageExportResponse" in models
    assert "GeneratedOutputReviewResponse" in models
    assert "ManifestExportResponse" in models
