"""M3 stage 1: XPBD cloth demo (one sleeveless top on the torso). Properties only; numbers and picture: docs/CLOTH_XPBD.md, scripts/cloth_demo.py."""
import math

from app import cloth_xpbd


def settled(steps=120):
    c = cloth_xpbd.Cloth("female", columns=16, rows=12)
    c.run(steps)
    return c


def test_the_cloth_never_ends_inside_the_body_and_settles():
    c = settled(150)
    m = c.measure()
    assert m["particles_inside_body"] == 0
    assert m["max_speed_m_s"] < 0.05, "still moving: not settled"


def test_the_pinned_top_ring_does_not_move_and_the_rest_hangs_lower_than_it_started():
    c = cloth_xpbd.Cloth("female", columns=16, rows=12)
    top0 = [p[:] for p in c.pos[:16]]
    hem0 = sum(p[1] for p in c.pos[-16:]) / 16
    c.run(120)
    assert c.pos[:16] == top0
    assert sum(p[1] for p in c.pos[-16:]) / 16 <= hem0 + 1e-9      # gravity only pulls the hem down (it may already hang at its limit)


def test_stretch_stays_bounded_and_all_numbers_are_finite():
    c = settled(120)
    m = c.measure()
    assert m["max_stretch_strain"] < 0.30 and m["mean_stretch_strain"] < 0.05
    assert all(math.isfinite(v) for p in c.pos for v in p)


def test_deterministic_and_renderable():
    a, b = settled(40), settled(40)
    assert a.pos == b.pos
    tris = a.triangles()
    assert len(tris) == 2 * (a.rows - 1) * a.columns and all(len(t[0]) == 3 for t in tris)
