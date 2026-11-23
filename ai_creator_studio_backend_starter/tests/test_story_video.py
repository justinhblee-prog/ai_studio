"""R-ENGINE-17: story -> video of a chosen length. Planning is pure (always tested); the MP4 itself needs ffmpeg and the open Korean font (installed in CI)."""
import pytest
from PIL import Image

from app import story_video as sv, video_mp4, video_subtitles

STORY = "아침에 일어났다. 커피를 마셨다. 길을 걸었다. 비가 왔다. 집에 돌아왔다."


def p(n, story=STORY, seconds=10, **kw):
    return sv.plan(n, story, seconds, **kw)


@pytest.mark.parametrize("seconds, ok", [(0, False), (0.5, False), (1, True), (60, True), (61, False)])
def test_total_seconds_boundaries(seconds, ok):
    if ok:
        assert p(2, "한 문장. 두 문장.", seconds)["total_seconds"] == seconds
    else:
        with pytest.raises(sv.StoryError) as e:
            p(2, "한 문장. 두 문장.", seconds)
        assert e.value.code == "STORY_SECONDS_INVALID"


@pytest.mark.parametrize("seconds", [True, "10", None])
def test_total_seconds_must_be_a_number(seconds):
    with pytest.raises(sv.StoryError):
        p(2, STORY, seconds)


def test_equal_sentences_and_pictures_map_one_to_one_and_share_the_time_equally():
    r = p(5)
    assert [c["image_index"] for c in r["cuts"]] == [0, 1, 2, 3, 4] and r["scenes"] == 5 and r["seconds_per_scene"] == 2.0
    assert [c["caption"] for c in r["cuts"]][0] == "아침에 일어났다."
    assert r["cuts"][-1]["end"] == 10.0 and [c["start"] for c in r["cuts"]] == [0, 2, 4, 6, 8]


def test_more_sentences_than_pictures_reuse_pictures_in_order():
    r = p(2)
    assert r["scenes"] == 5 and [c["image_index"] for c in r["cuts"]] == [0, 0, 0, 1, 1] and all(c["caption"] for c in r["cuts"])


def test_more_pictures_than_sentences_spread_a_caption_over_its_group():
    r = p(4, "첫 문장. 둘째 문장.", 8)
    assert r["scenes"] == 4 and [c["image_index"] for c in r["cuts"]] == [0, 1, 2, 3]
    assert [c["caption"] for c in r["cuts"]] == ["첫 문장.", None, "둘째 문장.", None]
    assert r["cues"] == [{"text": "첫 문장.", "start": 0.0, "end": 4.0}, {"text": "둘째 문장.", "start": 4.0, "end": 8.0}]


def test_captions_are_cut_at_forty_characters_and_can_be_given_or_switched_off():
    long = "가" * 100
    assert len(p(1, long)["cuts"][0]["caption"]) == 40 and p(1, long)["cuts"][0]["caption"].endswith("…")
    assert p(2, "a. b.", captions=None)["cues"] == [] and p(2, "a. b.", captions=["x", ""])["cuts"][1]["caption"] is None
    with pytest.raises(sv.StoryError) as e:
        p(2, "a. b.", captions=["x"])
    assert e.value.code == "STORY_CAPTIONS_INVALID"


def test_limits_and_closed_ai_engine():
    for args, code in (((1, "", 5), "STORY_EMPTY"), ((9, "a.", 5), "STORY_IMAGES_INVALID"), ((1, ". ".join(["s"] * 30) + ".", 60), "STORY_TOO_MANY_SCENES"), ((1, ". ".join(["s"] * 10) + ".", 3), "STORY_TOO_MANY_SCENES")):
        with pytest.raises(sv.StoryError) as e:
            sv.plan(*args)
        assert e.value.code == code
    with pytest.raises(sv.StoryError) as e:
        sv.plan(1, "a.", 5, engine="ai")
    assert e.value.code == "STORY_ENGINE_CLOSED"
    with pytest.raises(sv.StoryError) as e:
        sv.plan(1, "a.", 5, engine="gpu")
    assert e.value.code == "STORY_ENGINE_INVALID"


def test_the_plan_is_deterministic_and_cues_are_valid_for_the_subtitle_burner():
    assert p(3) == p(3)
    r = p(3)
    assert video_subtitles.parse_cues(r["cues"], r["total_seconds"])


def test_frame_count_matches_the_requested_length_exactly():
    imgs = [Image.new("RGB", (200, 300), c) for c in ((200, 40, 40), (40, 200, 40))]
    plan_ = sv.plan(2, "a. b.", 3.5)
    n = sum(1 for _ in sv._frames(imgs, plan_, "9:16", "zoom", "crossfade"))
    assert n == round(3.5 * video_mp4.FPS)


needs_ffmpeg = pytest.mark.skipif(video_mp4.find_ffmpeg() is None or video_subtitles.find_subtitle_font() is None, reason="needs ffmpeg and the Korean font (installed in CI)")


@needs_ffmpeg
@pytest.mark.parametrize("seconds", [2, 7, 12])
def test_the_mp4_has_the_asked_length_and_captions(seconds):
    imgs = [Image.new("RGB", (300, 400), c) for c in ((200, 60, 60), (60, 200, 60), (60, 60, 200))]
    data, meta = sv.make_story_mp4(imgs, "첫째 장면입니다. 둘째 장면입니다. 셋째 장면입니다.", seconds, aspect="9:16")
    facts = video_mp4.probe_mp4(data)
    assert abs(facts["duration_seconds"] - seconds) < 0.2 and meta["cues"] and meta["frames"] == seconds * video_mp4.FPS
