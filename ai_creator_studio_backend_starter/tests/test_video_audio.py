"""Lane 4 / 6c technical spike: a WAV sound track added to an MP4 (app/video_mp4.py::add_audio). Not connected to any route; policy-free."""
import io
import math
import os
import struct
import subprocess
import wave

import pytest
from PIL import Image

from app import video_mp4 as vm
from tests.test_video_mp4 import ffmpeg  # noqa: F401


def wav(seconds=2.0, rate=22050, channels=1, freq=440.0, width=2, amplitude=12000):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(channels); w.setsampwidth(width); w.setframerate(rate)
        frames = bytearray()
        for i in range(int(seconds * rate)):
            sample = int(amplitude * math.sin(2 * math.pi * freq * i / rate))
            frames += struct.pack("<h" * channels, *([sample] * channels)) if width == 2 else bytes([128 + sample // 256]) * channels
        w.writeframes(bytes(frames))
    return buf.getvalue()


def small_video(seconds=2):
    size = (160, 96)
    return vm.encode_mp4((Image.linear_gradient("L").resize(size).rotate(i * 4).convert("RGB") for i in range(seconds * 24)), size)


def levels(mp4, ffmpeg_path, step=0.25):
    """Loudness of consecutive slices of the sound track (0..32768), by decoding it again."""
    out = subprocess.run([ffmpeg_path, "-hide_banner", "-loglevel", "error", "-i", "-", "-vn", "-ac", "1", "-ar", "8000", "-f", "s16le", "-"], input=mp4, capture_output=True).stdout
    samples = struct.unpack("<" + "h" * (len(out) // 2), out)
    n = int(8000 * step)
    return [round(math.sqrt(sum(s * s for s in samples[i:i + n]) / max(1, len(samples[i:i + n])))) for i in range(0, len(samples), n)]


# ------------------------------------------------------------------------------------------------ the WAV check (no ffmpeg)
def test_a_good_wav_is_described():
    assert vm.check_wav(wav(1.5, 22050, 2)) == {"channels": 2, "rate": 22050, "seconds": 1.5}


@pytest.mark.parametrize("bad", [b"", b"RIFF" + bytes(40), b"not a wav at all, just text" * 5, wav(width=1), wav(rate=12345), None, "text", bytes(60)])
def test_anything_but_a_plain_16_bit_wav_is_refused(bad):
    with pytest.raises(vm.VideoEncodeError) as err:
        vm.check_wav(bad)
    assert err.value.code == "AUDIO_INVALID"


def test_size_and_length_limits(monkeypatch):
    monkeypatch.setattr(vm, "MAX_AUDIO_BYTES", 1000)
    with pytest.raises(vm.VideoEncodeError):
        vm.check_wav(wav(1.0))
    monkeypatch.undo()
    monkeypatch.setattr(vm, "MAX_AUDIO_SECONDS", 1)
    with pytest.raises(vm.VideoEncodeError):
        vm.check_wav(wav(2.0))


# ------------------------------------------------------------------------------------------------ the muxing (needs ffmpeg with AAC)
def test_a_sound_track_is_added_without_touching_the_picture(ffmpeg):
    video = small_video(2)
    before = vm.probe_mp4(video)
    out, info = vm.add_audio(video, wav(2.0))
    after = vm.probe_mp4(out)
    assert before["audio_tracks"] == 0 and after["audio_tracks"] == 1 and after["codec"] == "avc1" and after["faststart"] is True
    assert (after["width"], after["height"], after["frames"]) == (before["width"], before["height"], before["frames"]), "the picture is copied, not re-encoded"
    assert abs(after["duration_seconds"] - 2.0) <= 0.15 and info["audio"]["codec"] == "aac" and info["audio"]["padded"] is False
    loud = levels(out, ffmpeg)
    assert max(loud[:5]) > 1500, f"the tone is audible: {loud}"
    assert loud[-1] < max(loud) * 0.35, f"the last quarter second is faded: {loud}"
    assert vm.qc_mp4(out, (160, 96), 2)["passed"] is True


def test_a_longer_sound_is_cut_and_a_shorter_one_is_followed_by_silence(ffmpeg):
    video = small_video(2)
    long_out, long_info = vm.add_audio(video, wav(5.0))
    assert long_info["audio"]["cut"] is True and abs(vm.probe_mp4(long_out)["duration_seconds"] - 2.0) <= 0.15
    short_out, short_info = vm.add_audio(video, wav(0.5), fade_out_seconds=0)
    assert short_info["audio"]["padded"] is True and abs(vm.probe_mp4(short_out)["duration_seconds"] - 2.0) <= 0.15
    loud = levels(short_out, ffmpeg)
    assert max(loud[:2]) > 1500 and max(loud[-4:]) < 200, f"tone first, silence after: {loud}"


def test_stereo_and_other_rates_work_and_a_video_with_sound_is_refused(ffmpeg):
    video = small_video(2)
    out, _ = vm.add_audio(video, wav(2.0, rate=44100, channels=2))
    assert vm.probe_mp4(out)["audio_tracks"] == 1
    with pytest.raises(vm.VideoEncodeError) as err:
        vm.add_audio(out, wav(1.0))
    assert err.value.code == "AUDIO_INVALID"
    for fade in (-1, 6, True, "1"):
        with pytest.raises(vm.VideoEncodeError) as err:
            vm.add_audio(video, wav(1.0), fade_out_seconds=fade)
        assert err.value.code == "AUDIO_INVALID"


def test_without_ffmpeg_or_without_the_aac_encoder_it_fails_loudly(monkeypatch):
    monkeypatch.setattr(vm, "find_ffmpeg", lambda: None)
    with pytest.raises(vm.VideoEncodeError) as err:
        vm.add_audio(b"x", wav(1.0))
    assert err.value.code == "FFMPEG_MISSING"
