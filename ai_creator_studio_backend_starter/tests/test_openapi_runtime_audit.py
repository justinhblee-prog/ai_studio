from scripts.audit_openapi_runtime import compare_inventories, normalize_path


def test_normalize_runtime_prefix_without_touching_other_paths():
    assert normalize_path("/v1/assets", "/v1") == "/assets"
    assert normalize_path("/internal/ops/workers", "/v1") == "/internal/ops/workers"


def test_compare_reports_missing_extra_and_method_drift():
    report = compare_inventories(
        {
            "/assets": {"post": {}, "get": {}},
            "/quotes": {"post": {}},
        },
        {
            "/v1/assets": {"post": {}, "delete": {}},
            "/v1/workspaces": {"get": {}},
        },
    )
    assert report["spec_only_paths"] == ["/quotes"]
    assert report["runtime_only_paths"] == ["/workspaces"]
    assert report["method_gaps"] == [{
        "path": "/assets",
        "missing_runtime_methods": ["get"],
        "undocumented_runtime_methods": ["delete"],
    }]
    assert report["exact_match"] is False


def test_exact_inventory_match_is_reported():
    report = compare_inventories(
        {"/assets": {"post": {}}, "/jobs/{id}": {"get": {}}},
        {"/v1/assets": {"post": {}}, "/v1/jobs/{id}": {"get": {}}},
    )
    assert report["exact_match"] is True
