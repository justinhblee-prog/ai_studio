"""Compare design-draft and FastAPI OpenAPI request/response contracts.

This is a conservative structural audit. It resolves local component refs and
reports schema-shape drift; it does not claim semantic equivalence or validate
runtime payload behavior.
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


def dereference(schema: Any, components: dict[str, Any], depth: int = 0) -> Any:
    if not isinstance(schema, dict) or depth > 12:
        return schema
    ref = schema.get("$ref")
    if isinstance(ref, str) and ref.startswith("#/components/schemas/"):
        name = ref.rsplit("/", 1)[-1]
        target = components.get(name, {})
        resolved = dereference(target, components, depth + 1)
        if isinstance(resolved, dict):
            return {**resolved, **{k: v for k, v in schema.items() if k != "$ref"}}
        return resolved
    result = dict(schema)
    if isinstance(result.get("properties"), dict):
        result["properties"] = {k: dereference(v, components, depth + 1) for k, v in result["properties"].items()}
    if isinstance(result.get("items"), dict):
        result["items"] = dereference(result["items"], components, depth + 1)
    for key in ("oneOf", "anyOf", "allOf"):
        if isinstance(result.get(key), list):
            result[key] = [dereference(v, components, depth + 1) for v in result[key]]
    return result


def schema_shape(schema: Any, components: dict[str, Any]) -> dict[str, Any]:
    resolved = dereference(schema, components)
    if not isinstance(resolved, dict):
        return {"type": type(resolved).__name__, "properties": [], "required": []}
    properties = sorted(resolved.get("properties", {}).keys())
    required = sorted(resolved.get("required", []))
    variants = {}
    for key in ("oneOf", "anyOf", "allOf"):
        if key in resolved:
            variants[key] = [schema_shape(item, components) for item in resolved[key]]
    shape = {"type": resolved.get("type"), "properties": properties, "required": required}
    if "items" in resolved:
        shape["items"] = schema_shape(resolved["items"], components)
    if variants:
        shape["variants"] = variants
    return shape


def request_schema(operation: dict[str, Any], components: dict[str, Any]) -> dict[str, Any] | None:
    body = operation.get("requestBody", {})
    content = body.get("content", {}) if isinstance(body, dict) else {}
    media = content.get("application/json", {})
    schema = media.get("schema") if isinstance(media, dict) else None
    return schema_shape(schema, components) if schema is not None else None


def success_responses(operation: dict[str, Any], components: dict[str, Any], all_components: dict[str, Any] | None = None) -> dict[str, Any]:
    result = {}
    for code, response in operation.get("responses", {}).items():
        if not str(code).startswith("2") or not isinstance(response, dict):
            continue
        ref = response.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/components/responses/"):
            response = (all_components or {}).get("responses", {}).get(ref.rsplit("/", 1)[-1], {})
        content = response.get("content", {})
        media = content.get("application/json", {}) if isinstance(content, dict) else {}
        schema = media.get("schema") if isinstance(media, dict) else None
        result[str(code)] = schema_shape(schema, components) if schema is not None else None
    return result


def parameter_shape(operation: dict[str, Any], components: dict[str, Any]) -> list[tuple[Any, Any, bool]]:
    result = []
    component_parameters = components.get("parameters", {}) if isinstance(components, dict) else {}
    for parameter in operation.get("parameters", []):
        if not isinstance(parameter, dict):
            continue
        ref = parameter.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/components/parameters/"):
            parameter = component_parameters.get(ref.rsplit("/", 1)[-1], {})
        if str(parameter.get("in", "")).lower() == "header" and str(parameter.get("name", "")).lower() == "authorization":
            continue  # Authentication is modeled as an OpenAPI security scheme, not a business parameter.
        result.append((parameter.get("in"), parameter.get("name"), bool(parameter.get("required"))))
    return sorted(result, key=lambda item: (str(item[0]), str(item[1]), item[2]))


def compare_operation(spec_op: dict[str, Any], runtime_op: dict[str, Any], spec_components: dict[str, Any], runtime_components: dict[str, Any], spec_all_components: dict[str, Any] | None = None, runtime_all_components: dict[str, Any] | None = None) -> dict[str, Any]:
    spec_request = request_schema(spec_op, spec_components)
    runtime_request = request_schema(runtime_op, runtime_components)
    spec_responses = success_responses(spec_op, spec_components, spec_all_components)
    runtime_responses = success_responses(runtime_op, runtime_components, runtime_all_components)
    issues = []
    if spec_request != runtime_request:
        issues.append("request_schema_shape_mismatch")
    if spec_responses != runtime_responses:
        issues.append("success_response_schema_or_status_mismatch")
    spec_params = parameter_shape(spec_op, spec_all_components or {})
    runtime_params = parameter_shape(runtime_op, runtime_all_components or {})
    if spec_params != runtime_params:
        issues.append("parameter_contract_mismatch")
    if spec_op.get("operationId") != runtime_op.get("operationId"):
        issues.append("operation_id_mismatch")
    return {
        "operation_id": {"design": spec_op.get("operationId"), "runtime": runtime_op.get("operationId")},
        "issues": issues,
        "design_request": spec_request,
        "runtime_request": runtime_request,
        "design_success_responses": spec_responses,
        "runtime_success_responses": runtime_responses,
        "design_parameters": spec_params,
        "runtime_parameters": runtime_params,
    }


def audit_contract(spec_doc: dict[str, Any], runtime_doc: dict[str, Any], prefix: str = "/v1") -> dict[str, Any]:
    spec_paths = spec_doc.get("paths", {})
    raw_runtime_paths = runtime_doc.get("paths", {})
    runtime_paths: dict[str, Any] = {}
    normalized_collisions: dict[str, list[str]] = {}
    for raw_path, item in raw_runtime_paths.items():
        normalized = normalize_path(raw_path, prefix)
        if normalized in runtime_paths:
            normalized_collisions.setdefault(normalized, [next(
                original for original in raw_runtime_paths
                if normalize_path(original, prefix) == normalized
            )]).append(raw_path)
            # Preserve disjoint methods from both source paths while surfacing
            # the collision; a duplicate method remains explicitly ambiguous.
            runtime_paths[normalized] = {**runtime_paths[normalized], **item}
        else:
            runtime_paths[normalized] = item
    spec_all_components = spec_doc.get("components", {})
    runtime_all_components = runtime_doc.get("components", {})
    spec_components = spec_all_components.get("schemas", {})
    runtime_components = runtime_all_components.get("schemas", {})
    comparisons = []
    unmatched = []
    design_keys: set[tuple[str, str]] = set()
    runtime_keys: set[tuple[str, str]] = set()
    for path, methods in sorted(spec_paths.items()):
        if not isinstance(methods, dict):
            continue
        for method in methods:
            if method.lower() in HTTP_METHODS:
                design_keys.add((normalize_path(path, ""), method.lower()))
    for path, methods in runtime_paths.items():
        if isinstance(methods, dict):
            runtime_keys.update((path, method.lower()) for method in methods if method.lower() in HTTP_METHODS)
    for path, methods in sorted(spec_paths.items()):
        normalized = normalize_path(path, "")
        runtime_methods = runtime_paths.get(normalized, {})
        for method, operation in sorted(methods.items()):
            if method.lower() not in HTTP_METHODS:
                continue
            runtime_operation = runtime_methods.get(method.lower())
            if runtime_operation is None:
                unmatched.append({"path": normalized, "method": method.lower(), "reason": "missing_runtime_operation"})
                continue
            result = compare_operation(operation, runtime_operation, spec_components, runtime_components, spec_all_components, runtime_all_components)
            if result["issues"]:
                comparisons.append({"path": normalized, "method": method.lower(), **result})
    return {
        "prefix_normalized": prefix,
        "design_operations_compared": sum(1 for p in spec_paths.values() for m in p if m.lower() in HTTP_METHODS),
        "operations_with_contract_drift": len(comparisons),
        "unmatched_design_operations": unmatched,
        "runtime_only_operations": [
            {"path": path, "method": method, "reason": "not_in_design_draft"}
            for path, method in sorted(runtime_keys - design_keys)
        ],
        "runtime_operation_count": len(runtime_keys),
        "design_operation_count": len(design_keys),
        "normalized_runtime_path_collisions": [
            {"normalized_path": path, "source_paths": sorted(set(paths))}
            for path, paths in sorted(normalized_collisions.items())
        ],
        "contract_drift": comparisons,
        "scope_note": "Structural OpenAPI comparison only; no semantic validation or runtime payload conformance is implied.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", default=str(Path(__file__).resolve().parents[2] / "docs/product-baseline/AI_CREATOR_STUDIO_openapi_integrated_draft_v0_2.yaml"))
    parser.add_argument("--prefix", default="/v1")
    parser.add_argument("--runtime-output", help="Optional path for the generated FastAPI OpenAPI snapshot")
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
    runtime_doc = app.openapi()
    report = audit_contract(spec_doc, runtime_doc, args.prefix)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    print(rendered)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    if args.runtime_output:
        Path(args.runtime_output).write_text(json.dumps(runtime_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
