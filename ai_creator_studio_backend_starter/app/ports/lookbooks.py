"""Lookbook Draft port (stage a: draft lifecycle, review, archive, events, plan manifest).

Same check order on both backends: workspace role first (non-members see "Workspace not found"),
then draft lookup. Output attachment, assembly review and package export are ported in later stages.
"""
from __future__ import annotations

from datetime import timezone
from typing import Any, Protocol

from app.ports.assets import _plain
from app.ports.workspace import WorkspacePort, get_workspace_port, require_role
from app.repo_errors import InsufficientRoleError, NotAMemberError, RepositoryConflictError
from app.repository_registry import require_runtime_backend

DRAFT_NOT_FOUND = "Lookbook Draft not found"
REVIEW_ROLES = frozenset({"owner", "admin"})
WRITE_ROLES = frozenset({"owner", "admin", "editor"})
READ_ROLES = frozenset({"owner", "admin", "editor", "viewer"})


def _conflict(fn):
    """Legacy contract for output/assembly operations: every ValueError is an HTTP 409."""
    try:
        return fn()
    except ValueError as exc:
        raise RepositoryConflictError(str(exc)) from exc


def _no_seq(review: dict[str, Any]) -> dict[str, Any]:
    review["events"] = [{k: v for k, v in e.items() if k != "seq"} for e in review["events"]]
    return review


class LookbookDraftPort(Protocol):
    def create(self, workspace_id: str, user_id: str, body: Any) -> dict[str, Any]: ...
    def list(self, workspace_id: str, user_id: str, include_archived: bool, limit: int, offset: int) -> dict[str, Any]: ...
    def get(self, draft_id: str, workspace_id: str, user_id: str) -> dict[str, Any]: ...
    def update(self, draft_id: str, workspace_id: str, user_id: str, body: Any) -> dict[str, Any]: ...
    def submit(self, draft_id: str, workspace_id: str, user_id: str) -> dict[str, Any]: ...
    def decide(self, draft_id: str, workspace_id: str, user_id: str, decision: str, comment: str | None) -> dict[str, Any]: ...
    def archive(self, draft_id: str, workspace_id: str, user_id: str) -> dict[str, Any]: ...
    def events(self, draft_id: str, workspace_id: str, user_id: str, limit: int, offset: int) -> dict[str, Any]: ...
    def plan_manifest(self, draft_id: str, workspace_id: str, user_id: str) -> dict[str, Any]: ...
    def outputs(self, draft_id: str, workspace_id: str, user_id: str) -> dict[str, Any]: ...
    def attach_output(self, draft_id: str, workspace_id: str, user_id: str, body: Any) -> dict[str, Any]: ...
    def assembly_review(self, draft_id: str, workspace_id: str, user_id: str) -> dict[str, Any]: ...
    def submit_assembly(self, draft_id: str, workspace_id: str, user_id: str) -> dict[str, Any]: ...
    def decide_assembly(self, draft_id: str, workspace_id: str, user_id: str, decision: str, comment: str) -> dict[str, Any]: ...
    def output_manifest(self, draft_id: str, workspace_id: str, user_id: str) -> dict[str, Any]: ...
    def package_exports(self, draft_id: str, workspace_id: str, user_id: str) -> dict[str, Any]: ...
    def create_package(self, draft_id: str, workspace_id: str, user_id: str) -> dict[str, Any]: ...
    def download_package(self, export_id: str, expires: int, signature: str, user_id: str) -> Any: ...


def _require_reviewer(workspaces: WorkspacePort, workspace_id: str, user_id: str) -> None:
    role = workspaces.role(workspace_id, user_id)
    if role is None:
        raise NotAMemberError("Workspace not found")
    if role not in REVIEW_ROLES:
        raise InsufficientRoleError("Insufficient workspace role")


class SQLiteLookbookDraftPort:
    def __init__(self, workspaces: WorkspacePort | None = None):
        self._workspaces = workspaces or get_workspace_port()

    def _draft(self, draft_id: str, workspace_id: str) -> dict[str, Any]:
        from app.lookbook import get_draft
        value = get_draft(draft_id, workspace_id)
        if value is None:
            raise LookupError(DRAFT_NOT_FOUND)
        return value

    def create(self, workspace_id, user_id, body):
        from app.lookbook import create_draft
        require_role(self._workspaces, workspace_id, user_id, write=True)
        return create_draft(body, user_id)

    def list(self, workspace_id, user_id, include_archived, limit, offset):
        from app.lookbook import list_drafts
        require_role(self._workspaces, workspace_id, user_id)
        return list_drafts(workspace_id, include_archived, limit=limit, offset=offset)

    def get(self, draft_id, workspace_id, user_id):
        require_role(self._workspaces, workspace_id, user_id)
        return self._draft(draft_id, workspace_id)

    def update(self, draft_id, workspace_id, user_id, body):
        from app.lookbook import update_draft
        require_role(self._workspaces, workspace_id, user_id, write=True)
        self._draft(draft_id, workspace_id)
        return update_draft(draft_id, body, user_id)

    def submit(self, draft_id, workspace_id, user_id):
        from app.lookbook import submit_for_review
        require_role(self._workspaces, workspace_id, user_id, write=True)
        self._draft(draft_id, workspace_id)
        return submit_for_review(draft_id, workspace_id, user_id)

    def decide(self, draft_id, workspace_id, user_id, decision, comment):
        from app.lookbook import decide_review
        _require_reviewer(self._workspaces, workspace_id, user_id)
        self._draft(draft_id, workspace_id)
        return decide_review(draft_id, workspace_id, user_id, decision, comment)

    def archive(self, draft_id, workspace_id, user_id):
        from app.lookbook import archive_draft
        require_role(self._workspaces, workspace_id, user_id, write=True)
        self._draft(draft_id, workspace_id)
        return archive_draft(draft_id, workspace_id, user_id)

    def events(self, draft_id, workspace_id, user_id, limit, offset):
        from app.lookbook import list_events
        require_role(self._workspaces, workspace_id, user_id)
        self._draft(draft_id, workspace_id)
        return list_events(draft_id, workspace_id, limit=limit, offset=offset)

    def plan_manifest(self, draft_id, workspace_id, user_id):
        from app.lookbook import export_approved_manifest
        require_role(self._workspaces, workspace_id, user_id)
        self._draft(draft_id, workspace_id)
        return export_approved_manifest(draft_id, workspace_id)

    def outputs(self, draft_id, workspace_id, user_id):
        from app.lookbook import list_lookbook_outputs
        require_role(self._workspaces, workspace_id, user_id)
        self._draft(draft_id, workspace_id)
        return list_lookbook_outputs(draft_id, workspace_id)

    def attach_output(self, draft_id, workspace_id, user_id, body):
        import sqlite3

        from app.lookbook import attach_approved_photo_output
        require_role(self._workspaces, workspace_id, user_id, write=True)
        self._draft(draft_id, workspace_id)
        try:
            return _conflict(lambda: attach_approved_photo_output(draft_id, workspace_id, user_id, body))
        except sqlite3.IntegrityError as exc:
            raise RepositoryConflictError("Photo output is already attached or page order is in use") from exc

    def _assembly(self, fn, draft_id, workspace_id):
        result = _conflict(fn)
        if result is None:
            raise LookupError(DRAFT_NOT_FOUND)
        return result

    def assembly_review(self, draft_id, workspace_id, user_id):
        from app.lookbook import get_lookbook_output_assembly_review
        require_role(self._workspaces, workspace_id, user_id)
        self._draft(draft_id, workspace_id)
        return self._assembly(lambda: get_lookbook_output_assembly_review(draft_id, workspace_id), draft_id, workspace_id)

    def submit_assembly(self, draft_id, workspace_id, user_id):
        from app.lookbook import submit_lookbook_output_assembly
        require_role(self._workspaces, workspace_id, user_id, write=True)
        self._draft(draft_id, workspace_id)
        return self._assembly(lambda: submit_lookbook_output_assembly(draft_id, workspace_id, user_id), draft_id, workspace_id)

    def decide_assembly(self, draft_id, workspace_id, user_id, decision, comment):
        from app.lookbook import decide_lookbook_output_assembly
        _require_reviewer(self._workspaces, workspace_id, user_id)
        self._draft(draft_id, workspace_id)
        return self._assembly(lambda: decide_lookbook_output_assembly(draft_id, workspace_id, user_id, decision, comment),
                              draft_id, workspace_id)

    def output_manifest(self, draft_id, workspace_id, user_id):
        from app.lookbook import create_lookbook_output_manifest
        require_role(self._workspaces, workspace_id, user_id, write=True)
        self._draft(draft_id, workspace_id)
        return _conflict(lambda: create_lookbook_output_manifest(draft_id, workspace_id, user_id))

    def package_exports(self, draft_id, workspace_id, user_id):
        from app.lookbook import list_lookbook_output_package_exports
        require_role(self._workspaces, workspace_id, user_id)
        self._draft(draft_id, workspace_id)
        return list_lookbook_output_package_exports(draft_id, workspace_id)

    def create_package(self, draft_id, workspace_id, user_id):
        from app.lookbook import create_lookbook_output_package
        require_role(self._workspaces, workspace_id, user_id, write=True)
        self._draft(draft_id, workspace_id)
        return _conflict(lambda: create_lookbook_output_package(draft_id, workspace_id, user_id))

    def download_package(self, export_id, expires, signature, user_id):
        from app.lookbook import download_lookbook_output_package
        return download_lookbook_output_package(export_id, expires, signature, user_id)


class PostgreSQLLookbookDraftPort:
    def __init__(self, repository=None):
        if repository is None:
            from app.repository_registry import build_postgres_repository
            repository = build_postgres_repository("lookbooks")
        self._repo = repository

    @staticmethod
    def _payload(body: Any) -> dict[str, Any]:
        return body.model_dump(mode="json")

    def _draft(self, draft_id, workspace_id, user_id):
        value = self._repo.get_draft(draft_id, workspace_id, user_id)
        if value is None:
            raise LookupError(DRAFT_NOT_FOUND)
        return value

    def _gate(self, workspace_id, user_id, roles, draft_id=None):
        self._repo.check_access(workspace_id, user_id, set(roles))
        if draft_id is not None:
            self._draft(draft_id, workspace_id, user_id)

    def create(self, workspace_id, user_id, body):
        return _plain(self._repo.create_draft(workspace_id, user_id, self._payload(body)))

    def list(self, workspace_id, user_id, include_archived, limit, offset):
        return _plain(self._repo.list_drafts(workspace_id, user_id, include_archived, limit=limit, offset=offset))

    def get(self, draft_id, workspace_id, user_id):
        return _plain(self._draft(draft_id, workspace_id, user_id))

    def update(self, draft_id, workspace_id, user_id, body):
        self._gate(workspace_id, user_id, WRITE_ROLES, draft_id)
        return _plain(self._repo.update_draft(draft_id, workspace_id, user_id, self._payload(body)))

    def submit(self, draft_id, workspace_id, user_id):
        self._gate(workspace_id, user_id, WRITE_ROLES, draft_id)
        return _plain(self._repo.submit_for_review(draft_id, workspace_id, user_id))

    def decide(self, draft_id, workspace_id, user_id, decision, comment):
        self._gate(workspace_id, user_id, REVIEW_ROLES, draft_id)
        return _plain(self._repo.decide_review(draft_id, workspace_id, user_id, decision, comment))

    def archive(self, draft_id, workspace_id, user_id):
        self._gate(workspace_id, user_id, WRITE_ROLES, draft_id)
        return _plain(self._repo.archive_draft(draft_id, workspace_id, user_id))

    def events(self, draft_id, workspace_id, user_id, limit, offset):
        self._draft(draft_id, workspace_id, user_id)
        return _plain(self._repo.list_events(draft_id, workspace_id, user_id, limit=limit, offset=offset))

    def plan_manifest(self, draft_id, workspace_id, user_id):
        self._draft(draft_id, workspace_id, user_id)
        return _plain(self._repo.export_plan_manifest(draft_id, workspace_id, user_id))

    def outputs(self, draft_id, workspace_id, user_id):
        self._draft(draft_id, workspace_id, user_id)
        return _plain(self._repo.list_outputs(draft_id, workspace_id, user_id))

    def attach_output(self, draft_id, workspace_id, user_id, body):
        from app.ports.photos import verify_output_base
        self._gate(workspace_id, user_id, WRITE_ROLES, draft_id)
        return _plain(self._repo.attach_approved_photo_output(
            draft_id, workspace_id, user_id, photo_run_id=body.photo_run_id, page_order=body.page_order,
            product_id=body.product_id, product_variant_id=body.product_variant_id, caption=body.caption,
            verify=verify_output_base))

    def _assembly(self, value):
        if value is None:
            raise LookupError(DRAFT_NOT_FOUND)
        return _plain(_no_seq(value))

    def assembly_review(self, draft_id, workspace_id, user_id):
        from app.ports.photos import verify_output_base
        self._draft(draft_id, workspace_id, user_id)
        return self._assembly(self._repo.get_assembly_review(draft_id, workspace_id, user_id, verify_output_base))

    def submit_assembly(self, draft_id, workspace_id, user_id):
        from app.ports.photos import verify_output_base
        self._gate(workspace_id, user_id, WRITE_ROLES, draft_id)
        return self._assembly(self._repo.submit_assembly(draft_id, workspace_id, user_id, verify_output_base))

    def decide_assembly(self, draft_id, workspace_id, user_id, decision, comment):
        from app.ports.photos import verify_output_base
        self._gate(workspace_id, user_id, REVIEW_ROLES, draft_id)
        return self._assembly(self._repo.decide_assembly(draft_id, workspace_id, user_id, decision, comment, verify_output_base))

    def output_manifest(self, draft_id, workspace_id, user_id):
        from app.ports.photos import verify_output_base
        self._gate(workspace_id, user_id, WRITE_ROLES, draft_id)
        return _plain(self._repo.create_output_manifest(draft_id, workspace_id, user_id, verify_output_base))

    def package_exports(self, draft_id, workspace_id, user_id):
        from app.lookbook import package_export_list
        self._draft(draft_id, workspace_id, user_id)
        rows = self._repo.list_package_exports(draft_id, workspace_id, user_id)
        shaped = package_export_list(rows)
        for item in shaped["items"]:
            item["created_at"] = item["created_at"].astimezone(timezone.utc).isoformat()
        shaped["items"] = [{k: item[k] for k in ("export_id", "package_sha256", "package_size_bytes", "manifest_sha256",
                                                 "snapshot_sha256", "output_count", "created_at", "expires_at", "status")}
                           for item in shaped["items"]]
        return _plain(shaped)

    def create_package(self, draft_id, workspace_id, user_id):
        import time
        import uuid

        from app.lookbook import _lookbook_package_dir, _lookbook_package_signature, write_lookbook_package
        from app.ports.photos import verify_output_base
        self._gate(workspace_id, user_id, WRITE_ROLES, draft_id)
        export_id = "lbx_" + uuid.uuid4().hex
        try:
            # Validate signing configuration before creating any package/audit artifact (legacy order).
            _lookbook_package_signature(export_id, int(time.time()) + 15 * 60)
            prep = self._repo.prepare_package(draft_id, workspace_id, user_id, verify_output_base)
        except ValueError as exc:
            if isinstance(exc, RepositoryConflictError):
                raise
            raise RepositoryConflictError(str(exc)) from exc
        package_dir = _lookbook_package_dir()
        final_path = package_dir / f"{export_id}.zip"
        temp_path = package_dir / f".{export_id}.tmp"
        package_manifest = {
            "manifest_type": "AI_CREATOR_STUDIO_PRIVATE_LOOKBOOK_PACKAGE", "manifest_version": 1,
            "draft_id": draft_id, "workspace_id": workspace_id, "output_assembly_approved": True,
            "output_assembly_approved_by": prep["assembly_actor_id"],
            "output_assembly_reviewed_at": prep["assembly_reviewed_at"],
            "output_assembly_snapshot_sha256": prep["snapshot_sha256"],
            "is_ai_generated": False, "provider_dispatched": False, "credit_charged": False,
            "planning_approved_by": prep["planning_approved_by"], "planning_approved_at": prep["planning_approved_at"],
            "planning_input": prep["planning_input"], "publication_authorized": False,
            "commercial_rights_verified": False, "public_distribution_authorized": False,
            "internal_use_only": True, "binary_files_included": True, "outputs": [],
            "notice": "Private internal-use package only. No publication, public distribution or commercial-use rights are granted.",
        }
        try:
            try:
                manifest_hash, package_hash, package_size = write_lookbook_package(
                    temp_path, final_path, package_manifest, prep["bases"])
            except ValueError as exc:
                raise RepositoryConflictError(str(exc)) from exc
            expires_at = int(time.time()) + 24 * 60 * 60
            self._repo.record_package_export(
                draft_id, workspace_id, user_id, storage_key=final_path.name, package_sha256=package_hash,
                package_size_bytes=package_size, manifest_sha256=manifest_hash, snapshot_sha256=prep["snapshot_sha256"],
                output_count=len(prep["bases"]), expires_at=expires_at, export_id=export_id, verify=verify_output_base)
        except Exception:
            temp_path.unlink(missing_ok=True)
            final_path.unlink(missing_ok=True)
            raise
        row = self._repo.get_package_export(export_id)
        download_expires = min(expires_at, int(time.time()) + 15 * 60)
        signature = _lookbook_package_signature(export_id, download_expires)
        return {"export_id": export_id, "package_sha256": package_hash, "package_size_bytes": package_size,
                "manifest_sha256": manifest_hash, "output_count": len(prep["bases"]),
                "created_at": row["created_at"].astimezone(timezone.utc).isoformat(), "expires_at": expires_at,
                "download_url": f"/v1/lookbook-drafts/exports/{export_id}/download?expires={download_expires}&signature={signature}",
                "internal_use_only": True, "publication_authorized": False, "commercial_rights_verified": False}

    def download_package(self, export_id, expires, signature, user_id):
        from app.lookbook import download_lookbook_output_package
        return download_lookbook_output_package(
            export_id, expires, signature, user_id, fetch_row=self._repo.get_package_export,
            authorize=lambda workspace_id, user, roles: self._repo.check_access(workspace_id, user, set(roles)))


def get_lookbook_draft_port() -> LookbookDraftPort:
    return SQLiteLookbookDraftPort() if require_runtime_backend() == "sqlite" else PostgreSQLLookbookDraftPort()
