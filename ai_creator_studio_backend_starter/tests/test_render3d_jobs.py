"""R-ENGINE-10: the own3d ``render3d`` job (mock): flag closed by default, request checks, pictures from several angles, rotating MP4, roles, limits, failure states."""
import hashlib
import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import config, garments, render3d_jobs, render3d_soft, video_mp4
from app.main import app
from tests.test_photo_steps_api import auth, env  # noqa: F401  (wa: owner a + viewer c, wb: owner b)
from tests.test_video_mp4 import ffmpeg  # noqa: F401

client = TestClient(app)
BASE = "/v1/workspaces/wa/render3d-jobs"
FAST = {"sex": "female", "mp4": False}                      # pictures only: no ffmpeg needed


@pytest.fixture
def opened(env, monkeypatch):
    monkeypatch.setattr(config, "RENDER3D_ENABLED", True)
    return env


def create(body, who="a", ws="wa"):
    return client.post(f"/v1/workspaces/{ws}/render3d-jobs", headers=auth(who), json=body)


def poll(job_id, who="a", ws="wa"):
    r = client.get(f"/v1/workspaces/{ws}/render3d-jobs/{job_id}", headers=auth(who))
    assert r.status_code == 200, r.text
    return r.json()


def stored(env, asset_id):
    return next((env["tmp"] / "private").glob(f"{asset_id}.*"))


def test_the_flag_is_off_by_default_and_a_closed_feature_answers_409_after_the_usual_checks(env):
    assert config.RENDER3D_ENABLED is False
    r = create(FAST)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "RENDER3D_CLOSED"
    assert client.get(BASE, headers=auth("a")).status_code == 409 and client.get(BASE + "/r3d_x", headers=auth("a")).status_code == 409
    assert client.post(BASE, json=FAST).status_code == 401, "sign-in is checked first"
    assert create(FAST, who="b").status_code in (403, 404), "so is membership"
    assert create(FAST, who="c").status_code == 403, "and the role (a viewer cannot make jobs)"


def test_a_job_is_queued_then_polled_to_five_pictures_that_differ_and_are_not_blank(opened):
    r = create({**FAST, "garments": [{"kind": "dress", "id": "sample"}], "measurements": {"height_cm": 170, "chest_cm": 92}})
    assert r.status_code == 202, r.text
    first = r.json()
    assert first["status"] == "queued" and first["job_id"].startswith("r3d_") and first["images"] == [] and first["mp4"] is None and first["engine"] == "own3d-mock"
    job = poll(first["job_id"])
    assert job["status"] == "succeeded" and job["error_code"] is None and job["finished_at"] and job["mp4"] is None
    assert [i["angle"] for i in job["images"]] == [0, 45, 90, 180, 270]
    assert job["qc"]["passed"] is True and all(s >= render3d_jobs.MIN_PAINTED_SHARE for s in job["qc"]["painted_share"].values()) and job["qc"]["fits"][0]["penetrations"] == 0
    digests = set()
    for image in job["images"]:
        meta = client.get(f"/v1/assets/{image['asset_id']}", headers=auth("a")).json()
        assert meta["media_type"] == "image/png"
        with Image.open(stored(opened, image["asset_id"])) as png:
            assert png.size == render3d_jobs.STILL_SIZE
        digests.add(hashlib.sha256(stored(opened, image["asset_id"]).read_bytes()).hexdigest())
    assert len(digests) == 5, "every angle is a different picture"
    assert poll(first["job_id"], who="c")["status"] == "succeeded", "a viewer can read"
    assert [j["job_id"] for j in client.get(BASE, headers=auth("a")).json()["items"]] == [first["job_id"]]


def test_the_same_request_draws_the_same_pixels_and_garments_and_body_change_the_picture(opened):
    def front(body):
        job = poll(create({**body, "angles": [0]}).json()["job_id"])
        return stored(opened, job["images"][0]["asset_id"]).read_bytes()
    plain, again = front(FAST), front(FAST)
    assert plain == again, "deterministic"
    assert front({**FAST, "garments": [{"kind": "jacket", "id": "sample"}]}) != plain
    assert front({**FAST, "measurements": {"height_cm": 190}}) != plain
    assert front({**FAST, "sex": "male"}) != plain
    assert front({**FAST, "bg": "studio"}) != plain


@pytest.mark.parametrize("bad, code", [
    ({**FAST, "measurements": {"height_cm": 100}}, "RENDER3D_MEASUREMENT_INVALID"),
    ({**FAST, "measurements": {"sleeve_cm": 50}}, "RENDER3D_MEASUREMENT_INVALID"),
    ({**FAST, "garments": [{"kind": "dress", "id": "sample"}, {"kind": "top", "id": "sample"}]}, "RENDER3D_GARMENT_CONFLICT"),
    ({**FAST, "garments": [{"kind": "top", "id": "sample"}, {"kind": "top", "id": "sample"}]}, "RENDER3D_GARMENT_CONFLICT"),
    ({**FAST, "garments": [{"kind": "skirt", "id": "sample"}, {"kind": "bottom", "id": "sample"}]}, "RENDER3D_GARMENT_CONFLICT"),
    ({**FAST, "garments": [{"kind": "top", "id": "my-library-shirt"}]}, "RENDER3D_GARMENT_UNKNOWN"),
    ({**FAST, "garments": [{"kind": "top", "id": "sample-top-male"}]}, "RENDER3D_GARMENT_UNKNOWN"),
])
def test_bad_requests_are_refused_before_anything_is_made(opened, bad, code):
    r = create(bad)
    assert r.status_code == 422 and r.json()["detail"]["code"] == code
    assert client.get(BASE, headers=auth("a")).json()["items"] == []


@pytest.mark.parametrize("bad", [{"angles": []}, {"angles": [0, 0]}, {"angles": [10]}, {"angles": [360]}, {"angles": list(range(0, 135, 15))}, {"sex": "robot"}, {"bg": "red"},
                                 {"garments": [{"kind": "hat"}]}, {"extra": 1}, {"garments": [{"kind": "top"}] * 4}])
def test_malformed_bodies_are_422(opened, bad):
    assert create({**FAST, **bad}).status_code == 422


def test_other_angles_and_all_kinds_with_a_compatible_set_work(opened):
    job = poll(create({**FAST, "garments": [{"kind": "jacket"}, {"kind": "skirt"}], "angles": [15, 135, 345]}).json()["job_id"])
    assert job["status"] == "succeeded" and [i["angle"] for i in job["images"]] == [15, 135, 345]


def test_a_viewer_cannot_make_a_job_and_another_workspace_cannot_read_it(opened):
    assert create(FAST, who="c").status_code == 403
    job_id = create(FAST).json()["job_id"]
    assert client.get(f"/v1/workspaces/wb/render3d-jobs/{job_id}", headers=auth("b")).status_code == 404
    assert client.get(f"/v1/workspaces/wa/render3d-jobs/{job_id}", headers=auth("b")).status_code in (403, 404)


def test_the_daily_limit_stops_a_workspace(opened, monkeypatch):
    monkeypatch.setattr(config, "RENDER3D_DAILY_LIMIT", 1)
    assert create(FAST).status_code == 202
    r = create(FAST)
    assert r.status_code == 429 and r.json()["detail"]["code"] == "RENDER3D_DAILY_LIMIT"


def test_a_garment_that_cannot_be_fitted_fails_the_job_and_stores_nothing(opened, monkeypatch):
    def refuse(*args, **kwargs):
        raise garments.GarmentError(["the fitted garment would pass through the body at 3 vertices"])
    monkeypatch.setattr(render3d_jobs, "deform_garment", refuse)
    job = poll(create({**FAST, "garments": [{"kind": "top"}]}).json()["job_id"])
    assert job["status"] == "failed" and job["error_code"] == "FIT_REFUSED" and job["images"] == [] and job["mp4"] is None
    assert len(list((opened["tmp"] / "private").glob("*.png"))) == 1, "only the fixture's own upload exists: the failed job stored no picture"


def test_a_blank_picture_fails_the_quality_check_and_is_not_delivered(opened, monkeypatch):
    monkeypatch.setattr(render3d_soft, "render", lambda tris, angle, size=(360, 640), **kw: Image.new("RGB", size, kw.get("background", (242, 242, 242))))
    job = poll(create(FAST).json()["job_id"])
    assert job["status"] == "failed" and job["error_code"] == "QC_FAILED" and job["images"] == [] and job["qc"]["passed"] is False


def test_an_unexpected_error_ends_the_job_as_failed_without_echoing_the_cause(opened, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("secret internal detail")
    monkeypatch.setattr(render3d_jobs, "build_scene", boom)
    job = poll(create(FAST).json()["job_id"])
    assert job["status"] == "failed" and job["error_code"] == "RENDER_FAILED" and "secret" not in str(job)


def test_without_ffmpeg_an_mp4_request_is_refused_loudly_and_nothing_is_stored(opened, monkeypatch):
    monkeypatch.setattr(video_mp4, "find_ffmpeg", lambda: None)
    r = create({"sex": "male", "mp4": True})
    assert r.status_code == 503 and r.json()["detail"]["code"] == "FFMPEG_MISSING"
    assert client.get(BASE, headers=auth("a")).json()["items"] == []
    assert create({"sex": "male", "mp4": False}).status_code == 202, "pictures alone need no ffmpeg"


def test_the_rotating_mp4_is_a_real_five_second_video_saved_as_an_asset(opened, ffmpeg):
    job = poll(create({"sex": "female", "garments": [{"kind": "dress"}], "angles": [0, 90]}).json()["job_id"])
    assert job["status"] == "succeeded", job
    mp4 = job["mp4"]
    assert mp4["seconds"] == 5 and mp4["size"] == [720, 1280] and mp4["cuts"] == 8
    asset = client.get(f"/v1/assets/{mp4['asset_id']}", headers=auth("a")).json()
    assert asset["asset_kind"] == "video" and asset["media_type"] == "video/mp4"
    probe = video_mp4.probe_mp4(stored(opened, mp4["asset_id"]).read_bytes())
    assert (probe["width"], probe["height"], probe["frames"], probe["codec"], probe["faststart"]) == (720, 1280, 120, "avc1", True)
    assert "ai_generated=false" in probe["comment"] and job["qc"]["mp4"]["passed"] is True


@pytest.mark.parametrize("sql", ["SELECT COUNT(*) AS n FROM render3d_jobs WHERE workspace_id=? AND created_at>=?",
                                 "SELECT * FROM render3d_jobs WHERE workspace_id=? ORDER BY created_at DESC, job_id LIMIT 100"])
def test_the_workspace_queries_of_the_job_table_use_its_index(sql):
    """B-11: the per-workspace day count and list are answered through the index, not by scanning the table."""
    import sqlite3
    db = sqlite3.connect(":memory:")
    render3d_jobs._init(db)
    plan = [r[-1] for r in db.execute("EXPLAIN QUERY PLAN " + sql, ("ws", "2026-01-01")[:sql.count("?")]).fetchall()]
    assert any("USING" in step and "INDEX" in step for step in plan) and not any(step.startswith("SCAN render3d_jobs") for step in plan), plan
