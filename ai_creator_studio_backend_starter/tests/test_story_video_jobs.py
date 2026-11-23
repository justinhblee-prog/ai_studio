"""D-4: the story -> video job route. Plan/validation at request time is always tested; the encoding is faked locally (no ffmpeg on every machine) and REAL where ffmpeg + the Korean font exist (CI)."""
import io
import time

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import story_video, story_video_jobs, video_mp4, video_subtitles
from app.main import app
from tests.test_photo_steps_api import auth, env  # noqa: F401  (wa: owner a + viewer c, wb: owner b)

client = TestClient(app)
BASE = "/v1/workspaces/wa/video/story"
STORY = "아침에 일어났다. 커피를 마셨다. 길을 걸었다."


def upload(rgb, who="a"):
    buf = io.BytesIO()
    Image.new("RGB", (300, 400), rgb).save(buf, format="PNG")
    r = client.post("/v1/assets/images", headers=auth(who), data={"workspace_id": "wa", "rights_confirmed": "true"}, files={"file": ("s.png", buf.getvalue(), "image/png")})
    assert r.status_code == 201, r.text
    return r.json()["asset_id"]


@pytest.fixture
def have_tools(monkeypatch):
    """Pretend ffmpeg and the font exist and fake the encoder: the route logic is what is tested here."""
    monkeypatch.setattr(video_mp4, "find_ffmpeg", lambda: "/fake/ffmpeg")
    monkeypatch.setattr(video_subtitles, "find_subtitle_font", lambda: ("/fake/font.ttc", 0))
    monkeypatch.setattr(story_video, "make_story_mp4", lambda images, story, seconds, aspect, transitions, captions, motion, engine, comment: (b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64, {"size": [720, 1280], "frames": int(seconds * 24), "bytes": 80}))


def wait(job_id):
    for _ in range(100):
        j = client.get(f"{BASE}/{job_id}", headers=auth("a")).json()
        if j["status"] in ("succeeded", "failed"):
            return j
        time.sleep(0.1)
    raise AssertionError("job did not finish")


def post(env, sources, who="a", **kw):
    return client.post(BASE, headers=auth(who), json={"story": STORY, "sources": sources, **kw})


def test_the_plan_comes_back_at_once_with_scenes_seconds_and_captions(env, have_tools):
    a, b, c = upload((200, 40, 40)), upload((40, 200, 40)), upload((40, 40, 200))
    r = post(env, [a, b, c], length=15)
    assert r.status_code == 202, r.text
    plan = r.json()["plan"]
    assert plan["scenes"] == 3 and plan["seconds_per_scene"] == 5.0 and plan["total_seconds"] == 15
    assert [x["asset_id"] for x in r.json()["cuts"]] == [a, b, c] and r.json()["cuts"][0]["caption"] == "아침에 일어났다."
    job = wait(r.json()["job_id"])
    assert job["status"] == "succeeded" and job["asset_id"] and job["mp4"]["seconds"] == 15 and job["mp4"]["frames"] == 360


def test_auto_length_is_three_seconds_per_scene_and_pictures_are_shared_across_scenes(env, have_tools):
    a = upload((200, 40, 40))
    r = post(env, [a], length="auto")                                   # 3 sentences, 1 picture
    assert r.status_code == 202 and r.json()["plan"]["total_seconds"] == 9
    assert {x["asset_id"] for x in r.json()["cuts"]} == {a} and len(r.json()["cuts"]) == 3


@pytest.mark.parametrize("kw, code, status", [({"length": 0}, "STORY_SECONDS_INVALID", 422), ({"length": 61}, "STORY_SECONDS_INVALID", 422), ({"engine": "ai"}, "STORY_ENGINE_CLOSED", 409),
                                              ({"captions": ["only one"]}, "STORY_CAPTIONS_INVALID", 422)])
def test_bad_requests_are_refused_before_anything_is_queued(env, have_tools, kw, code, status):
    a = upload((200, 40, 40))
    r = post(env, [a], **kw)
    assert r.status_code == status and r.json()["detail"]["code"] == code
    assert client.get(BASE, headers=auth("a")).json()["items"] == []


def test_story_limits_sources_roles_and_scope(env, have_tools):
    a = upload((200, 40, 40))
    assert client.post(BASE, headers=auth("a"), json={"story": "", "sources": [a]}).status_code == 422
    assert post(env, [a, a]).json()["detail"]["code"] == "STORY_IMAGES_INVALID"
    assert post(env, ["ast_nope"]).status_code == 404
    assert post(env, [a], who="c").status_code == 403
    assert client.post(BASE, headers=auth("a"), json={"story": ". ".join(["s"] * 25) + ".", "sources": [a], "length": 60}).json()["detail"]["code"] == "STORY_TOO_MANY_SCENES"
    jid = post(env, [a], length=6).json()["job_id"]
    wait(jid)
    assert client.get(f"{BASE}/{jid}", headers=auth("c")).status_code == 200
    assert client.get(f"/v1/workspaces/wb/video/story/{jid}", headers=auth("b")).status_code == 404
    assert len(client.get(BASE, headers=auth("a")).json()["items"]) == 1


def test_no_ffmpeg_is_a_clear_503_and_no_font_is_a_clear_503(env, monkeypatch):
    a = upload((200, 40, 40))
    monkeypatch.setattr(video_mp4, "find_ffmpeg", lambda: None)
    assert post(env, [a], length=6).json()["detail"]["code"] == "FFMPEG_MISSING"
    monkeypatch.setattr(video_mp4, "find_ffmpeg", lambda: "/x")
    monkeypatch.setattr(video_subtitles, "find_subtitle_font", lambda: None)
    assert post(env, [a], length=6).json()["detail"]["code"] == "SUBTITLE_FONT_MISSING"
    assert post(env, [a], length=6, captions=None).status_code == 202          # no captions, no font needed


needs_tools = pytest.mark.skipif(video_mp4.find_ffmpeg() is None or video_subtitles.find_subtitle_font() is None, reason="needs ffmpeg and the Korean font (installed in CI)")


@needs_tools
def test_the_real_mp4_has_the_asked_length(env):
    a, b = upload((200, 40, 40)), upload((40, 200, 40))
    r = post(env, [a, b], length=6)
    job = wait(r.json()["job_id"])
    assert job["status"] == "succeeded", job
    path = next((env["tmp"] / "private").glob(f"{job['asset_id']}.*"))
    facts = video_mp4.probe_mp4(path.read_bytes())
    assert abs(facts["duration_seconds"] - 6) < 0.3
