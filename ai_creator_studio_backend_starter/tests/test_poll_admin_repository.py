from app.repositories.poll_admin import PollTaskAdminRepository, SQLitePollTaskAdminRepository, build_poll_task_admin_repository

class FakeImplementation:
    def list_poll_tasks(self, workspace_id, *, status=None, limit=100):
        return [{"workspace_id":workspace_id,"status":status,"limit":limit}]
    def retry_poll_task(self, task_id, workspace_id, *, actor_id, reason):
        return {"task_id":task_id,"workspace_id":workspace_id,"actor_id":actor_id,"reason":reason}

def test_poll_admin_adapter_implements_port_and_preserves_scope():
    adapter=SQLitePollTaskAdminRepository(FakeImplementation())
    assert isinstance(adapter, PollTaskAdminRepository)
    assert adapter.list_for_workspace("ws-1",status="pending",limit=7)==[{"workspace_id":"ws-1","status":"pending","limit":7}]
    assert adapter.retry("task-1","ws-1",actor_id="admin-1",reason="manual review")["workspace_id"]=="ws-1"

def test_poll_admin_builder_fails_closed_for_postgresql():
    import pytest
    with pytest.raises(RuntimeError,match="PostgreSQL storage driver is not implemented"):
        build_poll_task_admin_repository("postgresql")
