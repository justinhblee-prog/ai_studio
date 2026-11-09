from app.postgres_readiness import probe_postgres_runtime


def test_postgres_readiness_detects_complete_local_runtime():
    binaries = {"postgres", "initdb", "pg_ctl", "psql"}
    drivers = {"psycopg"}
    result = probe_postgres_runtime(
        executable_lookup=lambda name: f"/usr/bin/{name}" if name in binaries else None,
        module_lookup=lambda name: object() if name in drivers else None,
    )
    assert result.has_driver
    assert result.has_runtime_provisioner
    assert result.ready_for_local_integration_test


def test_postgres_readiness_accepts_container_runtime_with_driver():
    result = probe_postgres_runtime(
        executable_lookup=lambda name: "/usr/bin/docker" if name == "docker" else None,
        module_lookup=lambda name: object() if name == "asyncpg" else None,
    )
    assert result.ready_for_local_integration_test


def test_postgres_readiness_fails_closed_without_driver_or_provisioner():
    result = probe_postgres_runtime(
        executable_lookup=lambda name: None,
        module_lookup=lambda name: None,
    )
    assert not result.has_driver
    assert not result.has_runtime_provisioner
    assert not result.ready_for_local_integration_test


def test_postgres_readiness_does_not_require_psql_when_driver_and_container_exist():
    result = probe_postgres_runtime(
        executable_lookup=lambda name: "/usr/bin/podman" if name == "podman" else None,
        module_lookup=lambda name: object() if name == "psycopg2" else None,
    )
    assert result.ready_for_local_integration_test
    assert not result.binary_psql
