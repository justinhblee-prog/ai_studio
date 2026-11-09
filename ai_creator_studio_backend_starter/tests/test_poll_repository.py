from app.repositories.poll import PollRepository, SQLitePollRepository, build_poll_repository

class FakeImplementation:
    def initialize(self): pass
    def claim_next_poll_task(self, worker_id, lease_seconds): return {"worker":worker_id,"lease":lease_seconds}
    def get_job(self, job_id): return {"job_id":job_id}
    def complete_poll_task(self, task_id, worker_id): return True
    def mark_provider_succeeded_for_poll(self, task_id, worker_id, job_id, output_url): return True
    def exhaust_poll_task(self, task_id, worker_id, job_id, **kwargs): return True
    def reschedule_poll_task(self, task_id, worker_id, **kwargs): return True
    def heartbeat_worker(self, worker_id, state, metadata=None): pass

def test_poll_builder_returns_dedicated_adapter():
    adapter=build_poll_repository()
    assert isinstance(adapter, PollRepository)
    assert isinstance(adapter, SQLitePollRepository)
    assert adapter.backend == "sqlite"

def test_poll_builder_fails_closed_for_unimplemented_backend():
    import pytest
    with pytest.raises(RuntimeError, match="PostgreSQL storage driver is not implemented"):
        build_poll_repository("postgresql")

import pytest

@pytest.mark.parametrize("worker_id,lease_seconds", [
    ("", 30), ("   ", 30), (None, 30), ("worker", 0), ("worker", -1),
    ("worker", True), ("worker", 1.5), ("worker", "30"),
    ("w" * 129, 30),
])
def test_poll_claim_rejects_invalid_worker_lease_before_storage(worker_id, lease_seconds):
    adapter = SQLitePollRepository(FakeImplementation())
    with pytest.raises(ValueError):
        adapter.claim_next_poll_task(worker_id, lease_seconds)

@pytest.mark.parametrize("worker_id,lease_seconds,task_id", [
    ("", 30, "task"), ("worker", True, "task"), ("worker", 0, "task"),
    ("worker", 30, ""), ("worker", 30, None),
])
def test_poll_lease_renewal_rejects_invalid_owner_duration_or_task(worker_id, lease_seconds, task_id):
    adapter = SQLitePollRepository(FakeImplementation())
    with pytest.raises(ValueError):
        adapter.renew_poll_task_lease(task_id, worker_id, lease_seconds)
