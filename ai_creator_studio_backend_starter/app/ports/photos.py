"""Photo Draft port (stage a: drafts, draft events, run listings): SQLite (current behaviour) and PostgreSQL.

Order of checks is identical on both backends: workspace role first (non-members see
"Workspace not found"), then draft lookup. Review, export and local processing are
ported in later stages and still live in ``app.photo_engine``.
"""
from __future__ import annotations

from typing import Any, Protocol

from app.ports.assets import _plain
from app.ports.workspace import WorkspacePort, get_workspace_port, require_role
from app.repo_errors import InsufficientRoleError, NotAMemberError, RepositoryConflictError
from app.repository_registry import require_runtime_backend

DRAFT_NOT_FOUND = "Photo Draft not found"
RUN_NOT_FOUND = "Photo processing run not found"


REVIEW_ROLES = frozenset({"owner", "admin"})


def verify_output_base(base: dict[str, Any]) -> bool:
    """A reviewed/exported Photo output must still be an active, provenance-backed, byte-identical version."""
    if (not base["active_asset_id"] or not base["verified_version_id"] or not base["provenance_id"]
            or base["version_checksum"] != base["output_checksum_sha256"]):
        return False
    key = base["version_storage_key"]
    if not key:
        return False
    from app.assets.blob_store import LocalBlobStore
    return LocalBlobStore().audit_status(key, int(base["version_size_bytes"]), base["version_checksum"]) == "ok"


def _require_reviewer(workspaces: WorkspacePort, workspace_id: str, user_id: str) -> None:
    role = workspaces.role(workspace_id, user_id)
    if role is None:
        raise NotAMemberError("Workspace not found")
    if role not in REVIEW_ROLES:
        raise InsufficientRoleError("Insufficient workspace role")

class LocalProcessingFailed(Exception):
    """Local processing failed after a run was claimed; ``str(exc)`` is the safe public message (HTTP 422)."""


def _run_local(fn):
    """Legacy contract for ``process-local``: claim refusals are 409, a missing draft 404, any later failure 422."""
    try:
        result = fn()
    except ValueError as exc:
        raise RepositoryConflictError(str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - public message was already sanitised by the processor
        raise LocalProcessingFailed(str(exc)) from exc
    if result is None:
        raise LookupError(DRAFT_NOT_FOUND)
    return result


class PhotoDraftPort(Protocol):
    def create(self, workspace_id: str, user_id: str, body: Any) -> dict[str, Any]: ...
    def list(self, workspace_id: str, user_id: str, include_archived: bool, limit: int, offset: int) -> dict[str, Any]: ...
    def get(self, draft_id: str, workspace_id: str, user_id: str) -> dict[str, Any]: ...
    def update(self, draft_id: str, workspace_id: str, user_id: str, body: Any) -> dict[str, Any]: ...
    def archive(self, draft_id: str, workspace_id: str, user_id: str) -> dict[str, Any]: ...
    def events(self, draft_id: str, workspace_id: str, user_id: str, limit: int, offset: int) -> dict[str, Any]: ...
    def runs(self, draft_id: str, workspace_id: str, user_id: str, limit: int, offset: int) -> dict[str, Any]: ...
    def run_events(self, draft_id: str, run_id: str, workspace_id: str, user_id: str, limit: int, offset: int) -> dict[str, Any]: ...
    def review(self, draft_id: str, run_id: str, workspace_id: str, user_id: str) -> dict[str, Any]: ...
    def decide(self, draft_id: str, run_id: str, workspace_id: str, user_id: str, decision: str, comment: str) -> dict[str, Any]: ...
    def export_manifest(self, draft_id: str, run_id: str, workspace_id: str, user_id: str) -> dict[str, Any]: ...
    def process_local(self, draft_id: str, workspace_id: str, user_id: str, idempotency_key: str) -> dict[str, Any]: ...


class SQLitePhotoDraftPort:
    def __init__(self, workspaces: WorkspacePort | None = None):
        self._workspaces = workspaces or get_workspace_port()

    def _draft(self, draft_id: str, workspace_id: str) -> dict[str, Any]:
        from app.photo_engine import get_draft
        value = get_draft(draft_id, workspace_id)
        if value is None:
            raise LookupError(DRAFT_NOT_FOUND)
        return value

    def create(self, workspace_id, user_id, body):
        from app.photo_engine import create_draft
        require_role(self._workspaces, workspace_id, user_id, write=True)
        return create_draft(workspace_id, user_id, body)

    def list(self, workspace_id, user_id, include_archived, limit, offset):
        from app.photo_engine import list_drafts
        require_role(self._workspaces, workspace_id, user_id)
        return list_drafts(workspace_id, include_archived=include_archived, limit=limit, offset=offset)

    def get(self, draft_id, workspace_id, user_id):
        require_role(self._workspaces, workspace_id, user_id)
        return self._draft(draft_id, workspace_id)

    def update(self, draft_id, workspace_id, user_id, body):
        from app.photo_engine import update_draft
        require_role(self._workspaces, workspace_id, user_id, write=True)
        self._draft(draft_id, workspace_id)
        return update_draft(draft_id, workspace_id, user_id, body)

    def archive(self, draft_id, workspace_id, user_id):
        from app.photo_engine import archive_draft
        require_role(self._workspaces, workspace_id, user_id, write=True)
        self._draft(draft_id, workspace_id)
        return archive_draft(draft_id, workspace_id, user_id)

    def events(self, draft_id, workspace_id, user_id, limit, offset):
        from app.photo_engine import list_events
        require_role(self._workspaces, workspace_id, user_id)
        self._draft(draft_id, workspace_id)
        return list_events(draft_id, workspace_id, limit=limit, offset=offset)

    def runs(self, draft_id, workspace_id, user_id, limit, offset):
        from app.photo_engine import list_processing_runs
        require_role(self._workspaces, workspace_id, user_id)
        self._draft(draft_id, workspace_id)
        return list_processing_runs(draft_id, workspace_id, limit=limit, offset=offset)

    def run_events(self, draft_id, run_id, workspace_id, user_id, limit, offset):
        from app.photo_engine import list_processing_events
        require_role(self._workspaces, workspace_id, user_id)
        self._draft(draft_id, workspace_id)
        events = list_processing_events(run_id, draft_id, workspace_id, limit=limit, offset=offset)
        if events["total"] == 0:
            raise LookupError(RUN_NOT_FOUND)
        return events

    def review(self, draft_id, run_id, workspace_id, user_id):
        from app.photo_engine import get_photo_output_review
        require_role(self._workspaces, workspace_id, user_id)
        self._draft(draft_id, workspace_id)
        result = get_photo_output_review(draft_id, run_id, workspace_id)
        if result is None:
            raise LookupError(RUN_NOT_FOUND)
        return result

    def decide(self, draft_id, run_id, workspace_id, user_id, decision, comment):
        from app.photo_engine import decide_photo_output_review
        _require_reviewer(self._workspaces, workspace_id, user_id)
        self._draft(draft_id, workspace_id)
        try:
            result = decide_photo_output_review(draft_id, run_id, workspace_id, user_id, decision, comment)
        except ValueError as exc:  # legacy contract: every state/validation refusal here is a 409
            raise RepositoryConflictError(str(exc)) from exc
        if result is None:
            raise LookupError(RUN_NOT_FOUND)
        return result

    def export_manifest(self, draft_id, run_id, workspace_id, user_id):
        from app.photo_engine import create_photo_output_export_manifest
        require_role(self._workspaces, workspace_id, user_id, write=True)
        self._draft(draft_id, workspace_id)
        try:
            result = create_photo_output_export_manifest(draft_id, run_id, workspace_id, user_id)
        except ValueError as exc:
            raise RepositoryConflictError(str(exc)) from exc
        if result is None:
            raise LookupError(RUN_NOT_FOUND)
        return result

    def process_local(self, draft_id, workspace_id, user_id, idempotency_key):
        from app.photo_engine import execute_local_processing
        require_role(self._workspaces, workspace_id, user_id, write=True)
        self._draft(draft_id, workspace_id)
        return _run_local(lambda: execute_local_processing(draft_id, workspace_id, user_id, idempotency_key))


class PostgreSQLPhotoDraftPort:
    def __init__(self, repository=None, assets_repository=None):
        if repository is None:
            from app.repository_registry import build_postgres_repository
            repository = build_postgres_repository("photos")
        self._repo = repository
        self._assets = assets_repository

    @staticmethod
    def _payload(body: Any) -> dict[str, Any]:
        return body.model_dump(mode="json")

    def _draft(self, draft_id, workspace_id, user_id):
        value = self._repo.get_draft(draft_id, workspace_id, user_id)
        if value is None:
            raise LookupError(DRAFT_NOT_FOUND)
        return value

    def create(self, workspace_id, user_id, body):
        return _plain(self._repo.create_draft(workspace_id, user_id, self._payload(body)))

    def list(self, workspace_id, user_id, include_archived, limit, offset):
        return _plain(self._repo.list_drafts(workspace_id, user_id, include_archived, limit=limit, offset=offset))

    def get(self, draft_id, workspace_id, user_id):
        return _plain(self._draft(draft_id, workspace_id, user_id))

    def update(self, draft_id, workspace_id, user_id, body):
        return _plain(self._repo.update_draft(draft_id, workspace_id, user_id, self._payload(body)))

    def archive(self, draft_id, workspace_id, user_id):
        return _plain(self._repo.archive_draft(draft_id, workspace_id, user_id))

    def events(self, draft_id, workspace_id, user_id, limit, offset):
        self._draft(draft_id, workspace_id, user_id)
        return _plain(self._repo.list_events(draft_id, workspace_id, user_id, limit=limit, offset=offset))

    def runs(self, draft_id, workspace_id, user_id, limit, offset):
        self._draft(draft_id, workspace_id, user_id)
        return _plain(self._repo.list_processing_runs(draft_id, workspace_id, user_id, limit=limit, offset=offset))

    def run_events(self, draft_id, run_id, workspace_id, user_id, limit, offset):
        self._draft(draft_id, workspace_id, user_id)
        events = self._repo.list_processing_events(run_id, draft_id, workspace_id, user_id, limit=limit, offset=offset)
        if events["total"] == 0:
            raise LookupError(RUN_NOT_FOUND)
        return _plain(events)

    def review(self, draft_id, run_id, workspace_id, user_id):
        self._draft(draft_id, workspace_id, user_id)
        result = self._repo.output_review(draft_id, run_id, workspace_id, user_id, verify_output_base)
        if result is None:
            raise LookupError(RUN_NOT_FOUND)
        return _plain(result)

    def decide(self, draft_id, run_id, workspace_id, user_id, decision, comment):
        self._repo.check_access(workspace_id, user_id, roles=set(REVIEW_ROLES))
        self._draft(draft_id, workspace_id, user_id)
        result = self._repo.decide_output_review(draft_id, run_id, workspace_id, user_id, decision, comment,
                                                 verify_output_base)
        if result is None:
            raise LookupError(RUN_NOT_FOUND)
        return _plain(result)

    def export_manifest(self, draft_id, run_id, workspace_id, user_id):
        self._repo.check_access(workspace_id, user_id, write=True)
        self._draft(draft_id, workspace_id, user_id)
        result = self._repo.create_export_manifest(draft_id, run_id, workspace_id, user_id, verify_output_base)
        if result is None:
            raise LookupError(RUN_NOT_FOUND)
        return _plain(result)

    def process_local(self, draft_id, workspace_id, user_id, idempotency_key):
        self._repo.check_access(workspace_id, user_id, write=True)
        self._draft(draft_id, workspace_id, user_id)
        return _run_local(lambda: self._execute_local(draft_id, workspace_id, user_id, idempotency_key))

    def _execute_local(self, draft_id, workspace_id, user_id, idempotency_key):
        from app.assets.blob_store import BlobIntegrityError
        from app.photo_engine import LOCAL_PHOTO_PROCESSOR_VERSION, render_local_image_bytes
        from app.ports.assets import _public_asset
        claim = self._repo.claim_local_run(draft_id, workspace_id, user_id, idempotency_key)
        if claim is None:
            return None
        assets = self._assets_repo()
        if claim["already_succeeded"]:
            run = claim["run"]
            row = assets.get_asset(run["output_asset_id"], workspace_id)
            return {"run": _plain(run), "output_asset": (_public_asset(row) | {"version_id": run["output_version_id"]}) if row else None}
        run_id, token, payload = claim["run_id"], claim["claim_token"], claim["payload"]
        try:
            source_id, version_id = payload["source_asset_id"], payload["source_version_id"]
            source = assets.get_asset(source_id, workspace_id)
            version = assets.get_asset_version_record(source_id, workspace_id, version_id)
            if not source or not version:
                raise ValueError("Snapshotted source image version is missing or inactive")
            try:
                original = self._blobs().read_verified(version["storage_key"], int(version["size_bytes"]), version["checksum_sha256"])
            except BlobIntegrityError as exc:
                raise ValueError("Snapshotted source image failed its immutable version integrity check") from exc
            if version["checksum_sha256"] != payload["source_checksum_sha256"]:
                raise ValueError("Snapshotted source image failed its immutable version integrity check")
            content, validated, quality = render_local_image_bytes(original, version_id, payload["source_checksum_sha256"], payload)
            asset = self._bytes_port().save_derived(
                asset_id="ast_photo_" + run_id.removeprefix("phr_"), owner_id=user_id, workspace_id=workspace_id,
                source_asset_id=source_id, source_version_id=version_id,
                source_checksum_sha256=payload["source_checksum_sha256"],
                filename=f"photo-{payload['operation'].lower()}.{payload['output_format'].lower()}",
                content=content, validated=validated, run_id=run_id, operation=payload["operation"],
                processor_version=LOCAL_PHOTO_PROCESSOR_VERSION)
            if not self._repo.complete_local_run(run_id, token, user_id, asset_id=asset["asset_id"],
                                                 version_id=asset["version_id"], checksum=asset["checksum_sha256"], quality=quality):
                current = self._repo.get_run(run_id)
                if not current or current["status"] != "succeeded":
                    raise RuntimeError("Photo processing lease was lost before finalization")
            return {"run": _plain(self._repo.get_run(run_id)), "output_asset": asset}
        except Exception as exc:  # noqa: BLE001
            safe = "Source image integrity validation failed" if isinstance(exc, ValueError) else "Local image processing failed"
            self._repo.fail_local_run(run_id, token, user_id, safe)
            raise RuntimeError(safe) from exc

    def _assets_repo(self):
        if self._assets is None:
            from app.repository_registry import build_postgres_repository
            self._assets = build_postgres_repository("workspace_and_asset_metadata", allow_unverified=True)
        return self._assets

    def _blobs(self):
        from app.assets.blob_store import LocalBlobStore
        return LocalBlobStore()

    def _bytes_port(self):
        from app.ports.asset_bytes import PostgreSQLAssetBytesPort
        return PostgreSQLAssetBytesPort(self._assets_repo())


def get_photo_draft_port() -> PhotoDraftPort:
    return SQLitePhotoDraftPort() if require_runtime_backend() == "sqlite" else PostgreSQLPhotoDraftPort()
