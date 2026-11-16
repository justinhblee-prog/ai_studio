"""R-050 (mock): image -> short video jobs: contract, motions, sizes, frame QC, inputs from the library, roles, limits."""
import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from app import config, video_jobs
from app.main import app
from tests.test_photo_steps_api import auth, env  # noqa: F401  (wa: owner a + viewer c, wb: owner b)
from tests.test_workspace_library import glb

client = TestClient(app)


def pattern(seed=0, size=(300, 400)):
    img = Image.new("RGB", size, (40 + seed * 30 % 200, 90, 160))
    d = ImageDraw.Draw(img)
    for i in range(0, size[0], 20):
        d.line((i, 0, size[0] - i, size[1]), fill=(250 - seed * 20 % 200, 200, 40 + i % 200), width=6)
    d.ellipse((60 + seed * 10, 100, 220, 300), fill=(30, 200 - seed * 15 % 150, 90))
    buf = io.BytesIO(); img.save(buf, format="PNG"); return buf.getvalue()


def solid(color=(120, 120, 120)):
    buf = io.BytesIO(); Image.new("RGB", (200, 300), color).save(buf, format="PNG"); return buf.getvalue()


def item(content, kind="render", name="cut", ws="wa", who="a"):
    r = client.post(f"/v1/workspaces/{ws}/library", headers=auth(who), data={"kind": kind, "name": name, "rights_confirmed": "true"},
                    files={"file": (f"{name}.png", content, "image/png")})
    assert r.status_code == 201, r.text
    return r.json()["item_id"]


def make(body, who="a", ws="wa"):
    return client.post(f"/v1/workspaces/{ws}/video-jobs", headers=auth(who), json=body)


def stored(env, asset_id):
    return next((env["tmp"] / "private").glob(f"{asset_id}.*"))


def test_a_video_is_made_from_library_images_and_delivered_as_an_animated_picture(env):
    ids = [item(pattern(1), name="a"), item(pattern(2), name="b")]
    r = make({"input_item_ids": ids})
    assert r.status_code == 201, r.text
    job = r.json()
    assert job["status"] == "succeeded" and job["provider"] == "mock" and job["aspect"] == "9:16" and job["duration_seconds"] == 6 and job["error_code"] is None
    assert job["qc"]["passed"] is True and job["qc"]["frames"] == 48 and job["input_item_ids"] == ids and job["finished_at"]
    with Image.open(stored(env, job["output_asset_id"])) as out:
        assert out.format == "WEBP" and out.size == (270, 480) and out.n_frames == 48 and out.info.get("loop") == 0
    prov = client.get(f"/v1/assets/{job['output_asset_id']}/provenance", headers=auth("a")).json()
    event = next(p for p in (prov["items"] if isinstance(prov, dict) else prov) if p["event_type"] == "asset.video_output")
    details = event["details"] if "details" in event else __import__("json").loads(event["details_json"])
    assert details["mode"] == "mock" and details["is_ai_generated"] is False and details["job_id"] == job["job_id"]
    assert client.get(f"/v1/workspaces/wa/video-jobs/{job['job_id']}", headers=auth("c")).json()["status"] == "succeeded", "a viewer can read"


@pytest.mark.parametrize("aspect, size", [("9:16", (270, 480)), ("4:5", (320, 400)), ("16:9", (480, 270))])
def test_the_three_aspects_give_their_sizes(env, aspect, size):
    job = make({"input_item_ids": [item(pattern(3))], "aspect": aspect, "duration_seconds": 3}).json()
    with Image.open(stored(env, job["output_asset_id"])) as out:
        assert out.size == size and out.n_frames == 24


@pytest.mark.parametrize("seconds", [3, 5, 8])
def test_the_length_sets_the_frame_count(env, seconds):
    job = make({"input_item_ids": [item(pattern(4))], "duration_seconds": seconds}).json()
    assert job["qc"]["frames"] == seconds * video_jobs.FPS


def test_each_motion_moves_differently_and_the_same_request_gives_the_same_picture(env):
    images = [Image.open(io.BytesIO(pattern(5))).convert("RGB"), Image.open(io.BytesIO(pattern(6))).convert("RGB")]
    sets = {m: video_jobs.make_frames(images, "9:16", 4, m) for m in video_jobs.MOTIONS}
    mid = {m: f[12].tobytes() for m, f in sets.items()}   # inside the first picture, late enough for the crossfade to have started (the very first frames of a zoom and a crossfade are the same)
    assert len(set(mid.values())) == 3, "zoom, pan and crossfade are three different moves"
    again = video_jobs.make_frames(images, "9:16", 4, "pan")
    assert [f.tobytes() for f in again] == [f.tobytes() for f in sets["pan"]], "deterministic"
    assert sets["slow_zoom"][0].tobytes() != sets["slow_zoom"][-1].tobytes(), "it really moves"


def test_a_blank_result_fails_the_qc_and_nothing_is_delivered(env):
    before = len(client.get("/v1/assets?workspace_id=wa&kind=image", headers=auth("a")).json()["items"])
    job = make({"input_item_ids": [item(solid(), name="flat")], "duration_seconds": 3}).json()
    assert job["status"] == "failed" and job["error_code"] == "QC_FAILED" and job["output_asset_id"] is None
    assert job["qc"]["passed"] is False and job["qc"]["blank_frames"] == 24
    assert any(c["check"] == "blank_frames" and c["level"] == "fail" for c in job["qc"]["checks"])
    after = client.get("/v1/assets?workspace_id=wa&kind=image", headers=auth("a")).json()["items"]
    assert len(after) == before + 1, "only the library item itself; no video file was stored"


def test_qc_unit_checks_size_count_flicker_and_static_pictures():
    base = Image.open(io.BytesIO(pattern(7))).convert("RGB").resize((270, 480))
    good = video_jobs.make_frames([Image.open(io.BytesIO(pattern(7))).convert("RGB")], "9:16", 3, "slow_zoom")
    ok = video_jobs.qc_frames(good, "9:16", 24)
    assert ok["passed"] is True and all(c["level"] == "ok" for c in ok["checks"])
    wrong_size = video_jobs.qc_frames([base.resize((100, 100))] * 24, "9:16", 24)
    assert wrong_size["passed"] is False and next(c for c in wrong_size["checks"] if c["check"] == "size")["level"] == "fail"
    short = video_jobs.qc_frames(good[:10], "9:16", 24)
    assert short["passed"] is False and next(c for c in short["checks"] if c["check"] == "frame_count")["level"] == "fail"
    dark, bright = Image.eval(base, lambda v: v // 4), Image.eval(base, lambda v: min(255, v + 90))
    flicker = video_jobs.qc_frames([dark, bright] * 12, "9:16", 24)
    assert flicker["passed"] is True and next(c for c in flicker["checks"] if c["check"] == "brightness_flicker")["level"] == "warn", "a warning, not a failure"
    static = video_jobs.qc_frames([base] * 24, "9:16", 24)
    assert static["passed"] is True and next(c for c in static["checks"] if c["check"] == "static_picture")["level"] == "warn" and static["duplicate_ratio"] == 1.0


@pytest.mark.parametrize("body", [
    {"input_item_ids": []}, {"input_item_ids": ["wli_" + str(i) for i in range(9)]}, {"input_item_ids": ["wli_x"], "aspect": "1:1"},
    {"input_item_ids": ["wli_x"], "duration_seconds": 2}, {"input_item_ids": ["wli_x"], "duration_seconds": 9}, {"input_item_ids": ["wli_x"], "motion": "spin"},
    {"input_item_ids": ["wli_x"], "extra": 1}, {},
])
def test_bad_requests_are_refused(env, body):
    assert make(body).status_code == 422
    assert client.get("/v1/workspaces/wa/video-jobs", headers=auth("a")).json()["items"] == []


def test_inputs_must_be_real_distinct_image_items_of_this_workspace(env):
    good = item(pattern(8), name="g")
    three_d = client.post("/v1/workspaces/wa/library", headers=auth("a"), data={"kind": "3d", "name": "chair"}, files={"file": ("c.glb", glb(), "model/gltf-binary")}).json()["item_id"]
    other = item(pattern(9), ws="wb", who="b")
    assert make({"input_item_ids": ["wli_doesnotexist"]}).status_code == 404
    assert make({"input_item_ids": [good, other]}).status_code == 404, "another workspace's item"
    r3d = make({"input_item_ids": [three_d]})
    assert r3d.status_code == 422 and r3d.json()["detail"]["code"] == "VIDEO_INPUT_KIND"
    assert make({"input_item_ids": [good, good]}).status_code == 422
    assert client.get("/v1/workspaces/wa/video-jobs", headers=auth("a")).json()["items"] == [], "no refused request left a job behind"


def test_roles_and_isolation(env):
    ids = [item(pattern(1))]
    assert make({"input_item_ids": ids}, who="c").status_code == 403, "a viewer cannot make videos"
    assert client.post("/v1/workspaces/wa/video-jobs", json={"input_item_ids": ids}).status_code == 401
    job = make({"input_item_ids": ids, "duration_seconds": 3}).json()
    assert client.get(f"/v1/workspaces/wb/video-jobs/{job['job_id']}", headers=auth("b")).status_code == 404
    assert client.get("/v1/workspaces/wa/video-jobs", headers=auth("b")).status_code in (403, 404)
    assert client.delete(f"/v1/workspaces/wa/video-jobs/{job['job_id']}", headers=auth("c")).status_code == 403
    assert client.get("/v1/workspaces/wa/video-jobs").status_code == 401


def test_limits_and_a_real_provider_is_not_connected(env, monkeypatch):
    ids = [item(pattern(2))]
    monkeypatch.setattr(config, "VIDEO_DAILY_LIMIT", 1)
    assert make({"input_item_ids": ids, "duration_seconds": 3}).status_code == 201
    limited = make({"input_item_ids": ids, "duration_seconds": 3})
    assert limited.status_code == 429 and limited.json()["detail"]["code"] == "VIDEO_DAILY_LIMIT" and limited.json()["detail"]["used"] == 1
    monkeypatch.setattr(config, "PROVIDER_MODE", "fashn")
    closed = make({"input_item_ids": ids})
    assert closed.status_code == 409 and closed.json()["detail"]["code"] == "VIDEO_PROVIDER_NOT_CONNECTED"


def test_deleting_a_job_removes_its_output_file(env):
    job = make({"input_item_ids": [item(pattern(3))], "duration_seconds": 3}).json()
    path = stored(env, job["output_asset_id"])
    assert path.exists()
    assert client.delete(f"/v1/workspaces/wa/video-jobs/{job['job_id']}", headers=auth("a")).status_code == 204
    assert client.get(f"/v1/workspaces/wa/video-jobs/{job['job_id']}", headers=auth("a")).status_code == 404
    assert client.get(f"/v1/assets/{job['output_asset_id']}", headers=auth("a")).status_code == 404 and not path.exists()
    assert client.delete(f"/v1/workspaces/wa/video-jobs/{job['job_id']}", headers=auth("a")).status_code == 404
