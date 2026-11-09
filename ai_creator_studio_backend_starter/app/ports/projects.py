"""Project port: SQLite implementation (current behaviour) and PostgreSQL adapter."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Protocol

from app.ports.workspace import WorkspacePort, get_workspace_port, require_role
from app.repository_registry import require_runtime_backend


from app.repositories.postgres_projects import ProjectConflictError as ProjectConflict  # noqa: E402  single source


class ProjectPort(Protocol):
    def create(self, workspace_id: str, user_id: str, fields: dict[str, Any]) -> dict[str, Any]: ...
    def list(self, workspace_id: str, user_id: str, status: str | None) -> dict[str, Any]: ...
    def get(self, project_id: str, user_id: str) -> dict[str, Any]: ...
    def update(self, project_id: str, user_id: str, fields: dict[str, Any]) -> dict[str, Any]: ...


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SQLiteProjectPort:
    def __init__(self, workspaces: WorkspacePort | None = None):
        self._workspaces = workspaces or get_workspace_port()

    def _role(self, workspace_id: str, user_id: str, write: bool = False) -> None:
        require_role(self._workspaces, workspace_id, user_id, write=write)

    def create(self, workspace_id, user_id, fields):
        from app.assets.store import _connect
        from app.projects import _get, _initialize, _read
        self._role(workspace_id, user_id, True)
        _initialize()
        now, project_id = _now(), "prj_" + uuid.uuid4().hex
        with _connect() as db:
            db.execute("INSERT INTO projects VALUES(?,?,?,?,?,?,?,?,?,?)",
                       (project_id, workspace_id, fields["name"], fields["project_type"], "ACTIVE",
                        fields.get("description"), fields.get("external_reference"), user_id, now, now))
        return _read(_get(project_id))

    def list(self, workspace_id, user_id, status):
        from app.assets.store import _connect
        from app.projects import _initialize, _read
        self._role(workspace_id, user_id)
        _initialize()
        with _connect() as db:
            if status:
                rows = db.execute("SELECT * FROM projects WHERE workspace_id=? AND status=? ORDER BY updated_at DESC",
                                  (workspace_id, status)).fetchall()
            else:
                rows = db.execute("SELECT * FROM projects WHERE workspace_id=? ORDER BY updated_at DESC",
                                  (workspace_id,)).fetchall()
        return {"items": [_read(row) for row in rows]}

    def get(self, project_id, user_id):
        from app.projects import _get, _read
        row = _get(project_id)
        if row is None:
            raise LookupError("Project not found")
        self._role(row["workspace_id"], user_id)
        return _read(row)

    def update(self, project_id, user_id, fields):
        from app.assets.store import _connect
        from app.projects import _get, _read
        row = _get(project_id)
        if row is None:
            raise LookupError("Project not found")
        self._role(row["workspace_id"], user_id, True)
        now = _now()
        with _connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if fields["status"] != "ACTIVE" and db.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='lookbook_draft_entities'").fetchone():
                if db.execute("""SELECT 1 FROM lookbook_draft_entities e
                    JOIN lookbook_drafts d ON d.draft_id=e.draft_id
                    WHERE e.entity_type='project' AND e.entity_id=? AND d.archived_at IS NULL LIMIT 1""",
                              (project_id,)).fetchone():
                    raise ProjectConflict("Project is referenced by an active Lookbook Draft; archive the draft first")
            db.execute("UPDATE projects SET name=?, project_type=?, status=?, description=?, updated_at=? WHERE project_id=?",
                       (fields["name"], fields["project_type"], fields["status"], fields.get("description"), now, project_id))
        return _read(_get(project_id))


def _iso(value: dict[str, Any]) -> dict[str, Any]:
    return {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in value.items()}


class PostgreSQLProjectPort:
    def __init__(self, repository=None):
        if repository is None:
            from app.repository_registry import build_postgres_repository
            repository = build_postgres_repository("projects")
        self._repo = repository

    def create(self, workspace_id, user_id, fields):
        return _iso(self._repo.create(workspace_id=workspace_id, actor_id=user_id, name=fields["name"],
                                      project_type=fields["project_type"], description=fields.get("description"),
                                      external_reference=fields.get("external_reference")))

    def list(self, workspace_id, user_id, status):
        return {"items": [_iso(i) for i in self._repo.list_for_workspace(workspace_id, user_id, status=status)]}

    def get(self, project_id, user_id):
        row = self._repo.get(project_id, user_id)
        if row is None:
            raise LookupError("Project not found")
        return _iso(row)

    def update(self, project_id, user_id, fields):
        row = self._repo.update(project_id, user_id, name=fields["name"], project_type=fields["project_type"],
                                status=fields["status"], description=fields.get("description"))
        if row is None:
            raise LookupError("Project not found")
        return _iso(row)


def get_project_port() -> ProjectPort:
    return SQLiteProjectPort() if require_runtime_backend() == "sqlite" else PostgreSQLProjectPort()
