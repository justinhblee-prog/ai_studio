from fastapi.testclient import TestClient


def test_operations_api_routes_use_dedicated_dependencies(monkeypatch):
    from app.main import app
    from app import main
    from app.dependencies import (get_worker_health_repository,
        get_operations_monitoring_repository, get_operations_alert_read_repository)
    from app.assets.routes import current_user

    class Health:
        def worker_health(self, stale):
            return {"workers": [], "stale_after_seconds": stale}

    class Monitoring:
        def snapshot(self, stale):
            return {"workers": [], "outbox_counts": {}, "poll_task_counts": {},
                    "oldest_pending_outbox_age_seconds": None,
                    "oldest_pending_poll_age_seconds": None, "alerts": {}}

    class Alerts:
        def list_alerts(self, **kwargs):
            return []

    monkeypatch.setattr(main, "require_platform_ops", lambda user: None)
    app.dependency_overrides[current_user] = lambda: "test-user"
    app.dependency_overrides[get_worker_health_repository] = lambda: Health()
    app.dependency_overrides[get_operations_monitoring_repository] = lambda: Monitoring()
    app.dependency_overrides[get_operations_alert_read_repository] = lambda: Alerts()
    try:
        client = TestClient(app)
        headers = {"Authorization": "Bearer test-user"}
        assert client.get("/internal/ops/workers", headers=headers).status_code == 200
        assert client.get("/internal/ops/metrics", headers=headers).status_code == 200
        response = client.get("/internal/ops/alerts", headers=headers)
        assert response.status_code == 200
        assert response.json()["items"] == []
    finally:
        app.dependency_overrides.clear()


def test_public_health_route_does_not_read_worker_health_repository(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.dependencies import get_worker_health_repository

    class Health:
        def worker_health(self, stale):
            raise AssertionError("public health must not read operational diagnostics")

    app.dependency_overrides[get_worker_health_repository] = lambda: Health()
    try:
        response = TestClient(app).get("/health")
        assert response.status_code == 200
        assert response.json() == {"ok": True, "version": "0.7.0"}
    finally:
        app.dependency_overrides.clear()


def test_job_repository_does_not_have_broad_legacy_getattr_bridge():
    from app.repositories.job import SQLiteJobRepository
    repository = SQLiteJobRepository()
    assert not hasattr(repository, "prometheus_metrics")
    assert not hasattr(repository, "worker_health")
