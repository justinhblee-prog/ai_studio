import pytest
from app.repositories.postgres_project_products import PostgreSQLProjectProductRepository


def test_postgres_project_product_adapter_is_explicit_and_lazy():
    assert PostgreSQLProjectProductRepository().backend == "postgresql"


@pytest.mark.parametrize("ids", [
    ["prd_1", "prd_1"],
    [""],
    ["x" * 81],
    ["prd_" + str(i) for i in range(101)],
    "not-a-list",
])
def test_assignment_ids_validate_before_database_access(ids):
    with pytest.raises(ValueError):
        PostgreSQLProjectProductRepository().replace_for_project(
            "prj_1", "ws_1", ids, "user_1"
        )


def test_assignment_ids_allow_empty_to_clear_project():
    PostgreSQLProjectProductRepository._validate_ids([])


def test_assignment_migration_enforces_workspace_pair_and_append_only_events():
    from pathlib import Path

    migration = Path(__file__).parents[1] / "app/sql/postgres/migrations/0008_project_product_assignments.sql"
    sql = migration.read_text(encoding="utf-8")
    assert "FOREIGN KEY(project_id,workspace_id) REFERENCES projects(project_id,workspace_id)" in sql
    assert "FOREIGN KEY(product_id,workspace_id) REFERENCES products(product_id,workspace_id)" in sql
    assert "WHERE removed_at IS NULL" in sql
    assert "acs_reject_append_only_mutation" in sql
    assert "ALTER TABLE project_product_assignments ENABLE ROW LEVEL SECURITY" in sql
    assert "ALTER TABLE project_product_events ENABLE ROW LEVEL SECURITY" in sql
