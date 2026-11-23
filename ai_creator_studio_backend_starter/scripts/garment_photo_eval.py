"""R-ENGINE-15: the error table of the photo -> garment estimate on the SYNTHETIC set (app/garment_photo_synth.py).

   python scripts/garment_photo_eval.py            # prints a markdown table (about 3 minutes, pure Python)
   python scripts/garment_photo_eval.py --quick    # kinds x 1 size x 3 conditions

Errors are |estimate - truth| in cm per measure, grouped by condition. A photo the analysis REFUSES is counted as refused, not as an error of 0.
Honest limit: synthetic photos only; the garment shapes are simple and the truth follows this repository's own width definitions (``garment_photo.RULES``).
"""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import garment_photo as gp  # noqa: E402
from app import garment_photo_synth as gs  # noqa: E402

MEASURES = ("chest_cm", "waist_cm", "hips_cm", "length_cm", "sleeve_cm")


def run(quick: bool = False) -> dict:
    sizes = (1.0,) if quick else (0.85, 1.0, 1.15)
    conditions = ("clean", "noise_vignette", "low_contrast") if quick else gs.CONDITIONS
    errors: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    colour: dict[str, list[float]] = defaultdict(list)
    count: dict[str, int] = defaultdict(int)
    refused: dict[str, list[str]] = defaultdict(list)
    cases = [(k, s, c, "card") for c in conditions for k in gs.DEFAULTS for s in sizes] + ([] if quick else [(k, 1.0, "clean", "a4") for k in gs.DEFAULTS])
    for kind, size, cond, ref in cases:
        key = cond if ref == "card" else "a4_reference"
        data, truth = gs.synthetic_photo(kind, scale=size, condition=cond, reference=ref, seed=3)
        count[key] += 1
        try:
            result = gp.analyze(data, reference=ref, kind=kind)
        except gp.GarmentPhotoError as exc:
            refused[key].append(f"{kind}@{size}:{exc.code}")
            continue
        for name in MEASURES:
            if name in truth and name in result["measurements_cm"]:
                errors[key][name].append(abs(result["measurements_cm"][name] - truth[name]))
        colour[key].append(sum(abs(a - b) for a, b in zip(result["colour"]["base"], truth["colour"])) / 3)
    return {"errors": errors, "colour": colour, "count": count, "refused": refused}


def table(res: dict) -> str:
    lines = ["| condition | photos | refused | " + " | ".join(f"{m.replace('_cm', '')} mean / max (cm)" for m in MEASURES) + " | colour (mean RGB diff) |", "|" + "---|" * (4 + len(MEASURES))]
    for key in res["count"]:
        cells = []
        for m in MEASURES:
            v = res["errors"][key].get(m, [])
            cells.append(f"{sum(v) / len(v):.2f} / {max(v):.2f}" if v else "-")
        col = res["colour"][key]
        lines.append(f"| {key} | {res['count'][key]} | {len(res['refused'][key])} | " + " | ".join(cells) + f" | {sum(col) / len(col):.1f} |" if col else f"| {key} | {res['count'][key]} | {len(res['refused'][key])} | " + " | ".join("-" for _ in MEASURES) + " | - |")
    every = [e for per in res["errors"].values() for v in per.values() for e in v]
    refused = [f"{k}: {', '.join(v)}" for k, v in res["refused"].items() if v]
    lines.append("")
    lines.append(f"all measurements: {len(every)} values, mean {sum(every) / len(every):.2f} cm, max {max(every):.2f} cm")
    if refused:
        lines.append("refused: " + " | ".join(refused))
    return "\n".join(lines)


if __name__ == "__main__":
    print(table(run("--quick" in sys.argv)))
