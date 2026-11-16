"""R-070: the example JSON in the contract documents is checked against the server's OpenAPI (and, for two of them, against a real response).

A response example in docs/AIS_API_CONTRACT.md or docs/WORK_ITEMS_CONTRACT.md is written under a marker ``<!-- contract: <operationId> <status> -->``. This test validates every such example against the
response schema of that operation: a field that was renamed, removed, retyped or newly required makes it fail, so the homepage adapter cannot be broken silently by a server change.
The validator is small on purpose (no extra dependency): $ref, type, anyOf/oneOf, enum/const, properties/required, items, additionalProperties. An unknown field in the example is an error.
"""
import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.test_photo_steps_api import auth, env  # noqa: F401  (wa: owner a + viewer c, wb: owner b)

DOCS = Path(__file__).resolve().parents[2] / "docs"
FILES = ["AIS_API_CONTRACT.md", "WORK_ITEMS_CONTRACT.md"]
MARKER = re.compile(r"<!--\s*contract:\s*(\w+)\s+(\d{3})\s*-->\s*```json\n(.*?)```", re.S)
client = TestClient(app)
SPEC = app.openapi()


def resolve(schema):
    while isinstance(schema, dict) and "$ref" in schema:
        node = SPEC
        for part in schema["$ref"].lstrip("#/").split("/"):
            node = node[part]
        schema = node
    return schema


def validate(value, schema, path="$"):
    """The list of problems of ``value`` against ``schema`` (empty = fine)."""
    schema = resolve(schema)
    if schema == {} or schema is True:
        return []
    if "anyOf" in schema or "oneOf" in schema:
        options = schema.get("anyOf") or schema.get("oneOf")
        attempts = [validate(value, o, path) for o in options]
        return [] if any(not a for a in attempts) else [f"{path}: matches none of the {len(options)} allowed shapes ({attempts[0][:1]}...)"]
    if "const" in schema and value != schema["const"]:
        return [f"{path}: expected {schema['const']!r}"]
    if "enum" in schema and value not in schema["enum"]:
        return [f"{path}: {value!r} is not one of {schema['enum']}"]
    t = schema.get("type")
    if t == "null":
        return [] if value is None else [f"{path}: expected null"]
    if t == "string":
        return [] if isinstance(value, str) else [f"{path}: expected a string, got {type(value).__name__}"]
    if t == "boolean":
        return [] if isinstance(value, bool) else [f"{path}: expected a boolean"]
    if t == "integer":
        return [] if isinstance(value, int) and not isinstance(value, bool) else [f"{path}: expected an integer"]
    if t == "number":
        return [] if isinstance(value, (int, float)) and not isinstance(value, bool) else [f"{path}: expected a number"]
    if t == "array":
        if not isinstance(value, list):
            return [f"{path}: expected an array"]
        return [p for i, v in enumerate(value) for p in validate(v, schema.get("items", {}), f"{path}[{i}]")]
    if t == "object" or "properties" in schema:
        if not isinstance(value, dict):
            return [f"{path}: expected an object"]
        props, problems = schema.get("properties", {}), []
        for name in schema.get("required", []):
            if name not in value:
                problems.append(f"{path}.{name}: required by the server but missing in the example")
        free = schema.get("additionalProperties")
        for name, v in value.items():
            if name in props:
                problems += validate(v, props[name], f"{path}.{name}")
            elif isinstance(free, dict):
                problems += validate(v, free, f"{path}.{name}")
            elif free is not True and props:
                problems.append(f"{path}.{name}: the server no longer has this field")
        return problems
    return []


def response_schema(operation_id: str, status: str):
    for path, ops in SPEC["paths"].items():
        for method, op in ops.items():
            if isinstance(op, dict) and op.get("operationId") == operation_id:
                return op["responses"][status]["content"]["application/json"]["schema"]
    raise AssertionError(f"no operation {operation_id}")


def examples():
    found = []
    for name in FILES:
        for m in MARKER.finditer((DOCS / name).read_text(encoding="utf-8")):
            found.append((name, m.group(1), m.group(2), json.loads(m.group(3))))
    return found


EXAMPLES = examples()


def test_the_documents_carry_the_examples_the_adapter_depends_on():
    ids = {e[1] for e in EXAMPLES}
    assert {"getFeatures", "listWorkspaceLibraryFacets", "getWorkspaceLibraryItem", "getWorkItem", "listWorkItems", "listWorkItemEvents"} <= ids, ids


@pytest.mark.parametrize("doc,operation,status,example", EXAMPLES, ids=[f"{e[0]}:{e[1]}" for e in EXAMPLES])
def test_every_documented_example_matches_the_servers_openapi(doc, operation, status, example):
    problems = validate(example, response_schema(operation, status))
    assert not problems, f"{doc} / {operation}: " + "; ".join(problems)


# ---- the validator itself: it must notice the changes it exists to catch
SCHEMA = {"type": "object", "required": ["a", "b"], "properties": {"a": {"type": "string"}, "b": {"anyOf": [{"type": "integer"}, {"type": "null"}]}, "c": {"type": "array", "items": {"type": "boolean"}}}}


@pytest.mark.parametrize("value,fragment", [
    ({"a": "x", "b": 1}, None), ({"a": "x", "b": None, "c": [True]}, None),
    ({"b": 1}, "$.a: required"), ({"a": "x"}, "$.b: required"), ({"a": 1, "b": 1}, "expected a string"), ({"a": "x", "b": "1"}, "matches none"),
    ({"a": "x", "b": True}, "matches none"), ({"a": "x", "b": 1, "c": [1]}, "expected a boolean"), ({"a": "x", "b": 1, "renamed": 2}, "no longer has this field"),
    ([], "expected an object"),
])
def test_the_validator_catches_renamed_removed_and_retyped_fields(value, fragment):
    problems = validate(value, SCHEMA)
    if fragment is None:
        assert problems == []
    else:
        assert any(fragment in p for p in problems), problems


def test_a_changed_server_field_would_break_the_documented_example():
    spec = response_schema("getWorkItem", "200")
    good = next(e[3] for e in EXAMPLES if e[1] == "getWorkItem")
    assert validate(good, spec) == []
    renamed = {("asset_review_summary_v2" if k == "asset_review_summary" else k): v for k, v in good.items()}
    assert validate(renamed, spec), "a renamed field is noticed"
    retyped = {**good, "version": "3"}
    assert validate(retyped, spec), "a retyped field is noticed"
    missing = {k: v for k, v in good.items() if k != "assets"}
    assert validate(missing, spec), "a removed field is noticed"


# ---- two examples are also compared with what the server really answers
def test_the_features_example_has_exactly_the_names_the_server_returns(env):
    real = client.get("/v1/features", headers=auth("a")).json()
    documented = next(e[3] for e in EXAMPLES if e[1] == "getFeatures")
    assert set(real["features"]) == set(documented["features"]) == {"tryon", "character", "three_d", "video", "market"}
    assert validate(real, response_schema("getFeatures", "200")) == []
    for name, state in real["features"].items():
        assert set(state) == set(documented["features"][name]) == {"enabled", "status"}


def test_the_facets_example_has_the_servers_shape_and_a_real_answer_validates(env):
    import io
    from PIL import Image
    buf = io.BytesIO(); Image.new("RGB", (8, 8), (1, 2, 3)).save(buf, format="PNG")
    r = client.post("/v1/workspaces/wa/library", headers=auth("a"), data={"kind": "garment", "name": "x", "rights_confirmed": "true", "attrs": json.dumps({"category": "top", "size_no": 95, "colors": ["white", "beige"]})},
                    files={"file": ("a.png", buf.getvalue(), "image/png")})
    assert r.status_code == 201, r.text
    real = client.get("/v1/workspaces/wa/library/facets", headers=auth("a"), params={"kind": "garment"}).json()
    assert validate(real, response_schema("listWorkspaceLibraryFacets", "200")) == []
    assert real["kind"] == "garment" and {f["key"] for f in real["facets"]} == {"category", "colors", "size_no"}
    values = {f["key"]: {v["value"]: v["count"] for v in f["values"]} for f in real["facets"]}
    assert values == {"category": {"top": 1}, "colors": {"beige": 1, "white": 1}, "size_no": {"95": 1}}, "numbers come back as text, list values count per element"
    documented = next(e[3] for e in EXAMPLES if e[1] == "listWorkspaceLibraryFacets")
    assert set(documented) == set(real) and set(documented["facets"][0]) == set(real["facets"][0]) and set(documented["facets"][0]["values"][0]) == set(real["facets"][0]["values"][0])
    item = client.get("/v1/workspaces/wa/library", headers=auth("a")).json()["items"][0]
    assert validate(item, response_schema("getWorkspaceLibraryItem", "200")) == []
    assert set(item) == set(next(e[3] for e in EXAMPLES if e[1] == "getWorkspaceLibraryItem")), "the documented item has exactly the fields a real item has"


def test_a_real_work_item_answer_has_exactly_the_documented_fields(env):
    r = client.post("/v1/workspaces/wa/work-items", headers=auth("a"), json={"kind": "tryon", "title": "t", "status": "req", "attrs": {"sku": "S"}})
    assert r.status_code == 201
    documented = next(e[3] for e in EXAMPLES if e[1] == "getWorkItem")
    assert validate(r.json(), response_schema("getWorkItem", "200")) == [] and set(r.json()) == set(documented)
    listing = client.get("/v1/workspaces/wa/work-items", headers=auth("a")).json()
    assert validate(listing, response_schema("listWorkItems", "200")) == []
    ev = client.get(f"/v1/workspaces/wa/work-items/{r.json()['item_id']}/events", headers=auth("a")).json()
    assert validate(ev, response_schema("listWorkItemEvents", "200")) == [] and set(ev[0]) == set(next(e[3] for e in EXAMPLES if e[1] == "listWorkItemEvents")[0])
