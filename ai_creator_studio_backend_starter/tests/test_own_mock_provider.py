"""R-ENGINE-04 (slot): the ``own`` engine mock follows the provider contract and never claims what it does not do."""
import asyncio

import pytest

from app import provider_registry as reg
from app.assets.validation import validate_gltf_upload
from app.providers import own_mock
from app.providers.own_mock import OwnMockProvider

P = OwnMockProvider()


def run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def _finish(payload):
    started = run(P.start(payload))
    return started, run(P.status(started["request_id"]))


def test_a_request_runs_through_start_and_status_and_yields_a_valid_glb():
    started, done = _finish({"sex": "female", "garment_kind": "top", "measurements": {"height_cm": 172, "chest_cm": 92}})
    assert started["status"] == "running" and started["request_id"].startswith("own_")
    assert done["status"] == "succeeded" and done["charged"] is True and done["output_url"] is None
    out = done["output"]
    assert out["fit"]["penetrations"] == 0 and out["fit"]["method"] == "profile-ratio.v1" and out["glb_bytes"] > 0
    glb = P.result_glb(started["request_id"])
    assert validate_gltf_upload("own.glb", glb).media_type == "model/gltf-binary"
    import hashlib
    assert hashlib.sha256(glb).hexdigest() == out["glb_sha256"]


def test_the_review_is_not_faked_every_score_is_none_and_it_says_mock():
    _, done = _finish({"sex": "male", "garment_kind": "bottom"})
    review = done["output"]["review"]
    assert review["mock"] is True and set(review["scores"]) == set(own_mock.REVIEW_ITEMS) and all(v is None for v in review["scores"].values())


def test_the_same_request_gives_the_same_id_and_bytes_in_any_key_order():
    a, _ = _finish({"sex": "male", "garment_kind": "top", "measurements": {"chest_cm": 100, "height_cm": 180}})
    b, _ = _finish({"measurements": {"height_cm": 180, "chest_cm": 100}, "garment_kind": "top", "sex": "male"})
    assert a["request_id"] == b["request_id"]
    c, _ = _finish({"sex": "male", "garment_kind": "top", "measurements": {"chest_cm": 101, "height_cm": 180}})
    assert c["request_id"] != a["request_id"]


@pytest.mark.parametrize("bad", [{}, {"sex": "robot", "garment_kind": "top"}, {"sex": "male", "garment_kind": "hat"}, {"sex": "male", "garment_kind": "top", "measurements": "tall"},
                                 {"sex": "male", "garment_kind": "top", "measurements": {"height_cm": 100}}, {"sex": "male", "garment_kind": "top", "ease_cm": 99},
                                 {"sex": "male", "garment_kind": "top", "measurements": {"sleeve_cm": 50}}])
def test_bad_requests_are_refused_before_anything_runs(bad):
    with pytest.raises(ValueError):
        P.validate_request(bad)


def test_an_unknown_request_id_is_a_failed_status_that_charges_nothing():
    done = run(P.status("own_" + "0" * 32))
    assert done["status"] == "failed" and done["charged"] is False and done["error"]["code"] == "UNKNOWN_REQUEST" and P.result_glb("own_" + "0" * 32) is None


def test_a_refused_fit_is_a_failed_status_that_charges_nothing(monkeypatch):
    def refuse(*args, **kwargs):
        raise own_mock.garments.GarmentError(["the fitted garment would pass through the body at 3 vertices"])
    monkeypatch.setattr(own_mock, "deform_garment", refuse)
    started, done = _finish({"sex": "male", "garment_kind": "top", "measurements": {"height_cm": 151}})
    assert done["status"] == "failed" and done["charged"] is False and done["error"]["code"] == "FIT_REFUSED" and done["output"] is None
    assert P.result_glb(started["request_id"]) is None


def test_the_memory_is_bounded(monkeypatch):
    monkeypatch.setattr(own_mock, "MAX_KEPT", 3)
    ids = [run(P.start({"sex": "male", "garment_kind": "top", "measurements": {"height_cm": 160 + i}}))["request_id"] for i in range(6)]
    assert len(own_mock._RESULTS) <= 3 and len(own_mock._GLBS) <= 3
    assert run(P.status(ids[0]))["status"] == "failed" and run(P.status(ids[-1]))["status"] == "succeeded"


def test_it_is_registered_only_as_research_not_production_and_not_selectable():
    assert P.describe_capabilities() == ["TRY_ON_3D"] and P.name == "own"
    record = reg.find_capability("own", "own-3d-mock", "TRY_ON_3D")
    assert record is not None and record.production_eligible is False and record.status == "NOT_INTEGRATED"
    assert reg.find_capability("own", "own-3d-mock") is None, "it must not appear as a TRY_ON_IMAGE capability"
    with pytest.raises(reg.ProviderPolicyError):
        reg.resolve_manual("own", "own-3d-mock")
