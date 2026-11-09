"""PostgreSQL Product Catalog repository; not runtime-selected until all aggregates migrate."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from app.postgres import apply_migrations, connect
from app.repo_errors import DetailedValueError, InsufficientRoleError, NotAMemberError, RepositoryConflictError

SKU_TAKEN = "SKU already exists in this workspace"
IMAGE_DETAIL = {"code": "PRODUCT_IMAGE_ASSET_REQUIRED",
                "message": "All product images must be active image assets in this workspace."}


class ProductConflictError(RepositoryConflictError):
    """SKU taken, or the Product is referenced by an active Lookbook Draft / active Project."""


class PostgreSQLProductRepository:
    backend = "postgresql"
    WRITABLE_ROLES = {"owner", "admin", "editor"}
    READABLE_ROLES = WRITABLE_ROLES | {"viewer"}

    def initialize(self) -> None:
        apply_migrations()

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _validate(*, sku: str, name: str, description: str | None, category: str,
                  image_asset_ids: list[str]) -> None:
        if not isinstance(sku, str) or not 2 <= len(sku.strip()) <= 64:
            raise ValueError("Product SKU must contain 2 to 64 characters")
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 160:
            raise ValueError("Product name must contain 1 to 160 characters")
        if description is not None and (not isinstance(description, str) or len(description) > 2000):
            raise ValueError("Product description exceeds 2000 characters")
        if not isinstance(category, str) or not 1 <= len(category.strip()) <= 64:
            raise ValueError("Product category must contain 1 to 64 characters")
        if (not isinstance(image_asset_ids, list) or not 1 <= len(image_asset_ids) <= 12
                or len(image_asset_ids) != len(set(image_asset_ids))
                or any(not isinstance(value, str) or not value.strip() or len(value) > 80 for value in image_asset_ids)):
            raise ValueError("Product requires 1 to 12 unique image asset IDs")

    @staticmethod
    def _role(conn: Any, workspace_id: str, actor_id: str) -> str | None:
        row = conn.execute(
            "SELECT role FROM workspace_members WHERE workspace_id=%s AND user_id=%s",
            (workspace_id, actor_id),
        ).fetchone()
        return str(row["role"]) if row else None

    @classmethod
    def _require(cls, conn: Any, workspace_id: str, actor_id: str, *, write: bool = False) -> str:
        role = cls._role(conn, workspace_id, actor_id)
        if role is None:
            raise NotAMemberError("User is not a member of this workspace")
        if role not in (cls.WRITABLE_ROLES if write else cls.READABLE_ROLES):
            raise InsufficientRoleError("Insufficient workspace role")
        return role

    @staticmethod
    def _read(conn: Any, row: Any) -> dict[str, Any]:
        value = dict(row)
        images = conn.execute(
            "SELECT asset_id FROM product_assets WHERE product_id=%s ORDER BY sort_order,asset_id",
            (value["product_id"],),
        ).fetchall()
        variants = conn.execute(
            """SELECT variant_id,sku,option_values,status,created_by,created_at,updated_at,archived_at
               FROM product_variants WHERE product_id=%s ORDER BY created_at,variant_id""",
            (value["product_id"],),
        ).fetchall()
        value["image_asset_ids"] = [str(item["asset_id"]) for item in images]
        value["variants"] = []
        for variant in variants:
            variant_value = dict(variant)
            variant_assets = conn.execute(
                "SELECT asset_id FROM product_variant_assets WHERE variant_id=%s ORDER BY sort_order,asset_id",
                (variant_value["variant_id"],),
            ).fetchall()
            variant_value["image_asset_ids"] = [str(item["asset_id"]) for item in variant_assets]
            variant_value["status"] = "archived" if variant_value.get("archived_at") else str(variant_value["status"]).lower()
            value["variants"].append(variant_value)
        value["status"] = "archived" if value.get("archived_at") else str(value["status"]).lower()
        return value

    def create(self, *, workspace_id: str, actor_id: str, sku: str, name: str,
               description: str | None, category: str, image_asset_ids: list[str]) -> dict[str, Any]:
        self._validate(sku=sku, name=name, description=description, category=category,
                      image_asset_ids=image_asset_ids)
        now = self._now()
        product_id = "prd_" + uuid.uuid4().hex
        with connect() as conn:
            self._require(conn, workspace_id, actor_id, write=True)
            assets = conn.execute(
                """SELECT asset_id FROM assets WHERE workspace_id=%s AND deleted_at IS NULL
                   AND media_type LIKE 'image/%%' AND asset_id = ANY(%s)
                   ORDER BY asset_id FOR SHARE""",
                (workspace_id, image_asset_ids),
            ).fetchall()
            if len(assets) != len(image_asset_ids):
                raise DetailedValueError(IMAGE_DETAIL)
            collision = conn.execute(
                """SELECT 1 FROM products WHERE workspace_id=%s AND lower(sku)=lower(%s)
                   UNION ALL SELECT 1 FROM product_variants WHERE workspace_id=%s AND lower(sku)=lower(%s) LIMIT 1""",
                (workspace_id, sku.strip(), workspace_id, sku.strip()),
            ).fetchone()
            if collision:
                raise ProductConflictError(SKU_TAKEN)
            conn.execute(
                """INSERT INTO products(product_id,workspace_id,sku,name,description,category,status,
                   created_by,created_at,updated_at) VALUES(%s,%s,%s,%s,%s,%s,'ACTIVE',%s,%s,%s)""",
                (product_id, workspace_id, sku.strip().upper(), name.strip(), description,
                 category.strip(), actor_id, now, now),
            )
            conn.cursor().executemany(
                "INSERT INTO product_assets(product_id,asset_id,sort_order,role) VALUES(%s,%s,%s,%s)",
                [(product_id, asset_id, index, "primary" if index == 0 else "gallery")
                 for index, asset_id in enumerate(image_asset_ids)],
            )
            conn.execute(
                """INSERT INTO product_events(event_id,product_id,workspace_id,actor_id,event_type,details,created_at)
                   VALUES(%s,%s,%s,%s,'product.created',%s,%s)""",
                ("pev_" + uuid.uuid4().hex, product_id, workspace_id, actor_id,
                 self._jsonb({"sku": sku.strip().upper()}), now),
            )
            row = conn.execute("SELECT * FROM products WHERE product_id=%s", (product_id,)).fetchone()
            if row is None:
                raise RuntimeError("Product insert completed but row could not be read")
            return self._read(conn, row)

    @staticmethod
    def _validate_variant(*, sku: str, option_values: dict[str, str], image_asset_ids: list[str]) -> None:
        import re
        if not isinstance(sku, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{1,63}", sku.strip()):
            raise ValueError("Variant SKU must be 2 to 64 valid characters")
        if not isinstance(option_values, dict) or not 1 <= len(option_values) <= 12:
            raise ValueError("Variant requires 1 to 12 option values")
        normalized = set()
        for key, value in option_values.items():
            name = key.strip().lower() if isinstance(key, str) else ""
            if not name or len(name) > 40 or not name.replace("_", "").isalnum():
                raise ValueError("Variant option names must be short alphanumeric identifiers")
            if name in normalized:
                raise ValueError("Variant option names must be unique after normalization")
            normalized.add(name)
            if not isinstance(value, str) or not value.strip() or len(value.strip()) > 80:
                raise ValueError("Variant option values must be non-empty strings up to 80 characters")
        if (not isinstance(image_asset_ids, list) or len(image_asset_ids) > 12
                or len(image_asset_ids) != len(set(image_asset_ids))
                or any(not isinstance(value, str) or not value.strip() or len(value) > 80 for value in image_asset_ids)):
            raise ValueError("Variant image asset IDs must be unique; maximum 12")

    def create_variant(self, *, product_id: str, workspace_id: str, actor_id: str, sku: str,
                       option_values: dict[str, str], image_asset_ids: list[str] | None = None) -> dict[str, Any]:
        image_asset_ids = image_asset_ids or []
        self._validate_variant(sku=sku, option_values=option_values, image_asset_ids=image_asset_ids)
        now = self._now()
        variant_id = "pvr_" + uuid.uuid4().hex
        with connect() as conn:
            self._require(conn, workspace_id, actor_id, write=True)
            parent = conn.execute(
                "SELECT status FROM products WHERE product_id=%s AND workspace_id=%s FOR UPDATE",
                (product_id, workspace_id),
            ).fetchone()
            if parent is None or parent["status"] != "ACTIVE":
                raise KeyError(product_id)
            collision = conn.execute(
                """SELECT 1 FROM products WHERE workspace_id=%s AND lower(sku)=lower(%s)
                   UNION ALL SELECT 1 FROM product_variants WHERE workspace_id=%s AND lower(sku)=lower(%s) LIMIT 1""",
                (workspace_id, sku.strip(), workspace_id, sku.strip()),
            ).fetchone()
            if collision:
                raise ProductConflictError(SKU_TAKEN)
            if image_asset_ids:
                found = conn.execute(
                    """SELECT asset_id FROM assets WHERE workspace_id=%s AND deleted_at IS NULL
                       AND media_type LIKE 'image/%%' AND asset_id=ANY(%s)
                       ORDER BY asset_id FOR SHARE""",
                    (workspace_id, image_asset_ids),
                ).fetchall()
                if len(found) != len(image_asset_ids):
                    raise DetailedValueError(IMAGE_DETAIL)
            conn.execute(
                """INSERT INTO product_variants(variant_id,product_id,workspace_id,sku,option_values,status,
                   created_by,created_at,updated_at) VALUES(%s,%s,%s,%s,%s,'ACTIVE',%s,%s,%s)""",
                (variant_id, product_id, workspace_id, sku.strip().upper(), self._jsonb(option_values), actor_id, now, now),
            )
            conn.cursor().executemany(
                "INSERT INTO product_variant_assets(variant_id,asset_id,sort_order) VALUES(%s,%s,%s)",
                [(variant_id, asset_id, index) for index, asset_id in enumerate(image_asset_ids)],
            )
            conn.execute(
                """INSERT INTO product_events(event_id,product_id,workspace_id,actor_id,event_type,details,created_at)
                   VALUES(%s,%s,%s,%s,'product.variant_created',%s,%s)""",
                ("pev_" + uuid.uuid4().hex, product_id, workspace_id, actor_id,
                 self._jsonb({"variant_id": variant_id, "sku": sku.strip().upper()}), now),
            )
            row = conn.execute("SELECT * FROM product_variants WHERE variant_id=%s", (variant_id,)).fetchone()
            value = dict(row)
            assets = conn.execute(
                "SELECT asset_id FROM product_variant_assets WHERE variant_id=%s ORDER BY sort_order,asset_id",
                (variant_id,),
            ).fetchall()
            value["image_asset_ids"] = [str(item["asset_id"]) for item in assets]
            value["status"] = "active"
            return value

    def update_variant(self, product_id: str, variant_id: str, workspace_id: str, actor_id: str,
                       *, sku: str, option_values: dict[str, str],
                       image_asset_ids: list[str] | None = None) -> dict[str, Any]:
        image_asset_ids = image_asset_ids or []
        self._validate_variant(sku=sku, option_values=option_values, image_asset_ids=image_asset_ids)
        now = self._now()
        with connect() as conn:
            self._require(conn, workspace_id, actor_id, write=True)
            parent = conn.execute(
                "SELECT 1 FROM products WHERE product_id=%s AND workspace_id=%s AND status='ACTIVE' FOR UPDATE",
                (product_id, workspace_id),
            ).fetchone()
            if parent is None:
                raise KeyError(product_id)
            current = conn.execute(
                "SELECT 1 FROM product_variants WHERE variant_id=%s AND product_id=%s AND workspace_id=%s AND status='ACTIVE' FOR UPDATE",
                (variant_id, product_id, workspace_id),
            ).fetchone()
            if current is None:
                raise KeyError(variant_id)
            collision = conn.execute(
                """SELECT 1 FROM products WHERE workspace_id=%s AND lower(sku)=lower(%s)
                   UNION ALL SELECT 1 FROM product_variants WHERE workspace_id=%s AND lower(sku)=lower(%s)
                     AND variant_id<>%s LIMIT 1""",
                (workspace_id, sku.strip(), workspace_id, sku.strip(), variant_id),
            ).fetchone()
            if collision:
                raise ProductConflictError(SKU_TAKEN)
            if image_asset_ids:
                found = conn.execute(
                    """SELECT asset_id FROM assets WHERE workspace_id=%s AND deleted_at IS NULL
                       AND media_type LIKE 'image/%%' AND asset_id=ANY(%s)
                       ORDER BY asset_id FOR SHARE""",
                    (workspace_id, image_asset_ids),
                ).fetchall()
                if len(found) != len(image_asset_ids):
                    raise DetailedValueError(IMAGE_DETAIL)
            conn.execute(
                """UPDATE product_variants SET sku=%s,option_values=%s,updated_at=%s
                   WHERE variant_id=%s""",
                (sku.strip().upper(), self._jsonb(option_values), now, variant_id),
            )
            conn.execute("DELETE FROM product_variant_assets WHERE variant_id=%s", (variant_id,))
            conn.cursor().executemany(
                "INSERT INTO product_variant_assets(variant_id,asset_id,sort_order) VALUES(%s,%s,%s)",
                [(variant_id, asset_id, index) for index, asset_id in enumerate(image_asset_ids)],
            )
            conn.execute(
                """INSERT INTO product_events(event_id,product_id,workspace_id,actor_id,event_type,details,created_at)
                   VALUES(%s,%s,%s,%s,'product.variant_updated',%s,%s)""",
                ("pev_" + uuid.uuid4().hex, product_id, workspace_id, actor_id,
                 self._jsonb({"variant_id": variant_id, "sku": sku.strip().upper()}), now),
            )
            row = conn.execute("SELECT * FROM product_variants WHERE variant_id=%s", (variant_id,)).fetchone()
            value = dict(row)
            assets = conn.execute(
                "SELECT asset_id FROM product_variant_assets WHERE variant_id=%s ORDER BY sort_order,asset_id",
                (variant_id,),
            ).fetchall()
            value["image_asset_ids"] = [str(item["asset_id"]) for item in assets]
            value["status"] = "active"
            return value

    def list_variants(self, product_id: str, workspace_id: str, actor_id: str,
                      *, include_archived: bool = False) -> list[dict[str, Any]]:
        with connect() as conn:
            self._require(conn, workspace_id, actor_id)
            parent = conn.execute(
                "SELECT 1 FROM products WHERE product_id=%s AND workspace_id=%s AND status='ACTIVE'",
                (product_id, workspace_id),
            ).fetchone()
            if parent is None:
                raise KeyError(product_id)
            status_filter = "" if include_archived else " AND status='ACTIVE'"
            rows = conn.execute(
                "SELECT * FROM product_variants WHERE product_id=%s AND workspace_id=%s" + status_filter + " ORDER BY created_at,variant_id",
                (product_id, workspace_id),
            ).fetchall()
            result = []
            for row in rows:
                value = dict(row)
                assets = conn.execute(
                    "SELECT asset_id FROM product_variant_assets WHERE variant_id=%s ORDER BY sort_order,asset_id",
                    (value["variant_id"],),
                ).fetchall()
                value["image_asset_ids"] = [str(item["asset_id"]) for item in assets]
                value["status"] = "archived" if value.get("archived_at") else str(value["status"]).lower()
                result.append(value)
            return result

    def archive_variant(self, product_id: str, variant_id: str, workspace_id: str, actor_id: str) -> dict[str, Any]:
        now = self._now()
        with connect() as conn:
            self._require(conn, workspace_id, actor_id, write=True)
            parent = conn.execute(
                "SELECT 1 FROM products WHERE product_id=%s AND workspace_id=%s AND status='ACTIVE'",
                (product_id, workspace_id),
            ).fetchone()
            if parent is None:
                raise KeyError(product_id)
            row = conn.execute(
                """UPDATE product_variants SET status='ARCHIVED',archived_at=%s,updated_at=%s
                   WHERE variant_id=%s AND product_id=%s AND workspace_id=%s AND status='ACTIVE'
                   RETURNING variant_id,sku,option_values,status,created_by,created_at,updated_at,archived_at""",
                (now, now, variant_id, product_id, workspace_id),
            ).fetchone()
            if row is None:
                raise KeyError(variant_id)
            conn.execute(
                """INSERT INTO product_events(event_id,product_id,workspace_id,actor_id,event_type,details,created_at)
                   VALUES(%s,%s,%s,%s,'product.variant_archived',%s,%s)""",
                ("pev_" + uuid.uuid4().hex, product_id, workspace_id, actor_id,
                 self._jsonb({"variant_id": variant_id}), now),
            )
            value = dict(row)
            assets = conn.execute(
                "SELECT asset_id FROM product_variant_assets WHERE variant_id=%s ORDER BY sort_order,asset_id",
                (variant_id,),
            ).fetchall()
            value["image_asset_ids"] = [str(item["asset_id"]) for item in assets]
            value["status"] = "archived"
            return value

    @staticmethod
    def _jsonb(value: dict[str, Any]):
        try:
            from psycopg.types.json import Jsonb
            return Jsonb(value)
        except ImportError as exc:
            raise RuntimeError("psycopg 3 is required for PostgreSQL Product repository") from exc

    def list_for_workspace(self, workspace_id: str, actor_id: str, *, include_archived: bool = False,
                           limit: int = 50, offset: int = 0) -> dict[str, Any]:
        if not 1 <= limit <= 100 or offset < 0:
            raise ValueError("Product pagination is outside the allowed range")
        with connect() as conn:
            self._require(conn, workspace_id, actor_id)
            where = "workspace_id=%s" + ("" if include_archived else " AND status='ACTIVE'")
            total = conn.execute(f"SELECT count(*) AS n FROM products WHERE {where}", (workspace_id,)).fetchone()["n"]
            rows = conn.execute(
                f"SELECT * FROM products WHERE {where} ORDER BY updated_at DESC,product_id LIMIT %s OFFSET %s",
                (workspace_id, limit, offset),
            ).fetchall()
            return {"items": [self._read(conn, row) for row in rows],
                    "total": int(total), "limit": limit, "offset": offset}

    def get(self, product_id: str, workspace_id: str, actor_id: str) -> dict[str, Any] | None:
        with connect() as conn:
            self._require(conn, workspace_id, actor_id)
            row = conn.execute(
                "SELECT * FROM products WHERE product_id=%s AND workspace_id=%s",
                (product_id, workspace_id),
            ).fetchone()
            return self._read(conn, row) if row else None

    # -- lifecycle methods that previously existed only in the SQLite implementation -----------------

    @staticmethod
    def _active_lookbook_reference(conn: Any, product_id: str, workspace_id: str) -> bool:
        if conn.execute("SELECT to_regclass('public.lookbook_draft_entities') AS t").fetchone()["t"] is None:
            return False
        return conn.execute(
            """SELECT 1 FROM lookbook_draft_entities e JOIN lookbook_drafts d ON d.draft_id=e.draft_id
               WHERE e.entity_type='product' AND e.entity_id=%s AND d.workspace_id=%s
                 AND d.archived_at IS NULL LIMIT 1""",
            (product_id, workspace_id)).fetchone() is not None

    def update(self, product_id: str, workspace_id: str, actor_id: str, *, sku: str, name: str,
               description: str | None, category: str, image_asset_ids: list[str]) -> dict[str, Any]:
        self._validate(sku=sku, name=name, description=description, category=category,
                      image_asset_ids=image_asset_ids)
        now = self._now()
        sku_value = sku.strip().upper()
        with connect() as conn:
            self._require(conn, workspace_id, actor_id, write=True)
            row = conn.execute(
                "SELECT 1 FROM products WHERE product_id=%s AND workspace_id=%s AND status='ACTIVE' FOR UPDATE",
                (product_id, workspace_id)).fetchone()
            if row is None:
                raise LookupError("Product not found")
            if self._active_lookbook_reference(conn, product_id, workspace_id):
                raise ProductConflictError(
                    "Product is referenced by an active Lookbook Draft; archive the draft before editing the Product")
            found = conn.execute(
                """SELECT asset_id FROM assets WHERE workspace_id=%s AND deleted_at IS NULL
                   AND media_type LIKE 'image/%%' AND asset_id = ANY(%s)
                   ORDER BY asset_id FOR SHARE""",
                (workspace_id, image_asset_ids)).fetchall()
            if len(found) != len(image_asset_ids):
                raise DetailedValueError(IMAGE_DETAIL)
            collision = conn.execute(
                """SELECT 1 FROM products WHERE workspace_id=%s AND lower(sku)=lower(%s) AND product_id<>%s
                   UNION ALL SELECT 1 FROM product_variants WHERE workspace_id=%s AND lower(sku)=lower(%s) LIMIT 1""",
                (workspace_id, sku_value, product_id, workspace_id, sku_value)).fetchone()
            if collision:
                raise ProductConflictError(SKU_TAKEN)
            conn.execute(
                """UPDATE products SET sku=%s,name=%s,description=%s,category=%s,updated_at=%s
                   WHERE product_id=%s AND workspace_id=%s""",
                (sku_value, name.strip(), description, category.strip(), now, product_id, workspace_id))
            conn.execute("DELETE FROM product_assets WHERE product_id=%s", (product_id,))
            conn.cursor().executemany(
                "INSERT INTO product_assets(product_id,asset_id,sort_order,role) VALUES(%s,%s,%s,%s)",
                [(product_id, asset_id, index, "primary" if index == 0 else "gallery")
                 for index, asset_id in enumerate(image_asset_ids)])
            conn.execute(
                """INSERT INTO product_events(event_id,product_id,workspace_id,actor_id,event_type,details,created_at)
                   VALUES(%s,%s,%s,%s,'product.updated',%s,%s)""",
                ("pev_" + uuid.uuid4().hex, product_id, workspace_id, actor_id, self._jsonb({"sku": sku_value}), now))
            return self._read(conn, conn.execute("SELECT * FROM products WHERE product_id=%s", (product_id,)).fetchone())

    def archive(self, product_id: str, workspace_id: str, actor_id: str) -> dict[str, Any]:
        now = self._now()
        with connect() as conn:
            self._require(conn, workspace_id, actor_id, write=True)
            row = conn.execute(
                "SELECT 1 FROM products WHERE product_id=%s AND workspace_id=%s AND status='ACTIVE' FOR UPDATE",
                (product_id, workspace_id)).fetchone()
            if row is None:
                raise LookupError("Product not found")
            if self._active_lookbook_reference(conn, product_id, workspace_id):
                raise ProductConflictError("Product is referenced by an active Lookbook Draft; archive the draft first")
            assigned = conn.execute(
                """SELECT 1 FROM project_product_assignments a JOIN projects p ON p.project_id=a.project_id
                   WHERE a.product_id=%s AND a.removed_at IS NULL AND p.status='ACTIVE' LIMIT 1""",
                (product_id,)).fetchone()
            if assigned:
                raise ProductConflictError("Product is assigned to an active Project; remove the assignment first")
            conn.execute(
                """UPDATE product_variants SET status='ARCHIVED',archived_at=%s,updated_at=%s
                   WHERE product_id=%s AND status='ACTIVE'""", (now, now, product_id))
            conn.execute(
                "UPDATE products SET status='ARCHIVED',archived_at=%s,updated_at=%s WHERE product_id=%s",
                (now, now, product_id))
            conn.execute(
                """INSERT INTO product_events(event_id,product_id,workspace_id,actor_id,event_type,details,created_at)
                   VALUES(%s,%s,%s,%s,'product.archived',%s,%s)""",
                ("pev_" + uuid.uuid4().hex, product_id, workspace_id, actor_id, self._jsonb({}), now))
            return self._read(conn, conn.execute("SELECT * FROM products WHERE product_id=%s", (product_id,)).fetchone())

    def list_events(self, product_id: str, workspace_id: str, actor_id: str, *,
                    limit: int = 100, offset: int = 0) -> dict[str, Any]:
        if not 1 <= limit <= 500 or offset < 0:
            raise ValueError("Event pagination is outside the allowed range")
        with connect() as conn:
            self._require(conn, workspace_id, actor_id)
            if conn.execute("SELECT 1 FROM products WHERE product_id=%s AND workspace_id=%s",
                            (product_id, workspace_id)).fetchone() is None:
                raise LookupError("Product not found")
            total = conn.execute(
                "SELECT count(*) AS n FROM product_events WHERE product_id=%s AND workspace_id=%s",
                (product_id, workspace_id)).fetchone()["n"]
            rows = conn.execute(
                """SELECT event_id,product_id,actor_id,event_type,details,created_at FROM product_events
                   WHERE product_id=%s AND workspace_id=%s ORDER BY created_at DESC,event_id DESC LIMIT %s OFFSET %s""",
                (product_id, workspace_id, limit, offset)).fetchall()
            return {"items": [dict(r) for r in rows], "total": int(total), "limit": limit, "offset": offset}
