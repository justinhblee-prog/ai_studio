"""Looks at rendered turntable cuts of the fitted-garment .glb and checks that BOTH the body (skin colour) and the garment shell (blue) are really visible from four sides.
   python scripts/check_fitted_render.py <turn_dir> [cuts_per_turn]
It counts pixels by colour family, so it needs no reference image; it is a smoke check that the shell is drawn (double-sided) and not hidden inside the body or missing."""
import json
import sys
from pathlib import Path

from PIL import Image

MIN_SHARE = 0.004          # each colour family must cover at least 0.4% of the picture


def families(path: Path) -> dict:
    img = Image.open(path).convert("RGB")
    total, skin, garment = img.width * img.height, 0, 0
    for r, g, b in img.getdata():
        if r - b > 25 and r >= g:
            skin += 1
        elif b - r > 25 and b >= g:
            garment += 1
    return {"file": path.name, "skin_share": round(skin / total, 4), "garment_share": round(garment / total, 4)}


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    folder, cuts = Path(argv[0]), int(argv[1]) if len(argv) > 1 else 120
    rows = [families(folder / f"turn_{i:03d}.png") for i in (0, cuts // 4, cuts // 2, 3 * cuts // 4)]
    ok = all(r["skin_share"] >= MIN_SHARE and r["garment_share"] >= MIN_SHARE for r in rows)
    print(json.dumps({"views": rows, "min_share": MIN_SHARE, "ok": ok}))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
