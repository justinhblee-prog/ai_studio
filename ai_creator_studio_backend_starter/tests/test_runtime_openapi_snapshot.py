import json
from pathlib import Path

from app.main import app
from scripts.export_runtime_openapi import render_openapi

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = ROOT / "docs" / "api" / "openapi.runtime.v1.json"


def test_committed_runtime_openapi_snapshot_matches_fastapi_contract():
    assert SNAPSHOT.is_file(), "Run scripts/export_runtime_openapi.py to refresh the contract snapshot"
    committed = SNAPSHOT.read_text(encoding="utf-8")
    current = render_openapi(app.openapi())
    assert committed == current, "Runtime API contract changed; review and regenerate the OpenAPI snapshot"


def test_runtime_openapi_snapshot_has_expected_api_identity_and_routes():
    document = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    assert document["openapi"].startswith("3.")
    assert document["info"]["title"] == "AI CREATOR STUDIO API"
    assert "/v1/lookbook-drafts/{draft_id}/outputs/package-export" in document["paths"]
    assert "/v1/lookbook-drafts/exports/{export_id}/download" in document["paths"]
    assert "/v1/credits/accounts/{account_id}" not in document["paths"]
