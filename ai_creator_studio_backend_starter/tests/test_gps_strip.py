"""Reply 41: the GPS position is removed from downloaded pictures; the stored original, the picture data and the other metadata stay byte for byte."""
import hashlib
import io
import struct
import zlib

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import config, privacy_strip
from app.main import app
from tests.test_photo_steps_api import auth, env  # noqa: F401  (wa: owner a + viewer c, wb: owner b)

client = TestClient(app)
LAT, LON = (37.0, 33.0, 59.0), (126.0, 58.0, 41.0)


def exif_with_gps(orientation=6, make="SecretCamera", gps=True):
    ex = Image.Exif()
    ex[0x0112] = orientation
    ex[0x010F] = make
    if gps:
        ifd = ex.get_ifd(0x8825)
        ifd[1], ifd[2], ifd[3], ifd[4] = "N", LAT, "E", LON
        ex[0x8825] = ifd
    return ex.tobytes()


def jpeg(gps=True, size=(60, 40)):
    buf = io.BytesIO(); Image.new("RGB", size, (200, 40, 40)).save(buf, format="JPEG", exif=exif_with_gps(gps=gps)); return buf.getvalue()


def png(gps=True):
    buf = io.BytesIO(); Image.new("RGB", (30, 20), (10, 90, 200)).save(buf, format="PNG", exif=exif_with_gps(gps=gps)); return buf.getvalue()


def webp(gps=True):
    buf = io.BytesIO(); Image.new("RGB", (30, 20), (10, 90, 200)).save(buf, format="WEBP", lossless=True, exif=exif_with_gps(gps=gps)); return buf.getvalue()


def exif_of(data):
    with Image.open(io.BytesIO(data)) as im:
        ex = im.getexif()
        return dict(ex), dict(ex.get_ifd(0x8825))


def pixels(data):
    with Image.open(io.BytesIO(data)) as im:
        return im.convert("RGB").tobytes()


MAKERS = [("image/jpeg", jpeg), ("image/png", png), ("image/webp", webp)]


@pytest.mark.parametrize("media,make", MAKERS)
def test_gps_is_removed_and_everything_else_is_kept(media, make):
    original = make()
    tags, gps = exif_of(original)
    assert gps and 0x8825 in tags, "the test picture really carries a position"
    out, removed = privacy_strip.strip_gps(original, media)
    assert removed is True and len(out) == len(original), "nothing is re-encoded and the size does not change"
    tags2, gps2 = exif_of(out)
    assert gps2 == {} and 0x8825 not in tags2
    assert tags2[0x010F] == "SecretCamera" and tags2[0x0112] == 6, "make and orientation stay"
    assert {k: v for k, v in tags.items() if k != 0x8825} == tags2
    assert pixels(out) == pixels(original)
    assert b"37.0" not in out
    again, removed_again = privacy_strip.strip_gps(out, media)
    assert again == out and removed_again is False, "idempotent"


@pytest.mark.parametrize("media,make", MAKERS)
def test_a_picture_without_gps_comes_back_identical(media, make):
    original = make(gps=False)
    out, removed = privacy_strip.strip_gps(original, media)
    assert out == original and removed is False


def tiff(endian, with_gps=True):
    """A small hand-built EXIF block: IFD0 = [Make, GPS pointer, Orientation]; GPS IFD = [LatRef, Lat]; both byte orders."""
    e = endian
    p = lambda fmt, *a: struct.pack(e + fmt, *a)
    head = (b"II" if e == "<" else b"MM") + p("H", 42) + p("I", 8)
    make = b"Cam\x00"
    entries = [(0x010F, 2, 4, make), (0x0112, 3, 1, p("H", 6) + b"\x00\x00")]
    if with_gps:
        entries.append((0x8825, 4, 1, None))
    entries.sort(key=lambda t: t[0])
    ifd0_len = 2 + 12 * len(entries) + 4
    gps_off = 8 + ifd0_len
    ifd0 = p("H", len(entries))
    for tag, typ, cnt, val in entries:
        ifd0 += p("HHI", tag, typ, cnt) + (p("I", gps_off) if val is None else val)
    ifd0 += p("I", 0)
    gps = b""
    if with_gps:
        lat_data_off = gps_off + 2 + 24 + 4
        gps = p("H", 2) + p("HHI", 1, 2, 2) + b"N\x00\x00\x00" + p("HHI", 2, 5, 3) + p("I", lat_data_off) + p("I", 0)
        gps += p("IIIIII", 37, 1, 33, 1, 59, 1)
    return head + ifd0 + gps


@pytest.mark.parametrize("endian", ["<", ">"])
def test_both_byte_orders_and_the_other_entries_are_byte_for_byte_kept(endian):
    block = bytearray(tiff(endian))
    assert privacy_strip.strip_tiff(block) is True and len(block) == len(tiff(endian))
    assert block.count(b"Cam\x00") == 1 and bytes(block) != tiff(endian)
    e = endian
    n = struct.unpack(e + "H", bytes(block[8:10]))[0]
    tags = [struct.unpack(e + "H", bytes(block[10 + 12 * i:12 + 12 * i]))[0] for i in range(n)]
    assert tags == [0x010F, 0x0112], "the GPS entry is gone, the order of the others is kept"
    assert struct.pack(e + "IIIIII", 37, 1, 33, 1, 59, 1) not in bytes(block), "the position values are overwritten"
    clean = bytearray(tiff(endian, with_gps=False))
    assert privacy_strip.strip_tiff(clean) is False


def jpeg_with_blocks(*blocks):
    base = jpeg(gps=False)
    soi = base[:2]
    segs = b"".join(b"\xff\xe1" + struct.pack(">H", len(b) + 2) + b for b in blocks)
    return soi + segs + base[2:]


@pytest.mark.parametrize("endian", ["<", ">"])
def test_hand_built_exif_in_a_jpeg_is_cleaned_and_the_picture_still_opens(endian):
    data = jpeg_with_blocks(b"Exif\x00\x00" + tiff(endian))
    out, removed = privacy_strip.strip_gps(data, "image/jpeg")
    assert removed and len(out) == len(data)
    with Image.open(io.BytesIO(out)) as im:
        im.load()
    assert struct.pack(endian + "IIIIII", 37, 1, 33, 1, 59, 1) not in out


XMP = (b'<?xpacket begin="x"?><x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
       b'<rdf:Description xmlns:exif="http://ns.adobe.com/exif/1.0/" xmlns:tiff="http://ns.adobe.com/tiff/1.0/" exif:GPSLatitude="37,33.99N" exif:GPSLongitude=\'126,58.69E\' tiff:Make="SecretCamera">'
       b'<exif:GPSAltitude>35/1</exif:GPSAltitude><exif:GPSVersionID/><exif:ExposureTime>1/100</exif:ExposureTime></rdf:Description></rdf:RDF></x:xmpmeta><?xpacket end="w"?>')


def test_xmp_gps_is_blanked_with_the_same_length_and_other_values_stay():
    out = privacy_strip.scrub_xmp(XMP)
    assert len(out) == len(XMP) and b"GPS" not in out and b"37,33" not in out and b"126,58" not in out and b"35/1" not in out
    assert b'tiff:Make="SecretCamera"' in out and b"<exif:ExposureTime>1/100</exif:ExposureTime>" in out
    import xml.etree.ElementTree as ET
    ET.fromstring(out.split(b"?>", 1)[1].rsplit(b"<?xpacket", 1)[0])
    assert privacy_strip.scrub_xmp(out) == out


def test_xmp_gps_in_each_container():
    jp = jpeg_with_blocks(b"http://ns.adobe.com/xap/1.0/\x00" + XMP)
    out, removed = privacy_strip.strip_gps(jp, "image/jpeg")
    assert removed and b"GPSLatitude" not in out and b"SecretCamera" in out and len(out) == len(jp)
    base = png(gps=False)
    chunk_body = b"XML:com.adobe.xmp\x00\x00\x00\x00\x00" + XMP
    chunk = struct.pack(">I", len(chunk_body)) + b"iTXt" + chunk_body + struct.pack(">I", zlib.crc32(b"iTXt" + chunk_body) & 0xFFFFFFFF)
    ihdr_end = 8 + 12 + 13
    pn = base[:ihdr_end] + chunk + base[ihdr_end:]
    out, removed = privacy_strip.strip_gps(pn, "image/png")
    assert removed and b"GPSLatitude" not in out and len(out) == len(pn)
    Image.open(io.BytesIO(out)).load()
    assert zlib.crc32(b"iTXt" + out[ihdr_end + 8:ihdr_end + 8 + len(chunk_body)]) & 0xFFFFFFFF == struct.unpack(">I", out[ihdr_end + 8 + len(chunk_body):ihdr_end + 12 + len(chunk_body)])[0], "the chunk checksum was recomputed"
    from app.ai_marking import mark_webp
    marked = mark_webp(webp(gps=False), "generated")                # a VP8X container whose LAST chunk is an XMP chunk
    i = marked.index(b"XMP ")
    chunk = b"XMP " + struct.pack("<I", len(XMP)) + XMP + (b"\x00" if len(XMP) & 1 else b"")
    body = marked[12:i] + chunk
    wp = b"RIFF" + struct.pack("<I", 4 + len(body)) + b"WEBP" + body
    out, removed = privacy_strip.strip_gps(wp, "image/webp")
    assert removed and b"GPSLatitude" not in out and b"SecretCamera" in out and len(out) == len(wp)
    Image.open(io.BytesIO(out)).load()


@pytest.mark.parametrize("media,data", [("image/jpeg", b"nope"), ("image/png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 5), ("image/webp", b"RIFFxxxxWEBPxx"), ("image/gif", b"GIF89a"),
                                       ("image/jpeg", b"\xff\xd8\xff\xe1\xff\xff" + b"Exif\x00\x00"), ("image/jpeg", b"")])
def test_malformed_or_unsupported_input_comes_back_unchanged(media, data):
    assert privacy_strip.strip_gps(data, media) == (data, False)


# ------------------------------------------------------------------------------------------------------ through the API
def upload(content, name):
    r = client.post("/v1/workspaces/wa/library", headers=auth("a"), data={"kind": "model", "name": "x", "rights_confirmed": "true"}, files={"file": (name, content, "image/jpeg")})
    assert r.status_code == 201, r.text
    return r.json()


def preview(asset_id, who="a"):
    url = client.post(f"/v1/assets/{asset_id}/preview-url", headers=auth(who)).json()["url"]
    return client.get(url)


def stored(env_, asset_id):
    return next((env_["tmp"] / "private").glob(f"{asset_id}.*"))


@pytest.mark.parametrize("name,make", [("p.jpg", jpeg), ("p.png", png), ("p.webp", webp)])
def test_a_download_has_no_position_while_the_stored_original_is_unchanged(env, name, make):
    original = make()
    item = upload(original, name)
    r = preview(item["asset_id"])
    assert r.status_code == 200 and r.headers["x-gps-stripped"] == "1"
    assert exif_of(r.content)[1] == {} and exif_of(r.content)[0][0x010F] == "SecretCamera", "other camera data stays"
    assert pixels(r.content) == pixels(original) and len(r.content) == len(original)
    assert stored(env, item["asset_id"]).read_bytes() == original, "byte for byte what was uploaded (its checksum is the provenance)"
    assert hashlib.sha256(stored(env, item["asset_id"]).read_bytes()).hexdigest() == hashlib.sha256(original).hexdigest()
    assert exif_of(original)[1], "and the original still has the position"


def test_pictures_without_a_position_are_served_exactly_as_stored(env):
    original = jpeg(gps=False)
    item = upload(original, "n.jpg")
    r = preview(item["asset_id"])
    assert r.content == original and "x-gps-stripped" not in r.headers


def test_the_authenticated_version_download_is_cleaned_too(env):
    item = upload(jpeg(), "v.jpg")
    versions = client.get(f"/v1/assets/{item['asset_id']}/versions", headers=auth("a")).json()
    vid = (versions["items"] if isinstance(versions, dict) else versions)[0]["version_id"]
    r = client.get(f"/v1/assets/{item['asset_id']}/versions/{vid}/preview-content", headers=auth("a"))
    assert r.status_code == 200 and r.headers["x-gps-stripped"] == "1" and exif_of(r.content)[1] == {}


def test_it_can_be_switched_off(env, monkeypatch):
    original = jpeg()
    item = upload(original, "o.jpg")
    monkeypatch.setattr(config, "STRIP_GPS_ON_DOWNLOAD", False)
    r = preview(item["asset_id"])
    assert r.content == original and "x-gps-stripped" not in r.headers


def test_the_real_default_is_on():
    import os, subprocess, sys
    from pathlib import Path
    clean = {k: v for k, v in os.environ.items() if k != "STRIP_GPS_ON_DOWNLOAD"}
    out = subprocess.run([sys.executable, "-c", "import app.config as c; print(c.STRIP_GPS_ON_DOWNLOAD)"], cwd=Path(__file__).resolve().parents[1], env=clean,
                         capture_output=True, text=True, check=True).stdout.strip()
    assert out == "True"


def test_gps_and_the_ai_mark_both_apply_to_an_ai_result(env, monkeypatch):
    from app import ai_marking
    monkeypatch.setattr(ai_marking, "kind_for_asset", lambda asset_id: "generated")
    item = upload(jpeg(), "g.jpg")
    r = preview(item["asset_id"])
    assert r.headers["x-gps-stripped"] == "1" and r.headers["x-ai-marked"] == "generated"
    assert exif_of(r.content)[1] == {} and b"trainedAlgorithmicMedia" in r.content


def test_the_thumbnail_never_carried_it(env):
    item = upload(jpeg(), "t.jpg")
    data = client.get(item["thumbs"]["480"]).content
    with Image.open(io.BytesIO(data)) as im:
        assert not im.getexif() and b"SecretCamera" not in data
