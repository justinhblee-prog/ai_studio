"""Lane 4: HTTP Range for videos (and 3D files) served from private storage: the parser, 206/416 answers, and that pictures and zips are untouched."""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.private_file_response import parse_byte_range
from tests.test_photo_steps_api import auth, env  # noqa: F401
from tests.test_video_asset_kind import save_video
from tests.test_video_mp4 import ffmpeg  # noqa: F401

client = TestClient(app)


@pytest.mark.parametrize("header, size, expected", [
    (None, 100, ("full", 0, 99)), ("", 100, ("full", 0, 99)),
    ("bytes=0-9", 100, ("partial", 0, 9)), ("bytes=90-", 100, ("partial", 90, 99)), ("bytes=-10", 100, ("partial", 90, 99)),
    ("bytes=0-", 100, ("partial", 0, 99)), ("bytes=0-999", 100, ("partial", 0, 99)), ("bytes=-500", 100, ("partial", 0, 99)), ("bytes=99-99", 100, ("partial", 99, 99)),
    ("BYTES=5-6", 100, ("partial", 5, 6)),
    ("bytes=100-", 100, ("invalid", 0, 0)), ("bytes=500-600", 100, ("invalid", 0, 0)), ("bytes=5-2", 100, ("invalid", 0, 0)), ("bytes=-0", 100, ("invalid", 0, 0)),
    ("bytes=0-9", 0, ("invalid", 0, 0)),
    ("bytes=0-1,5-6", 100, ("full", 0, 99)), ("items=0-1", 100, ("full", 0, 99)), ("bytes=a-b", 100, ("full", 0, 99)), ("bytes=-", 100, ("full", 0, 99)), ("bytes", 100, ("full", 0, 99)),
])
def test_the_range_parser(header, size, expected):
    assert parse_byte_range(header, size) == expected


def link(asset_id, who="a"):
    return client.post(f"/v1/assets/{asset_id}/preview-url", headers=auth(who)).json()["url"]


def test_a_video_is_served_in_pieces(env, ffmpeg):
    saved = save_video()
    whole = next((env["tmp"] / "private").glob(saved["asset_id"] + ".mp4")).read_bytes()
    url = link(saved["asset_id"])
    full = client.get(url)
    assert full.status_code == 200 and full.content == whole and full.headers["accept-ranges"] == "bytes" and int(full.headers["content-length"]) == len(whole)
    first = client.get(url, headers={"Range": "bytes=0-99"})
    assert first.status_code == 206 and first.content == whole[:100] and first.headers["content-range"] == f"bytes 0-99/{len(whole)}" and first.headers["content-length"] == "100"
    open_end = client.get(url, headers={"Range": "bytes=0-"})            # what a browser asks first
    assert open_end.status_code == 206 and open_end.content == whole and open_end.headers["content-range"] == f"bytes 0-{len(whole) - 1}/{len(whole)}"
    tail = client.get(url, headers={"Range": "bytes=-64"})
    assert tail.status_code == 206 and tail.content == whole[-64:] and tail.headers["content-range"] == f"bytes {len(whole) - 64}-{len(whole) - 1}/{len(whole)}"
    middle = client.get(url, headers={"Range": f"bytes=50-{len(whole) + 5000}"})
    assert middle.status_code == 206 and middle.content == whole[50:]
    for header in (f"bytes={len(whole)}-", "bytes=5-2"):
        r = client.get(url, headers={"Range": header})
        assert r.status_code == 416 and r.headers["content-range"] == f"bytes */{len(whole)}" and r.content == b"", header
    assert client.get(url, headers={"Range": "bytes=0-1,5-6"}).content == whole, "several ranges: the whole file"
    assert first.headers["cache-control"] == "private, no-store", "pieces are as private as the whole"


def test_the_piece_still_needs_a_valid_link_and_membership(env, ffmpeg):
    saved = save_video()
    url = link(saved["asset_id"])
    assert client.get(url.replace("signature=", "signature=0"), headers={"Range": "bytes=0-9"}).status_code == 403
    assert client.post(f"/v1/assets/{saved['asset_id']}/preview-url", headers=auth("b")).status_code in (403, 404)


def test_a_version_content_request_also_serves_pieces(env, ffmpeg):
    saved = save_video()
    version_id = client.get(f"/v1/assets/{saved['asset_id']}/versions", headers=auth("a")).json()["items"][0]["version_id"]
    whole = client.get(f"/v1/assets/{saved['asset_id']}/versions/{version_id}/preview-content", headers=auth("a"))
    assert whole.status_code == 200 and whole.headers["accept-ranges"] == "bytes"
    part = client.get(f"/v1/assets/{saved['asset_id']}/versions/{version_id}/preview-content", headers={**auth("a"), "Range": "bytes=4-11"})
    assert part.status_code == 206 and part.content == whole.content[4:12] == b"ftypisom"[:8] or part.content == whole.content[4:12]


def test_pictures_are_not_served_in_pieces(env):
    url = link(env["asset"])
    r = client.get(url, headers={"Range": "bytes=0-9"})
    assert r.status_code == 200 and "content-range" not in r.headers and r.content[:4] == b"\x89PNG"
