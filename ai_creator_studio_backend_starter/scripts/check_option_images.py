"""R-051: checks the option / catalogue pictures of the homepage before they are published.

  python scripts/check_option_images.py <image-root> [--expected expected.json] [--json]

The root is the folder that holds ``opt/`` (option pictures ``opt/<key>-<value>.webp``) and ``cat/`` (style-catalogue pictures
``cat/<cat>-<id>.webp`` and ``cat/<style>/<cat>-<id>.webp``). Rules (proposals, the design window decides): .webp only, 64-1536 px per side, at most 200 KB
each, lowercase names built from letters, digits and underscores, no duplicates, no stray files. ``--expected`` is a JSON list of the file names the
pages ask for (``["opt/skin_tone-3.webp", ...]``): files that are expected but absent are reported as MISSING (the pages must show their fallback for
them), files present but not expected as UNEXPECTED. Exit code 0 = no errors (missing pictures are not errors while the pictures are still being made;
add --strict to fail on them), 1 = a picture breaks a rule, 2 = unusable input.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

MAX_BYTES, MIN_EDGE, MAX_EDGE = 200 * 1024, 64, 1536
STYLES = {"photo", "webtoon", "anime", "render3d", "illust"}
NAME = re.compile(r"^[a-z][a-z0-9_]*-[a-z0-9_]+\.webp$")


def rule_for(rel: Path) -> str | None:
    """Which naming rule a path falls under, or None when the location itself is not allowed."""
    parts = rel.parts
    if parts[0] == "opt" and len(parts) == 2:
        return "opt"
    if parts[0] == "cat" and len(parts) == 2:
        return "cat"
    if parts[0] == "cat" and len(parts) == 3 and parts[1] in STYLES:
        return "cat-style"
    return None


def check_file(root: Path, path: Path) -> list[str]:
    rel = path.relative_to(root)
    problems: list[str] = []
    if rule_for(rel) is None:
        return [f"{rel.as_posix()}: not an allowed location (opt/<name>, cat/<name>, cat/<{'|'.join(sorted(STYLES))}>/<name>)"]
    if not NAME.match(path.name):
        problems.append(f"{rel.as_posix()}: name must look like <key>-<value>.webp (lowercase letters, digits, underscores)")
    size = path.stat().st_size
    if size > MAX_BYTES:
        problems.append(f"{rel.as_posix()}: {size // 1024} KB is over the {MAX_BYTES // 1024} KB limit")
    if size == 0:
        return problems + [f"{rel.as_posix()}: empty file"]
    try:
        from PIL import Image
        with Image.open(path) as img:
            if img.format != "WEBP":
                problems.append(f"{rel.as_posix()}: content is {img.format}, not WebP (the extension must match the content)")
            w, h = img.size
            if not (MIN_EDGE <= w <= MAX_EDGE and MIN_EDGE <= h <= MAX_EDGE):
                problems.append(f"{rel.as_posix()}: {w}x{h} is outside {MIN_EDGE}-{MAX_EDGE} px")
            if getattr(img, "n_frames", 1) > 1:
                problems.append(f"{rel.as_posix()}: animated pictures are not allowed here")
    except Exception as exc:  # noqa: BLE001
        problems.append(f"{rel.as_posix()}: cannot be read as an image ({type(exc).__name__})")
    return problems


def run(root: Path, expected: list[str] | None = None) -> dict:
    files = sorted(p for p in root.rglob("*") if p.is_file())
    errors: list[str] = []
    seen_lower: dict[str, str] = {}
    for path in files:
        errors += check_file(root, path)
        key = path.relative_to(root).as_posix().lower()
        if key in seen_lower:
            errors.append(f"{path.relative_to(root).as_posix()}: differs from {seen_lower[key]} only by letter case")
        seen_lower[key] = path.relative_to(root).as_posix()
    present = {p.relative_to(root).as_posix() for p in files}
    missing = sorted(set(expected) - present) if expected is not None else []
    unexpected = sorted(present - set(expected)) if expected is not None else []
    return {"checked": len(files), "errors": errors, "missing": missing, "unexpected": unexpected}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root")
    ap.add_argument("--expected")
    ap.add_argument("--strict", action="store_true", help="a missing expected picture is an error too")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    root = Path(args.root)
    if not root.is_dir():
        print(f"not a folder: {root}", file=sys.stderr)
        return 2
    expected = None
    if args.expected:
        try:
            expected = json.loads(Path(args.expected).read_text(encoding="utf-8"))
            if not isinstance(expected, list) or not all(isinstance(x, str) for x in expected):
                raise ValueError("a JSON list of strings is required")
        except (OSError, ValueError) as exc:
            print(f"unusable --expected file: {exc}", file=sys.stderr)
            return 2
    report = run(root, expected)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"checked {report['checked']} picture(s): {len(report['errors'])} error(s), {len(report['missing'])} missing, {len(report['unexpected'])} unexpected")
        for line in report["errors"]:
            print("ERROR      " + line)
        for name in report["missing"]:
            print("MISSING    " + name)
        for name in report["unexpected"]:
            print("UNEXPECTED " + name)
    return 1 if report["errors"] or (args.strict and report["missing"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
