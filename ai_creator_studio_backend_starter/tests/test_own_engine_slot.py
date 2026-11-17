"""R-ENGINE-05: the in-house 3D engine exists in the registry only as a CLOSED slot: listed, never production eligible, never dispatchable, data handling unrecorded."""
import pytest
from fastapi.testclient import TestClient

from app import provider_registry as reg
from app.main import app

client = TestClient(app)


def test_the_in_house_engine_is_listed_as_research_only_and_not_integrated():
    record = reg.find_capability("own3d", "fitted-shell-v0")
    assert record is not None and record.capability_key == "TRY_ON_IMAGE"
    assert record.verification_status == "RESEARCH_ONLY" and record.status == "NOT_INTEGRATED" and record.production_eligible is False
    assert record.evidence_ref and "no cloth simulation" in record.notes and "No adapter" in record.notes
    assert not (record.supports_async or record.supports_status_query or record.supports_cancel or record.supports_webhook)


def test_it_can_never_be_selected_for_production_by_manual_or_routing_modes():
    with pytest.raises(reg.ProviderPolicyError) as manual:
        reg.resolve_manual("own3d", "fitted-shell-v0", purpose="production")
    assert manual.value.code == "PROVIDER_NOT_PRODUCTION_READY"
    with pytest.raises(reg.ProviderPolicyError) as routed:
        reg.resolve_routing("MANUAL", "own3d", "fitted-shell-v0")
    assert routed.value.code == "PROVIDER_NOT_PRODUCTION_READY"
    with pytest.raises(reg.ProviderPolicyError) as auto:
        reg.resolve_routing("AUTO", "own3d", "fitted-shell-v0")
    assert auto.value.code == "AUTO_ROUTING_NOT_APPROVED"


def test_no_data_handling_facts_are_recorded_so_it_reads_as_unknown_not_safe():
    policy = reg.data_policy("own3d")
    assert policy["trains_on_customer_content"] is None and policy["terms_check_required"] is True


def test_the_public_capability_list_shows_it_without_changing_the_documented_providers():
    items = client.get("/v1/engines/capabilities").json()["items"]
    own = [i for i in items if i["provider_id"] == "own3d"]
    assert len(own) == 1 and own[0]["production_eligible"] is False and own[0]["status"] == "NOT_INTEGRATED"
    assert len([i for i in items if i["provider_id"] == "fashn"]) == 2, "the FASHN records are untouched"
    assert all(i["production_eligible"] is False for i in items if i["provider_id"] != "mock"), "nothing but the flow-only mock can ever look usable"

