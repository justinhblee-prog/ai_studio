"""Non-invasive capability probe for PostgreSQL runtime verification."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from importlib.util import find_spec
from shutil import which
from typing import Callable


@dataclass(frozen=True)
class PostgresRuntimeCapabilities:
    driver_psycopg: bool
    driver_psycopg2: bool
    driver_asyncpg: bool
    binary_postgres: bool
    binary_initdb: bool
    binary_pg_ctl: bool
    binary_psql: bool
    binary_docker: bool
    binary_podman: bool

    @property
    def has_driver(self) -> bool:
        return self.driver_psycopg or self.driver_psycopg2 or self.driver_asyncpg

    @property
    def has_runtime_provisioner(self) -> bool:
        return (self.binary_postgres and self.binary_initdb and self.binary_pg_ctl) or self.binary_docker or self.binary_podman

    @property
    def ready_for_local_integration_test(self) -> bool:
        return self.has_driver and self.has_runtime_provisioner

    def as_dict(self) -> dict[str, object]:
        data = asdict(self)
        data.update({
            "has_driver": self.has_driver,
            "has_runtime_provisioner": self.has_runtime_provisioner,
            "ready_for_local_integration_test": self.ready_for_local_integration_test,
        })
        return data


def probe_postgres_runtime(
    executable_lookup: Callable[[str], str | None] = which,
    module_lookup: Callable[[str], object | None] = find_spec,
) -> PostgresRuntimeCapabilities:
    """Detect available tooling without connecting to or modifying any database."""
    return PostgresRuntimeCapabilities(
        driver_psycopg=module_lookup("psycopg") is not None,
        driver_psycopg2=module_lookup("psycopg2") is not None,
        driver_asyncpg=module_lookup("asyncpg") is not None,
        binary_postgres=executable_lookup("postgres") is not None,
        binary_initdb=executable_lookup("initdb") is not None,
        binary_pg_ctl=executable_lookup("pg_ctl") is not None,
        binary_psql=executable_lookup("psql") is not None,
        binary_docker=executable_lookup("docker") is not None,
        binary_podman=executable_lookup("podman") is not None,
    )
