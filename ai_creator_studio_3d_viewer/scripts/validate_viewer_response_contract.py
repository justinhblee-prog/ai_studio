#!/usr/bin/env python3
"""Audit success JSON response schemas for every Viewer fetch endpoint.

This is a static source/OpenAPI check. It verifies that each discovered Viewer
fetch maps to a runtime route and that every JSON-bearing 2xx response declares
an OpenAPI schema. It does not prove browser behavior or payload semantics.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

FETCH_RE = re.compile(r"fetch\(\s*`([^`]+)`\s*(?:,\s*\{([^}]*)\})?", re.DOTALL)
UNION_RE = re.compile(r"\b([A-Za-z_$][\w$]*)\s*:\s*((?:'[^']+'\s*\|\s*)+'[^']+')")
METHOD_RE = re.compile(r"\bmethod\s*:\s*['\"](GET|POST|PUT|PATCH|DELETE)['\"]", re.I)
PARAM_RE = re.compile(r"\$\{encodeURIComponent\([^}]+\)\}")
DYNAMIC_RE = re.compile(r"\$\{([A-Za-z_$][\w$]*)\}")


def canonical(path: str) -> str:
    path = path.split("?", 1)[0]
    path = PARAM_RE.sub("{param}", path)
    return re.sub(r"\{[^{}]+\}", "{param}", path)


def audit_viewer_response_contracts(viewer_root: Path, openapi: dict[str, Any]) -> dict[str, Any]:
    routes = {canonical(path): (path, operations) for path, operations in openapi.get("paths", {}).items()}
    sources = sorted((viewer_root / "src").glob("*.tsx"))
    unions: dict[str, list[str]] = {}
    for source in sources:
        text = source.read_text(encoding="utf-8")
        for match in UNION_RE.finditer(text):
            unions[match.group(1)] = re.findall(r"'([^']+)'", match.group(2))

    calls: set[tuple[str, str, str]] = set()
    unresolved: list[dict[str, str]] = []
    for source in sources:
        text = source.read_text(encoding="utf-8")
        for match in FETCH_RE.finditer(text):
            raw_url, options = match.groups()
            if "${base}" not in raw_url or "/v1/" not in raw_url:
                continue
            method_match = METHOD_RE.search(options or "")
            method = method_match.group(1).lower() if method_match else "get"
            raw_path = raw_url.split("${base}", 1)[-1]
            candidates = [raw_path]
            for name in DYNAMIC_RE.findall(raw_path):
                values = unions.get(name, [])
                if name == "action" and "/lookbook-drafts/" in raw_url and "/review/" not in raw_url:
                    values = ["submit", "approve", "request-changes"]
                elif name == "decision" and "/outputs/" in raw_url:
                    values = ["approve", "reject"]
                elif name == "action" and "/review/${action}" in raw_url:
                    values = ["approve", "request-changes", "reject"]
                if not values:
                    unresolved.append({"file": source.name, "dynamic": name, "url": raw_url})
                    candidates = []
                    break
                token = "${" + name + "}"
                candidates = [candidate.replace(token, value, 1)
                              for candidate in candidates for value in values]
            for candidate in candidates:
                calls.add((source.name, method, canonical(candidate)))

    endpoints = sorted({(method, path) for _, method, path in calls})
    missing_routes: list[dict[str, str]] = []
    missing_schemas: list[dict[str, Any]] = []
    no_content: list[dict[str, Any]] = []
    model_refs: set[str] = set()
    json_contract_count = 0
    endpoint_details = []
    for method, path in endpoints:
        route = routes.get(path)
        if route is None or method not in route[1]:
            missing_routes.append({"method": method, "path": path})
            continue
        original_path, operations = route
        operation = operations[method]
        success_responses = [(status, response) for status, response in operation.get("responses", {}).items()
                             if str(status).startswith("2")]
        json_schemas = []
        for status, response in success_responses:
            content = response.get("content", {})
            if "application/json" in content:
                schema = content["application/json"].get("schema")
                json_schemas.append((status, schema))
        if not json_schemas:
            no_content.append({"method": method, "path": path,
                               "success_statuses": [status for status, _ in success_responses]})
            endpoint_details.append({"method": method, "path": path, "response": "no-json-body"})
            continue
        json_contract_count += 1
        endpoint_refs = []
        for status, schema in json_schemas:
            if not schema:
                missing_schemas.append({"method": method, "path": path, "status": status})
                continue
            if "$ref" in schema:
                ref = schema["$ref"].rsplit("/", 1)[-1]
                model_refs.add(ref)
                endpoint_refs.append(ref)
            else:
                endpoint_refs.append("inline-schema")
        endpoint_details.append({"method": method, "path": path,
                                 "response_models": sorted(set(endpoint_refs))})

    return {
        "viewer_source_files": len(sources),
        "viewer_call_sites": len(calls),
        "unique_endpoints": len(endpoints),
        "json_success_response_contracts": json_contract_count,
        "distinct_response_models": len(model_refs),
        "response_models": sorted(model_refs),
        "no_json_body_endpoints": no_content,
        "missing_routes": missing_routes,
        "missing_response_schemas": missing_schemas,
        "unresolved_dynamic_segments": unresolved,
        "endpoints": endpoint_details,
        "scope_note": "Static Viewer source/OpenAPI contract audit; does not prove runtime payload semantics, TypeScript compilation, or browser execution.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--viewer", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--openapi", type=Path, default=Path(__file__).resolve().parents[2] / "docs/api/openapi.runtime.v1.json")
    parser.add_argument("--json", action="store_true", help="emit machine-readable audit")
    parser.add_argument("--output", type=Path, help="write machine-readable audit JSON")
    args = parser.parse_args()
    report = audit_viewer_response_contracts(args.viewer, json.loads(args.openapi.read_text(encoding="utf-8")))
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    if args.json:
        print(rendered, end="")
    else:
        print(f"Viewer response contract: {report['json_success_response_contracts']} JSON endpoints documented across {report['unique_endpoints']} endpoints; "
              f"{report['distinct_response_models']} models; {len(report['missing_routes'])} missing routes; "
              f"{len(report['missing_response_schemas'])} missing schemas; {len(report['unresolved_dynamic_segments'])} unresolved dynamic segments")
        for item in report["missing_routes"] + report["missing_response_schemas"] + report["unresolved_dynamic_segments"]:
            print("MISSING", item)
    return 1 if report["missing_routes"] or report["missing_response_schemas"] or report["unresolved_dynamic_segments"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
