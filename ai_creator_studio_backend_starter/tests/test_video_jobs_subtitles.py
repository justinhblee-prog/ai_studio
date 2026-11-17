"""Lane 4 / E-08c 2/2: the video job API with ``subtitles`` (MP4 only): checks before anything is made, the text really in the picture, retry keeps them."""
import sqlite3
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import video_jobs, video_mp4, video_subtitles
from app.main import app
from tests.test_photo_steps_api import auth, env  # noqa: F401
from tests.test_video_jobs import item, make, pattern
from tests.test_video_mp4 import ffmpeg  # noqa: F401
from tests.test_video_subtitles import font  # noqa: F401

client = TestClient(app)
KOREAN = "새 컬렉션이 도착했습니다"
CUE = {"text": KOREAN, "start": 1.0, "end": 3.0}


def body(**extra):
    return {"input_item_ids": [item(pattern(1), name="a"), item(pattern(2), name="b")], "output_format": "mp4", "duration_seconds": 5, **extra}


def nothing_stored():
    return client.get("/v1/workspaces/wa/video-jobs", headers=auth("a")).json()["items"] == []


def lit(job_id, at):
    r = client.get(f"/v1/workspaces/wa/video-jobs/{job_id}/poster", headers=auth("a"), params={"at": at, "max_side": 1280})
    assert r.status_code == 200, r.text
    frame = Image.open(BytesIO(r.content)).convert("L")
    w, h = frame.size
    return sum(frame.crop((0, int(h * 0.78), w, int(h * 0.95))).histogram()[236:])


def test_a_job_with_subtitles_shows_the_text_only_while_the_cue_runs(env, ffmpeg, font):
    job = make(body(subtitles=[CUE])).json()
    assert job["status"] == "succeeded" and job["subtitles"] == [CUE] and job["output_format"] == "mp4" and job["qc"]["passed"] is True
    inside, before, after = lit(job["job_id"], 0.4), lit(job["job_id"], 0.05), lit(job["job_id"], 0.9)
    assert inside > 300 and before < 20 and after < 20, (before, inside, after)
    assert "subtitle_cues" in client.get(f"/v1/assets/{job['output_asset_id']}/provenance", headers=auth("a")).text
    plain = make(body()).json()
    assert plain["subtitles"] is None and lit(plain["job_id"], 0.4) < 20


def test_subtitles_are_only_for_mp4(env):
    r = make({"input_item_ids": [item(pattern(1))], "subtitles": [CUE]})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "SUBTITLE_INVALID" and nothing_stored()


@pytest.mark.parametrize("cues, code", [
    ([{"text": "a", "start": 1.0, "end": 6.0}], "SUBTITLE_INVALID"),                                 # past the end of a 5 second video
    ([{"text": "a", "start": 3.0, "end": 2.0}], "SUBTITLE_INVALID"),
    ([{"text": "a", "start": 0.0, "end": 2.0}, {"text": "b", "start": 1.0, "end": 3.0}], "SUBTITLE_OVERLAP"),
])
def test_wrong_cues_are_refused_before_anything_is_made(env, cues, code):
    r = make(body(subtitles=cues))
    assert r.status_code == 422 and r.json()["detail"]["code"] == code, r.text
    assert nothing_stored() and client.get("/v1/assets", headers=auth("a"), params={"workspace_id": "wa", "kind": "video"}).json()["items"] == []


def test_the_request_shape_is_checked(env):
    for cues in ([{"text": "", "start": 0, "end": 1}], [{"text": "a", "start": 0, "end": 1, "color": "red"}], [{"text": "x" * 121, "start": 0, "end": 1}], [{"text": "a", "start": 0}],
                 [{"text": "a", "start": 0, "end": 1}] * 21):
        assert make(body(subtitles=cues)).status_code == 422, cues


def test_a_character_the_font_cannot_draw_and_a_too_long_cue_stop_the_job(env, ffmpeg, font):
    r = make(body(subtitles=[{"text": "좋아요 😀", "start": 0, "end": 2}]))
    assert r.status_code == 422 and r.json()["detail"]["code"] == "SUBTITLE_GLYPH_MISSING" and nothing_stored()
    r = make(body(subtitles=[{"text": "가" * 120, "start": 0, "end": 2}]))
    assert r.status_code == 422 and r.json()["detail"]["code"] == "SUBTITLE_TOO_LONG" and nothing_stored()


def test_without_the_font_the_job_fails_loudly_and_stores_nothing(env, monkeypatch):
    monkeypatch.setattr(video_subtitles, "find_subtitle_font", lambda: None)
    r = make(body(subtitles=[CUE]))
    assert r.status_code == 503 and r.json()["detail"]["code"] == "SUBTITLE_FONT_MISSING" and nothing_stored()


def test_retry_keeps_the_subtitles(env, ffmpeg, font, monkeypatch):
    real_qc = video_mp4.qc_mp4
    monkeypatch.setattr(video_mp4, "qc_mp4", lambda *a, **k: {**real_qc(*a, **k), "passed": False})
    failed = make(body(subtitles=[CUE])).json()
    assert failed["status"] == "failed" and failed["subtitles"] == [CUE]
    monkeypatch.setattr(video_mp4, "qc_mp4", real_qc)
    again = client.post(f"/v1/workspaces/wa/video-jobs/{failed['job_id']}/retry", headers=auth("a")).json()
    assert again["status"] == "succeeded" and again["subtitles"] == [CUE] and lit(again["job_id"], 0.4) > 300


def test_a_job_table_without_the_subtitles_column_gets_it():
    db = sqlite3.connect(":memory:")
    db.execute("""CREATE TABLE video_jobs (job_id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, owner_id TEXT NOT NULL, status TEXT NOT NULL, provider TEXT NOT NULL,
        aspect TEXT NOT NULL, duration_seconds INTEGER NOT NULL, motion TEXT NOT NULL, output_format TEXT NOT NULL DEFAULT 'webp', instruction TEXT,
        input_item_ids_json TEXT NOT NULL, output_asset_id TEXT, qc_json TEXT, error_code TEXT, created_at TEXT NOT NULL, finished_at TEXT)""")
    db.execute("INSERT INTO video_jobs(job_id, workspace_id, owner_id, status, provider, aspect, duration_seconds, motion, input_item_ids_json, created_at) "
               "VALUES ('vid_old','wa','u','succeeded','mock','9:16',6,'pan','[]','2026-01-01')")
    video_jobs._init(db)
    video_jobs._init(db)
    assert db.execute("SELECT subtitles_json FROM video_jobs WHERE job_id='vid_old'").fetchone()[0] is None
