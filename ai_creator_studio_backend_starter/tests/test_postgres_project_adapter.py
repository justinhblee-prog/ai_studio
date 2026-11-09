import pytest
from app.repositories.postgres_projects import PostgreSQLProjectRepository


def test_postgres_project_adapter_is_explicit_and_lazy():
    assert PostgreSQLProjectRepository().backend == "postgresql"


@pytest.mark.parametrize("name,project_type,description,external_reference", [
    ("", "general", None, None),
    ("x" * 121, "general", None, None),
    ("valid", "", None, None),
    ("valid", "x" * 65, None, None),
    ("valid", "general", "x" * 2001, None),
    ("valid", "general", None, "x" * 129),
])
def test_create_validates_fields_before_database_access(name, project_type, description, external_reference):
    with pytest.raises(ValueError):
        PostgreSQLProjectRepository().create(
            workspace_id="ws_1", actor_id="user_1", name=name,
            project_type=project_type, description=description,
            external_reference=external_reference,
        )


def test_update_rejects_unknown_status_before_database_access():
    with pytest.raises(ValueError, match="status"):
        PostgreSQLProjectRepository().update(
            "prj_1", "user_1", name="Project", project_type="general", status="DELETED"
        )


def test_project_status_contract():
    repo = PostgreSQLProjectRepository()
    for status in ("ACTIVE", "ARCHIVED", "COMPLETED"):
        repo._validate_status(status)
    with pytest.raises(ValueError):
        repo._validate_status("DELETED")


class _Result:
    def __init__(self, row=None, rows=None):
        self._row = row
        self._rows = rows if rows is not None else ([] if row is None else [row])

    def fetchone(self):
        return self._row

    def fetchall(self):
        return self._rows


class _FakeConnection:
    def __init__(self, member_role="owner", project=None):
        self.member_role = member_role
        self.project = project
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), params))
        normalized = " ".join(sql.split())
        if "SELECT role FROM workspace_members" in normalized:
            row = {"role": self.member_role} if self.member_role else None
            return _Result(row)
        if "SELECT * FROM projects WHERE project_id" in normalized:
            return _Result(self.project)
        return _Result()


def test_create_project_uses_workspace_membership_and_returns_persisted_row(monkeypatch):
    from app.repositories import postgres_projects

    persisted = {
        "project_id": "prj_test", "workspace_id": "ws_test", "name": "Lookbook",
        "project_type": "fashion", "status": "ACTIVE", "description": None,
        "external_reference": None, "created_by": "user_test",
        "created_at": "2026-11-07T00:00:00+00:00", "updated_at": "2026-11-07T00:00:00+00:00",
    }
    fake = _FakeConnection(project=persisted)
    monkeypatch.setattr(postgres_projects, "connect", lambda: fake)
    result = PostgreSQLProjectRepository().create(
        workspace_id="ws_test", actor_id="user_test", name="Lookbook", project_type="fashion"
    )
    assert result == persisted
    assert any("INSERT INTO projects" in sql for sql, _ in fake.calls)
    assert any("SELECT * FROM projects" in sql for sql, _ in fake.calls)


def test_create_project_denies_non_member_before_insert(monkeypatch):
    from app.repositories import postgres_projects

    fake = _FakeConnection(member_role=None)
    monkeypatch.setattr(postgres_projects, "connect", lambda: fake)
    with pytest.raises(PermissionError, match="not a member"):
        PostgreSQLProjectRepository().create(
            workspace_id="ws_test", actor_id="outsider", name="Lookbook"
        )
    assert not any("INSERT INTO projects" in sql for sql, _ in fake.calls)


def test_create_project_denies_viewer_before_insert(monkeypatch):
    from app.repositories import postgres_projects

    fake = _FakeConnection(member_role="viewer")
    monkeypatch.setattr(postgres_projects, "connect", lambda: fake)
    with pytest.raises(PermissionError, match="cannot create"):
        PostgreSQLProjectRepository().create(
            workspace_id="ws_test", actor_id="viewer", name="Lookbook"
        )
    assert not any("INSERT INTO projects" in sql for sql, _ in fake.calls)


def test_project_migration_enables_rls_and_scopes_project_to_workspace():
    from pathlib import Path

    migration = Path(__file__).parents[1] / "app/sql/postgres/migrations/0006_projects.sql"
    sql = migration.read_text(encoding="utf-8")
    assert "REFERENCES workspaces(workspace_id) ON DELETE CASCADE" in sql
    assert "CHECK (status IN ('ACTIVE','ARCHIVED','COMPLETED'))" in sql
    assert "ALTER TABLE projects ENABLE ROW LEVEL SECURITY" in sql
