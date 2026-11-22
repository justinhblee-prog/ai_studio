"""E-04: print the static performance budget table of .glb files.   python scripts/glb_budget.py [--strict mobile] file.glb [more.glb ...]
Without files it measures the models this repository generates itself (the two base bodies and the five sample garments). ``--strict PROFILE`` exits 1 if any model is over that profile."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import base_models, garments, glb_budget  # noqa: E402


def own_models() -> list[tuple[str, bytes]]:
    out = [(f"base_{sex}", base_models.build_base_model(sex)) for sex in base_models.SEXES]
    out += [(f"sample_{kind}_{sex}", garments.build_sample_garment(kind, sex)[0]) for sex in base_models.SEXES for kind in garments.KINDS]
    return out


def main(argv: list[str]) -> int:
    strict = None
    if argv[:1] == ["--strict"]:
        strict, argv = argv[1], argv[2:]
    models = [(Path(a).name, Path(a).read_bytes()) for a in argv] or own_models()
    worst = 0
    print(f"{'model':<26}{'triangles':>10}{'draws':>7}{'tex MB':>8}{'file MB':>9}   mobile  laptop  desktop")
    for name, data in models:
        rep = glb_budget.report(data)
        info = rep["info"]
        tex = "n/a" if info["texture_bytes"] is None else f"{info['texture_bytes'] / 1_048_576:.1f}"
        marks = "  ".join("OVER  " if rep["profiles"][p]["over"] else "ok    " if rep["profiles"][p]["passed"] else "?     " for p in glb_budget.PROFILES)
        print(f"{name:<26}{info['triangles']:>10}{info['draw_calls']:>7}{tex:>8}{info['file_bytes'] / 1_048_576:>9.2f}   {marks}")
        for hint in rep["profiles"][strict or "mobile"]["hints"] if strict else []:
            print(f"    hint: {hint}")
        if strict and not rep["profiles"][strict]["passed"]:
            worst = 1
    print("budgets are proposals; FPS is not measured (no GPU here); see docs/GLB_BUDGET.md")
    return worst


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
