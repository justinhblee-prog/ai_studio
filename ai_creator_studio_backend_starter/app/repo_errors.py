"""Shared repository error taxonomy and HTTP mapping.

Repositories raise these (or standard exceptions with the same meaning); route
adapters translate them with ``map_exception`` so every aggregate answers the
same way regardless of backend. Database driver messages are never echoed.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class NotAMemberError(PermissionError):
    """Actor is not a member of the workspace (HTTP 404: do not reveal existence)."""


class InsufficientRoleError(PermissionError):
    """Actor is a member but the workspace role is too low (HTTP 403)."""


class RepositoryConflictError(RuntimeError):
    """Operation conflicts with current state (HTTP 409)."""


class DetailedValueError(ValueError):
    """Validation failure (HTTP 422) whose public ``detail`` is structured (legacy ``{code, message}`` bodies)."""

    def __init__(self, detail: dict[str, Any]):
        super().__init__(str(detail.get("message", "")))
        self.detail = detail


class BackendNotReadyError(RuntimeError):
    """Selected storage backend cannot serve the runtime (fail closed; never fall back)."""


@dataclass(frozen=True)
class MappedError:
    status: int
    code: str
    detail: Any


# SQLSTATE classes/codes from PostgreSQL that the application can explain safely.
_SQLSTATE = {
    "23505": MappedError(409, "UNIQUE_VIOLATION", "A record with the same unique value already exists"),
    "23503": MappedError(409, "REFERENCE_VIOLATION", "The record is referenced by, or refers to, a missing record"),
    "23514": MappedError(422, "CHECK_VIOLATION", "A value violates a data constraint"),
    "23502": MappedError(422, "REQUIRED_VALUE_MISSING", "A required value is missing"),
    "P0001": MappedError(422, "INTEGRITY_GUARD", "The request violates a data integrity rule"),
}


def _sqlstate(exc: BaseException) -> str | None:
    value = getattr(exc, "sqlstate", None)
    return value if isinstance(value, str) else None


def map_exception(exc: BaseException) -> MappedError:
    """Translate a repository exception into (status, code, detail). Unknown errors -> 500, generic."""
    if isinstance(exc, NotAMemberError):
        return MappedError(404, "NOT_FOUND", "Workspace not found")
    if isinstance(exc, InsufficientRoleError):
        return MappedError(403, "INSUFFICIENT_ROLE", "Insufficient workspace role")
    if isinstance(exc, PermissionError):
        # Legacy repositories use one PermissionError for both cases; routes pre-check membership.
        return MappedError(403, "FORBIDDEN", "Insufficient workspace role")
    if isinstance(exc, BackendNotReadyError):
        return MappedError(503, "BACKEND_NOT_READY", "Storage backend is not ready")
    if isinstance(exc, RepositoryConflictError):
        return MappedError(409, "CONFLICT", str(exc) or "Request conflicts with the current state")
    if isinstance(exc, KeyError):
        return MappedError(404, "NOT_FOUND", "Resource not found")
    if isinstance(exc, LookupError):  # repositories word these messages for end users ("Character not found")
        return MappedError(404, "NOT_FOUND", str(exc) or "Resource not found")
    state = _sqlstate(exc)
    if state in _SQLSTATE:
        return _SQLSTATE[state]
    if type(exc).__name__ == "AssetVersionIntegrityError":  # legacy: stored bytes no longer match their metadata
        return MappedError(409, "ASSET_VERSION_INTEGRITY_FAILED",
                           {"code": "ASSET_VERSION_INTEGRITY_FAILED", "message": str(exc)})
    if isinstance(exc, DetailedValueError):
        return MappedError(422, str(exc.detail.get("code", "VALIDATION_FAILED")), exc.detail)
    if isinstance(exc, ValueError):
        return MappedError(422, "VALIDATION_FAILED", str(exc) or "Request validation failed")
    # Conflict-style runtime errors defined next to their repositories (single source below).
    if type(exc).__name__ in _CONFLICT_NAMES:
        return MappedError(409, "CONFLICT", str(exc) or "Request conflicts with the current state")
    return MappedError(500, "INTERNAL_ERROR", "Internal server error")


# Names kept for repositories that predate this module and subclass RuntimeError directly.
_CONFLICT_NAMES = frozenset({"CharacterConflictError", "LookbookStateError", "PhotoSourceVersionError"})


def to_http_exception(exc: BaseException):
    """Build a FastAPI HTTPException (imported lazily so repositories stay framework-free)."""
    from fastapi import HTTPException
    mapped = map_exception(exc)
    return HTTPException(status_code=mapped.status, detail={"code": mapped.code, "message": mapped.detail})


def raise_http(exc: BaseException):
    """Route-side translation preserving the legacy ``detail: str`` response shape.

    HTTPException passes through untouched. Unknown errors (HTTP 500) are re-raised
    as-is so real defects stay visible instead of being disguised as client errors.
    """
    from fastapi import HTTPException
    if isinstance(exc, HTTPException):
        raise exc
    mapped = map_exception(exc)
    if mapped.status == 500:
        raise exc
    raise HTTPException(status_code=mapped.status, detail=mapped.detail) from exc
