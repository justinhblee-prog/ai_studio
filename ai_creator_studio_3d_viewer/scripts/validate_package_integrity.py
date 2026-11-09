#!/usr/bin/env python3
"""Offline package/source integrity checks; does not claim TS type or browser validation."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

IMPORT_RE = re.compile(
    r"(?:\bfrom\s*|\bimport\s*)[\"']([^\"']+)[\"']|\bimport\s*[\"']([^\"']+)[\"']"
)
EXPORT_RE = re.compile(r"\bexport\s+(?:\{[^}]*\}\s+from\s*)?[\"']([^\"']+)[\"']")
SCRIPT_RE = re.compile(r"(?:^|\s)(?:python3?|node)\s+([^\s;&|]+)")
SOURCE_EXTENSIONS = (".ts", ".tsx", ".js", ".jsx", ".css", ".json")


def resolve_local_import(source_file: Path, specifier: str) -> Path | None:
    if not specifier.startswith("."):
        return None
    base = (source_file.parent / specifier).resolve()
    candidates = [base]
    if not base.suffix:
        candidates.extend(Path(f"{base}{suffix}") for suffix in SOURCE_EXTENSIONS)
        candidates.extend(base / f"index{suffix}" for suffix in SOURCE_EXTENSIONS)
    return next((candidate for candidate in candidates if candidate.is_file()), None)


def audit_viewer_package(root: Path) -> list[str]:
    findings: list[str] = []
    package_path = root / "package.json"
    if not package_path.is_file():
        return ["missing package.json"]
    package = json.loads(package_path.read_text(encoding="utf-8"))
    scripts = package.get("scripts", {})
    for name, command in scripts.items():
        for match in SCRIPT_RE.finditer(command):
            script_path = (root / match.group(1)).resolve()
            if not script_path.is_file():
                findings.append(f"npm script {name} references missing file: {match.group(1)}")

    runtime_dependencies = set(package.get("dependencies", {}))
    peer_dependencies = set(package.get("peerDependencies", {}))
    dev_dependencies = set(package.get("devDependencies", {}))
    declared = runtime_dependencies | peer_dependencies | dev_dependencies

    source_root = root / "src"
    if not source_root.is_dir():
        findings.append("missing src directory")
        return findings
    source_files = sorted(path for path in source_root.rglob("*") if path.is_file() and path.suffix in {".ts", ".tsx", ".js", ".jsx"})
    if not source_files:
        findings.append("no TypeScript/JavaScript source files found")

    for source_file in source_files:
        source = source_file.read_text(encoding="utf-8")
        for match in IMPORT_RE.finditer(source):
            specifier = match.group(1) or match.group(2)
            if specifier.startswith("."):
                if resolve_local_import(source_file, specifier) is None:
                    relative = source_file.relative_to(root).as_posix()
                    findings.append(f"{relative} imports missing local module: {specifier}")
                continue
            package_name = specifier.split("/", 1)[0]
            if specifier.startswith("@"):
                package_name = "/".join(specifier.split("/")[:2])
            if package_name not in declared and package_name not in {"node:", "node"}:
                relative = source_file.relative_to(root).as_posix()
                findings.append(f"{relative} imports undeclared package: {package_name}")

    index_path = source_root / "index.ts"
    if index_path.is_file():
        index_source = index_path.read_text(encoding="utf-8")
        for match in EXPORT_RE.finditer(index_source):
            specifier = match.group(1)
            if resolve_local_import(index_path, specifier) is None:
                findings.append(f"public entrypoint exports missing module: {specifier}")

    tsconfig_path = root / "tsconfig.json"
    if tsconfig_path.is_file():
        tsconfig = json.loads(tsconfig_path.read_text(encoding="utf-8"))
        includes = tsconfig.get("include", [])
        if not any("src/" in item.replace("\\", "/") for item in includes):
            findings.append("tsconfig does not include src source files")

    if "react" not in peer_dependencies or "react-dom" not in peer_dependencies:
        findings.append("React and ReactDOM must remain peer dependencies")
    if "three" not in runtime_dependencies:
        findings.append("Three.js must be declared as a runtime dependency")
    if "typescript" not in dev_dependencies:
        findings.append("TypeScript must be declared as a development dependency")
    return findings


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    findings = audit_viewer_package(root)
    if findings:
        for finding in findings:
            print(f"FAIL {finding}")
        print(f"Package integrity: {len(findings)} finding(s)")
        return 1
    print("PASS npm script targets")
    print("PASS relative imports and stylesheet references")
    print("PASS external package declarations")
    print("PASS public TypeScript entrypoint exports")
    print("PASS TypeScript source inclusion and dependency roles")
    print("Package integrity: 0 findings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
