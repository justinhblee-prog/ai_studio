import pytest
from app.job_state import InvalidJobTransition, transition


def test_happy_path_transitions():
    job = {"status": "queued"}
    transition(job, "running")
    transition(job, "post_processing")
    transition(job, "succeeded")
    assert job["status"] == "succeeded"


@pytest.mark.parametrize("current,target", [
    ("queued", "succeeded"),
    ("running", "succeeded"),
    ("post_processing", "running"),
    ("succeeded", "running"),
    ("failed", "post_processing"),
])
def test_rejects_invalid_transitions(current, target):
    job = {"status": current}
    with pytest.raises(InvalidJobTransition):
        transition(job, target)
    assert job["status"] == current


def test_rejects_unknown_status():
    with pytest.raises(InvalidJobTransition):
        transition({"status": "mystery"}, "running")
