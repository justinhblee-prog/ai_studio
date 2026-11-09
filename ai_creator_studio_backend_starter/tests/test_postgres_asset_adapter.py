import pytest
from app.repositories.postgres_assets import PostgreSQLAssetMetadataRepository


def test_postgres_asset_metadata_adapter_is_explicit_and_lazy():
    assert PostgreSQLAssetMetadataRepository().backend == "postgresql"


def test_workspace_member_role_rejects_owner_self_assignment():
    with pytest.raises(ValueError, match="owner is assigned only"):
        PostgreSQLAssetMetadataRepository().add_workspace_member(
            "ws_1", "user_2", "owner", actor_id="user_1")


def test_workspace_member_role_rejects_unknown_role():
    with pytest.raises(ValueError, match="role is invalid"):
        PostgreSQLAssetMetadataRepository().add_workspace_member(
            "ws_1", "user_2", "superuser", actor_id="user_1")


@pytest.mark.parametrize("kwargs", [
    {"asset_id": "", "owner_id": "u", "workspace_id": "w", "original_filename": "a.png",
     "storage_key": "a.png", "media_type": "image/png", "size_bytes": 1, "checksum_sha256": "a"*64},
    {"asset_id": "a", "owner_id": "u", "workspace_id": "w", "original_filename": "a.png",
     "storage_key": "a.png", "media_type": "image/png", "size_bytes": -1, "checksum_sha256": "a"*64},
    {"asset_id": "a", "owner_id": "u", "workspace_id": "w", "original_filename": "a.png",
     "storage_key": "a.png", "media_type": "image/png", "size_bytes": 1, "checksum_sha256": "not-a-checksum"},
])
def test_asset_registration_rejects_invalid_metadata_before_database_access(kwargs):
    with pytest.raises(ValueError):
        PostgreSQLAssetMetadataRepository().register_asset(**kwargs)


def test_asset_version_validation_rejects_invalid_checksum_before_connect():
    with pytest.raises(ValueError, match="checksum"):
        PostgreSQLAssetMetadataRepository().create_asset_version(
            asset_id="ast_1", workspace_id="ws_1", actor_id="u_1",
            storage_key="v2.png", media_type="image/png", size_bytes=1,
            checksum_sha256="invalid",
        )


def test_asset_version_validation_rejects_negative_size_before_connect():
    with pytest.raises(ValueError, match="size"):
        PostgreSQLAssetMetadataRepository().create_asset_version(
            asset_id="ast_1", workspace_id="ws_1", actor_id="u_1",
            storage_key="v2.png", media_type="image/png", size_bytes=-1,
            checksum_sha256="a" * 64,
        )


def test_asset_relation_rejects_self_link_and_unknown_type_before_connect():
    repository = PostgreSQLAssetMetadataRepository()
    with pytest.raises(ValueError, match="self"):
        repository.create_asset_relation(workspace_id="ws_1", source_asset_id="ast_1",
            target_asset_id="ast_1", relation_type="paired_with", created_by="u_1")
    with pytest.raises(ValueError, match="Unsupported"):
        repository.create_asset_relation(workspace_id="ws_1", source_asset_id="ast_1",
            target_asset_id="ast_2", relation_type="owns", created_by="u_1")


def test_asset_provenance_pagination_is_bounded_before_connect():
    with pytest.raises(ValueError, match="pagination"):
        PostgreSQLAssetMetadataRepository().list_asset_provenance("ast_1", "ws_1", limit=0)
    with pytest.raises(ValueError, match="pagination"):
        PostgreSQLAssetMetadataRepository().list_asset_provenance("ast_1", "ws_1", offset=-1)


def test_asset_registration_rejects_unknown_storage_backend_before_database_access():
    with pytest.raises(ValueError, match="storage locator"):
        PostgreSQLAssetMetadataRepository().register_asset(
            asset_id="ast_1", owner_id="u_1", workspace_id="ws_1",
            original_filename="a.png", storage_key="a.png", media_type="image/png",
            size_bytes=1, checksum_sha256="a" * 64, storage_backend="unknown")


def test_asset_version_rejects_unknown_storage_backend_before_database_access():
    with pytest.raises(ValueError, match="storage locator"):
        PostgreSQLAssetMetadataRepository().create_asset_version(
            asset_id="ast_1", workspace_id="ws_1", actor_id="u_1",
            storage_key="v2.png", media_type="image/png", size_bytes=1,
            checksum_sha256="a" * 64, storage_backend="unknown")
