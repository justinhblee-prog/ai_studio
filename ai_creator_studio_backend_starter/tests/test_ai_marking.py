"""R-062: the "AI-made" mark written into downloaded AI pictures (PNG / JPEG / WebP): present, parseable, pixels and existing metadata untouched,
never on uploads or mock/local results, wording from settings, the stored file unchanged."""
import hashlib
import io
import sqlite3
import struct
import xml.etree.ElementTree as ET

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import ai_marking, config
from app.main import app
from app.output_asset_link_worker import process_one
from tests.test_output_asset_link_worker import linked_output_env  # noqa: F401

client = TestClient(app)
A = {"Authorization": "Bearer token-user-a"}
WS = "ws-output-link"
GEN = "http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia"
COMP = "http://cv.iptc.org/newscodes/digitalsourcetype/compositeWithTrainedAlgorithmicMedia"


def png_bytes(size=(32, 24), color=(10, 200, 90), text=None, alpha=False):
    from PIL.PngImagePlugin import PngInfo
    info = PngInfo()
    for k, v in (text or {}).items():
        info.add_text(k, v)
    buf = io.BytesIO(); Image.new("RGBA" if alpha else "RGB", size, color + ((100,) if alpha else ())).save(buf, format="PNG", pnginfo=info); return buf.getvalue()


def jpeg_bytes(exif=True):
    ex = Image.Exif(); ex[0x010F] = "MyCamera"; ex[0x0112] = 1
    buf = io.BytesIO(); Image.new("RGB", (40, 30), (200, 30, 30)).save(buf, format="JPEG", exif=ex.tobytes() if exif else b""); return buf.getvalue()


def webp_bytes(alpha=False, animated=False, exif=False):
    buf = io.BytesIO()
    if animated:
        frames = [Image.new("RGB", (20, 20), (i * 40, 0, 0)) for i in range(3)]
        frames[0].save(buf, format="WEBP", save_all=True, append_images=frames[1:], duration=100, lossless=True)
    else:
        ex = Image.Exif(); ex[0x010F] = "Cam"
        Image.new("RGBA" if alpha else "RGB", (24, 16), (5, 6, 7) + ((50,) if alpha else ())).save(buf, format="WEBP", lossless=True, **({"exif": ex.tobytes()} if exif else {}))
    return buf.getvalue()


def pixels(data):
    out = []
    with Image.open(io.BytesIO(data)) as im:
        for i in range(getattr(im, "n_frames", 1)):
            im.seek(i)
            out.append(im.convert("RGBA").tobytes())
    return out


def xmp_of(data, media):
    if media == "image/png":
        i = data.index(b"XML:com.adobe.xmp\x00")
        start = data.index(b"<?xpacket", i)
        end = data.index(b"<?xpacket end=\"w\"?>", start) + len(b"<?xpacket end=\"w\"?>")
        return data[start:end]
    if media == "image/jpeg":
        i = data.index(b"http://ns.adobe.com/xap/1.0/\x00") + 29
        return data[i:data.index(b"<?xpacket end=\"w\"?>", i) + len(b"<?xpacket end=\"w\"?>")]
    i = data.index(b"XMP ")
    size = struct.unpack("<I", data[i + 4:i + 8])[0]
    return data[i + 8:i + 8 + size]


def source_type(xmp):
    root = ET.fromstring(xmp.split(b"?>", 1)[1].rsplit(b"<?xpacket", 1)[0])
    return next(el.text for el in root.iter() if el.tag.endswith("}DigitalSourceType")), next(el.text for el in root.iter() if el.tag.endswith("}li"))


CASES = [("image/png", png_bytes), ("image/jpeg", jpeg_bytes), ("image/webp", webp_bytes)]


@pytest.mark.parametrize("media,make", CASES)
@pytest.mark.parametrize("kind,dst,wording", [("generated", GEN, "AI-generated image"), ("edited", COMP, "AI-edited image"), ("unknown", GEN, "AI-generated or AI-edited image")])
def test_the_mark_is_inserted_parseable_and_the_pixels_are_unchanged(media, make, kind, dst, wording):
    original = make()
    marked = ai_marking.mark(original, media, kind)
    assert marked != original and len(marked) > len(original)
    assert source_type(xmp_of(marked, media)) == (dst, wording)
    assert pixels(marked) == pixels(original), "nothing was re-encoded"
    with Image.open(io.BytesIO(marked)) as im:
        im.load()
        assert im.format == {"image/png": "PNG", "image/jpeg": "JPEG", "image/webp": "WEBP"}[media]


def test_png_text_chunks_and_existing_chunks_are_kept():
    original = png_bytes(text={"Author": "Jane", "Software": "tool 1.0"})
    marked = ai_marking.mark(original, "image/png", "generated")
    with Image.open(io.BytesIO(marked)) as im:
        assert im.text["Author"] == "Jane" and im.text["Software"] == "tool 1.0", "what was there stays"
        assert im.text["AIGenerated"] == "true" and im.text["AIDisclosure"] == "AI-generated image" and im.text["DigitalSourceType"] == GEN
    for chunk in (b"IHDR", b"IDAT", b"IEND"):
        assert chunk in marked


def test_jpeg_exif_stays_and_the_comment_is_added():
    original = jpeg_bytes()
    marked = ai_marking.mark(original, "image/jpeg", "generated")
    with Image.open(io.BytesIO(marked)) as im:
        assert im.getexif()[0x010F] == "MyCamera", "the camera data that was there stays"
        assert im.info["comment"].startswith(b"AI: AI-generated image")
    assert marked[:2] == b"\xff\xd8" and marked.index(b"Exif") < marked.index(b"http://ns.adobe.com/xap/1.0/")


def test_webp_variants_simple_alpha_animated_and_with_exif():
    for make_kwargs in ({}, {"alpha": True}, {"animated": True}, {"exif": True}):
        original = webp_bytes(**make_kwargs)
        marked = ai_marking.mark(original, "image/webp", "generated")
        assert marked[:4] == b"RIFF" and struct.unpack("<I", marked[4:8])[0] == len(marked) - 8, make_kwargs
        assert source_type(xmp_of(marked, "image/webp"))[0] == GEN
        assert pixels(marked) == pixels(original), make_kwargs
        with Image.open(io.BytesIO(marked)) as im:
            assert im.n_frames == (3 if make_kwargs.get("animated") else 1)
            if make_kwargs.get("exif"):
                assert im.getexif()[0x010F] == "Cam"
            if make_kwargs.get("alpha"):
                assert im.convert("RGBA").getpixel((0, 0))[3] == 50


@pytest.mark.parametrize("media,make", CASES)
def test_marking_twice_does_not_stack(media, make):
    once = ai_marking.mark(make(), media, "generated")
    assert ai_marking.mark(once, media, "generated") == once


def test_an_existing_xmp_block_is_left_alone():
    xmp = b'<?xpacket begin="x"?><x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"/></x:xmpmeta><?xpacket end="w"?>'
    jpeg = jpeg_bytes()
    with_xmp = jpeg[:2] + b"\xff\xe1" + struct.pack(">H", 2 + 29 + len(xmp)) + b"http://ns.adobe.com/xap/1.0/\x00" + xmp + jpeg[2:]
    marked = ai_marking.mark(with_xmp, "image/jpeg", "generated")
    assert marked.count(b"http://ns.adobe.com/xap/1.0/\x00") == 1 and xmp in marked, "no second XMP segment; the existing one is intact"
    assert b"AI: AI-generated image" in marked, "the comment is still added"
    Image.open(io.BytesIO(marked)).load()


@pytest.mark.parametrize("media,data", [("image/png", b"not a png"), ("image/jpeg", b"nope"), ("image/webp", b"RIFFxxxx"), ("image/gif", b"GIF89a"), ("image/png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 3)])
def test_malformed_or_unsupported_pictures_raise_value_error(media, data):
    with pytest.raises(ValueError):
        ai_marking.mark(data, media, "generated")
    with pytest.raises(ValueError):
        ai_marking.mark(png_bytes(), "image/png", "mystery")


def test_the_wording_comes_from_the_settings(monkeypatch):
    monkeypatch.setattr(config, "AI_MARK_TEXT_GENERATED", "Gemaakt met AI <&>")
    marked = ai_marking.mark(png_bytes(), "image/png", "generated")
    assert source_type(xmp_of(marked, "image/png"))[1] == "Gemaakt met AI <&>", "escaped in XML, parsed back"


# ------------------------------------------------------------------------------------------------------ through the API
def finish(linked_output_env):
    job_id = linked_output_env["job_id"]
    assert process_one(worker_id="delivery-worker") is True
    out = client.get(f"/v1/generation-jobs/{job_id}/outputs", headers=A).json()["data"][0]
    return job_id, out["asset_id"]


def set_provider(provider):
    from tests.test_output_asset_link_worker import job_repository
    with job_repository._connect() as db:
        db.execute("UPDATE generation_jobs SET provider=?", (provider,))


def preview(asset_id):
    url = client.post(f"/v1/assets/{asset_id}/preview-url", headers=A).json()["url"]
    return client.get(url)


def test_a_mock_result_is_served_exactly_as_stored(linked_output_env):
    job_id, asset_id = finish(linked_output_env)
    r = client.get(f"/v1/generation-jobs/{job_id}/output", headers=A)
    assert r.status_code == 200 and r.content == linked_output_env["content"] and "x-ai-marked" not in r.headers, "the built-in mock is not AI"
    assert preview(asset_id).content == linked_output_env["content"]


@pytest.mark.parametrize("source,kind,dst", [("uploaded", "edited", COMP), ("platform_library_ai", "generated", GEN), ("unknown", "unknown", GEN)])
def test_an_ai_providers_result_is_marked_on_download_and_preview_by_input_source(linked_output_env, monkeypatch, source, kind, dst):
    import app.ai_disclosure as disclosure
    monkeypatch.setattr(disclosure, "input_source_of_job", lambda job: source)
    job_id, asset_id = finish(linked_output_env)
    set_provider("fashn")
    original = linked_output_env["content"]
    for r in (client.get(f"/v1/generation-jobs/{job_id}/output", headers=A), preview(asset_id)):
        assert r.status_code == 200 and r.headers["x-ai-marked"] == kind
        assert r.content != original and source_type(xmp_of(r.content, "image/png"))[0] == dst
        assert pixels(r.content) == pixels(original)
        assert r.headers["content-type"] == "image/png" and r.headers["cache-control"] == "private, no-store" and r.headers["content-length"] == str(len(r.content))
    stored = next(config.OUTPUT_DIR.glob(f"{job_id}.*"))
    assert hashlib.sha256(stored.read_bytes()).hexdigest() == linked_output_env["checksum"], "the stored file never changes"


def test_a_customers_own_upload_is_never_marked(linked_output_env):
    set_provider("fashn")
    buf = io.BytesIO(); Image.new("RGB", (20, 20), (1, 2, 3)).save(buf, format="PNG")
    up = client.post("/v1/assets/images", headers=A, data={"workspace_id": WS, "rights_confirmed": "true"}, files={"file": ("mine.png", buf.getvalue(), "image/png")}).json()
    r = preview(up["asset_id"])
    assert r.status_code == 200 and r.content == buf.getvalue() and "x-ai-marked" not in r.headers


def test_marking_can_be_switched_off_and_the_output_still_downloads(linked_output_env, monkeypatch):
    job_id, _ = finish(linked_output_env)
    set_provider("fashn")
    monkeypatch.setattr(config, "AI_MARKING_ENABLED", False)
    r = client.get(f"/v1/generation-jobs/{job_id}/output", headers=A)
    assert r.content == linked_output_env["content"] and "x-ai-marked" not in r.headers


def test_a_tampered_stored_file_still_fails_the_integrity_check_when_marking(linked_output_env):
    job_id, _ = finish(linked_output_env)
    set_provider("fashn")
    stored = next(config.OUTPUT_DIR.glob(f"{job_id}.*"))
    stored.write_bytes(stored.read_bytes() + b"x")
    assert client.get(f"/v1/generation-jobs/{job_id}/output", headers=A).status_code == 409


def test_the_real_defaults_are_on_with_the_default_wording():
    import os, subprocess, sys
    from pathlib import Path
    clean = {k: v for k, v in os.environ.items() if not k.startswith("AI_MARK")}
    out = subprocess.run([sys.executable, "-c", "import app.config as c; print(c.AI_MARKING_ENABLED, c.AI_MARK_TEXT_GENERATED, '|', c.AI_MARK_TEXT_EDITED)"],
                         cwd=Path(__file__).resolve().parents[1], env=clean, capture_output=True, text=True, check=True).stdout.strip()
    assert out == "True AI-generated image | AI-edited image"
