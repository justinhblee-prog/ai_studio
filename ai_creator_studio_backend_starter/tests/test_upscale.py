"""E-09d: classical upscaling (no model): sizes, limits, alpha without a dark fringe, the round-trip comparison, and the photo-steps integration."""
import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from app import upscale
from app.main import app
from app.photo_steps import StepError, run_steps, validate_steps
from tests.test_photo_steps_api import auth, env, run  # noqa: F401

client = TestClient(app)


def test_sizes_follow_the_factor_and_100_percent_is_an_unchanged_copy():
    img = Image.new("RGB", (40, 30), (10, 120, 200))
    assert upscale.upscale(img, 200).size == (80, 60) and upscale.upscale(img, 150).size == (60, 45) and upscale.upscale(img, 400, 0).size == (160, 120)
    same = upscale.upscale(img, 100, 0)
    assert same.size == img.size and same.tobytes() == img.tobytes() and same is not img


def test_a_flat_colour_stays_the_same_colour_at_any_factor_and_sharpening():
    img = Image.new("RGB", (32, 32), (90, 140, 60))
    for factor, sharpen in ((200, 0), (200, 100), (300, 50)):
        out = upscale.upscale(img, factor, sharpen)
        assert out.getextrema() == ((90, 90), (140, 140), (60, 60))


@pytest.mark.parametrize("size, factor", [((5000, 100), 400), ((8192, 10), 200), ((7000, 7000), 100)])
def test_a_result_that_is_too_large_is_refused_before_anything_is_allocated(size, factor):
    with pytest.raises(upscale.UpscaleError) as exc:
        upscale.target_size(size, factor)
    assert exc.value.code == "STEP_RESULT_TOO_LARGE" and "megapixels" in str(exc.value)


def test_an_unknown_method_is_refused():
    with pytest.raises(upscale.UpscaleError) as exc:
        upscale.upscale(Image.new("RGB", (8, 8)), 200, 0, "magic")
    assert exc.value.code == "UPSCALE_METHOD_UNKNOWN"


def test_alpha_is_kept_and_a_transparent_edge_gets_no_dark_fringe():
    img = Image.new("RGBA", (60, 60), (0, 0, 0, 0))
    ImageDraw.Draw(img).ellipse((10, 10, 50, 50), fill=(255, 255, 255, 255))
    for sharpen in (0, 100):
        out = upscale.upscale(img, 300, sharpen)
        assert out.mode == "RGBA" and out.size == (180, 180)
        assert out.getchannel("A").getextrema() == (0, 255)
        px = out.load()
        darkest = min(min(px[x, y][:3]) for x in range(out.width) for y in range(out.height) if px[x, y][3] > 0)
        assert darkest >= 235, f"sharpen {sharpen}: a dark fringe of {darkest} appeared next to the transparent area"


def test_sharpening_makes_a_soft_edge_steeper_but_never_leaves_the_valid_range():
    img = Image.new("RGB", (64, 32), (30, 30, 30))
    ImageDraw.Draw(img).rectangle((32, 0, 63, 31), fill=(220, 220, 220))
    soft = upscale.upscale(img, 200, 0)
    sharp = upscale.upscale(img, 200, 100)
    row = lambda im: [im.getpixel((x, 30))[0] for x in range(54, 76)]       # across the edge at x = 64
    assert max(abs(b - a) for a, b in zip(row(sharp), row(sharp)[1:])) >= max(abs(b - a) for a, b in zip(row(soft), row(soft)[1:]))
    assert sharp.getextrema()[0][0] >= 0 and sharp.getextrema()[0][1] <= 255


def test_the_round_trip_comparison_is_deterministic_capped_and_ranks_real_interpolation_above_nearest():
    one, two = upscale.round_trip_table(200), upscale.round_trip_table(200)
    assert one == two and len(one["rows"]) == 5
    assert all(0 < v <= upscale.PSNR_CAP for row in one["rows"] for k, v in row.items() if k != "case")
    mean = one["mean_psnr_db"]
    assert mean["lanczos+sharpen30"] > mean["nearest"] + 0.5 and mean["lanczos"] > mean["bilinear"], "measured at 2x on the synthetic set; the margin is small, the order is what is pinned"
    assert one["best"] in ("lanczos+sharpen30", "bicubic+sharpen30") and "no new detail" in one["note"]
    assert upscale.DEFAULT_METHOD == "lanczos"


def test_the_upscale_step_validates_runs_records_and_refuses_a_too_large_result():
    assert validate_steps([{"op": "upscale"}]) == [{"op": "upscale", "factor_pct": 200, "sharpen_pct": 30}]
    for bad in ({"factor_pct": 99}, {"factor_pct": 401}, {"factor_pct": "2"}, {"sharpen_pct": 101}, {"sharpen_pct": True}, {"mode": "x"}):
        with pytest.raises(StepError):
            validate_steps([{"op": "upscale", **bad}])
    out, records = run_steps(Image.new("RGB", (50, 40), (200, 30, 30)), [{"op": "upscale", "factor_pct": 250}])
    assert out.size == (125, 100) and records[0]["size_in"] == [50, 40] and records[0]["size_out"] == [125, 100] and records[0]["mode"] == "local"
    with pytest.raises(StepError) as exc:
        run_steps(Image.new("RGB", (4000, 4000)), [{"op": "upscale", "factor_pct": 400}])
    assert exc.value.code == "STEP_RESULT_TOO_LARGE"


def test_through_the_api_the_result_is_a_new_asset_and_a_too_large_request_is_a_clear_422(env):
    r = run(env, [{"op": "upscale", "factor_pct": 300, "sharpen_pct": 0}])
    assert r.status_code == 201, r.text
    assert r.json()["steps"][0]["size_in"] == [200, 100] and r.json()["steps"][0]["size_out"] == [600, 300]
    chained = run(env, [{"op": "fit_canvas", "width": 3000, "height": 3000}, {"op": "upscale", "factor_pct": 400}])
    assert chained.status_code in (400, 422) and "STEP_RESULT_TOO_LARGE" in chained.text
