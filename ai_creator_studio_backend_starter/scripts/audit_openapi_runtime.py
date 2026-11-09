"""Compare the product OpenAPI design draft with the live FastAPI route inventory.

This is an inventory/drift report, not an OpenAPI conformance validator.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

HTTP_METHODS = {"get", "post", "put", "patch", "delete", "options", "head", "trace"}


def normalize_path(path: str, prefix: str) -> str:
    prefix = prefix.rstrip("/")
    if prefix and (path == prefix or path.startswith(prefix + "/")):
        return path[len(prefix):] or "/"
    return path


def inventory(paths: dict[str, Any], prefix: str = "") -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for path, item in paths.items():
        normalized = normalize_path(path, prefix)
        result[normalized] = {method.lower() for method in item if method.lower() in HTTP_METHODS}
    return result


def compare_inventories(spec_paths: dict[str, Any], runtime_paths: dict[str, Any], prefix: str = "/v1") -> dict[str, Any]:
    spec = inventory(spec_paths)
    runtime = inventory(runtime_paths, prefix)
    missing_paths = sorted(set(spec) - set(runtime))
    extra_paths = sorted(set(runtime) - set(spec))
    method_gaps = []
    for path in sorted(set(spec) & set(runtime)):
        missing_methods = sorted(spec[path] - runtime[path])
        extra_methods = sorted(runtime[path] - spec[path])
        if missing_methods or extra_methods:
            method_gaps.append({
                "path": path,
                "missing_runtime_methods": missing_methods,
                "undocumented_runtime_methods": extra_methods,
            })
    return {
        "prefix_normalized": prefix,
        "spec_path_count": len(spec),
        "runtime_path_count": len(runtime),
        "spec_only_paths": missing_paths,
        "runtime_only_paths": extra_paths,
        "method_gaps": method_gaps,
        "exact_match": not (missing_paths or extra_paths or method_gaps),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", default=str(Path(__file__).resolve().parents[2] / "docs/product-baseline/AI_CREATOR_STUDIO_openapi_integrated_draft_v0_2.yaml"))
    parser.add_argument("--prefix", default="/v1", help="Runtime API prefix to strip before comparison")
    parser.add_argument("--strict", action="store_true", help="Exit 1 when any route/method drift exists")
    parser.add_argument("--output", help="Optional JSON report path")
    args = parser.parse_args()

    try:
        import yaml
    except ImportError as exc:
        raise SystemExit("PyYAML is required; install requirements-audit.txt") from exc

    spec_path = Path(args.spec)
    if not spec_path.is_absolute():
        spec_path = Path(__file__).resolve().parent / spec_path
    spec_doc = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    from app.main import app
    report = compare_inventories(spec_doc.get("paths", {}), app.openapi().get("paths", {}), args.prefix)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    print(rendered)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    return 1 if args.strict and not report["exact_match"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
