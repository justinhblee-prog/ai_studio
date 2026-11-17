"""Lane 4: the video job API with ``output_format: mp4`` -- a real H.264 file saved as a ``video`` asset, QC by decoding, cover picture, no silent fallback."""
import sqlite3

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import video_jobs, video_mp4
from app.main import app
from tests.test_photo_steps_api import auth, env  # noqa: F401
from tests.test_video_jobs import item, make, pattern
from tests.test_video_mp4 import ffmpeg  # noqa: F401

client = TestClient(app)
MP4 = {"output_format": "mp4", "duration_seconds": 5}


def two_items():
    return [item(pattern(1), name="a"), item(pattern(2), name="b")]


def stored_bytes(env, asset_id):
    return next((env["tmp"] / "private").glob(f"{asset_id}.*")).read_bytes()


def test_an_mp4_job_makes_a_real_video_saved_as_a_video_asset(env, ffmpeg):
    ids = two_items()
    r = make({"input_item_ids": ids, "aspect": "16:9", "motion": "crossfade", **MP4})
    assert r.status_code == 201, r.text
    job = r.json()
    assert job["status"] == "succeeded" and job["output_format"] == "mp4" and job["error_code"] is None and job["provider"] == "mock"
    assert job["qc"]["passed"] is True and job["qc"]["frames"] == 120, job["qc"]
    asset = client.get(f"/v1/assets/{job['output_asset_id']}", headers=auth("a")).json()
    assert asset["asset_kind"] == "video" and asset["media_type"] == "video/mp4" and asset["original_filename"].endswith(".mp4")
    content = stored_bytes(env, job["output_asset_id"])
    probe = video_mp4.probe_mp4(content)
    assert (probe["width"], probe["height"], probe["frames"], probe["codec"], probe["faststart"]) == (1280, 720, 120, "avc1", True)
    assert abs(probe["duration_seconds"] - 5) <= 0.1 and f"job={job['job_id']}" in probe["comment"] and "ai_generated=false" in probe["comment"]
    provenance = client.get(f"/v1/assets/{job['output_asset_id']}/provenance", headers=auth("a")).text
    assert "source_asset_ids" in provenance and '"output_format":"mp4"' in provenance.replace(" ", "") and "asset.video_output" in provenance


def test_the_default_output_is_still_the_animated_picture(env):
    job = make({"input_item_ids": two_items()}).json()
    assert job["output_format"] == "webp" and job["status"] == "succeeded"
    assert client.get(f"/v1/assets/{job['output_asset_id']}", headers=auth("a")).json()["media_type"] == "image/webp"


@pytest.mark.parametrize("seconds", [3, 6, 12])
def test_an_mp4_must_be_5_10_or_15_seconds_and_nothing_is_stored_when_it_is_not(env, seconds):
    r = make({"input_item_ids": two_items(), "output_format": "mp4", "duration_seconds": seconds})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "VIDEO_DURATION_INVALID"
    assert client.get("/v1/workspaces/wa/video-jobs", headers=auth("a")).json()["items"] == []


def test_without_ffmpeg_the_job_fails_loudly_and_does_not_fall_back_to_a_picture(env, monkeypatch):
    monkeypatch.setattr(video_mp4, "find_ffmpeg", lambda: None)
    r = make({"input_item_ids": two_items(), **MP4})
    assert r.status_code == 503 and r.json()["detail"]["code"] == "FFMPEG_MISSING"
    assert client.get("/v1/workspaces/wa/video-jobs", headers=auth("a")).json()["items"] == []


def test_a_video_that_fails_the_decode_check_is_not_delivered_and_retry_makes_a_new_mp4_job(env, ffmpeg, monkeypatch):
    real_qc = video_mp4.qc_mp4
    monkeypatch.setattr(video_mp4, "qc_mp4", lambda *a, **k: {**real_qc(*a, **k), "passed": False})
    failed = make({"input_item_ids": two_items(), **MP4}).json()
    assert failed["status"] == "failed" and failed["error_code"] == "QC_FAILED" and failed["output_asset_id"] is None and failed["output_format"] == "mp4"
    assert client.get("/v1/assets", headers=auth("a"), params={"workspace_id": "wa", "kind": "video"}).json()["items"] == [], "nothing was stored"
    monkeypatch.setattr(video_mp4, "qc_mp4", real_qc)
    again = client.post(f"/v1/workspaces/wa/video-jobs/{failed['job_id']}/retry", headers=auth("a"))
    assert again.status_code == 201 and again.json()["status"] == "succeeded" and again.json()["output_format"] == "mp4" and again.json()["job_id"] != failed["job_id"]


def test_the_cover_picture_is_a_frame_of_the_video_for_members_only(env, ffmpeg):
    job = make({"input_item_ids": two_items(), "aspect": "9:16", **MP4}).json()
    url = f"/v1/workspaces/wa/video-jobs/{job['job_id']}/poster"
    r = client.get(url, headers=auth("a"), params={"max_side": 200})
    assert r.status_code == 200 and r.headers["content-type"] == "image/png" and r.headers["cache-control"] == "private, no-store"
    from io import BytesIO
    cover = Image.open(BytesIO(r.content))
    assert max(cover.size) == 200 and cover.size[0] < cover.size[1], "a 9:16 video gives a tall cover, longest side 200"
    assert client.get(url, headers=auth("c")).status_code == 200, "a viewer of the workspace may see it"
    assert client.get(url, headers=auth("b")).status_code in (403, 404), "another workspace's owner may not"
    assert client.get(url, headers=auth("a"), params={"at": 1.5}).status_code == 422
    assert client.get(url, headers=auth("a"), params={"max_side": 8}).status_code == 422


def test_a_picture_job_has_no_cover_and_an_unknown_job_is_not_found(env):
    job = make({"input_item_ids": two_items()}).json()
    r = client.get(f"/v1/workspaces/wa/video-jobs/{job['job_id']}/poster", headers=auth("a"))
    assert r.status_code == 404 and r.json()["detail"]["code"] == "VIDEO_POSTER_NOT_AVAILABLE"
    assert client.get("/v1/workspaces/wa/video-jobs/vid_nope/poster", headers=auth("a")).status_code == 404


def test_the_finished_mp4_can_be_filed_in_the_library_as_a_render(env, ffmpeg):
    job = make({"input_item_ids": two_items(), **MP4}).json()
    r = client.post("/v1/workspaces/wa/library/from-job", headers=auth("a"), json={"job_id": job["job_id"]})
    assert r.status_code == 201, r.text
    assert r.json()["kind"] == "render" and r.json()["media_type"] == "video/mp4" and r.json()["attrs"]["service"] == "video"


def test_a_job_table_made_before_mp4_output_gets_its_new_column_and_keeps_its_rows():
    db = sqlite3.connect(":memory:")            # a plain connection (tuples), as other modules' tests use it
    db.execute("""CREATE TABLE video_jobs (job_id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, owner_id TEXT NOT NULL, status TEXT NOT NULL, provider TEXT NOT NULL,
        aspect TEXT NOT NULL, duration_seconds INTEGER NOT NULL, motion TEXT NOT NULL, instruction TEXT, input_item_ids_json TEXT NOT NULL,
        output_asset_id TEXT, qc_json TEXT, error_code TEXT, created_at TEXT NOT NULL, finished_at TEXT)""")
    db.execute("INSERT INTO video_jobs VALUES ('vid_old','wa','u','succeeded','mock','9:16',6,'pan',NULL,'[]',NULL,NULL,NULL,'2026-01-01',NULL)")
    video_jobs._init(db)
    video_jobs._init(db)          # and a second start does nothing
    assert db.execute("SELECT output_format FROM video_jobs WHERE job_id='vid_old'").fetchone()[0] == "webp"
