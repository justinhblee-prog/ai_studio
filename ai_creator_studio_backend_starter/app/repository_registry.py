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

Every live_verified aggregate lists ``evidence``: names of tests in
tests/test_postgres_live_repositories.py. tests/test_registry_evidence.py fails when a
live_verified aggregate has no evidence, when an evidence test does not exist, or when a
public repository method is not referenced by the live tests (except the explicit,
reviewed ``KNOWN_INDIRECT`` list in that test file).
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
    evidence: tuple[str, ...] = ()


# Update a status only together with the live test that justifies it.
AGGREGATES: tuple[Aggregate, ...] = (
    Aggregate("workspace_and_asset_metadata", PARTIAL, "app.repositories.postgres_assets", "PostgreSQLAssetMetadataRepository"),
    Aggregate("projects", LIVE_VERIFIED, "app.repositories.postgres_projects", "PostgreSQLProjectRepository", (
        "test_project_crud_and_role_enforcement", "test_project_port_parity_sqlite_vs_postgresql",
        "test_project_status_change_is_blocked_while_active_lookbook_references_it",
        "test_project_archive_vs_lookbook_draft_create_never_leaves_an_archived_reference")),
    Aggregate("products", LIVE_VERIFIED, "app.repositories.postgres_products", "PostgreSQLProductRepository", (
        "test_product_variant_sku_rules_and_isolation", "test_product_port_parity_sqlite_vs_postgresql",
        "test_product_update_and_archive_are_blocked_by_active_lookbook_draft",
        "test_asset_delete_vs_product_create_never_leaves_a_dangling_reference")),
    Aggregate("project_products", LIVE_VERIFIED, "app.repositories.postgres_project_products", "PostgreSQLProjectProductRepository", (
        "test_project_product_assignment_and_cross_workspace_denial",
        "test_project_product_port_parity_sqlite_vs_postgresql", "test_concurrent_project_product_replace_is_serialised")),
    Aggregate("characters", LIVE_VERIFIED, "app.repositories.postgres_characters", "PostgreSQLCharacterRepository", (
        "test_character_crud_roles_assets_and_soft_delete", "test_character_asset_trigger_blocks_cross_workspace_link",
        "test_character_port_parity_sqlite_vs_postgresql",
        "test_asset_delete_vs_character_create_never_leaves_a_dangling_reference")),
    Aggregate("photos", LIVE_VERIFIED, "app.repositories.postgres_photos", "PostgreSQLPhotoRepository", (
        "test_photo_draft_lifecycle_roles_events_and_isolation", "test_photo_run_idempotency_lease_and_append_only",
        "test_photo_concurrent_claims_have_single_winner", "test_photo_draft_port_parity_sqlite_vs_postgresql",
        "test_photo_review_export_port_parity_sqlite_vs_postgresql",
        "test_photo_process_local_port_parity_sqlite_vs_postgresql")),
    Aggregate("lookbooks", LIVE_VERIFIED, "app.repositories.postgres_lookbooks", "PostgreSQLLookbookRepository", (
        "test_lookbook_planning_workflow_roles_and_character_lock", "test_lookbook_draft_port_parity_sqlite_vs_postgresql",
        "test_lookbook_outputs_and_assembly_port_parity_sqlite_vs_postgresql",
        "test_lookbook_package_export_port_parity_sqlite_vs_postgresql",
        "test_lookbook_assembly_concurrent_attach_and_decide_are_serialised")),
    Aggregate("generation_jobs", LIVE_VERIFIED, "app.repositories.postgres_job", "PostgreSQLJobRepository", (
        "test_job_concurrent_idempotent_create_makes_one_job", "test_job_concurrent_transitions_have_one_winner",
        "test_job_cancel_vs_dispatch_completion_never_deadlocks_or_double_applies",
        "test_job_get_idempotent_returns_the_job_and_payload_hash_scoped_to_the_workspace",
        "test_job_update_applies_allowed_fields_bumps_version_and_records_an_event",
        "test_job_list_outputs_reports_recorded_outputs_and_not_queued_link_status",
        "test_job_list_pagination_is_total_ordered_and_workspace_scoped",
        "test_job_list_pagination_under_concurrent_creates_never_skips_existing_jobs",
        "test_job_execution_cursor_is_stable_while_new_attempts_arrive")),
    Aggregate("job_outbox", LIVE_VERIFIED, "app.repositories.postgres_outbox", "PostgreSQLOutboxRepository", (
        "test_outbox_dispatch_complete_vs_unknown_vs_lease_expiry_apply_once",
        "test_outbox_expired_lease_is_quarantined_and_stale_worker_cannot_complete",
        "test_outbox_completion_and_unknown_are_fenced_to_the_claiming_worker",
        "test_outbox_expired_but_unreclaimed_lease_cannot_complete_or_mark_unknown",
        "test_outbox_get_job_reads_the_job_aggregate", "test_worker_heartbeat_upserts_without_resetting_started_at")),
    Aggregate("provider_poll", LIVE_VERIFIED, "app.repositories.postgres_poll", "PostgreSQLPollRepository", (
        "test_expired_poll_lease_is_requeued_and_stale_worker_cannot_finalize",
        "test_poll_lease_renewal_extends_only_the_owner_before_expiry",
        "test_output_finalize_concurrent_duplicate_and_exhaust_apply_once")),
    Aggregate("outputs", LIVE_VERIFIED, "app.repositories.postgres_output", "PostgreSQLOutputRepository", (
        "test_output_finalize_concurrent_duplicate_and_exhaust_apply_once",
        "test_expired_poll_lease_is_requeued_and_stale_worker_cannot_finalize",
        "test_output_record_get_and_storage_key_listing")),
    Aggregate("operations_and_health", LIVE_VERIFIED, "app.repositories.postgres_operations", "PostgreSQLOperationsRepository", (
        "test_alert_delivery_claims_are_exclusive_under_contention",
        "test_alert_delivery_finish_is_fenced_by_owner_and_lease",
        "test_worker_heartbeat_upserts_without_resetting_started_at")),
    # No PostgreSQL implementation exists (build_output_asset_link_repository("postgresql") raises).
    Aggregate("output_asset_link", MISSING),
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
