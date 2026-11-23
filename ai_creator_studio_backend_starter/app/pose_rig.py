"""M5: a small joint rig + linear blend skinning for the own3d scene, so the body AND the fitted garments can be shown in five poses (standing, walking, hand on hip, sitting, arms raised).

Pure Python, no model, no new dependency. The rig is derived from the same body preset the mesh is built from (``base_models.PRESETS`` / ``_fit_measurements``), so the joints sit where the mesh's
shoulders, elbows, hips and knees are. Skinning works on ``render3d_soft.Triangle`` lists (corner positions, normals, colour): the weights come from each vertex's POSITION only, so a garment
fitted to the body follows it with the same weights as the body itself - no separate garment rig.
What it is NOT: linear blend skinning pinches at deep bends (armpit with arms raised, the back of a bent knee), the weights are distance based (no painted weights, no muscle or cloth simulation),
and a garment is only moved with the body, never re-draped. Penetration is MEASURED (``measure_pose`` -> ``render_qc.check_cuts``), not prevented.
"""
from __future__ import annotations

import math
from typing import Any

from app import base_models, render_qc, render3d_scene, render3d_soft
from app.render3d_soft import Triangle

Vec = tuple[float, float, float]
POSES = ("standing", "walking", "hand_on_hip", "sitting", "arms_raised")
SIDES = (("r", 1.0), ("l", -1.0))            # right = +x, as in base_models.body_profiles
WEIGHT_POWER = 3.0
WEIGHT_FLOOR = 0.008                           # metres: keeps a vertex exactly on a bone finite
MAX_BONES_PER_VERTEX = 4

# pose = {joint name: (rx, ry, rz) in degrees}, applied at the joint and inherited by everything below it.
# Axes: x right, y up, z towards the viewer (front). A thigh swung FORWARD is a NEGATIVE rx; a knee bends with a POSITIVE rx; an arm swung out sideways is rz > 0 on the right side, < 0 on the left.
POSE_DEGREES: dict[str, dict[str, Vec]] = {
    "standing": {},
    "walking": {
        "hip_l": (-22.0, 0.0, 0.0), "knee_l": (6.0, 0.0, 0.0), "ankle_l": (8.0, 0.0, 0.0),
        "hip_r": (16.0, 0.0, 0.0), "knee_r": (26.0, 0.0, 0.0), "ankle_r": (-12.0, 0.0, 0.0),
        "shoulder_l": (16.0, 0.0, 0.0), "elbow_l": (-10.0, 0.0, 0.0),
        "shoulder_r": (-20.0, 0.0, 0.0), "elbow_r": (-28.0, 0.0, 0.0),
        "pelvis": (0.0, 5.0, 0.0), "spine": (0.0, -7.0, 0.0),
    },
    "hand_on_hip": {
        "shoulder_r": (-4.0, 0.0, 34.0), "elbow_r": (0.0, 0.0, -118.0), "wrist_r": (0.0, 0.0, 12.0),
        "shoulder_l": (0.0, 0.0, -4.0),
        "pelvis": (0.0, 0.0, 2.0), "hip_r": (0.0, 0.0, -3.0), "hip_l": (0.0, 0.0, 2.0),
    },
    "sitting": {
        "hip_r": (-90.0, 0.0, 2.0), "hip_l": (-90.0, 0.0, -2.0), "knee_r": (92.0, 0.0, 0.0), "knee_l": (92.0, 0.0, 0.0),
        "ankle_r": (-2.0, 0.0, 0.0), "ankle_l": (-2.0, 0.0, 0.0),
        "shoulder_r": (-28.0, 0.0, 6.0), "elbow_r": (-62.0, 0.0, 0.0), "shoulder_l": (-28.0, 0.0, -6.0), "elbow_l": (-62.0, 0.0, 0.0),
        "spine": (4.0, 0.0, 0.0),
    },
    "arms_raised": {
        "shoulder_r": (0.0, 0.0, 152.0), "elbow_r": (0.0, 0.0, 6.0), "shoulder_l": (0.0, 0.0, -152.0), "elbow_l": (0.0, 0.0, -6.0),
    },
}


def _sub(a: Vec, b: Vec) -> Vec:
    return a[0] - b[0], a[1] - b[1], a[2] - b[2]


def _rotation(rx: float, ry: float, rz: float) -> tuple[tuple[float, float, float], ...]:
    """3x3 rotation, applied as Rz * Ry * Rx (x first), angles in degrees."""
    ax, ay, az = math.radians(rx), math.radians(ry), math.radians(rz)
    cx, sx, cy, sy, cz, sz = math.cos(ax), math.sin(ax), math.cos(ay), math.sin(ay), math.cos(az), math.sin(az)
    rx_m = ((1, 0, 0), (0, cx, -sx), (0, sx, cx))
    ry_m = ((cy, 0, sy), (0, 1, 0), (-sy, 0, cy))
    rz_m = ((cz, -sz, 0), (sz, cz, 0), (0, 0, 1))
    return _mul3(rz_m, _mul3(ry_m, rx_m))


def _mul3(a, b):
    return tuple(tuple(sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)) for i in range(3))


Affine = tuple[tuple[tuple[float, float, float], ...], Vec]       # (3x3, translation)


def _compose(a: Affine, b: Affine) -> Affine:
    """a after b."""
    rot = _mul3(a[0], b[0])
    t = tuple(sum(a[0][i][k] * b[1][k] for k in range(3)) + a[1][i] for i in range(3))
    return rot, t     # type: ignore[return-value]


def _about(pivot: Vec, rot) -> Affine:
    """Rotate about ``pivot``: x -> R (x - pivot) + pivot."""
    t = tuple(pivot[i] - sum(rot[i][k] * pivot[k] for k in range(3)) for i in range(3))
    return rot, t     # type: ignore[return-value]


IDENTITY: Affine = (((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)), (0.0, 0.0, 0.0))


class Skeleton:
    """Joints, their parents and the bones (segments) the skin weights are measured against, all in the rest pose of one body."""

    def __init__(self, sex: str, measurements: dict[str, float] | None = None) -> None:
        p = base_models._fit_measurements(base_models.PRESETS[sex], measurements or {}) if measurements else dict(base_models.PRESETS[sex])
        h, sh = p["height"], p["shoulder"]
        leg_x = p["hip"][0] * 0.52
        shoulder_y = 0.81 * h
        self.height = h
        joints: dict[str, tuple[str | None, Vec]] = {
            "pelvis": (None, (0.0, 0.52 * h, 0.0)),
            "spine": ("pelvis", (0.0, 0.65 * h, 0.0)),
            "neck": ("spine", (0.0, shoulder_y, 0.0)),
        }
        bones: list[tuple[str, str, Vec, Vec, float]] = [     # (name, driving joint, start, end, radius)
            ("pelvis", "pelvis", (0.0, 0.52 * h, 0.0), (0.0, 0.65 * h, 0.0), p["hip"][0] * 1.0),
            ("spine", "spine", (0.0, 0.65 * h, 0.0), (0.0, shoulder_y, 0.0), p["chest"][0] * 0.95),
            ("head", "neck", (0.0, shoulder_y, 0.0), (0.0, h, 0.0), p["head"] * 0.9),
        ]
        for tag, side in SIDES:
            shoulder = (side * sh * 0.78, shoulder_y - 0.035, 0.0)
            elbow = (side * (sh + 0.045), shoulder_y - 0.21 * h, 0.0)
            wrist = (side * (sh + 0.115), shoulder_y - 0.40 * h, 0.015)
            hand_end = (wrist[0] + side * 0.012, wrist[1] - 0.085, wrist[2])
            hip = (side * leg_x, 0.52 * h, 0.0)
            knee = (side * leg_x * 0.97, 0.36 * h, 0.0)
            ankle = (side * leg_x * 0.90, 0.04 * h, 0.0)
            toe = (ankle[0], 0.012, 0.11)
            joints.update({f"shoulder_{tag}": ("spine", shoulder), f"elbow_{tag}": (f"shoulder_{tag}", elbow), f"wrist_{tag}": (f"elbow_{tag}", wrist),
                           f"hip_{tag}": ("pelvis", hip), f"knee_{tag}": (f"hip_{tag}", knee), f"ankle_{tag}": (f"knee_{tag}", ankle)})
            ar = p["arm"]
            bones += [(f"upper_arm_{tag}", f"shoulder_{tag}", shoulder, elbow, ar * 1.3), (f"forearm_{tag}", f"elbow_{tag}", elbow, wrist, ar * 0.95),
                      (f"hand_{tag}", f"wrist_{tag}", wrist, hand_end, ar * 0.7),
                      (f"thigh_{tag}", f"hip_{tag}", hip, knee, p["thigh"] * 0.95), (f"calf_{tag}", f"knee_{tag}", knee, ankle, p["calf"] * 0.9),
                      (f"foot_{tag}", f"ankle_{tag}", ankle, toe, p["calf"] * 0.6)]
        self.joints = joints
        self.bones = bones
        self.order = list(joints)                  # parents come before children by construction

    def joint_transforms(self, pose: dict[str, Vec]) -> dict[str, Affine]:
        """Rest space -> posed space, per joint (the joint's own rotation about its rest position, after its parent's transform)."""
        out: dict[str, Affine] = {}
        for name in self.order:
            parent, position = self.joints[name]
            local = _about(position, _rotation(*pose.get(name, (0.0, 0.0, 0.0))))
            out[name] = local if parent is None else _compose(out[parent], local)
        return out


def _segment_distance(p: Vec, a: Vec, b: Vec) -> float:
    ab, ap = _sub(b, a), _sub(p, a)
    length2 = ab[0] * ab[0] + ab[1] * ab[1] + ab[2] * ab[2]
    t = 0.0 if length2 == 0 else max(0.0, min(1.0, (ap[0] * ab[0] + ap[1] * ab[1] + ap[2] * ab[2]) / length2))
    return math.dist(p, (a[0] + ab[0] * t, a[1] + ab[1] * t, a[2] + ab[2] * t))


def skin_weights(skeleton: Skeleton, point: Vec) -> list[tuple[int, float]]:
    """[(bone index, weight)] summing to 1, from the distance to each bone's surface (segment distance minus the bone's radius), the nearest ``MAX_BONES_PER_VERTEX`` kept."""
    raw = []
    for index, (_, _, a, b, radius) in enumerate(skeleton.bones):
        d = max(_segment_distance(point, a, b) - radius, 0.0) + WEIGHT_FLOOR
        raw.append((1.0 / d ** WEIGHT_POWER, index))
    raw.sort(reverse=True)
    kept = raw[:MAX_BONES_PER_VERTEX]
    total = sum(w for w, _ in kept)
    return [(i, w / total) for w, i in kept]


def _apply(m: Affine, p: Vec) -> Vec:
    r, t = m
    return (r[0][0] * p[0] + r[0][1] * p[1] + r[0][2] * p[2] + t[0], r[1][0] * p[0] + r[1][1] * p[1] + r[1][2] * p[2] + t[1], r[2][0] * p[0] + r[2][1] * p[1] + r[2][2] * p[2] + t[2])


def _turn(m: Affine, n: Vec) -> Vec:
    r = m[0]
    return r[0][0] * n[0] + r[0][1] * n[1] + r[0][2] * n[2], r[1][0] * n[0] + r[1][1] * n[1] + r[1][2] * n[2], r[2][0] * n[0] + r[2][1] * n[1] + r[2][2] * n[2]


def pose_degrees(name: str) -> dict[str, Vec]:
    if name not in POSE_DEGREES:
        raise ValueError(f"unknown pose {name!r}; one of {', '.join(POSES)}")
    return POSE_DEGREES[name]


def skin_triangles(skeleton: Skeleton, groups: list[list[Triangle]], pose_name: str) -> tuple[list[list[Triangle]], float]:
    """The triangle lists of ``groups`` (body, garments...) moved into ``pose_name``, and the vertical offset applied so the lowest point rests on the floor (y = 0).
    Weights are cached per rest position, so a corner shared by several triangles - or by the body and a garment at the same place - is weighted once."""
    joint_t = skeleton.joint_transforms(pose_degrees(pose_name))
    bone_t = [joint_t[joint] for _, joint, _, _, _ in skeleton.bones]
    cache: dict[Vec, list[tuple[int, float]]] = {}

    def move(point: Vec) -> Vec:
        key = (round(point[0], 5), round(point[1], 5), round(point[2], 5))
        weights = cache.get(key)
        if weights is None:
            weights = cache[key] = skin_weights(skeleton, point)
        x = y = z = 0.0
        for index, w in weights:
            q = _apply(bone_t[index], point)
            x, y, z = x + w * q[0], y + w * q[1], z + w * q[2]
        return x, y, z

    def turn(point: Vec, normal: Vec) -> Vec:
        key = (round(point[0], 5), round(point[1], 5), round(point[2], 5))
        weights = cache.get(key) or skin_weights(skeleton, point)
        x = y = z = 0.0
        for index, w in weights:
            q = _turn(bone_t[index], normal)
            x, y, z = x + w * q[0], y + w * q[1], z + w * q[2]
        length = math.sqrt(x * x + y * y + z * z) or 1.0
        return x / length, y / length, z / length

    moved: list[list[Triangle]] = []
    for tris in groups:
        out = []
        for corners, normals, rgb in tris:
            out.append((tuple(move(c) for c in corners), tuple(turn(c, n) for c, n in zip(corners, normals)), rgb))     # type: ignore[arg-type]
        moved.append(out)
    floor = min(c[1] for tris in moved for t in tris for c in t[0])
    lifted = [[(tuple((c[0], c[1] - floor, c[2]) for c in t[0]), t[1], t[2]) for t in tris] for tris in moved]       # type: ignore[misc]
    return lifted, -floor


def posed_scene(sex: str, measurements: dict[str, float] | None, garment_kinds: list[str], pose_name: str):
    """(skeleton, posed body, [(kind, posed garment triangles, colour)], fitting reports) for ``pose_name``."""
    body, layers, reports = render3d_scene.build_layers(sex, measurements, garment_kinds)
    skeleton = Skeleton(sex, measurements)
    moved, _ = skin_triangles(skeleton, [body] + [tris for _, tris, _ in layers], pose_name)
    return skeleton, moved[0], [(kind, moved[1 + i], colour) for i, (kind, _, colour) in enumerate(layers)], reports


def measure_pose(sex: str, measurements: dict[str, float] | None, garment_kinds: list[str], pose_name: str, angles: tuple[int, ...] = (0, 45, 90, 180, 270)) -> dict[str, Any]:
    """Penetration of the garments by the posed body, measured with ``render_qc.check_cuts`` (visible share of each garment from the given angles) - NOT prevented, only reported.
    ``ok`` is the render check's own verdict for the pose; the numbers are what to look at."""
    _, body, layers, reports = posed_scene(sex, measurements, garment_kinds, pose_name)
    report = render_qc.check_cuts(body, layers, angles, penetrations=None)
    return {"pose": pose_name, "angles": list(angles), "garments": [{"kind": g["kind"], "visible_share_min": g["visible_share_min"], "colour_distance_max": g["colour_distance_max"],
                                                                    "ok": g.get("passed")} for g in report["garments"]], "rest_fit": reports, "ok": report.get("passed")}


__all__ = ["POSES", "Skeleton", "skin_triangles", "posed_scene", "measure_pose", "pose_degrees", "render3d_soft"]
