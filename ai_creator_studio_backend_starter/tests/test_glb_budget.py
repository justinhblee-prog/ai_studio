"""E-04: the static .glb budget: numbers, device-class checks, honesty about what it cannot read, and a guard that our own models stay light enough for a phone."""
import io
import struct

import pytest
from PIL import Image

from app import base_models, garments, glb_budget
from app.glb_tools import GlbError, build_glb, inspect_glb
from scripts import glb_budget as budget_script


def png(width, height):
    buf = io.BytesIO()
    Image.new("RGB", (width, height), (120, 40, 40)).save(buf, format="PNG")
    return buf.getvalue()


def model_with_pictures(*pictures, shared=False):
    """A GLB whose images are embedded in the BIN chunk: one bufferView each, or all pointing at the first (identical pictures stored once)."""
    binary, views, images = b"", [], []
    for number, data in enumerate(pictures):
        if shared and number:
            images.append({"bufferView": 0, "mimeType": "image/png"})
            continue
        binary += b"\x00" * (-len(binary) % 4)
        views.append({"buffer": 0, "byteOffset": len(binary), "byteLength": len(data)})
        binary += data
        images.append({"bufferView": len(views) - 1, "mimeType": "image/png"})
    doc = {"asset": {"version": "2.0"}, "buffers": [{"byteLength": len(binary)}], "bufferViews": views, "images": images, "textures": [{"source": i} for i in range(len(images))]}
    return build_glb(doc, binary)


def heavy_model(triangles):
    doc = {"asset": {"version": "2.0"}, "meshes": [{"primitives": [{"attributes": {"POSITION": 0}, "indices": 1}]}],
           "accessors": [{"count": triangles, "componentType": 5126, "type": "VEC3", "min": [0, 0, 0], "max": [1, 1, 1]}, {"count": triangles * 3, "componentType": 5125, "type": "SCALAR"}]}
    return build_glb(doc, b"")


def test_the_numbers_of_a_real_model_agree_with_the_inspector():
    glb = base_models.build_base_model("female")
    info = glb_budget.analyze(glb)
    base = inspect_glb(glb)
    assert info["triangles"] == base["triangles"] and info["file_bytes"] == len(glb) and info["draw_calls"] == 3 and info["meshes"] == 1
    assert info["vertices"] > 1000 and info["texture_bytes"] == 0 and info["max_texture_side"] == 0 and info["pictures"] == []


def test_texture_memory_is_width_times_height_times_four_plus_mip_levels():
    info = glb_budget.analyze(model_with_pictures(png(1024, 512), png(256, 256)))
    expected = int(1024 * 512 * 4 * 4 / 3) + int(256 * 256 * 4 * 4 / 3)
    assert info["texture_bytes"] == expected and info["max_texture_side"] == 1024 and [(p["width"], p["height"]) for p in info["pictures"]] == [(1024, 512), (256, 256)]
    assert info["warnings"] == [] and info["textures"] == 2


def test_one_picture_used_twice_is_one_gpu_texture():
    info = glb_budget.analyze(model_with_pictures(png(512, 512), png(512, 512), shared=True))
    assert info["texture_bytes"] == int(512 * 512 * 4 * 4 / 3) and len(info["pictures"]) == 1 and info["textures"] == 2


def test_a_picture_that_is_not_a_power_of_two_is_warned_about():
    info = glb_budget.analyze(model_with_pictures(png(300, 200)))
    assert info["pictures"][0]["power_of_two"] is False and any("power of two" in w for w in info["warnings"])


def test_what_cannot_be_measured_is_unknown_never_guessed_and_never_a_silent_pass():
    broken = build_glb({"asset": {"version": "2.0"}, "buffers": [{"byteLength": 8}], "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": 8}], "images": [{"bufferView": 0, "mimeType": "image/ktx2"}]}, b"\x00" * 8)
    addressed = build_glb({"asset": {"version": "2.0"}, "images": [{"uri": "data:image/png;base64,AAAA"}]}, b"")
    for model in (broken, addressed):
        info = glb_budget.analyze(model)
        assert info["texture_bytes"] is None and info["warnings"]
        verdict = glb_budget.check(info, "desktop")
        assert verdict["passed"] is False and verdict["unknown"] == ["texture_mb"] and verdict["over"] == [] and verdict["rows"]["texture_mb"]["ok"] is None


def test_a_heavy_model_is_over_the_phone_budget_and_the_hint_says_by_how_much():
    info = glb_budget.analyze(heavy_model(400_000))
    mobile, laptop = glb_budget.check(info, "mobile"), glb_budget.check(info, "laptop")
    assert info["triangles"] == 400_000 and mobile["over"] == ["triangles"] and mobile["passed"] is False and laptop["passed"] is True
    assert mobile["rows"]["triangles"] == {"value": 400000, "limit": 100000, "ok": False, "share_of_limit": 4.0}
    assert any("25%" in h and "LOD" in h for h in mobile["hints"]) and mobile["proposal"] is True


def test_a_big_texture_set_is_over_and_the_hint_names_a_size_that_would_fit():
    info = glb_budget.analyze(model_with_pictures(png(4096, 4096)))
    mobile = glb_budget.check(info, "mobile")
    assert set(mobile["over"]) == {"texture_mb", "max_texture_side"} and any("px on the longest side" in h for h in mobile["hints"])
    assert glb_budget.check(info, "laptop")["passed"] is True, "4096 x 4096 with mip levels is about 85 MB: inside the laptop budget (256 MB, 4096 px)"
    assert glb_budget.check(glb_budget.analyze(model_with_pictures(png(2048, 2048))), "laptop")["passed"] is True


def test_unknown_profiles_and_files_that_are_not_glb_are_refused():
    with pytest.raises(ValueError):
        glb_budget.check(glb_budget.analyze(heavy_model(10)), "console")
    with pytest.raises(GlbError):
        glb_budget.analyze(b"not a glb at all, really, no")


def test_the_report_covers_every_device_class():
    rep = glb_budget.report(base_models.build_base_model("male"))
    assert set(rep["profiles"]) == {"mobile", "laptop", "desktop"} and all(p["passed"] for p in rep["profiles"].values())


@pytest.mark.parametrize("sex", base_models.SEXES)
def test_our_own_models_stay_within_the_phone_budget_with_room_to_spare(sex):
    """A guard against a model quietly growing (the base body went from 912 to 4,680 triangles in R-ENGINE-08): a body plus three garments must still fit a phone with half the triangle budget left."""
    body = glb_budget.analyze(base_models.build_base_model(sex))
    parts = [glb_budget.analyze(garments.build_sample_garment(k, sex)[0]) for k in ("jacket", "bottom")]
    scene_triangles = body["triangles"] + sum(p["triangles"] for p in parts)
    scene_calls = body["draw_calls"] + sum(p["draw_calls"] for p in parts)
    assert scene_triangles < glb_budget.PROFILES["mobile"]["triangles"] / 2 and scene_calls < glb_budget.PROFILES["mobile"]["draw_calls"]
    for kind in garments.KINDS:
        assert glb_budget.check(glb_budget.analyze(garments.build_sample_garment(kind, sex)[0]), "mobile")["passed"] is True


def test_the_script_prints_a_table_and_strict_fails_only_for_a_model_that_is_over(tmp_path, capsys):
    assert budget_script.main([]) == 0 and "base_male" in capsys.readouterr().out
    assert budget_script.main(["--strict", "mobile"]) == 0
    heavy = tmp_path / "heavy.glb"
    heavy.write_bytes(heavy_model(400_000))
    assert budget_script.main(["--strict", "mobile", str(heavy)]) == 1
    out = capsys.readouterr().out
    assert "OVER" in out and "hint:" in out and "no GPU" in out
    assert budget_script.main(["--strict", "laptop", str(heavy)]) == 0
