"""Project <-> Product assignment port: SQLite (current behaviour) and PostgreSQL adapter.

Routes only know a project_id; the workspace is resolved from the same backend that
holds the data, so lookup, role check and mutation can never straddle two databases.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Protocol

from app.ports.workspace import WorkspacePort, get_workspace_port, require_role
from app.repository_registry import require_runtime_backend
from app.repositories.postgres_project_products import ProjectStateConflictError as ProjectStateConflict  # noqa: F401


class ProjectProductPort(Protocol):
    def list(self, project_id: str, user_id: str) -> dict[str, Any]: ...
    def replace(self, project_id: str, user_id: str, product_ids: list[str]) -> dict[str, Any]: ...
    def events(self, project_id: str, user_id: str) -> dict[str, Any]: ...


class SQLiteProjectProductPort:
    def __init__(self, workspaces: WorkspacePort | None = None):
        self._workspaces = workspaces or get_workspace_port()

    def _workspace_id(self, project_id: str) -> str:
        from app.project_products import _get_project, initialize
        initialize()
        project = _get_project(project_id)
        if project is None:
            raise LookupError("Project not found")
        return str(project["workspace_id"])

    def list(self, project_id, user_id):
        from app.project_products import list_project_products
        workspace_id = self._workspace_id(project_id)
        require_role(self._workspaces, workspace_id, user_id)
        return list_project_products(project_id, workspace_id)

    def replace(self, project_id, user_id, product_ids):
        from app.project_products import replace_project_products
        workspace_id = self._workspace_id(project_id)
        require_role(self._workspaces, workspace_id, user_id, write=True)
        return replace_project_products(project_id, workspace_id, product_ids, user_id)

    def events(self, project_id, user_id):
        from app.products import _connect
        workspace_id = self._workspace_id(project_id)
        require_role(self._workspaces, workspace_id, user_id)
        db = _connect()
        try:
            rows = db.execute(
                "SELECT event_id,project_id,actor_id,event_type,details_json,created_at FROM project_product_events "
                "WHERE project_id=? AND workspace_id=? ORDER BY created_at DESC,event_id DESC",
                (project_id, workspace_id)).fetchall()
        finally:
            db.close()
        return {"items": [{**{k: row[k] for k in row.keys() if k != "details_json"},
                           "details": json.loads(row["details_json"])} for row in rows], "total": len(rows)}


def _plain(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_plain(v) for v in value]
    return value


class PostgreSQLProjectProductPort:
    def __init__(self, repository=None):
        if repository is None:
            from app.repository_registry import build_postgres_repository
            repository = build_postgres_repository("project_products")
        self._repo = repository

    def _workspace_id(self, project_id: str) -> str:
        workspace_id = self._repo.project_workspace(project_id)
        if workspace_id is None:
            raise LookupError("Project not found")
        return workspace_id

    def list(self, project_id, user_id):
        return _plain(self._repo.list_for_project(project_id, self._workspace_id(project_id), user_id))

    def replace(self, project_id, user_id, product_ids):
        return _plain(self._repo.replace_for_project(project_id, self._workspace_id(project_id), product_ids, user_id))

    def events(self, project_id, user_id):
        items = [_plain(i) for i in self._repo.list_events(project_id, self._workspace_id(project_id), user_id)]
        return {"items": items, "total": len(items)}


def get_project_product_port() -> ProjectProductPort:
    return SQLiteProjectProductPort() if require_runtime_backend() == "sqlite" else PostgreSQLProjectProductPort()
