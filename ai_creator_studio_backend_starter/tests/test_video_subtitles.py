"""Lane 4 / E-08c: burned-in subtitles -- cue checks (no font needed), drawing, the font and glyph guards, and an encoded MP4 that really shows the text.

The tests that draw need an installed open font (fonts-noto-cjk). CI installs it and sets REQUIRE_SUBTITLE_FONT=1, so there a missing font FAILS; on a developer
machine without it those tests are skipped with the reason shown.
"""
import os

import pytest
from PIL import Image, ImageChops, ImageStat

from app import video_mp4 as vm
from app import video_subtitles as vs

SIZE = (720, 1280)
KOREAN = "안녕하세요, 새 컬렉션입니다"


@pytest.fixture(scope="module")
def font():
    if vs.find_subtitle_font() is None:
        if os.environ.get("REQUIRE_SUBTITLE_FONT") == "1":
            pytest.fail("REQUIRE_SUBTITLE_FONT=1 but no subtitle font was found")
        pytest.skip("no subtitle font installed (fonts-noto-cjk)")
    return vs._load_font(36)


def cue(text="안녕하세요", start=1.0, end=2.0):
    return {"text": text, "start": start, "end": end}


# ------------------------------------------------------------------------------------------------ cues (no font)
def test_good_cues_are_returned_sorted_and_trimmed():
    out = vs.parse_cues([cue("  둘째  ", 2, 3), cue("첫째", 0, 1.5), cue("a\nb", 4, 5)], 5)
    assert [c["text"] for c in out] == ["첫째", "둘째", "a\nb"] and out[0]["end"] == 1.5 and out[2]["start"] == 4.0


@pytest.mark.parametrize("raw", [
    [], "text", None, [cue()] * 21, ["x"], [{"text": "a", "start": 0}], [{**cue(), "color": "red"}],
    [cue("")], [cue("   ")], [cue("x" * 121)], [cue("a\tb")], [cue("a\x00b")], [cue(text=5)],
    [cue(start=-1)], [cue(start=2, end=2)], [cue(start=3, end=2)], [cue(end=5.1)], [cue(start=True)], [cue(start="1")], [cue(end=float("nan"))]])
def test_bad_cues_are_refused_whole(raw):
    with pytest.raises(vm.VideoEncodeError) as err:
        vs.parse_cues(raw, 5)
    assert err.value.code == "SUBTITLE_INVALID"


def test_overlapping_cues_are_refused_but_touching_ones_are_fine():
    with pytest.raises(vm.VideoEncodeError) as err:
        vs.parse_cues([cue("a", 0, 2), cue("b", 1.5, 3)], 5)
    assert err.value.code == "SUBTITLE_OVERLAP"
    assert len(vs.parse_cues([cue("a", 0, 2), cue("b", 2, 3)], 5)) == 2


def test_without_a_font_subtitles_fail_loudly(monkeypatch):
    monkeypatch.setattr(vs, "find_subtitle_font", lambda: None)
    with pytest.raises(vm.VideoEncodeError) as err:
        vs.build_overlays(vs.parse_cues([cue()], 5), SIZE)
    assert err.value.code == "SUBTITLE_FONT_MISSING"
    monkeypatch.setenv("SUBTITLE_FONT_PATH", "/no/such/font.ttf")
    monkeypatch.undo()
    monkeypatch.setenv("SUBTITLE_FONT_PATH", "/no/such/font.ttf")
    assert vs.find_subtitle_font() is None, "a configured path that does not exist is not replaced by another font"


# ------------------------------------------------------------------------------------------------ drawing (needs the font)
def test_the_font_draws_korean_english_digits_and_punctuation_but_not_an_emoji(font):
    assert vs.unsupported_characters(KOREAN + " Hello 123 !?%", font) == []
    assert vs.unsupported_characters("좋아요 😀", font) == ["😀"], "an emoji would be a box: it is refused instead"


def test_the_glyph_and_length_guards_stop_the_job_before_any_frame_is_drawn(font):
    with pytest.raises(vm.VideoEncodeError) as err:
        vs.build_overlays(vs.parse_cues([cue("좋아요 😀")], 5), SIZE)
    assert err.value.code == "SUBTITLE_GLYPH_MISSING" and "😀" in str(err.value)
    with pytest.raises(vm.VideoEncodeError) as err:
        vs.build_overlays(vs.parse_cues([cue("가" * 120)], 5), SIZE)
    assert err.value.code == "SUBTITLE_TOO_LONG"
    assert vs.build_overlays(vs.parse_cues([cue("가" * 30)], 5), SIZE)[0]["lines"] <= 2


def test_text_is_only_on_the_frames_of_its_cue_and_only_in_the_lower_part(font):
    base = Image.new("RGB", SIZE, (90, 120, 150))
    overlays = vs.build_overlays(vs.parse_cues([cue(KOREAN, 1.0, 2.0)], 5), SIZE)
    frames = list(vs.overlay_frames((base for _ in range(120)), overlays, fps=24))
    assert len(frames) == 120
    same = lambda i: frames[i].tobytes() == base.tobytes()          # noqa: E731
    assert same(0) and same(23) and not same(24) and not same(47) and same(48) and same(119), "frame 24 (1.0 s) is the first with text, frame 48 (2.0 s) is the first without"
    shown = frames[30]
    assert ImageChops.difference(shown.crop((0, 0, 720, 800)), base.crop((0, 0, 720, 800))).getbbox() is None, "the upper part is untouched"
    box = overlays[0]["box"]
    assert box[1] > 900 and box[3] < 1280 and box[0] > 0 and box[2] < 720, "a box in the lower part, inside the picture"
    text_area = shown.crop(box).convert("L")
    assert max(text_area.getdata()) == 255 and ImageStat.Stat(text_area).mean[0] < ImageStat.Stat(base.crop(box).convert("L")).mean[0] + 100
    bright = sum(1 for v in text_area.getdata() if v > 235)
    assert bright > 300, f"white text pixels are there ({bright})"


def test_a_long_cue_wraps_to_two_lines_inside_the_picture(font):
    wide = vs.build_overlays(vs.parse_cues([cue("가나다라마바사 " * 5, 0, 1)], 5), SIZE)[0]
    assert wide["lines"] == 2 and wide["box"][0] >= 0 and wide["box"][2] <= SIZE[0]
    one = vs.build_overlays(vs.parse_cues([cue("가나다", 0, 1)], 5), SIZE)[0]
    assert one["lines"] == 1 and (one["box"][2] - one["box"][0]) < (wide["box"][2] - wide["box"][0])


# ------------------------------------------------------------------------------------------------ in the MP4 (needs ffmpeg and the font)
def test_an_mp4_with_subtitles_shows_the_text_only_while_the_cue_runs(font):
    if vm.find_ffmpeg() is None:
        if os.environ.get("REQUIRE_FFMPEG") == "1":
            pytest.fail("REQUIRE_FFMPEG=1 but ffmpeg was not found")
        pytest.skip("ffmpeg is not installed on this machine")
    picture = Image.new("RGB", (1200, 1200), (60, 60, 60))
    content, info = vm.make_mp4([picture], "9:16", 5, "pan", "cut", subtitles=[cue(KOREAN, 1.0, 3.0)])
    assert info["subtitle_cues"] == 1 and vm.qc_mp4(content, vm.SIZES["9:16"], 5)["passed"] is True
    def lower_band_brightness(at):
        frame = vm.poster_image(content, at=at).convert("L")
        band = frame.crop((0, 1000, 720, 1220))
        return sum(1 for v in band.getdata() if v > 200)
    inside, before, after = lower_band_brightness(0.4), lower_band_brightness(0.05), lower_band_brightness(0.9)
    assert inside > 300 and before < 20 and after < 20, (before, inside, after)
    plain, plain_info = vm.make_mp4([picture], "9:16", 5, "pan", "cut")
    assert plain_info["subtitle_cues"] == 0


def test_bad_subtitles_stop_make_mp4_before_ffmpeg_runs(monkeypatch):
    monkeypatch.setattr(vm, "find_ffmpeg", lambda: "/bin/true")                 # a pretend encoder: it must never be called
    monkeypatch.setattr(vm, "encode_mp4", lambda *a, **k: pytest.fail("the encoder must not run when the subtitles are wrong"))
    with pytest.raises(vm.VideoEncodeError) as err:
        vm.make_mp4([Image.new("RGB", (400, 400))], "9:16", 5, subtitles=[cue(start=4, end=9)])
    assert err.value.code == "SUBTITLE_INVALID"
