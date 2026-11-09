"""PostgreSQL Project ↔ Product assignment repository; not runtime-selected yet."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from app.postgres import apply_migrations, connect
from app.repo_errors import InsufficientRoleError, NotAMemberError, RepositoryConflictError
from app.repositories.postgres_products import PostgreSQLProductRepository


class ProjectStateConflictError(RepositoryConflictError):
    """Project is not ACTIVE, so its Product assignments cannot change."""


class PostgreSQLProjectProductRepository:
    backend = "postgresql"
    WRITABLE_ROLES = {"owner", "admin", "editor"}
    READABLE_ROLES = WRITABLE_ROLES | {"viewer"}

    def initialize(self) -> None:
        apply_migrations()

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _validate_ids(product_ids: list[str]) -> None:
        if (not isinstance(product_ids, list) or len(product_ids) > 100
                or len(product_ids) != len(set(product_ids))
                or any(not isinstance(value, str) or not value.strip() or len(value) > 80 for value in product_ids)):
            raise ValueError("Product IDs must be unique non-empty identifiers; maximum 100")

    @staticmethod
    def _jsonb(value: dict[str, Any]):
        try:
            from psycopg.types.json import Jsonb
            return Jsonb(value)
        except ImportError as exc:
            raise RuntimeError("psycopg 3 is required for PostgreSQL Project Product repository") from exc

    @staticmethod
    def _role(conn: Any, workspace_id: str, actor_id: str) -> str | None:
        row = conn.execute(
            "SELECT role FROM workspace_members WHERE workspace_id=%s AND user_id=%s",
            (workspace_id, actor_id),
        ).fetchone()
        return str(row["role"]) if row else None

    def list_for_project(self, project_id: str, workspace_id: str, actor_id: str) -> dict[str, Any]:
        with connect() as conn:
            role = self._role(conn, workspace_id, actor_id)
            if role is None:
                raise NotAMemberError("User is not a member of this workspace")
            if role not in self.READABLE_ROLES:
                raise InsufficientRoleError("User cannot read this Workspace")
            project = conn.execute(
                "SELECT status FROM projects WHERE project_id=%s AND workspace_id=%s",
                (project_id, workspace_id),
            ).fetchone()
            if project is None:
                raise LookupError("Project not found")
            rows = conn.execute(
                """SELECT p.* FROM project_product_assignments a
                   JOIN products p ON p.product_id=a.product_id AND p.workspace_id=a.workspace_id
                   WHERE a.project_id=%s AND a.workspace_id=%s AND a.removed_at IS NULL AND p.status='ACTIVE'
                   ORDER BY a.sort_order,a.assigned_at,a.assignment_id""",
                (project_id, workspace_id),
            ).fetchall()
            items = [PostgreSQLProductRepository._read(conn, row) for row in rows]
            return {"project_id": project_id, "workspace_id": workspace_id, "items": items, "total": len(items)}

    def replace_for_project(self, project_id: str, workspace_id: str, product_ids: list[str],
                            actor_id: str) -> dict[str, Any]:
        self._validate_ids(product_ids)
        now = self._now()
        with connect() as conn:
            project = conn.execute(
                "SELECT status FROM projects WHERE project_id=%s AND workspace_id=%s FOR UPDATE",
                (project_id, workspace_id),
            ).fetchone()
            if project is None:
                raise LookupError("Project not found")
            role = self._role(conn, workspace_id, actor_id)
            if role is None:
                raise NotAMemberError("User is not a member of this workspace")
            if role not in self.WRITABLE_ROLES:
                raise InsufficientRoleError("Workspace role cannot change Project Product assignments")
            if project["status"] != "ACTIVE":
                raise ProjectStateConflictError("Products can only be assigned to an ACTIVE Project")
            if product_ids:
                found = conn.execute(
                    "SELECT product_id FROM products WHERE workspace_id=%s AND status='ACTIVE' AND product_id=ANY(%s)",
                    (workspace_id, product_ids),
                ).fetchall()
                if len(found) != len(product_ids):
                    raise ValueError("Every Product must be active in this workspace")
            existing_rows = conn.execute(
                """SELECT product_id,sort_order FROM project_product_assignments
                   WHERE project_id=%s AND workspace_id=%s AND removed_at IS NULL FOR UPDATE""",
                (project_id, workspace_id),
            ).fetchall()
            existing = {str(row["product_id"]) for row in existing_rows}
            existing_order = {str(row["product_id"]): int(row["sort_order"]) for row in existing_rows}
            requested = set(product_ids)
            removed = sorted(existing - requested)
            added = [product_id for product_id in product_ids if product_id not in existing]
            reordered = any(existing_order.get(product_id) != index
                            for index, product_id in enumerate(product_ids) if product_id in existing)
            if removed:
                conn.execute(
                    """UPDATE project_product_assignments SET removed_at=%s
                       WHERE project_id=%s AND workspace_id=%s AND removed_at IS NULL AND product_id=ANY(%s)""",
                    (now, project_id, workspace_id, removed),
                )
            conn.cursor().executemany(
                """INSERT INTO project_product_assignments
                   (assignment_id,workspace_id,project_id,product_id,assigned_by,assigned_at,removed_at,sort_order)
                   VALUES(%s,%s,%s,%s,%s,%s,NULL,%s)""",
                [("ppa_" + uuid.uuid4().hex, workspace_id, project_id, product_id, actor_id, now, product_ids.index(product_id))
                 for product_id in added],
            )
            for index, product_id in enumerate(product_ids):
                if product_id in existing:
                    conn.execute(
                        """UPDATE project_product_assignments SET sort_order=%s
                           WHERE project_id=%s AND workspace_id=%s AND product_id=%s AND removed_at IS NULL""",
                        (index, project_id, workspace_id, product_id),
                    )
            if added or removed or reordered:
                conn.execute(
                    """INSERT INTO project_product_events(event_id,workspace_id,project_id,actor_id,event_type,details,created_at)
                       VALUES(%s,%s,%s,%s,'project.products_replaced',%s,%s)""",
                    ("ppe_" + uuid.uuid4().hex, workspace_id, project_id, actor_id,
                     self._jsonb({"added": added, "removed": removed, "reordered": reordered}), now),
                )
        return self.list_for_project(project_id, workspace_id, actor_id)

    def project_workspace(self, project_id: str) -> str | None:
        """Resolve a Project's workspace; authorization happens in the caller-visible methods."""
        with connect() as conn:
            row = conn.execute("SELECT workspace_id FROM projects WHERE project_id=%s", (project_id,)).fetchone()
        return str(row["workspace_id"]) if row else None

    def list_events(self, project_id: str, workspace_id: str, actor_id: str) -> list[dict[str, Any]]:
        with connect() as conn:
            role = self._role(conn, workspace_id, actor_id)
            if role is None:
                raise NotAMemberError("User is not a member of this workspace")
            if role not in self.READABLE_ROLES:
                raise InsufficientRoleError("User cannot read this Workspace")
            rows = conn.execute(
                """SELECT event_id,project_id,actor_id,event_type,details,created_at
                   FROM project_product_events WHERE project_id=%s AND workspace_id=%s
                   ORDER BY created_at DESC,event_id DESC""",
                (project_id, workspace_id),
            ).fetchall()
        return [dict(row) for row in rows]
