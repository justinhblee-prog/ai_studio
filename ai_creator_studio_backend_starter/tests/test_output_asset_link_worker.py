import hashlib
import io
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app import job_repository
from app.output_asset_link_worker import process_one, import_output_asset
from app.repositories.output_asset_link import build_output_asset_link_repository

client = TestClient(app)


def auth():
    return {"Authorization": "Bearer token-user-a"}


@pytest.fixture
def linked_output_env(tmp_path, monkeypatch):
    import app.config as config
    import app.main as main
    from app.assets.store import create_workspace
    monkeypatch.setattr(config, "ASSET_DATABASE_PATH", tmp_path / "asset-store.sqlite3")
    monkeypatch.setattr(config, "GENERATION_DATABASE_PATH", tmp_path / "generation-store.sqlite3")
    monkeypatch.setattr(config, "ASSET_STORAGE_DIR", tmp_path / "asset-files")
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path / "output-files")
    monkeypatch.setattr(config, "ASSET_SIGNING_SECRET", "s" * 48)
    monkeypatch.setattr(config, "asset_api_tokens", lambda: {"token-user-a": "user-a", "token-user-b": "user-b"})
    monkeypatch.setattr(main.config, "PROVIDER_MODE", "mock")
    create_workspace("ws-output-link", "user-a")
    response = client.post("/v1/generation-jobs", headers=auth(), json={
        "workspace_id": "ws-output-link", "model_image_url": "https://example.com/model.jpg",
        "garment_image_url": "https://example.com/garment.jpg",
    })
    assert response.status_code == 202, response.text
    job_id = response.json()["job_id"]
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    buffer = io.BytesIO()
    Image.new("RGB", (48, 48), (50, 120, 210)).save(buffer, format="PNG")
    content = buffer.getvalue()
    storage_key = f"{job_id}.attempt-test-001.png"
    (config.OUTPUT_DIR / storage_key).write_bytes(content)
    now = datetime.now(timezone.utc)
    task_id = "poll_link_test"
    with job_repository._connect() as db:
        db.execute("UPDATE generation_jobs SET status='post_processing' WHERE job_id=?", (job_id,))
        db.execute("UPDATE generation_executions SET status='post_processing' WHERE job_id=?", (job_id,))
        db.execute("""INSERT INTO generation_poll_tasks(task_id,job_id,phase,status,attempts,available_at,claimed_by,
            claimed_at,lease_expires_at,created_at,updated_at) VALUES(?,?,'persist_output','processing',1,?,?,?,?,?,?)""",
            (task_id, job_id, now.isoformat(), "poller", now.isoformat(), (now + timedelta(minutes=5)).isoformat(), now.isoformat(), now.isoformat()))
    assert job_repository.finalize_output_success(
        task_id, "poller", job_id, storage_key=storage_key, media_type="image/png",
        size_bytes=len(content), output_url=f"/v1/generation-jobs/{job_id}/output",
        checksum_sha256=hashlib.sha256(content).hexdigest(),
    ) is True
    return {"job_id": job_id, "storage_key": storage_key, "content": content,
            "checksum": hashlib.sha256(content).hexdigest(), "task_id": task_id}


def test_output_asset_link_worker_imports_immutable_asset_across_separate_databases(linked_output_env):
    assert process_one(worker_id="asset-link-test") is True
    outputs = client.get(f"/v1/generation-jobs/{linked_output_env['job_id']}/outputs", headers=auth())
    assert outputs.status_code == 200
    item = outputs.json()["data"][0]
    assert item["asset_link_status"] == "linked"
    assert item["checksum_sha256"] == linked_output_env["checksum"]
    assert item["asset_id"] and item["asset_version_id"] and item["provenance_record_id"]
    assert "storage_key" not in item

    asset = client.get(f"/v1/assets/{item['asset_id']}", headers=auth())
    assert asset.status_code == 200
    assert asset.json()["asset_kind"] == "image"
    assert asset.json()["checksum_sha256"] == linked_output_env["checksum"]
    assert client.delete(f"/v1/assets/{item['asset_id']}", headers=auth()).status_code == 409
    diagnostics = client.get(f"/v1/generation-jobs/{linked_output_env['job_id']}/events", headers=auth()).json()
    assert "storage_key" not in diagnostics["output"]
    assert all("storage_key" not in event.get("payload", {}) for event in diagnostics["events"])
    versions = client.get(f"/v1/assets/{item['asset_id']}/versions", headers=auth()).json()
    assert len(versions["items"]) == 1
    provenance = client.get(f"/v1/assets/{item['asset_id']}/provenance", headers=auth()).json()
    imported_event = next(row for row in provenance["items"] if row["event_type"] == "asset.generated_output_imported")
    assert imported_event["actor_id"] == "system:output_asset_link_worker"
    assert imported_event["details"]["initiated_by"] == "user-a"
    assert imported_event["details"]["worker_id"] == "asset-link-test"
    assert imported_event["details"]["job_id"] == linked_output_env["job_id"]

    from app import config
    import hashlib as _hashlib
    linked_file = config.ASSET_STORAGE_DIR / f"{item['asset_id']}.png"
    assert linked_file.read_bytes() == linked_output_env["content"]
    assert _hashlib.sha256(linked_file.read_bytes()).hexdigest() == linked_output_env["checksum"]
    with job_repository._connect() as db:
        row = db.execute("SELECT status,asset_id,asset_version_id FROM generation_output_asset_links WHERE job_id=?",
                         (linked_output_env["job_id"],)).fetchone()
    assert row["status"] == "linked" and row["asset_id"] == item["asset_id"]
    with job_repository._connect() as db:
        heartbeat = db.execute("SELECT metadata_json FROM generation_worker_heartbeats WHERE worker_id=?", ("asset-link-test",)).fetchone()
    assert heartbeat is not None and '"worker_type": "output_asset_link"' in heartbeat["metadata_json"]
    assert process_one(worker_id="asset-link-test") is False



def test_output_asset_link_retry_rejects_cross_workspace_version_tampering(linked_output_env):
    repository = build_output_asset_link_repository()
    claimed = repository.claim_one("asset-link-integrity-test", lease_seconds=60)
    assert claimed is not None
    imported = import_output_asset(claimed)

    from app.assets.store import _connect as asset_connect
    with asset_connect() as db:
        db.execute("UPDATE asset_versions SET workspace_id='ws-attacker' WHERE version_id=?",
                   (imported["asset_version_id"],))

    with pytest.raises(ValueError, match="Version or Provenance metadata failed integrity verification"):
        import_output_asset(claimed)


def test_output_asset_link_retry_rejects_asset_owner_mismatch(linked_output_env):
    repository = build_output_asset_link_repository()
    claimed = repository.claim_one("asset-link-owner-integrity-test", lease_seconds=60)
    assert claimed is not None
    imported = import_output_asset(claimed)

    from app.assets.store import _connect as asset_connect
    with asset_connect() as db:
        db.execute("UPDATE assets SET owner_id='user-attacker' WHERE asset_id=?", (imported["asset_id"],))

    with pytest.raises(ValueError, match="owner, workspace, or content metadata conflicts"):
        import_output_asset(claimed)

def test_output_asset_link_worker_marks_checksum_mismatch_failed_without_creating_asset(linked_output_env):
    from app import config
    output_file = config.OUTPUT_DIR / linked_output_env["storage_key"]
    data = bytearray(output_file.read_bytes()); data[-1] ^= 0x01; output_file.write_bytes(data)
    assert process_one(worker_id="asset-link-invalid") is True
    with job_repository._connect() as db:
        row = db.execute("SELECT status,attempts,last_error FROM generation_output_asset_links WHERE job_id=?",
                         (linked_output_env["job_id"],)).fetchone()
    assert row["status"] == "failed" and row["attempts"] == 1
    assert "checksum" in row["last_error"].lower()
    outputs = client.get(f"/v1/generation-jobs/{linked_output_env['job_id']}/outputs", headers=auth()).json()
    assert outputs["data"][0]["asset_link_status"] == "failed"


def test_output_asset_link_worker_recovers_after_asset_commit_before_outbox_ack(linked_output_env):
    repository = build_output_asset_link_repository()
    claimed = repository.claim_one("worker-before-crash", lease_seconds=1)
    assert claimed is not None
    imported = import_output_asset(claimed)
    # Simulate process death after Asset DB commit but before Generation DB acknowledgement.
    with job_repository._connect() as db:
        db.execute("UPDATE generation_output_asset_links SET lease_expires_at=? WHERE link_id=?",
                   ((datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(), claimed["link_id"]))
    assert process_one(worker_id="worker-recovery") is True
    with job_repository._connect() as db:
        row = db.execute("SELECT status,asset_id,asset_version_id,provenance_id FROM generation_output_asset_links WHERE link_id=?",
                         (claimed["link_id"],)).fetchone()
    assert row["status"] == "linked"
    assert row["asset_id"] == imported["asset_id"]
    assert row["asset_version_id"] == imported["asset_version_id"]
    assert row["provenance_id"] == imported["provenance_id"]


def test_failed_output_link_can_be_retried_by_workspace_admin_with_audit(linked_output_env):
    from app import config
    from app.assets.store import add_workspace_member
    output_file = config.OUTPUT_DIR / linked_output_env["storage_key"]
    damaged = bytearray(linked_output_env["content"]); damaged[-1] ^= 0x01; output_file.write_bytes(damaged)
    assert process_one(worker_id="asset-link-retry-test") is True
    outputs = client.get(f"/v1/generation-jobs/{linked_output_env['job_id']}/outputs", headers=auth()).json()
    output_id = outputs["data"][0]["id"]
    assert outputs["data"][0]["asset_link_status"] == "failed"

    add_workspace_member("ws-output-link", "user-b", "viewer")
    viewer_retry = client.post(f"/v1/generation-jobs/{linked_output_env['job_id']}/outputs/{output_id}/asset-link-retry",
                               headers={"Authorization": "Bearer token-user-b"}, json={"reason": "retry"})
    assert viewer_retry.status_code == 403
    missing_reason = client.post(f"/v1/generation-jobs/{linked_output_env['job_id']}/outputs/{output_id}/asset-link-retry",
                                 headers=auth(), json={})
    assert missing_reason.status_code == 422
    retried = client.post(f"/v1/generation-jobs/{linked_output_env['job_id']}/outputs/{output_id}/asset-link-retry",
                          headers=auth(), json={"reason": "Restored the original validated output file"})
    assert retried.status_code == 200 and retried.json()["status"] == "pending"
    duplicate_retry = client.post(f"/v1/generation-jobs/{linked_output_env['job_id']}/outputs/{output_id}/asset-link-retry",
                                  headers=auth(), json={"reason": "duplicate"})
    assert duplicate_retry.status_code == 409

    output_file.write_bytes(linked_output_env["content"])
    assert process_one(worker_id="asset-link-retry-test") is True
    events = client.get(f"/v1/generation-jobs/{linked_output_env['job_id']}/outputs/{output_id}/asset-link-events", headers=auth())
    assert events.status_code == 200 and events.json()["total"] == 1
    event = events.json()["items"][0]
    assert event["event_type"] == "output_asset_link.retry_requested"
    assert event["details"]["reason"] == "Restored the original validated output file"
    final = client.get(f"/v1/generation-jobs/{linked_output_env['job_id']}/outputs", headers=auth()).json()
    assert final["data"][0]["asset_link_status"] == "linked"


def test_generated_output_review_and_internal_export_manifest(linked_output_env):
    from app import config
    from app.assets.store import add_workspace_member
    job_id = linked_output_env["job_id"]
    outputs = client.get(f"/v1/generation-jobs/{job_id}/outputs", headers=auth()).json()
    output_id = outputs["data"][0]["id"]

    # A generated binary is not reviewable until the verified immutable AssetVersion exists.
    pending = client.get(f"/v1/generation-jobs/{job_id}/outputs/{output_id}/review", headers=auth())
    assert pending.status_code == 200
    assert pending.json()["status"] == "asset_link_pending"
    premature = client.post(f"/v1/generation-jobs/{job_id}/outputs/{output_id}/review/approve",
                            headers=auth(), json={})
    assert premature.status_code == 409

    assert process_one(worker_id="review-link-worker") is True
    ready = client.get(f"/v1/generation-jobs/{job_id}/outputs/{output_id}/review", headers=auth())
    assert ready.status_code == 200 and ready.json()["status"] == "pending_review"
    linked = ready.json()["output"]
    assert linked["asset_id"] and linked["asset_version_id"] and linked["provenance_id"]
    assert linked["checksum_sha256"] == linked_output_env["checksum"]

    add_workspace_member("ws-output-link", "user-b", "viewer")
    viewer_read = client.get(f"/v1/generation-jobs/{job_id}/outputs/{output_id}/review",
                             headers={"Authorization": "Bearer token-user-b"})
    assert viewer_read.status_code == 200 and viewer_read.json()["status"] == "pending_review"
    viewer = client.post(f"/v1/generation-jobs/{job_id}/outputs/{output_id}/review/approve",
                         headers={"Authorization": "Bearer token-user-b"}, json={})
    assert viewer.status_code == 403
    missing_comment = client.post(f"/v1/generation-jobs/{job_id}/outputs/{output_id}/review/request-changes",
                                  headers=auth(), json={})
    assert missing_comment.status_code == 409

    changes = client.post(f"/v1/generation-jobs/{job_id}/outputs/{output_id}/review/request-changes",
                          headers=auth(), json={"comment": "Please refine garment edge details."})
    assert changes.status_code == 200 and changes.json()["status"] == "changes_requested"
    assert changes.json()["events"][0]["comment"] == "Please refine garment edge details."

    blocked_export = client.post(f"/v1/generation-jobs/{job_id}/outputs/export-manifest", headers=auth())
    assert blocked_export.status_code == 409
    approved = client.post(f"/v1/generation-jobs/{job_id}/outputs/{output_id}/review/approve",
                           headers=auth(), json={"comment": "Final visual review passed."})
    assert approved.status_code == 200 and approved.json()["status"] == "approved"
    assert len(approved.json()["events"]) == 2

    exported = client.post(f"/v1/generation-jobs/{job_id}/outputs/export-manifest", headers=auth())
    assert exported.status_code == 200
    body = exported.json()
    manifest = body["manifest"]
    assert manifest["manifest_type"] == "AI_CREATOR_STUDIO_INTERNAL_OUTPUT_MANIFEST"
    assert manifest["publication_authorized"] is False
    assert manifest["commercial_rights_verified"] is False
    assert manifest["binary_files_included"] is False
    assert len(manifest["outputs"]) == 1
    viewer_export = client.post(f"/v1/generation-jobs/{job_id}/outputs/export-manifest",
                                headers={"Authorization": "Bearer token-user-b"})
    assert viewer_export.status_code == 403
    item = manifest["outputs"][0]
    assert item["asset_id"] == linked["asset_id"]
    assert item["asset_version_id"] == linked["asset_version_id"]
    assert item["provenance_id"] == linked["provenance_id"]
    assert item["checksum_sha256"] == linked_output_env["checksum"]
    assert body["manifest_sha256"]

    # Approval is terminal and its event is immutable; re-review needs a new generated output.
    terminal = client.post(f"/v1/generation-jobs/{job_id}/outputs/{output_id}/review/reject",
                           headers=auth(), json={"comment": "Try again"})
    assert terminal.status_code == 409
    with job_repository._connect() as db:
        review_count = db.execute("SELECT COUNT(*) FROM generation_output_review_events WHERE output_id=?", (output_id,)).fetchone()[0]
        export_count = db.execute("SELECT COUNT(*) FROM generation_output_export_events WHERE job_id=?", (job_id,)).fetchone()[0]
        event = db.execute("SELECT asset_id,asset_version_id,provenance_id,checksum_sha256 FROM generation_output_review_events WHERE output_id=? ORDER BY created_at DESC LIMIT 1", (output_id,)).fetchone()
        assert event["asset_id"] == linked["asset_id"]
        assert event["asset_version_id"] == linked["asset_version_id"]
        assert event["provenance_id"] == linked["provenance_id"]
        assert event["checksum_sha256"] == linked_output_env["checksum"]
        assert review_count == 2 and export_count == 1
        with pytest.raises(Exception):
            db.execute("UPDATE generation_output_review_events SET comment='tampered' WHERE output_id=?", (output_id,))


def test_output_review_requires_approval_before_export_and_rejection_is_terminal(linked_output_env):
    job_id = linked_output_env["job_id"]
    assert process_one(worker_id="review-reject-link-worker") is True
    outputs = client.get(f"/v1/generation-jobs/{job_id}/outputs", headers=auth()).json()
    output_id = outputs["data"][0]["id"]
    rejected = client.post(f"/v1/generation-jobs/{job_id}/outputs/{output_id}/review/reject",
                           headers=auth(), json={"comment": "Identity mismatch"})
    assert rejected.status_code == 200 and rejected.json()["status"] == "rejected"
    export = client.post(f"/v1/generation-jobs/{job_id}/outputs/export-manifest", headers=auth())
    assert export.status_code == 409
    retry_review = client.post(f"/v1/generation-jobs/{job_id}/outputs/{output_id}/review/approve",
                               headers=auth(), json={})
    assert retry_review.status_code == 409

@pytest.mark.parametrize("worker_id,lease_seconds", [
    ("", 10), ("  ", 10), (None, 10), ("worker", 0), ("worker", -1),
    ("worker", True), ("worker", 1.5), ("worker", "10"),
])
def test_output_asset_link_claim_rejects_invalid_lease_before_storage(worker_id, lease_seconds, monkeypatch):
    repository = build_output_asset_link_repository()
    monkeypatch.setattr(repository, "initialize", lambda: pytest.fail("storage touched before validation"))
    with pytest.raises(ValueError):
        repository.claim_one(worker_id, lease_seconds)


@pytest.mark.parametrize("max_attempts", [0, -1, True, 1.5, "5"])
def test_output_asset_link_failure_rejects_invalid_attempt_limit_before_storage(max_attempts, monkeypatch):
    repository = build_output_asset_link_repository()
    monkeypatch.setattr(repository, "initialize", lambda: pytest.fail("storage touched before validation"))
    with pytest.raises(ValueError):
        repository.record_failure("link-1", "worker-1", error="failure", max_attempts=max_attempts)


def test_output_asset_link_failure_rejects_invalid_owner_before_storage(monkeypatch):
    repository = build_output_asset_link_repository()
    monkeypatch.setattr(repository, "initialize", lambda: pytest.fail("storage touched before validation"))
    with pytest.raises(ValueError):
        repository.record_failure("link-1", " ", error="failure")


# ---- L-07: AI generated disclosure on provider job outputs -------------------------------------------------------

def _link_and_approve(job_id):
    """Link the verified AssetVersion, approve the output and export the internal manifest."""
    output_id = client.get(f"/v1/generation-jobs/{job_id}/outputs", headers=auth()).json()["data"][0]["id"]
    assert process_one(worker_id="disclosure-worker") is True
    approved = client.post(f"/v1/generation-jobs/{job_id}/outputs/{output_id}/review/approve", headers=auth(), json={"comment": "ok"})
    assert approved.status_code == 200, approved.text
    exported = client.post(f"/v1/generation-jobs/{job_id}/outputs/export-manifest", headers=auth())
    assert exported.status_code == 200, exported.text
    return output_id, exported.json()["manifest"]


def _set_provider(job_id, provider, model):
    with job_repository._connect() as db:
        db.execute("UPDATE generation_jobs SET provider=?, model=? WHERE job_id=?", (provider, model, job_id))


def _disclosure_view(job_id, output_id):
    listing = client.get(f"/v1/generation-jobs/{job_id}/outputs", headers=auth()).json()["data"][0]
    review = client.get(f"/v1/generation-jobs/{job_id}/outputs/{output_id}/review", headers=auth()).json()["output"]
    return listing, review


def test_mock_provider_outputs_are_not_labelled_as_ai_generated(linked_output_env):
    job_id = linked_output_env["job_id"]
    output_id, manifest = _link_and_approve(job_id)
    listing, review = _disclosure_view(job_id, output_id)
    assert listing["is_ai_generated"] is False and listing["provider"] == "mock"
    assert review["is_ai_generated"] is False
    assert manifest["is_ai_generated"] is False and [o["is_ai_generated"] for o in manifest["outputs"]] == [False]


@pytest.mark.parametrize("provider,model", [("fashn", "tryon-v1.6"), ("some-new-provider", "x"), ("", None)])
def test_real_unknown_and_missing_providers_are_labelled_as_ai_generated(linked_output_env, provider, model):
    job_id = linked_output_env["job_id"]
    _set_provider(job_id, provider, model)
    output_id, manifest = _link_and_approve(job_id)
    listing, review = _disclosure_view(job_id, output_id)
    assert listing["is_ai_generated"] is True and review["is_ai_generated"] is True
    assert manifest["is_ai_generated"] is True and [o["is_ai_generated"] for o in manifest["outputs"]] == [True]
    assert listing["provider"] == provider


def test_disclosure_helper_defaults_to_disclosing():
    from app.ai_disclosure import is_ai_generated_provider
    assert is_ai_generated_provider("mock") is False and is_ai_generated_provider(" MOCK ") is False
    for value in ("fashn", "Fashn", "other", "", None, "   "):
        assert is_ai_generated_provider(value) is True, value
