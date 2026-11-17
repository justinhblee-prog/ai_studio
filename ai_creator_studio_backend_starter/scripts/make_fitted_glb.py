"""Writes the R-ENGINE-03a fitted-garment sample .glb files (mannequin + top shell) from typed measurements. No photo, no AI, no network.
   python scripts/make_fitted_glb.py <out_dir> [size]      -> fitted_<size>.glb (default M) and fitted_<size>.json (the fit report)
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.garment_fit import build_fitted_glb  # noqa: E402
from app.mannequin import Measurements, SizeChart  # noqa: E402

BODY = Measurements(height_cm=170, chest_cm=92, waist_cm=76, hips_cm=98)
CHART = SizeChart(sizes={"S": {"chest": 94, "waist": 80, "hips": 100}, "M": {"chest": 100, "waist": 86, "hips": 106}, "L": {"chest": 108, "waist": 94, "hips": 114}})


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    out, size = Path(argv[0]), (argv[1] if len(argv) > 1 else "M")
    out.mkdir(parents=True, exist_ok=True)
    glb, report = build_fitted_glb(BODY, CHART, size)
    (out / f"fitted_{size}.glb").write_bytes(glb)
    (out / f"fitted_{size}.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"glb": f"fitted_{size}.glb", "bytes": len(glb), "cannot_fit": report["cannot_fit"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
