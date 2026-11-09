import json
import struct
import pytest
from app.assets.validation import (
    AssetValidationError, GLB_JSON_CHUNK, validate_gltf_upload,
)


def glb(document):
    payload = json.dumps(document, separators=(",", ":")).encode()
    payload += b" " * ((4 - len(payload) % 4) % 4)
    chunk = struct.pack("<II", len(payload), GLB_JSON_CHUNK) + payload
    total = 12 + len(chunk)
    return b"glTF" + struct.pack("<II", 2, total) + chunk


def test_accepts_minimal_glb():
    result = validate_gltf_upload("model.glb", glb({"asset": {"version": "2.0"}}))
    assert result.media_type == "model/gltf-binary"
    assert result.gltf_version == "2.0"


def test_accepts_self_contained_gltf():
    raw = json.dumps({"asset": {"version": "2.0"}, "buffers": [{"uri": "data:application/octet-stream;base64,AA=="}]}).encode()
    result = validate_gltf_upload("model.gltf", raw)
    assert result.media_type == "model/gltf+json"
    assert result.embedded_binary is True


@pytest.mark.parametrize("uri", ["https://example.com/model.bin", "../../secret", "file:///etc/passwd"])
def test_rejects_external_resource_uris(uri):
    raw = json.dumps({"asset": {"version": "2.0"}, "buffers": [{"uri": uri}]}).encode()
    with pytest.raises(AssetValidationError) as error:
        validate_gltf_upload("model.gltf", raw)
    assert error.value.code == "ASSET_EXTERNAL_URI_BLOCKED"


def test_rejects_fake_glb_signature():
    with pytest.raises(AssetValidationError) as error:
        validate_gltf_upload("model.glb", b"not a glb file")
    assert error.value.code == "ASSET_SIGNATURE_INVALID"


def test_rejects_unsupported_extension():
    with pytest.raises(AssetValidationError) as error:
        validate_gltf_upload("model.obj", b"v 0 0 0")
    assert error.value.code == "ASSET_FORMAT_UNSUPPORTED"


def test_rejects_oversized_upload():
    with pytest.raises(AssetValidationError) as error:
        validate_gltf_upload("model.gltf", b"{}", max_bytes=1)
    assert error.value.code == "ASSET_TOO_LARGE"


def test_rejects_old_gltf_version():
    with pytest.raises(AssetValidationError) as error:
        validate_gltf_upload("model.gltf", b'{"asset":{"version":"1.0"}}')
    assert error.value.code == "ASSET_FORMAT_UNSUPPORTED"
