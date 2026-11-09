from app.repositories.job import JobRepository, SQLiteJobRepository
from app.repositories.event import EventRepository, SQLiteEventRepository
from app.dependencies import get_job_repository, get_event_repository

class FakeImplementation:
    def create_job(self, job, key=None): return job, True
    def get_job(self, job_id): return {"job_id": job_id}
    def get_idempotent_job(self, workspace_id, key): return None
    def transition_job(self, job_id, target, **kwargs): return {"job_id": job_id, "status": target}
    def update_job(self, job_id, updates, **kwargs): return {"job_id": job_id, **updates}
    def list_events(self, job_id): return [{"job_id": job_id, "event_type": "JOB_CREATED"}]

def test_sqlite_job_adapter_satisfies_port():
    repo = SQLiteJobRepository(FakeImplementation())
    assert isinstance(repo, JobRepository)
    assert repo.get("job_1") == {"job_id": "job_1"}
    assert repo.transition("job_1", "running")["status"] == "running"

def test_sqlite_event_adapter_satisfies_port():
    repo = SQLiteEventRepository(FakeImplementation())
    assert isinstance(repo, EventRepository)
    assert repo.list_for_job("job_1")[0]["event_type"] == "JOB_CREATED"

def test_dependency_composition_is_cached_and_sqlite_only():
    get_job_repository.cache_clear(); get_event_repository.cache_clear()
    assert get_job_repository() is get_job_repository()
    assert get_event_repository() is get_event_repository()
    assert get_job_repository().backend == "sqlite"
    assert get_event_repository().backend == "sqlite"


def test_dedicated_job_repository_owns_lifecycle_sql_and_execution_adapter(monkeypatch, tmp_path):
    from app import config, job_repository
    from app.repositories.job import build_job_repository
    from app.repositories.execution import ExecutionRepository, SQLiteExecutionRepository
    monkeypatch.setattr(config, "ASSET_DATABASE_PATH", tmp_path / "dedicated-job.sqlite3")
    monkeypatch.setattr(config, "GENERATION_DATABASE_PATH", None)
    job_repository.initialize()
    job_repository.create_job({
        "job_id": "job-dedicated-repo", "workspace_id": "ws-dedicated", "owner_id": "owner",
        "status": "queued", "provider": "mock", "model": "mock-tryon",
        "payload_hash": "dedicated-hash", "payload": {"prompt": "test"},
    })
    repository = build_job_repository("sqlite")
    assert isinstance(repository, JobRepository)
    assert isinstance(SQLiteExecutionRepository(), ExecutionRepository)
    result = repository.transition("job-dedicated-repo", "running", updates={"provider_request_id": "provider-1"})
    assert result["status"] == "running"
    with job_repository._connect() as conn:
        execution = conn.execute("SELECT status,provider_request_id FROM generation_executions WHERE job_id=?", ("job-dedicated-repo",)).fetchone()
    assert execution["status"] == "running"
    assert execution["provider_request_id"] == "provider-1"


def test_dedicated_job_repository_keeps_job_execution_and_event_atomic(monkeypatch, tmp_path):
    import pytest
    from app import config, job_repository
    from app.repositories.job import build_job_repository
    monkeypatch.setattr(config, "ASSET_DATABASE_PATH", tmp_path / "dedicated-atomic.sqlite3")
    monkeypatch.setattr(config, "GENERATION_DATABASE_PATH", None)
    job_repository.initialize()
    job_repository.create_job({
        "job_id": "job-dedicated-atomic", "workspace_id": "ws-dedicated", "owner_id": "owner",
        "status": "queued", "provider": "mock", "model": "mock-tryon",
        "payload_hash": "atomic-hash", "payload": {"prompt": "test"},
    })
    with job_repository._connect() as conn:
        conn.execute("""CREATE TRIGGER reject_dedicated_event BEFORE INSERT ON generation_job_events
            WHEN NEW.event_type='REJECT_DEDICATED' BEGIN SELECT RAISE(ABORT, 'dedicated event failure'); END""")
    repository = build_job_repository("sqlite")
    with pytest.raises(Exception, match="dedicated event failure"):
        repository.transition("job-dedicated-atomic", "running", event_type="REJECT_DEDICATED")
    assert job_repository.get_job("job-dedicated-atomic")["status"] == "queued"
    with job_repository._connect() as conn:
        execution = conn.execute("SELECT status FROM generation_executions WHERE job_id=?", ("job-dedicated-atomic",)).fetchone()
    assert execution["status"] == "queued"
