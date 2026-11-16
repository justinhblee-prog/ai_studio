"""R-051: the option / catalogue picture checker: naming, location, size, content, duplicates, expected-vs-present, exit codes."""
import json
import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import check_option_images as chk  # noqa: E402


def webp(path: Path, size=(256, 256), animated=False, fmt="WEBP", pad=0):
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.effect_noise(size, 80).convert("RGB") if pad else Image.new("RGB", size, (200, 120, 90))
    if animated:
        img.save(path, format="WEBP", save_all=True, append_images=[Image.new("RGB", size, (1, 2, 3))], duration=100)
    else:
        img.save(path, format=fmt, quality=95 if pad else 80)
    return path


def test_good_pictures_in_every_allowed_place_pass(tmp_path):
    for rel in ("opt/skin_tone-3.webp", "opt/hair-wavy.webp", "cat/dress-a01.webp", "cat/webtoon/dress-a01.webp", "cat/render3d/shoes-k2.webp"):
        webp(tmp_path / rel)
    report = chk.run(tmp_path)
    assert report == {"checked": 5, "errors": [], "missing": [], "unexpected": []}
    assert chk.main([str(tmp_path)]) == 0


@pytest.mark.parametrize("rel, fragment", [
    ("opt/Skin_Tone-3.webp", "name must look like"), ("opt/skintone3.webp", "name must look like"), ("opt/a-b-c.webp", "name must look like"),
    ("opt/한글-1.webp", "name must look like"), ("opt/x-1.png", "name must look like"),
    ("other/x-1.webp", "not an allowed location"), ("opt/sub/x-1.webp", "not an allowed location"), ("cat/oilpaint/x-1.webp", "not an allowed location"),
    ("x-1.webp", "not an allowed location"),
])
def test_names_and_places_outside_the_rules_are_errors(tmp_path, rel, fragment):
    webp(tmp_path / rel)
    errors = chk.run(tmp_path)["errors"]
    assert errors and any(fragment in e for e in errors), errors
    assert chk.main([str(tmp_path)]) == 1


def test_content_must_match_the_extension_and_the_limits(tmp_path):
    webp(tmp_path / "opt/a-1.webp", fmt="PNG")                       # a PNG renamed to .webp
    webp(tmp_path / "opt/b-1.webp", size=(32, 32))                    # too small
    webp(tmp_path / "opt/c-1.webp", size=(2000, 100))                 # too wide
    webp(tmp_path / "opt/d-1.webp", animated=True)                    # animated
    (tmp_path / "opt/e-1.webp").write_bytes(b"not an image")          # not an image at all
    (tmp_path / "opt/f-1.webp").write_bytes(b"")                      # empty
    big = webp(tmp_path / "opt/g-1.webp", size=(1500, 1500), pad=1)   # noisy 1500x1500 at high quality: over 200 KB
    assert big.stat().st_size > chk.MAX_BYTES
    text = "\n".join(chk.run(tmp_path)["errors"])
    for needle in ("a-1.webp: content is PNG", "b-1.webp: 32x32", "c-1.webp: 2000x100", "d-1.webp: animated", "e-1.webp: cannot be read", "f-1.webp: empty", "g-1.webp:"):
        assert needle in text, needle + "\n" + text
    assert "over the 200 KB limit" in text


def test_names_that_differ_only_by_case_are_reported(tmp_path):
    webp(tmp_path / "opt/a-1.webp")
    if not (tmp_path / "opt/A-1.webp").exists():
        try:
            webp(tmp_path / "opt/A-1.webp")
        except OSError:
            pytest.skip("case-insensitive file system")
    if len(list((tmp_path / "opt").iterdir())) == 2:
        assert any("only by letter case" in e for e in chk.run(tmp_path)["errors"])


def test_expected_versus_present_reports_missing_and_unexpected_and_strict_fails_on_missing(tmp_path):
    webp(tmp_path / "opt/skin_tone-1.webp"); webp(tmp_path / "opt/skin_tone-2.webp")
    expected = tmp_path.parent / (tmp_path.name + "-expected.json")
    expected.write_text(json.dumps(["opt/skin_tone-1.webp", "opt/skin_tone-3.webp"]), encoding="utf-8")
    report = chk.run(tmp_path, ["opt/skin_tone-1.webp", "opt/skin_tone-3.webp"])
    assert report["missing"] == ["opt/skin_tone-3.webp"] and report["unexpected"] == ["opt/skin_tone-2.webp"] and report["errors"] == []
    assert chk.main([str(tmp_path), "--expected", str(expected)]) == 0, "missing pictures are normal while they are still being made"
    assert chk.main([str(tmp_path), "--expected", str(expected), "--strict"]) == 1
    assert chk.run(tmp_path, [])["unexpected"] == ["opt/skin_tone-1.webp", "opt/skin_tone-2.webp"]


def test_unusable_input_exits_2(tmp_path, capsys):
    assert chk.main([str(tmp_path / "nope")]) == 2
    bad = tmp_path / "bad.json"
    bad.write_text('{"not": "a list"}', encoding="utf-8")
    assert chk.main([str(tmp_path), "--expected", str(bad)]) == 2
    assert chk.main([str(tmp_path), "--expected", str(tmp_path / "absent.json")]) == 2
    err = capsys.readouterr().err
    assert "not a folder" in err and "unusable --expected" in err


def test_json_output_is_the_report(tmp_path, capsys):
    webp(tmp_path / "opt/a-1.webp")
    assert chk.main([str(tmp_path), "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == {"checked": 1, "errors": [], "missing": [], "unexpected": []}
