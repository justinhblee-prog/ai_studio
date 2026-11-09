import importlib
from pathlib import Path

import pytest

from app import config
from app import repository_registry as reg
from app.repo_errors import (BackendNotReadyError, InsufficientRoleError, NotAMemberError,
                             RepositoryConflictError, map_exception, to_http_exception)


class _Db(Exception):
    def __init__(self, sqlstate, message="secret driver text postgresql://u:pw@host/db"):
        super().__init__(message)
        self.sqlstate = sqlstate


@pytest.mark.parametrize("exc,status,code", [
    (NotAMemberError("x"), 404, "NOT_FOUND"),
    (InsufficientRoleError("x"), 403, "INSUFFICIENT_ROLE"),
    (PermissionError("legacy"), 403, "FORBIDDEN"),
    (RepositoryConflictError("busy"), 409, "CONFLICT"),
    (BackendNotReadyError("no"), 503, "BACKEND_NOT_READY"),
    (LookupError("gone"), 404, "NOT_FOUND"),
    (KeyError("k"), 404, "NOT_FOUND"),
    (ValueError("bad title"), 422, "VALIDATION_FAILED"),
    (_Db("23505"), 409, "UNIQUE_VIOLATION"),
    (_Db("23503"), 409, "REFERENCE_VIOLATION"),
    (_Db("23514"), 422, "CHECK_VIOLATION"),
    (_Db("P0001"), 422, "INTEGRITY_GUARD"),
    (RuntimeError("boom"), 500, "INTERNAL_ERROR"),
])
def test_exception_mapping(exc, status, code):
    mapped = map_exception(exc)
    assert (mapped.status, mapped.code) == (status, code)


def test_membership_failure_maps_to_404_not_403():
    assert issubclass(NotAMemberError, PermissionError)
    assert map_exception(NotAMemberError()).status == 404
    assert map_exception(InsufficientRoleError()).status == 403


def test_database_driver_text_is_never_echoed():
    for state in ("23505", "23503", "23514", "23502", "P0001"):
        detail = map_exception(_Db(state)).detail
        assert "secret" not in detail and "postgresql://" not in detail
    assert "boom-secret" not in map_exception(RuntimeError("boom-secret")).detail


def test_repository_conflicts_are_single_sourced_and_map_to_409():
    from app.repositories.postgres_characters import CharacterConflictError
    from app.repositories.postgres_lookbooks import LookbookStateError
    from app.repositories.postgres_photos import PhotoSourceVersionError
    for cls in (CharacterConflictError, LookbookStateError, PhotoSourceVersionError):
        assert issubclass(cls, RepositoryConflictError)
        assert map_exception(cls("state")).status == 409


def test_new_repositories_distinguish_non_member_from_insufficient_role():
    from app.repositories import postgres_characters, postgres_lookbooks, postgres_photos

    class Conn:
        def __init__(self, role):
            self.role = role

        def execute(self, *_a, **_k):
            role = self.role

            class R:
                def fetchone(self):
                    return {"role": role} if role else None
            return R()

    char = postgres_characters.PostgreSQLCharacterRepository
    photo = postgres_photos.PostgreSQLPhotoRepository
    look = postgres_lookbooks.PostgreSQLLookbookRepository
    for call in (lambda c: char._require(c, "ws", "u", write=True),
                 lambda c: photo._require(c, "ws", "u", write=True),
                 lambda c: look._require(c, "ws", "u", look.WRITABLE_ROLES)):
        with pytest.raises(NotAMemberError):
            call(Conn(None))
        with pytest.raises(InsufficientRoleError):
            call(Conn("viewer"))
        call(Conn("editor"))  # allowed


def test_http_exception_payload_shape():
    http = to_http_exception(ValueError("title too long"))
    assert http.status_code == 422
    assert http.detail == {"code": "VALIDATION_FAILED", "message": "title too long"}


def test_sqlite_backend_is_selected_and_normalized(monkeypatch):
    monkeypatch.setattr(config, "DATABASE_BACKEND", " SQLite ")
    assert reg.require_runtime_backend() == "sqlite"


def test_postgresql_runtime_selection_fails_closed_listing_pending_aggregates():
    with pytest.raises(BackendNotReadyError) as err:
        reg.require_runtime_backend("postgresql")
    message = str(err.value)
    assert "Refusing to fall back to SQLite" in message
    pending = reg.pending_aggregates()
    assert {"output_asset_link", "credits_ledger", "file_storage_lifecycle", "workspace_and_asset_metadata"} == set(pending)
    assert all(name in message for name in pending)
    assert not {"characters", "photos", "lookbooks", "projects", "products", "generation_jobs", "job_outbox",
                "provider_poll", "outputs", "operations_and_health"} & set(pending)


def test_unknown_or_blank_backend_is_rejected(monkeypatch):
    with pytest.raises(ValueError):
        reg.normalize_backend("mysql")
    monkeypatch.setattr(config, "DATABASE_BACKEND", "")
    with pytest.raises(ValueError):
        reg.normalize_backend()


def test_postgresql_becomes_selectable_only_when_all_aggregates_are_live_verified(monkeypatch):
    all_ok = tuple(reg.Aggregate(a.name, reg.LIVE_VERIFIED, a.module, a.cls) for a in reg.AGGREGATES)
    monkeypatch.setattr(reg, "AGGREGATES", all_ok)
    assert reg.require_runtime_backend("postgresql") == "postgresql"
    one_bad = all_ok[:-1] + (reg.Aggregate("file_storage_lifecycle", reg.MISSING),)
    monkeypatch.setattr(reg, "AGGREGATES", one_bad)
    with pytest.raises(BackendNotReadyError):
        reg.require_runtime_backend("postgresql")


def test_build_postgres_repository_gates_by_verification_status():
    assert type(reg.build_postgres_repository("characters")).__name__ == "PostgreSQLCharacterRepository"
    with pytest.raises(BackendNotReadyError):
        reg.build_postgres_repository("workspace_and_asset_metadata")  # partial, not live_verified
    assert type(reg.build_postgres_repository("workspace_and_asset_metadata", allow_unverified=True)).__name__ == "PostgreSQLAssetMetadataRepository"
    assert type(reg.build_postgres_repository("generation_jobs")).__name__ == "PostgreSQLJobRepository"
    with pytest.raises(BackendNotReadyError):
        reg.build_postgres_repository("credits_ledger", allow_unverified=True)  # missing
    with pytest.raises(BackendNotReadyError):
        reg.build_postgres_repository("output_asset_link", allow_unverified=True)  # missing: no PostgreSQL implementation
    with pytest.raises(KeyError):
        reg.build_postgres_repository("nope")


def test_every_listed_repository_class_exists():
    for a in reg.AGGREGATES:
        if a.module:
            assert hasattr(importlib.import_module(a.module), a.cls), a.name


def test_live_verified_status_requires_a_live_test_that_names_the_repository():
    text = (Path(__file__).parent / "test_postgres_live_repositories.py").read_text(encoding="utf-8")
    for a in reg.AGGREGATES:
        if a.status == reg.LIVE_VERIFIED:
            assert a.cls in text, f"{a.name} is marked live_verified without a live test"


def test_detailed_value_error_keeps_structured_detail_and_422():
    from app.repo_errors import DetailedValueError, map_exception, to_http_exception
    detail = {"code": "PRODUCT_IMAGE_ASSET_REQUIRED", "message": "images must be active"}
    mapped = map_exception(DetailedValueError(detail))
    assert (mapped.status, mapped.code, mapped.detail) == (422, "PRODUCT_IMAGE_ASSET_REQUIRED", detail)
    assert str(DetailedValueError(detail)) == "images must be active"
    # still a ValueError, so legacy `except ValueError` callers keep working
    assert isinstance(DetailedValueError(detail), ValueError)
    assert to_http_exception(DetailedValueError(detail)).status_code == 422


def test_detailed_value_error_passes_through_raise_http_unchanged():
    import pytest
    from fastapi import HTTPException
    from app.repo_errors import DetailedValueError, raise_http
    detail = {"code": "X", "message": "m"}
    with pytest.raises(HTTPException) as caught:
        raise_http(DetailedValueError(detail))
    assert caught.value.status_code == 422 and caught.value.detail == detail


def test_sqlite_runtime_and_all_ports_import_without_psycopg():
    """SQLite-only deployments must not need psycopg: ports may only import PG modules lazily."""
    import subprocess
    import sys
    root = __import__("pathlib").Path(__file__).resolve().parents[1]
    code = (
        f"import sys; sys.path.insert(0, {str(root)!r})\n"
        "import importlib.abc\n"
        "class B(importlib.abc.MetaPathFinder):\n"
        "    def find_spec(self, name, path, target=None):\n"
        "        if name == 'psycopg' or name.startswith('psycopg.'):\n"
        "            raise ImportError('psycopg blocked')\n"
        "sys.meta_path.insert(0, B())\n"
        "import app.main\n"
        "from app.ports.workspace import SQLiteWorkspacePort\n"
        "from app.ports.products import SQLiteProductPort\n"
        "from app.ports.projects import SQLiteProjectPort\n"
        "from app.ports.characters import SQLiteCharacterPort\n"
        "from app.ports.project_products import SQLiteProjectProductPort\n"
        "assert 'psycopg' not in sys.modules\n"
    )
    done = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, cwd=root)
    assert done.returncode == 0, done.stderr
