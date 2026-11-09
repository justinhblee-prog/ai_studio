from pathlib import Path
import pytest
yaml = pytest.importorskip("yaml")
from scripts.audit_openapi_contract import audit_contract, schema_shape


def test_schema_shape_resolves_component_references_and_variants():
    components = {
        "Base": {"type": "object", "required": ["id"], "properties": {"id": {"type": "string"}}},
        "Wrapped": {"allOf": [{"$ref": "#/components/schemas/Base"}, {"type": "object", "properties": {"meta": {"type": "object"}}}]},
    }
    shape = schema_shape({"$ref": "#/components/schemas/Wrapped"}, components)
    assert shape["variants"]["allOf"][0]["properties"] == ["id"]
    assert shape["variants"]["allOf"][0]["required"] == ["id"]


def test_design_runtime_contract_audit_surfaces_cancel_and_job_shape_drift():
    from app.main import app
    spec_path = Path(__file__).resolve().parents[2] / "docs/product-baseline/AI_CREATOR_STUDIO_openapi_integrated_draft_v0_2.yaml"
    spec = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    report = audit_contract(spec, app.openapi(), "/v1")
    cancel = next(item for item in report["contract_drift"] if item["path"] == "/generation-jobs/{job_id}/cancel" and item["method"] == "post")
    assert "request_schema_shape_mismatch" in cancel["issues"]
    assert "success_response_schema_or_status_mismatch" in cancel["issues"]
    create = next(item for item in report["contract_drift"] if item["path"] == "/generation-jobs" and item["method"] == "post")
    assert "request_schema_shape_mismatch" in create["issues"]
    assert report["operations_with_contract_drift"] > 0
    assert "semantic validation" in report["scope_note"]


def test_contract_audit_reports_runtime_only_operations_and_counts():
    design = {"paths": {"/jobs": {"get": {"operationId": "listJobs"}}}}
    runtime = {"paths": {
        "/v1/jobs": {"get": {"operationId": "listJobs"}, "post": {"operationId": "createJob"}},
        "/v1/health": {"get": {"operationId": "health"}},
    }}
    report = audit_contract(design, runtime, "/v1")
    assert report["design_operation_count"] == 1
    assert report["runtime_operation_count"] == 3
    assert report["runtime_only_operations"] == [
        {"path": "/health", "method": "get", "reason": "not_in_design_draft"},
        {"path": "/jobs", "method": "post", "reason": "not_in_design_draft"},
    ]


def test_contract_audit_reports_normalized_runtime_path_collisions():
    design = {"paths": {}}
    runtime = {"paths": {
        "/v1/jobs": {"get": {"operationId": "listJobs"}},
        "/jobs": {"post": {"operationId": "createJob"}},
    }}
    report = audit_contract(design, runtime, "/v1")
    assert report["normalized_runtime_path_collisions"] == [{
        "normalized_path": "/jobs", "source_paths": ["/jobs", "/v1/jobs"]
    }]
    assert report["runtime_operation_count"] == 2
    assert report["runtime_only_operations"] == [
        {"path": "/jobs", "method": "get", "reason": "not_in_design_draft"},
        {"path": "/jobs", "method": "post", "reason": "not_in_design_draft"},
    ]
