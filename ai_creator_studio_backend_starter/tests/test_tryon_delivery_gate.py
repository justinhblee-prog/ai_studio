"""R-046: a generated result reaches "my library" only after it is APPROVED (delivery is blocked before review)."""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.output_asset_link_worker import process_one
from tests.test_output_asset_link_worker import linked_output_env  # noqa: F401

client = TestClient(app)
A = {"Authorization": "Bearer token-user-a"}
WS = "ws-output-link"


def library():
    return client.get(f"/v1/workspaces/{WS}/library", headers=A).json()


def test_a_result_is_filed_in_the_library_only_when_approved(linked_output_env):
    job_id = linked_output_env["job_id"]
    output_id = client.get(f"/v1/generation-jobs/{job_id}/outputs", headers=A).json()["data"][0]["id"]
    assert process_one(worker_id="delivery-worker") is True
    assert library()["total"] == 0, "linked but not reviewed: not delivered"
    changes = client.post(f"/v1/generation-jobs/{job_id}/outputs/{output_id}/review/request-changes", headers=A, json={"comment": "더 밝게"})
    assert changes.status_code == 200 and library()["total"] == 0, "a change request delivers nothing"
    approved = client.post(f"/v1/generation-jobs/{job_id}/outputs/{output_id}/review/approve", headers=A, json={"comment": "ok"})
    assert approved.status_code == 200, approved.text
    items = library()["items"]
    assert len(items) == 1
    assert items[0]["kind"] == "render" and items[0]["origin"] == "ai" and items[0]["is_ai_generated"] is True
    assert items[0]["asset_id"] == approved.json()["output"]["asset_id"]


def test_rejection_delivers_nothing_and_filing_is_idempotent(linked_output_env):
    from app.workspace_library import file_generated_output
    job_id = linked_output_env["job_id"]
    output_id = client.get(f"/v1/generation-jobs/{job_id}/outputs", headers=A).json()["data"][0]["id"]
    assert process_one(worker_id="delivery-worker") is True
    rejected = client.post(f"/v1/generation-jobs/{job_id}/outputs/{output_id}/review/reject", headers=A, json={"comment": "다른 제품"})
    assert rejected.status_code == 200 and library()["total"] == 0
    asset_id = rejected.json()["output"]["asset_id"]
    assert file_generated_output(WS, asset_id, "user-a", "x") == "filed"
    assert file_generated_output(WS, asset_id, "user-a", "x") == "exists"
    assert file_generated_output(WS, None, "user-a", "x") == "skipped"
