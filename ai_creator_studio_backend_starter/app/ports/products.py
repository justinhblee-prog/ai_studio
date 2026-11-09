"""Product catalog port: SQLite (current behaviour) and PostgreSQL adapter.

Every operation authorises first (404 for non-members, 403 for low roles), then looks the
Product up, so a non-member can no longer distinguish "missing product" from "no access".
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from types import SimpleNamespace
from typing import Any, Protocol

from app.ports.workspace import WorkspacePort, get_workspace_port, require_role
from app.repository_registry import require_runtime_backend
from app.repositories.postgres_products import SKU_TAKEN, ProductConflictError as ProductConflict

PRODUCT_NOT_FOUND = "Product not found"
VARIANT_NOT_FOUND = "Product or variant not found"


class ProductPort(Protocol):
    def create(self, user_id: str, fields: dict[str, Any]) -> dict[str, Any]: ...
    def list(self, workspace_id: str, user_id: str, include_archived: bool, limit: int, offset: int) -> dict[str, Any]: ...
    def get(self, workspace_id: str, product_id: str, user_id: str) -> dict[str, Any]: ...
    def update(self, product_id: str, user_id: str, fields: dict[str, Any]) -> dict[str, Any]: ...
    def archive(self, workspace_id: str, product_id: str, user_id: str) -> dict[str, Any]: ...
    def events(self, workspace_id: str, product_id: str, user_id: str, limit: int, offset: int) -> dict[str, Any]: ...
    def create_variant(self, product_id: str, user_id: str, fields: dict[str, Any]) -> dict[str, Any]: ...
    def list_variants(self, workspace_id: str, product_id: str, user_id: str, include_archived: bool) -> dict[str, Any]: ...
    def update_variant(self, product_id: str, variant_id: str, user_id: str, fields: dict[str, Any]) -> dict[str, Any]: ...
    def archive_variant(self, workspace_id: str, product_id: str, variant_id: str, user_id: str) -> dict[str, Any]: ...


class SQLiteProductPort:
    def __init__(self, workspaces: WorkspacePort | None = None):
        self._workspaces = workspaces or get_workspace_port()

    def _role(self, workspace_id: str, user_id: str, write: bool = False) -> None:
        require_role(self._workspaces, workspace_id, user_id, write=write)

    @staticmethod
    def _missing(message: str):
        return LookupError(message)

    def create(self, user_id, fields):
        from app import products
        self._role(fields["workspace_id"], user_id, True)
        try:
            return products.create_product(SimpleNamespace(**fields), user_id)
        except sqlite3.IntegrityError as exc:
            raise ProductConflict(SKU_TAKEN) from exc

    def list(self, workspace_id, user_id, include_archived, limit, offset):
        from app import products
        self._role(workspace_id, user_id)
        return products.list_products(workspace_id, include_archived=include_archived, limit=limit, offset=offset)

    def get(self, workspace_id, product_id, user_id):
        from app import products
        self._role(workspace_id, user_id)
        value = products.get_product(product_id, workspace_id)
        if not value:
            raise self._missing(PRODUCT_NOT_FOUND)
        return value

    def update(self, product_id, user_id, fields):
        from app import products
        self._role(fields["workspace_id"], user_id, True)
        try:
            return products.update_product(product_id, SimpleNamespace(**fields), user_id)
        except LookupError as exc:
            raise self._missing(PRODUCT_NOT_FOUND) from exc
        except sqlite3.IntegrityError as exc:
            raise ProductConflict(SKU_TAKEN) from exc

    def archive(self, workspace_id, product_id, user_id):
        from app import products
        self._role(workspace_id, user_id, True)
        try:
            return products.archive_product(product_id, workspace_id, user_id)
        except LookupError as exc:
            raise self._missing(PRODUCT_NOT_FOUND) from exc

    def events(self, workspace_id, product_id, user_id, limit, offset):
        from app import products
        self._role(workspace_id, user_id)
        if not products.get_product(product_id, workspace_id):
            raise self._missing(PRODUCT_NOT_FOUND)
        return products.list_events(product_id, workspace_id, limit=limit, offset=offset)

    def create_variant(self, product_id, user_id, fields):
        from app import products
        self._role(fields["workspace_id"], user_id, True)
        try:
            return products.create_variant(product_id, SimpleNamespace(**fields), user_id)
        except LookupError as exc:
            raise self._missing(PRODUCT_NOT_FOUND) from exc

    def list_variants(self, workspace_id, product_id, user_id, include_archived):
        from app import products
        self._role(workspace_id, user_id)
        try:
            return {"items": products.list_variants(product_id, workspace_id, include_archived)}
        except LookupError as exc:
            raise self._missing(PRODUCT_NOT_FOUND) from exc

    def update_variant(self, product_id, variant_id, user_id, fields):
        from app import products
        self._role(fields["workspace_id"], user_id, True)
        try:
            return products.update_variant(product_id, variant_id, SimpleNamespace(**fields), user_id)
        except LookupError as exc:
            raise self._missing(VARIANT_NOT_FOUND) from exc

    def archive_variant(self, workspace_id, product_id, variant_id, user_id):
        from app import products
        self._role(workspace_id, user_id, True)
        try:
            return products.archive_variant(product_id, variant_id, workspace_id, user_id)
        except LookupError as exc:
            raise self._missing(VARIANT_NOT_FOUND) from exc


def _plain(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_plain(v) for v in value]
    return value


class PostgreSQLProductPort:
    def __init__(self, repository=None):
        if repository is None:
            from app.repository_registry import build_postgres_repository
            repository = build_postgres_repository("products")
        self._repo = repository

    @staticmethod
    def _translate(exc: KeyError, message: str) -> LookupError:
        return LookupError(message)

    def create(self, user_id, fields):
        return _plain(self._repo.create(workspace_id=fields["workspace_id"], actor_id=user_id, sku=fields["sku"],
                                        name=fields["name"], description=fields.get("description"),
                                        category=fields["category"], image_asset_ids=fields["image_asset_ids"]))

    def list(self, workspace_id, user_id, include_archived, limit, offset):
        return _plain(self._repo.list_for_workspace(workspace_id, user_id, include_archived=include_archived,
                                                    limit=limit, offset=offset))

    def get(self, workspace_id, product_id, user_id):
        value = self._repo.get(product_id, workspace_id, user_id)
        if value is None:
            raise LookupError(PRODUCT_NOT_FOUND)
        return _plain(value)

    def update(self, product_id, user_id, fields):
        return _plain(self._repo.update(product_id, fields["workspace_id"], user_id, sku=fields["sku"],
                                        name=fields["name"], description=fields.get("description"),
                                        category=fields["category"], image_asset_ids=fields["image_asset_ids"]))

    def archive(self, workspace_id, product_id, user_id):
        return _plain(self._repo.archive(product_id, workspace_id, user_id))

    def events(self, workspace_id, product_id, user_id, limit, offset):
        return _plain(self._repo.list_events(product_id, workspace_id, user_id, limit=limit, offset=offset))

    def create_variant(self, product_id, user_id, fields):
        try:
            return _plain(self._repo.create_variant(product_id=product_id, workspace_id=fields["workspace_id"],
                                                    actor_id=user_id, sku=fields["sku"],
                                                    option_values=fields["option_values"],
                                                    image_asset_ids=fields.get("image_asset_ids")))
        except KeyError as exc:
            raise LookupError(PRODUCT_NOT_FOUND) from exc

    def list_variants(self, workspace_id, product_id, user_id, include_archived):
        try:
            return {"items": _plain(self._repo.list_variants(product_id, workspace_id, user_id,
                                                             include_archived=include_archived))}
        except KeyError as exc:
            raise LookupError(PRODUCT_NOT_FOUND) from exc

    def update_variant(self, product_id, variant_id, user_id, fields):
        try:
            return _plain(self._repo.update_variant(product_id, variant_id, fields["workspace_id"], user_id,
                                                    sku=fields["sku"], option_values=fields["option_values"],
                                                    image_asset_ids=fields.get("image_asset_ids")))
        except KeyError as exc:
            raise LookupError(VARIANT_NOT_FOUND) from exc

    def archive_variant(self, workspace_id, product_id, variant_id, user_id):
        try:
            return _plain(self._repo.archive_variant(product_id, variant_id, workspace_id, user_id))
        except KeyError as exc:
            raise LookupError(VARIANT_NOT_FOUND) from exc


def get_product_port() -> ProductPort:
    return SQLiteProductPort() if require_runtime_backend() == "sqlite" else PostgreSQLProductPort()
