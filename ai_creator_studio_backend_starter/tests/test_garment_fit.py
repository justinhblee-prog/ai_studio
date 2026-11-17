"""R-ENGINE-03a: a top shell fitted around the mannequin. The clearance checks read the MESHES inside the finished .glb (not the module's own numbers)."""
import math
import struct

import pytest

from app.assets.validation import validate_gltf_upload
from app.garment_fit import MIN_GAP_CM, RINGS, build_fitted_glb, ring_plan
from app.glb_tools import inspect_glb, parse_glb
from app.mannequin import SEGMENTS, Measurements, SizeChart

M = Measurements(height_cm=170, chest_cm=92, waist_cm=76, hips_cm=98)
CHART = SizeChart(sizes={"S": {"chest": 94, "waist": 80, "hips": 100}, "M": {"chest": 100, "waist": 86, "hips": 106}, "L": {"chest": 108, "waist": 94, "hips": 114}})


def meshes(glb):
    """[(positions, triangles)] for every mesh of the .glb, read from its own buffers."""
    doc, binary = parse_glb(glb)
    out = []
    for mesh in doc["meshes"]:
        prim = mesh["primitives"][0]
        pos_acc, idx_acc = doc["accessors"][prim["attributes"]["POSITION"]], doc["accessors"][prim["indices"]]
        pv, iv = doc["bufferViews"][pos_acc["bufferView"]], doc["bufferViews"][idx_acc["bufferView"]]
        flat = struct.unpack_from(f"<{pos_acc['count'] * 3}f", binary, pv["byteOffset"])
        idx = struct.unpack_from(f"<{idx_acc['count']}H", binary, iv["byteOffset"])
        out.append(([flat[i:i + 3] for i in range(0, len(flat), 3)], [idx[i:i + 3] for i in range(0, len(idx), 3)]))
    return out


def body_polygon(body_verts, y):
    """The mannequin's own cross-section (a convex SEGMENTS-gon) at height y, interpolated between its rings."""
    rows = (len(body_verts) - 1) // SEGMENTS
    ys = [body_verts[r * SEGMENTS][1] for r in range(rows)]
    for r in range(rows - 1):
        if ys[r] - 1e-9 <= y <= ys[r + 1] + 1e-9:
            t = (y - ys[r]) / (ys[r + 1] - ys[r])
            return [((1 - t) * body_verts[r * SEGMENTS + i][0] + t * body_verts[(r + 1) * SEGMENTS + i][0],
                     (1 - t) * body_verts[r * SEGMENTS + i][2] + t * body_verts[(r + 1) * SEGMENTS + i][2]) for i in range(SEGMENTS)]
    raise AssertionError(f"height {y} is outside the body")


def strictly_inside(poly, x, z, eps=1e-7):
    signs = []
    for i in range(len(poly)):
        (x0, z0), (x1, z1) = poly[i], poly[(i + 1) % len(poly)]
        signs.append((x1 - x0) * (z - z0) - (z1 - z0) * (x - x0))
    return all(s > eps for s in signs) or all(s < -eps for s in signs)


def samples(verts, tris):
    for a, b, c in tris:
        pts = [verts[a], verts[b], verts[c]]
        for p, q in ((pts[0], pts[1]), (pts[1], pts[2]), (pts[2], pts[0])):
            for k in range(11):
                t = k / 10
                yield tuple((1 - t) * p[j] + t * q[j] for j in range(3))
        yield tuple(sum(p[j] for p in pts) / 3 for j in range(3))


def test_the_result_is_one_valid_glb_with_the_body_and_a_garment_marked_as_reference():
    glb, report = build_fitted_glb(M, CHART, "M")
    assert validate_gltf_upload("fit.glb", glb).media_type == "model/gltf-binary"
    doc = parse_glb(glb)[0]
    assert [n["name"] for n in doc["nodes"]] == ["mannequin", "garment_top"] and doc["scenes"][0]["nodes"] == [0, 1]
    assert [m["name"] for m in doc["materials"]] == ["skin", "garment"]
    extras = doc["nodes"][1]["extras"]
    assert extras["approximate"] is True and extras["is_reconstruction"] is False and extras["not_a_simulation"] is True and extras["size"] == "M"
    assert inspect_glb(glb)["meshes"] == 2
    assert report["reference_only"] is True and "no cloth simulation" in report["method"] and report["label_ko"] and report["label_en"]


def test_the_shell_never_cuts_into_the_body_for_every_size_even_one_that_is_too_small():
    for size in CHART.sizes:                                    # "S" is too small for this body with a woven fabric: it must still not poke through
        glb, report = build_fitted_glb(M, CHART, size)
        (body_verts, _), (shell_verts, shell_tris) = meshes(glb)
        checked = 0
        for x, y, z in samples(shell_verts, shell_tris):
            assert not strictly_inside(body_polygon(body_verts, y), x, z), (size, x, y, z)
            checked += 1
        assert checked > 1000, "the check really looked at the mesh"
        assert report["cannot_fit"] is (size == "S")


def test_at_every_ring_the_clearance_is_at_least_the_minimum_gap_in_centimetres():
    for size in CHART.sizes:
        glb, _ = build_fitted_glb(M, CHART, size)
        (body_verts, _), (shell_verts, _) = meshes(glb)
        for ring, (share, _) in enumerate(RINGS):
            y = share * 1.70
            body = body_polygon(body_verts, y)
            for i in range(SEGMENTS):
                sx, sy, sz = shell_verts[ring * SEGMENTS + i]
                assert sy == pytest.approx(y, abs=1e-5)
                clearance_cm = (math.hypot(sx, sz) - math.hypot(*body[i])) * 100
                assert clearance_cm >= MIN_GAP_CM * 0.95, (size, ring, i, clearance_cm)      # float32 positions: a hair of tolerance


def test_a_bigger_size_gives_a_bigger_shell_at_every_ring_and_the_numbers_come_from_the_chart():
    rings = {s: ring_plan(M, CHART, s) for s in CHART.sizes}
    for r in range(len(RINGS)):
        assert rings["S"][r]["shell_cm"] < rings["M"][r]["shell_cm"] < rings["L"][r]["shell_cm"]
    assert [r["shell_cm"] for r in rings["M"]] == [106.0, 86.0, 100.0, 100.0], "a size that already clears the body keeps its printed circumference"
    assert all(r["state"] == "ok" for r in rings["M"] + rings["L"])


def test_a_too_small_size_is_reported_not_hidden_and_a_stretchy_fabric_can_save_it():
    woven = ring_plan(M, CHART, "S")
    assert {r["state"] for r in woven} == {"cannot_fit", "ok"} and any(r["state"] == "cannot_fit" for r in woven)
    knit = SizeChart(sizes=CHART.sizes, stretch=0.1)
    stretchy = ring_plan(M, knit, "S")
    assert not any(r["state"] == "cannot_fit" for r in stretchy) and any(r["state"] == "stretched" for r in stretchy)
    assert build_fitted_glb(M, knit, "S")[1]["cannot_fit"] is False and build_fitted_glb(M, knit, "S")[1]["stretched"] is True


def test_the_same_input_gives_the_same_bytes_and_a_different_body_gives_different_geometry():
    assert build_fitted_glb(M, CHART, "M")[0] == build_fitted_glb(M, CHART, "M")[0]
    other = Measurements(height_cm=180, chest_cm=104, waist_cm=90, hips_cm=108)
    assert build_fitted_glb(other, CHART, "M")[0] != build_fitted_glb(M, CHART, "M")[0]


def test_unknown_sizes_and_charts_without_a_needed_measurement_are_refused():
    with pytest.raises(ValueError):
        build_fitted_glb(M, CHART, "XXL")
    with pytest.raises(ValueError):
        ring_plan(M, SizeChart(sizes={"M": {"chest": 100, "waist": 86}}), "M")
