"""PostgreSQL metadata adapter for Workspace RBAC and versioned Assets.

This adapter does not move object bytes and is not wired into the API runtime;
Supabase Storage integration and live tenant-policy tests are separate gates.
"""
from __future__ import annotations
import json
import uuid
from datetime import datetime, timezone
from typing import Any
from app.postgres import connect, apply_migrations
from app.repo_errors import InsufficientRoleError, NotAMemberError, RepositoryConflictError


class WorkspaceConflictError(RepositoryConflictError):
    """Workspace ID or membership already exists."""


class AssetConflictError(RepositoryConflictError):
    """Asset is referenced (delete refused) or a relation already exists."""


class PostgreSQLAssetMetadataRepository:
    backend = "postgresql"
    ROLES = {"owner", "admin", "editor", "viewer"}

    @staticmethod
    def _now():
        return datetime.now(timezone.utc)

    @staticmethod
    def _jsonb(value: Any):
        try:
            from psycopg.types.json import Jsonb
            return Jsonb(value)
        except ImportError as exc:
            raise RuntimeError("psycopg 3 is required for PostgreSQL Asset repository") from exc

    def initialize(self):
        return apply_migrations()

    def create_workspace(self, workspace_id: str, owner_id: str) -> dict[str, Any]:
        if not workspace_id.strip() or not owner_id.strip():
            raise ValueError("workspace_id and owner_id are required")
        now = self._now()
        try:
            with connect() as conn:
                conn.execute("INSERT INTO workspaces(workspace_id,owner_id,created_at) VALUES(%s,%s,%s)",
                             (workspace_id, owner_id, now))
                conn.execute("INSERT INTO workspace_members(workspace_id,user_id,role,created_at) VALUES(%s,%s,'owner',%s)",
                             (workspace_id, owner_id, now))
        except Exception as exc:
            if getattr(exc, "sqlstate", None) == "23505":
                raise WorkspaceConflictError("Workspace ID already exists") from exc
            raise
        return {"workspace_id": workspace_id, "owner_id": owner_id, "role": "owner", "created_at": now.isoformat()}

    def workspace_role(self, workspace_id: str, user_id: str) -> str | None:
        with connect() as conn:
            row = conn.execute("SELECT role FROM workspace_members WHERE workspace_id=%s AND user_id=%s",
                               (workspace_id, user_id)).fetchone()
        return row["role"] if row else None

    def add_workspace_member(self, workspace_id: str, user_id: str, role: str, *, actor_id: str) -> dict[str, str]:
        if role not in self.ROLES - {"owner"}:
            raise ValueError("Workspace member role is invalid; owner is assigned only at workspace creation")
        now = self._now()
        with connect() as conn:
            workspace = conn.execute("SELECT owner_id FROM workspaces WHERE workspace_id=%s FOR UPDATE",
                                     (workspace_id,)).fetchone()
            actor = conn.execute("SELECT role FROM workspace_members WHERE workspace_id=%s AND user_id=%s",
                                 (workspace_id, actor_id)).fetchone()
            if workspace is None or actor is None:  # a missing workspace is indistinguishable from no access
                raise NotAMemberError("User is not a member of this workspace")
            if actor["role"] not in {"owner", "admin"}:
                raise InsufficientRoleError("Only workspace owners or admins can manage membership")
            if user_id == workspace["owner_id"] or conn.execute(
                    "SELECT 1 FROM workspace_members WHERE workspace_id=%s AND user_id=%s",
                    (workspace_id, user_id)).fetchone():
                raise WorkspaceConflictError("Member already exists or workspace is invalid")
            conn.execute("""INSERT INTO workspace_members(workspace_id,user_id,role,created_at)
                VALUES(%s,%s,%s,%s)""", (workspace_id, user_id, role, now))
        return {"workspace_id": workspace_id, "user_id": user_id, "role": role, "created_at": now.isoformat()}

    def list_workspaces(self, user_id: str) -> list[dict[str, Any]]:
        with connect() as conn:
            rows = conn.execute("""SELECT w.workspace_id,w.owner_id,w.created_at,m.role
                FROM workspace_members m JOIN workspaces w USING(workspace_id)
                WHERE m.user_id=%s ORDER BY w.created_at DESC,w.workspace_id""", (user_id,)).fetchall()
        return [dict(row) for row in rows]

    def register_asset(self, *, asset_id: str, owner_id: str, workspace_id: str,
                       original_filename: str, storage_key: str, media_type: str,
                       size_bytes: int, checksum_sha256: str, gltf_version: str = "",
                       embedded_binary: bool = False, storage_backend: str = "local",
                       storage_bucket: str = "private_assets") -> dict[str, Any]:
        if not all(isinstance(v, str) and v.strip() for v in
                   (asset_id, owner_id, workspace_id, original_filename, storage_key, media_type)):
            raise ValueError("Asset identity and metadata fields are required")
        if isinstance(size_bytes, bool) or not isinstance(size_bytes, int) or size_bytes < 0:
            raise ValueError("Asset size must be a non-negative integer")
        if len(checksum_sha256) != 64 or any(c not in "0123456789abcdef" for c in checksum_sha256.lower()):
            raise ValueError("Asset checksum must be a SHA-256 hex digest")
        if storage_backend not in {"local", "supabase_storage"} or not storage_bucket.strip():
            raise ValueError("Asset storage locator is invalid")
        now = self._now()
        version_id = "av_" + uuid.uuid4().hex
        provenance_id = "ap_" + uuid.uuid4().hex
        with connect() as conn:
            member = conn.execute("SELECT role FROM workspace_members WHERE workspace_id=%s AND user_id=%s",
                                  (workspace_id, owner_id)).fetchone()
            if member is None or member["role"] not in {"owner", "admin", "editor"}:
                raise PermissionError("User does not have permission to register assets in this workspace")
            conn.execute("""INSERT INTO assets(asset_id,owner_id,workspace_id,original_filename,storage_key,
                media_type,size_bytes,checksum_sha256,storage_backend,storage_bucket,gltf_version,embedded_binary,created_at)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (asset_id, owner_id, workspace_id, original_filename[:255], storage_key, media_type,
                 size_bytes, checksum_sha256.lower(), storage_backend, storage_bucket,
                 gltf_version, embedded_binary, now))
            conn.execute("""INSERT INTO asset_versions(version_id,asset_id,workspace_id,version_number,
                storage_key,media_type,size_bytes,checksum_sha256,storage_backend,storage_bucket,created_by,created_at)
                VALUES(%s,%s,%s,1,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (version_id, asset_id, workspace_id, storage_key, media_type, size_bytes,
                 checksum_sha256.lower(), storage_backend, storage_bucket, owner_id, now))
            conn.execute("""INSERT INTO asset_provenance(provenance_id,workspace_id,asset_id,version_number,
                event_type,actor_id,details_json,created_at)
                VALUES(%s,%s,%s,1,'asset.uploaded',%s,%s,%s)""",
                (provenance_id, workspace_id, asset_id, owner_id,
                 self._jsonb({"source": "upload"}), now))
        return self.get_asset(asset_id, workspace_id)

    def get_asset(self, asset_id: str, workspace_id: str) -> dict[str, Any] | None:
        with connect() as conn:
            row = conn.execute("SELECT * FROM assets WHERE asset_id=%s AND workspace_id=%s AND deleted_at IS NULL",
                               (asset_id, workspace_id)).fetchone()
        return dict(row) if row else None

    def list_assets(self, workspace_id: str, *, kind: str = "all") -> list[dict[str, Any]]:
        if kind not in {"all", "image", "model"}:
            raise ValueError("Asset kind must be all, image, or model")
        predicate = "" if kind == "all" else (" AND media_type LIKE 'image/%%'" if kind == "image" else " AND media_type LIKE 'model/%%'")
        with connect() as conn:
            rows = conn.execute("SELECT * FROM assets WHERE workspace_id=%s AND deleted_at IS NULL" + predicate +
                                " ORDER BY created_at DESC,asset_id", (workspace_id,)).fetchall()
        return [dict(row) for row in rows]

    def create_asset_version(self, *, asset_id: str, workspace_id: str, actor_id: str,
                             storage_key: str, media_type: str, size_bytes: int,
                             checksum_sha256: str, storage_backend: str = "local",
                             storage_bucket: str = "private_assets", version_id: str | None = None,
                             original_filename: str | None = None, gltf_version: str | None = None,
                             embedded_binary: bool | None = None) -> dict[str, Any]:
        if not storage_key.strip() or not media_type.strip():
            raise ValueError("Version storage key and media type are required")
        if isinstance(size_bytes, bool) or not isinstance(size_bytes, int) or size_bytes < 0:
            raise ValueError("Version size must be a non-negative integer")
        if len(checksum_sha256) != 64 or any(c not in "0123456789abcdef" for c in checksum_sha256.lower()):
            raise ValueError("Version checksum must be a SHA-256 hex digest")
        if storage_backend not in {"local", "supabase_storage"} or not storage_bucket.strip():
            raise ValueError("Asset version storage locator is invalid")
        version_id = version_id or "av_" + uuid.uuid4().hex
        provenance_id = "ap_" + uuid.uuid4().hex
        now = self._now()
        with connect() as conn:
            self._require_writer(conn, workspace_id, actor_id)
            asset = conn.execute("""SELECT asset_id FROM assets WHERE asset_id=%s AND workspace_id=%s
                AND deleted_at IS NULL FOR UPDATE""", (asset_id, workspace_id)).fetchone()
            if asset is None:
                raise LookupError("Asset not found")
            number = conn.execute("SELECT COALESCE(MAX(version_number),0)+1 AS next_number FROM asset_versions WHERE asset_id=%s",
                                  (asset_id,)).fetchone()["next_number"]
            conn.execute("""INSERT INTO asset_versions(version_id,asset_id,workspace_id,version_number,
                storage_key,media_type,size_bytes,checksum_sha256,storage_backend,storage_bucket,created_by,created_at)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (version_id, asset_id, workspace_id, number, storage_key, media_type,
                 size_bytes, checksum_sha256.lower(), storage_backend, storage_bucket, actor_id, now))
            conn.execute("""UPDATE assets SET storage_key=%s,media_type=%s,size_bytes=%s,
                checksum_sha256=%s,storage_backend=%s,storage_bucket=%s,
                original_filename=COALESCE(%s,original_filename),
                gltf_version=COALESCE(%s,gltf_version),
                embedded_binary=COALESCE(%s,embedded_binary) WHERE asset_id=%s""",
                (storage_key, media_type, size_bytes, checksum_sha256.lower(),
                 storage_backend, storage_bucket,
                 original_filename[:255] if original_filename else None, gltf_version, embedded_binary, asset_id))
            conn.execute("""INSERT INTO asset_provenance(provenance_id,workspace_id,asset_id,version_number,
                event_type,actor_id,details_json,created_at)
                VALUES(%s,%s,%s,%s,'asset.version_created',%s,%s,%s)""",
                (provenance_id, workspace_id, asset_id, number, actor_id,
                 self._jsonb({"version_id": version_id, "previous_version": int(number) - 1}), now))
        return {"version_id": version_id, "asset_id": asset_id, "workspace_id": workspace_id,
                "version_number": number, "storage_key": storage_key, "media_type": media_type,
                "size_bytes": size_bytes, "checksum_sha256": checksum_sha256.lower(),
                "created_by": actor_id, "created_at": now}

    def list_asset_versions(self, asset_id: str, workspace_id: str) -> list[dict[str, Any]]:
        with connect() as conn:
            rows = conn.execute("""SELECT v.* FROM asset_versions v JOIN assets a USING(asset_id)
                WHERE v.asset_id=%s AND v.workspace_id=%s AND a.workspace_id=%s
                ORDER BY v.version_number DESC""", (asset_id, workspace_id, workspace_id)).fetchall()
        return [dict(row) for row in rows]

    def list_asset_provenance(self, asset_id: str, workspace_id: str, *, limit: int = 100,
                              offset: int = 0) -> list[dict[str, Any]]:
        if not 1 <= limit <= 500 or offset < 0:
            raise ValueError("Invalid provenance pagination")
        with connect() as conn:
            rows = conn.execute("""SELECT p.* FROM asset_provenance p JOIN assets a USING(asset_id)
                WHERE p.asset_id=%s AND p.workspace_id=%s AND a.workspace_id=%s
                ORDER BY p.created_at DESC,p.provenance_id DESC LIMIT %s OFFSET %s""",
                (asset_id, workspace_id, workspace_id, limit, offset)).fetchall()
        return [dict(row) for row in rows]

    def create_asset_relation(self, *, workspace_id: str, source_asset_id: str,
                              target_asset_id: str, relation_type: str,
                              created_by: str) -> dict[str, Any]:
        allowed = {"derived_from", "variant_of", "uses_texture", "paired_with"}
        if relation_type not in allowed:
            raise ValueError("Unsupported relation type")
        if source_asset_id == target_asset_id:
            raise ValueError("An asset cannot be related to itself")
        now = self._now()
        relation_id = "ar_" + uuid.uuid4().hex
        with connect() as conn:
            self._require_writer(conn, workspace_id, created_by)
            rows = conn.execute("""SELECT asset_id FROM assets WHERE workspace_id=%s AND deleted_at IS NULL
                AND asset_id IN (%s,%s) ORDER BY asset_id FOR UPDATE""",
                (workspace_id, source_asset_id, target_asset_id)).fetchall()
            if len(rows) != 2:
                raise LookupError("Both assets must exist in the same workspace")
            if relation_type == "derived_from":
                cycle = conn.execute("""WITH RECURSIVE reachable(asset_id) AS (
                    SELECT target_asset_id FROM asset_relations
                    WHERE workspace_id=%s AND source_asset_id=%s AND relation_type='derived_from'
                    UNION
                    SELECT r.target_asset_id FROM asset_relations r
                    JOIN reachable p ON r.source_asset_id=p.asset_id
                    WHERE r.workspace_id=%s AND r.relation_type='derived_from'
                ) SELECT 1 FROM reachable WHERE asset_id=%s LIMIT 1""",
                    (workspace_id, target_asset_id, workspace_id, source_asset_id)).fetchone()
                if cycle:
                    raise ValueError("derived_from relation would create a cycle")
            if conn.execute("""SELECT 1 FROM asset_relations WHERE source_asset_id=%s AND target_asset_id=%s
                AND relation_type=%s""", (source_asset_id, target_asset_id, relation_type)).fetchone():
                raise AssetConflictError("This asset relation already exists")
            conn.execute("""INSERT INTO asset_relations(relation_id,workspace_id,source_asset_id,
                target_asset_id,relation_type,created_by,created_at) VALUES(%s,%s,%s,%s,%s,%s,%s)""",
                (relation_id, workspace_id, source_asset_id, target_asset_id, relation_type, created_by, now))
            for asset_id, event, key, other in (
                    (source_asset_id, "asset.relation_created", "target_asset_id", target_asset_id),
                    (target_asset_id, "asset.relation_received", "source_asset_id", source_asset_id)):
                conn.execute("""INSERT INTO asset_provenance(provenance_id,workspace_id,asset_id,version_number,
                    event_type,actor_id,details_json,created_at) VALUES(%s,%s,%s,NULL,%s,%s,%s,%s)""",
                    ("ap_" + uuid.uuid4().hex, workspace_id, asset_id, event, created_by,
                     self._jsonb({"relation_id": relation_id, key: other, "relation_type": relation_type}), now))
        return {"relation_id": relation_id, "workspace_id": workspace_id, "source_asset_id": source_asset_id,
                "target_asset_id": target_asset_id, "relation_type": relation_type,
                "created_by": created_by, "created_at": now}

    def save_derived_image_metadata(self, *, asset_id: str, owner_id: str, workspace_id: str,
                                    source_asset_id: str, source_version_id: str, source_checksum_sha256: str,
                                    filename: str, media_type: str, size_bytes: int, checksum_sha256: str,
                                    storage_key: str, run_id: str, operation: str,
                                    processor_version: str) -> dict[str, Any]:
        """Idempotent metadata for a deterministic Photo output (the file is written by the bytes port).

        Mirrors ``app.assets.store.save_derived_image_asset``: a retry with identical bytes reuses the rows,
        any divergence is refused, and the version/provenance/relation ids derive from the run id.
        """
        if not asset_id.startswith("ast_") or size_bytes <= 0:
            raise ValueError("A deterministic asset ID and non-empty image are required")
        suffix = run_id.removeprefix("phr_")
        version_id, provenance_id, relation_id = "av_photo_" + suffix, "ap_photo_" + suffix, "ar_photo_" + suffix
        now = self._now()
        with connect() as conn:
            if not conn.execute("SELECT 1 FROM workspace_members WHERE workspace_id=%s AND user_id=%s",
                                (workspace_id, owner_id)).fetchone():
                raise ValueError("User is not a member of the workspace")
            source = conn.execute("""SELECT asset_id FROM assets WHERE asset_id=%s AND workspace_id=%s
                AND deleted_at IS NULL AND media_type LIKE 'image/%%' FOR UPDATE""",
                (source_asset_id, workspace_id)).fetchone()
            source_version = conn.execute("""SELECT version_id,checksum_sha256 FROM asset_versions
                WHERE asset_id=%s AND workspace_id=%s AND version_id=%s""",
                (source_asset_id, workspace_id, source_version_id)).fetchone()
            if source is None or source_version is None or source_version["checksum_sha256"] != source_checksum_sha256:
                raise ValueError("Snapshotted source image version is no longer available or failed integrity checks")
            existing = conn.execute("SELECT * FROM assets WHERE asset_id=%s AND workspace_id=%s AND deleted_at IS NULL",
                                    (asset_id, workspace_id)).fetchone()
            if existing:
                if (existing["checksum_sha256"] != checksum_sha256 or existing["size_bytes"] != size_bytes
                        or existing["media_type"] != media_type or existing["storage_key"] != storage_key):
                    raise ValueError("Existing deterministic Photo output metadata does not match the retry")
                version = conn.execute("""SELECT size_bytes,checksum_sha256,storage_key FROM asset_versions
                    WHERE asset_id=%s AND version_id=%s""", (asset_id, version_id)).fetchone()
                if (version is None or version["size_bytes"] != size_bytes
                        or version["checksum_sha256"] != checksum_sha256 or version["storage_key"] != storage_key):
                    raise ValueError("Existing deterministic Photo output is missing its verified immutable version")
                relation = conn.execute("""SELECT 1 FROM asset_relations WHERE source_asset_id=%s AND target_asset_id=%s
                    AND relation_type='derived_from'""", (asset_id, source_asset_id)).fetchone()
                provenance = conn.execute("""SELECT 1 FROM asset_provenance WHERE asset_id=%s
                    AND event_type='asset.photo_processed'""", (asset_id,)).fetchone()
                if relation is None or provenance is None:
                    raise ValueError("Existing deterministic Photo output is missing its provenance or source relation")
            else:
                conn.execute("""INSERT INTO assets(asset_id,owner_id,workspace_id,original_filename,storage_key,
                    media_type,size_bytes,checksum_sha256,gltf_version,embedded_binary,created_at)
                    VALUES(%s,%s,%s,%s,%s,%s,%s,%s,'',false,%s)""",
                    (asset_id, owner_id, workspace_id, filename[:255], storage_key, media_type,
                     size_bytes, checksum_sha256, now))
                conn.execute("""INSERT INTO asset_versions(version_id,asset_id,workspace_id,version_number,storage_key,
                    media_type,size_bytes,checksum_sha256,created_by,created_at) VALUES(%s,%s,%s,1,%s,%s,%s,%s,%s,%s)""",
                    (version_id, asset_id, workspace_id, storage_key, media_type, size_bytes, checksum_sha256,
                     owner_id, now))
                conn.execute("""INSERT INTO asset_provenance(provenance_id,workspace_id,asset_id,version_number,
                    event_type,actor_id,details_json,created_at) VALUES(%s,%s,%s,1,'asset.photo_processed',%s,%s,%s)""",
                    (provenance_id, workspace_id, asset_id, owner_id, self._jsonb({
                        "run_id": run_id, "source_asset_id": source_asset_id, "source_version_id": source_version_id,
                        "source_checksum_sha256": source_checksum_sha256, "operation": operation,
                        "processor_version": processor_version, "is_ai_generated": False,
                        "provider_dispatched": False, "credit_charged": False}), now))
                conn.execute("""INSERT INTO asset_relations(relation_id,workspace_id,source_asset_id,target_asset_id,
                    relation_type,created_by,created_at) VALUES(%s,%s,%s,%s,'derived_from',%s,%s)""",
                    (relation_id, workspace_id, asset_id, source_asset_id, owner_id, now))
                conn.execute("""INSERT INTO asset_provenance(provenance_id,workspace_id,asset_id,version_number,
                    event_type,actor_id,details_json,created_at) VALUES(%s,%s,%s,NULL,'asset.relation_created',%s,%s,%s)""",
                    ("ap_photo_relation_" + suffix, workspace_id, asset_id, owner_id, self._jsonb({
                        "relation_id": relation_id, "target_asset_id": source_asset_id, "relation_type": "derived_from"}), now))
                conn.execute("""INSERT INTO asset_provenance(provenance_id,workspace_id,asset_id,version_number,
                    event_type,actor_id,details_json,created_at) VALUES(%s,%s,%s,NULL,'asset.relation_received',%s,%s,%s)""",
                    ("ap_photo_received_" + suffix, workspace_id, source_asset_id, owner_id, self._jsonb({
                        "relation_id": relation_id, "source_asset_id": asset_id, "relation_type": "derived_from"}), now))
        return {"version_id": version_id, "version_number": 1, "checksum_sha256": checksum_sha256}

    def list_asset_relations(self, asset_id: str, workspace_id: str) -> list[dict[str, Any]]:
        with connect() as conn:
            rows = conn.execute("""SELECT * FROM asset_relations WHERE workspace_id=%s
                AND (source_asset_id=%s OR target_asset_id=%s) ORDER BY created_at DESC,relation_id""",
                (workspace_id, asset_id, asset_id)).fetchall()
        return [dict(row) for row in rows]

    @classmethod
    def _require_writer(cls, conn: Any, workspace_id: str, actor_id: str) -> None:
        member = conn.execute("SELECT role FROM workspace_members WHERE workspace_id=%s AND user_id=%s",
                              (workspace_id, actor_id)).fetchone()
        if member is None:
            raise NotAMemberError("User is not a member of this workspace")
        if member["role"] not in {"owner", "admin", "editor"}:
            raise InsufficientRoleError("Insufficient workspace role")

    def workspace_for_asset(self, asset_id: str) -> str | None:
        with connect() as conn:
            row = conn.execute("SELECT workspace_id FROM assets WHERE asset_id=%s AND deleted_at IS NULL",
                               (asset_id,)).fetchone()
        return str(row["workspace_id"]) if row else None

    def get_asset_version_record(self, asset_id: str, workspace_id: str, version_id: str) -> dict[str, Any] | None:
        with connect() as conn:
            row = conn.execute("""SELECT v.*,a.original_filename FROM asset_versions v
                JOIN assets a ON a.asset_id=v.asset_id AND a.workspace_id=v.workspace_id
                WHERE v.asset_id=%s AND v.workspace_id=%s AND v.version_id=%s AND a.deleted_at IS NULL""",
                (asset_id, workspace_id, version_id)).fetchone()
        return dict(row) if row else None

    def soft_delete_asset(self, asset_id: str, workspace_id: str, *, actor_id: str) -> bool:
        """Metadata-only delete with the same reference guards as the legacy implementation.

        Object bytes are NOT removed here; the bytes port owns that step (see ASSET_STORAGE_PORT_DESIGN.md).
        """
        now = self._now()
        with connect() as conn:
            self._require_writer(conn, workspace_id, actor_id)
            row = conn.execute("""SELECT 1 FROM assets WHERE asset_id=%s AND workspace_id=%s
                AND deleted_at IS NULL FOR UPDATE""", (asset_id, workspace_id)).fetchone()
            if row is None:
                return False
            guards = (
                ("""SELECT 1 FROM asset_provenance WHERE asset_id=%s AND event_type IN
                    ('asset.generated_output_imported','asset.photo_processed') LIMIT 1""", (asset_id,),
                 "Asset is a persisted generated or processed output; use the Output retention workflow before deletion"),
                ("""SELECT 1 FROM product_assets pa JOIN products p ON p.product_id=pa.product_id
                    WHERE pa.asset_id=%s AND p.workspace_id=%s AND p.status='ACTIVE' LIMIT 1""", (asset_id, workspace_id),
                 "Asset is referenced by an active Product; update or archive the Product first"),
                ("""SELECT 1 FROM product_variant_assets pva JOIN product_variants pv ON pv.variant_id=pva.variant_id
                    WHERE pva.asset_id=%s AND pv.workspace_id=%s AND pv.status='ACTIVE' LIMIT 1""", (asset_id, workspace_id),
                 "Asset is referenced by an active Product Variant; update or archive the Variant first"),
                ("""SELECT 1 FROM photo_draft_assets l JOIN photo_drafts d ON d.draft_id=l.draft_id
                    WHERE l.asset_id=%s AND d.workspace_id=%s AND d.archived_at IS NULL LIMIT 1""", (asset_id, workspace_id),
                 "Asset is referenced by an active Photo Draft; archive the draft first"),
                ("""SELECT 1 FROM lookbook_draft_assets l JOIN lookbook_drafts d ON d.draft_id=l.draft_id
                    WHERE l.asset_id=%s AND d.workspace_id=%s AND d.archived_at IS NULL LIMIT 1""", (asset_id, workspace_id),
                 "Asset is referenced by an active Lookbook Draft; archive the draft first"),
            )
            for query, params, message in guards:
                if conn.execute(query, params).fetchone():
                    raise AssetConflictError(message)
            conn.execute("UPDATE assets SET deleted_at=%s WHERE asset_id=%s AND workspace_id=%s",
                         (now, asset_id, workspace_id))
            conn.execute("""INSERT INTO asset_provenance(provenance_id,workspace_id,asset_id,version_number,
                event_type,actor_id,details_json,created_at) VALUES(%s,%s,%s,NULL,'asset.deleted',%s,%s,%s)""",
                ("ap_" + uuid.uuid4().hex, workspace_id, asset_id, actor_id,
                 self._jsonb({"source": "user_delete"}), now))
        return True

    # -- byte-adjacent metadata (the bytes port writes/removes the files around these) ------------------

    def restore_asset_version(self, *, asset_id: str, workspace_id: str, actor_id: str, source_version_id: str,
                              new_version_id: str, storage_key: str, media_type: str, size_bytes: int,
                              checksum_sha256: str, original_filename: str, gltf_version: str,
                              embedded_binary: bool) -> dict[str, Any]:
        """Promote a verified historical version as a NEW immutable current version (legacy semantics)."""
        now = self._now()
        with connect() as conn:
            self._require_writer(conn, workspace_id, actor_id)
            if conn.execute("""SELECT 1 FROM assets WHERE asset_id=%s AND workspace_id=%s
                AND deleted_at IS NULL FOR UPDATE""", (asset_id, workspace_id)).fetchone() is None:
                raise LookupError("Asset or historical version not found")
            source = conn.execute("""SELECT version_number FROM asset_versions
                WHERE asset_id=%s AND workspace_id=%s AND version_id=%s""",
                (asset_id, workspace_id, source_version_id)).fetchone()
            if source is None:
                raise LookupError("Asset or historical version not found")
            current = int(conn.execute("SELECT COALESCE(MAX(version_number),0) AS n FROM asset_versions WHERE asset_id=%s",
                                       (asset_id,)).fetchone()["n"])
            number = current + 1
            conn.execute("""INSERT INTO asset_versions(version_id,asset_id,workspace_id,version_number,storage_key,
                media_type,size_bytes,checksum_sha256,created_by,created_at) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (new_version_id, asset_id, workspace_id, number, storage_key, media_type, size_bytes,
                 checksum_sha256.lower(), actor_id, now))
            conn.execute("""UPDATE assets SET original_filename=%s,storage_key=%s,media_type=%s,size_bytes=%s,
                checksum_sha256=%s,gltf_version=%s,embedded_binary=%s WHERE asset_id=%s AND workspace_id=%s""",
                (original_filename[:255], storage_key, media_type, size_bytes, checksum_sha256.lower(),
                 gltf_version, embedded_binary, asset_id, workspace_id))
            conn.execute("""INSERT INTO asset_provenance(provenance_id,workspace_id,asset_id,version_number,
                event_type,actor_id,details_json,created_at) VALUES(%s,%s,%s,%s,'asset.version_restored',%s,%s,%s)""",
                ("ap_" + uuid.uuid4().hex, workspace_id, asset_id, number, actor_id,
                 self._jsonb({"version_id": new_version_id, "restored_from_version_id": source_version_id,
                              "restored_from_version_number": int(source["version_number"]),
                              "previous_version": current}), now))
        return {"version_number": number, "version_id": new_version_id}

    def asset_storage_keys(self, asset_id: str) -> set[str]:
        """Every object key an asset ever pointed at (current + all versions)."""
        with connect() as conn:
            rows = conn.execute("""SELECT storage_key FROM assets WHERE asset_id=%s
                UNION SELECT storage_key FROM asset_versions WHERE asset_id=%s""", (asset_id, asset_id)).fetchall()
        return {str(r["storage_key"]) for r in rows}

    def audit_page(self, workspace_id: str, *, limit: int, offset: int) -> tuple[int, list[dict[str, Any]]]:
        if not 1 <= limit <= 500 or offset < 0:
            raise ValueError("Invalid audit pagination")
        with connect() as conn:
            total = conn.execute("SELECT count(*) AS n FROM assets WHERE workspace_id=%s AND deleted_at IS NULL",
                                 (workspace_id,)).fetchone()["n"]
            rows = conn.execute("""SELECT asset_id,storage_key,size_bytes,checksum_sha256 FROM assets
                WHERE workspace_id=%s AND deleted_at IS NULL ORDER BY created_at DESC,asset_id LIMIT %s OFFSET %s""",
                (workspace_id, limit, offset)).fetchall()
        return int(total), [dict(r) for r in rows]
