from pathlib import Path

import pytest

from app.assets.blob_lifecycle import (
    AssetBlobRef,
    build_asset_blob_store,
    delete_asset_blob,
    get_asset_blob,
    make_asset_blob_ref,
    put_asset_blob,
)


def test_local_gateway_preserves_legacy_asset_directory_and_flat_key(tmp_path, monkeypatch):
    from app import config
    asset_root = tmp_path / "private"
    monkeypatch.setattr(config, "ASSET_STORAGE_DIR", asset_root)
    backend, bucket, store = build_asset_blob_store("local")
    assert backend == "local" and bucket == "private"
    assert store.root == tmp_path.resolve()

    ref = make_asset_blob_ref(workspace_id="ws-a", asset_id="ast_123", filename="model.glb", backend="local")
    assert ref == AssetBlobRef("local", "private", "ast_123.glb")
    put_asset_blob(ref, b"glb-data", "model/gltf-binary")
    assert (asset_root / "ast_123.glb").read_bytes() == b"glb-data"
    assert get_asset_blob(ref) == b"glb-data"
    assert delete_asset_blob(ref) is True
    assert delete_asset_blob(ref) is False


def test_supabase_ref_is_workspace_scoped_and_safe(tmp_path, monkeypatch):
    from app import config
    monkeypatch.setattr(config, "ASSET_STORAGE_DIR", tmp_path / "private")
    ref = make_asset_blob_ref(workspace_id="ws-a", asset_id="ast_123", filename="model.glb",
                              backend="supabase_storage")
    assert ref.backend == "supabase_storage"
    assert ref.bucket == "acs-assets"
    assert ref.key == "ws-a/ast_123/ast_123.glb"
    assert AssetBlobRef.from_record(ref.to_record()) == ref


@pytest.mark.parametrize("record", [
    {"backend": "remote", "bucket": "acs-assets", "key": "ws/a"},
    {"backend": "supabase_storage", "bucket": "public", "key": "ws/a"},
    {"backend": "supabase_storage", "bucket": "acs-assets", "key": "../secret"},
    {"backend": "local", "bucket": "wrong", "key": "asset.glb"},
])
def test_asset_blob_ref_rejects_invalid_persisted_locator(record, tmp_path, monkeypatch):
    from app import config
    monkeypatch.setattr(config, "ASSET_STORAGE_DIR", tmp_path / "private")
    with pytest.raises(ValueError):
        AssetBlobRef.from_record(record)


def test_local_gateway_rejects_unsafe_key(tmp_path, monkeypatch):
    from app import config
    monkeypatch.setattr(config, "ASSET_STORAGE_DIR", tmp_path / "private")
    ref = AssetBlobRef("local", "private", "../outside.glb")
    with pytest.raises(ValueError):
        put_asset_blob(ref, b"data", "model/gltf-binary")
