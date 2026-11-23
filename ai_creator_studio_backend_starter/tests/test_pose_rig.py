"""M5: joint rig + skinning of body and garments in five poses. Measurable properties only; the picture is scripts/pose_sheet.py (docs/POSES.md)."""
import math

import pytest

from app import pose_rig, render3d_scene

SEX = "female"


@pytest.fixture(scope="module")
def scene():
    body, layers, _ = render3d_scene.build_layers(SEX, None, ["top", "bottom"])
    return body, layers, pose_rig.Skeleton(SEX)


def points(tris):
    return [c for t in tris for c in t[0]]


def test_weights_are_a_partition_of_one_with_at_most_four_bones(scene):
    _, _, skel = scene
    for p in ((0.0, 1.0, 0.0), (0.17, 1.2, 0.05), (-0.1, 0.3, 0.0), (0.3, 0.9, 0.0)):
        w = pose_rig.skin_weights(skel, p)
        assert 1 <= len(w) <= pose_rig.MAX_BONES_PER_VERTEX and abs(sum(x for _, x in w) - 1) < 1e-9


def test_standing_keeps_the_shape_and_only_puts_the_feet_on_the_floor(scene):
    body, layers, skel = scene
    (moved, *_), lift = pose_rig.skin_triangles(skel, [body], "standing")
    assert abs(lift) < 0.02
    a, b = points(body), points(moved)
    assert max(math.dist(p, q) for p, q in zip(a, b)) < 0.02 + abs(lift)


@pytest.mark.parametrize("pose", pose_rig.POSES)
def test_every_pose_rests_on_the_floor_and_keeps_all_triangles(scene, pose):
    body, layers, skel = scene
    moved, _ = pose_rig.skin_triangles(skel, [body] + [t for _, t, _ in layers], pose)
    assert [len(m) for m in moved] == [len(body)] + [len(t) for _, t, _ in layers]
    assert abs(min(c[1] for c in points(moved[0]))) < 1e-9
    assert all(math.isfinite(v) for p in points(moved[0]) for v in p)


def test_the_poses_actually_move_the_limbs(scene):
    body, _, skel = scene
    base = {c: i for i, c in enumerate(points(body))}
    def extent(pose, axis):
        (m,), _ = pose_rig.skin_triangles(skel, [body], pose)
        vals = [c[axis] for c in points(m)]
        return min(vals), max(vals)
    assert extent("arms_raised", 1)[1] > extent("standing", 1)[1] + 0.05        # hands above the head
    assert extent("sitting", 1)[1] < extent("standing", 1)[1] - 0.2              # clearly lower (seated head ~0.27 m lower)
    z0, z1 = extent("sitting", 2)
    assert z1 - z0 > extent("standing", 2)[1] - extent("standing", 2)[0] + 0.4   # the thighs stick out forwards
    w0, w1 = extent("walking", 2)
    assert w1 - w0 > 0.5                                                         # a stride
    assert sorted(set(base))  # keep the fixture used


def test_arms_raised_is_left_right_symmetric(scene):
    body, _, skel = scene
    (m,), _ = pose_rig.skin_triangles(skel, [body], "arms_raised")
    xs = [c[0] for c in points(m)]
    assert abs(max(xs) + min(xs)) < 0.01


def test_a_garment_follows_the_body_it_was_fitted_to(scene):
    body, layers, skel = scene
    moved, _ = pose_rig.skin_triangles(skel, [body, layers[0][1]], "arms_raised")
    body_pts, top_pts = points(moved[0]), points(moved[1])
    near = [min(math.dist(t, b) for b in body_pts[::7]) for t in top_pts[::11]]
    assert max(near) < 0.12                                         # no garment vertex is left behind far from the body


def test_penetration_is_measured_per_pose_and_stays_within_the_pinned_limit():
    for pose in pose_rig.POSES:
        r = pose_rig.measure_pose(SEX, None, ["top", "bottom"], pose, angles=(0, 90, 180))
        for g in r["garments"]:
            assert g["visible_share_min"] is not None and g["visible_share_min"] >= 0.85, (pose, g)       # documented limit of linear blend skinning, docs/POSES.md


def test_unknown_pose_is_refused_and_the_result_is_deterministic(scene):
    body, _, skel = scene
    with pytest.raises(ValueError):
        pose_rig.skin_triangles(skel, [body], "dancing")
    a, _ = pose_rig.skin_triangles(skel, [body], "walking")
    b, _ = pose_rig.skin_triangles(skel, [body], "walking")
    assert points(a[0]) == points(b[0])
