"""PostgreSQL Project aggregate repository; not selected by the API runtime yet."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from app.postgres import apply_migrations, connect
from app.repo_errors import InsufficientRoleError, NotAMemberError, RepositoryConflictError

ProjectStatus = Literal["ACTIVE", "ARCHIVED", "COMPLETED"]
_PROJECT_FIELDS = (
    "project_id", "workspace_id", "name", "project_type", "status",
    "description", "external_reference", "created_by", "created_at", "updated_at",
)


class ProjectConflictError(RepositoryConflictError):
    """Project is referenced by an active Lookbook Draft."""


class PostgreSQLProjectRepository:
    backend = "postgresql"
    WRITABLE_ROLES = {"owner", "admin", "editor"}
    READABLE_ROLES = WRITABLE_ROLES | {"viewer"}
    STATUSES = {"ACTIVE", "ARCHIVED", "COMPLETED"}

    def initialize(self) -> None:
        apply_migrations()

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _read(row: Any) -> dict[str, Any]:
        return {key: row[key] for key in _PROJECT_FIELDS}

    def workspace_role(self, workspace_id: str, user_id: str) -> str | None:
        with connect() as conn:
            row = conn.execute(
                "SELECT role FROM workspace_members WHERE workspace_id=%s AND user_id=%s",
                (workspace_id, user_id),
            ).fetchone()
        return str(row["role"]) if row else None

    def create(self, *, workspace_id: str, actor_id: str, name: str,
               project_type: str = "general", description: str | None = None,
               external_reference: str | None = None) -> dict[str, Any]:
        self._validate(name, project_type, description, external_reference)
        now = self._now()
        project_id = "prj_" + uuid.uuid4().hex
        with connect() as conn:
            member = conn.execute(
                "SELECT role FROM workspace_members WHERE workspace_id=%s AND user_id=%s",
                (workspace_id, actor_id),
            ).fetchone()
            if member is None:
                raise NotAMemberError("User is not a member of this workspace")
            if member["role"] not in self.WRITABLE_ROLES:
                raise InsufficientRoleError("Workspace role cannot create projects")
            conn.execute(
                """INSERT INTO projects(project_id,workspace_id,name,project_type,status,description,
                   external_reference,created_by,created_at,updated_at)
                   VALUES(%s,%s,%s,%s,'ACTIVE',%s,%s,%s,%s,%s)""",
                (project_id, workspace_id, name.strip(), project_type.strip(), description,
                 external_reference, actor_id, now, now),
            )
            row = conn.execute("SELECT * FROM projects WHERE project_id=%s", (project_id,)).fetchone()
        if row is None:
            raise RuntimeError("Project insert completed but row could not be read")
        return self._read(row)

    def list_for_workspace(self, workspace_id: str, actor_id: str,
                           *, status: ProjectStatus | None = None) -> list[dict[str, Any]]:
        role = self.workspace_role(workspace_id, actor_id)
        if role is None:
            raise NotAMemberError("User is not a member of this workspace")
        if role not in self.READABLE_ROLES:
            raise InsufficientRoleError("User cannot read projects in this workspace")
        with connect() as conn:
            if status is None:
                rows = conn.execute(
                    "SELECT * FROM projects WHERE workspace_id=%s ORDER BY updated_at DESC,project_id",
                    (workspace_id,),
                ).fetchall()
            else:
                self._validate_status(status)
                rows = conn.execute(
                    "SELECT * FROM projects WHERE workspace_id=%s AND status=%s ORDER BY updated_at DESC,project_id",
                    (workspace_id, status),
                ).fetchall()
        return [self._read(row) for row in rows]

    def get(self, project_id: str, actor_id: str) -> dict[str, Any] | None:
        with connect() as conn:
            row = conn.execute("SELECT * FROM projects WHERE project_id=%s", (project_id,)).fetchone()
        if row is None:
            return None
        role = self.workspace_role(str(row["workspace_id"]), actor_id)
        if role is None:
            raise NotAMemberError("User is not a member of this workspace")
        if role not in self.READABLE_ROLES:
            raise InsufficientRoleError("User cannot read this project")
        return self._read(row)

    def update(self, project_id: str, actor_id: str, *, name: str, project_type: str,
               status: ProjectStatus, description: str | None = None) -> dict[str, Any] | None:
        self._validate(name, project_type, description, None)
        self._validate_status(status)
        now = self._now()
        with connect() as conn:
            row = conn.execute("SELECT workspace_id FROM projects WHERE project_id=%s FOR UPDATE",
                               (project_id,)).fetchone()
            if row is None:
                return None
            member = conn.execute(
                "SELECT role FROM workspace_members WHERE workspace_id=%s AND user_id=%s",
                (row["workspace_id"], actor_id),
            ).fetchone()
            if member is None:
                raise NotAMemberError("User is not a member of this workspace")
            if member["role"] not in self.WRITABLE_ROLES:
                raise InsufficientRoleError("Workspace role cannot update projects")
            if status != "ACTIVE" and self._active_lookbook_reference(conn, project_id):
                raise ProjectConflictError("Project is referenced by an active Lookbook Draft; archive the draft first")
            conn.execute(
                """UPDATE projects SET name=%s,project_type=%s,status=%s,description=%s,updated_at=%s
                   WHERE project_id=%s""",
                (name.strip(), project_type.strip(), status, description, now, project_id),
            )
            updated = conn.execute("SELECT * FROM projects WHERE project_id=%s", (project_id,)).fetchone()
        return self._read(updated) if updated else None

    @staticmethod
    def _active_lookbook_reference(conn: Any, project_id: str) -> bool:
        if conn.execute("SELECT to_regclass('public.lookbook_draft_entities') AS t").fetchone()["t"] is None:
            return False
        return conn.execute(
            """SELECT 1 FROM lookbook_draft_entities e JOIN lookbook_drafts d ON d.draft_id=e.draft_id
               WHERE e.entity_type='project' AND e.entity_id=%s AND d.archived_at IS NULL LIMIT 1""",
            (project_id,)).fetchone() is not None

    @classmethod
    def _validate(cls, name: str, project_type: str, description: str | None,
                  external_reference: str | None) -> None:
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 120:
            raise ValueError("Project name must contain 1 to 120 characters")
        if not isinstance(project_type, str) or not 1 <= len(project_type.strip()) <= 64:
            raise ValueError("Project type must contain 1 to 64 characters")
        if description is not None and (not isinstance(description, str) or len(description) > 2000):
            raise ValueError("Project description exceeds 2000 characters")
        if external_reference is not None and (not isinstance(external_reference, str) or len(external_reference) > 128):
            raise ValueError("Project external reference exceeds 128 characters")

    @classmethod
    def _validate_status(cls, status: str) -> None:
        if status not in cls.STATUSES:
            raise ValueError("Unsupported project status")
