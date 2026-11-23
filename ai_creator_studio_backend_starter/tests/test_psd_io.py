"""R-PSD-01: PSD/PSB writer + reader. Round trips, layer names/order/hidden state, 16-bit, PSB, blank-merged fallback, limits, damaged files.
Not yet checked against Photoshop / Photopea themselves (미확인); Pillow's own PSD reader is used as an independent check of the merged image."""
import io
import struct

import pytest
from PIL import Image

from app import psd_io

SIZE = (40, 30)


def layers():
    bg = Image.new("RGBA", SIZE, (200, 220, 255, 255))
    subject = Image.new("RGBA", (16, 20), (220, 40, 60, 255))
    ref = Image.new("RGBA", SIZE, (10, 10, 10, 255))
    return [psd_io.Layer("원본 (참고)", ref, visible=False), psd_io.Layer("배경", bg), psd_io.Layer("피사체", subject, x=12, y=5, opacity=255)]


def merged():
    img = Image.new("RGB", SIZE, (200, 220, 255))
    img.paste(Image.new("RGB", (16, 20), (220, 40, 60)), (12, 5))
    return img


@pytest.mark.parametrize("version", [1, 2])
@pytest.mark.parametrize("depth", [8, 16])
@pytest.mark.parametrize("compat", [False, True])
def test_round_trip_keeps_names_order_visibility_position_and_pixels(version, depth, compat):
    data = psd_io.write_psd(layers(), SIZE, merged(), depth=depth, version=version, compat=compat)
    assert data[:4] == b"8BPS" and struct.unpack(">H", data[4:6])[0] == version
    psd = psd_io.read_psd(data)
    assert (psd.width, psd.height, psd.depth, psd.version) == (*SIZE, depth, version)
    assert [l.name for l in psd.layers] == ["원본 (참고)", "배경", "피사체"]
    assert [l.visible for l in psd.layers] == [False, True, True]
    assert (psd.layers[2].x, psd.layers[2].y, psd.layers[2].image.size) == (12, 5, (16, 20))
    assert psd.layers[2].image.getpixel((3, 3)) == (220, 40, 60, 255) and psd.layers[1].image.getpixel((0, 0)) == (200, 220, 255, 255)
    assert psd.merged is not None and psd.merged.getpixel((15, 10)) == (220, 40, 60) and psd.merged.getpixel((0, 0)) == (200, 220, 255)
    assert psd.icc and psd.icc[36:40] == b"acsp" and b"mntrRGB" in psd.icc[:24]       # a real ICC display profile for RGB


def test_transparency_survives_in_a_layer():
    cut = Image.new("RGBA", (8, 8), (255, 0, 0, 0))
    cut.putpixel((2, 2), (255, 0, 0, 255))
    psd = psd_io.read_psd(psd_io.write_psd([psd_io.Layer("누끼", cut)], (8, 8), Image.new("RGB", (8, 8), (255, 255, 255))))
    assert psd.layers[0].image.getpixel((2, 2))[3] == 255 and psd.layers[0].image.getpixel((0, 0))[3] == 0


def test_pillow_reads_the_merged_image_of_our_file():
    data = psd_io.write_psd(layers(), SIZE, merged(), compat=True)
    img = Image.open(io.BytesIO(data))
    img.load()
    assert img.size == SIZE and img.convert("RGB").getpixel((15, 10)) == (220, 40, 60)


def test_a_file_without_a_usable_merged_image_is_read_through_its_layers():
    data = bytearray(psd_io.write_psd(layers(), SIZE, merged()))
    blank = psd_io.read_psd(bytes(data))
    blank.merged = Image.new("RGB", SIZE, (255, 255, 255))                     # an application that wrote an empty (white) merged image
    img, how = psd_io.to_image(blank)
    assert how == "layers" and img.getpixel((15, 10)) == (220, 40, 60) and img.getpixel((0, 0)) == (200, 220, 255), "the hidden reference layer is not painted"
    blank.merged = None
    assert psd_io.to_image(blank)[1] == "layers"
    ok = psd_io.read_psd(bytes(data))
    assert psd_io.to_image(ok)[1] == "merged"


def test_truncated_text_garbage_and_oversized_files_are_refused_with_codes():
    data = psd_io.write_psd(layers(), SIZE, merged())
    for bad, code in ((b"not a psd at all", "PSD_NOT_PSD"), (data[:60], "PSD_CORRUPT"), (data[:300], "PSD_CORRUPT")):
        with pytest.raises(psd_io.PsdError) as e:
            psd_io.read_psd(bad)
        assert e.value.code == code
    with pytest.raises(psd_io.PsdError) as e:
        psd_io.read_psd(b"8BPS" + b"\x00" * (psd_io.MAX_BYTES + 1))
    assert e.value.code == "PSD_TOO_LARGE"


def test_cmyk_and_32_bit_files_are_refused_as_unsupported():
    data = bytearray(psd_io.write_psd(layers(), SIZE, merged()))
    cmyk = bytearray(data)
    cmyk[24:26] = struct.pack(">H", 4)                                          # colour mode 4 = CMYK
    with pytest.raises(psd_io.PsdError) as e:
        psd_io.read_psd(bytes(cmyk))
    assert e.value.code == "PSD_UNSUPPORTED"
    deep = bytearray(data)
    deep[22:24] = struct.pack(">H", 32)
    with pytest.raises(psd_io.PsdError) as e:
        psd_io.read_psd(bytes(deep))
    assert e.value.code == "PSD_UNSUPPORTED"


def test_writer_limits():
    with pytest.raises(psd_io.PsdError):
        psd_io.write_psd([], (30001, 10), Image.new("RGB", (30001, 10)), version=1)
    with pytest.raises(psd_io.PsdError):
        psd_io.write_psd([], SIZE, merged(), depth=32)
    with pytest.raises(psd_io.PsdError):
        psd_io.write_psd([psd_io.Layer(str(i), Image.new("RGBA", (1, 1))) for i in range(psd_io.MAX_LAYERS + 1)], (1, 1), Image.new("RGB", (1, 1)))


def test_zip_with_prediction_channels_are_decoded():
    # hand-built reader check for compression 3 on a layer channel of a tiny picture
    import zlib
    row = bytes([10, 20, 30, 40])
    delta = bytes([row[0]] + [(row[i] - row[i - 1]) & 255 for i in range(1, 4)])
    plane = psd_io._undo_prediction(delta, 4, 1, 8)
    assert plane == row
    assert zlib.decompress(zlib.compress(delta)) == delta


def test_deterministic_and_icc_can_be_left_out():
    a, b = psd_io.write_psd(layers(), SIZE, merged()), psd_io.write_psd(layers(), SIZE, merged())
    assert a == b
    assert psd_io.read_psd(psd_io.write_psd(layers(), SIZE, merged(), icc=False)).icc is None
