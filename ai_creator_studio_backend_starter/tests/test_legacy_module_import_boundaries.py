from pathlib import Path


def test_application_runtime_has_no_import_dependency_on_legacy_job_repository():
    app_root = Path("app")
    offenders = []
    for path in app_root.rglob("*.py"):
        source = path.read_text()
        if "from app import job_repository" in source or "from app.job_repository import" in source:
            offenders.append(str(path))
    assert offenders == []


def test_legacy_job_repository_is_sql_free_compatibility_facade():
    source = Path("app/job_repository.py").read_text()
    forbidden = ("SELECT ", "INSERT INTO ", "UPDATE ", "DELETE FROM ", "CREATE TABLE ")
    assert not any(statement in source.upper() for statement in forbidden)
    assert "Backward-compatible facade" in source
