import pytest


def test_local_blob_store_rejects_escape_overwrite_and_unsafe_delete(tmp_path, monkeypatch):
    import app.config as config
    from app.assets.blob_store import BlobIntegrityError, LocalBlobStore
    root = tmp_path / "private"; root.mkdir()
    outside = tmp_path / "outside.bin"; outside.write_bytes(b"keep")
    monkeypatch.setattr(config, "ASSET_STORAGE_DIR", root)
    blobs = LocalBlobStore()
    for bad in ("../outside.bin", "sub/x.bin", "/etc/passwd", ""):
        with pytest.raises((RuntimeError, ValueError)):
            blobs.write_new(bad, b"x")
        with pytest.raises(BlobIntegrityError):
            blobs.read_verified(bad, 1, "0" * 64)
        blobs.delete(bad)                       # silently ignored, never touches anything outside the root
        assert blobs.current_file(bad) is None
    assert outside.read_bytes() == b"keep"
    blobs.write_new("k.bin", b"one")
    with pytest.raises(FileExistsError):        # immutable: an existing object is never overwritten
        blobs.write_new("k.bin", b"two")
    assert (root / "k.bin").read_bytes() == b"one"
    assert blobs.audit_status("k.bin", 3, __import__("hashlib").sha256(b"one").hexdigest()) == "ok"
    assert blobs.audit_status("missing.bin", 1, "0" * 64) == "missing"
