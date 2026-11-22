"""M4: write the S / M / L ease-and-pressure sheet (PNG) and print the size report (JSON).
   python scripts/ease_sheet.py top female --body 170,96,80,102 --nominal 170,92,76,98 out.png
--body and --nominal are  height,chest,waist,hips  in cm (nominal = the body the garment's size M is made for; default: the preset). Local, no network, no model."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import ease_map  # noqa: E402


def parse(text: str | None) -> dict[str, float] | None:
    if not text:
        return None
    height, chest, waist, hips = (float(v) for v in text.split(","))
    return {"height_cm": height, "chest_cm": chest, "waist_cm": waist, "hips_cm": hips}


def main(argv: list[str]) -> int:
    args, flags = [], {}
    it = iter(argv)
    for a in it:
        if a in ("--body", "--nominal"):
            flags[a[2:]] = next(it, None)
        else:
            args.append(a)
    if len(args) != 3:
        print(__doc__)
        return 2
    kind, sex, out = args
    body, nominal = parse(flags.get("body")), parse(flags.get("nominal"))
    report = ease_map.compare(kind, sex, body, nominal)
    ease_map.render_sheet(kind, sex, body, nominal=nominal).save(out)
    print(json.dumps(report, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
