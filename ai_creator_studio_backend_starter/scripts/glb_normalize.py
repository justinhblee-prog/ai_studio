"""E-01: inspect / normalize a .glb from the command line.  python scripts/glb_normalize.py in.glb [--out out.glb]   (prints the before/after numbers as JSON)"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.glb_tools import normalize_glb  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source")
    parser.add_argument("--out")
    args = parser.parse_args(argv)
    data = Path(args.source).read_bytes()
    result, report = normalize_glb(data)
    if args.out and report["changed"]:
        Path(args.out).write_bytes(result)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
