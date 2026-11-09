import httpx
import pytest
from pathlib import Path

from app.blob_storage import (BlobStorageError, LocalFileBlobStore,
    SupabaseStorageBlobStore, build_blob_store, tenant_object_key, validate_object_key)


def test_storage_key_rejects_traversal_and_absolute_paths():
    for key in ("../secret", "/absolute/file", "a/../../b", "a\\b", "a//b"):
        with pytest.raises(ValueError):
            validate_object_key(key)


def test_local_blob_store_roundtrip_and_bucket_isolation(tmp_path):
    store = LocalFileBlobStore(tmp_path)
    meta = store.put("assets", "workspace-a/asset-1.glb", b"glb", "model/gltf-binary")
    assert meta["size_bytes"] == 3
    assert store.get("assets", "workspace-a/asset-1.glb") == b"glb"
    assert store.delete("assets", "workspace-a/asset-1.glb") is True
    assert store.delete("assets", "workspace-a/asset-1.glb") is False


def test_supabase_storage_requires_https_and_credentials():
    with pytest.raises(RuntimeError, match="required"):
        SupabaseStorageBlobStore(project_url="", service_key="")
    with pytest.raises(ValueError, match="HTTPS"):
        SupabaseStorageBlobStore(project_url="http://localhost", service_key="test")


def test_supabase_storage_private_upload_download_delete_contract():
    calls = []
    def handler(request):
        calls.append(request)
        if request.method == "GET":
            return httpx.Response(200, content=b"image-bytes", headers={"content-type": "image/png"})
        return httpx.Response(200, json={"ok": True}, headers={"etag": '"abc"'})
    transport = httpx.MockTransport(handler)
    store = SupabaseStorageBlobStore(project_url="https://project.supabase.co",
        service_key="secret-test-key", transport=transport)
    result = store.put("acs-gallery", "ws_1/ast_1/source.png", b"png", "image/png")
    assert result["etag"] == '"abc"'
    assert store.get("acs-gallery", "ws_1/ast_1/source.png") == b"image-bytes"
    assert store.delete("acs-gallery", "ws_1/ast_1/source.png") is True
    assert [r.method for r in calls] == ["POST", "GET", "DELETE"]
    assert all(r.headers["authorization"] == "Bearer secret-test-key" for r in calls)
    assert calls[0].headers["x-upsert"] == "false"
    store.close()


def test_supabase_storage_rejects_public_unknown_bucket_and_wrong_mime():
    store = SupabaseStorageBlobStore(project_url="https://project.supabase.co",
        service_key="secret-test-key", transport=httpx.MockTransport(lambda r: httpx.Response(200)))
    with pytest.raises(ValueError, match="allowlist"):
        store.put("public", "a.png", b"x", "image/png")
    with pytest.raises(ValueError, match="not allowed"):
        store.put("acs-assets", "a.png", b"x", "image/png")
    store.close()


def test_supabase_storage_does_not_leak_response_body_on_failure():
    store = SupabaseStorageBlobStore(project_url="https://project.supabase.co",
        service_key="secret-test-key", transport=httpx.MockTransport(lambda r: httpx.Response(403, text="sensitive")))
    with pytest.raises(BlobStorageError, match="HTTP 403") as exc:
        store.get("acs-gallery", "ws_1/a.png")
    assert "sensitive" not in str(exc.value)
    store.close()


def test_blob_store_factory_defaults_to_local(monkeypatch, tmp_path):
    monkeypatch.setenv("BLOB_STORAGE_BACKEND", "local")
    monkeypatch.setattr("app.blob_storage.config.ASSET_STORAGE_DIR", tmp_path)
    assert isinstance(build_blob_store(), LocalFileBlobStore)


def test_tenant_object_key_is_workspace_scoped_and_rejects_untrusted_segments():
    assert tenant_object_key("ws_1", "ast_1", "source.png") == "ws_1/ast_1/source.png"
    with pytest.raises(ValueError):
        tenant_object_key("../other", "ast_1", "source.png")


def test_supabase_storage_download_enforces_declared_size_before_read(monkeypatch):
    store = SupabaseStorageBlobStore(project_url="https://project.supabase.co",
        service_key="secret-test-key", transport=httpx.MockTransport(
            lambda r: httpx.Response(200, headers={"content-type": "image/png", "content-length": str(21 * 1024 * 1024)}, content=b"x")))
    with pytest.raises(BlobStorageError, match="exceeds"):
        store.get("acs-gallery", "ws_1/ast_1/source.png")
    store.close()


def test_supabase_storage_download_enforces_streamed_size_without_content_length():
    class Chunked(httpx.SyncByteStream):
        def __iter__(self):
            yield b"x" * (10 * 1024 * 1024)
            yield b"y" * (10 * 1024 * 1024)
            yield b"z"
        def close(self):
            pass

    store = SupabaseStorageBlobStore(project_url="https://project.supabase.co",
        service_key="secret-test-key", transport=httpx.MockTransport(
            lambda r: httpx.Response(200, headers={"content-type": "image/png"}, stream=Chunked())))
    with pytest.raises(BlobStorageError, match="exceeds"):
        store.get("acs-gallery", "ws_1/ast_1/source.png")
    store.close()


def test_supabase_storage_download_rejects_wrong_response_mime():
    store = SupabaseStorageBlobStore(project_url="https://project.supabase.co",
        service_key="secret-test-key", transport=httpx.MockTransport(
            lambda r: httpx.Response(200, headers={"content-type": "text/html"}, content=b"<html>")))
    with pytest.raises(BlobStorageError, match="unsupported media"):
        store.get("acs-gallery", "ws_1/ast_1/source.png")
    store.close()
