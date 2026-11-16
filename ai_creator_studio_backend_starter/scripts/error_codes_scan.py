"""R-072: every error ``code`` the server can send, found by reading the source (not by running it).

A code is a SCREAMING_SNAKE string (at least two words) that appears (1) as the value of a ``"code"`` key in a dict, (2) as a ``code=`` keyword, or (3) as the first argument of a call to
something named ``*Error`` / ``*Exceeded`` / ``too_many``. ``tests/test_error_catalog.py`` fails when a code found here has no entry in ``app/error_catalog.py``.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

CODE = re.compile(r"^[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+$")
CALLS = ("too_many", "_fail", "_err")


def scan(root: Path | None = None) -> dict[str, str]:
    root = root or Path(__file__).resolve().parents[1] / "app"
    found: dict[str, str] = {}
    for path in sorted(root.rglob("*.py")):
        if "sql" in path.relative_to(root).parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        rel = path.relative_to(root).as_posix()

        def add(node):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and CODE.match(node.value):
                found.setdefault(node.value, rel)

        for node in ast.walk(tree):
            if isinstance(node, ast.Dict):
                for key, value in zip(node.keys, node.values):
                    if isinstance(key, ast.Constant) and key.value == "code":
                        add(value)
            elif isinstance(node, ast.Call):
                name = getattr(node.func, "id", None) or getattr(node.func, "attr", None) or ""
                for kw in node.keywords:
                    if kw.arg == "code":
                        add(kw.value)
                if (name.endswith("Error") or name.endswith("Exceeded") or name in CALLS) and node.args:
                    add(node.args[0])
    return dict(sorted(found.items()))


if __name__ == "__main__":
    result = scan()
    print(len(result))
    for code, where in result.items():
        print(code, where)
    sys.exit(0)
