"""Lane 5: the image -> 3D provider slot: the mock produces a valid .glb, the researched candidates are registered as NOT integrated and never production eligible."""
import asyncio

import pytest

from app import provider_registry as reg
from app.assets.validation import validate_gltf_upload
from app.providers.mock3d import MockImageTo3D


def test_the_mock_returns_a_valid_glb_that_records_the_picture_and_says_it_is_no_reconstruction():
    glb = asyncio.run(MockImageTo3D().convert(b"some picture bytes"))
    ok = validate_gltf_upload("m.glb", glb, max_bytes=1_000_000)
    assert ok.media_type == "model/gltf-binary"
    assert b"source_sha256" in glb and b'"is_reconstruction":false' in glb
    assert asyncio.run(MockImageTo3D().convert(b"some picture bytes")) == glb, "deterministic"
    assert asyncio.run(MockImageTo3D().convert(b"another")) != glb
    with pytest.raises(ValueError):
        asyncio.run(MockImageTo3D().convert(b""))


def test_candidates_are_registered_as_research_only_and_can_never_be_production_eligible():
    items = [r for r in reg.list_capabilities() if r["capability_key"] == "IMAGE_TO_3D"]
    assert {r["provider_id"] for r in items} == {"mock3d", "meshy", "tripo", "stability"}
    for r in items:
        assert r["production_eligible"] is False and r["evidence_ref"], r
        if r["provider_id"] != "mock3d":
            assert r["verification_status"] == "RESEARCH_ONLY" and r["status"] == "NOT_INTEGRATED"
            assert "NOT reviewed" in r["notes"] or "NOT" in r["notes"]
    assert reg.find_capability("meshy", "image-to-3d", "IMAGE_TO_3D") is not None
    assert reg.find_capability("meshy", "image-to-3d") is None, "the default capability key is still try-on only"


def test_no_data_handling_facts_exist_for_the_candidates_so_they_read_as_unknown_not_safe():
    for provider in ("meshy", "tripo", "stability", "mock3d"):
        policy = reg.data_policy(provider)
        assert policy["trains_on_customer_content"] is None and policy["terms_check_required"] is True


def test_a_candidate_cannot_be_selected_for_try_on_or_production():
    for provider in ("meshy", "tripo", "stability"):
        with pytest.raises(reg.ProviderPolicyError):
            reg.resolve_manual(provider, "image-to-3d", purpose="production")
