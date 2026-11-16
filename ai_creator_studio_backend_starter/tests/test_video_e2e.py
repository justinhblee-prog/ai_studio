"""R-073: video end to end with the mock provider: library pictures (including rotation cuts) -> job -> frame QC -> stored result -> review -> library; every aspect and length; failure and retry."""
import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import config
from app.main import app
from tests.test_photo_steps_api import auth, env  # noqa: F401
from tests.test_video_jobs import item, make, pattern, solid, stored

client = TestClient(app)
SIZES = {"9:16": (270, 480), "4:5": (320, 400), "16:9": (480, 270)}


def rotation_cuts(n=4):
    """Pictures that differ from each other like turntable cuts of one product (the server cannot render a 3D model; the cuts come from the studio)."""
    return [item(pattern(i + 1), name=f"cut{i}") for i in range(n)]


@pytest.mark.parametrize("aspect", list(SIZES))
@pytest.mark.parametrize("seconds", [5, 10, 15])
def test_every_aspect_and_length_gives_the_right_picture(env, aspect, seconds):
    r = make({"input_item_ids": rotation_cuts(3), "aspect": aspect, "duration_seconds": seconds})
    assert r.status_code == 201, r.text
    job = r.json()
    assert job["status"] == "succeeded" and job["qc"]["passed"] is True and job["qc"]["frames"] == seconds * 8
    with Image.open(stored(env, job["output_asset_id"])) as out:
        assert out.format == "WEBP" and out.size == SIZES[aspect] and out.n_frames == seconds * 8


def test_the_whole_chain_cuts_to_video_to_review_to_library(env):
    cuts = rotation_cuts(4)
    job = make({"input_item_ids": cuts, "aspect": "9:16", "duration_seconds": 5}).json()
    assert job["status"] == "succeeded"
    filed = client.post("/v1/workspaces/wa/library/from-job", headers=auth("a"), json={"job_id": job["job_id"], "name": "회전 영상"})
    assert filed.status_code in (200, 201), filed.text
    it = filed.json()
    assert it["kind"] == "render" and it["asset_id"] == job["output_asset_id"] and it["attrs"]["service"] == "video" and len(it["attrs"]["source_asset_ids"]) == 4
    rv = client.post("/v1/workspaces/wa/reviews", headers=auth("a"), json={"asset_id": job["output_asset_id"]})
    assert rv.status_code == 201
    assert client.post(f"/v1/workspaces/wa/reviews/{rv.json()['review_id']}/approve", headers=auth("a"), json={}).status_code == 200
    status = client.get("/v1/workspaces/wa/reviews/status", headers=auth("c"), params={"asset_ids": job["output_asset_id"]}).json()["items"][0]
    assert status["status"] == "approved" and status["exportable"] is True
    work = client.post("/v1/workspaces/wa/work-items", headers=auth("a"), json={"kind": "video", "title": "회전 영상", "status": "done", "asset_ids": [job["output_asset_id"]]}).json()
    assert work["asset_review_summary"] == "ok"
    assert client.get("/v1/workspaces/wa/video-jobs", headers=auth("c")).json()["items"][0]["job_id"] == job["job_id"]


def test_a_failed_video_stores_nothing_and_a_retry_is_a_new_job_with_the_same_settings(env):
    flat = item(solid(), name="flat")
    bad = make({"input_item_ids": [flat], "aspect": "4:5", "duration_seconds": 5, "motion": "pan"}).json()
    assert bad["status"] == "failed" and bad["error_code"] == "QC_FAILED" and bad["output_asset_id"] is None
    retried = client.post(f"/v1/workspaces/wa/video-jobs/{bad['job_id']}/retry", headers=auth("a"))
    assert retried.status_code == 201, retried.text
    again = retried.json()
    assert again["job_id"] != bad["job_id"] and (again["aspect"], again["duration_seconds"], again["motion"], again["input_item_ids"]) == ("4:5", 5, "pan", [flat])
    assert again["status"] == "failed", "the same flat picture fails the same check"
    jobs = client.get("/v1/workspaces/wa/video-jobs", headers=auth("a")).json()["items"]
    assert len(jobs) == 2 and bad["job_id"] in {j["job_id"] for j in jobs}, "the failed job stays as a record"


def test_retry_and_cancel_rules(env):
    ok = make({"input_item_ids": rotation_cuts(2), "duration_seconds": 3}).json()
    r = client.post(f"/v1/workspaces/wa/video-jobs/{ok['job_id']}/retry", headers=auth("a"))
    assert r.status_code == 409 and r.json()["detail"]["code"] == "VIDEO_RETRY_NOT_FAILED"
    c = client.post(f"/v1/workspaces/wa/video-jobs/{ok['job_id']}/cancel", headers=auth("a"))
    assert c.status_code == 409 and c.json()["detail"]["code"] == "VIDEO_NOT_CANCELLABLE", "the mock finishes inside the request: nothing to cancel"
    for path in ("retry", "cancel"):
        assert client.post(f"/v1/workspaces/wa/video-jobs/{ok['job_id']}/{path}", headers=auth("c")).status_code == 403, "a viewer cannot"
        assert client.post(f"/v1/workspaces/wb/video-jobs/{ok['job_id']}/{path}", headers=auth("b")).status_code == 404, "another workspace"
        assert client.post(f"/v1/workspaces/wa/video-jobs/vid_nope/{path}", headers=auth("a")).status_code == 404
        assert client.post(f"/v1/workspaces/wa/video-jobs/{ok['job_id']}/{path}").status_code == 401


def test_a_retry_counts_toward_the_daily_limit_and_the_generate_budget(env, monkeypatch):
    bad = make({"input_item_ids": [item(solid(), name="flat")], "duration_seconds": 3}).json()
    monkeypatch.setattr(config, "VIDEO_DAILY_LIMIT", 1)
    r = client.post(f"/v1/workspaces/wa/video-jobs/{bad['job_id']}/retry", headers=auth("a"))
    assert r.status_code == 429 and r.json()["detail"]["code"] == "VIDEO_DAILY_LIMIT"
    monkeypatch.setattr(config, "VIDEO_DAILY_LIMIT", 20)
    monkeypatch.setattr(config, "RATE_LIMITS_ENABLED", True)
    monkeypatch.setattr(config, "RATE_GENERATE_USER_PER_MINUTE", 1)
    assert client.post(f"/v1/workspaces/wa/video-jobs/{bad['job_id']}/retry", headers=auth("a")).status_code == 201
    assert client.post(f"/v1/workspaces/wa/video-jobs/{bad['job_id']}/retry", headers=auth("a")).status_code == 429


def test_lengths_outside_3_to_15_and_a_real_provider_are_refused(env, monkeypatch):
    ids = rotation_cuts(2)
    for seconds in (2, 16):
        assert make({"input_item_ids": ids, "duration_seconds": seconds}).status_code == 422
    monkeypatch.setattr(config, "PROVIDER_MODE", "fashn")
    assert make({"input_item_ids": ids, "duration_seconds": 5}).json()["detail"]["code"] == "VIDEO_PROVIDER_NOT_CONNECTED"
