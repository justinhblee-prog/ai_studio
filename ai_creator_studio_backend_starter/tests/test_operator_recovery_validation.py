import pytest

from app.repositories.operator_validation import validate_operator_action, validate_resource_id


@pytest.mark.parametrize("actor,reason", [
    ("", "reviewed"), ("   ", "reviewed"), ("x" * 129, "reviewed"),
    ("admin", ""), ("admin", "   "), ("admin", "x" * 501),
    (None, "reviewed"), ("admin", None),
])
def test_operator_action_rejects_invalid_actor_or_reason(actor, reason):
    with pytest.raises(ValueError):
        validate_operator_action(actor, reason)


def test_operator_action_normalizes_reason_and_actor():
    assert validate_operator_action(" admin ", "  verified recovery  ") == ("admin", "verified recovery")


@pytest.mark.parametrize("value", [None, "", "   ", "x" * 129])
def test_resource_id_rejects_invalid_values(value):
    with pytest.raises(ValueError):
        validate_resource_id(value, "resource_id")


def test_poll_admin_validates_before_legacy_side_effect():
    class Fake:
        called = False
        def retry_poll_task(self, *args, **kwargs):
            self.called = True
    fake = Fake()
    from app.repositories.poll_admin import SQLitePollTaskAdminRepository
    repo = SQLitePollTaskAdminRepository(fake)
    with pytest.raises(ValueError, match="reason"):
        repo.retry("task-1", "ws-1", actor_id="admin-1", reason="  ")
    assert fake.called is False


def test_outbox_admin_validates_provider_reference_and_operator_reason_before_delegation():
    class Fake:
        called = False
        def reconcile_unknown_submission(self, *args, **kwargs):
            self.called = True
    fake = Fake()
    from app.repositories.outbox_admin import SQLiteOutboxAdminRepository
    repo = SQLiteOutboxAdminRepository(fake)
    with pytest.raises(ValueError, match="provider_request_id"):
        repo.reconcile_unknown_submission("job-1", action="attach_request_id", actor_id="admin-1",
                                          reason="verified", provider_request_id=" " )
    assert fake.called is False
