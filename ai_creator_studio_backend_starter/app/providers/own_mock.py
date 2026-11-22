"""R-ENGINE-04 / R-ENGINE-07 (slot only): the in-house engine ``own3d`` as a MOCK provider that plugs into the same start/status contract as ``mock`` and ``fashn``.

What it does: builds a sample garment (``app/garments.py``), deforms it to the requested body measurements (``app/garment_deform.py``) and reports the result. It is the
flow of the own 3D engine (track A) behind the provider contract, so the rest of the system can be wired and tested before any real engine exists.
What it is NOT: no image, no photo, no GPU, no model weights, no paid call, no review score (the 5-item review of the plan is NOT run here: every score is ``None``).
One name (D-66a, R-ENGINE-07): this mock IS the mock implementation of ``own3d``; the registry keeps exactly ONE ``own3d`` record (the closed slot of R-ENGINE-05) and this class adds no second one.
Fitting uses ONLY the garment.v1 mesh deformation (R-ENGINE-03b, ``app/garment_deform.py``, canonical per D-66b); the older ring-shell ``app/garment_fit.py`` (03a) is not on this path.
It is not selectable through ``PROVIDER_MODE`` (``main.py`` is unchanged) and the registry slot stays closed (never dispatchable, never production eligible).
A fitting that is refused (the garment would pass through the body) ends as ``failed`` with ``charged: False`` (the "no deduction on failure" rule of the plan).
"""
from __future__ import annotations

import hashlib
import json
from collections import OrderedDict
from typing import Any

from app import base_models, garments, render3d_scene, render_qc
from app.garment_deform import deform_garment

REVIEW_ITEMS = ("logo", "text", "pattern", "hands", "length")
QC_ANGLES = (0, 90, 180, 270)                      # the cuts the render check looks at (R-ENGINE-11)
MAX_KEPT = 256                                  # results kept in memory (a mock: nothing is stored durably)
_RESULTS: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
_GLBS: dict[str, bytes] = {}


def _clean(payload: dict) -> dict[str, Any]:
    sex, kind = payload.get("sex"), payload.get("garment_kind")
    if sex not in base_models.SEXES:
        raise ValueError(f"sex must be one of {list(base_models.SEXES)}")
    if kind not in garments.KINDS:
        raise ValueError(f"garment_kind must be one of {list(garments.KINDS)}")
    measurements = payload.get("measurements") or {}
    if not isinstance(measurements, dict):
        raise ValueError("measurements must be an object")
    ease = payload.get("ease_cm", 4.0)
    return {"sex": sex, "garment_kind": kind, "measurements": {k: measurements[k] for k in sorted(measurements)}, "ease_cm": ease}


class OwnMockProvider:
    name = "own3d"
    model = "own3d-mock"

    def validate_request(self, payload: dict) -> None:
        clean = _clean(payload)
        base_models._fit_measurements(base_models.PRESETS[clean["sex"]], clean["measurements"]) if clean["measurements"] else None   # raises ValueError on bad values
        garments.build_sample_garment(clean["garment_kind"], clean["sex"], clean["ease_cm"])                                         # raises ValueError on a bad ease

    def describe_capabilities(self) -> list[str]:
        return ["TRY_ON_3D"]

    async def start(self, payload: dict) -> dict:
        clean = _clean(payload)
        request_id = "own3d_" + hashlib.sha256(json.dumps(clean, sort_keys=True).encode()).hexdigest()[:32]
        if request_id not in _RESULTS:
            _RESULTS[request_id] = self._run(clean)
            while len(_RESULTS) > MAX_KEPT:
                dropped, _ = _RESULTS.popitem(last=False)
                _GLBS.pop(dropped, None)
            glb = _RESULTS[request_id].pop("_glb", None)
            if glb is not None:
                _GLBS[request_id] = glb
        return {"request_id": request_id, "status": "running"}

    def _run(self, clean: dict[str, Any]) -> dict[str, Any]:
        glb, spec = garments.build_sample_garment(clean["garment_kind"], clean["sex"], clean["ease_cm"])
        try:
            fitted, report = deform_garment(glb, spec, clean["measurements"] or None)
        except garments.GarmentError as exc:
            return {"status": "failed", "charged": False, "error": {"code": "FIT_REFUSED", "message": str(exc)}, "output": None}
        body_tris, layers, fits = render3d_scene.build_layers(clean["sex"], clean["measurements"] or None, [clean["garment_kind"]], clean["ease_cm"])
        qc = render_qc.check_cuts(body_tris, layers, QC_ANGLES, penetrations={f["kind"]: f["penetrations"] for f in fits})     # R-ENGINE-11: recorded, never invented
        review = {"mock": True, "scores": {item: None for item in REVIEW_ITEMS}, "note": "the 5-item review is not run in the mock: no score is invented"}
        return {"status": "succeeded", "charged": True, "error": None, "_glb": fitted,
                "output": {"glb_sha256": hashlib.sha256(fitted).hexdigest(), "glb_bytes": len(fitted), "fit": report, "garment_spec_id": spec["id"], "review": review, "qc": qc}}

    async def status(self, request_id: str) -> dict:
        found = _RESULTS.get(request_id)
        if found is None:
            return {"request_id": request_id, "status": "failed", "charged": False, "output_url": None, "error": {"code": "UNKNOWN_REQUEST", "message": "no such own3d-mock request (results are kept in memory only)"}}
        return {"request_id": request_id, "output_url": None, "message": "own3d mock: geometry only, no image, no photo", **found}

    def result_glb(self, request_id: str) -> bytes | None:
        """The fitted garment .glb of a finished request (for the later render step); None for an unknown or failed one."""
        return _GLBS.get(request_id)
