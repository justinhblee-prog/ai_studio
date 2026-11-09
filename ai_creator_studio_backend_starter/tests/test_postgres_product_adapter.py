import pytest
from app.repositories.postgres_products import PostgreSQLProductRepository


def test_postgres_product_adapter_is_explicit_and_lazy():
    assert PostgreSQLProductRepository().backend == "postgresql"


@pytest.mark.parametrize("kwargs", [
    {"sku": "", "name": "Jacket", "description": None, "category": "fashion", "image_asset_ids": ["ast_1"]},
    {"sku": "x" * 65, "name": "Jacket", "description": None, "category": "fashion", "image_asset_ids": ["ast_1"]},
    {"sku": "SKU-1", "name": "", "description": None, "category": "fashion", "image_asset_ids": ["ast_1"]},
    {"sku": "SKU-1", "name": "Jacket", "description": "x" * 2001, "category": "fashion", "image_asset_ids": ["ast_1"]},
    {"sku": "SKU-1", "name": "Jacket", "description": None, "category": "", "image_asset_ids": ["ast_1"]},
    {"sku": "SKU-1", "name": "Jacket", "description": None, "category": "fashion", "image_asset_ids": []},
    {"sku": "SKU-1", "name": "Jacket", "description": None, "category": "fashion", "image_asset_ids": ["ast_1", "ast_1"]},
])
def test_product_create_validation_happens_before_database_access(kwargs):
    with pytest.raises(ValueError):
        PostgreSQLProductRepository().create(
            workspace_id="ws_1", actor_id="user_1", **kwargs
        )


def test_product_pagination_is_bounded_before_database_access():
    repo = PostgreSQLProductRepository()
    with pytest.raises(ValueError, match="pagination"):
        repo.list_for_workspace("ws_1", "user_1", limit=0)
    with pytest.raises(ValueError, match="pagination"):
        repo.list_for_workspace("ws_1", "user_1", offset=-1)
    with pytest.raises(ValueError, match="pagination"):
        repo.list_for_workspace("ws_1", "user_1", limit=101)


def test_products_migration_has_tenant_foreign_keys_rls_and_asset_workspace_guard():
    from pathlib import Path

    migration = Path(__file__).parents[1] / "app/sql/postgres/migrations/0007_products.sql"
    sql = migration.read_text(encoding="utf-8")
    assert "FOREIGN KEY(product_id,workspace_id) REFERENCES products(product_id,workspace_id)" in sql
    assert "CREATE UNIQUE INDEX IF NOT EXISTS uq_products_workspace_sku_ci" in sql
    assert "acs_check_product_asset_workspace" in sql
    assert "acs_reject_append_only_mutation" in sql
    for table in ("products", "product_assets", "product_variants", "product_variant_assets", "product_events"):
        assert f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY" in sql


@pytest.mark.parametrize("sku,options,images", [
    ("", {"size": "M"}, []),
    ("S", {"size": "M"}, []),
    ("SKU-1", {}, []),
    ("SKU-1", {"size": "M", " SIZE ": "L"}, []),
    ("SKU-1", {"bad key": "M"}, []),
    ("SKU-1", {"size": ""}, []),
    ("SKU-1", {"size": "x" * 81}, []),
    ("SKU-1", {"size": "M"}, ["ast_1", "ast_1"]),
    ("SKU-1", {"size": "M"}, ["x" * 81]),
])
def test_variant_validation_happens_before_database_access(sku, options, images):
    with pytest.raises(ValueError):
        PostgreSQLProductRepository().create_variant(
            product_id="prd_1", workspace_id="ws_1", actor_id="user_1",
            sku=sku, option_values=options, image_asset_ids=images,
        )


def test_cross_catalog_sku_guard_uses_workspace_lock_and_both_tables():
    from pathlib import Path

    migration = Path(__file__).parents[1] / "app/sql/postgres/migrations/0010_cross_catalog_sku_guard.sql"
    sql = migration.read_text(encoding="utf-8")
    assert "pg_advisory_xact_lock" in sql
    assert "public.product_variants" in sql
    assert "public.products" in sql
    assert "trg_products_cross_catalog_sku" in sql
    assert "trg_product_variants_cross_catalog_sku" in sql
