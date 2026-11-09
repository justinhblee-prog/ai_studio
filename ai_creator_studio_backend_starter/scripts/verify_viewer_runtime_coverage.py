#!/usr/bin/env python3
"""Run backend tests and prove every Viewer JSON success endpoint is exercised."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
VIEWER_ROOT = PROJECT_ROOT / "ai_creator_studio_3d_viewer"


def canonical_runtime_path(method: str, actual_path: str, openapi: dict) -> str | None:
    actual_segments = urlsplit(actual_path).path.strip("/").split("/")
    matches = []
    for route_path, operations in openapi.get("paths", {}).items():
        route_segments = route_path.strip("/").split("/")
        if len(route_segments) != len(actual_segments) or method not in operations:
            continue
        if all(
            expected == actual or (expected.startswith("{") and expected.endswith("}"))
            for expected, actual in zip(route_segments, actual_segments)
        ):
            matches.append(route_path)
    if len(matches) != 1:
        return None
    return re.sub(r"\{[^{}]+\}", "{param}", matches[0])


def main() -> int:
    sys.path.insert(0, str(BACKEND_ROOT))
    sys.path.insert(0, str(VIEWER_ROOT / "scripts"))
    from app.main import app
    from validate_viewer_response_contract import audit_viewer_response_contracts

    audit = audit_viewer_response_contracts(VIEWER_ROOT, app.openapi())
    expected = {
        (item["method"], item["path"])
        for item in audit["endpoints"]
        if item.get("response") != "no-json-body"
    }
    with tempfile.TemporaryDirectory(prefix="acs-viewer-runtime-") as temporary:
        capture_path = Path(temporary) / "responses.json"
        environment = os.environ.copy()
        plugin_dir = str(BACKEND_ROOT / "scripts")
        environment["PYTHONPATH"] = os.pathsep.join(
            [plugin_dir, str(BACKEND_ROOT), environment.get("PYTHONPATH", "")]
        )
        environment["ACS_VIEWER_RUNTIME_COVERAGE_OUTPUT"] = str(capture_path)
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-p", "viewer_runtime_coverage_plugin"],
            cwd=BACKEND_ROOT,
            env=environment,
            check=False,
        )
        if not capture_path.exists():
            print("ERROR: pytest did not produce runtime response capture", file=sys.stderr)
            return result.returncode or 1
        captured = json.loads(capture_path.read_text(encoding="utf-8"))

    observed = set()
    for item in captured:
        if not (200 <= int(item["status"]) < 300):
            continue
        if item["content_type"] != "application/json":
            continue
        route = canonical_runtime_path(str(item["method"]), str(item["path"]), app.openapi())
        if route:
            observed.add((str(item["method"]), route))

    observed_viewer = expected & {
        (method, re.sub(r"\{[^{}]+\}", "{param}", path))
        for method, path in observed
    }
    missing = sorted(expected - observed_viewer)
    print(f"Viewer runtime JSON success coverage: {len(observed_viewer)}/{len(expected)}")
    if missing:
        print("Unexercised Viewer endpoints:")
        for method, path in missing:
            print(f"  {method.upper()} {path}")
    if result.returncode:
        return result.returncode
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
