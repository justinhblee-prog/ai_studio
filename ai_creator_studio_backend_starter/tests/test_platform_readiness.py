from app import config
from app.platform_readiness import build_platform_readiness


def test_readiness_report_is_read_only_and_does_not_expose_secret_values(monkeypatch):
    monkeypatch.setattr(config, "DATABASE_BACKEND", "sqlite")
    monkeypatch.setattr(config, "DATABASE_URL", "postgresql://user:super-secret@example.invalid/db")
    monkeypatch.setattr(config, "FASHN_API_KEY", "fashn-secret-value")
    monkeypatch.setattr(config, "PROVIDER_MODE", "mock")

    report = build_platform_readiness()
    rendered = repr(report)

    assert report["scope"] == "read-only-preflight"
    assert report["overall_status"] == "blocked"
    assert report["database_url_configured"] is True
    assert "super-secret" not in rendered
    assert "fashn-secret-value" not in rendered
    assert {item["id"] for item in report["checks"]} == {
        "database_runtime", "postgresql_repository_coverage", "supabase_postgresql", "supabase_storage",
        "worker_runtime", "ai_provider", "vercel_preview",
    }
    assert "supabase_postgresql" in report["blockers"]
    assert "vercel_preview" in report["blockers"]


def test_readiness_report_marks_sqlite_and_mock_as_local_capabilities(monkeypatch):
    monkeypatch.setattr(config, "DATABASE_BACKEND", "sqlite")
    monkeypatch.setattr(config, "DATABASE_URL", "")
    monkeypatch.setattr(config, "FASHN_API_KEY", "")
    monkeypatch.setattr(config, "PROVIDER_MODE", "mock")

    report = build_platform_readiness()
    by_id = {item["id"]: item for item in report["checks"]}
    assert by_id["database_runtime"]["status"] == "supported"
    assert by_id["ai_provider"]["status"] == "partial"
    assert report["database_url_configured"] is False
    assert "live integration tests" in report["disclaimer"]


def test_postgresql_selection_is_never_reported_as_supported(monkeypatch):
    monkeypatch.setattr(config, "DATABASE_BACKEND", "postgresql")
    report = build_platform_readiness()
    database = next(item for item in report["checks"] if item["id"] == "database_runtime")
    assert database["status"] == "blocked"
    assert "not implemented" in database["detail"]
