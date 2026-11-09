import pytest

from app.repositories.diagnostics import build_job_diagnostics_repository
from app.repositories.job import build_job_repository
from app.repositories.job_event_uow import build_job_event_uow
from app.repositories.operations import (
    build_alert_delivery_repository,
    build_operations_alert_read_repository,
    build_operations_monitoring_repository,
    build_worker_heartbeat_repository,
    build_worker_health_repository,
)
from app.repositories.outbox import build_outbox_repository
from app.repositories.outbox_admin import build_outbox_admin_repository
from app.repositories.output_asset_link import build_output_asset_link_repository
from app.repositories.output_review import build_output_review_repository
from app.repositories.poll import build_poll_repository
from app.repositories.poll_admin import build_poll_task_admin_repository
from app.repositories.sqlite_output import build_output_repository
from app.storage import get_storage


@pytest.mark.parametrize(
    "factory",
    [
        build_job_diagnostics_repository,
        build_job_repository,
        build_job_event_uow,
        build_alert_delivery_repository,
        build_operations_alert_read_repository,
        build_operations_monitoring_repository,
        build_worker_heartbeat_repository,
        build_worker_health_repository,
        build_outbox_repository,
        build_outbox_admin_repository,
        build_output_asset_link_repository,
        build_output_review_repository,
        build_poll_repository,
        build_poll_task_admin_repository,
    ],
)
def test_postgresql_factory_refuses_silent_sqlite_fallback(factory):
    with pytest.raises(RuntimeError, match="PostgreSQL|storage driver"):
        factory("postgresql")


def test_postgresql_storage_port_refuses_silent_sqlite_fallback():
    with pytest.raises(RuntimeError, match="PostgreSQL storage driver is not implemented"):
        get_storage("postgresql")
