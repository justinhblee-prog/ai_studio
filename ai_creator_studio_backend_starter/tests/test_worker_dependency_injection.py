"""Worker entry points accept explicit repository ports without module globals."""
import asyncio


def test_outbox_worker_accepts_explicit_repository(monkeypatch):
    from app import worker
    class Repo:
        def claim_next_outbox(self, worker_id, lease_seconds):
            return None
    monkeypatch.setattr(worker, "build_outbox_repository", lambda: (_ for _ in ()).throw(AssertionError("factory called")))
    assert asyncio.run(worker.process_one(Repo())) is False
    assert not hasattr(worker, "job_repository")


def test_poll_worker_accepts_explicit_repository(monkeypatch):
    from app import poll_worker
    class Repo:
        def claim_next_poll_task(self, worker_id, lease_seconds):
            return None
    monkeypatch.setattr(poll_worker, "build_poll_repository", lambda: (_ for _ in ()).throw(AssertionError("factory called")))
    assert asyncio.run(poll_worker.process_one("test-worker", Repo())) is False
    assert not hasattr(poll_worker, "job_repository")


def test_operations_worker_accepts_explicit_repository(monkeypatch):
    from app import monitor_worker
    class Repo:
        def evaluate_operational_alerts(self, **kwargs):
            return []
        def heartbeat_worker(self, worker_id, state, metadata=None):
            self.heartbeat = (worker_id, state, metadata)
    repo = Repo()
    monkeypatch.setattr(monitor_worker, "build_operations_repository", lambda: (_ for _ in ()).throw(AssertionError("factory called")))
    result = asyncio.run(monitor_worker.run_once(repo))
    assert result == {"active_alerts": [], "delivery_attempted": False}
    assert repo.heartbeat[1] == "running"
    assert not hasattr(monitor_worker, "job_repository")


def test_worker_composition_root_uses_dedicated_outbox_adapter():
    from app import job_repository
    from app.worker_repositories import build_worker_repositories
    bundle = build_worker_repositories()
    assert bundle.outbox._impl is None
    assert bundle.poll._impl is None
    assert bundle.operations._impl is None
