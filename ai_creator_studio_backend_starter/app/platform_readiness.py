"""Read-only deployment and integration readiness report.

This module deliberately reports capability gaps without probing networks,
reading secret values, creating database objects, or mutating external services.
It is a preflight inventory, not evidence that a live integration works.
"""
from __future__ import annotations

from typing import Any

from app import config


def build_platform_readiness() -> dict[str, Any]:
    backend = str(getattr(config, "DATABASE_BACKEND", "sqlite")).strip().lower()
    provider = str(getattr(config, "PROVIDER_MODE", "mock")).strip().lower()
    database_url_configured = bool(str(getattr(config, "DATABASE_URL", "")).strip())
    fashn_key_configured = bool(str(getattr(config, "FASHN_API_KEY", "")).strip())

    database_supported = backend == "sqlite"
    database_detail = (
        "SQLite aggregate repositories are implemented."
        if database_supported
        else "PostgreSQL runtime adapters are not implemented across all aggregates; startup must fail closed."
        if backend == "postgresql"
        else "Unsupported database backend."
    )

    checks = [
        {
            "id": "database_runtime",
            "status": "supported" if database_supported else "blocked",
            "selected_backend": backend,
            "detail": database_detail,
        },
        {
            "id": "postgresql_repository_coverage",
            "status": "blocked",
            "implemented_aggregates": [],
            "pending_aggregates": [
                "workspace_and_asset_metadata", "generation_job_and_execution", "job_event_and_lifecycle",
                "outbox_submission", "provider_poll", "output_and_asset_link", "output_review_and_export",
                "worker_heartbeat_and_health", "operations_alerts_and_delivery", "credits_ledger",
            ],
            "detail": "No complete PostgreSQL aggregate adapter is enabled; SQLite implementations remain the only supported runtime.",
        },
        {
            "id": "supabase_postgresql",
            "status": "blocked",
            "detail": "Supabase test project exists, but application PostgreSQL repositories, migration runner, and live transaction tests are not complete.",
        },
        {
            "id": "supabase_storage",
            "status": "blocked",
            "detail": "Private buckets are provisioned, but the application still uses local filesystem storage; upload/download authorization is not integrated.",
        },
        {
            "id": "worker_runtime",
            "status": "partial",
            "detail": "Worker entry points exist, but a separately deployed durable worker topology and live lease/claim integration are not verified.",
        },
        {
            "id": "ai_provider",
            "status": "partial" if provider == "mock" or (provider == "fashn" and fashn_key_configured) else "blocked",
            "selected_provider": provider,
            "provider_secret_configured": fashn_key_configured,
            "detail": "Mock mode verifies workflow only; no real generation is claimed." if provider == "mock" else "Provider configuration is present; real paid generation still requires an explicitly approved live test." if fashn_key_configured else "Selected real provider has no configured credential.",
        },
        {
            "id": "vercel_preview",
            "status": "not_verified",
            "detail": "The existing Vercel deployment is a bootstrap smoke-test response, not the complete application. A source-backed Preview deployment is still required.",
        },
    ]

    blockers = [item["id"] for item in checks if item["status"] in {"blocked", "not_verified"}]
    return {
        "report_version": "1.0",
        "scope": "read-only-preflight",
        "overall_status": "blocked" if blockers else "partial",
        "database_url_configured": database_url_configured,
        "checks": checks,
        "blockers": blockers,
        "disclaimer": "Preflight inventory only; it does not perform or certify live integration tests.",
    }
