#!/usr/bin/env python3
"""Validate Viewer fetch URL/method usage against the committed runtime OpenAPI snapshot.

This is a source-level guard, not a TypeScript compiler or browser integration test.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

FETCH_RE = re.compile(r"fetch\(\s*`([^`]+)`\s*(?:,\s*\{([^}]*)\})?", re.DOTALL)
UNION_RE = re.compile(r"\b([A-Za-z_$][\w$]*)\s*:\s*((?:'[^']+'\s*\|\s*)+'[^']+')")
METHOD_RE = re.compile(r"\bmethod\s*:\s*['\"](GET|POST|PUT|PATCH|DELETE)['\"]", re.I)
PARAM_RE = re.compile(r"\$\{encodeURIComponent\([^}]+\)\}")
DYNAMIC_RE = re.compile(r"\$\{([A-Za-z_$][\w$]*)\}")


def canonical(path: str) -> str:
    path = path.split("?", 1)[0]
    path = PARAM_RE.sub("{param}", path)
    path = re.sub(r"\{[^{}]+\}", "{param}", path)
    return path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--viewer", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--openapi", type=Path, default=Path(__file__).resolve().parents[2] / "docs/api/openapi.runtime.v1.json")
    parser.add_argument("--json", action="store_true", help="emit machine-readable report")
    args = parser.parse_args()

    spec = json.loads(args.openapi.read_text(encoding="utf-8"))
    routes = {}
    for path, operations in spec.get("paths", {}).items():
        routes[canonical(path)] = {
            method.lower(): {parameter.get("name") for parameter in operation.get("parameters", [])
                             if parameter.get("in") == "query"}
            for method, operation in operations.items()
            if method.lower() in {"get", "post", "put", "patch", "delete"}
        }

    sources = sorted((args.viewer / "src").glob("*.tsx"))
    unions: dict[str, list[str]] = {}
    for source in sources:
        text = source.read_text(encoding="utf-8")
        for match in UNION_RE.finditer(text):
            unions[match.group(1)] = re.findall(r"'([^']+)'", match.group(2))

    calls = []
    unresolved = []
    for source in sources:
        text = source.read_text(encoding="utf-8")
        for match in FETCH_RE.finditer(text):
            raw_url, options = match.groups()
            if "${base}" not in raw_url or "/v1/" not in raw_url:
                continue
            method_match = METHOD_RE.search(options or "")
            method = (method_match.group(1).lower() if method_match else "get")
            raw_path = raw_url.split("${base}", 1)[-1]
            dynamic_names = DYNAMIC_RE.findall(raw_path)
            # Resolve dynamic route segments from the owning callback's narrow action union.
            # The same identifier can also appear in unrelated object fields elsewhere in a file.
            candidates = [raw_url.split("${base}", 1)[-1]]
            for name in dynamic_names:
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
                candidates = [candidate.replace(token, value, 1) for candidate in candidates for value in values]
            for candidate in candidates:
                path = canonical(candidate)
                methods = routes.get(path, {})
                declared_query = methods.get(method, set())
                used_query = set(re.findall(r"[?&]([A-Za-z_][A-Za-z0-9_]*)=", candidate))
                missing_query = sorted(used_query - declared_query)
                calls.append({"file": source.name, "method": method, "path": path,
                              "query": sorted(used_query), "missing_query": missing_query,
                              "ok": method in methods and not missing_query})

    # De-duplicate repeated calls to the same endpoint/method while retaining file attribution.
    unique = {(c["file"], c["method"], c["path"]): c for c in calls}
    calls = sorted(unique.values(), key=lambda c: (c["file"], c["path"], c["method"]))
    missing = [c for c in calls if c["method"] not in routes.get(c["path"], {})]
    query_mismatches = [c for c in calls if c["missing_query"]]
    failures = missing + [c for c in query_mismatches if c not in missing]
    report = {"snapshot": str(args.openapi), "source_files": len(sources), "viewer_calls": len(calls),
              "unique_endpoints": len({(c['method'], c['path']) for c in calls}),
              "matched": len(calls) - len(failures), "missing": missing,
              "query_mismatches": query_mismatches, "unresolved_dynamic": unresolved,
              "scope_note": "Source-level fetch URL/method check only; does not validate payload/response schemas or browser execution."}
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Viewer API contract: {report['matched']}/{len(calls)} calls matched; {len(missing)} missing; {len(query_mismatches)} query mismatches; {len(unresolved)} unresolved dynamic segments")
        for item in missing:
            print(f"MISSING {item['file']} {item['method'].upper()} {item['path']}")
        for item in query_mismatches:
            print(f"QUERY {item['file']} {item['method'].upper()} {item['path']} undeclared={','.join(item['missing_query'])}")
        for item in unresolved:
            print(f"UNRESOLVED {item['file']} {item['dynamic']}: {item['url']}")
    return 1 if failures or unresolved or not calls else 0


if __name__ == "__main__":
    raise SystemExit(main())
