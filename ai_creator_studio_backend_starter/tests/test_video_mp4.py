"""Lane 4 / E-08a: real MP4 output (ffmpeg) -- the frames, the 3 aspects x 3 lengths matrix, the structure reader and the QC.

The tests that encode need the ffmpeg executable. CI installs it and sets REQUIRE_FFMPEG=1, so there a missing ffmpeg FAILS (never a silent skip);
on a developer machine without ffmpeg those tests are skipped with the reason shown.
"""
import os
import struct
import time
from pathlib import Path

import pytest
from PIL import Image, ImageChops, ImageDraw, ImageStat

from app import video_mp4 as vm

MATRIX = [(aspect, seconds) for aspect in vm.SIZES for seconds in vm.DURATIONS]
ROWS: list[dict] = []


def picture(seed: int, size=(1500, 1500)) -> Image.Image:
    """A drawn 'product photo': a shaded background with a few coloured shapes, different for every seed."""
    shade = Image.linear_gradient("L").resize(size)
    img = Image.merge("RGB", (shade.point(lambda v: 60 + v // 2), shade.point(lambda v: 200 - v // 3), Image.new("L", size, 40 + 60 * seed)))
    draw = ImageDraw.Draw(img)
    draw.ellipse((300 + 100 * seed, 250, 900 + 100 * seed, 1000), fill=(230, 60 + 50 * seed, 40))
    draw.rectangle((150, 1050, 1350, 1300), fill=(20, 40, 160 + 30 * seed))
    draw.line((0, 0, size[0], size[1]), fill=(255, 255, 255), width=12)
    return img


@pytest.fixture(scope="module")
def ffmpeg():
    path = vm.find_ffmpeg()
    if path is None:
        if os.environ.get("REQUIRE_FFMPEG") == "1":
            pytest.fail("REQUIRE_FFMPEG=1 but ffmpeg was not found")
        pytest.skip("ffmpeg is not installed on this machine")
    return path


@pytest.fixture(scope="module", autouse=True)
def write_the_matrix_table():
    yield
    target = os.environ.get("VIDEO_MATRIX_OUT")
    if target and ROWS:
        lines = ["| aspect | size | seconds | motion | transition | frames | duration s | bytes | make ms | qc ms | qc |", "|---|---|---|---|---|---|---|---|---|---|---|"]
        lines += [f"| {r['aspect']} | {r['size']} | {r['seconds']} | {r['motion']} | {r['transition']} | {r['frames']} | {r['duration']} | {r['bytes']} | "
                  f"{r['make_ms']} | {r['qc_ms']} | {r['qc']} |" for r in ROWS]
        Path(target).write_text("\n".join(lines) + "\n", encoding="utf-8")


# ------------------------------------------------------------------------------------------------ frames (no ffmpeg needed)
def test_frames_have_the_right_count_and_size_and_the_inputs_are_not_changed():
    src = picture(0)
    before = src.tobytes()
    frames = list(vm.render_frames([src], "9:16", 5, "zoom"))
    assert len(frames) == 5 * vm.FPS == 120 and all(f.size == (720, 1280) and f.mode == "RGB" for f in frames)
    assert src.tobytes() == before


@pytest.mark.parametrize("motion", vm.MOTIONS)
def test_every_motion_really_moves_the_picture_and_never_shows_an_empty_corner(motion):
    frames = list(vm.render_frames([picture(1)], "16:9", 5, motion))
    assert ImageStat.Stat(ImageChops.difference(frames[0], frames[-1]).convert("L")).mean[0] > 2.0, "first and last frame differ"
    assert ImageStat.Stat(ImageChops.difference(frames[0], frames[1]).convert("L")).mean[0] < 8.0, "neighbouring frames are close: the move is smooth"
    for frame in (frames[0], frames[60], frames[-1]):
        for corner in ((0, 0), (1279, 0), (0, 719), (1279, 719)):
            assert frame.getpixel(corner) != (0, 0, 0), "the camera window stays inside the picture (no black corner from the rotation)"


def test_cut_and_crossfade_between_two_pictures():
    a, b = picture(0), picture(2)
    cut = list(vm.render_frames([a, b], "4:5", 5, "zoom", "cut"))
    fade = list(vm.render_frames([a, b], "4:5", 5, "zoom", "crossfade"))
    def diff(x, y):
        return ImageStat.Stat(ImageChops.difference(x, y).convert("L")).mean[0]
    assert diff(cut[59], cut[60]) > 10, "a cut: the picture changes from one frame to the next"
    assert cut[30].tobytes() == fade[30].tobytes(), "outside the fade both are the same"
    assert diff(fade[59], fade[60]) < diff(cut[59], cut[60]) / 3, "a crossfade: no jump at the change"
    assert 0 < diff(fade[54], cut[54]) and diff(fade[54], cut[60]) < diff(cut[54], cut[60]), "half-way frames are a blend of both pictures"


@pytest.mark.parametrize("args, code", [
    ((1, "1:1", 5, "zoom", "cut"), "VIDEO_ASPECT_INVALID"), ((1, "9:16", 6, "zoom", "cut"), "VIDEO_DURATION_INVALID"),
    ((1, "9:16", True, "zoom", "cut"), "VIDEO_DURATION_INVALID"), ((1, "9:16", 5, "spin", "cut"), "VIDEO_MOTION_INVALID"),
    ((1, "9:16", 5, "zoom", "wipe"), "VIDEO_TRANSITION_INVALID"), ((0, "9:16", 5, "zoom", "cut"), "VIDEO_INPUT_COUNT"),
    ((9, "9:16", 5, "zoom", "cut"), "VIDEO_INPUT_COUNT")])
def test_bad_requests_are_refused_before_anything_is_drawn(args, code):
    with pytest.raises(vm.VideoEncodeError) as err:
        vm.check_request(*args)
    assert err.value.code == code


def test_without_ffmpeg_the_call_fails_instead_of_delivering_something_else(monkeypatch):
    monkeypatch.setattr(vm, "find_ffmpeg", lambda: None)
    for call in (lambda: vm.make_mp4([picture(0)], "9:16", 5), lambda: vm.encode_mp4([], (160, 90)), lambda: vm.qc_mp4(b"", (160, 90), 5),
                 lambda: vm.poster_image(b"")):
        with pytest.raises(vm.VideoEncodeError) as err:
            call()
        assert err.value.code == "FFMPEG_MISSING"


def test_a_configured_ffmpeg_path_that_does_not_exist_is_not_replaced_by_another_one(monkeypatch, tmp_path):
    monkeypatch.setenv("FFMPEG_BINARY", str(tmp_path / "no-such-ffmpeg"))
    assert vm.find_ffmpeg() is None


def test_the_structure_reader_refuses_things_that_are_not_mp4():
    for junk in (b"", b"not an mp4 at all", struct.pack(">I4s", 16, b"ftyp") + b"isom\x00\x00\x02\x00", struct.pack(">I4s", 4000, b"ftyp") + b"isom"):
        with pytest.raises(vm.VideoEncodeError) as err:
            vm.probe_mp4(junk)
        assert err.value.code == "MP4_INVALID"


# ------------------------------------------------------------------------------------------------ real encoding
# B-14: the two slowest rows (15 s in 4:5 and 16:9, about 8 s each) run in the nightly workflow (.github/workflows/video-nightly.yml, RUN_SLOW_VIDEO=1).
# Every pull request still runs all 5 s and 10 s rows, the 15 s row in 9:16, and the 15 s turntable in the browser job (360 cuts).
NIGHTLY_ONLY = pytest.mark.skipif(os.environ.get("RUN_SLOW_VIDEO") != "1", reason="the slow 15 s rows run in the nightly workflow (B-14)")
MATRIX_PARAMS = [pytest.param(a, s, marks=NIGHTLY_ONLY) if (s == 15 and a != "9:16") else pytest.param(a, s) for a, s in MATRIX]


@pytest.mark.parametrize("aspect, seconds", MATRIX_PARAMS)
def test_the_matrix_of_three_aspects_and_three_lengths_gives_playable_mp4(ffmpeg, aspect, seconds):
    index = MATRIX.index((aspect, seconds))
    motion, transition = vm.MOTIONS[index % 3], vm.TRANSITIONS[index % 2]
    content, info = vm.make_mp4([picture(0), picture(1), picture(2)], aspect, seconds, motion, transition)
    started = time.perf_counter()
    qc = vm.qc_mp4(content, vm.SIZES[aspect], seconds)
    qc_ms = round((time.perf_counter() - started) * 1000)
    probe = qc["probe"]
    ROWS.append({"aspect": aspect, "size": f"{probe['width']}x{probe['height']}", "seconds": seconds, "motion": motion, "transition": transition,
                 "frames": probe["frames"], "duration": probe["duration_seconds"], "bytes": len(content), "make_ms": info["encode_ms"], "qc_ms": qc_ms,
                 "qc": "pass" if qc["passed"] else "FAIL"})
    assert content[4:8] == b"ftyp" and info["mode"] == "local" and info["ai"] is False and info["frames"] == seconds * 24
    assert probe["codec"] == "avc1" and (probe["width"], probe["height"]) == vm.SIZES[aspect] and probe["audio_tracks"] == 0
    assert probe["frames"] == seconds * 24 and abs(probe["duration_seconds"] - seconds) <= 0.1 and probe["faststart"] is True
    assert qc["passed"] is True and qc["decoded_frames"] == seconds * 24 and qc["blank_frames"] == 0, qc["checks"]
    levels = {c["check"]: c["level"] for c in qc["checks"]}
    assert levels["static_picture"] == "ok" and levels["decodable"] == "ok", "the picture moves and the file decodes without errors"
    assert len(content) > 50_000, "a real video, not an empty shell"


def test_the_qc_fails_blank_videos_wrong_expectations_and_broken_files(ffmpeg):
    size = (160, 96)
    blank = vm.encode_mp4((Image.new("RGB", size, (128, 128, 128)) for _ in range(120)), size)
    result = vm.qc_mp4(blank, size, 5)
    levels = {c["check"]: c["level"] for c in result["checks"]}
    assert result["passed"] is False and levels["blank_frames"] == "fail" and result["blank_frames"] == 120
    assert levels["static_picture"] == "warn" and levels["frame_count"] == "ok" and levels["codec"] == "ok"

    moving = vm.encode_mp4((Image.linear_gradient("L").resize(size).rotate(i * 3).convert("RGB") for i in range(120)), size)
    assert vm.qc_mp4(moving, size, 5)["passed"] is True
    wrong = {c["check"]: c["level"] for c in vm.qc_mp4(moving, (96, 160), 10)["checks"]}
    assert wrong["size"] == "fail" and wrong["frame_count"] == "fail" and wrong["duration"] == "fail"

    cut = vm.qc_mp4(moving[: len(moving) // 2], size, 5)
    assert cut["passed"] is False and cut["checks"][0] == {"check": "container", "level": "fail", "detail": cut["checks"][0]["detail"]}
    damaged = bytearray(moving)
    start = moving.index(b"mdat") + 200
    damaged[start:start + 4000] = b"\x00" * min(4000, len(damaged) - start)
    assert vm.qc_mp4(bytes(damaged), size, 5)["passed"] is False, "a file whose picture data is damaged does not pass"


def test_the_encoder_refuses_odd_sizes_wrong_frames_and_no_frames(ffmpeg):
    with pytest.raises(vm.VideoEncodeError) as err:
        vm.encode_mp4([Image.new("RGB", (161, 90))], (161, 90))
    assert err.value.code == "VIDEO_SIZE_INVALID"
    with pytest.raises(vm.VideoEncodeError) as err:
        vm.encode_mp4([Image.new("RGB", (160, 90)), Image.new("RGB", (80, 90))], (160, 90))
    assert err.value.code == "VIDEO_FRAME_SIZE"
    with pytest.raises(vm.VideoEncodeError) as err:
        vm.encode_mp4([], (160, 90))
    assert err.value.code == "FFMPEG_FAILED"


def test_a_comment_travels_inside_the_file_and_is_read_back(ffmpeg):
    size = (160, 96)
    def frames():
        return (Image.linear_gradient("L").resize(size).rotate(i * 3).convert("RGB") for i in range(24))
    line = "ai_generated=true; ai_edited=false; tool=AI Creator Studio; 표시=AI 생성 이미지 포함"
    tagged = vm.encode_mp4(frames(), size, comment=line)
    assert vm.probe_mp4(tagged)["comment"] == line, "the line is inside the MP4 itself, Korean included"
    assert vm.probe_mp4(tagged)["faststart"] is True and vm.probe_mp4(tagged)["frames"] == 24
    assert vm.probe_mp4(vm.encode_mp4(frames(), size))["comment"] is None, "no comment asked, none written"


@pytest.mark.parametrize("comment", ["", "   ", "two\nlines", "x" * 501, "tab\there", 7])
def test_a_comment_that_is_empty_too_long_or_not_one_line_is_refused(ffmpeg, comment):
    with pytest.raises(vm.VideoEncodeError) as err:
        vm.encode_mp4([Image.new("RGB", (160, 96))], (160, 96), comment=comment)
    assert err.value.code == "VIDEO_COMMENT_INVALID"


def test_the_cover_picture_is_a_frame_of_the_video_at_the_asked_position(ffmpeg):
    size = (320, 192)
    shade = Image.linear_gradient("L").resize(size)
    red = Image.merge("RGB", (Image.new("L", size, 220), shade.point(lambda v: v // 4), Image.new("L", size, 20)))
    blue = Image.merge("RGB", (Image.new("L", size, 20), shade.point(lambda v: v // 4), Image.new("L", size, 220)))
    video = vm.encode_mp4([red] * 24 + [blue] * 24, size)
    def red_minus_blue(picture):
        r, _, b = ImageStat.Stat(picture).mean
        return r - b
    first = vm.poster_image(video)
    assert first.size == size and first.mode == "RGB" and red_minus_blue(first) > 100, "position 0 is the first picture"
    assert red_minus_blue(vm.poster_image(video, at=0.25)) > 100
    assert red_minus_blue(vm.poster_image(video, at=0.75)) < -100, "three quarters in is the second picture"
    assert red_minus_blue(vm.poster_image(video, at=1.0)) < -100, "position 1 is still a real frame (the end), not an error"
    small = vm.poster_image(video, at=0.75, max_side=80)
    assert small.size == (80, 48) and red_minus_blue(small) < -100
    assert vm.poster_image(video, max_side=4000).size == size, "a cover is never enlarged"


def test_the_cover_picture_refuses_a_bad_position_and_a_file_that_is_not_mp4(ffmpeg):
    for at in (-0.1, 1.5, True, "0.5"):
        with pytest.raises(vm.VideoEncodeError) as err:
            vm.poster_image(b"", at=at)
        assert err.value.code == "VIDEO_POSTER_POSITION"
    with pytest.raises(vm.VideoEncodeError) as err:
        vm.poster_image(b"not an mp4 at all")
    assert err.value.code == "MP4_INVALID"


# ------------------------------------------------------------------------------------------------ E-08b: 3D rotation cuts
def cuts(n=12, side=256):
    """A drawn 360-degree set: a bar whose place and colour depend on the angle, on the render's light background."""
    out = []
    for k in range(n):
        img = Image.new("RGB", (side, side), (242, 242, 242))
        x = 40 + round(150 * k / n)
        ImageDraw.Draw(img).rectangle((x, 60, x + 30, 200), fill=(30 + 15 * k, 60, 200 - 12 * k))
        out.append(img)
    return out


def test_a_rotation_set_becomes_frames_that_pass_through_every_cut_and_blend_in_between():
    source = cuts()
    before = [c.tobytes() for c in source]
    frames = list(vm.render_turntable_frames(source, "4:5", 5))
    assert len(frames) == 120 and all(f.size == (864, 1080) for f in frames) and [c.tobytes() for c in source] == before
    def diff(x, y):
        return ImageStat.Stat(ImageChops.difference(x, y).convert("L")).mean[0]
    for k in (0, 1, 7, 11):                       # 120 frames / 12 cuts: every 10th frame is exactly one cut
        assert frames[10 * k].tobytes() == vm._contain(source[k], (864, 1080)).tobytes(), k
    assert 0 < diff(frames[5], frames[0]) and 0 < diff(frames[5], frames[10]) and diff(frames[5], frames[0]) < diff(frames[10], frames[0])
    assert diff(frames[119], frames[0]) < diff(frames[110], frames[0]), "the last frame leads back to the first: the video loops"
    two_turns = list(vm.render_turntable_frames(source, "4:5", 5, turns=2))
    assert two_turns[5].tobytes() == frames[10].tobytes() and two_turns[60].tobytes() == frames[0].tobytes()


def test_the_whole_cut_is_shown_on_a_tall_or_wide_frame_with_the_renders_background_around_it():
    tall = list(vm.render_turntable_frames(cuts(), "9:16", 5))[0]
    assert tall.getpixel((5, 5)) == (242, 242, 242) and tall.getpixel((360, 1270)) == (242, 242, 242), "background above and below"
    assert tall.getpixel((157, 640)) != (242, 242, 242), "the bar of cut 0 (x 40..70 of 256, scaled by 720/256) is there"
    wide = list(vm.render_turntable_frames(cuts(), "16:9", 5))[0]
    assert wide.getpixel((5, 360)) == (242, 242, 242) and wide.getpixel((1275, 360)) == (242, 242, 242), "background left and right"


@pytest.mark.parametrize("bad", [lambda: cuts(7), lambda: cuts(361, 16), lambda: cuts(8) + [Image.new("RGB", (64, 64))], lambda: tuple(cuts(8))])
def test_a_rotation_set_that_is_too_small_too_large_or_of_mixed_sizes_is_refused(bad):
    with pytest.raises(vm.VideoEncodeError) as err:
        vm.render_turntable_frames(bad(), "9:16", 5)
    assert err.value.code == "VIDEO_TURNTABLE_INVALID"
    for turns in (0, 4, True, 1.5):
        with pytest.raises(vm.VideoEncodeError) as err:
            vm.render_turntable_frames(cuts(8), "9:16", 5, turns=turns)
        assert err.value.code == "VIDEO_TURNTABLE_INVALID"


def test_a_rotation_set_encodes_to_a_playable_mp4_that_moves(ffmpeg):
    content, info = vm.make_turntable_mp4(cuts(24), "9:16", 5, comment="source=3d_rotation_cuts")
    qc = vm.qc_mp4(content, vm.SIZES["9:16"], 5)
    levels = {c["check"]: c["level"] for c in qc["checks"]}
    assert qc["passed"] is True and qc["decoded_frames"] == 120 and levels["static_picture"] == "ok", qc["checks"]
    assert info["motion"] == "turntable" and info["inputs"] == 24 and info["turns"] == 1 and info["ai"] is False
    assert qc["probe"]["comment"] == "source=3d_rotation_cuts" and (qc["probe"]["width"], qc["probe"]["height"]) == (720, 1280)


def ring(n, side=128):
    """n cuts that are all different: the bar moves and changes colour with the angle (works for any n up to 120)."""
    out = []
    for k in range(n):
        img = Image.new("RGB", (side, side), (242, 242, 242))
        x = round(k * 100 / n)
        ImageDraw.Draw(img).rectangle((x, 20, x + 20, 100), fill=(2 * k, 60, 255 - 2 * k))
        out.append(img)
    return out


def test_with_as_many_cuts_as_frames_no_frame_is_a_blend():
    assert vm.turntable_blended_frames(120, 5) == 0 and vm.turntable_blended_frames(60, 5, turns=2) == 0 and vm.turntable_blended_frames(120, 10) == 120
    assert vm.turntable_blended_frames(24, 5) == 96 and vm.turntable_blended_frames(12, 5) == 108, "24 cuts: only every 5th frame is a rendered cut"
    assert vm.turntable_blended_frames(240, 10) == 0 and vm.turntable_blended_frames(360, 15) == 0 and vm.turntable_blended_frames(360, 5, turns=3) == 0
    source = ring(120)
    prepared = {vm._contain(c, (720, 1280)).tobytes() for c in source}
    assert len(prepared) == 120, "the test set itself has 120 different cuts"
    frames = list(vm.render_turntable_frames(source, "9:16", 5))
    assert all(f.tobytes() in prepared for f in frames) and len({f.tobytes() for f in frames}) == 120, "every frame is one rendered cut, each used once"
    few = ring(24)
    few_prepared = {vm._contain(c, (720, 1280)).tobytes() for c in few}
    blended = [f for f in vm.render_turntable_frames(few, "9:16", 5) if f.tobytes() not in few_prepared]
    assert len(few_prepared) == 24 and len(blended) == vm.turntable_blended_frames(24, 5) == 96


def test_a_fifteen_second_turn_from_360_cuts_uses_each_cut_once_without_keeping_them_all_fitted():
    source = [Image.new("RGB", (32, 32), (k % 256, (k * 7) % 256, 200)) for k in range(360)]     # 360 different flat cuts
    seen = [f.getpixel((360, 640)) for f in vm.render_turntable_frames(source, "9:16", 15)]
    assert len(seen) == 360 and seen == [(k % 256, (k * 7) % 256, 200) for k in range(360)], "frame k is cut k, in order, none blended"
