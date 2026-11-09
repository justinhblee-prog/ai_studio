"""Fail-closed catalogue of PostgreSQL repository coverage and backend selection.

This module does not connect to anything and is not wired into API routes yet.
It records, per aggregate, how far the PostgreSQL implementation has been
proven, and refuses to select ``postgresql`` for the runtime until every
required aggregate is ``live_verified``. It never falls back to SQLite.

Statuses
  live_verified  repository exercised by tests/test_postgres_live_repositories.py against real PostgreSQL
  unverified     repository code exists but has no live PostgreSQL test
  partial        live tests cover only part of the repository surface
  missing        no PostgreSQL repository
"""
from __future__ import annotations

import importlib
from dataclasses import dataclass

from app import config
from app.repo_errors import BackendNotReadyError

LIVE_VERIFIED, UNVERIFIED, PARTIAL, MISSING = "live_verified", "unverified", "partial", "missing"


@dataclass(frozen=True)
class Aggregate:
    name: str
    status: str
    module: str | None = None
    cls: str | None = None


# Update a status only together with the live test that justifies it.
AGGREGATES: tuple[Aggregate, ...] = (
    Aggregate("workspace_and_asset_metadata", PARTIAL, "app.repositories.postgres_assets", "PostgreSQLAssetMetadataRepository"),
    Aggregate("projects", LIVE_VERIFIED, "app.repositories.postgres_projects", "PostgreSQLProjectRepository"),
    Aggregate("products", LIVE_VERIFIED, "app.repositories.postgres_products", "PostgreSQLProductRepository"),
    Aggregate("project_products", LIVE_VERIFIED, "app.repositories.postgres_project_products", "PostgreSQLProjectProductRepository"),
    Aggregate("characters", LIVE_VERIFIED, "app.repositories.postgres_characters", "PostgreSQLCharacterRepository"),
    Aggregate("photos", LIVE_VERIFIED, "app.repositories.postgres_photos", "PostgreSQLPhotoRepository"),
    Aggregate("lookbooks", LIVE_VERIFIED, "app.repositories.postgres_lookbooks", "PostgreSQLLookbookRepository"),
    Aggregate("generation_jobs", UNVERIFIED, "app.repositories.postgres_job", "PostgreSQLJobRepository"),
    Aggregate("job_outbox", UNVERIFIED, "app.repositories.postgres_outbox", "PostgreSQLOutboxRepository"),
    Aggregate("provider_poll", UNVERIFIED, "app.repositories.postgres_poll", "PostgreSQLPollRepository"),
    Aggregate("outputs", UNVERIFIED, "app.repositories.postgres_output", "PostgreSQLOutputRepository"),
    Aggregate("operations_and_health", UNVERIFIED, "app.repositories.postgres_operations", "PostgreSQLOperationsRepository"),
    Aggregate("credits_ledger", MISSING),
    Aggregate("file_storage_lifecycle", MISSING),
)
_BY_NAME = {a.name: a for a in AGGREGATES}
SUPPORTED_BACKENDS = ("sqlite", "postgresql")


def normalize_backend(backend: str | None = None) -> str:
    selected = (backend if backend is not None else getattr(config, "DATABASE_BACKEND", "sqlite"))
    selected = str(selected).strip().lower()
    if selected not in SUPPORTED_BACKENDS:
        raise ValueError(f"Unsupported DATABASE_BACKEND: {selected}")
    return selected


def coverage() -> dict[str, str]:
    return {a.name: a.status for a in AGGREGATES}


def pending_aggregates() -> list[str]:
    return [a.name for a in AGGREGATES if a.status != LIVE_VERIFIED]


def require_runtime_backend(backend: str | None = None) -> str:
    """Return the backend if the whole runtime can use it; raise BackendNotReadyError otherwise."""
    selected = normalize_backend(backend)
    if selected == "sqlite":
        return selected
    pending = pending_aggregates()
    if pending:
        raise BackendNotReadyError(
            "PostgreSQL is not ready for the runtime; aggregates not live-verified: " + ", ".join(pending)
            + ". Refusing to fall back to SQLite.")
    return selected


def build_postgres_repository(aggregate: str, *, allow_unverified: bool = False):
    """Instantiate one PostgreSQL repository. Only live_verified aggregates unless explicitly allowed."""
    entry = _BY_NAME.get(aggregate)
    if entry is None:
        raise KeyError(f"Unknown aggregate: {aggregate}")
    if entry.module is None or entry.status == MISSING:
        raise BackendNotReadyError(f"No PostgreSQL repository exists for aggregate: {aggregate}")
    if entry.status != LIVE_VERIFIED and not allow_unverified:
        raise BackendNotReadyError(f"PostgreSQL repository for {aggregate} is {entry.status}, not live_verified")
    return getattr(importlib.import_module(entry.module), entry.cls)()
