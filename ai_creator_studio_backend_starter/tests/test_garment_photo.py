"""R-ENGINE-15: flat-lay photo -> ESTIMATED dimensions + colour -> fit-ready garment.v1, on SYNTHETIC photos with known truth (app/garment_photo_synth.py).
The tolerances below are what the synthetic set shows today (see docs/GARMENT_PHOTO.md); they say nothing about real garments or real phones."""
import io

import pytest
from PIL import Image, ImageDraw

from app import garment_deform, garment_photo as gp, garment_photo_synth as gs, garments

KINDS = ("top", "jacket", "bottom", "skirt", "dress")


def photo(kind, **kw):
    return gs.synthetic_photo(kind, **kw)


def worst_error(result, truth):
    return max(abs(v - truth[k]) for k, v in result["measurements_cm"].items() if k in truth)


@pytest.mark.parametrize("kind", KINDS)
def test_a_clean_photo_is_measured_within_a_couple_of_centimetres_and_labelled_as_an_estimate(kind):
    data, truth = photo(kind, seed=1)
    result = gp.analyze(data, reference="card", kind=kind)
    assert result["estimated"] is True and "ESTIMATED" in result["label"]
    assert result["kind"] == kind and result["kind_source"] == "hint"
    assert worst_error(result, truth) <= 1.6, (result["measurements_cm"], truth)
    assert sum(abs(a - b) for a, b in zip(result["colour"]["base"], truth["colour"])) / 3 <= 6
    assert result["reference"]["name"] == "card" and 5.8 <= result["reference"]["px_per_cm"] <= 6.4
    assert result["capture_rules"]


def test_a_bigger_size_of_the_same_shape_measures_bigger_in_proportion():
    small = gp.analyze(photo("top", scale=0.85, seed=1)[0], reference="card", kind="top")["measurements_cm"]
    large = gp.analyze(photo("top", scale=1.15, seed=1)[0], reference="card", kind="top")["measurements_cm"]
    assert 1.25 <= large["chest_cm"] / small["chest_cm"] <= 1.45          # truth 1.15 / 0.85 = 1.353
    assert abs(large["length_cm"] - small["length_cm"]) <= 1.0          # the length does not change with the size


def test_an_a4_sheet_works_as_the_reference_too():
    data, truth = photo("top", reference="a4", seed=1)
    result = gp.analyze(data, reference="a4", kind="top")
    assert result["reference"]["name"] == "a4" and worst_error(result, truth) <= 1.8


@pytest.mark.parametrize("condition", ["noise_vignette", "shadow", "low_contrast", "stripes"])
def test_noise_uneven_light_a_soft_shadow_a_low_contrast_background_and_a_dark_pattern_are_survived(condition):
    data, truth = photo("top", condition=condition, seed=1)
    result = gp.analyze(data, reference="card", kind="top")
    assert worst_error(result, truth) <= 3.2, (condition, result["measurements_cm"], truth)


def test_uneven_lighting_is_levelled_out_and_said_so():
    result = gp.analyze(photo("top", condition="noise_vignette", seed=1)[0], reference="card", kind="top")
    assert result["lighting_spread"] > gp.FLAT_WARN and any("lighting" in w for w in result["warnings"])


def test_a_tilted_camera_costs_accuracy_and_the_tests_pin_how_much():
    data, truth = photo("top", condition="perspective", seed=1)
    result = gp.analyze(data, reference="card", kind="top")
    err = worst_error(result, truth)
    assert 1.5 < err <= 8.0, "a mild perspective makes the card and the garment differ in scale: known limit, see docs/GARMENT_PHOTO.md"


def test_the_kind_is_guessed_from_the_outline_only_when_not_given_and_it_says_so():
    for kind in ("top", "bottom", "skirt", "dress"):
        result = gp.analyze(photo(kind, seed=1)[0], reference="card")
        assert result["kind"] == kind and result["kind_source"] == "guess" and any("GUESSED" in w for w in result["warnings"]), kind
    assert gp.analyze(photo("jacket", seed=1)[0], reference="card")["kind"] == "top"       # a jacket cannot be told from a top: the caller must say


def test_a_photo_without_the_reference_object_is_refused():
    data, _ = photo("top", seed=1)
    img = Image.open(io.BytesIO(data)).convert("RGB")
    ImageDraw.Draw(img).rectangle([1100, 0, img.width, img.height], fill=img.getpixel((img.width - 3, img.height - 3)))      # paint the card (right side) over
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    with pytest.raises(gp.GarmentPhotoError) as err:
        gp.analyze(buf.getvalue(), reference="card", kind="top")
    assert err.value.code == "PHOTO_REFERENCE_NOT_FOUND"


def test_a_garment_cut_by_the_picture_edge_is_refused():
    data, _ = photo("top", seed=1)
    img = Image.open(io.BytesIO(data)).convert("RGB").crop((150, 0, 1400, 1100))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    with pytest.raises(gp.GarmentPhotoError) as err:
        gp.analyze(buf.getvalue(), reference="card", kind="top")
    assert err.value.code == "PHOTO_GARMENT_CLIPPED"


def test_a_pattern_close_to_the_background_colour_is_refused_instead_of_answering_with_garbage():
    with pytest.raises(gp.GarmentPhotoError) as err:
        gp.analyze(photo("top", condition="stripes_light", seed=1)[0], reference="card", kind="top")
    assert err.value.code == "PHOTO_GARMENT_FRAGMENTED"


def test_bad_input_is_refused_with_catalogued_codes():
    data, _ = photo("top", seed=1)
    for args, code in (((b"not a picture",), "PHOTO_UNREADABLE"), ((data,), "PHOTO_REFERENCE_UNKNOWN"), ((data,), "PHOTO_KIND")):
        kwargs = {"reference": "card", "kind": "top"}
        if code == "PHOTO_REFERENCE_UNKNOWN":
            kwargs["reference"] = "coin"
        if code == "PHOTO_KIND":
            kwargs["kind"] = "hat"
        with pytest.raises(gp.GarmentPhotoError) as err:
            gp.analyze(*args, **kwargs)
        assert err.value.code == code
    with pytest.raises(gp.GarmentPhotoError) as err:
        gp.analyze(b"x" * (gp.MAX_BYTES + 1), reference="card")
    assert err.value.code == "PHOTO_TOO_LARGE"


def test_the_estimate_becomes_a_valid_fit_ready_garment_v1_that_can_be_fitted():
    result = gp.analyze(photo("top", seed=1)[0], reference="card", kind="top")
    glb, spec, report = gp.to_garment(result, garment_id="photo-top-1", sex="female", provenance="user photo test", rights_confirmed=True)
    garments.validate_garment(glb, spec)
    assert spec["id"] == "photo-top-1" and spec["kind"] == "top" and "fit" in spec and report["fit_ready"] is True
    assert "ESTIMATES" in spec["source"]["provenance"] and spec["source"]["rights_confirmed"] is True
    chart = spec["sizes"][spec["reference_size"]]
    assert abs(chart["chest_cm"] - result["measurements_cm"]["chest_cm"]) <= 2.5, (chart, result["measurements_cm"])
    assert abs(chart["length_cm"] - result["measurements_cm"]["length_cm"]) <= 2.5 or report["notes"]
    fitted, fit_report = garment_deform.deform_garment(glb, spec, None)
    assert fitted and "penetrations" in fit_report


def test_the_colour_of_the_photo_becomes_the_garment_colour():
    result = gp.analyze(photo("top", seed=1, colour=(30, 120, 60))[0], reference="card", kind="top")
    glb, _, _ = gp.to_garment(result, garment_id="photo-green", sex="male", provenance="user photo test", rights_confirmed=True)
    from app import glb_tools
    doc, _ = glb_tools.parse_glb(glb)
    factor = doc["materials"][0]["pbrMetallicRoughness"]["baseColorFactor"]
    assert factor[1] > factor[0] and factor[1] > factor[2], factor            # green stays the strongest channel


def test_a_garment_without_confirmed_rights_is_refused_and_an_implausible_size_too():
    result = gp.analyze(photo("top", seed=1)[0], reference="card", kind="top")
    with pytest.raises(garments.GarmentError):
        gp.to_garment(result, garment_id="x", sex="female", provenance="user photo test", rights_confirmed=False)
    absurd = {**result, "measurements_cm": {**result["measurements_cm"], "chest_cm": 400.0}}
    with pytest.raises(gp.GarmentPhotoError) as err:
        gp.to_garment(absurd, garment_id="x", sex="female", provenance="p", rights_confirmed=True)
    assert err.value.code == "PHOTO_SIZE_IMPLAUSIBLE"


def test_every_kind_converts_to_a_valid_garment():
    for kind in KINDS:
        result = gp.analyze(photo(kind, seed=1)[0], reference="card", kind=kind)
        glb, spec, _ = gp.to_garment(result, garment_id=f"photo-{kind}", sex="female", provenance="user photo test", rights_confirmed=True)
        garments.validate_garment(glb, spec)
        assert spec["kind"] == kind


def test_the_synthetic_photos_are_deterministic():
    assert photo("dress", condition="noise_vignette", seed=2)[0] == photo("dress", condition="noise_vignette", seed=2)[0]
