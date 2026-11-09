"""Workspace membership port: routes ask the *same backend as the data* for a role."""
from __future__ import annotations

from typing import Protocol

from app.repo_errors import InsufficientRoleError, NotAMemberError
from app.repository_registry import require_runtime_backend

WRITABLE_ROLES = frozenset({"owner", "admin", "editor"})


class WorkspacePort(Protocol):
    def role(self, workspace_id: str, user_id: str) -> str | None: ...
    def create(self, workspace_id: str, user_id: str) -> dict: ...
    def list(self, user_id: str) -> dict: ...
    def add_member(self, workspace_id: str, actor_id: str, member_id: str, role: str) -> dict: ...


class SQLiteWorkspacePort:
    def role(self, workspace_id: str, user_id: str) -> str | None:
        from app.assets.store import workspace_role
        return workspace_role(workspace_id, user_id)

    def create(self, workspace_id: str, user_id: str) -> dict:
        import sqlite3
        from app.assets.store import create_workspace
        from app.repositories.postgres_assets import WorkspaceConflictError
        try:
            return create_workspace(workspace_id, user_id)
        except sqlite3.IntegrityError as exc:
            raise WorkspaceConflictError("Workspace ID already exists") from exc

    def list(self, user_id: str) -> dict:
        from app.assets.store import list_workspaces
        return {"items": list_workspaces(user_id)}

    def add_member(self, workspace_id: str, actor_id: str, member_id: str, role: str) -> dict:
        import sqlite3
        from app.assets.store import add_workspace_member
        from app.repositories.postgres_assets import WorkspaceConflictError
        actor_role = self.role(workspace_id, actor_id)
        if actor_role is None:
            raise NotAMemberError("Workspace not found")
        if actor_role not in {"owner", "admin"}:
            raise InsufficientRoleError("Insufficient workspace role")
        try:
            return add_workspace_member(workspace_id, member_id, role)
        except sqlite3.IntegrityError as exc:
            raise WorkspaceConflictError("Member already exists or workspace is invalid") from exc


class PostgreSQLWorkspacePort:
    def __init__(self, repository=None):
        if repository is None:
            from app.repository_registry import build_postgres_repository
            repository = build_postgres_repository("workspace_and_asset_metadata", allow_unverified=True)
        self._repository = repository

    def role(self, workspace_id: str, user_id: str) -> str | None:
        return self._repository.workspace_role(workspace_id, user_id)

    def create(self, workspace_id: str, user_id: str) -> dict:
        return self._repository.create_workspace(workspace_id, user_id)

    def list(self, user_id: str) -> dict:
        from datetime import datetime
        return {"items": [{k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in row.items()}
                          for row in self._repository.list_workspaces(user_id)]}

    def add_member(self, workspace_id: str, actor_id: str, member_id: str, role: str) -> dict:
        return self._repository.add_workspace_member(workspace_id, member_id, role, actor_id=actor_id)


def get_workspace_port() -> WorkspacePort:
    """Select once per call from configuration; PostgreSQL is refused until fully verified."""
    return SQLiteWorkspacePort() if require_runtime_backend() == "sqlite" else PostgreSQLWorkspacePort()


def require_role(port: WorkspacePort, workspace_id: str, user_id: str, *, write: bool = False) -> str:
    role = port.role(workspace_id, user_id)
    if role is None:
        raise NotAMemberError("Workspace not found")
    if write and role not in WRITABLE_ROLES:
        raise InsufficientRoleError("Insufficient workspace role")
    return role
