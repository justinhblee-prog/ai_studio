"""B-18 (draft): event envelope shape, identifiers-only data, signing and replay window. Pure functions: no network, no secrets from the environment."""
import json
import re

import pytest

from app import events

SECRET = b"unit-test-secret-0123456789"


def good(t="review.approved"):
    data = {k: "x1" for k in events.EVENT_TYPES[t]}
    return events.build_event(t, "ws-a", data, now=1_700_000_000)


def test_envelope_shape():
    e = good()
    assert set(e) == {"id", "type", "version", "occurred_at", "workspace_id", "data"}
    assert re.fullmatch(r"evt_[0-9a-f]{32}", e["id"]) and e["version"] == 1 and e["occurred_at"] == "2023-11-14T22:13:20Z"


def test_every_type_builds_and_ids_are_unique():
    assert len({good(t)["id"] for t in events.EVENT_TYPES}) == len(events.EVENT_TYPES)


@pytest.mark.parametrize("data", [{"review_id": "r1", "asset_id": "a1"}, {"review_id": "r1", "asset_id": "a1", "status": "approved", "extra": "x"},
                                  {"review_id": "r1", "asset_id": "a1", "status": "two words"}, {"review_id": "r1", "asset_id": "a1", "status": 5}])
def test_data_must_match_the_type_and_be_plain_identifiers(data):
    with pytest.raises(events.EventError):
        events.build_event("review.approved", "ws-a", data)


def test_free_text_and_unknown_types_are_refused():
    with pytest.raises(events.EventError):
        events.build_event("review.rejected", "ws-a", {"review_id": "r1", "asset_id": "a1", "status": "rejected: it looks bad, contact me@example.com"})
    with pytest.raises(events.EventError):
        events.build_event("asset.deleted", "ws-a", {})
    with pytest.raises(events.EventError):
        events.build_event("job.completed", "bad workspace!", {"job_id": "j1", "status": "completed"})


def test_no_declared_field_can_carry_personal_text():
    assert all(not (fields & events.FORBIDDEN_DATA_KEYS) for fields in events.EVENT_TYPES.values())


def test_serialization_is_stable_and_compact():
    e = good()
    assert events.serialize(e) == events.serialize(json.loads(events.serialize(e))) and " " not in events.serialize(e)


def test_sign_and_verify_round_trip_and_tamper_detection():
    body = events.serialize(good())
    header = events.sign(body, SECRET, now=1_700_000_000)
    assert events.verify(body, header, SECRET, now=1_700_000_010)
    assert not events.verify(body + " ", header, SECRET, now=1_700_000_010), "body changed"
    assert not events.verify(body, header, b"another-secret-0123456789", now=1_700_000_010), "wrong secret"
    assert not events.verify(body, header.replace("t=1700000000", "t=1700000001"), SECRET, now=1_700_000_010), "timestamp is part of the signature"


def test_replay_window_both_directions():
    body = events.serialize(good())
    header = events.sign(body, SECRET, now=1_700_000_000)
    assert events.verify(body, header, SECRET, now=1_700_000_000 + events.TOLERANCE_SECONDS)
    assert not events.verify(body, header, SECRET, now=1_700_000_000 + events.TOLERANCE_SECONDS + 1), "too old"
    assert not events.verify(body, header, SECRET, now=1_700_000_000 - events.TOLERANCE_SECONDS - 1), "from the future"


@pytest.mark.parametrize("header", ["", "garbage", "t=1,v1=zz", "t=abc,v1=" + "0" * 64, "v1=" + "0" * 64, "t=1700000000,v1=" + "0" * 63])
def test_malformed_headers_are_false_not_errors(header):
    assert events.verify("{}", header, SECRET, now=1_700_000_000) is False


def test_short_secret_is_refused_for_signing():
    with pytest.raises(events.EventError):
        events.sign("{}", b"short")
    assert events.verify("{}", "t=1700000000,v1=" + "0" * 64, b"", now=1_700_000_000) is False
